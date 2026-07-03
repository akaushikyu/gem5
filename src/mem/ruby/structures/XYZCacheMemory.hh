#ifndef __MEM_RUBY_STRUCTURES_XYZCACHEMEMORY_HH__
#define __MEM_RUBY_STRUCTURES_XYZCACHEMEMORY_HH__

#include <string>
#include <unordered_map>
#include <unordered_set>
#include <map>
#include <vector>
#include "debug/ZIVCache.hh"

#include "base/statistics.hh"
#include "mem/cache/replacement_policies/base.hh"
#include "mem/cache/replacement_policies/replaceable_entry.hh"
#include "mem/ruby/common/DataBlock.hh"
#include "mem/ruby/protocol/CacheRequestType.hh"
#include "mem/ruby/protocol/CacheResourceType.hh"
#include "mem/ruby/protocol/RubyRequest.hh"
#include "mem/ruby/slicc_interface/AbstractCacheEntry.hh"
#include "mem/ruby/slicc_interface/RubySlicc_ComponentMapping.hh"
#include "mem/ruby/structures/BankedArray.hh"
#include "mem/ruby/structures/CacheMemory.hh"
#include "mem/ruby/system/CacheRecorder.hh"
// #include "params/RubyCache.hh"
#include "params/XYZCache.hh"
#include "sim/sim_object.hh"

namespace gem5 {

namespace ruby {

class XYZCacheMemory : public CacheMemory {
    struct Location {
        int row;
        int loc;
    };
 public:
  typedef XYZCacheParams XYZParams;
  // typedef std::shared_ptr<replacement_policy::ReplacementData> ReplData;
  XYZCacheMemory(const XYZParams& p);
  ~XYZCacheMemory();
  virtual void deallocate(Addr address);
  // This was the original thing
  Addr addressToCacheSet(Addr address) const {
      return Addr(CacheMemory::addressToCacheSet(address));
  }
  int getLHS() const {
      // get the left hand side of the vacancy invariant
      return getNumBlocks() - getNotSync() - getPrv();
  }
  bool calculateVIwithDelta(int delta_lhs, int delta_rhs, int private_capacity) {
      if(pri_tot  == -1) pri_tot = private_capacity;
      // return getLHS() + delta_lhs >= pri_tot - totalPrivateCache + delta_rhs;
      DPRINTF(ZIVCache, "%d %d >=? %d %d\n", getNumBlocks(), getNotSync(), pri_tot, delta_rhs);
      // if(getNotSync() == 0) return true;
      return getNumBlocks() - getNotSync() >= pri_tot + delta_rhs;
  }
  int getNotSync() const { return Q.size(); }
  int getPrv() const { return P.size(); }
  bool isRelocated(Addr lineAddress) {
      return relocation_table.find(lineAddress) != relocation_table.end();
  }

  virtual AbstractCacheEntry* allocate(Addr address, AbstractCacheEntry* new_entry);
  // deallocate uses lookup which we hooked, so no need to change
  // virtual void deallocate(Addr address);
  virtual AbstractCacheEntry* lookup(Addr address);
  virtual const AbstractCacheEntry* lookup(Addr address) const;
  virtual void init();

  virtual void addSharer(Addr address) {
      if(!m_ziv) return;
      //assert(isTagPresent(address));
      if(Q.find(address) != Q.end()) {
          Q.erase(address);
          assert(P.find(address) == P.end());
      }
      if(P.find(address) == P.end()) P[address] = 0;
      P[address] += 1;
      totalPrivateCache += 1;
      markEntryNotCRE(address);
      reportInvariant(address);
  }
  void markEntryNotCRE(Addr address) {
      if(!m_ziv) return;
      auto e = lookup(address);
      if(isCRE[e->getSet()][e->getWay()]) {
        isCRE[e->getSet()][e->getWay()] = false;
        CRECountPerSet[e->getSet()] -= 1;
        CRETotal -= 1;
      }

  }
  virtual void markOwner(Addr address) {
      if(!m_ziv) return;
      //assert(isTagPresent(address));
      if(Q.find(address) != Q.end()) {
          Q.erase(address);
          assert(P.find(address) == P.end());
      }
      if(P.find(address) != P.end()) {
        totalPrivateCache -= P[address];
        P[address] = 0;
      }
      P[address] = 1;
      totalPrivateCache += 1;

      markEntryNotCRE(address);
      reportInvariant(address);
  }
  virtual void removeSharer(Addr address) {
      if(!m_ziv) return;
      //assert(isTagPresent(address));
      assert(Q.find(address) == Q.end());
      auto it = P.find(address);
      assert(it != P.end());
      assert(it->second > 0);
      it->second--;
      if(it->second == 0) {
          Q.insert(address);
          P.erase(it);
      }
      totalPrivateCache -= 1;
      reportInvariant(address);
  }
  virtual void clearSharer(Addr address) {
      if(!m_ziv) return;
      //assert(isTagPresent(address));
      auto it = P.find(address);
      assert(it != P.end());
      assert(Q.find(address) == Q.end());
      totalPrivateCache -= it->second;
      P.erase(it);
      Q.insert(address);
      reportInvariant(address);
  }
  // must be called afterwards
  // called manually
  virtual void markCRE(Addr address) {
      if(!m_ziv) return;
      DPRINTF(ZIVCache, "ZIV: marking %#x ad CRE\n", address);
      //assert(isTagPresent(address));
      assert(Q.find(address) != Q.end());
      assert(P.find(address) == P.end());
      Q.erase(address);
      auto e = lookup(address);
      auto row = e->getSet();
      auto way = e->getWay();
      if(!isCRE[row][way]) {
          isCRE[row][way] = true;
          CRECountPerSet[row] += 1;
          CRETotal += 1;
      }

      reportInvariant(address);
  }

  // Whether a CRE is available
  virtual bool xyzCREAvail(Addr address) const {
      if(!m_ziv) return cacheAvail(address);
      return CRETotal > 0;
  }
  bool checkCRE(Addr address) {
      panic_if(!m_ziv, "Relocation when ziv is not used");
      //assert(isTagPresent(address));
      if(P.find(address) == P.end()) {
          return false;
      } else if(Q.find(address) == Q.end()) {
          return false;
      } else {
          return true;
      }
  }
  Location locateCRE(Addr address) {
      // We could use a more intelligent policy
      // NOTE: the state in the LLC is either invalid or LLCOnly
      panic_if(!m_ziv, "Relocation when ziv is not used");
      assert(CRETotal > 0);
      int64_t cacheSet = addressToCacheSet(address);
      // prioritize CREs in the same set
      if(CRECountPerSet[cacheSet]) {
          for(auto j = 0; j < m_cache_assoc; j++) {
                if(isCRE[cacheSet][j]) {
                    return { (int)cacheSet, j };
                }
            }
      }
      for(auto i = 0; i < m_cache_num_sets; i++) {
          if(CRECountPerSet[i] > 0) {
              for(auto j = 0; j < m_cache_assoc; j++) {
                  if(isCRE[i][j]) {
                      return { i, j };
                  }
              }
          }
      }
      panic("CRETotal is greater than 0 but no CRE found");
  }
  void reportInvariant(Addr address);
  void relocateVictim(AbstractCacheEntry* entry, Location targetLocation);
  AbstractCacheEntry* cacheProbeEntry(Addr address) const {
      // just return an entry instead of an address, used to find a victim to relocate
    assert(address == makeLineAddress(address));
    assert(!cacheAvail(address));

    int64_t cacheSet = addressToCacheSet(address);
    std::vector<ReplaceableEntry*> candidates;
    for (int i = 0; i < m_cache_assoc; i++) {
        candidates.push_back(static_cast<ReplaceableEntry*>(
                                                    m_cache[cacheSet][i]));
    }
    return m_cache[cacheSet][m_replacementPolicy_ptr->
                        getVictim(candidates)->getWay()];
  }
  Addr xyzCacheProbe(Addr address) const {

      // Just probe arbitrary line so that we can create a CRE
      if(!m_ziv) return cacheProbe(address);
      // probe an address, but we must assume there is no CRE
      assert(!xyzCREAvail(address));
      // We now needs to select a cache line from Q
      // TODO: use a more intelligent replacement policy
      assert(Q.size() > 0);
      Addr victim = *Q.begin();
      //assert(isTagPresent(victim));
      return victim;
  }
  Addr simpleProbe(Addr address) const {
      if(!m_ziv) return cacheProbe(address);

      // assert(Q.size() >= 0);
      Addr victim = *Q.begin();
      //assert(isTagPresent(victim));
      return victim;
  }
  bool vi_enabled() const {
      return m_use_vi;
  }
  bool ziv_enabled() const {
      return m_ziv;
  }


  protected:
  bool m_use_vi;
  bool m_ziv;
  // Store all relocated cache line
  std::unordered_map<Addr, Location> relocation_table;
  // Store the number of sharers for cache lines cached
  std::unordered_map<Addr, int> P; // the P set for maintaining P
  std::unordered_set<Addr> Q; // the lines that are dirty but not privately cached

  std::vector<int> CRECountPerSet; // The number of CRE per set, initialized to be all zeros
  std::vector<std::vector<bool>> isCRE;
  int CRETotal = 0; // Total number of CREs
  int pri_tot = -1;

  int totalPrivateCache = 0;

private:
    // We don't need to copy this
    XYZCacheMemory(const CacheMemory& obj);
    XYZCacheMemory& operator=(const XYZCacheMemory& obj);
};

}  // namespace ruby
}  // namespace gem5

#endif  // __MEM_RUBY_STRUCTURES_CACHEMEMORY_HH__
