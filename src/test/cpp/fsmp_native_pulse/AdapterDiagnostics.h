#pragma once
// TEST-only POD publications. No engine, clock, JSON or file access.
#include "PulseCase.h"
#include <type_traits>

namespace claw::test::pulse {
enum class Work { prepare,confirm,start,step,retire,none };
enum class FatalOrigin { none,callbackThreadMismatch,addTaskException,callbackException,workerException,resultWriteFailure,workerStartFailure };
enum class WorkerExit { running,terminal,queueFatal,workerFatal,deadline };
constexpr WorkerExit classifyWorkerExit(bool terminal,bool queueFatal,bool workerFatal,Tick now,Tick deadline) {
    if (terminal) return WorkerExit::terminal;
    if (queueFatal) return WorkerExit::queueFatal;
    if (workerFatal) return WorkerExit::workerFatal;
    return now>=deadline?WorkerExit::deadline:WorkerExit::running;
}
struct CallbackWitness {
    std::uint64_t sequence{},generation{};
    Work work{Work::none};
    std::uint32_t expectedThread{},actualThread{};
    Tick qpc{};
    bool qpcAvailable{};
};
struct FatalWitness {
    FatalOrigin origin{FatalOrigin::none};
    CallbackWitness context{};
};
static_assert(std::is_trivially_copyable_v<CallbackWitness>&&std::is_trivially_copyable_v<FatalWitness>);

class AdapterDiagnostics {
    struct Slot { CallbackWitness value{}; std::atomic<bool> ready{false}; };
    // Each callback claims one distinct slot and never overwrites it. Readers
    // acquire its publication before copying POD, including a wrong-thread entry.
    std::array<Slot,64> callbacks{};
    std::atomic<std::uint64_t> sequence{};
    std::atomic<bool> fatalClaimed{false},fatalReady{false};
    FatalWitness firstFatal{};
public:
    static constexpr std::size_t capacity=64;
    CallbackWitness entered(Work work,std::uint32_t expected,std::uint32_t actual,
                            Tick qpc,bool qpcAvailable,std::uint64_t generation) {
        const auto next=sequence.fetch_add(1)+1;
        const CallbackWitness value{next,generation,work,expected,actual,qpc,qpcAvailable};
        if (next<=capacity) {
            auto& slot=callbacks[next-1]; slot.value=value;
            slot.ready.store(true,std::memory_order_release);
        }
        return value;
    }
    void fatal(FatalOrigin origin,CallbackWitness context) {
        bool expected=false;
        if (fatalClaimed.compare_exchange_strong(expected,true)) {
            firstFatal={origin,context}; fatalReady.store(true,std::memory_order_release);
        }
    }
    std::uint64_t reserved() const { return sequence.load(); }
    bool callback(std::size_t index,CallbackWitness& value) const {
        if (index>=capacity||!callbacks[index].ready.load(std::memory_order_acquire)) return false;
        value=callbacks[index].value; return true;
    }
    bool fatal(FatalWitness& value) const {
        if (!fatalReady.load(std::memory_order_acquire)) return false;
        value=firstFatal; return true;
    }
};
}
