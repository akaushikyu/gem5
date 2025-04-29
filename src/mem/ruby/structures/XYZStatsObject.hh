#ifndef __MEM_RUBY_STRUCTURES_XYZSTATSOBJECT_HH__
#define __MEM_RUBY_STRUCTURES_XYZSTATSOBJECT_HH__

#include "params/XYZStatsObject.hh"
#include "sim/sim_object.hh"
#include "sim/clocked_object.hh"
#include "base/statistics.hh"
#include "base/logging.hh"
#include "base/trace.hh"
#include "debug/XYZInfo.hh"

namespace gem5::ruby {
class XYZStatsObject: public ClockedObject
{
    using Base = ClockedObject;

  protected:
    struct XYZStats : public statistics::Group
    {
      XYZStats(statistics::Group *parent);
        statistics::Distribution latencies;
        statistics::Scalar total_repl;
        statistics::Scalar total_repl_shared;
        statistics::Scalar total_repl_owned;
        statistics::Scalar total_repl_llc;
        statistics::Scalar total_put;
        statistics::Scalar total_putm;
        statistics::Scalar total_puts;
        statistics::Scalar total_put_as_wt;
        statistics::Scalar total_puts_as_wt;
        statistics::Scalar total_putm_as_wt;
        gem5::statistics::Formula wt_putRatio;
        gem5::statistics::Formula wt_putsRatio;
        gem5::statistics::Formula wt_putmRatio;
    } customXYZStats;

    public:
        XYZStatsObject(const XYZStatsObjectParams &p);

        Cycles w;

        uint64_t wcl_bound;

        void tic() {
            w = curCycle();
        }

        void toc() {
            customXYZStats.latencies.sample(curCycle() - w);
            DPRINTF(XYZInfo, "Samping latency: %lld\n", curCycle() - w);
            if(curCycle() - w > wcl_bound) {
                DPRINTF(XYZInfo, "Worst case latency bound reached: %lld\n", curCycle() - w);
                panic("Worst case latency bound reached: %lld\n", curCycle() - w);
            }
        }

        void regStats() override;
        void recordReplShared() {
            customXYZStats.total_repl++;
            customXYZStats.total_repl_shared++;
        }
        void recordReplOwned() {
            customXYZStats.total_repl++;
            customXYZStats.total_repl_owned++;
        }
        void recordReplLLC() {
            customXYZStats.total_repl++;
            customXYZStats.total_repl_llc++;
        }
        void recordPutM(bool is_write_through) {
            customXYZStats.total_put++;
            customXYZStats.total_putm++;
            if(is_write_through) {
                customXYZStats.total_putm_as_wt++;
                customXYZStats.total_put_as_wt++;
            }
        };
        void recordPutS(bool is_write_through) {
            customXYZStats.total_put++;
            customXYZStats.total_puts++;
            if(is_write_through) {
                customXYZStats.total_puts_as_wt++;
                customXYZStats.total_put_as_wt++;
            }
        };
    };
};


#endif
