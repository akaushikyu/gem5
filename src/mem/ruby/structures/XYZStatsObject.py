# from m5.SimObject import SimObject
from m5.objects.ClockedObject import ClockedObject
from m5.params import *


class XYZStatsObject(ClockedObject):
    type = "XYZStatsObject"
    cxx_header = "mem/ruby/structures/XYZStatsObject.hh"
    cxx_class = "gem5::ruby::XYZStatsObject"

    worst_case_latency_bound = Param.UInt64(
        (1 << 64) - 1,
        "The upper bound on the latency, in cycles, of the worst-case path in the system, used at L2",
    )
