#!/bin/usr/python3
"""
gem5 configuration script
--------------------------
ISA:          RISC-V
CPU:          MinorCPU
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
"""

import argparse

import m5
from m5.objects import (
    AddrRange,
    Cache,
    DDR3_1600_8x8,
    MemCtrl,
    MinorCPU,
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
parser = argparse.ArgumentParser(description="RISC-V MinorCPU one-level cache SE config")
parser.add_argument("--cmd", type=str, required=True,
                     help="Path to the RISC-V binary to simulate")
parser.add_argument("--options", type=str, default="",
                     help="Space separated arguments to pass to the binary")
parser.add_argument("--cpu-clock", type=str, default="2GHz")
parser.add_argument("--sys-clock", type=str, default="1GHz")
parser.add_argument("--mem-size", type=str, default="512MB")

# ---- Multi-core options --------------------------------------------------
parser.add_argument("--num-cpus", type=int, default=1,
                     help="Number of MinorCPU cores")
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

# Use the timing memory model everywhere (required for MinorCPU and for a
# meaningful shared timing DRAM model)
system.mem_mode = "timing"
system.mem_ranges = [AddrRange(args.mem_size)]

num_cpus = args.num_cpus


# ---- Starvation freedom  -------------------------------------------------
system.tbe_cycle_limit = args.tbe_cycle_limit
system.cbe_insn_count_limit = args.cbe_insn_count_limit

# ---- CPUs ----------------------------------------------------------------

system.cpu = [MinorCPU(cpu_id=i) for i in range(num_cpus)]

for cpu in system.cpu:
    cpu.clk_domain = SrcClockDomain(
        clock=args.cpu_clock, voltage_domain=VoltageDomain()
    )

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
exit_event = m5.simulate()
print(
    "Exiting @ tick {} because {}".format(
        m5.curTick(), exit_event.getCause()
    )
)
