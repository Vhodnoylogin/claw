// TEST ONLY. Read-only Bullet event snapshots; no actor/rig/configuration/clock writes.
#include <RE/Skyrim.h>
#include <SKSE/SKSE.h>
#include <Windows.h>
#include <nlohmann/json.hpp>
#include <PluginAPI.h>
#include <BulletDynamics/Dynamics/btRigidBody.h>
#include <BulletDynamics/ConstraintSolver/btGeneric6DofSpring2Constraint.h>
#include "Witness.h"
#include "ObjectWindow.h"
#include <algorithm>
#include <limits>
#include <memory>
#include <mutex>
#include <string>

namespace {
using Json=nlohmann::json;
using claw::witness::EventCounter;
using claw::witness::ObjectFrame;
using claw::witness::ObjectWindow;
using claw::witness::WindowSnapshot;
#if !defined(BT_USE_SSE_IN_API) || defined(BT_USE_DOUBLE_PRECISION)
#error Exact provider PDB requires float32 BT_USE_SSE_IN_API
#endif
static_assert(BT_BULLET_VERSION==325);
static_assert(sizeof(btScalar)==4&&sizeof(btVector3)==16&&alignof(btVector3)==16);
static_assert(sizeof(btTransform)==64&&sizeof(btCollisionObject)==384&&sizeof(btRigidBody)==784);
static_assert(sizeof(btAlignedObjectArray<btCollisionObject*>)==32);
static_assert(sizeof(btTypedConstraint)==80&&sizeof(btGeneric6DofSpring2Constraint)==1664);
static_assert(sizeof(btTranslationalLimitMotor2)==352&&sizeof(btRotationalLimitMotor2)==96);
static_assert(D6_SPRING_2_CONSTRAINT_TYPE==12);
std::uint64_t qpc() noexcept { LARGE_INTEGER v{};return QueryPerformanceCounter(&v)?v.QuadPart:0; }
ObjectWindow objectWindow; // Fixed process-lifetime storage; no external pointer identities.
claw::witness::ObjectFrameBuffer frameBuffer;
std::atomic<std::uint64_t> eventEpoch{1};
void objectFrame(ObjectFrame& out,const btAlignedObjectArray<btCollisionObject*>& objects,float dt) noexcept {
    out.qpc=qpc();out.thread=GetCurrentThreadId();out.epoch=eventEpoch.load();out.dt=dt;
    const int count=objects.size();
    if(count<0||count>static_cast<int>(claw::witness::objectCapacity)){out.count=claw::witness::objectCapacity+1;return;}
    out.count=static_cast<std::uint32_t>(count);
    for(int i=0;i<count;++i) {
        const btCollisionObject* object=objects[i];auto& row=out.objects[i];
        if(!object)continue;
        row.key=reinterpret_cast<std::uintptr_t>(object); // Only callback-local matching; never dereferenced later.
        const auto& transform=object->getWorldTransform();const auto& basis=transform.getBasis();
        for(int r=0;r<3;++r)for(int c=0;c<3;++c)row.world[r*3+c]=basis[r][c];
        for(int j=0;j<3;++j)row.world[9+j]=transform.getOrigin()[j];
        row.flags=object->getCollisionFlags();
        if(const auto* body=btRigidBody::upcast(object)){
            row.rigidBody=true;row.inverseMass=body->getInvMass();
            const auto& linear=body->getLinearVelocity();const auto& angular=body->getAngularVelocity();
            const auto& inertia=body->getInvInertiaDiagLocal();
            for(int j=0;j<3;++j){row.linearVelocity[j]=linear[j];row.angularVelocity[j]=angular[j];row.inverseLocalInertia[j]=inertia[j];}
        }
    }
    std::sort(out.objects.begin(),out.objects.begin()+out.count,[](const auto& a,const auto& b){return a.key<b.key;});
    claw::witness::incidentConstraints(out,[&](std::uint32_t i) noexcept {
        // Mutable pointer is already supplied by the provider; no const_cast.
        auto* object=objects[static_cast<int>(i)];return object?btRigidBody::upcast(object):nullptr;
    },[](btTypedConstraint* edge,claw::witness::ConstraintPose& row) noexcept {
        const btTypedConstraint* base=edge;
        row.type=base->getConstraintType();row.enabled=base->isEnabled();
        if(row.type!=D6_SPRING_2_CONSTRAINT_TYPE)return true; // Explicit unsupported payload.
        // Type tag, exact PDB-matched header and base-at-zero layout qualify this cast.
        auto* spring=static_cast<btGeneric6DofSpring2Constraint*>(edge);
        const auto* linear=spring->getTranslationalLimitMotor(); // Public nonmutating SDK reader.
        if(!linear)return false;
        for(int axis=0;axis<3;++axis) {
            row.lowerLimit[axis]=linear->m_lowerLimit[axis];row.upperLimit[axis]=linear->m_upperLimit[axis];
            row.springEnabled[axis]=linear->m_enableSpring[axis];
            row.stiffness[axis]=linear->m_springStiffness[axis];row.damping[axis]=linear->m_springDamping[axis];
            row.stopERP[axis]=linear->m_stopERP[axis];
            row.stiffnessLimited[axis]=linear->m_springStiffnessLimited[axis];row.dampingLimited[axis]=linear->m_springDampingLimited[axis];
            const auto* angular=spring->getRotationalLimitMotor(axis);
            if(!angular)return false;
            const int j=axis+3;row.lowerLimit[j]=angular->m_loLimit;row.upperLimit[j]=angular->m_hiLimit;
            row.springEnabled[j]=angular->m_enableSpring;row.stiffness[j]=angular->m_springStiffness;
            row.damping[j]=angular->m_springDamping;row.stopERP[j]=angular->m_stopERP;
            row.stiffnessLimited[j]=angular->m_springStiffnessLimited;row.dampingLimited[j]=angular->m_springDampingLimited;
        }
        for(const auto* values:{&row.lowerLimit,&row.upperLimit,&row.stiffness,&row.damping,&row.stopERP})
            for(float value:*values)if(!std::isfinite(value))return false;
        return true;
    });
}
void captureFrame(const btAlignedObjectArray<btCollisionObject*>& objects,float dt,bool pre) noexcept {
    if(!frameBuffer.capture([&](ObjectFrame& frame) noexcept {objectFrame(frame,objects,dt);},
        [pre](const ObjectFrame& frame) noexcept {if(pre)objectWindow.pre(frame);else objectWindow.post(frame);}))
        objectWindow.captureDropped();
}
struct Context;
struct Pre final:RE::BSTEventSink<hdt::PreStepEvent> {
    EventCounter events;
    RE::BSEventNotifyControl ProcessEvent(const hdt::PreStepEvent* event,RE::BSTEventSource<hdt::PreStepEvent>*) override {
        events.record(event?event->timeStep:0,qpc(),GetCurrentThreadId());
        if(event&&objectWindow.requested())captureFrame(event->objects,event->timeStep,true);
        return RE::BSEventNotifyControl::kContinue;
    }
};
struct Post final:RE::BSTEventSink<hdt::PostStepEvent> {
    EventCounter events;
    RE::BSEventNotifyControl ProcessEvent(const hdt::PostStepEvent* event,RE::BSTEventSource<hdt::PostStepEvent>*) override {
        events.record(event?event->timeStep:0,qpc(),GetCurrentThreadId());
        if(event&&objectWindow.requested())captureFrame(event->objects,event->timeStep,false);
        return RE::BSEventNotifyControl::kContinue;
    }
};
struct Context {
    Pre pre;Post post;
    std::atomic<int> providerState{}; // 0 waiting,1 startup in progress,2 ready,3 refused
    std::atomic<std::uint64_t> loadEpoch{1};
    std::mutex mutex;
    Json provider{{"status","waiting"}},sample;
    int serial{};bool pending{},ready{};
    int beginNonce{};bool beginPending{},beginReady{};std::string beginReason;
    std::uint64_t beginEpoch{},beginQpc{};
    std::uint64_t frequency{};
};
Context* context{}; // Deliberate process lifetime; no sink destruction before provider shutdown.

Json eventJson(const claw::witness::EventSample& s) {
    return {{"count",s.count},{"lastQpc",s.lastQpc},{"lastThreadId",s.lastThreadId},
            {"lastTimeStep",std::isfinite(s.lastTimeStep)?Json(s.lastTimeStep):Json(nullptr)},
            {"coherent",s.coherent},{"invalidEvents",s.invalidEvents},{"droppedEvents",s.droppedEvents}};
}
Json envelope(const char* status,int serial) {
    return {{"schema","claw-fsmp-step-witness/4"},{"status",status},{"requestSerial",serial},
            {"provider",context->provider},{"pid",GetCurrentProcessId()},{"qpcFrequency",context->frequency}};
}
Json poseJson(const claw::witness::ObjectPose& pose) {
    // key is intentionally omitted. Tokens are 1-based positions in the fixed catalog.
    return {{"world",pose.world},{"rigidBody",pose.rigidBody},{"inverseMass",pose.inverseMass},{"flags",pose.flags},
            {"linearVelocity",pose.rigidBody?Json(pose.linearVelocity):Json(nullptr)},
            {"angularVelocity",pose.rigidBody?Json(pose.angularVelocity):Json(nullptr)},
            {"inverseLocalInertia",pose.rigidBody?Json(pose.inverseLocalInertia):Json(nullptr)}};
}
Json windowJson() {
    auto window=std::make_unique<WindowSnapshot>(); // Main task only; never in a provider event.
    if(!objectWindow.copy(*window))return {{"status","copy_busy"},{"coherent",false}};
    const auto& s=*window;
    if(s.nonce&&s.epoch!=context->loadEpoch.load())return {{"status","refused"},{"reason","window load epoch changed"},{"nonce",s.nonce},{"loadEpoch",s.epoch}};
    const char* status=s.failure!=claw::witness::WindowFailure::none?"refused":!s.nonce?"idle":!s.started?"armed":s.complete?"complete":"collecting";
    Json out={{"schemaVersion",4},{"status",status},{"nonce",s.nonce},{"loadEpoch",s.epoch},{"coherent",s.coherent},
        {"objectCapacity",claw::witness::objectCapacity},{"pairedStepLimit",claw::witness::pairedStepLimit},
        {"objectCount",s.count},{"pairedSteps",s.pairedSteps},{"failureCode",static_cast<unsigned>(s.failure)},
        {"callbackDrops",s.dropped},{"firstPreQpc",s.firstPreQpc},{"lastPreQpc",s.lastPreQpc},{"lastPostQpc",s.lastPostQpc},
        {"lastPreThreadId",s.lastPreThread},{"lastPostThreadId",s.lastPostThread},{"lastTimeStep",s.lastTimeStep},
        {"minimumPairedHostTimeStep",s.pairedSteps?Json(s.minimumPairedHostTimeStep):Json(nullptr)},
        {"summedPairedHostTimeStep",s.summedPairedHostTimeStep},
        {"timeStepStatisticsScope","completed-provider-callback-pairs; not Bullet substeps or integrated simulated time"},
        {"awaitingPost",s.awaitingPost},{"objects",Json::array()}};
    for(std::uint32_t i=0;i<s.count;++i) {
        const auto& r=s.objects[i];Json object={{"token",i+1},{"initialPre",poseJson(r.initialPre)},
            {"lastPre",poseJson(r.lastPre)},{"lastPost",s.pairedSteps?poseJson(r.lastPost):Json(nullptr)},
            {"minimumPostWorld",s.pairedSteps?Json(r.minimumPost):Json(nullptr)},
            {"maximumPostWorld",s.pairedSteps?Json(r.maximumPost):Json(nullptr)},
            {"maximumPairedDifference",r.maximumPairedDifference},{"firstNonzeroStep",r.firstNonzeroStep},
            {"firstNonzeroPreQpc",r.firstNonzeroPreQpc},{"firstNonzeroPostQpc",r.firstNonzeroPostQpc}};
        object["firstNonzeroPair"]=r.firstNonzeroStep?Json{{"pre",poseJson(r.firstNonzeroPre)},{"post",poseJson(r.firstNonzeroPost)}}:Json(nullptr);
        out["objects"].push_back(std::move(object));
    }
    Json edges=Json::array();bool unsupported=false;
    for(std::uint32_t i=0;i<s.constraintCount;++i) {
        const auto& c=s.constraints[i];const bool supported=c.type==D6_SPRING_2_CONSTRAINT_TYPE;
        unsupported|=!supported;
        Json parameters=supported?Json{{"lowerLimit",c.lowerLimit},{"upperLimit",c.upperLimit},
            {"springEnabled",c.springEnabled},{"stiffness",c.stiffness},{"damping",c.damping},{"stopERP",c.stopERP},
            {"stiffnessLimited",c.stiffnessLimited},{"dampingLimited",c.dampingLimited}}:Json(nullptr);
        edges.push_back({{"token",i+1},{"bodyAToken",c.bodyA},{"bodyBToken",c.bodyB},{"type",c.type},
            {"enabled",c.enabled},{"status",supported?"spring2":"unsupported_type"},{"spring2",std::move(parameters)}});
    }
    out["incidentConstraints"]={{"status",s.failure!=claw::witness::WindowFailure::none?"refused":!s.started?"not_started":unsupported?"unsupported":"observed"},
        {"scope","initial-pre configuration; identical at every captured callback"},
        {"axisOrder","linear xyz; angular xyz"},{"perBodyReferenceLimit",claw::witness::constraintRefsPerBodyLimit},
        {"uniqueConstraintCapacity",claw::witness::constraintCapacity},{"constraintCount",s.constraintCount},
        {"failureCode",static_cast<unsigned>(s.constraintFailure)},{"constraints",std::move(edges)}};
    return out;
}
void refuse(const char* reason) {
    context->providerState.store(3,std::memory_order_release);
    std::lock_guard lock(context->mutex);context->provider={{"status","refused"},{"reason",reason}};
}
void snapshot(int serial,std::uint64_t epoch) noexcept {
    Json result;
    try {
        auto* main=RE::Main::GetSingleton();auto* timer=RE::BSTimer::GetSingleton();auto* ui=RE::UI::GetSingleton();
        if(!main||!timer||!ui||epoch!=context->loadEpoch.load())throw std::runtime_error("world singleton/load epoch unavailable or changed");
        const auto& data=main->GetRuntimeData();
        result={{"phase","skse_main_thread_task"},{"physicsPhase","not_synchronized"},
            {"loadEpoch",epoch},{"sampledQpc",qpc()},{"sampledThreadId",GetCurrentThreadId()},
            {"mainThreadIdRaw",main->threadID},{"mainFreezeTime",data.freezeTime},
            {"mainFreezeNextFrame",data.freezeNextFrame},{"mainGameActive",data.gameActive},
            {"uiPaused",ui->GameIsPaused()},{"timerPauseCount",timer->pauseCount},
            {"timerRealDelta",timer->realTimeDelta},{"timerDelta",timer->delta},
            {"engineMultiplier",RE::BSTimer::QGlobalTimeMultiplier()},
            {"worldRootPresent",RE::Main::WorldRootNode()!=nullptr},
            {"worldCameraPresent",RE::Main::WorldRootCamera()!=nullptr},
            {"pre",eventJson(context->pre.events.read())},{"post",eventJson(context->post.events.read())},
            {"objectWindow",windowJson()}};
        if(!std::isfinite(timer->realTimeDelta)||!std::isfinite(timer->delta)||
           !std::isfinite(RE::BSTimer::QGlobalTimeMultiplier())||!result["sampledQpc"].get<std::uint64_t>())
            throw std::runtime_error("invalid timer/QPC witness");
    } catch(const std::exception& e) { result={{"refused",true},{"reason",e.what()}}; }
      catch(...) { result={{"refused",true},{"reason","snapshot exception"}}; }
    std::lock_guard lock(context->mutex);
    if(context->serial==serial&&context->pending) {
        context->sample=std::move(result);context->pending=false;context->ready=true;
    }
}
std::string readState(RE::StaticFunctionTag*,std::int32_t requested) {
    if(!context)return R"({"schema":"claw-fsmp-step-witness/4","status":"refused","reason":"context unavailable"})";
    std::lock_guard lock(context->mutex);
    if(context->providerState.load(std::memory_order_acquire)!=2) {
        auto out=envelope("refused",requested);out["reason"]="provider startup/version unavailable";return out.dump();
    }
    if(requested==0) {
        if(!context->pending) {
            if(context->serial==std::numeric_limits<std::int32_t>::max())return envelope("refused",0).dump();
            ++context->serial;context->pending=true;context->ready=false;
            const auto serial=context->serial;const auto epoch=context->loadEpoch.load();
            try { SKSE::GetTaskInterface()->AddTask([serial,epoch]{snapshot(serial,epoch);}); }
            catch(...) { context->pending=false;context->ready=false;auto out=envelope("refused",serial);out["reason"]="AddTask rejected";return out.dump(); }
        }
        return envelope("pending",context->serial).dump();
    }
    if(requested<0||requested!=context->serial) { auto out=envelope("refused",requested);out["reason"]="unknown request serial";return out.dump(); }
    auto out=envelope(context->ready?"ready":"pending",requested);
    if(context->ready) {
        if(context->sample.value("refused",false))out["status"]="refused";
        out["sample"]=context->sample;
    }
    return out.dump();
}
std::string beginWindow(RE::StaticFunctionTag*,std::int32_t nonce) {
    if(!context)return R"({"schema":"claw-fsmp-step-witness/4","status":"refused","reason":"context unavailable"})";
    std::lock_guard lock(context->mutex);
    Json out={{"schema","claw-fsmp-step-witness/4"},{"nonce",nonce},{"status","refused"}};
    if(nonce<=0||context->providerState.load(std::memory_order_acquire)!=2){out["reason"]="positive nonce/ready provider required";return out.dump();}
    if(context->beginNonce&&context->beginNonce!=nonce){out["reason"]="different nonce refused; one window per process";return out.dump();}
    if(!context->beginNonce) {
        context->beginNonce=nonce;context->beginPending=true;context->beginEpoch=context->loadEpoch.load();
        const auto epoch=context->beginEpoch;
        try {SKSE::GetTaskInterface()->AddTask([nonce,epoch]{
            const bool sameEpoch=context->loadEpoch.load()==epoch;
            const bool accepted=sameEpoch&&objectWindow.request(static_cast<std::uint64_t>(nonce),epoch);
            std::lock_guard inner(context->mutex);context->beginPending=false;context->beginReady=accepted;
            context->beginQpc=qpc();if(!accepted)context->beginReason="load epoch changed or window already consumed";
        });}catch(...){context->beginPending=false;context->beginReason="AddTask rejected; nonce consumed, no replay";}
    }
    if(context->beginEpoch!=context->loadEpoch.load()){out["reason"]="load epoch changed; nonce cannot rearm";return out.dump();}
    out["status"]=context->beginPending?"pending":context->beginReady?"ready":"refused";
    out["loadEpoch"]=context->beginEpoch;out["markedQpc"]=context->beginQpc;
    if(!context->beginReason.empty())out["reason"]=context->beginReason;
    return out.dump();
}
bool papyrus(RE::BSScript::IVirtualMachine* vm) {
    if(!vm)return false;vm->RegisterFunction("ReadState","CLAWFSMPWitness",readState);
    vm->RegisterFunction("BeginWindow","CLAWFSMPWitness",beginWindow);return true;
}
void providerMessage(SKSE::MessagingInterface::Message* message) {
    if(!message||!context||!message->sender||_stricmp(message->sender,"hdtSMP64")!=0)return;
    if(!claw::witness::startupEnvelope(message->type,message->data,message->dataLen)) { refuse("malformed provider startup envelope");return; }
    int expected=0;
    if(!context->providerState.compare_exchange_strong(expected,1)) { refuse("duplicate provider startup");return; }
    try {
        auto* api=static_cast<hdt::PluginInterface*>(message->data);
        const auto version=api->getVersionInfo();
        if(!claw::witness::compatible({version.interfaceVersion.major,version.interfaceVersion.minor,version.interfaceVersion.patch},
                                     {version.bulletVersion.major,version.bulletVersion.minor,version.bulletVersion.patch})) {
            refuse("unexpected interface/Bullet version; no listeners attached");return;
        }
        api->addListener(static_cast<hdt::IPreStepListener*>(&context->pre));
        api->addListener(static_cast<hdt::IPostStepListener*>(&context->post));
        { std::lock_guard lock(context->mutex);context->provider={{"status","ready"},
            {"interfaceVersion",{2,0,0}},{"bulletVersion",{3,24,0}},
            {"startupDataLen",message->dataLen},{"bulletObjectsDereferenced",true},
            {"compiledBulletHeaderVersion",325},{"btUseSseInApi",true},{"btScalarBytes",sizeof(btScalar)},
            {"bulletVersionDeclarationIsHardcoded",true},
            {"objectLayoutPdbGuid","FA13003A-6397-4D63-833B-71BE3CFFE2C2"},
            {"objectLayoutPdbSha256","1fcd447240416f1f40a4ddb0cdad3e2a16c0028d690a2a86b7bea8ed89b5006f"}}; }
        context->providerState.store(2,std::memory_order_release);
    } catch(...) { refuse("provider startup exception; no retry"); }
}
void skseMessage(SKSE::MessagingInterface::Message* message) {
    if(!message||!context)return;
    if(message->type==SKSE::MessagingInterface::kPostLoad) {
        if(!SKSE::GetMessagingInterface()->RegisterListener("hdtSMP64",providerMessage))refuse("provider sender not registered");
    } else if(message->type==SKSE::MessagingInterface::kPreLoadGame||message->type==SKSE::MessagingInterface::kNewGame)
        eventEpoch.store(context->loadEpoch.fetch_add(1)+1);
}
bool supported(const SKSE::QueryInterface* s) {
    return s&&!s->IsEditor()&&s->RuntimeVersion()==SKSE::RUNTIME_SSE_1_7_104&&s->SKSEVersion()>=REL::Version{2,3,1,0}.pack();
}
}
extern "C" __declspec(dllexport) constinit SKSE::PluginVersionData SKSEPlugin_Version=[] {
    SKSE::PluginVersionData v;v.PluginVersion({0,0,4,0});v.PluginName("CLAWFSMPWitness");v.AuthorName("CLAW contributors");
    v.versionIndependenceEx=SKSE::PluginVersionData::kVersionIndependentEx_AddressLibraryV5;
    v.compatibleVersions[0]=SKSE::RUNTIME_SSE_1_7_104.pack();v.MinimumRequiredXSEVersion({2,3,1,0});return v;
}();
extern "C" __declspec(dllexport) bool SKSEPlugin_Query(const SKSE::QueryInterface* s,SKSE::PluginInfo* info) {
    if(!info)return false;info->infoVersion=SKSE::PluginInfo::kVersion;info->name="CLAWFSMPWitness";info->version=4;return supported(s);
}
extern "C" __declspec(dllexport) bool SKSEPlugin_Load(const SKSE::LoadInterface* s) {
    if(!supported(s))return false;
    try {
        SKSE::Init(s,{.log=false});LARGE_INTEGER f{};
        if(!QueryPerformanceFrequency(&f)||f.QuadPart<=0||!SKSE::GetTaskInterface()||!SKSE::GetMessagingInterface()||!SKSE::GetPapyrusInterface())return false;
        context=new Context;context->frequency=f.QuadPart;
        return SKSE::GetPapyrusInterface()->Register(papyrus)&&SKSE::GetMessagingInterface()->RegisterListener(skseMessage);
    } catch(...) { return false; }
}
