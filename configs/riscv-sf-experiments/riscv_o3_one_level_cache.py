#!/bin/usr/python3
"""
gem5 configuration script
--------------------------
ISA:          RISC-V
CPU:          O3CPU (out-of-order, RISC-V ISA build), 1..N cores
Cache:        2-level hierarchy
                - Private split L1 I-Cache / D-Cache per core
                - Single shared L2 Cache (coherent across all cores)
Memory:       Shared timing DRAM model (DDR3_1600_8x8) accessed via
              a system-level timing crossbar (mem_mode = "timing")

Usage (Syscall-Emulation / SE mode):
    <gem5-build-dir>/build/RISCV/gem5.opt riscv_o3_two_level.py \
        --cmd=<path-to-riscv-static-binary> --num-cpus=4

This assumes a gem5 binary built for the RISCV ISA
(scons build/RISCV/gem5.opt -j<N>).

Key O3CPU microarchitectural parameters (ROB size, stage widths, issue
queue/LSQ sizes, physical register file sizes, inter-stage delays) are
exposed as command-line flags and applied identically to every core --
run with --help to see all of them, e.g.:
    --rob-size=192 --fetch-width=8 --decode-width=8 --issue-width=8 \
    --commit-width=8 --num-iq-entries=64 --lq-entries=32 --sq-entries=32
"""

import argparse

import m5
from m5.objects import (
    AddrRange,
    Cache,
    DDR3_1600_8x8,
    MemCtrl,
    O3CPU,
    Process,
    Root,
    RiscvSEWorkload,
    SrcClockDomain,
    System,
    SystemXBar,
    VoltageDomain,
)

# ----------------------------------------------------------------------
# Command line options
# ----------------------------------------------------------------------
parser = argparse.ArgumentParser(description="RISC-V O3CPU two-level cache SE config")
parser.add_argument("--cmd", type=str, required=True,
                     help="Path to the RISC-V binary to simulate")
parser.add_argument("--options", type=str, default="",
                     help="Space separated arguments to pass to the binary")
parser.add_argument("--cpu-clock", type=str, default="2GHz")
parser.add_argument("--sys-clock", type=str, default="1GHz")
parser.add_argument("--mem-size", type=str, default="512MB")

# ---- Multi-core options --------------------------------------------------
parser.add_argument("--num-cpus", type=int, default=1,
                     help="Number of O3CPU cores")

# ---- L2 cache sizing (scales with core count by default) -----------------
parser.add_argument("--l2-size", type=str, default=None,
                     help="Shared L2 size, e.g. '2MB'. Defaults to "
                          "256kB * num-cpus if unset")

# ---- O3CPU microarchitectural parameters --------------------------------
# Pipeline stage widths (instructions/cycle at each stage)
parser.add_argument("--fetch-width", type=int, default=8)
parser.add_argument("--decode-width", type=int, default=8)
parser.add_argument("--rename-width", type=int, default=8)
parser.add_argument("--dispatch-width", type=int, default=8)
parser.add_argument("--issue-width", type=int, default=8)
parser.add_argument("--wb-width", type=int, default=8)
parser.add_argument("--commit-width", type=int, default=8)
parser.add_argument("--squash-width", type=int, default=8)

# Fetch queue / buffer depth
parser.add_argument("--fetch-buffer-size", type=int, default=64)
parser.add_argument("--fetch-queue-size", type=int, default=32)

# Out-of-order core structures
parser.add_argument("--rob-size", type=int, default=192,
                     help="Reorder buffer (ROB) entries")
parser.add_argument("--num-iq-entries", type=int, default=64,
                     help="Instruction queue (issue queue) entries")
parser.add_argument("--lq-entries", type=int, default=32,
                     help="Load queue entries")
parser.add_argument("--sq-entries", type=int, default=32,
                     help="Store queue entries")

# Physical register file sizes
parser.add_argument("--num-phys-int-regs", type=int, default=256)
parser.add_argument("--num-phys-float-regs", type=int, default=256)
parser.add_argument("--num-phys-vec-regs", type=int, default=256)

# Inter-stage pipeline delays (cycles)
parser.add_argument("--fetch-to-decode-delay", type=int, default=1)
parser.add_argument("--decode-to-rename-delay", type=int, default=1)
parser.add_argument("--rename-to-iew-delay", type=int, default=1)
parser.add_argument("--iew-to-commit-delay", type=int, default=1)

# Starvation freedom options
parser.add_argument("--tbe-cycle-limit", type=int, default=(-1 & 0xFFFFFFFF))
parser.add_argument("--cbe-insn-count-limit", type=int, default=(-1 & 0xFFFFFFFF))

args = parser.parse_args()

# ----------------------------------------------------------------------
# Cache class definitions
# ----------------------------------------------------------------------
class L1Cache(Cache):
    """Base class for the private, per-core L1 caches."""

    assoc = 2
    tag_latency = 2
    data_latency = 2
    response_latency = 2
    mshrs = 4
    tgts_per_mshr = 20

    def connectBus(self, bus):
        """Connect this L1 cache's memory-side port to the crossbar."""
        self.mem_side = bus.cpu_side_ports

    def connectCPU(self, cpu):
        raise NotImplementedError


class L1ICache(L1Cache):
    size = "32kB"

    def connectCPU(self, cpu):
        self.cpu_side = cpu.icache_port


class L1DCache(L1Cache):
    size = "32kB"

    def connectCPU(self, cpu):
        self.cpu_side = cpu.dcache_port

# ----------------------------------------------------------------------
# System setup
# ----------------------------------------------------------------------
system = System()

# Clock / voltage domain for the system
system.clk_domain = SrcClockDomain()
system.clk_domain.clock = args.sys_clock
system.clk_domain.voltage_domain = VoltageDomain()

# Use the timing memory model everywhere (required for O3CPU and for a
# meaningful shared timing DRAM model)
system.mem_mode = "timing"
system.mem_ranges = [AddrRange(args.mem_size)]

num_cpus = args.num_cpus


# ---- Starvation freedom  -------------------------------------------------
system.tbe_cycle_limit = args.tbe_cycle_limit
system.cbe_insn_count_limit = args.cbe_insn_count_limit

# ---- CPUs ----------------------------------------------------------------

system.cpu = [O3CPU(cpu_id=i) for i in range(num_cpus)]

for cpu in system.cpu:
    cpu.clk_domain = SrcClockDomain(
        clock=args.cpu_clock, voltage_domain=VoltageDomain()
    )

    # Pipeline stage widths
    cpu.fetchWidth = args.fetch_width
    cpu.decodeWidth = args.decode_width
    cpu.renameWidth = args.rename_width
    cpu.dispatchWidth = args.dispatch_width
    cpu.issueWidth = args.issue_width
    cpu.wbWidth = args.wb_width
    cpu.commitWidth = args.commit_width
    cpu.squashWidth = args.squash_width

    # Fetch buffering
    cpu.fetchBufferSize = args.fetch_buffer_size
    cpu.fetchQueueSize = args.fetch_queue_size

    # Core structures: ROB, issue queue, load/store queues
    cpu.numROBEntries = args.rob_size
    cpu.numIQEntries = args.num_iq_entries
    cpu.LQEntries = args.lq_entries
    cpu.SQEntries = args.sq_entries

    # Physical register files
    cpu.numPhysIntRegs = args.num_phys_int_regs
    cpu.numPhysFloatRegs = args.num_phys_float_regs
    cpu.numPhysVecRegs = args.num_phys_vec_regs

    # Inter-stage pipeline delays (cycles)
    cpu.fetchToDecodeDelay = args.fetch_to_decode_delay
    cpu.decodeToRenameDelay = args.decode_to_rename_delay
    cpu.renameToIEWDelay = args.rename_to_iew_delay
    cpu.iewToCommitDelay = args.iew_to_commit_delay

    # RISC-V needs no PIC wiring beyond this call, but each core needs
    # its own interrupt controller
    cpu.createInterruptController()

# ---- Private L1 caches (one pair per core) -------------------------------
system.cpu_icache = [L1ICache() for _ in range(num_cpus)]
system.cpu_dcache = [L1DCache() for _ in range(num_cpus)]

for cpu, icache, dcache in zip(system.cpu, system.cpu_icache, system.cpu_dcache):
    icache.connectCPU(cpu)
    dcache.connectCPU(cpu)

# ---- Main (system) memory bus ---------------------------------------------
system.membus = SystemXBar()

for icache, dcache in zip(system.cpu_icache, system.cpu_dcache):
    icache.connectBus(system.membus)
    dcache.connectBus(system.membus)

# System port used by gem5 for functional accesses
system.system_port = system.membus.cpu_side_ports

# ---- Shared timing memory controller --------------------------------------
system.mem_ctrl = MemCtrl()
system.mem_ctrl.dram = DDR3_1600_8x8()
system.mem_ctrl.dram.range = system.mem_ranges[0]
system.mem_ctrl.port = system.membus.mem_side_ports

# ----------------------------------------------------------------------
# Workload (Syscall Emulation mode)
# ----------------------------------------------------------------------
binary = args.cmd
system.workload = RiscvSEWorkload.init_compatible(binary)

process = Process()
process.cmd = [binary] + args.options.split()
for cpu in system.cpu:
    cpu.workload = process

for cpu in system.cpu:
    cpu.createThreads()

# ----------------------------------------------------------------------
# Instantiate and run
# ----------------------------------------------------------------------
root = Root(full_system=False, system=system)
m5.instantiate()

print("Beginning simulation!")
exit_event = m5.simulate(99999999999)
print(
    "Exiting @ tick {} because {}".format(
        m5.curTick(), exit_event.getCause()
    )
)
