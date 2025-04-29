from m5.params import *
from m5.proxy import *
from m5.objects.ReplacementPolicies import *
from m5.objects.RubyCache import RubyCache

class XYZCache(RubyCache):
    type = 'XYZCache'
    cxx_class = 'gem5::ruby::XYZCacheMemory'
    cxx_header = "mem/ruby/structures/XYZCacheMemory.hh"

    use_vi = Param.Bool(True, "Whether enable vacancy invariant")
    ziv = Param.Bool(True, "Whether enable ZIV, when use_vi is enabled, ziv must also be true")
    pri_tot = Param.Int(-1, "Total private cache size")

    # size = Param.MemorySize("capacity in bytes");
    # assoc = Param.Int("");
    # replacement_policy = Param.BaseReplacementPolicy(TreePLRURP(), "")
    # start_index_bit = Param.Int(6, "index start, default 6 for 64-byte line");
    # is_icache = Param.Bool(False, "is instruction only cache");
    # block_size = Param.MemorySize("0B", "block size in bytes. 0 means default RubyBlockSize")

    # dataArrayBanks = Param.Int(1, "Number of banks for the data array")
    # tagArrayBanks = Param.Int(1, "Number of banks for the tag array")
    # dataAccessLatency = Param.Cycles(1, "cycles for a data array access")
    # tagAccessLatency = Param.Cycles(1, "cycles for a tag array access")
    # resourceStalls = Param.Bool(False, "stall if there is a resource failure")
    # ruby_system = Param.RubySystem(Parent.any, "")
