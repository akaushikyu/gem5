#include "xyz/ROCQueue.hh"

#include "mem/ruby/slicc_interface/Message.hh"
#include "mem/ruby/protocol/RequestMsg.hh"
#include "base/types.hh"

#include <iostream>

using namespace gem5;
using namespace gem5::ruby;

int ROCQueue::getCoreId(const Message& msg) const {
    const RequestMsg& req = dynamic_cast<const RequestMsg&>(msg);
    auto machineID = req.getRequestor();
    panic_if(machineID.getType() != MachineType::MachineType_L1Cache, "ROCQueue only accepts requests originated from L1Cache");
    return static_cast<int>(machineID.getNum());
}

Addr ROCQueue::getAddress(const Message& msg) const {
    const RequestMsg& req = dynamic_cast<const RequestMsg&>(msg);
    auto addr = req.getaddr();
    return addr;
}

bool ROCQueue::coreHasRequestAtHead(int c) const {
    if(isStrictOrderEnabled()) {
        return coreHasRequestAtHeadStrictOrder(c);
    } else {
        return coreHasRequestAtAnyPosition(c);
    }
}

void ROCQueue::enqueueROCRequest(int c, MsgPtr msg) {

    RequestMsg& req = dynamic_cast<RequestMsg&>(*msg);
    //req.setis_reordered(true);

    this->m_msg_queue.push_back(msg);
}
void ROCQueue::enqueueFrontROCRequest(int c, MsgPtr msg) {
    this->m_msg_queue.push_front(msg);
}

MsgPtr  ROCQueue::dequeueROCRequest(int c) {
    if(isStrictOrderEnabled()) {
        return dequeueROCRequestStrictOrder(c);
    } else {
        return dequeueROCRequestAnyPosition(c);
    }
}


void ROCQueue::print(std::ostream& out) const {
    out << "[ROCQueue] Total Entries: " << this->m_msg_queue.size() << "; ";
    for(auto msg : this->m_msg_queue) {
        out << "[" << this->getCoreId(*msg) << ": " << std::hex << this->getAddress(*msg) << "],";
    }
    out << std::flush;
}

int ROCQueue::count() const {
    return this->m_msg_queue.size();
}

bool ROCQueue::coreHasRequestAtHeadStrictOrder(int c) const {
    if(m_msg_queue.empty()) return false;
    MsgPtr ptr = m_msg_queue.front();
    int head_core = getCoreId(*ptr);
    return head_core == c;
}

bool ROCQueue::coreHasRequestAtAnyPosition(int c) const {
    panic_if(isStrictOrderEnabled(), "ROCQueue::coreHasRequestAtAnyPosition: strict order is enabled");
    for(auto msg : m_msg_queue) {
        int core = getCoreId(*msg);
        if(core == c) return true;
    }
    return false;
}

MsgPtr ROCQueue::dequeueROCRequestStrictOrder(int c) {
    panic_if(!coreHasRequestAtHeadStrictOrder(c), "ROCQueue::dequeueROCRequestStrictOrder: core %d does not have request at head", c);
    MsgPtr res = m_msg_queue.front();
    m_msg_queue.pop_front();
    return res;
}

MsgPtr ROCQueue::dequeueROCRequestAnyPosition(int c) {
    panic_if(!coreHasRequestAtAnyPosition(c), "ROCQueue::dequeueROCRequestAnyPosition: core %d does not have request at any position", c);
    MsgPtr res;
    for(auto it = m_msg_queue.begin(); it != m_msg_queue.end(); it++) {
        int core = getCoreId(**it);
        if(core == c) {
            res = *it;
            m_msg_queue.erase(it);
            break;
        }
    }
    return res;
}
