""" This file creates a set of Ruby caches, the Ruby network, and a simple
point-to-point topology.
See Part 3 in the Learning gem5 book:
http://gem5.org/documentation/learning_gem5/part3/MSIintro

IMPORTANT: If you modify this file, it's likely that the Learning gem5 book
           also needs to be updated. For now, email Jason <jason@lowepower.com>

"""

import math
from dataclasses import dataclass

from m5.defines import buildEnv
from m5.objects import *
from m5.util import (
    fatal,
    panic,
)


def get_wcl(
    ncore, slot_width, use_ziv, use_vi, disable_roc, wc, subslot_opt, split_bus
):
    if split_bus:
        return (1 << 64) - 1
    if not use_vi and use_ziv:  # xyz
        return (ncore + 1) * ncore * slot_width  # one extra period for put
    if use_vi and use_ziv:
        return 2 * ncore * slot_width


class MyCacheSystem(RubySystem):

    def getBlockSizeBits(self, system):
        bits = int(math.log(system.cache_line_size, 2))
        if 2**bits != system.cache_line_size.value:
            panic("Cache line size not a power of 2!")
        return bits

    def __init__(self):
        if buildEnv["PROTOCOL"] not in [
            "LC_MSI",
            "LC_MSI_ql",
            "Baseline_LC_MSI",
        ]:
            fatal("This system assumes MSI from learning gem5!")

        super().__init__()

    def setup(
        self,
        system,
        cpus_or_testers,
        mem_ctrls,
        l1size,
        l1_assoc,
        l2size,
        l3size,
        l2_assoc,
        l3_assoc,
        use_ziv,
        use_vi,
        type_of_system,
        use_wc,
        use_write_through,
        enforce_roc,
        **kwargs
    ):
        """Set up the Ruby cache subsystem. Note: This can't be done in the
        constructor because many of these items require a pointer to the
        ruby system (self). This causes infinite recursion in initialize()
        if we do this in the __init__.
        """
        # parse parameters
        subslot_opt = kwargs["subslot_opt"]
        split_bus = kwargs["split_bus"]
        resp_bus_latency = kwargs["resp_bus_latency"]
        wb_buffer_size = kwargs["wb_buffer_size"]
        slot_width = kwargs["slot_width"]
        llc_latency = kwargs["llc_latency"]

        # assert not use_write_through, "Write though not supported"
        # assert not use_wc, "WCRR not supported"
        assert type_of_system in ["tester", "cpu"]

        # Ruby's global network.
        self.network = MyNetwork(self)
        num_agents = None
        num_agents = len(cpus_or_testers)
        #if type_of_system == "tester":
        #    num_agents = cpus_or_testers.num_cpus
        #elif type_of_system == "cpu":
        #    num_agents = len(cpus_or_testers)

        # MSI uses 3 virtual networks. One for requests (lowest priority), one
        # for responses (highest priority), and one for "forwards" or
        # cache-to-cache requests. See *.sm files for details.
        # We have another for RoC
        self.number_of_virtual_networks = 7
        self.network.number_of_virtual_networks = 7

        private_total = (
            MemorySize(l2size) * num_agents
        ) / self.block_size_bytes
        l1s = [
            L0Cache(
                system,
                self,
                cpus_or_testers[i] if type_of_system == "cpu" else self,
                l1_assoc,
                size=l1size,
            )
            for i in range(num_agents)
        ]

        # There is a single global list of all of the controllers to make it
        # easier to connect everything to the global network. This can be
        # customized depending on the topology/network requirements.
        # Create one controller for each L1 cache (and the cache mem obj.)
        # Create a single directory controller (Really the memory cntrl)
        self.controllers = (
            l1s
            + [
                L1Cache(
                    system,
                    self,
                    cpus_or_testers[i] if type_of_system == "cpu" else self,
                    l2_assoc,
                    size=l2size,
                    l0=l1s[i],
                    split_bus=split_bus,
                    resp_bus_latency=resp_bus_latency,
                )
                for i in range(num_agents)
            ]
            + [
                DirController(
                    self,
                    system.mem_ranges,
                    mem_ctrls,
                    self.getBlockSizeBits(system),
                    num_agents,
                    l2_assoc,
                    private_total,
                    use_ziv,
                    use_vi,
                    size=l3size,
                    use_write_through=use_write_through,
                    enforce_roc=enforce_roc,
                    assoc=l3_assoc,
                    resp_bus_latency=resp_bus_latency,
                    split_bus=split_bus,
                    wb_buffer_size=wb_buffer_size,
                )
            ]
        )  # 256 corresponds to 16kB L2, 64B CL
        # 4 corresponds to 256B

        # Create one sequencer per CPU. In many systems this is more
        # complicated since you have to create sequencers for DMA controllers
        # and other controllers, too.
        self.sequencers = [
            RubySequencer(
                version=i,
                # I/D cache is combined and grab from ctrl
                max_outstanding_requests=1,
                dcache=self.controllers[i].DCache,
                clk_domain=self.controllers[i].clk_domain,
                ruby_system=self,
            )
            for i in range(num_agents)
        ]

        # We know that we put the controllers in an order such that the first
        # N of them are the L1 caches which need a sequencer pointer
        for i, c in enumerate(self.controllers[0 : len(self.sequencers)]):
            c.sequencer = self.sequencers[i]

        self.num_of_sequencers = len(self.sequencers)

        # Create the network and connect the controllers.
        # NOTE: This is quite different if using Garnet!
        self.network.connectControllers(
            self.controllers[:-1],
            self.controllers[-1],
            enforce_roc,
            subslot_opt,
            use_wc,
            split_bus,
            resp_bus_latency,
            slot_width,
            llc_latency,
        )
        self.network.setup_buffers()

        # Set up a proxy port for the system_port. Used for load binaries and
        # other functional-only things.
        self.sys_port_proxy = RubyPortProxy(ruby_system=self)
        system.system_port = self.sys_port_proxy.in_ports

        if type_of_system == "cpu":
            cpus = cpus_or_testers
            # Connect the cpu's cache, interrupt, and TLB ports to Ruby
            for i, cpu in enumerate(cpus):
                self.sequencers[i].connectCpuPorts(cpu)
        elif type_of_system == "tester":
            tester = cpus_or_testers
            for i in range(0, num_agents):
                tester[i].port = self.sequencers[i].in_ports
                self.sequencers[i].no_retry_on_stall = True
                self.sequencers[i].using_ruby_tester = False
            #for seq in self.sequencers:
            #    if seq.support_data_reqs and seq.support_inst_reqs:
            #        tester.cpuInstDataPort = seq.in_ports
            #    elif seq.support_data_reqs:
            #        tester.cpuDataPort = seq.in_ports
            #    elif seq.support_inst_reqs:
            #        tester.cpuInstDataPort = seq.in_ports
                # Do not automatically retry stalled Ruby requests
                #seq.no_retry_on_stall = True

                # Tell each sequencer this is the ruby tester so that it
                # copies the subblock back to the checker
                #seq.using_ruby_tester = True

class L0Cache(LC_MSI_L0Cache_Controller):
    _version = 0

    @classmethod
    def versionCount(cls):
        cls._version += 1  # Use count for this particular type
        return cls._version - 1

    def __init__(self, system, ruby_system, cpu, assoc, size):
        """CPUs are needed to grab the clock domain and system is needed for
        the cache block size.
        """
        super().__init__()

        self.version = self.versionCount()
        # This is the cache memory object that stores the cache data and tags

        self.ICache = RubyCache(
            size=size,
            assoc=assoc,
            start_index_bit=self.getBlockSizeBits(system),
        )
        self.DCache = RubyCache(
            size=size,
            assoc=assoc,
            start_index_bit=self.getBlockSizeBits(system),
        )

        self.xyzStatsObject = XYZStatsObject()
        self.clk_domain = cpu.clk_domain
        self.send_evictions = self.sendEvicts(cpu)
        self.ruby_system = ruby_system
        self.connectQueues(L1Cache)

    def getBlockSizeBits(self, system):
        bits = int(math.log(system.cache_line_size, 2))
        if 2**bits != system.cache_line_size.value:
            panic("Cache line size not a power of 2!")
        return bits

    def sendEvicts(self, cpu):
        """True if the CPU model or ISA requires sending evictions from caches
        to the CPU. Two scenarios warrant forwarding evictions to the CPU:
        1. The O3 model must keep the LSQ coherent with the caches
        2. The x86 mwait instruction is built on top of coherence
        3. The local exclusive monitor in ARM systems
        """
        # if type(cpu) is DerivO3CPU or \
        #   buildEnv['TARGET_ISA'] in ('x86', 'arm', 'riscv'):
        #    return True
        # return False
        return True

    def connectQueues(self, ruby_system):
        """Connect all of the queues for this controller."""
        # mandatoryQueue is a special variable. It is used by the sequencer to
        # send RubyRequests from the CPU (or other processor). It isn't
        # explicitly connected to anything.
        self.mandatoryQueue = MessageBuffer(ordered=True)

        self.requestToL1 = MessageBuffer(ordered=True)
        self.requestToL1.out_port = self.ruby_system.network.in_port

        self.forwardFromL1 = MessageBuffer(ordered=True)
        self.forwardFromL1.in_port = self.ruby_system.network.out_port

        self.responseFromL1 = MessageBuffer(ordered=True)
        self.responseFromL1.in_port = self.ruby_system.network.out_port

        self.responseToL1 = MessageBuffer(ordered=True)
        self.responseToL1.out_port = self.ruby_system.network.in_port


class L1Cache(LC_MSI_L1Cache_Controller):

    _version = 0

    @classmethod
    def versionCount(cls):
        cls._version += 1  # Use count for this particular type
        return cls._version - 1

    def __init__(
        self,
        system,
        ruby_system,
        cpu,
        assoc,
        size,
        l0,
        split_bus,
        resp_bus_latency,
    ):
        """CPUs are needed to grab the clock domain and system is needed for
        the cache block size.
        """
        super().__init__()

        self.version = self.versionCount()
        # This is the cache memory object that stores the cache data and tags
        self.cacheMemory = RubyCache(
            size=size,
            assoc=assoc,
            start_index_bit=self.getBlockSizeBits(system),
        )

        self.responseBusLatency = resp_bus_latency
        self.xyzStatsObject = XYZStatsObject(
            worst_case_latency_bound=3289
        )  # TODO: remove this guard
        self.clk_domain = cpu.clk_domain
        self.ruby_system = ruby_system
        self.splitBus = split_bus
        self.connectQueues(ruby_system, l0)

    def getBlockSizeBits(self, system):
        bits = int(math.log(system.cache_line_size, 2))
        if 2**bits != system.cache_line_size.value:
            panic("Cache line size not a power of 2!")
        return bits

    def connectQueues(self, ruby_system, l0):
        """Connect all of the queues for this controller."""
        # # mandatoryQueue is a special variable. It is used by the sequencer to
        # # send RubyRequests from the CPU (or other processor). It isn't
        # # explicitly connected to anything.
        # self.mandatoryQueue = MessageBuffer(ordered=True)

        # All message buffers must be created and connected to the
        # general Ruby network. In this case, "in_port/out_port" don't
        # mean the same thing as normal gem5 ports. If a MessageBuffer
        # is a "to" buffer (i.e., out) then you use the "out_port",
        # otherwise, the in_port.
        self.requestToDir = MessageBuffer(ordered=True)
        self.requestToDir.out_port = ruby_system.network.in_port
        self.responseToDirOrSibling = MessageBuffer(ordered=True)
        self.responseToDirOrSibling.out_port = ruby_system.network.in_port
        self.forwardFromDir = MessageBuffer(ordered=True)
        self.forwardFromDir.in_port = ruby_system.network.out_port
        self.responseFromDirOrSibling = MessageBuffer(ordered=True)
        self.responseFromDirOrSibling.in_port = ruby_system.network.out_port

        self.responseToDirOnly = MessageBuffer(ordered=True)
        self.responseToDirOnly.out_port = ruby_system.network.in_port
        self.responseFromDirOnly = MessageBuffer(ordered=True)
        self.responseFromDirOnly.in_port = ruby_system.network.out_port

        # self.requestFromL0 = l0.requestToL1
        # self.forwardToL0 = l0.forwardFromL1
        # self.responseToL0 = l0.responseFromL1
        # self.responseFromL0 = l0.responseToL1
        self.requestFromL0 = MessageBuffer(ordered=True)
        self.requestFromL0.in_port = ruby_system.network.out_port

        self.forwardToL0 = MessageBuffer(ordered=True)
        self.forwardToL0.out_port = ruby_system.network.in_port

        self.responseToL0 = MessageBuffer(ordered=True)
        self.responseToL0.out_port = ruby_system.network.in_port

        self.responseFromL0 = MessageBuffer(ordered=True)
        self.responseFromL0.in_port = ruby_system.network.out_port


class DirController(Directory_Controller):
    _version = 0

    @classmethod
    def versionCount(cls):
        cls._version += 1  # Use count for this particular type
        return cls._version - 1

    def __init__(
        self,
        ruby_system,
        ranges,
        mem_ctrls,
        blksz,
        ncore,
        ncore_assoc,
        prv_tot,
        use_ziv,
        use_vi,
        size,
        use_write_through,
        enforce_roc,
        assoc,
        resp_bus_latency,
        split_bus,
        wb_buffer_size,
    ):
        """ranges are the memory ranges assigned to this controller."""
        if len(mem_ctrls) > 1:
            panic("This cache system can only be connected to one mem ctrl")
        super().__init__()
        self.version = self.versionCount()
        self.addr_ranges = ranges
        self.ruby_system = ruby_system
        self.responseBusLatency = resp_bus_latency
        # Directory entry is the memory of all!
        self.directory = RubyDirectoryMemory(
            block_size=ruby_system.block_size_bytes
        )
        self.splitBus = split_bus
        # TODO: change to another organization
        # 2 MB of size?
        self.cacheMemory = RubyCache(
            size=size, assoc=ncore * ncore_assoc, start_index_bit=blksz
        )  # not used actually
        self.xyzCacheMemory = XYZCache(
            size=size,
            assoc=assoc,
            start_index_bit=blksz,
            pri_tot=prv_tot,
            ziv=use_ziv,
            use_vi=use_vi,
        )
        self.xyzStatsObject = XYZStatsObject()
        self.enforce_roc = enforce_roc
        self.sum_prv_capacity = prv_tot
        self.write_through = use_write_through
        self.wb_buffer_size = 1 if not split_bus else wb_buffer_size
        # Connect this directory to the memory side.
        self.memory = mem_ctrls[0].port
        self.connectQueues(ruby_system)

    def connectQueues(self, ruby_system):
        # Special handling for blocking request
        self.requestFromCache = MessageBuffer(ordered=True, buffer_size=1)
        self.requestFromCache.in_port = ruby_system.network.out_port
        self.responseFromCache = MessageBuffer(ordered=True)
        self.responseFromCache.in_port = ruby_system.network.out_port

        self.responseToCache = MessageBuffer(ordered=True)
        self.responseToCache.out_port = ruby_system.network.in_port
        self.forwardToCache = MessageBuffer(ordered=True)
        self.forwardToCache.out_port = ruby_system.network.in_port

        # For maintaining ROC
        self.requestFromOrdered = MessageBuffer(ordered=True)
        self.requestFromOrdered.in_port = ruby_system.network.out_port
        self.requestToOrder = MessageBuffer(ordered=True)
        self.requestToOrder.out_port = ruby_system.network.in_port

        self.responseToBusOnly = MessageBuffer(ordered=True)
        self.responseToBusOnly.out_port = ruby_system.network.in_port

        self.responseFromBusOnly = MessageBuffer(ordered=True)
        self.responseFromBusOnly.in_port = ruby_system.network.out_port

        # These are other special message buffers. They are used to send
        # requests to memory and responses from memory back to the controller.
        # Any messages sent or received on the memory port (see self.memory
        # above) will be directed through these message buffers.
        self.requestToMemory = MessageBuffer()
        self.responseFromMemory = MessageBuffer()


class MyNetwork(SimpleNetwork):
    """A simple point-to-point network. This doesn't not use garnet."""

    def __init__(self, ruby_system):
        super().__init__()
        self.netifs = []
        self.ruby_system = ruby_system

    def connectControllers(
        self,
        controllers,
        llc,
        enforce_roc,
        subslot_opt,
        use_wc,
        split_bus,
        resp_bus_latency,
        slot_width,
        llc_latency,
    ):
        """Connect all of the controllers to routers and connec the routers
        together in a point-to-point network.
        """
        # Note: ext_links, int_links and routers are inherited and should be always used
        # Create one router/switch per controller in the system
        ncore = len(controllers) // 2

        self.routers = [
            Switch(router_id=i, shared=False) for i in range(len(controllers))
        ] + [
            Switch(
                router_id=len(controllers),
                enforce_roc=enforce_roc,
                subslot_opt=subslot_opt,
                work_conserving=use_wc,
                split_bus=split_bus,
                response_bus_latency=resp_bus_latency,
                slot_width=slot_width,
                llc_latency=llc_latency,
                shared=True,
            )
        ]
        bus = self.routers[-1]
        bus.ncore = ncore
        llc.bus = bus

        # Make a link from each controller to the router. The link goes
        # externally to the network.
        self.ext_links = [
            SimpleExtLink(link_id=i, ext_node=c, int_node=self.routers[i])
            for i, c in enumerate(controllers)
        ] + [
            SimpleExtLink(link_id=len(controllers), ext_node=llc, int_node=bus)
        ]

        # Make an "internal" link (internal to the network) between every pair
        # of routers.
        link_count = 0
        self.int_links = []
        for ri in self.routers[ncore:]:
            for rj in self.routers[ncore:]:
                if ri == rj:
                    continue  # Don't connect a router to itself!
                if (
                    ri.router_id < ncore or rj.router_id < ncore
                ):  # don't connect L1 routers
                    continue
                link_count += 1
                self.int_links.append(
                    SimpleIntLink(link_id=link_count, src_node=ri, dst_node=rj)
                )

        # private link within l1 and l2
        for ri, rj in zip(self.routers[:ncore], self.routers[ncore:]):
            link_count += 1
            self.int_links.append(
                SimpleIntLink(link_id=link_count, src_node=ri, dst_node=rj)
            )
            link_count += 1
            self.int_links.append(
                SimpleIntLink(link_id=link_count, src_node=rj, dst_node=ri)
            )
        # special case for internal back loop
        link_count += 1
        self.int_links.append(
            SimpleIntLink(link_id=link_count, src_node=bus, dst_node=bus)
        )
