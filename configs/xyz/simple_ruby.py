# import the m5 (gem5) library created when gem5 is built
import m5

# import all of the SimObjects
from m5.objects import *

m5.util.addToPath("../")
from argparse import ArgumentParser

from common.FileSystemConfig import config_filesystem
from msi_caches import MyCacheSystem

parser = ArgumentParser()
parser.add_argument("--ncore", type=int, help="Number of cores", required=True)
parser.add_argument(
    "--use-ziv", help="Use ZIV", default=False, action="store_true"
)
parser.add_argument(
    "--subslot-opt",
    help="Whether enabling subslot optimization",
    default=False,
    action="store_true",
)
parser.add_argument(
    "--use-vi", help="Use VI", default=False, action="store_true"
)
parser.add_argument(
    "--disable-roc", help="Disable ROC", default=False, action="store_true"
)
parser.add_argument("--relax-vi", help="VI relaxation", default=0)
parser.add_argument(
    "--wc",
    help="Work conserving round-robin",
    default=False,
    action="store_true",
)
parser.add_argument(
    "--split-bus",
    help="Split response bus",
    default=False,
    action="store_true",
)
parser.add_argument(
    "--write-through",
    help="Whether bypassing the LLC",
    default=False,
    action="store_true",
)
parser.add_argument("--program", type=str, help="Program to run")
parser.add_argument("--l1-size", type=str, help="L1 Size", default="4kB")
parser.add_argument("--l1-assoc", type=int, help="L1 Associativity", default=2)
parser.add_argument("--l2-assoc", type=int, help="L2 Association", default=2)
parser.add_argument("--l2-size", type=str, help="L2 Size", default="16kB")
parser.add_argument("--l2-latency", type=str, help="L2 latency", default="5")
parser.add_argument("--l3-size", type=str, help="L3 Size", default="2MB")
parser.add_argument("--l3-assoc", type=int, help="L3 Association", default=2)
parser.add_argument(
    "--cwd", type=str, help="Current working directory", default=None
)
# This number assumes a pipelined version of the bus, where each cycle we could issue 64-bit worth-of data per cycle
# This corresponds to a peak bandwidth (or throughput?) of 8B / 1ns ~ 8GB @ 1Ghz, which is reasonable for an on-chip communication device like a bus
parser.add_argument(
    "--resp-bus-latency",
    type=int,
    help="Response bus latency for sending one cache line worth-of data",
    default=9,
)
parser.add_argument(
    "--ruby-test", help="Ruby test", default=False, action="store_true"
)
parser.add_argument("--args", type=str, help="Arguments", default="")
parser.add_argument("--nreq", type=int, help="# of request", default=10000)
parser.add_argument("--wakeup-frequency", type=int, help="", default=10)
parser.add_argument("--input-file", type=str, help="", default=None)
parser.add_argument("--wb-buffer-size", type=int, help="", default=None)
parser.add_argument(
    "--c2c-latency", type=int, help="Cache to cache latency", default=1
)
parser.add_argument(
    "--slot-width",
    type=int,
    help="Slot width (only used for non-split)",
    default=128,
)
parser.add_argument(
    "--llc-end-latency", type=int, help="LLC latency", default=5
)
args = parser.parse_args()


# create the system we are going to simulate
system = System()

# Set the clock fequency of the system (and all of its children)
system.clk_domain = SrcClockDomain()
system.clk_domain.clock = "1GHz"
system.clk_domain.voltage_domain = VoltageDomain()

# Set up the system
system.mem_mode = "timing"  # Use timing accesses
system.mem_ranges = [AddrRange("16GB")]  # Create an address range
system.mem_ctrl = SimpleMemory(latency="100ns")  # 100 cycles under 2Ghz
system.mem_ctrl.range = system.mem_ranges[0]

traceFile = f"lock-traces/{args.ncore}_core_trace.txt"

# Create a pair of simple CPUs
if not args.ruby_test:
    system.cpu = [RiscvTimingSimpleCPU() for i in range(args.ncore)]
else:
    system.cpu = [TraceTester(id = i, traceFile = traceFile) for i in range (args.ncore)]
    #system.tester = WCLRubyTester(
    #    checks_to_complete=args.nreq,
    #    wakeup_frequency=args.wakeup_frequency,
    #    num_cpus=args.ncore,
    #    deadlock_threshold=50000,
    #)

# create the interrupt controller for the CPU and connect to the membus
if not args.ruby_test:
    for cpu in system.cpu:
        cpu.createInterruptController()

# Create the Ruby System

system_type = "tester" if args.ruby_test else "cpu"
system.caches = MyCacheSystem()
system.caches.setup(
    system,
    system.cpu, #if not args.ruby_test else system.tester,
    [system.mem_ctrl],
    l1size=args.l1_size,
    l1_assoc=args.l1_assoc,
    l2size=args.l2_size,
    l3size=args.l3_size,
    l2_assoc=args.l2_assoc,
    l3_assoc=args.l3_assoc,
    use_ziv=args.use_ziv,
    use_vi=args.use_vi,
    type_of_system=system_type,
    use_wc=args.wc,
    use_write_through=args.write_through,
    enforce_roc=not args.disable_roc,
    subslot_opt=args.subslot_opt,
    split_bus=args.split_bus,
    resp_bus_latency=args.resp_bus_latency,
    wb_buffer_size=args.wb_buffer_size,
    c2c_latency=args.c2c_latency,
    slot_width=args.slot_width,
    llc_latency=args.llc_end_latency,
)

# Run application and use the compiled ISA to find the binary
# grab the specific path to the binary
thispath = os.path.dirname(os.path.realpath(__file__))
# binary = os.path.join(
#    thispath,
#    "../../../",
#    "tests/test-progs/hello/bin/riscv/linux/hello",
# )

if not args.ruby_test:
    binary = args.program
    # Create a process for a simple "multi-threaded" application
    process = Process()
    process.cwd = "/working/gem5-zcllc/rundir" if not args.cwd else args.cwd
    if args.input_file:
        process.input = args.input_file
    # Set the command
    # cmd is a list which begins with the executable (like argv)
    process.cmd = [binary] + args.args.split(" ")
    # Set the cpu to use the process as its workload and create thread contexts
    for cpu in system.cpu:
        cpu.workload = process
        cpu.createThreads()

    system.workload = SEWorkload.init_compatible(binary)

    # Set up the pseudo file system for the threads function above
    config_filesystem(system)

    # set up the root SimObject and start the simulation
root = Root(full_system=False, system=system)

m5.ticks.setGlobalFrequency('1ns')
# instantiate all of the objects we've created above
m5.instantiate()

print("Beginning simulation!")
exit_event = m5.simulate()
print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")
