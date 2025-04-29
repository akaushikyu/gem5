from m5.objects.ReplacementPolicies import *


class ZIVReplacementPolicy(BaseReplacementPolicy):
    type = "LRURP"
    cxx_class = "gem5::replacement_policy::ZIVReplacementPolicy"
    cxx_header = "xyz/ZIVReplacementPolicy.hh"
