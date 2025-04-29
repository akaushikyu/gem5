#ifndef __XYZ_ZIVCACHEMEMORY_HH__
#define __XYZ_ZIVCACHEMEMORY_HH__

#include <string>
#include <unordered_map>
#include <vector>

#include "mem/cache/replacement_policies/base.hh"

namespace gem5 {
struct ZIVReplacementPolicyParams;  // forward declaration
namespace replacement_policy {
class ZIVReplacementPolicy : public Base
{
 public:
  struct ZIVReplacementPolicyReplData : ReplacementData
  {
    Tick lastTouchTick;
    bool inPrC; // whether the cache line is in private cache
    ZIVReplacementPolicyReplData() : lastTouchTick(0) {}
  };
  typedef ZIVReplacementPolicyParams Params;
  ZIVReplacementPolicy(const Params& p);
  ~ZIVReplacementPolicy() = default;

  /**
   * Invalidate replacement data to set it as the next probable victim.
   * Sets its last touch tick as the starting tick.
   *
   * @param replacement_data Replacement data to be invalidated.
   */
  void invalidate(
      const std::shared_ptr<ReplacementData>& replacement_data) override;

  /**
   * Touch an entry to update its replacement data.
   * Sets its last touch tick as the current tick.
   *
   * @param replacement_data Replacement data to be touched.
   */
  void touch(
      const std::shared_ptr<ReplacementData>& replacement_data) const override;

  /**
   * Reset replacement data. Used when an entry is inserted.
   * Sets its last touch tick as the current tick.
   *
   * @param replacement_data Replacement data to be reset.
   */
  void reset(
      const std::shared_ptr<ReplacementData>& replacement_data) const override;

  /**
   * Find replacement victim using LRU timestamps.
   *
   * @param candidates Replacement candidates, selected by indexing
   * policy.
   * @return Replacement entry to be replaced.
   */
  // We should getVictim of all over the cache
  ReplaceableEntry* getVictim(
      const ReplacementCandidates& candidates) const override;

  /**
   * Instantiate a replacement data entry.
   *
   * @return A shared pointer to the new replacement data.
   */
  std::shared_ptr<ReplacementData> instantiateEntry() override;
        };
    };  // namespace replacement_policy
    };  // namespace gem5

#endif
