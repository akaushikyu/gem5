#include "sim/clocked_object.hh"
#include "xyz/SlotManager.hh"
#include "mem/ruby/common/Consumer.hh"
#include "mem/ruby/slicc_interface/Message.hh"
#include "mem/ruby/network/MessageBuffer.hh"
#include "mem/ruby/protocol/RequestMsg.hh"
#include "mem/ruby/protocol/ResponseMsg.hh"
#include "sim/cur_tick.hh"

#include "debug/ZCLLC_TDMSwitch.hh"
#include "debug/ZCLLC_TDM.hh"
#include "debug/TDMOrder.hh"
#include "debug/ROC.hh"

#include <vector>

using namespace gem5;
using namespace gem5::ruby;

SlotManager::SlotManager(
    ClockedObject& parent,
    Consumer& consumer,
    const std::vector<int>& schedule,
    bool work_conserving,
    bool subslot_opt,
    bool split_bus,
    bool enable_roc,
    Cycles full_slot_width,

    int ncore
) :
m_schedule(schedule),
m_llc_finish_signal(false),
m_llc_finish_wait_for_data_response(false),
m_consumer(consumer),
m_clock(parent),
m_work_conserving(work_conserving),
m_subslot_opt(subslot_opt),
m_split_bus(split_bus),
m_enable_roc(enable_roc),
m_full_slot_width(full_slot_width),
m_current_slot_idx(0),
m_ncore(ncore)
 {
    if(work_conserving) {
        m_slot_status = SlotStatus::SlotReady;
    } else {
        m_slot_status = SlotStatus::SlotIdle;
    }
    DPRINTF(ZCLLC_TDM, "work_conserving: %d, subslot_opt: %d, full_slot_width: %d\n", work_conserving, subslot_opt, full_slot_width);
}

int SlotManager::getCoreIDFromRequest(const Message* msg) const {
    const RequestMsg* req = dynamic_cast<const RequestMsg*>(msg);
    auto machineID = req->getRequestor();
    panic_if(machineID.getType() != MachineType::MachineType_L1Cache, "ROCQueue only accepts requests originated from L1Cache");
    return static_cast<int>(machineID.getNum());
};
int SlotManager::getCoreIDFromResponse(const Message* msg) const {
    const ResponseMsg* req = dynamic_cast<const ResponseMsg*>(msg);
    NetDest destinations = req->getDestination();
    for(int i = 0; i < m_ncore; i++) {
        if(destinations.isElement(MachineID(MachineType::MachineType_L1Cache, i))) {
            return i;
        }
    }
    panic("Cannot find core id from response\n");
};

Cycles
SlotManager::vanillaNextSlotBoundary(Cycles c, int core) const {
    bool found = core == -1;
    for(int i = 0; core != -1 && i < m_schedule.size(); i++) {
        int idx = (m_current_slot_idx + i + 1) % m_schedule.size();
        int candidate_core = m_schedule[idx];
        if(core == candidate_core) {
            c = Cycles(c + i * this->m_full_slot_width);
            found = true;
            break;
        }
    }
    panic_if(!found, "Core %d not found in schedule\n", core);
    auto div = c / this->m_full_slot_width;
    return Cycles((div + 1) * this->m_full_slot_width);
}

void
SlotManager::scheduleNextSlotBoundary(int core) {
        if(this->isVanilla()) {
            auto curCycle = m_clock.curCycle();
            auto nextSlotCycle = vanillaNextSlotBoundary(curCycle, core);
            panic_if(nextSlotCycle <= curCycle, "next slot cycle %d is not greater than current cycle %d\n", nextSlotCycle, curCycle);
            DPRINTF(ZCLLC_TDM, "Scheduling next slot boundary at %d\n", nextSlotCycle);
            m_consumer.scheduleEvent(Cycles(nextSlotCycle - curCycle));
        } else if(this->isWorkConserving() && !this->isSubslotOpt()) {
            auto curCycle = m_clock.curCycle();
            auto div = curCycle / this->m_full_slot_width;
            auto nextSlotCycle = Cycles((div + 1) * this->m_full_slot_width);
            panic_if(nextSlotCycle <= curCycle, "next slot cycle %d is not greater than current cycle %d\n", nextSlotCycle, curCycle);
            DPRINTF(ZCLLC_TDM, "Scheduling next slot boundary at %d\n", nextSlotCycle);
            m_consumer.scheduleEvent(Cycles(nextSlotCycle - curCycle));
        } else if(this->isSubslotOpt()) {
            m_consumer.scheduleEvent(Cycles(1));
            DPRINTF(ZCLLC_TDM, "Scheduling next slot boundary at next cycle\n");
        }
}
bool SlotManager::probeLLCResponse(int core, int slot_idx,
    const std::vector<std::vector<MessageBuffer*> >& m_in,
    std::list<TDMAction>& actions) {
    int device_idx = getLLCDeviceId();
    auto& in = m_in[device_idx];
    auto& buffer = in[ResponseVnet];
    // handle one response only
    if(buffer->isReady(gem5::curTick())) {
        panic_if(this->m_split_bus, "LLC should not send response over normal bus");

        const Message* msg = buffer->peek();
        int core_id = getCoreIDFromResponse(msg);
        if(core_id != core) return false;

        DPRINTF(ZCLLC_TDMSwitch, "Encountered LLC response to core %d, current status: %d\n", core_id, this->m_slot_status);
        if(this->m_slot_status == SlotStatus::SlotReady) {
            DPRINTF(ZCLLC_TDMSwitch, "Start new slot to send LLC Response\n");
            this->scheduleNextSlotBoundary(core);
            actions.push_back(
                {TDMAction::OpVnet, ResponseVnet, device_idx, -1}
            );
            this->activateSlot(slot_idx, ResponseVnet);
        } else if(this->m_slot_status == SlotStatus::SlotIdle ||
            this->m_slot_status == SlotStatus::SlotEnd
        ) {
            DPRINTF(ZCLLC_TDMSwitch, "Schedule next slot\n");
            this->scheduleNextSlotBoundary(core);
            deactivateSlotIfEnd();
            // the slot status will be
        } else if(this->m_slot_status == SlotStatus::SlotActive || this->m_slot_status == SlotStatus::SlotWaitDataResponse) {
            // LLC can issue it back within the same same slot
            DPRINTF(ZCLLC_TDMSwitch, "LLC response for core %d sent within a slot (slot owner: %d)\n", core_id, this->getSlotOwner());
            if(this->getSlotOwner() == core) {
                actions.push_back(
                    {TDMAction::OpVnet, ResponseVnet, device_idx, -1}
                );
            }
            if(this->m_slot_status == SlotStatus::SlotWaitDataResponse) {
                deactivateSlotIfEnd();
            }
        }
        return true;
    }
    return false;
}

bool SlotManager::probeCoreRequest(int core, int slot_idx,
        ROCQueue& roc_queue,
        std::list<int>* response_order,
        const std::vector<std::vector<MessageBuffer*> >& m_in,
        std::list<TDMAction>& actions) {
    int device_idx = coreToDeviceId(core);
    auto& in = m_in[device_idx];
    auto& buffer = in[RequestVnet];
    if(buffer->isReady(gem5::curTick())) {
        DPRINTF(ZCLLC_TDMSwitch, "Encountered Core request from core %d, slot status: %d\n", core, this->m_slot_status);

        if(this->m_slot_status == SlotStatus::SlotReady) {
            this->scheduleNextSlotBoundary(core);
            actions.push_back(
                {TDMAction::OpVnet, RequestVnet, device_idx, 1}
            );
            this->activateSlot(slot_idx, RequestVnet);
            // enqueue into the request_queue
            if(response_order != nullptr) {
                auto msg = dynamic_cast<const RequestMsg*>(buffer->peek());
                if(!msg->getisWritebackRequest()) {
                    // this is built upon the assumption that there is 1 outstanding request
                        // remove the core from the reorder bus, if any
                    auto it = std::find(response_order->begin(), response_order->end(), device_idx);
                    if (it != response_order->end()) {
                        response_order->erase(it);
                    }

                    response_order->push_back(device_idx);
                    DPRINTF(ZCLLC_TDMSwitch, "recording request for the split bus: %d, size: %d\n", core, response_order->size());
                    // msg->print(std::cout);
                    // std::cout << std::endl;
                }
                // FIXME: take parameters instead of hardcoding
                panic_if(response_order->size() > m_ncore, "We currently only support %d cores\n", m_ncore);
            }
        } else if(this->m_slot_status == SlotStatus::SlotIdle ||
                    this->m_slot_status == SlotStatus::SlotEnd
        )  {
            this->scheduleNextSlotBoundary(core);
            deactivateSlotIfEnd();
            // simply ignore the request if the bus is active, will
            // handle in the slot end state
            // this->scheduleNextSlotBoundary(core);
        } else if(this->m_slot_status == SlotStatus::SlotWaitDataResponse) {
            this->scheduleNextSlotBoundary(core);
        }
        return true;
    }
    return false;
}

bool SlotManager::probeROCRequest(int core, int slot_idx, const ROCQueue& roc_queue, std::list<TDMAction>& actions) {
    if (roc_queue.coreHasRequestAtHead(core)) {
        DPRINTF(ZCLLC_TDMSwitch, "Encountered ROCReq of %d, status %d\n", core, this->m_slot_status);
        if (this->m_slot_status == SlotStatus::SlotReady) {
            actions.push_back({TDMAction::ROCDequeue, -1, coreToDeviceId(core), 1});
            this->activateSlot(slot_idx, ROCVnet);
        } else if(this->m_slot_status == SlotStatus::SlotIdle ||
                    this->m_slot_status == SlotStatus::SlotEnd) {
            this->scheduleNextSlotBoundary(core);
            deactivateSlotIfEnd();
        }
        return true;
    }
    return false;
}

std::list<TDMAction>
SlotManager::getNextEvent(
        const std::vector<std::vector<MessageBuffer*> >& m_in,
        ROCQueue& roc_queue,
        std::list<int>* response_order,
        bool llc_finish_signal
) {
    // LLCFinish
    // Active -> End
    std::list<TDMAction> actions;
    if(this->m_llc_finish_signal) {
        panic_if(this->m_slot_status != SlotStatus::SlotActive && this->m_slot_status != SlotStatus::SlotWaitDataResponse,
            "LLC finish signal should only be active when a slot is active, current status: %d\n",
            this->m_slot_status
        );
        panic_if(this->m_llc_finish_wait_for_data_response && this->isSplitBus(), "Full slot wait for data response should not be present in split bus mode\n");
        // this->scheduleNextClosestSlotBoundary();
        DPRINTF(ZCLLC_TDMSwitch, "LLC finish signal encountered, current_status: %d, cleaning up remaining messages\n", this->m_slot_status);
        if(this->m_llc_finish_wait_for_data_response) {
            this->m_slot_status = SlotStatus::SlotWaitDataResponse;
        } else {
            this->m_slot_status = SlotStatus::SlotEnd;
        }
        DPRINTF(ZCLLC_TDMSwitch, "    -- current_status (new): %d\n", this->m_slot_status);

        // actions.push_back(
        //     {TDMAction::SchedEnd, 0}
        // )
    }

    auto precedence = getCorePrecedence();
    bool detected_non_split_bus_llc_response = false;
    int _pre_size = actions.size();
    if(!this->isSplitBus() && (this->m_slot_status == SlotStatus::SlotActive || this->m_slot_status == SlotStatus::SlotWaitDataResponse))
        this->probeLLCResponse(
            this->getSlotOwner(),
            this->m_current_slot_idx, m_in, actions);
    detected_non_split_bus_llc_response = actions.size() > _pre_size;

    // here indicate the cases where we would start a new slot
    for(auto [core, slot_idx] : precedence) {
        // LLCResponse(i)
        // In split bus transaction, the LLC sending response independently
        if(!this->isSplitBus() && !detected_non_split_bus_llc_response && this->probeLLCResponse(core, slot_idx, m_in, actions)) {
            break;
        }
        if(this->probeCoreRequest(core, slot_idx, roc_queue, response_order, m_in, actions)) {
            break;
        }
        if(this->probeROCRequest(core, slot_idx, roc_queue, actions)) {
            break;
        }
    }

    // CoreResp(i)
    // we can have unlimited response from core thanks to p2p
    //
    // when split bus is enabled, BI response should go through the response bus
    // Here we only look at ResponseVnet, which is the shared bus/p2p interconnect
    for(auto [core, slot_idx] : precedence) {
        int device_idx = coreToDeviceId(core);
        auto& in = m_in[device_idx];
        auto& buffer = in[ResponseVnet];
        if(buffer->isReady(gem5::curTick())) {
            // auto msg = buffer->peek();

            if(this->m_slot_status == SlotStatus::SlotActive  || this->m_slot_status == SlotStatus::SlotWaitDataResponse ) {
                DPRINTF(ZCLLC_TDMSwitch, "Encountered Core response from core %d\n", core);
                actions.push_back(
                    {TDMAction::OpVnet, ResponseVnet, device_idx, -1}
                );
            }
        }
    }

    // LLCROCReq(i)
    // LLCROCRequeueReq(i)
    {
        int device_idx = getLLCDeviceId();
        auto& in = m_in[device_idx];
        auto& buffer = in[ROCVnet];
        if(buffer->isReady(gem5::curTick())) {
            if(this->m_slot_status == SlotStatus::SlotActive) {
                DPRINTF(ZCLLC_TDMSwitch, "Encountered LLCROCReq/rereq\n");
                if(this->m_slot_initiatining_source == RequestVnet) {
                    actions.push_back(
                        {TDMAction::ROCQueue, -1, device_idx, 1}
                    );
                } else if(this->m_slot_initiatining_source == ROCVnet) {
                    actions.push_back(
                        {TDMAction::ROCQueueFront, -1, device_idx, 1}
                    );
                }
            } else {
                panic("ROC request encountered when a slot is not active\n");
            }
        }
    }

    // LLCBI(i) or LLCDowngrade
    {
        int device_idx = getLLCDeviceId();
        auto& in = m_in[device_idx];
        auto& buffer = in[ForwardVnet];
        if(buffer->isReady(gem5::curTick())) {
            if(this->m_slot_status == SlotStatus::SlotActive) {
                DPRINTF(ZCLLC_TDMSwitch, "Encountered LLCBI or LLCDowngrade\n");
                actions.push_back(
                    {TDMAction::OpVnet, ForwardVnet, device_idx, -1}
                );
            } else {
                panic("BI request encountered when a slot is not active\n");
            }
        }
    }

    if(this->m_slot_status == SlotStatus::SlotEnd) {
        DPRINTF(ZCLLC_TDMSwitch, "Slot end detected and no extra events, forcing stop\n");
        deactivateSlotIfEnd();
    }

    return actions;
}

std::vector< SlotManager::pii > SlotManager::getCorePrecedence() const {
    std::vector< SlotManager::pii > precedence;
    uint64_t core_mask = 0;
    for(
        int i = 0, idx = (m_current_slot_idx + 1) % m_schedule.size();
        i < m_schedule.size();
        i++) {
            int core = m_schedule[idx];
            if(core_mask & (1 << core)) continue;

            precedence.push_back({core, idx});
            core_mask |= (1 << core);

            idx++;
            if(idx >= m_schedule.size()) idx = 0;
    }
    return precedence;
}
