#include "PulseCase.h"
#include <functional>
#include <future>
#include <condition_variable>
#include <mutex>
#include <thread>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <vector>
using namespace claw::test::pulse;
namespace {
int checks{};
void require(bool ok,const char* message) { ++checks; if (!ok) throw std::runtime_error(message); }
struct Fake final:Port {
    Tick now{1000};
    Frame f{};
    std::vector<std::string> trace;
    std::function<void()> afterTranslation;
    std::function<void(int)> afterObservation;
    std::atomic<bool> queueFatal{false},workerFatal{false};
    FatalGate fatal{queueFatal,workerFatal};
    int translations{},updates{},observations{};
    bool throwTranslation{},throwUpdate{},anchorOnly{},failReturn{},staleClock{},cancelFlag{},staleMove{};
    Fake() {
        f.generation=1; f.actor=20; f.root=10; f.handle=1; f.form=0xFF000001; f.base=0x01000800;
        f.race=0xCDD84; f.sex=1; f.attached=true; f.anchorParent=999;
        f.model.address=10;
        for (std::size_t i=0;i<controlCount;++i) { f.controls[i].address=11+i; f.controls[i].parent=10; }
        f.parentWorld.r={0,-1,0,1,0,0,0,0,1}; f.parentWorld.s=2; f.parentWorld.t={10,20,30};
        f.controls[2].address=999; f.controls[2].world=f.parentWorld;
        f.subtreeCount=2; f.subtree[0].address=100; f.subtree[0].parent=999;
        f.subtree[0].local.r={0,-1,0,1,0,0,0,0,1}; f.subtree[0].local.s=3; f.subtree[0].local.t={1,2,3};
        f.subtree[1].address=101; f.subtree[1].parent=100; f.subtree[1].local.t={0,1,0};
        recompute(true);
    }
    Tick clock() override { return now; }
    bool cancelled() const override { return cancelFlag; }
    Frame observe() override {
        trace.push_back("read"); ++observations;
        if (!staleClock) { f.begin=++now; f.end=++now; }
        Frame out=f; out.fatalObserved=fatal.failed(); out.attached&=!out.fatalObserved;
        if (afterObservation) afterObservation(observations);
        return out;
    }
    void translation(Vec v) override {
        fatal.requireCallEntry();
        trace.push_back("translation"); ++translations; ++now; f.subtree[0].local.t=v;
        if (afterTranslation) afterTranslation();
        if (throwTranslation) throw 1;
    }
    void recompute(bool all) {
        f.subtree[0].world=compose(f.parentWorld,f.subtree[0].local);
        if (all) f.subtree[1].world=compose(f.subtree[0].world,f.subtree[1].local);
    }
    void updateWorldData() override {
        fatal.requireCallEntry();
        trace.push_back("updateWorldData"); ++updates; ++now;
        if (!((staleMove&&updates==1)||(failReturn&&updates==2))) recompute(!anchorOnly);
        if (throwUpdate) throw 1;
    }
};
std::unique_ptr<Case> prepared(Fake& p,bool durable=true) {
    auto c=std::make_unique<Case>();
    const auto first=p.observe();
    c->prepare({first.form,first.base,first.race,first.sex,1000},first);
    require(c->view().state==State::awaitingIntent,"valid prepare");
    c->confirmIntent(durable,p.clock()); p.trace.clear(); return c;
}
void drain(Case& c,Fake& p) {
    for (int i=0;i<40&&c.active();++i) { p.now=std::max(p.now,c.view().nextDue); c.step(p); }
}
void normal() {
    Fake p; auto c=prepared(p); const auto original=c->view().baseline.subtree[0].local;
    c->start(p);
    require(c->view().state==State::holding,"move witnessed");
    require(close(p.f.subtree[0].local.t,Vec{1,2.3F,3},1e-6F),"rotated scaled local offset");
    require(close(p.f.subtree[0].world.t,add(c->view().baseline.subtree[0].world.t,Vec{-.6F,0,0}),1e-5F),"actual world offset");
    require(p.trace==std::vector<std::string>{"read","translation","read","updateWorldData","read"},"separate fresh guard before both consumer calls");
    const auto trace=p.trace;
    c->start(p); // Duplicate start cannot replay.
    p.now=c->view().nextDue-1; c->step(p);
    require(p.trace==trace,"duplicate start and early callback do not write");
    drain(*c,p);
    require(c->view().state==State::completeClean&&c->view().failure==Failure::none,"clean mechanical completion");
    require(c->view().sampleCount==25&&c->view().recordCount()==36,"all 25 read-only samples and every call/guard retained");
    require(p.translations==2&&p.updates==2,"exactly move and saved restore");
    require(bits(p.f.subtree[0].local,original),"all original local bits restored");
    require(c->view().holdTicks>=120&&c->view().holdTicks<=600,"actual producer hold scored");
    const auto size=p.trace.size(); c->start(p); c->step(p,true); c->confirmIntent(true,p.now);
    require(p.trace.size()==size,"terminal status/cancel/repeated start cannot replay");
    for (std::size_t i=p.trace.size()-25;i<p.trace.size();++i) require(p.trace[i]=="read","sampling issues no writes");
}
void admission() {
    Fake p; auto c=prepared(p,false); c->start(p);
    require(c->view().state==State::rejectedNoMutation&&p.trace.empty(),"unflushed intent cannot mutate");
    Fake a; auto q=std::make_unique<Case>(); auto f=a.observe();
    q->prepare({f.form,f.base,f.race,0,1000},f);
    require(q->view().state==State::rejectedNoMutation,"female fixed fixture required");
    Fake b; auto d=prepared(b); d->step(b,true);
    require(d->view().state==State::rejectedNoMutation&&b.trace.empty(),"cancel before start makes no calls");
    Fake e; auto late=prepared(e); e.now=late->view().deadline; late->start(e);
    require(late->view().state==State::rejectedNoMutation&&e.trace.empty(),"expired prepared intent cannot start");
}
void guards() {
    const std::vector<std::function<void(Fake&)>> change={
        [](Fake& p){++p.f.generation;},[](Fake& p){++p.f.root;},[](Fake& p){++p.f.actor;},
        [](Fake& p){++p.f.handle;},[](Fake& p){++p.f.base;},[](Fake& p){++p.f.race;},
        [](Fake& p){p.f.sex=0;},[](Fake& p){p.f.attached=false;},[](Fake& p){++p.f.subtree[0].parent;},
        [](Fake& p){p.f.subtree[0].local.r[2]=-0.F;},[](Fake& p){p.f.controls[1].world.t.x+=.01F;},
        [](Fake& p){p.f.parentWorld.t.x+=.01F;}};
    for (const auto& mutate:change) {
        Fake p; auto c=prepared(p); mutate(p); c->start(p);
        require(c->view().state==State::quarantined&&c->view().failure==Failure::ownership,"guard loss quarantines");
        require(p.translations==0&&p.updates==0,"guard checked before first translation");
    }
    Fake p; auto c=prepared(p); p.afterTranslation=[&]{++p.f.generation;}; c->start(p);
    require(c->view().state==State::quarantined&&p.translations==1&&p.updates==0,"guard repeated after local write before world update");
    auto calls=p.trace.size(); c->step(p,true); require(calls==p.trace.size(),"epoch loss forbids blind restoration");
    Fake q; auto d=prepared(q); q.afterTranslation=[&]{q.f.subtree[0].local.t.x+=.01F;}; d->start(q);
    require(d->view().state==State::quarantined&&q.updates==0,"foreign local bits block update and restore");
    Fake s; auto r=prepared(s); s.staleClock=true; r->start(s);
    require(r->view().state==State::quarantined&&r->view().failure==Failure::clock&&s.translations==0,"nonadvancing own producer timestamp rejected");
}
void propagation() {
    Fake p; p.staleMove=true; auto c=prepared(p); c->start(p);
    require(c->view().state==State::failedClean&&c->view().failure==Failure::moveWitness,"stale anchor world fails witness distinctly from ownership loss");
    require(p.translations==2&&p.updates==2&&bits(p.f.subtree[0].local,c->view().baseline.subtree[0].local),"only guarded saved restore after known anchor witness failure");
    require(c->view().sampleCount==0,"failed feasibility is not physical response acceptance");
    Fake q; q.failReturn=true; auto d=prepared(q); d->start(q); q.now=d->view().nextDue; d->step(q);
    require(d->view().state==State::quarantined&&d->view().failure==Failure::restoreWitness,"stale restored anchor world quarantines");
    const auto calls=q.trace.size(); d->step(q,true); require(q.trace.size()==calls,"failed restore never retries");
}
void timingAndCancel() {
    Fake p; auto c=prepared(p); c->start(p); p.now=c->view().movedAt+601; c->step(p); drain(*c,p);
    require(c->view().state==State::failedClean&&c->view().failure==Failure::holdBounds&&c->view().holdTicks>600,"late callback remains failed hold, no rebase");
    require(c->view().sampleCount==25,"late hold still retains 25 read-only samples");
    Fake q; auto d=prepared(q); d->start(q); d->step(q,true);
    require(d->view().state==State::failedClean&&d->view().failure==Failure::cancelled&&q.translations==2,"known cancellation performs only declared restore");
    Fake t; auto f=prepared(t); f->start(t); t.now=f->view().deadline; f->step(t);
    require(f->view().state==State::failedClean&&f->view().failure==Failure::deadline&&t.translations==2,"deadline permits guarded restore only");
    Fake u; auto g=prepared(u); g->start(u); ++u.f.root; g->step(u,true);
    require(g->view().state==State::quarantined&&u.translations==1,"cancel cannot restore replacement root");
    Fake v; auto h=prepared(v); h->start(v); v.now=h->view().nextDue; h->step(v); v.now=h->view().zeroAt+201; h->step(v); drain(*h,v);
    require(h->view().state==State::failedClean&&h->view().failure==Failure::cadence,"late read cadence stays failed");
}
void exceptions() {
    for (bool inUpdate:{false,true}) {
        Fake p; auto c=prepared(p); p.throwTranslation=!inUpdate; p.throwUpdate=inUpdate; c->start(p);
        require(c->view().state==State::quarantined&&c->view().failure==Failure::exception,"exception quarantines");
        require(c->view().unknown==(inUpdate?UnknownCall::updateWorldData:UnknownCall::translation),"unreturned call identity retained");
        const auto size=p.trace.size(); c->step(p,true); require(p.trace.size()==size,"unknown call never replays or restores");
    }
}
void additionalBoundaries() {
    static_assert(std::is_same_v<decltype(std::declval<const Case&>().view()),const Report&>);
    Fake p; auto c=std::make_unique<Case>(); const auto initial=p.observe();
    c->prepare({initial.form,initial.base,initial.race,initial.sex,1000},initial);
    c->cancelBeforeStart(); c->confirmIntent(true,p.clock()); p.trace.clear(); c->start(p);
    require(c->view().state==State::rejectedNoMutation&&c->view().failure==Failure::cancelled&&p.trace.empty(),"cancel awaiting intent is permanent and prevents later start");
    Fake q; auto d=prepared(q); q.cancelFlag=true; d->start(q);
    require(d->view().state==State::rejectedNoMutation&&q.trace.empty(),"cancel ready prevents any later first write");
    Fake r; auto e=prepared(r); r.afterTranslation=[&]{r.cancelFlag=true;}; e->start(r);
    require(e->view().state==State::failedClean&&e->view().failure==Failure::cancelled&&r.translations==2&&r.updates==1,"cancel between move translation and update permits restore/update only");
    Fake t; auto f=prepared(t); f->start(t); t.afterTranslation=[&]{if(t.translations==2)t.f.attached=false;}; t.now=f->view().nextDue; f->step(t);
    require(f->view().state==State::quarantined&&t.translations==2&&t.updates==1,"restore update requires its own fresh attachment guard");
    for (bool actor:{false,true}) {
        Fake u; if(actor)u.f.actorScale=1.01F; else u.f.model.world.s=1.01F;
        auto g=std::make_unique<Case>(); const auto first=u.observe();
        g->prepare({first.form,first.base,first.race,first.sex,1000},first);
        require(g->view().state==State::rejectedNoMutation,"nonunit actor or model-root scale rejected at admission");
    }
    Fake sheared; sheared.f.model.world.r[0]=2.F; auto invalid=std::make_unique<Case>(); const auto bad=sheared.observe();
    invalid->prepare({bad.form,bad.base,bad.race,bad.sex,1000},bad);
    require(invalid->view().state==State::rejectedNoMutation,"nonuniform/sheared root matrix rejected");
    auto buffer=std::make_unique<RecordBuffer>();
    for (std::size_t i=0;i<maxRecords;++i) buffer->append(Kind::sample);
    bool full=false; try { buffer->append(Kind::guardMove); } catch (...) { full=true; }
    require(full&&buffer->size()==maxRecords&&(*buffer)[maxRecords-1].kind==Kind::sample,"actual bounded record buffer refuses overflow without overwriting retained evidence");
    static_assert(std::is_trivially_copyable_v<Frame> && std::is_trivially_copyable_v<Record> && std::is_trivially_copyable_v<Report>);
    std::unique_ptr<Case> archived;
    { Fake retiring; archived=prepared(retiring); archived->start(retiring); drain(*archived,retiring); }
    require(archived->view().state==State::completeClean&&archived->view().recordCount()==36,"completed controller retains only independent POD receipts after port lifetime ends");
    Fake forbidden; forbidden.throwTranslation=true; archived->start(forbidden); archived->step(forbidden,true);
    require(forbidden.trace.empty(),"late commands after retirement never dereference a port or replay work");
}

void completionBeforeWait() {
    for (bool callbackWait:{false,true}) {
        std::atomic<bool> terminal{false},pending{callbackWait},unknown{false},cancel{false},start{false};
        std::atomic<std::uint64_t> epoch{1};
        const WorkerWake signals{terminal,pending,unknown,cancel,start,epoch,1};
        std::condition_variable cv; std::mutex mutex;
        std::promise<void> topChecked,enterWait;
        auto checked=topChecked.get_future(),proceed=enterWait.get_future();
        std::promise<bool> outcome; auto result=outcome.get_future();
        std::thread worker([&] {
            const bool initial=signals.completed(); // Same first top-loop check as the adapter.
            topChecked.set_value(); proceed.wait();
            std::unique_lock lock(mutex);
            const bool woke=waitWorker(cv,lock,std::chrono::milliseconds(200),[&] {
                return callbackWait?signals.callback():signals.scheduled(false,false);
            });
            outcome.set_value(!initial&&woke&&signals.completed());
        });
        checked.get();
        terminal.store(true,std::memory_order_release);
        cv.notify_one(); // Deliberately notify BEFORE the worker enters its wait: no later notification.
        enterWait.set_value();
        const bool persisted=result.get(); worker.join();
        require(persisted,"actual worker gate observes terminal published between top check and wait without another notification");
    }
}
void generationAndRigidMath() {
    Fake p; p.f.generation=0; const auto first=p.observe(); auto c=std::make_unique<Case>();
    c->prepare({first.form,first.base,first.race,first.sex,1000},first);
    require(c->view().state==State::rejectedNoMutation,"zero generation cannot establish a baseline owner");
    const std::vector<std::function<void(Fake&)>> distort={
        [](Fake& f){f.f.parentWorld.r[0]=2.F; f.f.controls[2].world=f.f.parentWorld;},
        [](Fake& f){f.f.subtree[0].local.r={-1,0,0,0,1,0,0,0,1};},
        [](Fake& f){f.f.subtree[1].local.r[1]=.2F;}};
    for (const auto& change:distort) {
        Fake f; change(f); f.recompute(true); const auto initial=f.observe(); auto d=std::make_unique<Case>();
        d->prepare({initial.form,initial.base,initial.race,initial.sex,1000},initial);
        require(d->view().state==State::rejectedNoMutation,"nonrigid parent/anchor/subtree math rejected even with composition-consistent world values");
        d->confirmIntent(true,f.now); f.trace.clear(); d->start(f);
        require(f.trace.empty(),"invalid rotation admission never reaches a consumer call");
    }
    Fake zero; auto q=prepared(zero); zero.f.generation=0; q->start(zero);
    require(q->view().state==State::quarantined&&zero.translations==0,"zero current generation quarantines before a write");
}

void completionAfterPredicate() {
    std::atomic<bool> terminal{false},pending{false},unknown{false},cancel{false},start{false};
    std::atomic<std::uint64_t> epoch{1};
    const WorkerWake signals{terminal,pending,unknown,cancel,start,epoch,1};
    std::condition_variable cv; std::mutex mutex;
    std::promise<void> evaluated,returnPredicate;
    auto eval=evaluated.get_future(),proceed=returnPredicate.get_future();
    std::promise<bool> outcome; auto result=outcome.get_future();
    std::thread worker([&] {
        bool first=true;
        std::unique_lock lock(mutex);
        const bool woke=waitWorker(cv,lock,std::chrono::seconds(2),[&] {
            const bool ready=signals.scheduled(false,false);
            if (first) { first=false; evaluated.set_value(); proceed.wait(); }
            return ready; // Intentionally stale false, after completion/notify but before CV wait.
        });
        outcome.set_value(woke&&signals.completed());
    });
    eval.get(); terminal.store(true,std::memory_order_release); cv.notify_one(); returnPredicate.set_value();
    const bool bounded=result.wait_for(std::chrono::seconds(1))==std::future_status::ready;
    if (!bounded) cv.notify_all(); // Stop a broken/unbounded implementation without hanging the suite.
    const bool completed=result.get(); worker.join();
    require(bounded&&completed,"actual bounded worker wait recovers completion notify lost after predicate evaluation");
}
void fatalAtBoundary() {
    Fake first; auto a=prepared(first); first.workerFatal.store(true); a->start(first);
    require(a->view().state==State::quarantined&&first.translations==0&&first.updates==0&&!first.cancelled(),"fatal observation is quarantine, never cancellation/recovery");
    Fake move; auto b=prepared(move);
    move.afterObservation=[&](int n){if(n==2)move.queueFatal.store(true);}; // Capture valid move guard, then fatal before setter entry.
    b->start(move);
    require(b->view().state==State::quarantined&&b->view().unknown==UnknownCall::translation&&move.translations==0,"fatal at immediate translation entry prevents raw assignment");
    Fake update; auto c=prepared(update);
    update.afterObservation=[&](int n){if(n==3)update.workerFatal.store(true);}; // Prepared read1, move guard2, update guard3.
    c->start(update);
    require(c->view().state==State::quarantined&&c->view().unknown==UnknownCall::updateWorldData&&update.translations==1&&update.updates==0,"fatal at immediate update entry prevents engine dispatch");
    const auto calls=update.trace.size(); c->step(update,true);
    require(update.trace.size()==calls,"fatal unknown outcome never restores or replays");
    Fake afterWrite; auto d=prepared(afterWrite); afterWrite.afterTranslation=[&]{afterWrite.queueFatal.store(true);}; d->start(afterWrite);
    require(d->view().state==State::quarantined&&afterWrite.translations==1&&afterWrite.updates==0,"fatal after returned assignment invalidates next observation guard");
    Fake final; auto e=prepared(final); e->start(final); drain(*e,final); final.workerFatal.store(true);
    if (final.fatal.failed()) e->quarantine(Failure::exception);
    require(e->view().state==State::quarantined&&e->view().recordCount()==36,"fatal before final publication invalidates completed report without further writes");
}

void descendantWorldsAreRecordsOnly() {
    Fake p; p.anchorOnly=true; p.f.subtree[1].world.t.x+=7.F;
    const auto divergent=p.f.subtree[1].world;
    auto c=prepared(p); c->start(p);
    require(c->view().state==State::holding,"anchor witness tolerates a rigid finite divergent descendant world");
    bool retained=false;
    for (std::size_t i=0;i<c->view().recordCount();++i) {
        const auto& row=c->view().records[i];
        if (row.kind==Kind::moved) retained=bits(row.frame.subtree[1].world,divergent);
    }
    require(retained,"actual divergent descendant world retained verbatim in moved receipt");
    // Current descendant locals may change BETWEEN direct calls; only per-call continuity is owned.
    p.f.subtree[1].local.t.z+=.2F;
    drain(*c,p);
    require(c->view().state==State::completeClean&&c->view().sampleCount==25,"divergent child worlds and between-call local changes are not anchor-world scores");
    Fake q; auto d=prepared(q); q.afterTranslation=[&]{q.f.subtree[1].local.t.x+=.01F;}; d->start(q);
    require(d->view().state==State::quarantined&&q.updates==0,"descendant locals must remain exact across each translation call");
}

}
int main() {
    try { normal(); admission(); guards(); propagation(); timingAndCancel(); exceptions(); additionalBoundaries(); completionBeforeWait(); generationAndRigidMath(); completionAfterPredicate(); fatalAtBoundary(); descendantWorldsAreRecordsOnly(); }
    catch (const std::exception& e) { std::cerr<<"FAILED after "<<checks<<" checks: "<<e.what()<<'\n'; return 1; }
    std::cout<<checks<<" finite-controller checks passed; no engine or plugin loaded\n";
}
