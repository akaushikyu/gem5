
#include "xyz/ZIVReplacementPolicy.hh"

#include <cassert>
#include <memory>

#include "params/ZIVReplacementPolicy.hh"
#include "sim/cur_tick.hh"

namespace gem5 {

namespace replacement_policy {

using RP = ZIVReplacementPolicy;
using RPData = ZIVReplacementPolicy::ZIVReplacementPolicyReplData;

RP::ZIVReplacementPolicy(const Params& p)
    : Base(p) {}

void RP::invalidate(const std::shared_ptr<ReplacementData>& replacement_data) {
  // Reset last touch timestamp
  std::static_pointer_cast<RPData>(replacement_data)->lastTouchTick =
      Tick(0);
}

void ZIVReplacementPolicy::touch(
    const std::shared_ptr<ReplacementData>& replacement_data) const {
  // Update last touch timestamp
  std::static_pointer_cast<RPData>(replacement_data)->lastTouchTick =
      curTick();
}

void ZIVReplacementPolicy::reset(
    const std::shared_ptr<ReplacementData>& replacement_data) const {
  // Set last touch timestamp
  std::static_pointer_cast<RPData>(replacement_data)->lastTouchTick =
      curTick();
}

ReplaceableEntry* ZIVReplacementPolicy::getVictim(
    const ReplacementCandidates& candidates) const {
  // There must be at least one replacement candidate
  assert(candidates.size() > 0);

  // Visit all candidates to find victim
  ReplaceableEntry* victim = candidates[0];
  for (const auto& candidate : candidates) {
    // Update victim entry if necessary
    if (std::static_pointer_cast<RPData>(candidate->replacementData)
            ->lastTouchTick <
        std::static_pointer_cast<RPData>(victim->replacementData)
            ->lastTouchTick) {
      victim = candidate;
    }
  }

  return victim;
}

std::shared_ptr<ReplacementData> ZIVReplacementPolicy::instantiateEntry() {
  return std::shared_ptr<ReplacementData>(new RPData());
}

}  // namespace replacement_policy
}  // namespace gem5
