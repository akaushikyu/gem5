#include "mem/ruby/profiler/CustomProfiler.hh"

namespace gem5
{

namespace ruby
{


CustomProfiler::CustomProfiler(const Params &p)
    : SimObject(p), customProfilerStats(this)
{
    // empty constructor
}

CustomProfiler::CustomProfilerStats::CustomProfilerStats
(statistics::Group *parent)
    : statistics::Group(parent),
      ADD_STAT(m_num_get_request, "..."),
      ADD_STAT(m_num_l1_hit, "..."),
      ADD_STAT(m_num_l1_miss, "..."),
      ADD_STAT(m_num_upg, "..."),
      ADD_STAT(m_num_ctc, "..."),
      ADD_STAT(m_num_llc_hit, "..."),
      ADD_STAT(m_num_memory_read, "..."),
      ADD_STAT(m_num_memory_write, "..."),
      ADD_STAT(m_num_back_invalidation, "..."),
      ADD_STAT(m_num_back_invalidation_wb, "..."),
      ADD_STAT(m_num_put_request, "..."),
      ADD_STAT(m_mem_latency_hist, "..."),
      ADD_STAT(m_e2e_latency_hist, "..."),
      ADD_STAT(m_wcl_access_time,"...")
{
    m_mem_latency_hist
        .init(10)
        .flags(statistics::nozero | statistics::pdf | statistics::oneline);

    m_e2e_latency_hist
        .init(10)
        .flags(statistics::nozero | statistics::pdf | statistics::oneline);
}

void
CustomProfiler::profileGetRequest(){
    customProfilerStats.m_num_get_request++;
}

void
CustomProfiler::profileL1Hit(){
    customProfilerStats.m_num_l1_hit++;
}

void
CustomProfiler::profileL1Miss(){
    customProfilerStats.m_num_l1_miss++;
}

void
CustomProfiler::profileUpg(){
    customProfilerStats.m_num_upg++;
}

void CustomProfiler::profileCacheToCacheTrf() {
    customProfilerStats.m_num_ctc++;
}

void
CustomProfiler::profileLLCHit(){
    customProfilerStats.m_num_llc_hit++;
}

void
CustomProfiler::profileMemoryRead(){
    customProfilerStats.m_num_memory_read++;
}

void
CustomProfiler::profileMemoryWrite(){
    customProfilerStats.m_num_memory_write++;
}

void
CustomProfiler::profilePutRequest(){
    customProfilerStats.m_num_put_request++;
}

void
CustomProfiler::profileBackInvalidation(){
    customProfilerStats.m_num_back_invalidation++;
}

void
CustomProfiler::profileBackInvalidationWB(){
    customProfilerStats.m_num_back_invalidation_wb++;
}

void
CustomProfiler::profileMemLatency(Cycles latency) {
    customProfilerStats.m_mem_latency_hist.sample(latency, 1);
}

void
CustomProfiler::profileE2ELatency(Cycles endCycle, Cycles beginCycle) {
    uint64_t beginCycleRaw = uint64_t(beginCycle);

    if (beginCycleRaw > 0) {
      Cycles latency = endCycle - beginCycle;
      if (customProfilerStats.m_wcl_access_time.value() == 0) {
        customProfilerStats.m_wcl_access_time = latency;
      } else {
        if (customProfilerStats.m_wcl_access_time.value() < uint64_t(latency)) {
          customProfilerStats.m_wcl_access_time = latency;
        }
      }
      customProfilerStats.m_e2e_latency_hist.sample(latency, 1);
    }
}

} // namespace ruby


} // namespace gem5
