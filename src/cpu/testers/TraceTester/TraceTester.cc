#include "cpu/testers/TraceTester/TraceTester.hh"
#include "debug/TraceTester.hh"

#include <sstream>

#include "sim/sim_exit.hh"
#include "sim/system.hh"

namespace gem5
{


bool
TraceTester::CpuPort::recvTimingResp(PacketPtr pkt)
{
    tester->completeRequest(pkt);
    return true;
}

TraceTester::TraceTester(const Params &p)
    : ClockedObject(p),
      wakeupEvent([this]{ wakeup(); }, name()),
      port("port", this, p.id),
      id(p.id),
      traceFile(p.traceFile)
{
    traceInputStream.open(p.traceFile, std::ifstream::in);
    if (!traceInputStream.is_open()) {
        fatal("Trace file not found at %s\n", traceFile);
    }

    // kick things into action
    if (readTrace(traceElement)) {
        schedule(wakeupEvent, cyclesToTicks(traceElement.timestamp));
    } else {
        fatal("Trace of cpu %d not found at %s\n", id, traceFile);
    }
}

TraceTester::~TraceTester() {
    if (traceInputStream.is_open()) {
        traceInputStream.close();
    }
}

void
TraceTester::completeRequest(PacketPtr pkt) {
    DPRINTF(TraceTester, "Core %d: Completing %s at address 0x%x, %s\n",
            id,
            pkt->isWrite() ? "write" : "read",
            pkt->getAddr(),
            pkt->isError() ? "error" : "success");
    delete pkt;
    if (readTrace(traceElement)) {
        if (traceElement.timestamp < curCycle()) {
            schedule(wakeupEvent, nextCycle());
        } else {
            schedule(wakeupEvent, cyclesToTicks(traceElement.timestamp));
        }
    } else {
        // Reserve some time for other cores to complete the trace test
        exitSimLoop("Reached trace end", 0, cyclesToTicks(curCycle() + Cycles(8000000000)));
    }
}

bool
TraceTester::readTrace(TraceElement& element) {
  std::string line;
  bool success = false;
  while (getline(traceInputStream, line).good()) {
    uint64_t timestamp;
    int requestorID;
    std::string command;
    Addr addr;
    std::istringstream iss(line);

    if (!(iss >> timestamp >> requestorID >> command >> std::hex >> addr)) {
      panic("Failure in parsing line \"%s\" in trace file %s\n", line, traceFile);
    }

    if (requestorID == id) {
      element.timestamp = Cycles(timestamp);
      element.requestorID = requestorID;
      if (command == "R") {
        element.cmd = MemCmd::ReadReq;
      }
#if defined (BESPOKE)
      else if (command == "QLI") {
        element.cmd = MemCmd::EnqueueInitReq;
      } else if (command == "QLE") {
        element.cmd = MemCmd::EnqueueWriteReq;
      } else if (command == "QLLL") {
        element.cmd = MemCmd::EnqueueLdLinkedReq;
      } else if (command == "QLSC") {
        element.cmd = MemCmd::EnqueueStCondReq;
      } else if (command == "QLSCI") {
        element.cmd = MemCmd::EnqueueStCondInvReq;
      } else if (command == "QLA") {
        element.cmd = MemCmd::AcquireReq;
      } else if (command == "QLR") {
        element.cmd = MemCmd::ReleaseReq;
      } else if (command == "QLT") {
        element.cmd = MemCmd::TransferReq;
      }
#endif
      else if (command == "LL") {
        element.cmd = MemCmd::LoadLockedReq;
      } else {
        assert(command == "W");
        element.cmd = MemCmd::WriteReq;
      }
      element.addr = addr;
      success = true;
      break;
    }
  }
  return success;
}

void
TraceTester::wakeup() {
    Cycles current_cycle = curCycle();
    assert(traceElement.timestamp <= current_cycle);
    sendRequest(traceElement);
}

bool
TraceTester::sendRequest(TraceElement element) {
    DPRINTF(TraceTester, "Core %d: Issuing %s at address 0x%x\n",
            id,
#if defined (BESPOKE)
            (element.cmd == MemCmd::WriteReq) ? "write" :
            ((element.cmd == MemCmd::EnqueueLdLinkedReq) ? "enqueueLL" :
            ((element.cmd == MemCmd::EnqueueStCondReq) ? "enqueueStCond" :
            ((element.cmd == MemCmd::EnqueueStCondInvReq) ? "enqueueStCondInv" :
            ((element.cmd == MemCmd::EnqueueWriteReq) ? "enqueueWriteReq" :
            ((element.cmd == MemCmd::AcquireReq) ? "acquire" :
            ((element.cmd == MemCmd::ReleaseReq) ? "release" :
            ((element.cmd == MemCmd::TransferReq) ? "transfer" : "read"))))))),
#else
            (element.cmd == MemCmd::WriteReq) ? "write" : "read",
#endif
            element.addr);
    Request::Flags flags;
    RequestPtr req = std::make_shared<Request>(element.addr, 1, flags, id);
    req->setContext(id);
    uint8_t *pkt_data = new uint8_t[1];
    PacketPtr pkt = new Packet(req, element.cmd);
    pkt->dataDynamic(pkt_data);
    if (!port.sendTimingReq(pkt)) {
       panic("Failed to send request to port %d\n", id);
    }
    DPRINTF(TraceTester, "Issuing request: requestor %d, command %s, addr 0x%x\n",
            id,
            (element.cmd == MemCmd::WriteReq) ? "write" : "read",
            element.addr);
    return true;
}

Port &
TraceTester::getPort(const std::string &if_name, PortID idx)
{
    if (if_name == "port")
        return port;
    else
        return ClockedObject::getPort(if_name, idx);
}


} // namespace gem5
