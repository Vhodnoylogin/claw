#pragma once
// Test-only finite pulse and worker wake gates. No engine, file or JSON code.
#include <algorithm>
#include <array>
#include <atomic>
#include <bit>
#include <cmath>
#include <chrono>
#include <condition_variable>
#include <mutex>
#include <cstdint>
#include <limits>

namespace claw::test::pulse {
using Tick = std::int64_t;
inline constexpr std::size_t maxSubtree = 32, controlCount = 3, maxRecords = 48;
inline constexpr auto schema = "claw-test-direct-left-p1-pulse/2";
inline constexpr auto producer = "CLAWNativeLeftP1Test";
inline constexpr auto anchorName = "NPC L PreBreast P1";
inline constexpr Tick never = std::numeric_limits<Tick>::max();
// These are the ACTUAL worker predicates, also exercised without the engine SDK.
// Completion may publish between the worker's top check and entering either wait.
struct WorkerWake {
    const std::atomic<bool>& terminal;
    const std::atomic<bool>& pending;
    const std::atomic<bool>& queueUnknown;
    const std::atomic<bool>& cancelled;
    const std::atomic<bool>& startRequested;
    const std::atomic<std::uint64_t>& generation;
    std::uint64_t expectedGeneration{};
    bool completed() const { return terminal.load(std::memory_order_acquire); }
    bool callback() const { return completed()||!pending.load(std::memory_order_acquire)||queueUnknown.load(); }
    bool scheduled(bool ready,bool startConsumed) const {
        return completed()||pending.load()||queueUnknown.load()||cancelled.load()||generation.load()!=expectedGeneration||
            (ready&&startRequested.load()&&!startConsumed);
    }
};
// Producers never lock the wait mutex. A bounded backstop covers a notify lost
// between predicate evaluation and the CV's atomic unlock/wait transition.
template<class Predicate>
bool waitWorker(std::condition_variable& cv,std::unique_lock<std::mutex>& lock,
                std::chrono::duration<double> requested,Predicate ready) {
    return cv.wait_for(lock,std::min(requested,std::chrono::duration<double>(.1)),ready);
}
struct FatalGate {
    const std::atomic<bool>& queueUnknown;
    const std::atomic<bool>& workerFailed;
    bool failed() const { return queueUnknown.load(std::memory_order_acquire)||workerFailed.load(std::memory_order_acquire); }
    void requireCallEntry() const { if (failed()) throw 1; } // Fatal is never normal cancellation/recovery permission.
};
struct Vec { float x{}, y{}, z{}; };
struct Transform {
    std::array<float, 9> r{1,0,0,0,1,0,0,0,1};
    Vec t{};
    float s{1};
};
inline Vec add(Vec a, Vec b) { return {a.x+b.x,a.y+b.y,a.z+b.z}; }
inline Vec multiply(const Transform& a, Vec p) {
    return {(a.r[0]*p.x+a.r[1]*p.y+a.r[2]*p.z)*a.s,
            (a.r[3]*p.x+a.r[4]*p.y+a.r[5]*p.z)*a.s,
            (a.r[6]*p.x+a.r[7]*p.y+a.r[8]*p.z)*a.s};
}
inline Transform compose(const Transform& p, const Transform& local) {
    Transform out;
    for (std::size_t row=0; row<3; ++row) for (std::size_t col=0; col<3; ++col)
        out.r[row*3+col]=p.r[row*3]*local.r[col]+p.r[row*3+1]*local.r[col+3]+p.r[row*3+2]*local.r[col+6];
    out.t=add(p.t,multiply(p,local.t)); out.s=p.s*local.s; return out;
}
inline bool bits(float a,float b) { return std::bit_cast<std::uint32_t>(a)==std::bit_cast<std::uint32_t>(b); }
inline bool bits(Vec a,Vec b) { return bits(a.x,b.x)&&bits(a.y,b.y)&&bits(a.z,b.z); }
inline bool bits(const Transform& a,const Transform& b) {
    if (!bits(a.t,b.t)||!bits(a.s,b.s)) return false;
    for (std::size_t i=0;i<9;++i) if (!bits(a.r[i],b.r[i])) return false;
    return true;
}
inline bool close(Vec a,Vec b,float tolerance) {
    return std::abs(a.x-b.x)<=tolerance&&std::abs(a.y-b.y)<=tolerance&&std::abs(a.z-b.z)<=tolerance;
}
inline bool close(const Transform& a,const Transform& b,float position=1e-4F) {
    if (!close(a.t,b.t,position)||!std::isfinite(a.s)||!std::isfinite(b.s)||std::abs(a.s-b.s)>1e-5F) return false;
    for (std::size_t i=0;i<9;++i) if (!std::isfinite(a.r[i])||!std::isfinite(b.r[i])||std::abs(a.r[i]-b.r[i])>1e-5F) return false;
    return true;
}
inline bool rotation(const Transform& t) {
    for (std::size_t a=0;a<3;++a) for (std::size_t b=0;b<3;++b) {
        const float dot=t.r[a*3]*t.r[b*3]+t.r[a*3+1]*t.r[b*3+1]+t.r[a*3+2]*t.r[b*3+2];
        if (!std::isfinite(dot)||std::abs(dot-(a==b?1.F:0.F))>1e-5F) return false;
    }
    const float determinant=t.r[0]*(t.r[4]*t.r[8]-t.r[5]*t.r[7])-t.r[1]*(t.r[3]*t.r[8]-t.r[5]*t.r[6])+t.r[2]*(t.r[3]*t.r[7]-t.r[4]*t.r[6]);
    return std::isfinite(determinant)&&std::abs(determinant-1.F)<=1e-5F;
}
inline bool finite(const Transform& t) {
    if (!(std::isfinite(t.t.x)&&std::isfinite(t.t.y)&&std::isfinite(t.t.z)&&std::isfinite(t.s)&&t.s>0)) return false;
    for (float n:t.r) if (!std::isfinite(n)) return false;
    return true;
}
inline bool rigid(const Transform& t) { return finite(t)&&rotation(t); }
struct Node {
    std::uintptr_t address{}, parent{};
    Transform local{}, world{};
};
struct Frame {
    Tick begin{}, end{};
    std::uint64_t generation{};
    std::uintptr_t actor{}, root{}, anchorParent{};
    std::uint32_t handle{}, form{}, base{}, race{}, sex{};
    Vec position{}, angles{};
    float actorScale{1};
    bool fatalObserved{};
    bool attached{}; // Adapter verified CURRENT root, full declared topology and parent membership.
    Node model{};
    Transform parentWorld{};
    std::array<Node, controlCount> controls{};
    std::size_t subtreeCount{};
    std::array<Node, maxSubtree> subtree{}; // Anchor first, then preorder descendants.
};
struct Declaration {
    std::uint32_t form{}, base{}, race{0xCDD84}, sex{1};
    Tick frequency{};
};
enum class State { empty, awaitingIntent, ready, holding, sampling, completeClean, failedClean, rejectedNoMutation, quarantined };
enum class Failure { none, admission, intent, ownership, clock, exception, moveWitness, restoreWitness, cancelled, deadline, holdBounds, cadence };
enum class Kind { prepared, guardMove, translateMove, guardUpdateMove, updateMove, moved,
                  guardRestore, translateRestore, guardUpdateRestore, updateRestore, returned, sample, closeRead };
enum class UnknownCall { none, translation, updateWorldData };
struct Record { Kind kind{}; Tick begin{},end{}; bool callReturned{},hasFrame{}; Frame frame{}; };
class RecordBuffer {
    std::array<Record,maxRecords> rows_{};
    std::size_t count_{};
public:
    std::size_t size() const noexcept { return count_; }
    const Record& operator[](std::size_t index) const { if (index>=count_) throw 1; return rows_[index]; }
    Record& append(Kind kind) {
        if (count_==maxRecords) throw 1;
        auto& row=rows_[count_++]; row={}; row.kind=kind; return row;
    }
};
static_assert(maxRecords>=36); // prepare + 2*(guard,translation,guard,update,witness) +25 reads.
struct Port {
    virtual ~Port()=default;
    virtual Tick clock()=0;
    virtual Frame observe()=0;
    virtual bool cancelled() const { return false; }
    virtual void translation(Vec)=0; // EXACT saved/moved translation only; rotation/scale untouched.
    virtual void updateWorldData()=0; // EXACT NiAVObject::UpdateWorldData(&NiUpdateData{}).
};
struct Report {
    State state{State::empty};
    Failure failure{Failure::none};
    UnknownCall unknown{UnknownCall::none};
    Declaration declaration{};
    Frame baseline{};
    RecordBuffer records{};
    std::size_t sampleCount{};
    std::size_t recordCount() const noexcept { return records.size(); }
    Tick nextDue{never},deadline{},movedAt{},zeroAt{},holdTicks{},firstSample{},lastSample{};
    bool intentDurable{},translationMoved{};

};
class Case {
    Report report_{};
public:
    const Report& view() const noexcept { return report_; }

    bool terminal() const { return report_.state>=State::completeClean; }
    bool active() const { return report_.state==State::ready||report_.state==State::holding||report_.state==State::sampling; }
    void quarantine(Failure why) { if (report_.state!=State::quarantined) { report_.failure=why; report_.state=State::quarantined; report_.nextDue=never; } }
    Tick ticks(double seconds) const { return static_cast<Tick>(std::ceil(seconds*static_cast<double>(report_.declaration.frequency))); }
    Tick maxTicks(double seconds) const { return static_cast<Tick>(std::floor(seconds*static_cast<double>(report_.declaration.frequency))); }
    void prepare(const Declaration& d,const Frame& frame) {
        if (report_.state!=State::empty) return; // One case per process: a repeated nonce never restarts it.
        report_.declaration=d; report_.baseline=frame; expected=frame.subtree[0].local;
        if (d.frequency<=0||d.frequency>1000000000||frame.end<=0||frame.end>never-d.frequency*15||
            d.form==0||d.form==0x14||d.base==0||d.race!=0xCDD84||d.sex!=1||
            frame.form!=d.form||frame.base!=d.base||frame.race!=d.race||frame.sex!=d.sex||
            frame.model.address!=frame.root||frame.subtree[0].parent!=frame.anchorParent||
            !guard(frame)||!anchorWitness(frame,frame)) {
            report_.failure=Failure::admission; report_.state=State::rejectedNoMutation; return;
        }
        report_.deadline=frame.end+ticks(15.); report_.state=State::awaitingIntent;
        appendFrame(Kind::prepared,frame); lastObserved=frame.end;
    }
    void cancelBeforeStart() {
        if (report_.state==State::empty||report_.state==State::awaitingIntent||report_.state==State::ready) finishNoMutation(Failure::cancelled);
    }
    void confirmIntent(bool flushed,Tick now) {
        if (report_.state!=State::awaitingIntent) return;
        if (!flushed||now>=report_.deadline) {
            report_.failure=flushed?Failure::deadline:Failure::intent; report_.state=State::rejectedNoMutation; return;
        }
        report_.intentDurable=true; report_.state=State::ready; report_.nextDue=report_.deadline;
    }
    void start(Port& port) noexcept {
        if (report_.state!=State::ready||!report_.intentDurable) return;
        try {
            if (port.cancelled()||port.clock()>=report_.deadline) { finishNoMutation(port.cancelled()?Failure::cancelled:Failure::deadline); return; }
            if (!apply(port,true)) {
                if (!terminal()) recover(port,Failure::moveWitness);
                return;
            }
            report_.movedAt=lastTransition; report_.state=State::holding; report_.nextDue=report_.movedAt+ticks(.12);
        } catch (...) { quarantine(Failure::exception); }
    }
    void step(Port& port,bool cancelled=false) noexcept {
        if (!active()) return;
        try {
            const auto now=port.clock();
            cancelled=cancelled||port.cancelled();
            if (cancelled||now>=report_.deadline) {
                if (report_.state==State::ready) finishNoMutation(cancelled?Failure::cancelled:Failure::deadline);
                else recover(port,cancelled?Failure::cancelled:Failure::deadline);
                return;
            }
            if (now<report_.nextDue) return;
            if (report_.state==State::holding) {
                if (!apply(port,false)) {
                    if (report_.state!=State::quarantined) quarantine(Failure::restoreWitness);
                    return;
                }
                report_.zeroAt=lastTransition; report_.holdTicks=report_.zeroAt-report_.movedAt;
                if (report_.holdTicks<ticks(.12)||report_.holdTicks>maxTicks(.6)) fail(Failure::holdBounds);
                report_.state=State::sampling; report_.nextDue=report_.zeroAt; // Sample 0 is a separate worker-posted read callback.
            } else if (report_.state==State::sampling) sample(port);
        } catch (...) { quarantine(Failure::exception); }
    }
private:
    Transform expected{};
    Tick lastTransition{},lastObserved{};
    void fail(Failure why) { if (report_.failure==Failure::none) report_.failure=why; }
    void finishNoMutation(Failure why) { report_.failure=why; report_.state=State::rejectedNoMutation; report_.nextDue=never; }
    bool guard(const Frame& f) const {
        if (f.fatalObserved||!f.attached||!f.actor||!f.root||!f.handle||!f.anchorParent||!f.generation||
            !std::isfinite(f.actorScale)||std::abs(f.actorScale-1.F)>1e-5F||
            std::abs(f.model.local.s-1.F)>1e-5F||std::abs(f.model.world.s-1.F)>1e-5F||
            !rotation(f.model.local)||!rotation(f.model.world)||f.begin<=0||f.end<f.begin||
            f.generation!=report_.baseline.generation||f.actor!=report_.baseline.actor||f.root!=report_.baseline.root||
            f.handle!=report_.baseline.handle||f.form!=report_.baseline.form||f.base!=report_.baseline.base||f.race!=report_.baseline.race||f.sex!=report_.baseline.sex||
            f.anchorParent!=report_.baseline.anchorParent||f.subtreeCount==0||f.subtreeCount>maxSubtree||f.subtreeCount!=report_.baseline.subtreeCount||
            !close(f.position,report_.baseline.position,.025F)||!close(f.angles,report_.baseline.angles,1e-5F)||
            !rigid(f.model.local)||!rigid(f.model.world)||!rigid(f.parentWorld)||
            f.model.address!=report_.baseline.model.address||f.model.parent!=report_.baseline.model.parent||
            !close(f.model.local,report_.baseline.model.local)||!close(f.model.world,report_.baseline.model.world)||
            !close(f.parentWorld,report_.baseline.parentWorld)) return false;
        for (std::size_t i=0;i<controlCount;++i) {
            const auto& n=f.controls[i]; const auto& b=report_.baseline.controls[i];
            if (!n.address||n.address!=b.address||n.parent!=b.parent||!rigid(n.local)||!rigid(n.world)||
                !close(n.local,b.local)||!close(n.world,b.world)) return false;
        }
        for (std::size_t i=0;i<f.subtreeCount;++i) {
            const auto& n=f.subtree[i]; const auto& b=report_.baseline.subtree[i];
            if (!n.address||n.address!=b.address||n.parent!=b.parent||!rigid(n.local)||!rigid(n.world)) return false;
        }
        return bits(f.subtree[0].local,expected);
    }
    static bool sameLocals(const Frame& before,const Frame& after,std::size_t first=0) {
        if (before.subtreeCount!=after.subtreeCount||!before.subtreeCount) return false;
        for (std::size_t i=first;i<before.subtreeCount;++i)
            if (!bits(before.subtree[i].local,after.subtree[i].local)) return false;
        return true;
    }
    static bool anchorWitness(const Frame& before,const Frame& after) {
        if (!sameLocals(before,after)) return false;
        const auto wanted=compose(before.parentWorld,before.subtree[0].local);
        // Descendant worlds are retained observations, never composition/zero scores.
        return rigid(wanted)&&close(after.subtree[0].world,wanted,.003F);
    }
    Record& append(Kind kind) { return report_.records.append(kind); }

    void appendFrame(Kind kind,const Frame& f) {
        auto& r=append(kind); r.hasFrame=true; r.begin=f.begin; r.end=f.end; r.frame=f;
    }
    Frame read(Port& port,Kind kind) {
        auto f=port.observe(); appendFrame(kind,f);
        if (f.begin<=lastObserved||f.end<f.begin) { quarantine(Failure::clock); return f; }
        lastObserved=f.end; return f;
    }
    bool checked(const Frame& f) {
        if (report_.state==State::quarantined) return false;
        if (!guard(f)) { quarantine(Failure::ownership); return false; }
        return true;
    }
    bool displacement(const Frame& f,Vec wanted) const {
        const auto& base=report_.baseline.subtree[0].world; const auto& actual=f.subtree[0].world;
        const Vec d{actual.t.x-base.t.x,actual.t.y-base.t.y,actual.t.z-base.t.z};
        const Vec inAnchor{(base.r[0]*d.x+base.r[3]*d.y+base.r[6]*d.z)/base.s,
            (base.r[1]*d.x+base.r[4]*d.y+base.r[7]*d.z)/base.s,
            (base.r[2]*d.x+base.r[5]*d.y+base.r[8]*d.z)/base.s};
        Transform samePose=base; samePose.t=actual.t;
        return close(actual,samePose,.003F)&&close(inAnchor,wanted,.003F);
    }
    bool zero(const Frame& f) const { return anchorWitness(f,f)&&displacement(f,Vec{}); }
    bool apply(Port& port,bool moving) {
        auto before=read(port,moving?Kind::guardMove:Kind::guardRestore);
        if (!checked(before)) return false;
        if (moving&&(port.cancelled()||port.clock()>=report_.deadline)) { finishNoMutation(port.cancelled()?Failure::cancelled:Failure::deadline); return false; }
        Transform wanted=report_.baseline.subtree[0].local;
        if (moving) wanted.t=add(wanted.t,multiply(wanted,Vec{.1F,0,0})); // t' = t + (R*offset)*scale.
        auto& write=append(moving?Kind::translateMove:Kind::translateRestore);
        write.begin=port.clock(); report_.unknown=UnknownCall::translation;
        port.translation(wanted.t);
        write.end=port.clock(); write.callReturned=true; report_.unknown=UnknownCall::none;
        expected=wanted; report_.translationMoved=moving;
        auto ready=read(port,moving?Kind::guardUpdateMove:Kind::guardUpdateRestore);
        if (!checked(ready)) return false;
        if (!sameLocals(before,ready,1)) { quarantine(Failure::ownership); return false; }
        if (moving&&(port.cancelled()||port.clock()>=report_.deadline)) { fail(port.cancelled()?Failure::cancelled:Failure::deadline); return false; }
        auto& update=append(moving?Kind::updateMove:Kind::updateRestore);
        update.begin=port.clock(); report_.unknown=UnknownCall::updateWorldData;
        port.updateWorldData();
        update.end=port.clock(); update.callReturned=true; report_.unknown=UnknownCall::none;
        auto observed=read(port,moving?Kind::moved:Kind::returned);
        if (!checked(observed)) return false;
        lastTransition=observed.end;
        return anchorWitness(ready,observed)&&displacement(observed,moving?Vec{.1F,0,0}:Vec{});
    }
    void recover(Port& port,Failure why) {
        fail(why);
        if (report_.translationMoved) {
            if (!apply(port,false)) { if (report_.state!=State::quarantined) quarantine(Failure::restoreWitness); return; }
            report_.zeroAt=lastTransition;
        } else {
            auto f=read(port,Kind::closeRead);
            if (!checked(f)) return;
            if (!zero(f)) { quarantine(Failure::restoreWitness); return; }
        }
        report_.state=State::failedClean; report_.nextDue=never;
    }
    void sample(Port& port) {
        auto f=read(port,Kind::sample);
        if (!checked(f)) return;
        if (!zero(f)) { quarantine(Failure::restoreWitness); return; }
        if (!report_.sampleCount) {
            report_.firstSample=f.end;
            if (f.end-report_.zeroAt>maxTicks(.2)) fail(Failure::cadence);
        } else if (f.end-report_.lastSample<ticks(.04)||f.end-report_.lastSample>maxTicks(.2)) fail(Failure::cadence);
        report_.lastSample=f.end; ++report_.sampleCount;
        if (report_.sampleCount==25) {
            if (report_.lastSample-report_.firstSample<ticks(2.1)) fail(Failure::cadence);
            report_.state=report_.failure==Failure::none?State::completeClean:State::failedClean; report_.nextDue=never;
        } else report_.nextDue=std::max(report_.zeroAt+ticks(.1)*static_cast<Tick>(report_.sampleCount),report_.lastSample+ticks(.04));
    }
};
}
