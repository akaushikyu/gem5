#!/usr/bin/env python3
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
        (Conditional mode only) Number of mixed blobs executed in a separate
        asm block when the post-LR branch fires (loaded value != expected).
        Each blob is a fixed sequence of 8 instructions (add, sub, xor, or,
        lw, sw, add, xor), so M blobs = 8*M instructions.  These blobs are
        outside the constrained LR/SC window.  Default: 0.

    --lr-fail-action ACTION
        (Conditional mode only) What the C++ wrapper does after executing the
        retry-fail blobs when the LR value fails the condition check:
          exit  – breaks out of the retry loop entirely. [default]
          retry – continues the retry loop, re-executing the LR/SC block.

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
from textwrap import (
    dedent,
    indent,
)

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
    ("or", "%[{a0}], %[{a0}], %[{a1}]"),
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
    ("add", "%[{a1}], %[{a1}], %[{a0}]", "arith"),
    ("sub", "%[{a0}], %[{a0}], %[{a1}]", "arith"),
    ("xor", "%[{a1}], %[{a1}], %[{a0}]", "arith"),
    ("or", "%[{a0}], %[{a0}], %[{a1}]", "arith"),
    ("lw", "%[{m1}], 64(%[{addr}])", "mem"),
    ("lw", "%[{m1}], 64(%[{addr}])", "mem"),
    ("add", "%[{a0}], %[{a0}], %[{m1}]", "chain"),
    ("xor", "%[{a1}], %[{a1}], %[{m1}]", "chain"),
]
assert len(_RETRY_BLOB_INSTRS) == RETRY_BLOB_SIZE


def retry_fail_blob(
    blob_index: int, arith0: str, arith1: str, addr: str, mem1: str
) -> list[str]:
    """Return the RETRY_BLOB_SIZE asm lines for one retry-fail blob (zero-indexed).

    arith0, arith1, addr, mem1 are asm operand names (not register names);
    the compiler allocates the actual registers via the constraint block.
    lw/sw access addr+64 — 64 bytes past the lock word.
    """
    lines = []
    for instr_idx, (mnemonic, operands, _kind) in enumerate(
        _RETRY_BLOB_INSTRS
    ):
        op = operands.format(a0=arith0, a1=arith1, addr=addr, m1=mem1)
        comment = (
            f"  //# retry-fail blob {blob_index + 1} instr {instr_idx + 1}"
        )
        lines.append(f'        "{mnemonic}  {op}\\n\\t"{comment}')
    return lines


def retry_fail_blobs(
    count: int, arith0: str, arith1: str, addr: str, mem1: str
) -> list[str]:
    """Return asm lines for *count* consecutive retry-fail blobs."""
    lines = []
    for b in range(count):
        lines += retry_fail_blob(b, arith0, arith1, addr, mem1)
    return lines


# --- Pre-LR store sequence (constant 8 stores to different cache lines) ----

# Number of stores issued immediately before each LR instruction.
NUM_PRE_LR_STORES = 8

# Each store targets a different cache line offset from %[addr].
# Offsets start at 64 (one cache line past the lock word) and step by 64,
# so the sequence covers eight distinct cache lines without touching the
# lock word at offset 0.
_PRE_LR_STORE_OFFSETS = [64 * (i + 1) for i in range(NUM_PRE_LR_STORES)]


def pre_lr_stores(addr: str) -> list[str]:
    """Return NUM_PRE_LR_STORES sw-zero lines, one per cache line offset.

    addr is the asm operand name for the LR/SC address (e.g. 'addr').
    sw uses the architectural zero register so no extra value constraint
    is needed.
    """
    lines = []
    for i, offset in enumerate(_PRE_LR_STORE_OFFSETS):
        comment = f"  //# pre-LR store {i + 1}: addr+{offset}"
        lines.append(f'        "sw zero, {offset}(%[{addr}])\\n\\t"{comment}')
    return lines


def build_asm_lines(
    *,
    conditional: bool,
    between: int,
    memorder: str,
) -> list[str]:
    """
    Build the raw asm lines for the constrained inner LR/SC block.

    This block contains NO backwards branches, satisfying the RISC-V
    architectural constraint on LR/SC sequences.  All retry logic is
    handled by the surrounding C++ loop.

    All registers use named %[name] constraint placeholders — no hard-coded
    register names appear in the asm string.

    Conditional flow (both exit and retry — inner block is identical):
    ------------------------------------------------------------------
      sw zero, 64(%[addr]) ... sw zero, 512(%[addr])  # pre-LR stores
      lr.w<mo>  %[lr_val], (%[addr])
      bne  %[lr_val], %[expected], 1f   # forward branch: skip SC if mismatch
      <between * BETWEEN_BLOB_SIZE arithmetic instrs>
      sc.w<mo>  %[sc_result], %[newval], (%[addr])
      1:                                # lr_val and sc_result readable by C++

    Unconditional flow:
    -------------------
      sw zero, 64(%[addr]) ... sw zero, 512(%[addr])  # pre-LR stores
      lr.w<mo>  %[lr_val], (%[addr])
      <between * BETWEEN_BLOB_SIZE arithmetic instrs>
      sc.w<mo>  %[sc_result], %[newval], (%[addr])
    """

    mo = memorder
    lines: list[str] = []

    lines += pre_lr_stores("addr")
    lines.append(f'        "lr.w  %[lr_val], (%[addr])\\n\\t"')

    if conditional:
        # Forward branch only: skip the SC entirely when the loaded value
        # does not match expected.  The C++ wrapper inspects lr_val after
        # the asm block and decides whether to retry or exit.
        lines.append(
            f'        "bne %[lr_val], %[expected], 1f\\n\\t"'
            f"  //# skip SC if loaded != expected"
        )
        lines += between_blobs(between, "arith0", "arith1")
        lines.append(
            f'        "sc.w.aqrl  %[sc_result], %[newval], (%[addr])\\n\\t"'
        )
        lines.append(f'        "1:\\n\\t"')
    else:
        lines += between_blobs(between, "arith0", "arith1")
        lines.append(
            f'        "sc.w.aqrl  %[sc_result], %[newval], (%[addr])\\n\\t"'
        )

    return lines


def make_retry_fail_asm_lines(retry_fail: int) -> list[str]:
    """
    Build asm lines for the retry-fail blob sequence.

    This is emitted as a separate asm block inside the C++ if-branch that
    handles the LR condition failure, keeping it outside the constrained
    LR/SC block entirely.
    """
    return retry_fail_blobs(retry_fail, "arith0", "arith1", "addr", "mem1")


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
#include "gem5/m5ops.h"

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
        memorder=memorder,
    )

    mode_tag = "conditional" if conditional else "unconditional"
    func_name = f"lrsc_{mode_tag}_between{between}"
    if conditional:
        func_name += f"_fail{retry_fail}_{lr_fail_action}"

    asm_body = "\n".join(asm_lines)

    # -------------------------------------------------------------------------
    # Shared constrained LR/SC asm block (all modes)
    # -------------------------------------------------------------------------
    # Named early-clobber outputs prevent the compiler aliasing any output
    # register with an input.  %[name] placeholders are used throughout —
    # no hard-coded register names appear in the asm string.
    #
    # The conditional block exports lr_val so the C++ wrapper can inspect
    # whether the LR condition passed before deciding to retry or exit.
    # sc_result is 0 on SC success, non-zero on failure.

    if conditional:
        # Shared asm block for both exit and retry.
        # sc_result is initialised to 1 so that if the bne skips the SC
        # (LR condition failed), sc_result reads as "failed" and the C++
        # wrapper can distinguish the two cases via lr_val.
        constrained_asm = dedent(
            f"""\
            int32_t lr_val = 0, sc_result = 1;
            int32_t arith_a = 1, arith_b = 2;
            const int32_t expected_val = 0;  // LR checks for 0
            const int32_t new_val      = 1;  // SC writes 1
            __asm__ volatile (
{asm_body}
                : [lr_val]    "=&r"(lr_val),
                  [sc_result] "=&r"(sc_result),
                  [arith0]    "=&r"(arith_a),
                  [arith1]    "=&r"(arith_b)
                : [addr]      "r"  (&g_counter),
                  [newval]    "r"  (new_val),
                  [expected]  "r"  (expected_val),
                  "2"(arith_a), "3"(arith_b)
                : "memory"
            );
        """
        )

        # Retry-fail blob asm block — emitted inside the C++ if-branch that
        # handles LR condition failure.  It is a separate unconstrained block
        # entirely outside the LR/SC reservation window.
        retry_fail_asm_lines = make_retry_fail_asm_lines(retry_fail)
        retry_fail_asm_body = "\n".join(retry_fail_asm_lines)
        retry_fail_asm = dedent(
            f"""\
            int32_t mem_val = 0;
            __asm__ volatile (
{retry_fail_asm_body}
                : [arith0] "+&r"(arith_a),
                  [arith1] "+&r"(arith_b),
                  [mem1]   "=&r"(mem_val)
                : [addr]   "r"  (&g_counter)
                : "memory"
            );
            (void)mem_val;
        """
        )

        if lr_fail_action == "exit":
            # C++ loop structure for exit mode:
            #
            #   while (true) {
            #     [constrained LR/SC asm]
            #     if (lr_val != expected_val) {
            #       [retry-fail blobs]   ← M blobs of 8 instrs each
            #       break;               ← exit: do not retry
            #     }
            #     if (sc_result == 0) {  ← SC succeeded
            #       sw zero resets addr
            #       break;
            #     }
            #     // sc_result != 0: SC failed, retry from top
            #   }
            loop_body = dedent(
                f"""\
                while (true) {{
                    {indent(constrained_asm, ' ' * 4).lstrip()}
                    if (lr_val != expected_val) {{
                        // LR loaded an unexpected value — run retry-fail blobs then exit.
                        {indent(retry_fail_asm, ' ' * 8).lstrip()}
                        break;
                    }}
                    if (sc_result == 0) {{
                        // SC succeeded — reset the lock word and exit.
                        __asm__ volatile ("sw zero, 0(%0)" :: "r"(&g_counter) : "memory");
                        break;
                    }}
                    // SC failed (reservation lost) — retry the LR/SC.
                }}
            """
            )
        else:  # retry
            # C++ loop structure for retry mode:
            #
            #   while (true) {
            #     [constrained LR/SC asm]
            #     if (lr_val != expected_val) {
            #       [retry-fail blobs]   ← M blobs of 8 instrs each
            #       continue;            ← retry: go back to LR
            #     }
            #     if (sc_result == 0) {  ← SC succeeded
            #       sw zero resets addr
            #       break;
            #     }
            #     // sc_result != 0: SC failed, retry from top
            #   }
            loop_body = dedent(
                f"""\
                while (true) {{
                    {indent(constrained_asm, ' ' * 4).lstrip()}
                    if (lr_val != expected_val) {{
                        // LR loaded an unexpected value — run retry-fail blobs then retry.
                        {indent(retry_fail_asm, ' ' * 8).lstrip()}
                        continue;
                    }}
                    if (sc_result == 0) {{
                        // SC succeeded — reset the lock word and exit.
                        __asm__ volatile ("sw zero, 0(%0)" :: "r"(&g_counter) : "memory");
                        break;
                    }}
                    // SC failed (reservation lost) — retry the LR/SC.
                }}
            """
            )

        loop_body_indented = indent(loop_body, " " * 8)

    else:  # unconditional
        asm_block = dedent(
            f"""\
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
        """
        )
        loop_body_indented = indent(asm_block, " " * 8)

    lines = [
        f"// {'Conditional' if conditional else 'Unconditional'} LR/SC sequence",
        f"// - Pre-LR stores (before each LR)            : {NUM_PRE_LR_STORES}"
        f" (sw zero to addr+64..addr+{64*NUM_PRE_LR_STORES}, one per cache line)",
        f"// - Between-blobs (LR branch → SC)            : {between}"
        f" ({between * BETWEEN_BLOB_SIZE} instrs, blob size = {BETWEEN_BLOB_SIZE})",
    ]
    if conditional:
        lines.append(
            f"// - Post-LR branch                            : bne "
            "(skips SC when loaded != 0; C++ loop handles retry/exit)"
        )
        lines.append(
            f"// - LR-fail action                            : {lr_fail_action} "
            f"({'retry LR' if lr_fail_action == 'retry' else 'exit loop'})"
        )
        lines.append(
            f"// - Retry-fail blobs (on LR condition failure) : {retry_fail}"
            f" ({retry_fail * RETRY_BLOB_SIZE} instrs, blob size = {RETRY_BLOB_SIZE})"
        )
        lines.append(
            f"// - SC writes                                 : 1 (then resets addr to 0 on success)"
        )
        lines.append(
            f"// - Constrained LR/SC block                   : no backwards branches"
        )
    lines.append(
        f"// - Memory ordering                            : lr.w{memorder} / sc.w{memorder}"
    )
    lines.append(
        f"// - Registers                                  : compiler-allocated via named constraints"
    )
    lines.append(f"//")
    lines.append(f"static void {func_name}(int iterations = {iterations}) {{")
    lines.append(f'    m5_add_symbol((uint64_t)&g_counter, "global");')
    lines.append(f"    for (int i = 0; i < iterations; ++i) {{")
    if not conditional:
        lines.append(
            f"        const int32_t new_val = i & 0x7fffffff;  // arbitrary store value"
        )
    lines.append(loop_body_indented.rstrip())
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

    return dedent(
        f"""\
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
    """
    )


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
        help="(Conditional only) What the C++ wrapper does after the retry-fail blobs "
        "when the LR value fails the condition: 'exit' breaks the retry loop; "
        "'retry' continues it (re-executes the LR/SC). (default: exit)",
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
            warnings.append(
                "--retry-fail is only meaningful with --conditional; it will be ignored."
            )
        if args.lr_fail_action != "exit":
            warnings.append(
                "--lr-fail-action is only meaningful with --conditional; it will be ignored."
            )

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
