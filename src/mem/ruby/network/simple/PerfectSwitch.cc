/*
 * Copyright (c) 2020-2021 ARM Limited
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
 * "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, EXCLUDING, BUT NOT
 * LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
 * A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
 * OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
 * SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (EXCLUDING, BUT NOT
 * LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
 * DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
 * THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (EXCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

#include "mem/ruby/network/simple/PerfectSwitch.hh"

#include <algorithm>

#include "base/cast.hh"
#include "base/cprintf.hh"
#include "base/random.hh"
#include "debug/RubyNetwork.hh"
#include "mem/ruby/network/MessageBuffer.hh"
#include "mem/ruby/network/simple/SimpleNetwork.hh"
#include "mem/ruby/network/simple/Switch.hh"
#include "mem/ruby/slicc_interface/Message.hh"

#if defined (ZCLLC)
#include "debug/TDMOrder.hh"
#include "debug/ROC.hh"
#include "xyz/SlotManager.hh"
#include "sim/cur_tick.hh"
#include "sim/clocked_object.hh"
#include "xyz/SlotManager.hh"
#include "xyz/ROCQueue.hh"
#endif

#if defined (SNOOPING_BUS)
#include "debug/TDM.hh"
#endif

#if defined(SNOOPING_BUS) || defined(ZCLLC)
#include "mem/ruby/protocol/RequestMsg.hh"
#include "mem/ruby/protocol/ResponseMsg.hh"
#endif

namespace gem5
{

namespace ruby
{

const int PRIORITY_SWITCH_LIMIT = 128;
#if defined(SNOOPING_BUS)
PerfectSwitch::PerfectSwitch(SwitchID sid, Switch *sw, uint32_t virt_nets,
              int num_processor, int tdm_slot_width, int resp_bus_slot_width)
    : Consumer(sw, Switch::PERFECTSWITCH_EV_PRI),
      m_switch_id(sid), m_switch(sw), m_num_processor(num_processor),
      m_tdm_slot_width(tdm_slot_width), m_resp_bus_slot_width(resp_bus_slot_width)
{
    m_wakeups_wo_switch = 0;
    m_virtual_networks = virt_nets;
}
#elif defined (ZCLLC)
PerfectSwitch::PerfectSwitch(SwitchID sid, Switch *sw, uint32_t virt_nets,
               int ncore, bool enforce_roc, bool work_conserving, bool subslot_opt,
               bool split_bus, int response_bus_latency, int slot_width,
               int llc_latency, bool shared)
    : Consumer(sw, Switch::PERFECTSWITCH_EV_PRI),
    m_switch_id(sid), m_switch(sw), m_tdm_slot_owner(0), m_enforce_roc(enforce_roc),
    m_work_conserving(work_conserving), m_subslot_opt(subslot_opt),
    m_split_bus(split_bus), sharedSwitch(shared),
    m_slot_manager(*sw, *this, {}, work_conserving, subslot_opt, split_bus,
                   enforce_roc, Cycles(slot_width), ncore),
    m_llc_end_event(
        [this] {
          DPRINTF(RubyNetwork,
              "setting llc finish signal to true, ... wait for data? %d\n",
              this->m_slot_manager.m_llc_finish_wait_for_data_response);
          this->m_slot_manager.m_llc_finish_signal = true;
          },
          "Consumer Event", false),
    m_roc_queue(enforce_roc) {
      m_round_robin_start = 0;
      m_wakeups_wo_switch = 0;
      m_virtual_networks = virt_nets;
      m_ncore = ncore;
      m_end_delay = Cycles(llc_latency);
      m_response_bus_latency = Cycles(response_bus_latency);
      m_schedule = std::vector<int>(ncore);
      std::iota(m_schedule.begin(), m_schedule.end(), 0);
      m_slot_manager.m_schedule = m_schedule;

      if (m_split_bus) {
        this->m_response_order = new std::list<int>;
      } else {
        this->m_response_order = nullptr;
      }
}
/*
PerfectSwitch::PerfectSwitch(SwitchID sid, Switch *sw, uint32_t virt_nets)
  : Consumer(sw, Switch::PERFECTSWITCH_EV_PRI),
  m_switch_id(sid), m_switch(sw), m_tdm_slot_owner(0), m_enforce_roc(false),
  m_work_conserving(false), m_subslot_opt(false), m_split_bus(false), sharedSwitch(false),
  m_slot_manager(*sw, *this, {}, false, false, false, false, Cycles(0), 0),
  m_llc_end_event(
      [] {}, "Consumer Event", false),
  m_roc_queue() {
    m_wakeups_wo_switch = 0;
    m_virtual_networks = virt_nets;
    m_schedule = std::vector<int>(0);
  }
*/
#else
PerfectSwitch::PerfectSwitch(SwitchID sid, Switch *sw, uint32_t virt_nets)
    : Consumer(sw, Switch::PERFECTSWITCH_EV_PRI),
      m_switch_id(sid), m_switch(sw)
{
    m_wakeups_wo_switch = 0;
    m_virtual_networks = virt_nets;
}
#endif

void
PerfectSwitch::init(SimpleNetwork *network_ptr)
{
    m_network_ptr = network_ptr;

    for (int i = 0;i < m_virtual_networks;++i) {
        m_pending_message_count.push_back(0);
    }
}

void
PerfectSwitch::addInPort(const std::vector<MessageBuffer*>& in)
{
    NodeID port = m_in.size();
    m_in.push_back(in);
#if defined(ZCLLC)
    m_cycles.push_back(Cycles(0));
#endif

    for (int i = 0; i < in.size(); ++i) {
        if (in[i] != nullptr) {
            in[i]->setConsumer(this);
            in[i]->setIncomingLink(port);
            in[i]->setVnet(i);
            updatePriorityGroups(i, in[i]);
        }
    }
}

void
PerfectSwitch::updatePriorityGroups(int vnet, MessageBuffer* in_buf)
{
    while (m_in_prio.size() <= vnet) {
        m_in_prio.emplace_back();
        m_in_prio_groups.emplace_back();
    }

    m_in_prio[vnet].push_back(in_buf);

    std::sort(m_in_prio[vnet].begin(), m_in_prio[vnet].end(),
        [](const MessageBuffer* i, const MessageBuffer* j)
        { return i->routingPriority() < j->routingPriority(); });

    // reset groups
    m_in_prio_groups[vnet].clear();
    int cur_prio = m_in_prio[vnet].front()->routingPriority();
    m_in_prio_groups[vnet].emplace_back();
    for (auto buf : m_in_prio[vnet]) {
        if (buf->routingPriority() != cur_prio)
            m_in_prio_groups[vnet].emplace_back();
        m_in_prio_groups[vnet].back().push_back(buf);
    }
}

void
PerfectSwitch::addOutPort(const std::vector<MessageBuffer*>& out,
                          const NetDest& routing_table_entry,
                          const PortDirection &dst_inport,
                          Tick routing_latency,
                          int link_weight)
{
    // Add to routing unit
    m_switch->getRoutingUnit().addOutPort(m_out.size(),
                                          out,
                                          routing_table_entry,
                                          dst_inport,
                                          link_weight);
    m_out.push_back({routing_latency, out});
}

PerfectSwitch::~PerfectSwitch()
{
}

MessageBuffer*
PerfectSwitch::inBuffer(int in_port, int vnet) const
{
    if (m_in[in_port].size() <= vnet) {
        return nullptr;
    }
    else {
        return m_in[in_port][vnet];
    }
}

void
PerfectSwitch::operateRegularVnet(int vnet) {
  if (m_pending_message_count[vnet] == 0)
        return;

    for (auto &in : m_in_prio_groups[vnet]) {
        // first check the port with the oldest message
        unsigned start_in_port = 0;
        Tick lowest_tick = MaxTick;
        for (int i = 0; i < in.size(); ++i) {
            MessageBuffer *buffer = in[i];
            if (buffer) {
                Tick ready_time = buffer->readyTime();
                if (ready_time < lowest_tick){
                    lowest_tick = ready_time;
                    start_in_port = i;
                }
            }
        }
        DPRINTF(RubyNetwork, "vnet %d: %d pending msgs. "
                            "Checking port %d first\n",
                vnet, m_pending_message_count[vnet], start_in_port);
        // check all ports starting with the one with the oldest message
        for (int i = 0; i < in.size(); ++i) {
            int in_port = (i + start_in_port) % in.size();
            MessageBuffer *buffer = in[in_port];
            if (buffer)
                operateMessageBuffer(buffer, vnet);
        }
    }
}

void
PerfectSwitch::operateVnet(int vnet)
{
#if defined (ZCLLC)
  if (sharedSwitch) {
    int incoming = m_round_robin_start;
    m_round_robin_start++;
    if (m_round_robin_start >= m_in.size()) {
      m_round_robin_start = 0;
    }

    if (m_pending_message_count[vnet] > 0) {
      // for all input ports, use round robin scheduling
      for (int counter = 0; counter < m_in.size(); counter++) {
        // round robin scheduling
        incoming++;
        if (incoming >= m_in.size()) {
          incoming = 0;
        }
        operateVnet(vnet, incoming, -1);
      }
    }
  } else {
    return operateRegularVnet(vnet);
  }
#else
    return operateRegularVnet(vnet);
    /*
    if (m_pending_message_count[vnet] == 0)
        return;

    for (auto &in : m_in_prio_groups[vnet]) {
        // first check the port with the oldest message
        unsigned start_in_port = 0;
        Tick lowest_tick = MaxTick;
        for (int i = 0; i < in.size(); ++i) {
            MessageBuffer *buffer = in[i];
            if (buffer) {
                Tick ready_time = buffer->readyTime();
                if (ready_time < lowest_tick){
                    lowest_tick = ready_time;
                    start_in_port = i;
                }
            }
        }
        DPRINTF(RubyNetwork, "vnet %d: %d pending msgs. "
                            "Checking port %d first\n",
                vnet, m_pending_message_count[vnet], start_in_port);
        // check all ports starting with the one with the oldest message
        for (int i = 0; i < in.size(); ++i) {
            int in_port = (i + start_in_port) % in.size();
            MessageBuffer *buffer = in[in_port];
            if (buffer)
                operateMessageBuffer(buffer, vnet);
        }
    }
    */
#endif
}

#if defined (ZCLLC)
Cycles PerfectSwitch::getNextCycleForCore(int c) const {
  auto currentSlotStart =
        m_switch->curCycle() / m_slot_width * m_slot_width;
   panic_if((currentSlotStart % m_slot_width != 0),
          "Slot start should be divided");
   auto so = getCurrentSlotOwner();
   auto delta = (c - so + m_ncore) % m_ncore;
   if(c == so)
    delta = m_ncore;
   // if inlinks() == 5, it's 4 core
   panic_if(currentSlotStart + delta * m_slot_width < m_switch->curCycle(),
          "Should be scheduled later, c: %d, ncore: %d", c, m_ncore);
   return Cycles(
    currentSlotStart + delta * m_slot_width - m_switch->curCycle());
}

Cycles PerfectSwitch::curCycle() const {
  return m_switch->curCycle();
}

void PerfectSwitch::operateVnet(int vnet, int message_limit) {
    // This is for round-robin scheduling
    int incoming = m_round_robin_start;
    m_round_robin_start++;
    if (m_round_robin_start >= m_in.size()) {
        m_round_robin_start = 0;
    }

    if (m_pending_message_count[vnet] > 0) {
        // for all input ports, use round robin scheduling
        for (int counter = 0; counter < m_in.size(); counter++) {
            // Round robin scheduling
            incoming++;
            if (incoming >= m_in.size()) {
                incoming = 0;
            }
            operateVnet(vnet, incoming, message_limit);
        }
    }
}

void PerfectSwitch::operateVnet(int vnet, int deviceIdx, int message_limit) {
    // Is there a message waiting?
    int incoming = deviceIdx;

    if (m_in[incoming].size() <= vnet) {
        return;
    }

    MessageBuffer *buffer = m_in[incoming][vnet];
    if (buffer == nullptr) {
        return;
    }

    operateMessageBuffer(buffer, vnet, message_limit);
}
#endif

void
PerfectSwitch::operateMessageBuffer(MessageBuffer *buffer, int vnet, int message_limit)
{
    MsgPtr msg_ptr;
    Message *net_msg_ptr = NULL;

    // temporary vectors to store the routing results
    static thread_local std::vector<BaseRoutingUnit::RouteInfo> output_links;

    Tick current_time = m_switch->clockEdge();

#if defined (ZCLLC)
    int sent_messages = 0;
    while (buffer->isReady(current_time) && ((message_limit < 0) || sent_messages < message_limit) ) {
#else
    while (buffer->isReady(current_time)) {
#endif
        DPRINTF(RubyNetwork, "incoming: %d\n", buffer->getIncomingLink());

        // Peek at message
        msg_ptr = buffer->peekMsgPtr();
        net_msg_ptr = msg_ptr.get();
        DPRINTF(RubyNetwork, "Message: %s\n", (*net_msg_ptr));


        output_links.clear();
        m_switch->getRoutingUnit().route(*net_msg_ptr, vnet,
                                         m_network_ptr->isVNetOrdered(vnet),
                                         output_links);

        // Check for resources - for all outgoing queues
        bool enough = true;
        for (int i = 0; i < output_links.size(); i++) {
            int outgoing = output_links[i].m_link_id;
            OutputPort &out_port = m_out[outgoing];

            if (!out_port.buffers[vnet]->areNSlotsAvailable(1, current_time))
                enough = false;

            DPRINTF(RubyNetwork, "Checking if node is blocked ..."
                    "outgoing: %d, vnet: %d, enough: %d\n",
                    outgoing, vnet, enough);
        }

        // There were not enough resources
        if (!enough) {
            scheduleEvent(Cycles(1));
            DPRINTF(RubyNetwork, "Can't deliver message since a node "
                    "is blocked\n");
            DPRINTF(RubyNetwork, "Message: %s\n", (*net_msg_ptr));
            break; // go to next incoming port
        }

        MsgPtr unmodified_msg_ptr;

        if (output_links.size() > 1) {
            // If we are sending this message down more than one link
            // (size>1), we need to make a copy of the message so each
            // branch can have a different internal destination we need
            // to create an unmodified MsgPtr because the MessageBuffer
            // enqueue func will modify the message

            // This magic line creates a private copy of the message
            unmodified_msg_ptr = msg_ptr->clone();
        }

        // Dequeue msg
        buffer->dequeue(current_time);
        m_pending_message_count[vnet]--;

        // Enqueue it - for all outgoing queues
        for (int i=0; i<output_links.size(); i++) {
            int outgoing = output_links[i].m_link_id;
            OutputPort &out_port = m_out[outgoing];

            if (i > 0) {
                // create a private copy of the unmodified message
                msg_ptr = unmodified_msg_ptr->clone();
            }

            // Change the internal destination set of the message so it
            // knows which destinations this link is responsible for.
            net_msg_ptr = msg_ptr.get();
            net_msg_ptr->getDestination() = output_links[i].m_destinations;

            // Enqeue msg
            DPRINTF(RubyNetwork, "Enqueuing net msg from "
                    "inport[%d][%d] to outport [%d][%d].\n",
                    buffer->getIncomingLink(), vnet, outgoing, vnet);

            out_port.buffers[vnet]->enqueue(msg_ptr, current_time,
                out_port.latency, m_switch->getNetPtr()->getRandomization(),
                m_switch->getNetPtr()->getWarmupEnabled());
        }
#if defined(ZCLLC)
        sent_messages++;
#endif
    }
}

#if defined (ZCLLC)
void
PerfectSwitch::enqueueROCQueue(int llc_idx, bool is_front) {
    DPRINTF(RubyNetwork, "Before: %s\n", this->m_roc_queue);
    const int ROCVnet = 3;
    // if failure something is wrong
    auto buffer = m_in[llc_idx][ROCVnet];
    panic_if(!buffer->isReady(curTick()), "ROC buffer should be ready");

    Tick current_time = m_switch->clockEdge();
    m_pending_message_count[ROCVnet]--;

    MsgPtr ptr = buffer->peekMsgPtr();
    buffer->dequeue(current_time);

    DPRINTF(RubyNetwork, "enqueueROCQueue: idx: %d\n", this->m_slot_manager.getCoreIDFromRequest(&*ptr));
    if(is_front) {
        DPRINTF(RubyNetwork, "enqueueROCQueue front\n");
        this->m_roc_queue.enqueueFrontROCRequest(this->m_slot_manager.getSlotOwner(),
                                          ptr);
    } else {
        DPRINTF(RubyNetwork, "enqueueROCQueue back\n");
        this->m_roc_queue.enqueueROCRequest(this->m_slot_manager.getSlotOwner(),
                                          ptr);
    }
    DPRINTF(RubyNetwork, "After: %s\n", this->m_roc_queue);
}

void
PerfectSwitch::dequeuROCQueue() {
    DPRINTF(RubyNetwork, "> Before: %s\n", this->m_roc_queue);
    DPRINTF(RubyNetwork, "dequeuROCQueue\n");
    const int RequestVnet = 0;
    int core = this->m_slot_manager.getSlotOwner();
    int llc_idx = this->m_slot_manager.getLLCDeviceId();
    // if failure something is wrong
    OutputPort &out_port = m_out[llc_idx];
    auto buffer = out_port.buffers[RequestVnet];

    Tick current_time = m_switch->clockEdge();

    // TODO: fix
    MsgPtr ptr = this->m_roc_queue.dequeueROCRequest(core);

    buffer->enqueue(ptr, current_time, m_switch->cyclesToTicks(Cycles(1)), false, false);

    DPRINTF(RubyNetwork, "> After: %s\n", this->m_roc_queue);
}

void
PerfectSwitch::handleSplitBusResponse() {
    // if this is split bus instance, the response bus needs to operate asynchronously
    // response bus occupies vnet 6 only
    // Three cases of request path:
    // 1. Request [C -> D Push Req] (if splitBus then markLLCDone) ->
          // Response [D -> C Pop Req]
    // 2. Request BI [C -> D Push Req] -> BIReq [D -> C' Push Req] ->
          // BIResponse [C' -> D PushReq] -> (MemResponse) -> Response [D-> C Pop Req]
    // 3. WB [C -> D Push Req] -> Resposne [C -> D Pop Req]
    // 4. Request [C -> D Push Req] -> FwdReq [D -> C' Push Req] ->
          // FwdResponse [C' -> D PushReq]
    // Responses are ordered by the initial request
    auto llc_device_idx = 0;
    panic_if(m_in[llc_device_idx].size() <= SlotManager::SplitResponseVnet,
        "Cannot find split response vnet on LLC, perhaps there's an error in \
        configuration");

    auto* llc_response_mb = m_in[llc_device_idx][SlotManager::SplitResponseVnet];
    auto current_time = curTick();

    // get the cores that have a inward or outward response message
    // the indices are core indices
    const int dir_to_core = 0;
    const int core_to_dir = 1;
    // [arbitration, [buffer_idx, dir]]
    std::map<int, std::tuple<int, int> > current_message_destinations;

    // collect all responses over the split bus
    // LLC response
    // Since LLC response always signifies the end of a transaction
    // the destination is the slot that we will occupy
    for(auto msg : llc_response_mb->m_prio_heap) {
        if(!mbIsMsgReady(msg, current_time)) continue;
        // this must be the response message from the LLC
        auto destinations /*: NetDest*/ = mbGetDestination<ResponseMsg>(msg);
        int any_message = 0;
        for(int i = 0; i < m_ncore; i++) {
            if(destinations.isElement(MachineID(MachineType::MachineType_L1Cache, i))) {
                int device_idx = m_slot_manager.coreToDeviceId(i);
                current_message_destinations.insert({device_idx, {0, dir_to_core} });
                any_message++;
            }
        }
        panic_if(any_message > 1, "Cannot check message into llc_response");
        // msg is ready
    }
    // BI responses or FwdGetM responses
    for(int device_idx = 1; device_idx < m_in.size(); device_idx++) {
        panic_if(m_in[device_idx].size() <= SlotManager::SplitResponseVnet,
                  "Split bus enabled on LLC but it is not connected");
        auto core_response_mb = m_in[device_idx][SlotManager::SplitResponseVnet];
        if(!core_response_mb->isReady(current_time)) continue;
        auto msg = core_response_mb->peekMsgPtr();
        auto originRequestor = this->mbGetOriginalRequestor<ResponseMsg>(msg);
        auto originalRequestorDeviceIdx =
          m_slot_manager.coreToDeviceId(originRequestor.getNum());
        current_message_destinations.insert({originalRequestorDeviceIdx,
                                            {device_idx, core_to_dir}});
    }

    DPRINTF(RubyNetwork,
        "current_message_destinations (response split bus): %d entries\n",
        current_message_destinations.size());
    for(auto it : current_message_destinations) {
        auto [device_idx, dir] = it.second;
        DPRINTF(RubyNetwork,
            "device_idx (slot to occupy): %d, (buffer to operate): %d, dir: %d\n",
              it.first, device_idx, dir);
    }

    DPRINTF(RubyNetwork, "current response order: ");
    for(auto it : *m_response_order) {
        DPRINTF(RubyNetwork, "%d \n", it);
    }

    // dispatch the collected messages
    // with work-conserving arbitration
    // selected = false;
    for(auto it = this->m_response_order->begin();
        it != this->m_response_order->end(); it++) {
        auto device_idx = *it;
        auto core = m_slot_manager.deviceIdToCore(device_idx);
        panic_if(m_in[device_idx].size() <= SlotManager::SplitResponseVnet,
            "Cannot find split response vnet on private L2, \
            perhaps there's an error in configuration");
        auto it_dir = current_message_destinations.find(device_idx);
        if(it_dir == current_message_destinations.end()) continue;

        auto [buffer_device_idx, dir] = it_dir->second;

        // now we know that there is ONE message that we could handle,
        // either it is in the LLC response buffer, or it is in the core response buffer
        if(dir == dir_to_core) {
            // okay but we need to delay the head for later scheduling
            auto head_msg_ptr = llc_response_mb->peekMsgPtr();
            auto initial_value = head_msg_ptr.get();
            auto destinations /*: NetDest*/ =
                mbGetDestination<ResponseMsg>(head_msg_ptr);
            // delay until we find the correct head
            while(!destinations.isElement(MachineID(MachineType::MachineType_L1Cache,
                                          core))) {
                // delay head
                llc_response_mb->delayHead(curTick(),
                    getObject()->cyclesToTicks(m_response_bus_latency));

                // ok and we move to next message
                head_msg_ptr = llc_response_mb->peekMsgPtr();
                destinations /*: NetDest*/ =
                  mbGetDestination<ResponseMsg>(head_msg_ptr);

                panic_if(initial_value == head_msg_ptr.get(),
                    "Cannot find the correct head after iterating through the \
                    whole llc response buffer");
            }
            // int head_device_idx = ;
            this->operateVnet(SlotManager::SplitResponseVnet,
                m_slot_manager.getLLCDeviceId(), 1);
            DPRINTF(RubyNetwork, "Split bus: LLC -> Core %d, deviceIdx = %d\n",
                core, m_slot_manager.getLLCDeviceId());
            m_response_order->erase(it);
        } else {  // core to LLC
            this->operateVnet(SlotManager::SplitResponseVnet, buffer_device_idx, 1);
            int buffer_core = m_slot_manager.deviceIdToCore(buffer_device_idx);
            DPRINTF(RubyNetwork,
                "Split bus: Core %d -> LLC, using slot of Core %d\n", buffer_core, core);
        }
        break;
    }

    if(current_message_destinations.size() > 1) {
        scheduleEvent(Cycles(m_response_bus_latency));
    }
}

void
PerfectSwitch::scheduleNextSlot() {
  // this is to prevent the slot being scheduled too many times
  if (m_last_scheduled_slot <= curCycle()) {
    auto nxt_slot = m_last_slot_start + this->m_slot_width;
    scheduleEvent(Cycles(nxt_slot - curCycle()));
    DPRINTF(RubyNetwork, "WCRR scheduling next slot to %d from %d!\n",
        nxt_slot, curCycle());
    m_last_scheduled_slot = Cycles(nxt_slot);
  }
}

bool PerfectSwitch::coreHasPendingRequest(int c) const {
  // whether a core has pending request
  // core c, vnet 0
  // incoming?
  return c == m_order.front() ||
         (m_in[c + 1][0] != nullptr && !m_in[c + 1][0]->isEmpty());
}

void PerfectSwitch::markLLCDone() {
    // we immediately schedule at next cycle when the LLC tells us that it's done
    ClockedObject* em = this->getObject();
    if(m_llc_end_event.scheduled()) {
        DPRINTF(RubyNetwork, "LLC done, RE-scheduling sometime later\n");
        em->reschedule(m_llc_end_event, em->clockEdge(m_end_delay), true);
    } else {
        DPRINTF(RubyNetwork, "LLC done, scheduling sometime later\n");
        em->schedule(m_llc_end_event, em->clockEdge(m_end_delay));
    }
    scheduleEvent(m_end_delay + Cycles(1));
    // The LLC should be finished at the momment
}

void PerfectSwitch::markLLCDone(bool wait_for_data) {
    markLLCDone();
    this->m_slot_manager.m_llc_finish_wait_for_data_response = wait_for_data;
}

// useful when we account for the response bus latency!
void PerfectSwitch::markLLCDone(Cycles delay) {
    // we immediately schedule at next cycle when the LLC tells us that it's done
    ClockedObject* em = this->getObject();
    if(m_llc_end_event.scheduled()) {
        DPRINTF(RubyNetwork, "LLC done, RE-scheduling sometime later\n");
        em->reschedule(m_llc_end_event, em->clockEdge(delay), true);
    } else {
        DPRINTF(RubyNetwork, "LLC done, scheduling sometime later\n");
        em->schedule(m_llc_end_event, em->clockEdge(delay));
    }
    scheduleEvent(delay + Cycles(1));
    // The LLC should be finished at the momment
}

void PerfectSwitch::markTransactionDone() {
    panic_if(true, "markTransactionDone is not implemented");
}
#endif

void
PerfectSwitch::regularWakeup() {
  // Give the highest numbered link priority most of the time
  m_wakeups_wo_switch++;
  int highest_prio_vnet = m_virtual_networks-1;
  int lowest_prio_vnet = 0;
  int decrementer = 1;

  // invert priorities to avoid starvation seen in the component network
  if (m_wakeups_wo_switch > PRIORITY_SWITCH_LIMIT) {
    m_wakeups_wo_switch = 0;
    highest_prio_vnet = 0;
    lowest_prio_vnet = m_virtual_networks-1;
    decrementer = -1;
  }

  // For all components incoming queues
  for (int vnet = highest_prio_vnet;
    (vnet * decrementer) >= (decrementer * lowest_prio_vnet);
    vnet -= decrementer) {
#if defined (SNOOPING_BUS)
    if ((vnet == 0) && (m_switch_id == 0)) {
      operateTDMRequestBus(vnet);
    } else if ((vnet == 2) && (m_switch_id == 0)) {
      operateOARespBus(vnet);
    } else {
      operateVnet(vnet);
    }
#else
    operateVnet(vnet);
#endif // SNOOPING_BUS
  }
}

void
PerfectSwitch::wakeup()
{
#if defined (ZCLLC)
/* There are several possibilities when wakeup is called
     * that we model:
     * 1. vanilla TDM (!m_work_conserving && !m_subslot_opt )
     * 2. Work conserving (m_work_conserving && !m_subslot_opt)
     * 3. WC + Subslot (m_work_conserving && m_subslot_opt)
     * In 1 and 2, once a slot starts, it will always be slot width
     * In 3, the slot length will be variable, depending on whether it hits
       or misses in the next level cache
     */

    /* there are 3 sources that can wakeup the bus
     * 1. the caches: (a) issue new request (b) send BI response
     * 2. the LLC: (a) send response, (b) send request for issuing later, and
                                          we need to maintain order for it
     *             (c) send back-invalidation
     * 3. the bus: self-scheduled wake-up - (a) send requests in ROC order
     *
     * 1.a and 3.a are subject to delays and may be scheduled in futher cycles
     *
     * 1.b, 2.a, 2.b, 2.c, 3.a can be processed immediately, however,
       these should only happen for the bus owner - we don't have
       dedicated data buses anyways
     */

    if (sharedSwitch) {
    // Check SlotManager.hh for the rationale of how the bus handle events
    m_slot_manager.updateBusStatus();
    auto actions = m_slot_manager.getNextEvent(
        this->m_in,
        this->m_roc_queue,
        this->m_response_order,
        this->m_llc_finish_signal
    );

    for(auto action : actions) {
        if(action.act == action.OpVnet)  {
            // for response this would be different
            panic_if(action.OpVnet == SlotManager::SplitResponseVnet,
                "SplitResposneVnet operates asynchronously, and should not \
                be accessed by the slot manager");
            operateVnet(action.vnet, action.deviceIdx, action.messageLimit);
        } else if(action.act == action.ROCQueue) {
            // ROC
            enqueueROCQueue(action.deviceIdx, false);
        } else if(action.act == action.ROCQueueFront) {
            enqueueROCQueue(action.deviceIdx, true);
        } else if(action.act == action.ROCDequeue) {
            dequeuROCQueue();
        } else if(action.act == action.SchedEnd) {
            panic("SchedEnd is not implemented");
        } else {
            panic("Unrecognized action");
        }
    }

    if(this->is_split_bus()) {
        // for filtering past requests which may have been satisfied
        // through c2c interconnect we need to remove that from the
        // response order arbitration
        handleSplitBusResponse();
    }
    } else {
      regularWakeup();
    }
#else
    regularWakeup();
    /*
    // Give the highest numbered link priority most of the time
    m_wakeups_wo_switch++;
    int highest_prio_vnet = m_virtual_networks-1;
    int lowest_prio_vnet = 0;
    int decrementer = 1;

    // invert priorities to avoid starvation seen in the component network
    if (m_wakeups_wo_switch > PRIORITY_SWITCH_LIMIT) {
        m_wakeups_wo_switch = 0;
        highest_prio_vnet = 0;
        lowest_prio_vnet = m_virtual_networks-1;
        decrementer = -1;
    }

    // For all components incoming queues
    for (int vnet = highest_prio_vnet;
         (vnet * decrementer) >= (decrementer * lowest_prio_vnet);
         vnet -= decrementer) {
#if defined (SNOOPING_BUS)
        if ((vnet == 0) && (m_switch_id == 0)) {
            operateTDMRequestBus(vnet);
        } else if ((vnet == 2) && (m_switch_id == 0)) {
            operateOARespBus(vnet);
        } else {
            operateVnet(vnet);
        }
#else
        operateVnet(vnet);
#endif // SNOOPING_BUS
    }
*/
#endif // ZCLLC
}

void
PerfectSwitch::storeEventInfo(int info)
{
    m_pending_message_count[info]++;
}

void
PerfectSwitch::clearStats()
{
}
void
PerfectSwitch::collateStats()
{
}


void
PerfectSwitch::print(std::ostream& out) const
{
    out << "[PerfectSwitch " << m_switch_id << "]";
}

#ifdef SNOOPING_BUS
bool
PerfectSwitch::isStartOfSlot() {
    uint64_t cur_cycle = m_switch->curCycle();
    DPRINTF(RubyNetwork, "cur_cycle: %s, tdm_slot_width: %s\n", cur_cycle, m_tdm_slot_width);
    return (cur_cycle % m_tdm_slot_width == 0)? true : false;
}

uint64_t
PerfectSwitch::getNextSlotStartCycle () {
    uint64_t cur_cycle = m_switch->curCycle();
    return (cur_cycle / m_tdm_slot_width + 1) * m_tdm_slot_width;
}

void
PerfectSwitch::operateTDMRequestBus(int vnet) {
    assert(m_switch_id == 0);

    // We only perform TDM arbitration on vnet 0
    assert(vnet == 0);

    // Optimization: directly return if the current cycle is smaller than the next scheduled event
    uint64_t current_cycle = m_switch->curCycle();
    /*
    if (m_req_bus_next_free_cycle > current_cycle) {
        return;
    }
    */

    assert(m_in_prio_groups[vnet].size() == 1);  // sanity check

    if (isStartOfSlot()) {
      DPRINTF(RubyNetwork, "START OF SLOT, OWNER: %d\n", m_request_bus_owner);
    }

    for (auto &in : m_in_prio_groups[vnet]) {
        int j = m_request_bus_owner;
        Tick current_time = m_switch->clockEdge();
        MessageBuffer *in_buffer;

        // Search for the next input buffer that has message ready
        bool message_is_ready = false;
        int num_in_port = in.size();
        for (int i = 0; i < num_in_port; i++) {
            DPRINTF(RubyNetwork, "CHECKING IN BUFFER i: %d\n", i);
            in_buffer = in[j];
            if (in_buffer->isReady(current_time)) {
                message_is_ready = true;
                break;
            }
            j = (j + 1) % num_in_port;
        }

        if (!message_is_ready) {
            DPRINTF(RubyNetwork, "NO MESSAGE READY... \n");
            return;
            // try again
            /*
            uint64_t next_slot_start_cycle = getNextSlotStartCycle();
            assert(next_slot_start_cycle > current_cycle);
            DPRINTF(RubyNetwork, "NEXT SCHEDULE EVENT: %d\n", Cycles(next_slot_start_cycle-current_cycle));
            scheduleEvent(Cycles(next_slot_start_cycle-current_cycle));
            m_req_bus_next_free_cycle = next_slot_start_cycle;
            return;
            */
        }

        if (isStartOfSlot()) {
            DPRINTF(RubyNetwork, "START OF SLOT, OWNER: %d\n", m_request_bus_owner);
            // hack the message destination
            MsgPtr in_msg_smart_ptr;
            RequestMsg* in_msg_ptr = NULL;
            in_msg_smart_ptr = in_buffer->peekMsgPtr();
            in_msg_ptr = dynamic_cast<RequestMsg *> (in_msg_smart_ptr.get());
            assert(in_msg_ptr);
            NetDest& destination = in_msg_ptr->getDestination();
            destination.clear();
            destination.add(in_msg_ptr->getrequestor());

            // move the message to output buffer
            operateMessageBufferOnce(in_buffer, vnet);
            DPRINTF(RubyNetwork, "TDM arbitration: slot owner %d sent message\n ", j);

            // update next owner
            j = (j + 1) % num_in_port;
            m_request_bus_owner = j;
        }

        uint64_t next_slot_start_cycle = getNextSlotStartCycle();
        assert(next_slot_start_cycle > current_cycle);
        DPRINTF(RubyNetwork, "NEXT SCHEDULE EVENT: %d\n", Cycles(next_slot_start_cycle-current_cycle));
        scheduleEvent(Cycles(next_slot_start_cycle-current_cycle));
        m_req_bus_next_free_cycle = next_slot_start_cycle;
    }
}


// This function is basically a copy of operateMessageBuffer except that it only sends one message at a time
void
PerfectSwitch::operateMessageBufferOnce(MessageBuffer *buffer, int vnet)
{
    MsgPtr msg_ptr;
    Message *net_msg_ptr = NULL;

    // temporary vectors to store the routing results
    static thread_local std::vector<BaseRoutingUnit::RouteInfo> output_links;

    Tick current_time = m_switch->clockEdge();

    bool msg_sent = false;

    while (buffer->isReady(current_time)) {
        DPRINTF(RubyNetwork, "incoming: %d\n", buffer->getIncomingLink());

        // Peek at message
        msg_ptr = buffer->peekMsgPtr();
        net_msg_ptr = msg_ptr.get();
        DPRINTF(RubyNetwork, "Message: %s\n", (*net_msg_ptr));


        output_links.clear();
        m_switch->getRoutingUnit().route(*net_msg_ptr, vnet,
                                         m_network_ptr->isVNetOrdered(vnet),
                                         output_links);

        // Check for resources - for all outgoing queues
        bool enough = true;
        for (int i = 0; i < output_links.size(); i++) {
            int outgoing = output_links[i].m_link_id;
            OutputPort &out_port = m_out[outgoing];

            if (!out_port.buffers[vnet]->areNSlotsAvailable(1, current_time))
                enough = false;

            DPRINTF(RubyNetwork, "Checking if node is blocked ..."
                    "outgoing: %d, vnet: %d, enough: %d\n",
                    outgoing, vnet, enough);
        }

        // There were not enough resources
        if (!enough) {
            scheduleEvent(Cycles(1));
            DPRINTF(RubyNetwork, "Can't deliver message since a node "
                    "is blocked\n");
            DPRINTF(RubyNetwork, "Message: %s\n", (*net_msg_ptr));
            break; // go to next incoming port
        }

        MsgPtr unmodified_msg_ptr;

        if (output_links.size() > 1) {
            // If we are sending this message down more than one link
            // (size>1), we need to make a copy of the message so each
            // branch can have a different internal destination we need
            // to create an unmodified MsgPtr because the MessageBuffer
            // enqueue func will modify the message

            // This magic line creates a private copy of the message
            unmodified_msg_ptr = msg_ptr->clone();
        }

        // Dequeue msg
        buffer->dequeue(current_time);
        m_pending_message_count[vnet]--;

        // Enqueue it - for all outgoing queues
        for (int i=0; i<output_links.size(); i++) {
            int outgoing = output_links[i].m_link_id;
            OutputPort &out_port = m_out[outgoing];

            if (i > 0) {
                // create a private copy of the unmodified message
                msg_ptr = unmodified_msg_ptr->clone();
            }

            // Change the internal destination set of the message so it
            // knows which destinations this link is responsible for.
            net_msg_ptr = msg_ptr.get();
            net_msg_ptr->getDestination() = output_links[i].m_destinations;

            // Enqeue msg
            DPRINTF(RubyNetwork, "Enqueuing net msg from "
                    "inport[%d][%d] to outport [%d][%d].\n",
                    buffer->getIncomingLink(), vnet, outgoing, vnet);

            out_port.buffers[vnet]->enqueue(msg_ptr, current_time,
                                           out_port.latency, false, false, false);
        }

        msg_sent = true;
        break;  // We only want one message to be sent at a time
    }

    assert(msg_sent);  // sanity check: one message has been sent
}

void
PerfectSwitch::operateOARespBus(int vnet) {
    assert(m_switch_id == 0);

    // We only perform oldest age arbitration on response bus (i.e. vnet is 2)
    assert(vnet == 2);

    uint64_t current_cycle = m_switch->curCycle();
    if (m_resp_bus_next_free_cycle > current_cycle) {
        return;
    }

    assert(m_in_prio_groups[vnet].size() == 1);  // sanity check
    for (auto &in : m_in_prio_groups[vnet]) {
        Tick current_time = m_switch->clockEdge();
        MessageBuffer *in_buffer;

        // Search for the response message that has the highest priority (i.e. lowest request ID)
        bool first_found = false;
        Cycles lowest_ID = Cycles(0);
        int found_port = 0;
        int num_in_port = in.size();
        for (int i = 0; i < num_in_port; i++) {
            in_buffer = in[i];
            for (int j = 0; j < in_buffer->m_prio_heap.size(); j++) {
              ResponseMsg* in_msg_ptr = NULL;
                in_msg_ptr = dynamic_cast<ResponseMsg *> (in_buffer->m_prio_heap[j].get());
                assert(in_msg_ptr != NULL);

                // if message is ready
                if (in_msg_ptr->getLastEnqueueTime() <= current_time) {
                    if (first_found == false) {
                        lowest_ID = in_msg_ptr->m_reqID;
                        found_port = i;
                        first_found = true;
                    } else if (in_msg_ptr->m_reqID < lowest_ID) {
                        lowest_ID = in_msg_ptr->m_reqID;
                        found_port = i;
                    }
                }
            }
        }

        if (!first_found) {
            return;
        }

        in_buffer = in[found_port];
        bool found = false;
        int buf_size = in_buffer->m_prio_heap.size();
        while (true) {
            if (buf_size < 0) {
                break;
            }
            buf_size--;
            ResponseMsg* in_msg_ptr = NULL;
            in_msg_ptr = dynamic_cast<ResponseMsg *> (in_buffer->m_prio_heap.front().get());
            assert(in_msg_ptr != NULL);
            if (in_msg_ptr->m_reqID == lowest_ID) {
                found = true;
                break;
            } else {
                assert(in_msg_ptr->getLastEnqueueTime() <= current_time);
                in_buffer->delayHead(current_time, 1);
            }
        }
        assert(found == true);

        // move the message to output buffer
        operateMessageBufferOnce(in_buffer, vnet);
        m_resp_bus_next_free_cycle = current_cycle + m_resp_bus_slot_width;

        DPRINTF(RubyNetwork, "OA arbitration: resp bus owner %d sent response message with reqID %d\n", found_port, lowest_ID);
        scheduleEvent(Cycles(m_resp_bus_next_free_cycle-current_cycle));
    }
}
#endif

} // namespace ruby
} // namespace gem5
