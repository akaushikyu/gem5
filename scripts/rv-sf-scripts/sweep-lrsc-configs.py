#!/usr/bin/env python3
"""
sweep.py - Python/multiprocessing port of sweep.sh

Generates the RISC-V LR/SC workloads, compiles them, then runs the full
gem5 configuration sweep (SF and NoSF, minor/o3, one/two-level cache,
cbe/tbe limited, unconditional / conditional-no-retry / conditional-retry).

Usage:
    python3 sweep.py NUM_CPUS [--dry-run] [--clean]

NUM_CPUS is the number of *host* CPU cores to spread the work across.
It is unrelated to the gem5 `--num-cpus`/`--threads` simulation parameters
below (those come from the sweep's own CPU-count axis, kept as `sim_cpu`
in the code to avoid confusion).

How the work is batched
------------------------
All simulation commands (~thousands, one per gem5 invocation) are collected
into a single flat list. That list is split into NUM_CPUS contiguous
batches. Each batch is handed to its own worker process and the commands
inside a batch run one-after-another (serially). The NUM_CPUS worker
processes themselves run concurrently, so you effectively get NUM_CPUS
simulations executing at once, each core chewing through its own queue.

Workload generation + compilation is treated as a separate, earlier phase
(also batched/parallelized the same way) so that every workload's .cpp/
binary exists before any gem5 run that depends on it is launched -
mixing that into the same batches as the gem5 runs could otherwise race
(a run could get scheduled on one core before compilation, running on a
different core, has finished).
"""

import argparse
import os
import shutil
import subprocess
import sys
from multiprocessing import Process, Queue

from tqdm import tqdm

# ----------------------------------------------------------------------
# Paths / binaries (unchanged from sweep.sh)
# ----------------------------------------------------------------------
GEN_SCRIPT = "scripts/rv-sf-scripts/gen_riscv_lrsc.py"
COMPILE_SCRIPT = "./scripts/rv-sf-scripts/compile.sh"
GEM5_SF = "./build/RISCV_NoRuby_SF/gem5.fast"
GEM5_NOSF = "./build/RISCV_NoRuby_NoSF/gem5.fast"

WORKLOAD_DIR = "rv-sf-workloads"
OUTPUT_DIR = "riscv-lrsc-exp"

CACHE_CONFIGS = [
    #("minor-one-level", "configs/riscv-sf-experiments/riscv_minor_one_level_cache.py"),
    ("minor-two-level", "configs/riscv-sf-experiments/riscv_minor_two_level_cache.py"),
    #("o3-one-level", "configs/riscv-sf-experiments/riscv_single_issue_o3_one_level_cache.py"),
    ("o3-two-level", "configs/riscv-sf-experiments/riscv_single_issue_o3_two_level_cache.py"),
]

# ----------------------------------------------------------------------
# Sweep axes (unchanged from sweep.sh)
# ----------------------------------------------------------------------
CPUS = [8, 4]
INSN_BETWEEN = [1, 2, 3, 4]

UNCOND_CBE = [1, 4, 8, 12, 16, 20, 50, 80, 100, 150]
UNCOND_TBE = [1, 2, 4, 8, 10, 20, 50, 80, 100, 150, 200, 300]

COND_EXIT_PATH = [1, 2, 4, 8, 12, 16, 20, 50]
COND_RETRY_PATH = [1, 2, 4, 8, 12, 16, 20, 50]
COND_CBE = [1, 4, 8, 12, 16, 20, 50, 100, 150]
COND_NORETRY_TBE = [1, 2, 4, 8, 10, 20, 50, 80, 100, 150, 200, 300]
# NOTE: sweep.sh's conditional-retry tbe list has a duplicated "10 10",
# kept as-is here for a faithful port (harmless - just runs that value twice).
COND_RETRY_TBE = [1, 2, 4, 8, 10, 20, 50, 80, 100, 150, 200, 300]


# ----------------------------------------------------------------------
# Workload + simulation command builders
# ----------------------------------------------------------------------
def gem5_cmd(binary, outdir, config, extra_flags, sim_cpu, cmd_cpp):
    return [
        binary, "-r", "-d", outdir, config,
        *extra_flags,
        "--num-cpus", str(sim_cpu), "--mem-size=8GB",
        "--cmd", cmd_cpp,
    ]


def build_unconditional_jobs():
    jobs = []
    for cpu in CPUS:
        for insn_between in INSN_BETWEEN:
            base = f"unconditional-threads-{cpu}-bb-{insn_between}"
            cmd_cpp = os.path.join(WORKLOAD_DIR, base)
            sim_cpu = cpu + 1

            gen_cmd = [
                "python3", GEN_SCRIPT, "--threads", str(cpu), "--iterations", "5000",
                "--unconditional", "--between", str(insn_between),
                "--output", cmd_cpp + ".cpp",
            ]
            compile_cmd = [COMPILE_SCRIPT, cmd_cpp]

            sims = []
            for cbe in UNCOND_CBE:
                for name, config in CACHE_CONFIGS:
                    outdir = os.path.join(
                        OUTPUT_DIR,
                        f"SF-uc-bb-{insn_between}-{name}-cbe-{cbe}-num-cpus-{cpu}")
                    sims.append((gem5_cmd(GEM5_SF, outdir, config,
                                           ["--cbe-insn-count-limit", str(cbe)],
                                           sim_cpu, cmd_cpp), outdir))
            for tbe in UNCOND_TBE:
                for name, config in CACHE_CONFIGS:
                    outdir = os.path.join(
                        OUTPUT_DIR,
                        f"SF-uc-bb-{insn_between}-{name}-tbe-{tbe}-num-cpus-{cpu}")
                    sims.append((gem5_cmd(GEM5_SF, outdir, config,
                                           ["--tbe-cycle-limit", str(tbe)],
                                           sim_cpu, cmd_cpp), outdir))
            for name, config in CACHE_CONFIGS:
                outdir = os.path.join(
                    OUTPUT_DIR, f"NOSF-uc-bb-{insn_between}-{name}-num-cpus-{cpu}")
                sims.append((gem5_cmd(GEM5_NOSF, outdir, config, [],
                                       sim_cpu, cmd_cpp), outdir))

            jobs.append({"gen_cmd": gen_cmd, "compile_cmd": compile_cmd, "sims": sims})
    return jobs


def build_conditional_jobs(retry: bool):
    """retry=False -> conditional-no-retry (lr-fail-action exit)
       retry=True  -> conditional-retry   (lr-fail-action retry)"""
    jobs = []
    path_values = COND_RETRY_PATH if retry else COND_EXIT_PATH
    tbe_values = COND_RETRY_TBE if retry else COND_NORETRY_TBE
    tag = "cr" if retry else "cnr"
    path_flag_char = "r" if retry else "e"  # rb-/eb- prefix in dir names
    lr_fail_action = "retry" if retry else "exit"
    prefix = "conditional-retry" if retry else "conditional-no-retry"

    for cpu in CPUS:
        for insn_between in INSN_BETWEEN:
            for path_val in path_values:
                base = f"{prefix}-threads-{cpu}-bb-{insn_between}-{path_flag_char}b-{path_val}"
                cmd_cpp = os.path.join(WORKLOAD_DIR, base)
                sim_cpu = cpu + 1

                gen_cmd = [
                    "python3", GEN_SCRIPT, "--threads", str(cpu), "--iterations", "5000",
                    "--conditional", "--between", str(insn_between),
                    "--retry-fail", str(path_val), "--lr-fail-action", lr_fail_action,
                    "--output", cmd_cpp + ".cpp",
                ]
                compile_cmd = [COMPILE_SCRIPT, cmd_cpp]

                sims = []
                for cbe in COND_CBE:
                    for name, config in CACHE_CONFIGS:
                        outdir = os.path.join(
                            OUTPUT_DIR,
                            f"SF-{tag}-bb-{insn_between}-{path_flag_char}b-{path_val}"
                            f"-{name}-cbe-{cbe}-num-cpus-{cpu}")
                        sims.append((gem5_cmd(GEM5_SF, outdir, config,
                                               ["--cbe-insn-count-limit", str(cbe)],
                                               sim_cpu, cmd_cpp), outdir))
                for tbe in tbe_values:
                    for name, config in CACHE_CONFIGS:
                        outdir = os.path.join(
                            OUTPUT_DIR,
                            f"SF-{tag}-bb-{insn_between}-{path_flag_char}b-{path_val}"
                            f"-{name}-tbe-{tbe}-num-cpus-{cpu}")
                        sims.append((gem5_cmd(GEM5_SF, outdir, config,
                                               ["--tbe-cycle-limit", str(tbe)],
                                               sim_cpu, cmd_cpp), outdir))
                for name, config in CACHE_CONFIGS:
                    outdir = os.path.join(
                        OUTPUT_DIR,
                        f"NOSF-{tag}-bb-{insn_between}-{path_flag_char}b-{path_val}"
                        f"-{name}-num-cpus-{cpu}")
                    sims.append((gem5_cmd(GEM5_NOSF, outdir, config, [],
                                           sim_cpu, cmd_cpp), outdir))

                jobs.append({"gen_cmd": gen_cmd, "compile_cmd": compile_cmd, "sims": sims})
    return jobs


# ----------------------------------------------------------------------
# Batched parallel execution
# ----------------------------------------------------------------------
def chunk(items, n):
    """Split items into n contiguous, roughly-equal batches."""
    n = max(1, n)
    k, m = divmod(len(items), n)
    batches = []
    start = 0
    for i in range(n):
        size = k + (1 if i < m else 0)
        if size:
            batches.append(items[start:start + size])
        start += size
    return batches


def _worker(batch, queue, dry_run, log_root):
    """Run every command in `batch` serially, reporting one queue item
    per completed command."""
    for cmd, outdir in batch:
        if dry_run:
            print("[dry-run]", " ".join(cmd))
        else:
            os.makedirs(outdir, exist_ok=True)
            log_path = os.path.join(outdir, "run.log")
            with open(log_path, "w") as log_file:
                subprocess.run(cmd, stdout=log_file, stderr=subprocess.STDOUT, check=False)
        queue.put(1)
    queue.put(None)  # sentinel: this worker is done


def run_batches(commands, num_cpus, dry_run, desc):
    """Split `commands` (list of (cmd, outdir)) into num_cpus batches,
    run each batch serially in its own process, batches run in parallel,
    and show a single progress bar for the total."""
    if not commands:
        return

    batches = chunk(commands, num_cpus)
    queue = Queue()
    procs = [
        Process(target=_worker, args=(batch, queue, dry_run, OUTPUT_DIR))
        for batch in batches
    ]
    for p in procs:
        p.start()

    total = len(commands)
    done_workers = 0
    with tqdm(total=total, desc=desc, unit="sim") as pbar:
        while done_workers < len(procs):
            item = queue.get()
            if item is None:
                done_workers += 1
            else:
                pbar.update(item)

    for p in procs:
        p.join()


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Run the RISC-V LR/SC gem5 sweep across NUM_CPUS host cores.")
    parser.add_argument("num_cpus", type=int,
                         help="Number of host CPU cores to parallelize across "
                              "(NOT the gem5 --num-cpus sweep axis).")
    parser.add_argument("--dry-run", action="store_true",
                         help="Print commands instead of running them "
                              "(equivalent to sweep.sh's -d).")
    parser.add_argument("--clean", action="store_true",
                         help="Remove the workloads directory and exit "
                              "(equivalent to sweep.sh's -c).")
    args = parser.parse_args()

    if args.clean:
        shutil.rmtree(WORKLOAD_DIR, ignore_errors=True)
        print(f"Removed {WORKLOAD_DIR}/")
        return

    if args.num_cpus < 1:
        parser.error("num_cpus must be >= 1")

    if not args.dry_run:
        os.makedirs(WORKLOAD_DIR, exist_ok=True)
        os.makedirs(OUTPUT_DIR, exist_ok=True)

    jobs = (
        build_unconditional_jobs() +
        #build_conditional_jobs(retry=False) +
        build_conditional_jobs(retry=True)
    )

    # --- Phase 1: generate + compile every workload -------------------
    gen_cmds = []
    compile_cmds = []
    for job in jobs:
        gen_cmds.append((job["gen_cmd"], WORKLOAD_DIR))
        compile_cmds.append((job["compile_cmd"], WORKLOAD_DIR))
    run_batches(gen_cmds, args.num_cpus, args.dry_run, desc="Generate")
    run_batches(compile_cmds, args.num_cpus, args.dry_run, desc="Compile")

    # --- Phase 2: run every gem5 simulation ----------------------------
    sim_cmds = [sim for job in jobs for sim in job["sims"]]
    run_batches(sim_cmds, args.num_cpus, args.dry_run, desc="Simulations")

    print(f"Done. {len(sim_cmds)} simulations across {len(jobs)} workloads "
          f"using {args.num_cpus} host cores.")

if __name__ == "__main__":
    main()
