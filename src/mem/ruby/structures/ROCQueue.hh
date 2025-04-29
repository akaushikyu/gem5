#ifndef __XYZ_ROCQUEUE_HH__
#define __XYZ_ROCQUEUE_HH__

#include "sim/clocked_object.hh"
#include "mem/ruby/slicc_interface/Message.hh"
#include "base/types.hh"

#include <vector>
#include <list>
#include <unordered_map>

namespace gem5 {
namespace ruby {

struct AbstractROCQueue {
    virtual bool coreHasRequestAtHead(int c) const = 0;
    virtual void enqueueROCRequest(int c, MsgPtr msg) = 0;
    virtual void enqueueFrontROCRequest(int c, MsgPtr msg) = 0;
    virtual MsgPtr dequeueROCRequest(int c) = 0;
    virtual void print(std::ostream& out) const = 0;
    virtual int count() const = 0;
    protected:
    // this will be dependent on implementation of the protocol message
    virtual int getCoreId(const Message& msg) const = 0;

};

struct ROCQueue : public AbstractROCQueue {

    ROCQueue(bool enable_strict_order) : m_enable_strict_order(enable_strict_order) {}
    ROCQueue() {}

    virtual bool coreHasRequestAtHead(int c) const;

    virtual void enqueueROCRequest(int c, MsgPtr msg);
    virtual void enqueueFrontROCRequest(int c, MsgPtr msg);

    virtual MsgPtr dequeueROCRequest(int c);

    virtual void print(std::ostream& out) const;
    virtual int count() const;

    std::list<MsgPtr> m_msg_queue;

    bool isStrictOrderEnabled() const { return m_enable_strict_order; }

    protected:
    // This will be dependent on the implementation of the protocol message
    virtual int getCoreId(const Message& msg) const;

    private:
    gem5::Addr getAddress(const Message& msg) const;

    bool m_enable_strict_order;

    bool coreHasRequestAtHeadStrictOrder(int c) const;
    bool coreHasRequestAtAnyPosition(int c) const;

    virtual MsgPtr dequeueROCRequestStrictOrder(int c);
    virtual MsgPtr dequeueROCRequestAnyPosition(int c);
};
inline std::ostream& operator<<(std::ostream& out, const ROCQueue& obj) {
  obj.print(out);
  out << std::flush;
  return out;
}

};  // namespace ruby
};  // namespace gem5


#endif // __XYZ_ROCQUEUE_HH__

