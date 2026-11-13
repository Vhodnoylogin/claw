#pragma once
#include <atomic>
#include <bit>
#include <cmath>
#include <cstdint>

namespace claw::witness {
struct Version { int major, minor, patch; };
inline bool compatible(Version api,Version bullet) noexcept {
    return api.major==2&&api.minor==0&&api.patch==0&&bullet.major==3&&bullet.minor==24&&bullet.patch==0;
}
inline bool startupEnvelope(std::uint32_t type,const void* data,std::uint32_t length) noexcept {
    return type==0&&data&&length==0; // Provider dispatches the INTERFACE itself, not pointer storage.
}
struct EventSample {
    std::uint64_t count{},lastQpc{},invalidEvents{},droppedEvents{};
    std::uint32_t lastThreadId{};
    float lastTimeStep{};
    bool coherent{};
};
class EventCounter {
    std::atomic_flag writer=ATOMIC_FLAG_INIT;
    std::atomic<std::uint64_t> sequence{},count{},qpc{},invalid{},dropped{};
    std::atomic<std::uint32_t> thread{},dt{};
public:
    void record(float step,std::uint64_t when,std::uint32_t tid) noexcept {
        if(writer.test_and_set(std::memory_order_acquire)) { dropped.fetch_add(1);return; }
        sequence.fetch_add(1,std::memory_order_acq_rel);
        count.fetch_add(1,std::memory_order_relaxed);
        if(!std::isfinite(step)||step<=0||!when||!tid)invalid.fetch_add(1,std::memory_order_relaxed);
        dt.store(std::bit_cast<std::uint32_t>(step),std::memory_order_relaxed);
        qpc.store(when,std::memory_order_relaxed);thread.store(tid,std::memory_order_relaxed);
        sequence.fetch_add(1,std::memory_order_release);writer.clear(std::memory_order_release);
    }
    EventSample read() const noexcept {
        EventSample out;
        for(int attempt=0;attempt<3;++attempt) {
            const auto before=sequence.load(std::memory_order_acquire);
            out={count.load(),qpc.load(),invalid.load(),dropped.load(),thread.load(),
                 std::bit_cast<float>(dt.load()),false};
            const auto after=sequence.load(std::memory_order_acquire);
            if(!(before&1)&&before==after) { out.coherent=true;break; }
        }
        return out;
    }
};
}
