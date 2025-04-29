#ifndef __XYZ_SLOT_MANAGER_HH__
#define __XYZ_SLOT_MANAGER_HH__

#include "sim/clocked_object.hh"
#include "mem/ruby/common/Consumer.hh"
#include "xyz/ROCQueue.hh"
#include "base/trace.hh"
#include "debug/ZCLLC_TDM.hh"
#include "debug/ZCLLC_TDMSwitch.hh"

#include <vector>

namespace gem5 {

namespace ruby {

class Consumer;
class MessageBuffer;


enum SlotStatus {
    SlotIdle = 0,
    SlotReady = 1,
    SlotStart = 2,
    SlotActive = 3,
    SlotWaitDataResponse = 4,
    SlotEnd = 5
};

// POD struct
struct TDMAction {
    enum Type {
        OpVnet, ROCQueue, ROCQueueFront, ROCDequeue, SchedEnd
    };
    Type act;
    int vnet;
    int deviceIdx;
    int messageLimit;
};

// POD struct
struct TDMEvent {
    enum Type {
        Core, CoreResp, LLCResp, LLCROCReq, LLCBI, ROC, LLCSlotEnd
    };

    Type ev;
    int ev_core;

};

/**
 * there are 3 sources that can wakeup the bus
 * 1. the caches: (a) issue new request (b) send BI response
 * 2. the LLC: (a) send response, (b) send request for issuing later, and we need to maintain order for it
 *             (c) send back-invalidation
 * 3. the bus: self-scheduled wake-up - (a) send requests in ROC order
 *
 * 1.a and 3.a are subject to delays and may be scheduled in futher cycles
 *
 * 1.b, 2.a, 2.b, 2.c, 3.a can be processed immediately, however, these should only happen
 * for the bus owner - we don't have dedicated data buses anyways
 */
/** The bus is in one of three states:
 * Idle, Start, Active, End and each of them will accept different types of events shown below
 * as a state machine.
 *
 * Note that "End" is a special state that facilitates the implementation in simulation for
 * easier scheduling of the next slot start and it is not really needed in real hardware
 * Note that we should also consider how we could incorporate the support for split bus, in which the
 * resposes are not handled by the our bus
 * note that causes like [ss]C or [!ss]C indicates that the condition C is only checked
 * when the bus is configured with subslot_opt or not, same with wc, va
 * ss: subslot_opt
 * wc: work conserving
 * va: vanilla
 *
 * Idle and Ready are needed in vanilla mode, where Ready means that we are at multiples of full_slot_width
 * wc and ss can fire start at any cycles, and hence the default state is Ready
 *
 * We have the following events
 * Core(i), CoreBIResp(i)
 * LLCResp(i), LLCROCReq(i), LLCBI(i)
 * ROC(i)
 * Also, note that there are multiple events that can happen at the same cycle
 *
 * The slot owner is dependent on the slot status and whether it is va/ss/wc
 * For va, this is static, and for ss/wc it is dependent on previous slot owner,
 * which looks like something as follows:
 *
 * for i = 0; i < schedule.size(); i++ {
 *      check events for core i, and if there's an event that can be handled, then i is the slot owner
 * }
 *
 *          Core(i) CoreBIResp(i) LLCResp(i) LLCROCReq(i) LLCBI(i) ROC(i)
 * Idle    
 * Ready
 * Start
 * Active
 * End
 *
 * (Only va has Idle state)
 * Idle /\ [va] cycle is multiple of full_slot_width -> Ready;
 * Idle /\ [va] any requests from core i or response to core i from LLC  -> Idle; schedule next slot for i
 *
 * Ready /\ core i has a request /\ slot owner is i /\ [va]cycle is slot start cycle -> Start
 * Ready /\ ROC head has a request /\ slot owner is ROC head -> Start
 * Ready /\ LLC has a response for core i /\ slot owner is i -> Start
 * Active /\ LLC has a back invalidation -> Active
 * Active /\ core i has a back invalidation response -> Active
 * Active /\ LLC has a response for core i /\ slot owner is i -> Idle
 * Active /\ core i has a request -> Active; schedule the next slot for core i
 *
 * End /\ [va] -> Idle;
 * End /\ [!va] -> Ready; schedule the next slot for requests from the core, and the requests from the ROC
 *
 * for wc and va, schedule the next slot start corresponds to the next multiple of full_slot_width
 * for ss, schedule the next slot start corresponds to the point when the slot status is changed to Idle
 */

struct SlotManager {
    /**
     * clock_source: the clock source
     * schedule: represents the owner of each slot, wrap around if
     * reaching the end
     *
     * work_conserving: whether we skip a whole slot when the slot owner does not
     * need to process any event
     *
     * subslot_opt: whether we skip a remainder part of a slot when an operation is deemed finished
     *
     * split_bus: whether we allows a response from LLC to move forward, while taking in another request
    */

    const static int RequestVnet = 0;
    const static int ForwardVnet = 1;
    const static int ResponseVnet = 2;
    const static int ROCVnet = 3;
    // thestatic  vnet that is dedicated for split bus
    const static int SplitResponseVnet = 6;

    typedef std::pair<int, int> pii;

    SlotManager(
        ClockedObject& parent,
        Consumer& consumer,
        const std::vector<int>& schedule,
        bool work_conserving,
        bool subslot_opt,
        bool split_bus,
        bool enable_roc,
        Cycles full_slot_width,
        int ncore
    );

    SlotStatus getSlotStatus() const { return m_slot_status; }

    bool isWorkConserving() const { return m_work_conserving; }
    bool isSubslotOpt() const { return m_subslot_opt; }
    bool isVanilla() const { return !m_work_conserving && !m_subslot_opt; }
    bool isSplitBus() const { return m_split_bus; }

    [[deprecated]]
    int getCoreDeviceId(int core) const { return coreToDeviceId(core); }
    int coreToDeviceId(int core) const { return core + 1; }

    [[deprecated]]
    int getDeviceIdCore(int device_idx) const { return deviceIdToCore(device_idx); }
    int deviceIdToCore(int device_idx) const { return device_idx - 1; }

    int getLLCDeviceId() const { return 0; }
    void updateBusStatus() {
        if(this->isVanilla()) {
            if(
                m_clock.curCycle() % m_full_slot_width == Cycles(0) &&
                m_slot_status == SlotStatus::SlotIdle) {
                m_slot_status = SlotStatus::SlotReady;
            }
        }
    }
    void scheduleNextClosestSlotBoundary() {
        this->scheduleNextSlotBoundary(-1);
    }
    void scheduleNextSlotBoundary(int core);
    /**
     * m_in: message buffer of incoming events
     * roc_queue: the roc queue
    */
    std::list<TDMAction> getNextEvent(
        const std::vector<std::vector<MessageBuffer*> >& m_in,
        ROCQueue& roc_queue,
        std::list<int>* response_order,
        bool llc_finish_signal
    );

    int getSlotOwner() const { return this->m_slot_owner; }
    int getCoreIDFromRequest(const Message*) const;



    std::vector<int> m_schedule;
    bool m_llc_finish_signal;
    // delay the end of the slot until the data response is issued
    // from the LLC
    bool m_llc_finish_wait_for_data_response;
    private:

    bool probeLLCResponse(int core, int slot_idx,
        const std::vector<std::vector<MessageBuffer*> >& m_in,
        std::list<TDMAction>& actions);
    bool probeCoreRequest(int core, int slot_idx,
        ROCQueue& roc_queue,
        std::list<int>* response_order,
        const std::vector<std::vector<MessageBuffer*> >& m_in,
        std::list<TDMAction>& actions);
    bool probeROCRequest(int core, int slot_idx, const ROCQueue& roc_queue, std::list<TDMAction>& actions);

    // get the precendence of slots, which is dependent
    // on current slot idx, this most likely won't be featured
    // in hardware and is just for simulation
    std::vector< pii >  getCorePrecedence() const;
    Cycles vanillaNextSlotBoundary(Cycles c, int core) const;
    int getCoreIDFromResponse(const Message*) const;
    void setSlotOwner(int core) { this->m_slot_owner = core; }
    void activateSlot(int slot_idx, int initiating_vnet) {
        this->m_slot_status = SlotStatus::SlotActive;
        this->setSlotOwner(m_schedule[slot_idx]);
        this->m_current_slot_idx = slot_idx;
        this->m_slot_initiatining_source = initiating_vnet;
        panic_if(this->m_llc_finish_signal, "Slot start should have llc_finish_signal deactivated");
        DPRINTF(ZCLLC_TDM, "++++++++++ SLOT STARTED (L1Cache %d) ++++++++++\n", this->getSlotOwner());
    }
    void deactivateSlotIfEnd() {
        if(this->m_slot_status == SlotStatus::SlotEnd || this->m_slot_status == SlotStatus::SlotWaitDataResponse) {
            if(this->isVanilla())
                this->m_slot_status = SlotStatus::SlotIdle;
            else
                this->m_slot_status = SlotStatus::SlotReady;
            DPRINTF(ZCLLC_TDM, "---------- SLOT DONE ---------- -> %d\n", this->m_slot_status);
            panic_if(!this->m_llc_finish_signal, "Slot end should have llc_finish_signal activated");
            this->m_llc_finish_signal = false;
            this->m_llc_finish_wait_for_data_response = false;
        } else {
            panic_if(this->m_llc_finish_signal, "Non-slot-end should have llc_finish_signal deactivated");
        }
    }
    Consumer& m_consumer;
    ClockedObject& m_clock;
    bool m_work_conserving;
    bool m_subslot_opt;
    bool m_split_bus;
    bool m_enable_roc;
    Cycles m_full_slot_width;
    int m_current_slot_idx;
    int m_slot_owner;
    int m_slot_initiatining_source;
    int m_ncore;


    // simulation status
    SlotStatus m_slot_status;
};

};
};


#endif // __XYZ_SLOT_MANAGER_HH__

