
#include "mem/ruby/structures/XYZStatsObject.hh"

#include <iostream>

namespace gem5::ruby
{

XYZStatsObject::XYZStatsObject(const XYZStatsObjectParams &params) :
    ClockedObject(params), customXYZStats(this)
{
    std::cout << "XYZStatsObject !" << std::endl;
    wcl_bound = params.worst_case_latency_bound;
}

XYZStatsObject::XYZStats::XYZStats(statistics::Group *parent)
  : statistics::Group(parent),
    ADD_STAT(total_repl,"..."),
    ADD_STAT(total_repl_shared,"..."),
    ADD_STAT(total_repl_owned,"..."),
    ADD_STAT(total_repl_llc,"..."),
    ADD_STAT(total_put,"..."),
    ADD_STAT(total_putm,"..."),
    ADD_STAT(total_puts,"..."),
    ADD_STAT(total_put_as_wt,"..."),
    ADD_STAT(total_puts_as_wt,"..."),
    ADD_STAT(total_putm_as_wt,"...")
{
    latencies.init(0,100000, 50000);
}

void XYZStatsObject::regStats() {
    Base::regStats();
    customXYZStats.latencies.init(0, 100000, 50000);
    customXYZStats.latencies.name(name() + "latency").desc("Mem access latency");
    customXYZStats.total_repl.name(name() + ".total_repl").desc("Total Replacement");
    customXYZStats.total_repl_shared.name(name() + ".total_repl_shared").desc("Total Replacement of shared line");
    customXYZStats.total_repl_owned.name(name() + ".total_repl_owned").desc("Total Replacement of owned line");
    customXYZStats.total_repl_llc.name(name() + ".total_repl_llc").desc("Total Replacement of LLC line");
    customXYZStats.total_put.name(name() + ".total_put").desc("Total number of put (PutM + PutS)");
    customXYZStats.total_putm.name(name() + ".total_putm").desc("Total number of PutM");
    customXYZStats.total_puts.name(name() + ".total_puts").desc("Total number of PutS");
    customXYZStats.total_put_as_wt.name(name() + ".total_put_as_wt").desc("Total number of put as write through");
    customXYZStats.total_puts_as_wt.name(name() + ".total_puts_as_wt").desc("Total number of PutS as write through");
    customXYZStats.total_putm_as_wt.name(name() + ".total_putm_as_wt").desc("Total number of PutM as write through");
    customXYZStats.wt_putRatio.name(name() + ".wt_putRatio").desc("WT / Put");
    customXYZStats.wt_putsRatio.name(name() + ".wt_putsRatio").desc("PutS WT / PutS");
    customXYZStats.wt_putmRatio.name(name() + ".wt_putmRatio").desc("PutM WT / PutM");
    customXYZStats.wt_putRatio = customXYZStats.total_put_as_wt / customXYZStats.total_put;
    customXYZStats.wt_putsRatio = customXYZStats.total_puts_as_wt / customXYZStats.total_puts;
    customXYZStats.wt_putmRatio = customXYZStats.total_putm_as_wt / customXYZStats.total_putm;
}


} // namespace gem5
