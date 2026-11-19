#pragma once
#include <array>
#include <atomic>
#include <cmath>
#include <cstdint>

namespace claw::witness {
constexpr std::size_t objectCapacity=128;
constexpr std::uint32_t pairedStepLimit=900;
constexpr std::size_t constraintCapacity=256;
constexpr int constraintRefsPerBodyLimit=64;
enum class ConstraintFailure : std::uint32_t { none, referenceOverflow, uniqueOverflow, nullReference, invalidEndpoint, notIncident, referencesChanged, invalidParameter };
struct ConstraintPose {
    std::uintptr_t key{}; // Callback identity only; never serialized or dereferenced later.
    std::uint32_t bodyA{},bodyB{}; // Tokens in the SAME sorted object frame.
    int type{};
    bool enabled{};
    // Linear xyz then angular xyz. Unsupported types publish null, never zeros.
    std::array<float,6> lowerLimit{},upperLimit{},stiffness{},damping{},stopERP{};
    std::array<bool,6> springEnabled{},stiffnessLimited{},dampingLimited{};
    bool operator==(const ConstraintPose&) const = default;
};
// Callback-local identity only. Never dereferenced here or serialized externally.
struct ObjectPose {
    std::uintptr_t key{};
    std::array<float,12> world{}; // row-major 3x3 basis followed by xyz origin
    // Public const btRigidBody getters, copied in the SAME provider callback.
    // Unavailable for a non-rigid collision object; JSON publishes null then.
    std::array<float,3> linearVelocity{},angularVelocity{},inverseLocalInertia{};
    float inverseMass{};
    int flags{};
    bool rigidBody{};
};
struct ObjectFrame {
    std::array<ObjectPose,objectCapacity> objects{};
    std::uint32_t count{};
    std::uint64_t qpc{},epoch{};
    std::uint32_t thread{};
    float dt{};
    std::uint32_t constraintCount{};
    ConstraintFailure constraintFailure{};
    std::array<ConstraintPose,constraintCapacity> constraints{};
};
// One process-lifetime scratch frame. Provider callbacks never allocate or put
// the complete object/constraint arrays on their worker's stack. Reentry drops
// visibly instead of sharing a partially filled frame or waiting on a lock.
class ObjectFrameBuffer {
    std::atomic_flag gate=ATOMIC_FLAG_INIT;
    ObjectFrame frame{};
public:
    template<class Fill,class Consume>
    bool capture(Fill fill,Consume consume) noexcept {
        if(gate.test_and_set(std::memory_order_acquire))return false;
        frame.objects.fill(ObjectPose{});
        frame.constraints.fill(ConstraintPose{});
        frame.count=frame.thread=frame.constraintCount=0;
        frame.qpc=frame.epoch=0;frame.dt=0;
        frame.constraintFailure=ConstraintFailure::none;
        fill(frame);consume(frame);
        gate.clear(std::memory_order_release);return true;
    }
};
// Production and portable fixtures use this same bounded traversal. Reader copies
// only public constraint state; all Body/constraint pointers die with this call.
template<class BodyAt,class Reader>
void incidentConstraints(ObjectFrame& frame,BodyAt bodyAt,Reader read) noexcept {
    auto token=[&](std::uintptr_t key) noexcept -> std::uint32_t {
        for(std::uint32_t i=0;i<frame.count;++i)if(frame.objects[i].key==key&&frame.objects[i].rigidBody)return i+1;
        return 0;
    };
    for(std::uint32_t i=0;i<frame.count;++i) {
        auto* body=bodyAt(i);if(!body)continue;
        const auto bodyKey=reinterpret_cast<std::uintptr_t>(body);
        const auto bodyToken=token(bodyKey);
        if(!bodyToken){frame.constraintFailure=ConstraintFailure::invalidEndpoint;return;}
        const int count=body->getNumConstraintRefs();
        if(count<0||count>constraintRefsPerBodyLimit){frame.constraintFailure=ConstraintFailure::referenceOverflow;return;}
        for(int j=0;j<count;++j) {
            auto* edge=body->getConstraintRef(j);
            if(!edge){frame.constraintFailure=ConstraintFailure::nullReference;return;}
            const auto key=reinterpret_cast<std::uintptr_t>(edge);
            std::uint32_t index=0;while(index<frame.constraintCount&&frame.constraints[index].key!=key)++index;
            if(index==frame.constraintCount) {
                if(index==constraintCapacity){frame.constraintFailure=ConstraintFailure::uniqueOverflow;return;}
                auto& row=frame.constraints[index];row.key=key;
                // Endpoints must be catalogue members before a Spring2 dereference.
                row.bodyA=token(reinterpret_cast<std::uintptr_t>(&edge->getRigidBodyA()));
                row.bodyB=token(reinterpret_cast<std::uintptr_t>(&edge->getRigidBodyB()));
                if(!row.bodyA||!row.bodyB){frame.constraintFailure=ConstraintFailure::invalidEndpoint;return;}
                if(row.bodyA!=bodyToken&&row.bodyB!=bodyToken){frame.constraintFailure=ConstraintFailure::notIncident;return;}
                if(!read(edge,row)){frame.constraintFailure=ConstraintFailure::invalidParameter;return;}
                ++frame.constraintCount;
            } else if(frame.constraints[index].bodyA!=bodyToken&&frame.constraints[index].bodyB!=bodyToken) {
                frame.constraintFailure=ConstraintFailure::notIncident;return;
            }
        }
        if(body->getNumConstraintRefs()!=count){frame.constraintFailure=ConstraintFailure::referencesChanged;return;}
    }
    // Stable edge tokens for later callbacks; pointer values never leave the DLL.
    for(std::uint32_t i=1;i<frame.constraintCount;++i) {
        auto row=frame.constraints[i];auto j=i;
        while(j&&row.key<frame.constraints[j-1].key){frame.constraints[j]=frame.constraints[j-1];--j;}
        frame.constraints[j]=row;
    }
}
enum class WindowFailure : std::uint32_t {
    none, overflow, empty, invalid, epochChanged, unpaired, identityChanged,
    metadataChanged, timing, callbackDropped, constraintRefused, constraintChanged
};
struct ObjectRecord {
    ObjectPose initialPre{},lastPre{},lastPost{},firstNonzeroPre{},firstNonzeroPost{};
    std::array<float,12> minimumPost{},maximumPost{};
    std::uint32_t firstNonzeroStep{};
    std::uint64_t firstNonzeroPreQpc{},firstNonzeroPostQpc{};
    float maximumPairedDifference{};
};
struct WindowSnapshot {
    std::uint64_t nonce{},epoch{},firstPreQpc{},lastPreQpc{},lastPostQpc{},dropped{};
    std::uint32_t count{},pairedSteps{},lastPreThread{},lastPostThread{};
    float lastTimeStep{};
    float minimumPairedHostTimeStep{};
    double summedPairedHostTimeStep{}; // Completed host callback pairs, NOT Bullet substeps.
    WindowFailure failure{};
    bool started{},complete{},awaitingPost{},coherent{};
    std::array<ObjectRecord,objectCapacity> objects{};
    std::uint32_t constraintCount{};
    ConstraintFailure constraintFailure{};
    std::array<ConstraintPose,constraintCapacity> constraints{};
};
// One fixed-memory, one-window collector. Main tasks may copy under a try-gate;
// callbacks NEVER wait, allocate, call engine APIs, or retain a Bullet pointer.
class ObjectWindow {
    std::atomic_flag gate=ATOMIC_FLAG_INIT;
    std::atomic<std::uint64_t> requestedNonce{},requestedEpoch{},dropped{};
    std::atomic<bool> finished{};
    WindowSnapshot state{};
    bool enter() noexcept {
        if(!gate.test_and_set(std::memory_order_acquire))return true;
        dropped.fetch_add(1,std::memory_order_relaxed);return false;
    }
    void leave() noexcept {gate.clear(std::memory_order_release);}
    void fail(WindowFailure reason) noexcept {state.failure=reason;state.complete=true;state.awaitingPost=false;finished.store(true,std::memory_order_release);}
    static bool valid(const ObjectFrame& frame) noexcept {
        if(!frame.qpc||!frame.thread||!frame.epoch||!std::isfinite(frame.dt)||frame.dt<=0)return false;
        for(std::uint32_t i=0;i<frame.count;++i) {
            const auto& o=frame.objects[i];
            if(!o.key||!std::isfinite(o.inverseMass)||o.inverseMass<0)return false;
            if(i&&frame.objects[i-1].key>=o.key)return false;
            for(float v:o.world)if(!std::isfinite(v))return false;
            for(float v:o.linearVelocity)if(!std::isfinite(v))return false;
            for(float v:o.angularVelocity)if(!std::isfinite(v))return false;
            for(float v:o.inverseLocalInertia)if(!std::isfinite(v)||v<0)return false;
        }
        return true;
    }
    bool admit(const ObjectFrame& frame) noexcept {
        if(frame.count>objectCapacity){fail(WindowFailure::overflow);return false;}
        if(!frame.count){fail(WindowFailure::empty);return false;}
        if(!valid(frame)){fail(WindowFailure::invalid);return false;}
        if(frame.constraintFailure!=ConstraintFailure::none||frame.constraintCount>constraintCapacity){
            state.constraintFailure=frame.constraintFailure;fail(WindowFailure::constraintRefused);return false;
        }
        for(std::uint32_t i=0;i<frame.constraintCount;++i) {
            const auto& c=frame.constraints[i];
            if(!c.key||(i&&frame.constraints[i-1].key>=c.key)||!c.bodyA||!c.bodyB||c.bodyA>frame.count||c.bodyB>frame.count||
                !frame.objects[c.bodyA-1].rigidBody||!frame.objects[c.bodyB-1].rigidBody||c.type<0){
                state.constraintFailure=ConstraintFailure::invalidEndpoint;fail(WindowFailure::constraintRefused);return false;
            }
            if(c.type==12)for(const auto* values:{&c.lowerLimit,&c.upperLimit,&c.stiffness,&c.damping,&c.stopERP})
                for(float value:*values)if(!std::isfinite(value)){
                    state.constraintFailure=ConstraintFailure::invalidParameter;fail(WindowFailure::constraintRefused);return false;
                }
        }
        if(frame.epoch!=state.epoch){fail(WindowFailure::epochChanged);return false;}
        if(dropped.load(std::memory_order_relaxed)){fail(WindowFailure::callbackDropped);return false;}
        return true;
    }
    bool sameObjects(const ObjectFrame& frame) noexcept {
        if(frame.count!=state.count){fail(WindowFailure::identityChanged);return false;}
        for(std::uint32_t i=0;i<frame.count;++i) {
            const auto& a=state.objects[i].initialPre;const auto& b=frame.objects[i];
            if(a.key!=b.key){fail(WindowFailure::identityChanged);return false;}
            if(a.flags!=b.flags||a.rigidBody!=b.rigidBody||a.inverseMass!=b.inverseMass){fail(WindowFailure::metadataChanged);return false;}
        }
        if(frame.constraintCount!=state.constraintCount){fail(WindowFailure::constraintChanged);return false;}
        for(std::uint32_t i=0;i<frame.constraintCount;++i)
            if(!(frame.constraints[i]==state.constraints[i])){fail(WindowFailure::constraintChanged);return false;}
        return true;
    }
public:
    // Called once by a queued main task. Repeated nonce is idempotent; any other
    // nonce/epoch is refused for this process-lifetime collector (no reset).
    bool request(std::uint64_t nonce,std::uint64_t epoch) noexcept {
        if(!nonce||!epoch)return false;
        if(requestedNonce.load(std::memory_order_acquire))
            return requestedNonce.load()==nonce&&requestedEpoch.load()==epoch;
        requestedEpoch.store(epoch,std::memory_order_relaxed);
        requestedNonce.store(nonce,std::memory_order_release);return true;
    }
    bool requested() const noexcept {return requestedNonce.load(std::memory_order_acquire)!=0&&!finished.load(std::memory_order_acquire);}
    void captureDropped() noexcept {dropped.fetch_add(1,std::memory_order_relaxed);}
    void pre(const ObjectFrame& frame) noexcept {
        if(!requested()||!enter())return;
        if(state.complete){leave();return;}
        if(!state.nonce) {state.nonce=requestedNonce.load();state.epoch=requestedEpoch.load();}
        if(!admit(frame)){leave();return;}
        if(state.awaitingPost){fail(WindowFailure::unpaired);leave();return;}
        if(!state.started) {
            state.count=frame.count;state.started=true;state.firstPreQpc=frame.qpc;
            for(std::uint32_t i=0;i<frame.count;++i)state.objects[i].initialPre=frame.objects[i];
            state.constraintCount=frame.constraintCount;
            for(std::uint32_t i=0;i<frame.constraintCount;++i)state.constraints[i]=frame.constraints[i];
        } else if(!sameObjects(frame)){leave();return;}
        else if(frame.qpc<=state.lastPostQpc){fail(WindowFailure::timing);leave();return;}
        for(std::uint32_t i=0;i<frame.count;++i)state.objects[i].lastPre=frame.objects[i];
        state.lastPreQpc=frame.qpc;state.lastPreThread=frame.thread;state.lastTimeStep=frame.dt;
        state.awaitingPost=true;leave();
    }
    void post(const ObjectFrame& frame) noexcept {
        if(!requested()||!enter())return;
        if(state.complete){leave();return;}
        // An arm arriving between pre/post waits for the next complete pair.
        if(!state.nonce){leave();return;}
        if(!admit(frame)||!sameObjects(frame)){leave();return;}
        if(!state.awaitingPost){fail(WindowFailure::unpaired);leave();return;}
        if(frame.qpc<=state.lastPreQpc||frame.thread!=state.lastPreThread||frame.dt!=state.lastTimeStep){fail(WindowFailure::timing);leave();return;}
        for(std::uint32_t i=0;i<frame.count;++i) {
            auto& r=state.objects[i];r.lastPost=frame.objects[i];float difference=0;
            for(std::size_t j=0;j<12;++j) {
                const float value=r.lastPost.world[j];
                if(!state.pairedSteps)r.minimumPost[j]=r.maximumPost[j]=value;
                else {if(value<r.minimumPost[j])r.minimumPost[j]=value;if(value>r.maximumPost[j])r.maximumPost[j]=value;}
                const float d=std::abs(value-r.lastPre.world[j]);
                if(!std::isfinite(d)){fail(WindowFailure::invalid);leave();return;}
                if(d>difference)difference=d;
            }
            if(difference>r.maximumPairedDifference)r.maximumPairedDifference=difference;
            if(difference>0&&!r.firstNonzeroStep){
                r.firstNonzeroStep=state.pairedSteps+1;r.firstNonzeroPre=r.lastPre;r.firstNonzeroPost=r.lastPost;
                r.firstNonzeroPreQpc=state.lastPreQpc;r.firstNonzeroPostQpc=frame.qpc;
            }
        }
        if(!state.pairedSteps||frame.dt<state.minimumPairedHostTimeStep)state.minimumPairedHostTimeStep=frame.dt;
        state.summedPairedHostTimeStep+=static_cast<double>(frame.dt);
        ++state.pairedSteps;state.lastPostQpc=frame.qpc;state.lastPostThread=frame.thread;state.awaitingPost=false;
        if(state.pairedSteps==pairedStepLimit){state.complete=true;finished.store(true,std::memory_order_release);}
        leave();
    }
    bool copy(WindowSnapshot& out) noexcept {
        if(gate.test_and_set(std::memory_order_acquire))return false;
        out=state;out.nonce=requestedNonce.load();out.epoch=requestedEpoch.load();out.dropped=dropped.load();
        out.coherent=true;if(out.dropped){out.failure=WindowFailure::callbackDropped;out.complete=true;}
        gate.clear(std::memory_order_release);return true;
    }
};
}
