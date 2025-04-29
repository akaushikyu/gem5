/*
 * Copyright (c) 2021 ARM Limited
 * All rights reserved.
 *
 * The license below extends only to copyright in the software and shall
 * not be construed as granting a license to any other intellectual
 * property including but not limited to intellectual property relating
 * to a hardware implementation of the functionality of the software
 * licensed hereunder.  You may use the software subject to the license
 * terms below provided that you ensure that this notice is replicated
 * unmodified and in its entirety in all distributions of the software,
 * modified or unmodified, in source code or in binary form.
 *
 * Copyright (c) 1999-2008 Mark D. Hill and David A. Wood
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are
 * met: redistributions of source code must retain the above copyright
 * notice, this list of conditions and the following disclaimer;
 * redistributions in binary form must reproduce the above copyright
 * notice, this list of conditions and the following disclaimer in the
 * documentation and/or other materials provided with the distribution;
 * neither the name of the copyright holders nor the names of its
 * contributors may be used to endorse or promote products derived from
 * this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 * "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 * LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
 * A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
 * OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
 * SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
 * LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
 * DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
 * THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

/*
 * Perfect switch, of course it is perfect and no latency or what so
 * ever. Every cycle it is woke up and perform all the necessary
 * routings that must be done. Note, this switch also has number of
 * input ports/output ports and has a routing table as well.
 */

#ifndef __MEM_RUBY_NETWORK_SIMPLE_PERFECTSWITCH_HH__
#define __MEM_RUBY_NETWORK_SIMPLE_PERFECTSWITCH_HH__

#include <iostream>
#include <string>
#include <vector>

#include "mem/ruby/common/Consumer.hh"
#include "mem/ruby/common/TypeDefines.hh"

#if defined (ZCLLC)
#include "mem/ruby/slicc_interface/Message.hh"
#include "xyz/SlotManager.hh"
#include "xyz/ROCQueue.hh"
#endif

namespace gem5
{

namespace ruby
{

class MessageBuffer;
class NetDest;
class SimpleNetwork;
class Switch;

class PerfectSwitch : public Consumer
{
  public:
#if defined(SNOOPING_BUS)
    PerfectSwitch(SwitchID sid, Switch *, uint32_t, int, int, int);
#elif defined (ZCLLC)
    PerfectSwitch(SwitchID sid, Switch *, uint32_t, int, bool, bool, bool, bool,
                  int, int, int, bool);
    //PerfectSwitch(SwitchID sid, Switch *, uint32_t);
#else
    PerfectSwitch(SwitchID sid, Switch *, uint32_t);
#endif
    ~PerfectSwitch();

    std::string name()
    { return csprintf("PerfectSwitch-%i", m_switch_id); }

    void init(SimpleNetwork *);
    void addInPort(const std::vector<MessageBuffer*>& in);
    void addOutPort(const std::vector<MessageBuffer*>& out,
                    const NetDest& routing_table_entry,
                    const PortDirection &dst_inport,
                    Tick routing_latency,
                    int link_weight);

    int getInLinks() const { return m_in.size(); }
    int getOutLinks() const { return m_out.size(); }

#if defined (ZCLLC)
    int getCurrentSlotOwner() const { return m_cur_tdm_slot_owner; }
    bool isStartOfSlot() const {
      return (curCycle() - m_last_slot_start) >= m_slot_width;
    }
    int getRequestVNet() const { return 0; }

    Cycles getNextCycleForCore(int c) const;

    void scheduleNextSlot();
    void gotoNextSlotOwner() {
      m_tdm_slot_owner_idx = m_tdm_slot_owner_idx + 1;
      if(m_tdm_slot_owner_idx >= m_schedule.size()) m_tdm_slot_owner_idx = 0;
      m_tdm_slot_owner = m_schedule[m_tdm_slot_owner_idx];
    }

    Cycles curCycle() const;
    bool coreHasPendingRequest(int c) const;

    // denote that the bus in not active,
    // used by caches to indicate that their operations are finish'd
    void deactivate() { m_bus_active = false; }

    void markLLCDone();
    void markLLCDone(bool wait_for_data);
    void markLLCDone(Cycles delay);
    void markTransactionDone();
    int getROCCount(int set) { return this->m_roc_queue.count(); }
    int m_slot_width = 128;
    bool isSharedSwitch() const { return sharedSwitch; }
#endif

    void wakeup();
    void regularWakeup();
    void storeEventInfo(int info);

    void clearStats();
    void collateStats();
    void print(std::ostream& out) const;

  private:
    // Private copy constructor and assignment operator
    PerfectSwitch(const PerfectSwitch& obj);
    PerfectSwitch& operator=(const PerfectSwitch& obj);

    void operateVnet(int vnet);
    void operateRegularVnet(int vnet);
#if defined (ZCLLC)
    void operateVnet(int vnet, int message_limit);
    void operateVnet(int vnet, int deviceIdx, int message_limit);
    void enqueueROCQueue(int llc_idx, bool is_front);
    void dequeuROCQueue();
    void handleSplitBusResponse();
    // mb* methods are used in conjunction with the message buffer for invasive probes
    bool mbIsMsgReady(MsgPtr& msg, Tick current_time) const {
        return (msg->getLastEnqueueTime() <= current_time);
    }

    // get the destination of the message used
    template<typename MsgType>
    NetDest mbGetDestination(MsgPtr& msg) {
        const MsgType* req = dynamic_cast<const MsgType*>(msg.get());
        return req->getDestination();
    }

    template<typename MsgType>
    MachineID mbGetSrc(MsgPtr& msg) {
        const MsgType* req = dynamic_cast<const MsgType*>(msg.get());
        return req->getSender();
    }

    template<typename MsgType>
    MachineID mbGetOriginalRequestor(MsgPtr& msg) {
        const MsgType* req = dynamic_cast<const MsgType*>(msg.get());
        return req->getOriginalRequestor();
    }

    bool is_vanilla_tdm() const {
      return !this->m_work_conserving && !this->m_subslot_opt;
    }

    bool is_work_conserving() const {
      return this->m_work_conserving && !this->m_subslot_opt;
    }

    bool is_subslot_opt() const {
      return this->m_work_conserving && this->m_subslot_opt;
    }

    bool is_split_bus() const { return this->m_split_bus; }
#endif
    void operateMessageBuffer(MessageBuffer *b, int vnet, int message_limit=-1);

    const SwitchID m_switch_id;
    Switch * const m_switch;

    // Vector of queues associated to each port.
    std::vector<std::vector<MessageBuffer*> > m_in;

    // Each output port also has a latency for routing to that port
    struct OutputPort
    {
        Tick latency;
        std::vector<MessageBuffer*> buffers;
    };
    std::vector<OutputPort> m_out;

    // input ports ordered by priority; indexed by vnet first
    std::vector<std::vector<MessageBuffer*> > m_in_prio;
    // input ports grouped by priority; indexed by vnet,prio_lv
    std::vector<std::vector<std::vector<MessageBuffer*>>> m_in_prio_groups;

    void updatePriorityGroups(int vnet, MessageBuffer* buf);

    uint32_t m_virtual_networks;
    int m_round_robin_start;
    int m_wakeups_wo_switch;

#if defined (ZCLLC)
    std::vector<Cycles> m_cycles;
    int m_tdm_slot_owner;
    int m_cur_tdm_slot_owner;
    int m_tdm_slot_owner_idx;
    std::vector<int> m_schedule;
    std::list<int> m_order;
    std::set<int> m_core_ordered;
    int m_ordered_slot = -1;
    Cycles m_last_opererated_cycle = Cycles(0);
    Cycles m_last_insertion_cycle = Cycles(0);
    Cycles m_last_slot_start = Cycles(0);
    Cycles m_last_scheduled_slot = Cycles(0);
    Cycles m_response_bus_latency;
    int m_ncore = -1;
    bool m_enforce_roc;
    bool m_work_conserving;
    bool m_subslot_opt;
    // whether the bus is active handling a request
    bool m_bus_active;
    bool m_split_bus;
    bool sharedSwitch;
    SlotManager m_slot_manager;
    EventFunctionWrapper m_llc_end_event;
    ROCQueue m_roc_queue;
    bool m_llc_finish_signal;
    // How long does it take for the LLC signal to stop propogate to
    // the bus, this value should be greater than the network latency
    // b/c we want to ensure that the bus first propagate the LLC responses
    Cycles m_end_delay;
    // a queue that record the request order of incoming requests,
    // where we will handle the response corresponding to the request
    // m_request_order[i] == core means that a response is pending from OR TO core
    // this is because it is possible that a back-invalidation or a
    // voluntary write-back are pending
    // differences b/w m_roc_queue and m_response_order
    // roc queue is only enqueued when a request cannot finish within its slot
    // and an entry is removed as soon as a request is "done" by LLC
    // but response queue is used even if a request can finish within its first
    // attempt and it is used to throttle the response bus (in shared bus, there
    // will be slot width allocated for response bus so no need there for arbitration)
    std::list<int>* m_response_order;
#endif

    SimpleNetwork* m_network_ptr;
    std::vector<int> m_pending_message_count;

    MessageBuffer* inBuffer(int in_port, int vnet) const;
#ifdef SNOOPING_BUS
    // Bus arbitration support
    int m_num_processor;
    int m_tdm_slot_width;
    int m_resp_bus_slot_width;
    int m_request_bus_owner = 0;
    uint64_t m_req_bus_next_free_cycle = 0;
    bool isStartOfSlot();
    uint64_t getNextSlotStartCycle();
    void operateTDMRequestBus(int vnet);
    void operateMessageBufferOnce(MessageBuffer *buffer, int vnet);

    uint64_t m_resp_bus_next_free_cycle = 0;
    void operateOARespBus(int vnet);
#endif

};

inline std::ostream&
operator<<(std::ostream& out, const PerfectSwitch& obj)
{
    obj.print(out);
    out << std::flush;
    return out;
}

} // namespace ruby
} // namespace gem5

#endif // __MEM_RUBY_NETWORK_SIMPLE_PERFECTSWITCH_HH__
