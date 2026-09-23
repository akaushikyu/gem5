#!/usr/bin/python3
"""
gen_riscv_lrsc.py

Generates multi-threaded C++ functions containing RISC-V LR/SC instruction
sequences embedded via inline assembly.

Usage
-----
    python gen_riscv_lrsc.py [OPTIONS]

Options
-------
    --conditional / --unconditional
        Whether to generate a conditional LR/SC sequence or an unconditional
        one.  Default: unconditional.

    --between N
        Number of arithmetic blobs inserted between the post-LR conditional
        branch and SC (conditional mode), or directly between LR and SC
        (unconditional mode).  Each blob is a fixed sequence of 4 arithmetic
        instructions (add, sub, xor, or), so N blobs = 4*N instructions.
        Default: 0.

    --retry-fail M
        (Conditional mode only) Number of mixed blobs on the path taken when
        the post-LR conditional branch fires.  Each blob is a fixed sequence
        of 8 instructions (add, sub, xor, or, lw, sw, add, xor), so M blobs
        = 8*M instructions.  Blobs appear between the branch target and the
        next LR attempt (retry action) or before the done label (exit action).
        Default: 0.

    --lr-fail-action ACTION
        (Conditional mode only) What to do when the post-LR branch fires.
          exit  – branch jumps to lr_cond_fail and falls through to done
                  (exits the LR/SC loop entirely).  retry_fail blobs execute
                  on this path before done.  [default]
          retry – branch jumps back to lr_retry, which runs the retry_fail
                  blobs and then repeats the LR.  The loop only exits after a
                  successful SC.

    --memorder MO
        Memory ordering suffix appended to LR/SC mnemonics.
        Choices: (none), .aq, .rl, .aqrl.  Default: .aqrl.

    --output FILE
        Write the generated C++ to FILE.  If omitted, prints to stdout.

    --threads N
        Number of threads the generated test harness spawns.  Default: 4.

    --iterations N
        Number of loop iterations each thread executes.  Default: 1000000.

Examples
--------
    # Unconditional, 3 blobs (12 arithmetic instrs) between LR and SC
    python gen_riscv_lrsc.py --unconditional --between 3

    # Conditional: beq exits; 2 between blobs; 3 retry-fail blobs (24 instrs) on exit path
    python gen_riscv_lrsc.py --conditional --between 2 --retry-fail 3 --lr-fail-action exit

    # Conditional: beq retries LR; 2 between blobs; 4 retry-fail blobs before retry
    python gen_riscv_lrsc.py --conditional --between 2 --retry-fail 4 --lr-fail-action retry

    # Write to file
    python gen_riscv_lrsc.py --conditional --between 1 --retry-fail 2 --output out.cpp
"""

import argparse
import sys
from textwrap import indent, dedent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Blob definitions
# ---------------------------------------------------------------------------

# --- Between-LR-and-SC blob (pure arithmetic, size 4) ---------------------

# Fixed size of each between-blob (number of instructions).
BETWEEN_BLOB_SIZE = 4

# Four arithmetic instructions forming one between-blob.  They operate on
# %[arith0] and %[arith1] and form a true dependency chain so the hardware
# cannot collapse them.
#
#   add  %[arith1], %[arith1], %[arith0]
#   sub  %[arith0], %[arith0], %[arith1]
#   xor  %[arith1], %[arith1], %[arith0]
#   or   %[arith0], %[arith0], %[arith1]
_BETWEEN_BLOB_INSTRS = [
    ("add", "%[{a1}], %[{a1}], %[{a0}]"),
    ("sub", "%[{a0}], %[{a0}], %[{a1}]"),
    ("xor", "%[{a1}], %[{a1}], %[{a0}]"),
    ("or",  "%[{a0}], %[{a0}], %[{a1}]"),
]
assert len(_BETWEEN_BLOB_INSTRS) == BETWEEN_BLOB_SIZE


def arith_blob(blob_index: int, arith0: str, arith1: str) -> list[str]:
    """Return the BETWEEN_BLOB_SIZE asm lines for one between-blob (zero-indexed).

    arith0, arith1 are the asm operand names (e.g. 'arith0', 'arith1'),
    not register names — the compiler allocates the actual registers.
    """
    lines = []
    for instr_idx, (mnemonic, operands) in enumerate(_BETWEEN_BLOB_INSTRS):
        op = operands.format(a0=arith0, a1=arith1)
        comment = f"  //# between blob {blob_index + 1} instr {instr_idx + 1}"
        lines.append(f'        "{mnemonic}  {op}\\n\\t"{comment}')
    return lines


def between_blobs(count: int, arith0: str, arith1: str) -> list[str]:
    """Return asm lines for *count* consecutive between-blobs."""
    lines = []
    for b in range(count):
        lines += arith_blob(b, arith0, arith1)
    return lines


# --- Retry-fail blob (arithmetic + memory, size 8) ------------------------

# Fixed size of each retry-fail blob (number of instructions).
RETRY_BLOB_SIZE = 8

# Eight instructions forming one retry-fail blob.  The first four are
# arithmetic (same pattern as the between-blob, reusing arith0/arith1).
# The last four are memory operations:
#   - lw/sw use a 64-byte offset from the LR/SC address (%[addr]) so they
#     access a neighbouring cache line without disturbing the lock word.
#   - mem1 holds the loaded/stored value and is folded back into the
#     arithmetic chain to maintain data dependencies.
#
#   add  %[arith1], %[arith1], %[arith0]
#   sub  %[arith0], %[arith0], %[arith1]
#   xor  %[arith1], %[arith1], %[arith0]
#   or   %[arith0], %[arith0], %[arith1]
#   lw   %[mem1],  64(%[addr])
#   sw   %[mem1],  64(%[addr])
#   add  %[arith0], %[arith0], %[mem1]
#   xor  %[arith1], %[arith1], %[mem1]
#
# mem1 is an early-clobber output register for the loaded value.
# The address register (addr) is already an input to the enclosing asm block.
_RETRY_BLOB_INSTRS = [
    ("add", "%[{a1}], %[{a1}], %[{a0}]",    "arith"),
    ("sub", "%[{a0}], %[{a0}], %[{a1}]",    "arith"),
    ("xor", "%[{a1}], %[{a1}], %[{a0}]",    "arith"),
    ("or",  "%[{a0}], %[{a0}], %[{a1}]",    "arith"),
    ("lw",  "%[{m1}], 64(%[{addr}])",       "mem"),
    ("sw",  "%[{m1}], 64(%[{addr}])",       "mem"),
    ("add", "%[{a0}], %[{a0}], %[{m1}]",    "chain"),
    ("xor", "%[{a1}], %[{a1}], %[{m1}]",    "chain"),
]
assert len(_RETRY_BLOB_INSTRS) == RETRY_BLOB_SIZE


def retry_fail_blob(blob_index: int, arith0: str, arith1: str,
                    addr: str, mem1: str) -> list[str]:
    """Return the RETRY_BLOB_SIZE asm lines for one retry-fail blob (zero-indexed).

    arith0, arith1, addr, mem1 are asm operand names (not register names);
    the compiler allocates the actual registers via the constraint block.
    lw/sw access addr+64 — 64 bytes past the lock word.
    """
    lines = []
    for instr_idx, (mnemonic, operands, _kind) in enumerate(_RETRY_BLOB_INSTRS):
        op = operands.format(a0=arith0, a1=arith1, addr=addr, m1=mem1)
        comment = f"  //# retry-fail blob {blob_index + 1} instr {instr_idx + 1}"
        lines.append(f'        "{mnemonic}  {op}\\n\\t"{comment}')
    return lines


def retry_fail_blobs(count: int, arith0: str, arith1: str,
                     addr: str, mem1: str) -> list[str]:
    """Return asm lines for *count* consecutive retry-fail blobs."""
    lines = []
    for b in range(count):
        lines += retry_fail_blob(b, arith0, arith1, addr, mem1)
    return lines


def build_asm_lines(
    *,
    conditional: bool,
    between: int,
    retry_fail: int,
    lr_fail_action: str,
    memorder: str,
) -> list[str]:
    """
    Build the raw asm string lines (no surrounding C boilerplate).

    All registers are referenced via named constraint placeholders (%[name])
    so the compiler allocates them — no hard-coded register names appear in
    the asm string.

    Between the post-LR branch and SC: *between* arithmetic blobs
    (each = BETWEEN_BLOB_SIZE=4 instrs: add, sub, xor, or).

    On the LR-condition-fail path: *retry_fail* mixed blobs
    (each = RETRY_BLOB_SIZE=8 instrs: add, sub, xor, or, lw, sw, add, xor).

    Conditional flow — lr_fail_action="exit"
    -----------------------------------------
      retry:
        lr.w<mo>  %[lr_val], (%[addr])
        bne %[lr_val], %[expected], lr_cond_fail
        <between * BETWEEN_BLOB_SIZE arithmetic instrs>
        sc.w<mo>  %[sc_result], %[newval], (%[addr])
        bnez %[sc_result], sc_fail
        sw zero, 0(%[addr])
        j done
      sc_fail:
        j retry
      lr_cond_fail:
        <retry_fail * RETRY_BLOB_SIZE mixed instrs>
      done:

    Conditional flow — lr_fail_action="retry"
    ------------------------------------------
      lr_retry:
        <retry_fail * RETRY_BLOB_SIZE mixed instrs>
      retry:
        lr.w<mo>  %[lr_val], (%[addr])
        bne %[lr_val], %[expected], lr_retry
        <between * BETWEEN_BLOB_SIZE arithmetic instrs>
        sc.w<mo>  %[sc_result], %[newval], (%[addr])
        bnez %[sc_result], sc_fail
        sw zero, 0(%[addr])
        j done
      sc_fail:
        j retry
      done:

    Unconditional flow
    ------------------
        lr.w<mo>  %[lr_val], (%[addr])
        <between * BETWEEN_BLOB_SIZE arithmetic instrs>
        sc.w<mo>  %[sc_result], %[newval], (%[addr])
    """

    mo = memorder
    lines: list[str] = []

    if conditional:
        if lr_fail_action == "retry":
            lines.append('        "lr_retry_%=:\\n\\t"')
            lines += retry_fail_blobs(retry_fail, "arith0", "arith1", "addr", "mem1")
            lines.append('        "retry_%=:\\n\\t"')
            lines.append(f'        "lr.w{mo}  %[lr_val], (%[addr])\\n\\t"')
            lines.append(
                f'        "bne %[lr_val], %[expected], lr_retry_%=\\n\\t"'
                f'  //# retry LR if loaded != expected (expected == 0)'
            )
            lines += between_blobs(between, "arith0", "arith1")
            lines.append(f'        "sc.w{mo}  %[sc_result], %[newval], (%[addr])\\n\\t"')
            lines.append(f'        "bnez %[sc_result], sc_fail_%=\\n\\t"')
            lines.append(f'        "sw zero, 0(%[addr])\\n\\t"'
                         f'  //# SC succeeded: reset address to 0')
            lines.append('        "j done_%=\\n\\t"')
            lines.append('        "sc_fail_%=:\\n\\t"')
            lines.append('        "j retry_%=\\n\\t"')
            lines.append('        "done_%=:\\n\\t"')
        else:  # lr_fail_action == "exit"
            lines.append('        "retry_%=:\\n\\t"')
            lines.append(f'        "lr.w{mo}  %[lr_val], (%[addr])\\n\\t"')
            lines.append(
                f'        "bne %[lr_val], %[expected], lr_cond_fail_%=\\n\\t"'
                f'  //# exit if loaded != expected (expected == 0)'
            )
            lines += between_blobs(between, "arith0", "arith1")
            lines.append(f'        "sc.w{mo}  %[sc_result], %[newval], (%[addr])\\n\\t"')
            lines.append(f'        "bnez %[sc_result], sc_fail_%=\\n\\t"')
            lines.append(f'        "sw zero, 0(%[addr])\\n\\t"'
                         f'  //# SC succeeded: reset address to 0')
            lines.append('        "j done_%=\\n\\t"')
            lines.append('        "sc_fail_%=:\\n\\t"')
            lines.append('        "j retry_%=\\n\\t"')
            lines.append('        "lr_cond_fail_%=:\\n\\t"')
            lines += retry_fail_blobs(retry_fail, "arith0", "arith1", "addr", "mem1")
            lines.append('        "done_%=:\\n\\t"')
    else:
        lines.append(f'        "lr.w{mo}  %[lr_val], (%[addr])\\n\\t"')
        lines += between_blobs(between, "arith0", "arith1")
        lines.append(f'        "sc.w{mo}  %[sc_result], %[newval], (%[addr])\\n\\t"')

    return lines


# ---------------------------------------------------------------------------
# C++ code generators
# ---------------------------------------------------------------------------

HEADER = """\
// AUTO-GENERATED by gen_riscv_lrsc.py
// DO NOT EDIT MANUALLY
//
// Target ISA : RISC-V (rv32/rv64 with A extension)
// Toolchain  : riscv64-linux-gnu (Linux, pthreads)
//
// Compile example:
//   riscv64-linux-gnu-g++ -O2 -march=rv64imac -pthread {filename} -o {stem}

#include <cstdint>
#include <cstdio>
#include <thread>
#include <vector>

// Shared counter exercised by the LR/SC sequences.
static volatile int32_t g_counter = 0;

"""


def make_lrsc_function(
    *,
    conditional: bool,
    between: int,
    retry_fail: int,
    lr_fail_action: str,
    memorder: str,
    iterations: int,
) -> str:
    """Generate the C++ function string."""

    asm_lines = build_asm_lines(
        conditional=conditional,
        between=between,
        retry_fail=retry_fail,
        lr_fail_action=lr_fail_action,
        memorder=memorder,
    )

    mode_tag = "conditional" if conditional else "unconditional"
    func_name = f"lrsc_{mode_tag}_between{between}"
    if conditional:
        func_name += f"_fail{retry_fail}_{lr_fail_action}"

    asm_body = "\n".join(asm_lines)

    # All output registers use named early-clobber constraints ("=&r") so the
    # compiler allocates non-overlapping registers for every operand.
    # No register names appear in the asm string — %[name] placeholders are
    # used throughout, letting both GCC and Clang assign registers freely.
    if conditional:
        if lr_fail_action == "exit":
            asm_block = dedent(f"""\
                int32_t lr_val, sc_result, arith_a = 1, arith_b = 2;
                int32_t mem_val = 0;
                const int32_t expected_val = 0;  // LR checks for 0
                const int32_t new_val      = 1;  // SC writes 1
                __asm__ volatile (
{asm_body}
                    : [lr_val]    "=&r"(lr_val),
                      [sc_result] "=&r"(sc_result),
                      [arith0]    "=&r"(arith_a),
                      [arith1]    "=&r"(arith_b),
                      [mem1]      "=&r"(mem_val)
                    : [addr]      "r"  (&g_counter),
                      [newval]    "r"  (new_val),
                      [expected]  "r"  (expected_val),
                      "3"(arith_a), "4"(arith_b)
                    : "memory"
                );
                (void)lr_val;
                (void)sc_result;
                (void)arith_a;
                (void)arith_b;
                (void)mem_val;
            """)
        else:  # retry
            asm_block = dedent(f"""\
                int32_t lr_val, sc_result, arith_a = 1, arith_b = 2;
                int32_t mem_val = 0;
                const int32_t expected_val = 0;  // LR checks for 0
                const int32_t new_val      = 1;  // SC writes 1
                __asm__ volatile (
{asm_body}
                    : [lr_val]    "=&r"(lr_val),
                      [sc_result] "=&r"(sc_result),
                      [arith0]    "=&r"(arith_a),
                      [arith1]    "=&r"(arith_b),
                      [mem1]      "=&r"(mem_val)
                    : [addr]      "r"  (&g_counter),
                      [newval]    "r"  (new_val),
                      [expected]  "r"  (expected_val),
                      "3"(arith_a), "4"(arith_b)
                    : "memory"
                );
                (void)lr_val;
                (void)sc_result;
                (void)arith_a;
                (void)arith_b;
                (void)mem_val;
            """)
    else:
        asm_block = dedent(f"""\
            int32_t lr_val, sc_result, arith_a = 1, arith_b = 2;
            __asm__ volatile (
{asm_body}
                : [lr_val]    "=&r"(lr_val),
                  [sc_result] "=&r"(sc_result),
                  [arith0]    "=&r"(arith_a),
                  [arith1]    "=&r"(arith_b)
                : [addr]      "r"  (&g_counter),
                  [newval]    "r"  (new_val),
                  "2"(arith_a), "3"(arith_b)
                : "memory"
            );
            (void)lr_val;
            (void)sc_result;
            (void)arith_a;
            (void)arith_b;
        """)

    loop_body = indent(asm_block, " " * 8)

    lines = [
        f"// {'Conditional' if conditional else 'Unconditional'} LR/SC sequence",
        f"// - Between-blobs (LR branch → SC)            : {between}"
        f" ({between * BETWEEN_BLOB_SIZE} instrs, blob size = {BETWEEN_BLOB_SIZE})",
    ]
    if conditional:
        lines.append(f"// - Post-LR conditional branch                : bne "
                     + ("(LR checks loaded == 0; retries if loaded != 0)"
                        if lr_fail_action == "retry"
                        else "(LR checks loaded == 0; exits if loaded != 0)"))
        lines.append(f"// - LR-fail action                            : {lr_fail_action} "
                     f"({'retry LR' if lr_fail_action == 'retry' else 'exit loop'})")
        lines.append(f"// - Retry-fail blobs (LR-condition-fail path) : {retry_fail}"
                     f" ({retry_fail * RETRY_BLOB_SIZE} instrs, blob size = {RETRY_BLOB_SIZE},"
                     f" {'before LR retry' if lr_fail_action == 'retry' else 'before done'})")
        lines.append(f"// - SC writes                                 : 1 (then resets addr to 0 on success)")
    lines.append(f"// - Memory ordering                            : lr.w{memorder} / sc.w{memorder}")
    lines.append(f"// - Registers                                  : compiler-allocated via named constraints")
    lines.append(f"//")
    lines.append(f"static void {func_name}(int iterations = {iterations}) {{")
    lines.append(f"    for (int i = 0; i < iterations; ++i) {{")
    if not conditional:
        lines.append(f"        const int32_t new_val = i & 0x7fffffff;  // arbitrary store value")
    lines.append(loop_body.rstrip())
    lines.append(f"    }}")
    lines.append(f"}}")
    lines.append(f"")

    return "\n".join(lines)


def make_main(
    *,
    conditional: bool,
    between: int,
    retry_fail: int,
    lr_fail_action: str,
    threads: int,
    iterations: int,
) -> str:
    """Generate a main() that spawns std::thread workers."""

    mode_tag = "conditional" if conditional else "unconditional"
    func_name = f"lrsc_{mode_tag}_between{between}"
    if conditional:
        func_name += f"_fail{retry_fail}_{lr_fail_action}"

    return dedent(f"""\
        int main() {{
            constexpr int kThreads    = {threads};
            constexpr int kIterations = {iterations};

            printf("Spawning %d threads, each running %d LR/SC iterations...\\n",
                   kThreads, kIterations);

            std::vector<std::thread> workers;
            workers.reserve(kThreads);

            for (int t = 0; t < kThreads; ++t) {{
                workers.emplace_back({func_name}, kIterations);
            }}

            for (auto& w : workers) w.join();

            printf("Done. g_counter final value: %d\\n", g_counter);
            return 0;
        }}
    """)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate multi-threaded C++ with RISC-V LR/SC inline asm.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--conditional",
        dest="conditional",
        action="store_true",
        default=False,
        help="Generate a conditional LR/SC sequence with a post-LR branch.",
    )
    mode.add_argument(
        "--unconditional",
        dest="conditional",
        action="store_false",
        help="Generate an unconditional (single-attempt) LR/SC sequence. (default)",
    )

    p.add_argument(
        "--between",
        type=int,
        default=0,
        metavar="N",
        help=f"Number of arithmetic blobs between the post-LR branch and SC "
             f"(conditional), or between LR and SC (unconditional). "
             f"Each blob = {BETWEEN_BLOB_SIZE} instructions (add, sub, xor, or). (default: 0)",
    )
    p.add_argument(
        "--retry-fail",
        type=int,
        default=0,
        metavar="M",
        help=f"(Conditional only) Number of mixed blobs on the LR-condition-fail "
             f"path: before the next LR attempt (retry action) or before done "
             f"(exit action). Each blob = {RETRY_BLOB_SIZE} instructions "
             f"(add, sub, xor, or, lw, sw, add, xor). (default: 0)",
    )
    p.add_argument(
        "--lr-fail-action",
        default="exit",
        choices=["exit", "retry"],
        metavar="ACTION",
        help="(Conditional only) What to do when the post-LR branch fires: "
             "'exit' jumps to lr_cond_fail then done (retry_fail blobs run before done); "
             "'retry' jumps back to lr_retry and repeats the LR (retry_fail blobs run "
             "before each LR attempt). (default: exit)",
    )
    p.add_argument(
        "--memorder",
        default=".aqrl",
        choices=["", ".aq", ".rl", ".aqrl"],
        metavar="MO",
        help="Memory ordering suffix for LR/SC (none | .aq | .rl | .aqrl). "
             "(default: .aqrl)",
    )
    p.add_argument(
        "--output",
        default=None,
        metavar="FILE",
        help="Output file path. Omit to print to stdout.",
    )
    p.add_argument(
        "--threads",
        type=int,
        default=4,
        metavar="N",
        help="Number of threads the test harness spawns. (default: 4)",
    )
    p.add_argument(
        "--iterations",
        type=int,
        default=1_000_000,
        metavar="N",
        help="Loop iterations per thread. (default: 1000000)",
    )

    return p.parse_args(argv)


def validate(args: argparse.Namespace) -> None:
    errors = []
    warnings = []

    if args.between < 0:
        errors.append("--between must be >= 0")
    if args.retry_fail < 0:
        errors.append("--retry-fail must be >= 0")
    if args.threads < 1:
        errors.append("--threads must be >= 1")
    if args.iterations < 1:
        errors.append("--iterations must be >= 1")
    if not args.conditional:
        if args.retry_fail != 0:
            warnings.append("--retry-fail is only meaningful with --conditional; it will be ignored.")
        if args.lr_fail_action != "exit":
            warnings.append("--lr-fail-action is only meaningful with --conditional; it will be ignored.")

    for w in warnings:
        print(f"Warning: {w}", file=sys.stderr)
    if errors:
        for e in errors:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def generate(args: argparse.Namespace) -> str:
    output_filename = args.output or "<stdout>"
    stem = output_filename.replace(".cpp", "").replace(".cc", "")

    parts = [
        HEADER.format(filename=output_filename, stem=stem),
        make_lrsc_function(
            conditional=args.conditional,
            between=args.between,
            retry_fail=args.retry_fail if args.conditional else 0,
            lr_fail_action=args.lr_fail_action,
            memorder=args.memorder,
            iterations=args.iterations,
        ),
        make_main(
            conditional=args.conditional,
            between=args.between,
            retry_fail=args.retry_fail if args.conditional else 0,
            lr_fail_action=args.lr_fail_action,
            threads=args.threads,
            iterations=args.iterations,
        ),
    ]
    return "".join(parts)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    validate(args)
    code = generate(args)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(code)
        print(f"Written to {args.output}", file=sys.stderr)
    else:
        print(code)


if __name__ == "__main__":
    main()
