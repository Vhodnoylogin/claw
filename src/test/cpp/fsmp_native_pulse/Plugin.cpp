// TEST ONLY. Consumes external MIT DevBench glue and the pinned CommonLib SDK.
#include "PulseCase.h"
#include "AdapterDiagnostics.h"
#include "claw/WorldStartPolicy.h"
#include "DevBenchAPI.h"
#include <Windows.h>
#include <objbase.h>
#include <nlohmann/json.hpp>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstring>
#include <filesystem>
#include <mutex>
#include <memory>
#include <string>
#include <set>
#include <stdexcept>
#include <thread>
#include <type_traits>
using namespace claw::test::pulse;
using Json=nlohmann::json;
namespace {
constexpr auto toolName="claw_test_direct_left_p1_v2";
constexpr const char* controlNames[]{"NPC Root [Root]","NPC Pelvis [Pelv]","NPC Spine2 [Spn2]"};
using Names=std::array<std::array<char,96>,maxSubtree>;
std::atomic<std::uint64_t> generation{1};
std::atomic<bool> worldReady{false};
Tick qpc() { LARGE_INTEGER t{}; if (!QueryPerformanceCounter(&t)) throw 1; return t.QuadPart; }
std::uintptr_t address(const void* p) { return reinterpret_cast<std::uintptr_t>(p); }
Vec copy(const RE::NiPoint3& p) { return {p.x,p.y,p.z}; }
Transform copy(const RE::NiTransform& t) {
    Transform out;
    for (std::size_t r=0;r<3;++r) for (std::size_t c=0;c<3;++c) out.r[r*3+c]=t.rotate.entry[r][c];
    out.t=copy(t.translate); out.s=t.scale; return out;
}
Node copy(const RE::NiAVObject* p) { return {address(p),address(p->parent),copy(p->local),copy(p->world)}; }

// Constructed, used and destroyed ONLY inside SKSE AddTask game callbacks.
// The process-lifetime registration context owns only this pointer, never a static RE value.
class Scene final:public Port {
    const std::atomic<bool>* cancelFlag{};
    const std::atomic<bool>* expiredFlag{};
    FatalGate fatal;
    RE::ActorHandle handle{};
    RE::Actor* actor{};
    RE::NiPointer<RE::NiAVObject> root{},parent{};
    std::array<RE::NiPointer<RE::NiAVObject>,controlCount> controls{};
    std::array<RE::NiPointer<RE::NiAVObject>,maxSubtree> nodes{};
    std::array<RE::NiPointer<RE::NiAVObject>,128> ancestors{};
    std::size_t count{},ancestorCount{};
    std::array<std::uintptr_t,maxSubtree> parents{};
    std::uintptr_t rootParent{};
    std::uint64_t epoch{};
    bool retained(RE::NiAVObject* p) const {
        if (p==root.get()) return true;
        for (std::size_t i=0;i<ancestorCount;++i) if (ancestors[i].get()==p) return true;
        return false;
    }
    void pinChain(RE::NiAVObject* p) {
        for (unsigned depth=0;p&&depth<64;++depth) {
            if (p==root.get()) return;
            if (!retained(p)) {
                if (ancestorCount==ancestors.size()) throw 1;
                ancestors[ancestorCount++]=RE::NiPointer<RE::NiAVObject>(p);
            }
            p=p->parent;
        }
        throw 1; // Not attached to this exact root, or cyclic/over-budget ancestry.
    }
    bool attached(RE::NiAVObject* p) const {
        for (unsigned depth=0;p&&depth<64;++depth) {
            if (p==root.get()) return true;
            auto* owner=p->parent;
            if (!owner||!retained(owner)) return false; // Never dereference a newly encountered parent.
            bool member=false;
            for (const auto& child:owner->GetChildren()) if (child.get()==p) { member=true; break; }
            if (!member) return false;
            p=owner;
        }
        return false;
    }
    bool topology() const {
        for (std::size_t i=0;i<count;++i) {
            if (address(nodes[i]->parent)!=parents[i]||!attached(nodes[i].get())) return false;
            if (auto* branch=nodes[i]->AsNode()) {
                std::size_t actual=0,expected=0;
                for (std::size_t k=1;k<count;++k) if (nodes[k]->parent==nodes[i].get()) ++expected;
                for (const auto& child:branch->GetChildren()) if (child) {
                    ++actual; bool known=false;
                    for (std::size_t k=1;k<count;++k) if (nodes[k].get()==child.get()&&parents[k]==address(nodes[i].get())) { known=true; break; }
                    if (!known) return false;
                }
                if (actual!=expected) return false;
            }
        }
        return true;
    }
public:
    Scene(const std::atomic<bool>* cancel,const std::atomic<bool>* expired,
          const std::atomic<bool>& queueUnknown,const std::atomic<bool>& workerFailed):
        cancelFlag(cancel),expiredFlag(expired),fatal{queueUnknown,workerFailed} {}
    bool cancelled() const override { return cancelFlag->load()||expiredFlag->load(); }
    Names names{}; // POD authored names copied during prepare; safe to archive off-thread.
    void prepare(const Declaration& d,std::uint64_t expectedEpoch) {
        epoch=expectedEpoch;
        if (!worldReady.load()||generation.load()!=epoch) throw 1;
        actor=RE::TESForm::LookupByID<RE::Actor>(d.form);
        if (!actor||actor->IsDeleted()||!actor->GetActorBase()||!actor->GetRace()||
            actor->GetActorBase()->GetFormID()!=d.base||actor->GetRace()->GetFormID()!=d.race||
            static_cast<std::uint32_t>(actor->GetActorBase()->GetSex())!=d.sex) throw 1;
        handle=actor->GetHandle(); root=RE::NiPointer<RE::NiAVObject>(actor->Get3D(false));
        if (!handle||!root) throw 1;
        rootParent=address(root->parent);
        auto* anchor=root->GetObjectByName(RE::BSFixedString(anchorName));
        if (!anchor||!anchor->parent||std::strcmp(anchor->name.c_str(),anchorName)!=0) throw 1;
        parent=RE::NiPointer<RE::NiAVObject>(anchor->parent);
        for (std::size_t i=0;i<controlCount;++i) {
            controls[i]=RE::NiPointer<RE::NiAVObject>(root->GetObjectByName(RE::BSFixedString(controlNames[i])));
            if (!controls[i]||std::strcmp(controls[i]->name.c_str(),controlNames[i])!=0) throw 1;
            pinChain(controls[i].get());
        }
        std::array<RE::NiAVObject*,maxSubtree> stack{}; std::size_t pending=1; stack[0]=anchor;
        while (pending) {
            auto* p=stack[--pending];
            if (count==maxSubtree) throw 1;
            for (std::size_t i=0;i<count;++i) if (nodes[i].get()==p) throw 1;
            const char* name=p->name.c_str();
            if (!name||std::strlen(name)>=names[count].size()) throw 1;
            std::memcpy(names[count].data(),name,std::strlen(name)+1);
            nodes[count]=RE::NiPointer<RE::NiAVObject>(p); parents[count]=address(p->parent); ++count; pinChain(p);
            if (auto* branch=p->AsNode()) for (const auto& child:branch->GetChildren()) if (child) {
                if (pending==stack.size()) throw 1;
                stack[pending++]=child.get();
            }
        }
        bool driver=false;
        for (std::size_t i=1;i<count;++i) if (std::strcmp(names[i].data(),"NPC L Breast P1")==0) driver=true;
        if (!driver||!topology()) throw 1;
    }
    Tick clock() override { return qpc(); }
    Frame observe() override {
        Frame f; f.begin=qpc(); f.generation=generation.load(); f.fatalObserved=fatal.failed();
        if (f.fatalObserved) { f.end=qpc(); return f; }
        auto resolved=handle.get();
        f.handle=handle.native_handle(); f.actor=address(resolved.get());
        if (!worldReady.load()||f.generation!=epoch||!resolved||resolved.get()!=actor||resolved->IsDeleted()) { f.end=qpc(); return f; }
        auto* base=resolved->GetActorBase(); auto* race=resolved->GetRace();
        f.form=resolved->GetFormID(); f.base=base?base->GetFormID():0; f.race=race?race->GetFormID():0;
        f.sex=base?static_cast<std::uint32_t>(base->GetSex()):~0U; f.root=address(resolved->Get3D(false));
        if (f.root!=address(root.get())||address(root->parent)!=rootParent) { f.end=qpc(); return f; }
        f.actorScale=resolved->GetScale(); f.position=copy(resolved->GetPosition()); f.angles=copy(resolved->GetAngle());
        f.model=copy(root.get()); f.anchorParent=address(parent.get()); f.parentWorld=copy(parent->world);
        f.subtreeCount=count; f.attached=topology();
        for (std::size_t i=0;i<count;++i) f.subtree[i]=copy(nodes[i].get());
        for (std::size_t i=0;i<controlCount;++i) { f.controls[i]=copy(controls[i].get()); f.attached&=attached(controls[i].get()); }
        f.fatalObserved=fatal.failed();
        f.attached&=generation.load()==epoch&&worldReady.load()&&!f.fatalObserved; f.end=qpc(); return f;
    }
    void translation(Vec v) override { fatal.requireCallEntry(); nodes[0]->local.translate={v.x,v.y,v.z}; }
    void updateWorldData() override { fatal.requireCallEntry(); RE::NiUpdateData data{}; nodes[0]->UpdateWorldData(&data); }
};
static_assert(std::is_trivially_copyable_v<Frame> && std::is_trivially_copyable_v<Record>);

Json vector(Vec v) { return Json::array({v.x,v.y,v.z}); }
Json transform(const Transform& t) { return {{"rotationRowMajor",t.r},{"translation",vector(t.t)},{"scale",t.s}}; }
Json floatBits(const Transform& t) {
    Json out=Json::array();
    for (float value:t.r) out.push_back(std::bit_cast<std::uint32_t>(value));
    for (float value:{t.t.x,t.t.y,t.t.z,t.s}) out.push_back(std::bit_cast<std::uint32_t>(value));
    return out;
}
Json node(const Node& n) { return {{"address",n.address},{"parent",n.parent},{"local",transform(n.local)},{"localFloat32Bits",floatBits(n.local)},{"world",transform(n.world)}}; }
Json frame(const Frame& f) {
    Json children=Json::array(),controls=Json::array();
    for (std::size_t i=0;i<f.subtreeCount&&i<maxSubtree;++i) children.push_back(node(f.subtree[i]));
    for (const auto& n:f.controls) controls.push_back(node(n));
    return {{"qpcBegin",f.begin},{"qpcEnd",f.end},{"generation",f.generation},{"actor",f.actor},{"handle",f.handle},
        {"form",f.form},{"base",f.base},{"race",f.race},{"sex",f.sex},{"root",f.root},{"anchorParent",f.anchorParent},
        {"fatalObserved",f.fatalObserved},{"currentAttachmentVerified",f.attached},{"actorScale",f.actorScale},{"actorPosition",vector(f.position)},{"actorAngles",vector(f.angles)},
        {"model",node(f.model)},{"parentWorld",transform(f.parentWorld)},{"controls",controls},{"subtree",children}};
}
const char* stateName(State s) {
    constexpr const char* names[]{"empty","awaitingIntent","ready","holding","sampling","completeClean","failedClean","rejectedNoMutation","quarantined"};
    return names[static_cast<unsigned>(s)];
}
struct Parameters {
    std::string operation,fixtureSha;
    std::filesystem::path directory,intentPath,resultPath;
    Declaration declaration{};
    std::uint64_t epoch{};
    Tick accepted{};
};
std::string utf8(const std::filesystem::path& path) { const auto text=path.u8string(); return {text.begin(),text.end()}; }
bool flushNew(const std::filesystem::path& path,const Json& value) {
    const auto text=value.dump(2)+"\n";
    HANDLE file=CreateFileW(path.c_str(),GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL|FILE_FLAG_WRITE_THROUGH,nullptr);
    if (file==INVALID_HANDLE_VALUE) return false;
    DWORD wrote=0;
    const bool good=text.size()<=MAXDWORD&&WriteFile(file,text.data(),static_cast<DWORD>(text.size()),&wrote,nullptr)&&
        wrote==text.size()&&FlushFileBuffers(file);
    const bool closed=CloseHandle(file)!=0;
    return good&&closed; // Never overwrite/delete an old or partially written intent/result.
}

const char* workName(Work work) {
    constexpr const char* names[]{"prepare","confirm","start","step","retire","none"};
    return names[static_cast<unsigned>(work)];
}
const char* fatalName(FatalOrigin origin) {
    constexpr const char* names[]{"none","callbackThreadMismatch","addTaskException","callbackException","workerException","resultWriteFailure","workerStartFailure"};
    return names[static_cast<unsigned>(origin)];
}
CallbackWitness diagnosticContext(Work work=Work::none) noexcept {
    LARGE_INTEGER now{}; const bool available=QueryPerformanceCounter(&now)!=0;
    return {0,generation.load(),work,0,GetCurrentThreadId(),now.QuadPart,available};
}
Json callbackWitness(const CallbackWitness& value) {
    return {{"sequence",value.sequence},{"work",workName(value.work)},{"generation",value.generation},
        {"expectedFirstCallbackOSThreadId",value.expectedThread},{"actualOSThreadId",value.actualThread},
        {"qpc",value.qpc},{"qpcAvailable",value.qpcAvailable}};
}
struct Runtime final:RE::BSTEventSink<RE::TESObjectLoadedEvent>,RE::BSTEventSink<RE::TESSwitchRaceCompleteEvent>,RE::BSTEventSink<SKSE::NiNodeUpdateEvent> {
    Parameters parameters{}; // Written once on listener, immutable after claimed-release.
    Case controller{}; // Game thread only; terminal/prepare publication exposes POD records to worker.
    std::unique_ptr<Scene> scene{}; // Game-thread construction AND reset only; Runtime itself is never destroyed.
    Names names{};
    Frame preparedBaseline{}; Tick preparedDeadline{}; // Immutable worker publication; no Case reads.
    Report terminalReport{}; // POD-only copy published after game-thread engine retirement.
    std::string instance;
    Tick frequency{};
    std::atomic<DWORD> gameThread{};
    AdapterDiagnostics diagnostics{};
    std::mutex admissionMutex,waitMutex;
    std::condition_variable wake;
    std::atomic<bool> enabled{false},claimed{false},pending{false},startRequested{false},cancelRequested{false};
    std::atomic<bool> prepared{false},terminal{false},intentFlushed{false},resultFlushed{false},workerExpired{false},queueUnknown{false},workerFailed{false};
    std::atomic<State> published{State::empty};
    std::atomic<Failure> failure{Failure::none};
    std::atomic<UnknownCall> unknown{UnknownCall::none};
    std::atomic<Tick> due{never};
    std::atomic<std::size_t> samples{},recordCount{};
    std::atomic<std::uint64_t> statusSequence{};
    void adapterFatal(FatalOrigin origin,Work work=Work::none) {
        auto context=diagnosticContext(work); context.expectedThread=gameThread.load();
        diagnostics.fatal(origin,context);
    }
    Json diagnosticStatus() const {
        Json rows=Json::array(); CallbackWitness value{};
        for (std::size_t i=0;i<AdapterDiagnostics::capacity;++i)
            if (diagnostics.callback(i,value)) rows.push_back(callbackWitness(value));
        FatalWitness fatal{}; const bool hasFatal=diagnostics.fatal(fatal);
        const auto reserved=diagnostics.reserved();
        return {{"expectedFirstCallbackOSThreadId",gameThread.load()},{"callbackEntries",rows},
            {"callbackEntriesReserved",reserved},{"callbackEntriesDropped",reserved>AdapterDiagnostics::capacity?reserved-AdapterDiagnostics::capacity:0},
            {"fatalOriginPublished",hasFatal},{"fatalOrigin",hasFatal?fatalName(fatal.origin):"none"},
            {"fatalContext",hasFatal?callbackWitness(fatal.context):Json(nullptr)}};
    }
    void publish() {
        statusSequence.fetch_add(1);
        failure.store(controller.view().failure); unknown.store(controller.view().unknown); samples.store(controller.view().sampleCount);
        recordCount.store(controller.view().recordCount()); due.store(controller.view().nextDue); published.store(controller.view().state);
        statusSequence.fetch_add(1);
    }
    void main(Work work,bool intentOK=false) noexcept {
        const auto thread=GetCurrentThreadId();
        DWORD expected=0; gameThread.compare_exchange_strong(expected,thread);
        const auto boundThread=expected?expected:thread;
        const auto context=diagnosticContext(work);
        const auto entry=diagnostics.entered(work,boundThread,thread,context.qpc,context.qpcAvailable,context.generation);
        if (boundThread!=thread) {
            diagnostics.fatal(FatalOrigin::callbackThreadMismatch,entry);
            queueUnknown.store(true); pending.store(false); wake.notify_one(); return;
        }
        try {
            if (queueUnknown.load()||workerFailed.load()) controller.quarantine(Failure::exception);
            else if (work==Work::prepare&&workerExpired.load()) controller.quarantine(Failure::deadline);
            else if (work==Work::prepare) {
                if (cancelRequested.load()) { controller.cancelBeforeStart(); }
                else {
                    scene=std::make_unique<Scene>(&cancelRequested,&workerExpired,queueUnknown,workerFailed); scene->prepare(parameters.declaration,parameters.epoch);
                    const auto initial=scene->observe(); controller.prepare(parameters.declaration,initial); names=scene->names;
                    if (controller.view().state==State::awaitingIntent) {
                        preparedBaseline=controller.view().baseline; preparedDeadline=controller.view().deadline;
                        prepared.store(true,std::memory_order_release);
                    }
                }
            } else if (generation.load()!=parameters.epoch||!worldReady.load()) controller.quarantine(Failure::ownership);
            else if (work==Work::retire) {
                if (controller.view().state==State::awaitingIntent) controller.confirmIntent(intentFlushed.load(),qpc());
                else if (scene) controller.step(*scene,true);
                else controller.quarantine(Failure::deadline);
            }
            else if (work==Work::confirm) {
                if (cancelRequested.load()) controller.cancelBeforeStart();
                else controller.confirmIntent(intentOK&&!workerExpired.load(),qpc());
            }
            else if (scene) {
                if (work==Work::start&&!cancelRequested.load()&&!workerExpired.load()) controller.start(*scene);
                else controller.step(*scene,cancelRequested.load()||workerExpired.load());
            }
        } catch (...) { diagnostics.fatal(FatalOrigin::callbackException,entry); controller.quarantine(Failure::exception); }
        // No engine-owned value reaches a worker or static exit destructor. Even quarantine retires
        // retained old roots on this game thread without writing them. If this callback never arrives,
        // the leaked process-lifetime context intentionally retains unresolved objects until process exit.
        // Fatal flags may have changed while the callback was running. They authorize no
        // cleanup writes and must invalidate even a just-completed numerical report.
        if (queueUnknown.load(std::memory_order_acquire)||workerFailed.load(std::memory_order_acquire)) controller.quarantine(Failure::exception);
        if (controller.terminal()) {
            scene.reset(); // Game-thread retirement only, no actuator recovery.
            if (queueUnknown.load(std::memory_order_acquire)||workerFailed.load(std::memory_order_acquire)) controller.quarantine(Failure::exception);
            terminalReport=controller.view(); terminal.store(true,std::memory_order_release);
        }
        publish(); pending.store(false,std::memory_order_release); wake.notify_one();
    }
    bool post(Work work,bool intentOK=false) {
        bool expected=false;
        if (!pending.compare_exchange_strong(expected,true)) return false;
        try { SKSE::GetTaskInterface()->AddTask([this,work,intentOK]{main(work,intentOK);}); }
        catch (...) { adapterFatal(FatalOrigin::addTaskException,work); queueUnknown.store(true); wake.notify_one(); } // Void AddTask has no completion token: no retry.
        return !queueUnknown.load();
    }
    Json intent() const {
        Json labels=Json::array(); for (std::size_t i=0;i<preparedBaseline.subtreeCount;++i) labels.push_back(names[i].data());
        Transform moved=preparedBaseline.subtree[0].local; moved.t=add(moved.t,multiply(moved,Vec{.1F,0,0}));
        return {{"schema",schema},{"producer",producer},{"producerInstance",instance},{"operation",parameters.operation},
            {"qpcFrequency",frequency},{"acceptedQpc",parameters.accepted},{"absoluteOperationDeadlineQpc",preparedDeadline},
            {"outerOwnerFixtureEvidenceSha256",parameters.fixtureSha},{"baseline",frame(preparedBaseline)},
            {"subtreeNames",labels},{"anchor",anchorName},{"offsetInBaselineAnchorFrame",Json::array({.1,0.,0.})},
            {"translationFormula","original.t + (original.R * offset) * original.scale"},
            {"expectedMovedLocalFloat32Bits",floatBits(moved)},{"savedLocalFloat32Bits",floatBits(preparedBaseline.subtree[0].local)},
            {"orderedMutationScope",Json::array({"guard; translation-only move; guard; UpdateWorldData(&NiUpdateData{}); actual anchor witness; exact subtree locals", "guard; exact saved translation restore; guard; same UpdateWorldData; actual anchor zero witness; exact subtree locals"})},
            {"knownRecoveryOnly",Json::array({"cancel","deadline","known-returned update with failed anchor/local witness"})},
            {"quarantineNoFurtherWrites",Json::array({"actor/root/attachment/expected-local-bits/control/epoch loss","exception or unknown call","failed restoration witness"})},
            {"holdSeconds",.12},{"maxHoldSeconds",.6},{"samples",25},{"periodSeconds",.1},{"minGapSeconds",.04},{"maxGapSeconds",.2},{"minSpanSeconds",2.1},
            {"descendantWorldsScored",false},{"requiredProviderState","absent-or-stopped"},
            {"physicsAcceptance",false},{"worldObserverCompatibility",false},{"replayAllowed",false}};
    }
    bool result() const {
        Json rows=Json::array();
        for (std::size_t i=0;i<terminalReport.recordCount();++i) {
            const auto& r=terminalReport.records[i];
            Json row{{"ownRecordId",i+1},{"kind",static_cast<int>(r.kind)},{"qpcBegin",r.begin},{"qpcEnd",r.end},{"callReturned",r.callReturned}};
            if (r.hasFrame) row["frame"]=frame(r.frame);
            rows.push_back(std::move(row));
        }
        return flushNew(parameters.resultPath,{{"schema",schema},{"producer",producer},{"producerInstance",instance},
            {"operation",parameters.operation},{"qpcFrequency",frequency},{"state",stateName(terminalReport.state)},
            {"failure",static_cast<int>(terminalReport.failure)},{"unknownCall",static_cast<int>(terminalReport.unknown)},
            {"intentFlushedBeforeMutation",intentFlushed.load()},{"intentPath",utf8(parameters.intentPath)},
            {"holdTicks",terminalReport.holdTicks},{"sampleCount",terminalReport.sampleCount},{"records",rows},
            {"queueUnknown",queueUnknown.load()},{"workerFailed",workerFailed.load()},
            {"adapterDiagnostics",diagnosticStatus()},
            {"mechanicalCompletionValid",terminalReport.state==State::completeClean&&!queueUnknown.load()&&!workerFailed.load()},
            {"engineObjectsRetiredOnGameThread",true},{"physicsAcceptance",false},{"noReplay",true}});
    }
    void archiveTerminal() {
        const bool good=result(); resultFlushed.store(good);
        if (!good) adapterFatal(FatalOrigin::resultWriteFailure);
        workerFailed.store(!good);
    }
    void run() noexcept {
        bool preparePosted=false,confirmPosted=false,startConsumed=false;
        const Tick workerDeadline=parameters.accepted+frequency*20;
        const WorkerWake signals{terminal,pending,queueUnknown,cancelRequested,startRequested,generation,parameters.epoch};
        try {
            while (qpc()<workerDeadline&&!queueUnknown.load()) {
                if (signals.completed()) { archiveTerminal(); return; }
                if (pending.load(std::memory_order_acquire)) {
                    std::unique_lock lock(waitMutex); waitWorker(wake,lock,std::chrono::milliseconds(100),[&]{return signals.callback();}); continue;
                }
                if (!preparePosted) { preparePosted=true; if (!post(Work::prepare)) return; continue; }
                const auto state=published.load();
                if (state==State::awaitingIntent&&!confirmPosted&&prepared.load(std::memory_order_acquire)) {
                    const bool good=!cancelRequested.load()&&flushNew(parameters.intentPath,intent()); intentFlushed.store(good);
                    confirmPosted=true; if (!post(Work::confirm,good)) return; continue;
                }
                if (state==State::ready&&startRequested.load()&&!startConsumed&&!cancelRequested.load()) {
                    startConsumed=true; if (!post(Work::start)) return; continue;
                }
                const auto now=qpc();
                if ((state==State::ready||state==State::holding||state==State::sampling)&&
                    (cancelRequested.load()||generation.load()!=parameters.epoch||now>=due.load())) {
                    if (!post(Work::step)) return; continue;
                }
                Tick waitUntil=workerDeadline;
                if (state==State::ready||state==State::holding||state==State::sampling) waitUntil=std::min(waitUntil,due.load());
                const double remaining=static_cast<double>(std::max<Tick>(1,waitUntil-qpc()))/static_cast<double>(frequency);
                std::unique_lock lock(waitMutex);
                waitWorker(wake,lock,std::chrono::duration<double>(remaining),[&]{
                    return signals.scheduled(state==State::ready,startConsumed);
                });
            }
            // Completion can publish after the loop condition observes its cutoff. Persist it
            // before declaring expiration; the acquire pairs with terminal POD publication.
            if (signals.completed()) { archiveTerminal(); return; }
            const auto exit=classifyWorkerExit(false,queueUnknown.load(),workerFailed.load(),qpc(),workerDeadline);
            if (exit==WorkerExit::deadline) workerExpired.store(true);
            if (signals.completed()) { archiveTerminal(); return; }
            // At most one task remains. A late callback may ONLY guarded-clean up.
            if (!pending.load()&&!terminal.load()) (void)post(Work::retire);
        } catch (...) {
            adapterFatal(FatalOrigin::workerException);
            workerFailed.store(true);
            if (!pending.load()&&!terminal.load()) (void)post(Work::retire); // Known idle: quarantine/release on game thread only.
        }
        // Unresolved queued work/IO failure leaves the immutable intent unresolved. Never inspect
        // or release Scene here. Polling cannot restart this worker or replay an operation.
    }
    Json status(const std::string& operation) const {
        if (!claimed.load(std::memory_order_acquire)||operation!=parameters.operation) return {{"ok",false},{"error","unknown operation"}};
        Json out;
        for (int attempt=0;attempt<8;++attempt) {
            const auto before=statusSequence.load(); if (before&1) continue;
            const auto state=published.load();
            out={{"ok",true},{"schema",schema},{"producer",producer},{"producerInstance",instance},{"operation",operation},
                {"state",stateName(state)},{"failure",static_cast<int>(failure.load())},{"unknownCall",static_cast<int>(unknown.load())},
                {"samples",samples.load()},{"records",recordCount.load()},{"nextDueQpc",due.load()},{"qpcFrequency",frequency},
                {"intentFlushed",intentFlushed.load()},{"resultFlushed",resultFlushed.load()},
                {"workerExpired",workerExpired.load()},{"queueUnknown",queueUnknown.load()},{"workerFailed",workerFailed.load()},
                {"adapterDiagnostics",diagnosticStatus()},
                {"completedClean",state==State::completeClean&&resultFlushed.load()&&!queueUnknown.load()&&!workerExpired.load()&&!workerFailed.load()},
                {"physicsAcceptance",false},{"intentPath",utf8(parameters.intentPath)},{"resultPath",utf8(parameters.resultPath)}};
            if (before==statusSequence.load()) return out;
        }
        return {{"ok",true},{"operation",operation},{"statusBusy",true},{"retryStatusOnly",true}};
    }
    void changed() { generation.fetch_add(1); wake.notify_one(); }
    RE::BSEventNotifyControl ProcessEvent(const RE::TESObjectLoadedEvent* e,RE::BSTEventSource<RE::TESObjectLoadedEvent>*) override {
        if (e&&claimed.load(std::memory_order_acquire)&&e->formID==parameters.declaration.form) changed();
        return RE::BSEventNotifyControl::kContinue;
    }
    RE::BSEventNotifyControl ProcessEvent(const RE::TESSwitchRaceCompleteEvent* e,RE::BSTEventSource<RE::TESSwitchRaceCompleteEvent>*) override {
        if (e&&e->subject&&claimed.load(std::memory_order_acquire)&&e->subject->GetFormID()==parameters.declaration.form) changed();
        return RE::BSEventNotifyControl::kContinue;
    }
    RE::BSEventNotifyControl ProcessEvent(const SKSE::NiNodeUpdateEvent* e,RE::BSTEventSource<SKSE::NiNodeUpdateEvent>*) override {
        if (e&&e->reference&&claimed.load(std::memory_order_acquire)&&e->reference->GetFormID()==parameters.declaration.form) changed();
        return RE::BSEventNotifyControl::kContinue;
    }
};
Runtime* runtime{}; // Intentionally never deleted: SDK has no unregister. No static engine-owned destructor.

bool identifier(const std::string& s) {
    return s.size()>=16&&s.size()<=64&&std::all_of(s.begin(),s.end(),[](unsigned char c){return (c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='-'||c=='_';});
}
bool digest(const std::string& s) {
    return s.size()==64&&std::all_of(s.begin(),s.end(),[](unsigned char c){return (c>='0'&&c<='9')||(c>='a'&&c<='f');});
}
std::uint32_t integer(const Json& args,const char* key) {
    const auto& value=args.at(key);
    if (!value.is_number_integer()) throw std::runtime_error("integer form/sex field required");
    if (value.is_number_unsigned()) {
        const auto n=value.get<std::uint64_t>();
        if (n>0xFFFFFFFFULL) throw std::runtime_error("form/sex field exceeds uint32");
        return static_cast<std::uint32_t>(n);
    }
    const auto n=value.get<std::int64_t>();
    if (n<0||n>0xFFFFFFFFLL) throw std::runtime_error("negative/overflow form/sex field");
    return static_cast<std::uint32_t>(n);
}
std::filesystem::path evidencePath(const std::string& text) {
    if (text.empty()||text.size()>1024||text.find('\0')!=std::string::npos) throw std::runtime_error("bounded UTF-8 evidence path required");
    const auto size=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,text.data(),static_cast<int>(text.size()),nullptr,0);
    if (!size) throw std::runtime_error("invalid UTF-8 evidence path");
    std::wstring wide(static_cast<std::size_t>(size),L'\0');
    if (MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,text.data(),static_cast<int>(text.size()),wide.data(),size)!=size) throw 1;
    return std::filesystem::path(wide);
}
Json dispatch(Runtime& r,const Json& args) {
    if (!r.enabled.load()) return {{"ok",false},{"error","test registration unavailable/collided"}};
    if (!args.is_object()||args.size()>8) throw std::runtime_error("bounded argument object required");
    const auto action=args.at("action").get<std::string>(),operation=args.at("operation").get<std::string>();
    if (!identifier(operation)) throw std::runtime_error("explicit 16..64 character operation nonce required");
    if (action=="prepare") {
        if (args.size()!=8) throw std::runtime_error("exact prepare fields required");
        Parameters p; p.operation=operation; p.fixtureSha=args.at("fixtureEvidenceSha256").get<std::string>();
        if (!digest(p.fixtureSha)) throw std::runtime_error("external fixture evidence SHA256 required");
        p.declaration={integer(args,"actorForm"),integer(args,"baseForm"),integer(args,"raceForm"),integer(args,"sex"),r.frequency};
        if (!p.declaration.form||p.declaration.form==0x14||!p.declaration.base||p.declaration.race!=0xCDD84||p.declaration.sex!=1) throw std::runtime_error("explicit nonplayer female WerewolfBeast actor/base required");
        p.directory=evidencePath(args.at("outputDirectory").get<std::string>());
        if (!p.directory.is_absolute()||!std::filesystem::is_directory(p.directory)||GetDriveTypeW(p.directory.root_path().c_str())!=DRIVE_FIXED) throw std::runtime_error("existing absolute local fixed-drive evidence directory required");
        p.intentPath=p.directory/("claw-native-left-p1-"+operation+".intent.json");
        p.resultPath=p.directory/("claw-native-left-p1-"+operation+".result.json");
        p.accepted=qpc(); p.epoch=generation.load();
        std::lock_guard lock(r.admissionMutex);
        if (r.claimed.load(std::memory_order_acquire)) return r.status(operation); // No reprepare/replay.
        if (!worldReady.load()) throw std::runtime_error("loaded new game required; no save/load during case");
        r.parameters=std::move(p); r.claimed.store(true,std::memory_order_release);
        try { std::thread([context=&r]{context->run();}).detach(); }
        catch (...) { r.adapterFatal(FatalOrigin::workerStartFailure); r.workerFailed.store(true); throw; }
    } else {
        if (args.size()!=2) throw std::runtime_error("exact action/operation fields required");
        if (!r.claimed.load(std::memory_order_acquire)||operation!=r.parameters.operation) return {{"ok",false},{"error","unknown operation"}};
        if (action=="start") {
            if (!r.cancelRequested.load()&&r.published.load()==State::ready&&r.intentFlushed.load()) r.startRequested.store(true);
            else if (r.published.load()==State::awaitingIntent||r.published.load()==State::empty) return {{"ok",false},{"error","not ready; poll status before first start"}};
            r.wake.notify_one();
        } else if (action=="cancel") { r.cancelRequested.store(true); r.wake.notify_one(); }
        else if (action!="status") throw std::runtime_error("action must be prepare/start/status/cancel");
    }
    return r.status(operation);
}
void handler(void* ctx,const char* args,void* sink,DevBenchAPI::WriteFn write) {
    if (!write) return; // Invalid host cannot acknowledge; do not accept any operation.
    std::string reply;
    const char* result="{\"ok\":false,\"error\":\"handler failure; status only; no replay\"}";
    try {
        const auto length=args?strnlen_s(args,8193):0;
        if (length>8192) throw std::runtime_error("arguments exceed 8192 bytes");
        const std::string owned(args?args:"",length); // No retained argument/writer/sink pointers.
        std::set<std::string> keys;
        const auto parsed=Json::parse(owned,[&](int,Json::parse_event_t event,Json& value) {
            if (event==Json::parse_event_t::key&&!keys.emplace(value.get<std::string>()).second) throw std::runtime_error("duplicate argument key");
            return true;
        });
        reply=dispatch(*static_cast<Runtime*>(ctx),parsed).dump(); result=reply.c_str();
    } catch (const std::exception& e) {
        try { reply=Json{{"ok",false},{"error",e.what()},{"retry","status only after any uncertain acknowledgement"}}.dump(); result=reply.c_str(); }
        catch (...) {} // Static fallback still writes exactly once if error formatting fails.
    } catch (...) {}
    write(sink,result); // Exactly once synchronously before return. Never retain the sink.
}
void message(SKSE::MessagingInterface::Message* e) {
    if (!e||!runtime) return;
    using M=SKSE::MessagingInterface;
    // All providers have completed kPostLoad before this single registration.
    if (e->type==M::kPostPostLoad) {
        auto* api=DevBenchAPI::GetDevBenchInterface001();
        if (api&&api->GetBuildNumber()==13600) runtime->enabled.store(api->RegisterTool(toolName,
            R"({"description":"TEST ONLY: one declared female left-P1 direct-scenegraph mechanical feasibility pulse; no physics acceptance","readOnly":false,"inputSchema":{"type":"object","required":["action","operation"],"properties":{"action":{"enum":["prepare","start","status","cancel"]},"operation":{"type":"string"},"actorForm":{"type":"integer"},"baseForm":{"type":"integer"},"raceForm":{"type":"integer"},"sex":{"const":1},"fixtureEvidenceSha256":{"type":"string"},"outputDirectory":{"type":"string"}},"additionalProperties":false}})",handler,runtime));
    } else if (e->type==M::kDataLoaded) {
        if (auto* source=RE::ScriptEventSourceHolder::GetSingleton()) {
            source->AddEventSink<RE::TESObjectLoadedEvent>(runtime); source->AddEventSink<RE::TESSwitchRaceCompleteEvent>(runtime);
        }
        if (auto* source=SKSE::GetNiNodeUpdateEventSource()) source->AddEventSink(runtime);
    } else if (e->type==M::kPreLoadGame||e->type==M::kSaveGame) {
        worldReady.store(false); runtime->changed();
    } else if (e->type==M::kNewGame||e->type==M::kPostLoadGame) {
        runtime->changed();
        worldReady.store(claw::mayActivateWorld(e->type==M::kNewGame?claw::WorldStart::newGame:claw::WorldStart::postLoadGame,
            e->dataLen,reinterpret_cast<std::uintptr_t>(e->data)));
    }
}
bool supported(const SKSE::QueryInterface* s) {
    return s&&!s->IsEditor()&&s->RuntimeVersion()==SKSE::RUNTIME_SSE_1_7_104&&s->SKSEVersion()>=REL::Version{2,3,1,0}.pack();
}
}
extern "C" __declspec(dllexport) constinit SKSE::PluginVersionData SKSEPlugin_Version=[] {
    SKSE::PluginVersionData v; v.PluginVersion({0,0,3,0}); v.PluginName("CLAWNativeLeftP1Test"); v.AuthorName("CLAW contributors");
    v.versionIndependenceEx=SKSE::PluginVersionData::kVersionIndependentEx_AddressLibraryV5|SKSE::PluginVersionData::kVersionIndependentEx_NoStructUse;
    v.compatibleVersions[0]=SKSE::RUNTIME_SSE_1_7_104.pack(); v.MinimumRequiredXSEVersion({2,3,1,0}); return v;
}();
extern "C" __declspec(dllexport) bool SKSEPlugin_Query(const SKSE::QueryInterface* s,SKSE::PluginInfo* info) {
    if (!info) return false; info->infoVersion=SKSE::PluginInfo::kVersion; info->name="CLAWNativeLeftP1Test"; info->version=3; return supported(s);
}
extern "C" __declspec(dllexport) bool SKSEPlugin_Load(const SKSE::LoadInterface* s) {
    if (!supported(s)) return false;
    try {
        SKSE::Init(s,{.log=false});
        if (!SKSE::GetTaskInterface()||!SKSE::GetMessagingInterface()) return false;
        auto* context=new Runtime; LARGE_INTEGER frequency{}; GUID id{}; wchar_t text[40]{};
        if (!QueryPerformanceFrequency(&frequency)||frequency.QuadPart<=0||frequency.QuadPart>1000000000||FAILED(CoCreateGuid(&id))||!StringFromGUID2(id,text,40)) return false;
        context->frequency=frequency.QuadPart; for (const auto ch:text) { if (!ch) break; context->instance.push_back(static_cast<char>(ch)); }
        runtime=context; return SKSE::GetMessagingInterface()->RegisterListener(message);
    } catch (...) { return false; }
}
