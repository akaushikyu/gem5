// Author: Xinzhe Wang

#ifndef __MEM_RUBY_SLICC_INTERFACE_EXCL_INCLUDES_HH__
#define __MEM_RUBY_SLICC_INTERFACE_EXCL_INCLUDES_HH__

#include <string>

namespace gem5
{

namespace ruby
{

inline int getNumSharer(const NetDest& sharers) {
    return sharers.count();
}

#if defined (BESPOKE)
inline DataBlock coalesceData(
      const DataBlock &ablk,
      const DataBlock &bblk,
      const Addr waddr,
      const int size) {
  DataBlock d = DataBlock(64);
  d = ablk;
  d.coalesce(bblk, waddr, size);
  return d;
}
#endif


}  // namespace ruby
}  // namespace gem5

#endif // __MEM_RUBY_SLICC_INTERFACE_EXCL_INCLUDES_HH__
