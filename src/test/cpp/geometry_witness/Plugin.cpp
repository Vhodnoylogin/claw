// TEST ONLY: CPU pre-skin bytes/typed transforms. No GPU reads, hooks or world writes.
#include <RE/Skyrim.h>
#include <SKSE/SKSE.h>
#include <Windows.h>
#include <nlohmann/json.hpp>
#include "Geometry.h"
#include "../../../main/cpp/include/claw/WorldStartPolicy.h"
#include <SealedManifest.h>
#include <atomic>
#include <memory>
#include <mutex>
#include <string>
#include <vector>
#if !defined(EXCLUSIVE_SKYRIM_FLAT) || defined(SKYRIM_CROSS_VR)
#error Geometry witness requires the SDK flat layout; no universal/VR lock offsets
#endif
static_assert(sizeof(RE::NiSkinInstance)==0x88);
static_assert(sizeof(REX::W32::CRITICAL_SECTION)==sizeof(CRITICAL_SECTION));
namespace {
namespace g=claw::geometry;using Json=nlohmann::json;
std::uint64_t now(){LARGE_INTEGER q{};return QueryPerformanceCounter(&q)?q.QuadPart:0;}
bool sameName(const char* a,const char* b){if(!a||!b)return false;while(*a&&*b){auto x=*a++,y=*b++;if(x>='A'&&x<='Z')x+=32;if(y>='A'&&y<='Z')y+=32;if(x!=y)return false;}return *a==*b;}
void name(char(&out)[64],const char* text){g::require(text,"Missing object name");auto size=strnlen_s(text,64);g::require(size<64,"Object name exceeds bound");std::memcpy(out,text,size+1);}
using Transform=std::array<float,13>;
Transform transform(const RE::NiTransform& t){Transform out{};for(unsigned r=0;r<3;++r)for(unsigned c=0;c<3;++c)out[r*3+c]=t.rotate.entry[r][c];out[9]=t.translate.x;out[10]=t.translate.y;out[11]=t.translate.z;out[12]=t.scale;for(auto v:out)g::require(std::isfinite(v),"Nonfinite typed transform");return out;}
class LockBusy final : public std::runtime_error {
public:
    LockBusy(g::LockStage stage, g::LockRole role) : std::runtime_error(g::lockBusyReason(stage, role)) {}
};
class TryCritical {
    CRITICAL_SECTION* lock_{};
public:
    explicit TryCritical(REX::W32::CRITICAL_SECTION& lock,g::LockStage stage,g::LockRole role){auto* p=reinterpret_cast<CRITICAL_SECTION*>(&lock);if(!TryEnterCriticalSection(p))throw LockBusy(stage,role);lock_=p;}
    ~TryCritical(){if(lock_)LeaveCriticalSection(lock_);}TryCritical(const TryCritical&)=delete;
};
Json rendererBusyDiagnostic(RE::BSGraphics::Renderer& renderer) {
    const auto base = reinterpret_cast<std::uintptr_t>(&renderer);
    const auto accessor = reinterpret_cast<std::uintptr_t>(&renderer.GetLock());
    const auto member = reinterpret_cast<std::uintptr_t>(&renderer.GetRendererData().lock);
    const auto* main = RE::Main::GetSingleton();
    auto stack = Json::array();
    std::array<void*, 12> frames{};
    const auto count = CaptureStackBackTrace(0, static_cast<DWORD>(frames.size()), frames.data(), nullptr);
    const auto game = GetModuleHandleW(nullptr);
    const auto skse = GetModuleHandleW(L"skse64_1_7_104.dll");
    for (unsigned i = 0; i < count; ++i) {
        MEMORY_BASIC_INFORMATION mapping{};
        if (!VirtualQuery(frames[i], &mapping, sizeof(mapping)) || mapping.Type != MEM_IMAGE) {
            stack.push_back({{"module", "unresolved"}});
            continue;
        }
        const char* module = mapping.AllocationBase == game ? "SkyrimSE.exe" :
                             mapping.AllocationBase == skse ? "skse64_1_7_104.dll" : "other-image";
        Json row{{"module", module}};
        if (mapping.AllocationBase == game || mapping.AllocationBase == skse)
            row["rva"] = reinterpret_cast<std::uintptr_t>(frames[i]) -
                         reinterpret_cast<std::uintptr_t>(mapping.AllocationBase);
        stack.push_back(std::move(row));
    }
    return {{"callbackThreadId", GetCurrentThreadId()}, {"engineMainThreadId", main ? Json(main->threadID) : Json(nullptr)},
            {"lockAccessorOffset", accessor - base}, {"lockMemberOffset", member - base},
            {"sdkAccessorsAgree", accessor == member}, {"stack", std::move(stack)}};
}
struct Bone {char name[64]{};Transform local{},world{},bind{};};
struct Partition {
    unsigned vertices{},triangles{},bones{},bonesPerVertex{};g::Layout layout{};bool vertexMap{},palette{};
    std::array<std::uint16_t,g::maxBones> boneMap{};
    std::array<int,6> localRows{};std::array<std::array<std::uint8_t,4>,6> paletteRows{};
};
struct Mesh {
    char name[64]{};unsigned vertices{},triangles{},boneCount{},partitionCount{},pointCount{};
    Transform local{},world{},skinTransform{};std::array<Bone,g::maxBones> bones{};
    std::array<Partition,g::maxPartitions> partitions{};std::array<g::Point,6> points{};
    std::array<g::Triangle,g::maxTriangles> direct{},mapped{};unsigned triangleRows{};
    bool directPossible{true},mappedPossible{true};int supportVariant{-1};std::uint64_t topologyHash{};const char* topologyMode{};
};
struct Sample {std::array<Mesh,2> meshes{};Transform rootLocal{},rootWorld{};std::uint64_t started{},finished{},rootKey{};std::uint32_t handle{},form{},base{},race{};};
struct MeshLease {
    RE::NiPointer<RE::NiSkinInstance> skin;RE::NiPointer<RE::NiSkinData> data;RE::NiPointer<RE::NiSkinPartition> partition;
    std::array<RE::NiPointer<RE::NiAVObject>,g::maxBones> bones{};
};
struct Context {
    std::mutex mutex;g::Slot slot;std::string payload,reason;Json rendererBusy;std::atomic<std::uint64_t> epoch{1};std::atomic<bool> loading{false};
    std::uint64_t frequency{},boundRoot{},boundEpoch{};std::uint32_t boundHandle{};
};
Context* context{};
void meshCopy(RE::BSGeometry* geometry,unsigned shapeIndex,Mesh& out,MeshLease& lease) {
    const auto& expected=sealed::shapes[shapeIndex];name(out.name,geometry->name.c_str());
    g::require(geometry->AsDynamicTriShape()==nullptr,"Dynamic stream unsupported: SDK has no bounded BSSpinLock try API; no stream read");
    auto* shape=geometry->AsTriShape();g::require(shape&&geometry->GetType().underlying()==static_cast<std::uint8_t>(RE::BSGeometry::Type::kTriShape),"Unsupported fixed geometry RTTI/type");
    auto& skin=lease.skin;skin=geometry->GetGeometryRuntimeData().skinInstance;g::require(bool(skin),"Missing skin instance");
    TryCritical skinLock(skin->lock,g::LockStage::skinCopy,shapeIndex?g::LockRole::head:g::LockRole::furBelly); // Renderer lock is already held by caller, matching SKEE writer order.
    auto& data=lease.data;data=skin->skinData;auto& partition=lease.partition;partition=skin->skinPartition;
    g::require(data&&partition&&skin->bones,"Missing attached skin data/partition/bones");
    out.vertices=partition->vertexCount;out.partitionCount=partition->numPartitions;out.boneCount=data->GetBoneCount();out.pointCount=expected.pointCount;
    g::require(out.vertices==expected.vertices&&shape->GetTrishapeRuntimeData().vertexCount==expected.vertices,"Vertex topology differs from sealed input");
    g::require(out.boneCount==expected.bones&&out.boneCount<=g::maxBones&&out.partitionCount&&out.partitionCount<=g::maxPartitions,"Skin/partition count outside sealed bounds");
    const auto partitions=g::partitionStorage(partition->partitions.data(),out.partitionCount);
    out.local=transform(geometry->local);out.world=transform(geometry->world);out.skinTransform=transform(data->rootParentToSkin);
    auto& heldBones=lease.bones;
    for(unsigned b=0;b<out.boneCount;++b){heldBones[b]=RE::NiPointer<RE::NiAVObject>{skin->bones[b]};g::require(bool(heldBones[b]),"Missing skin bone");
        auto& row=out.bones[b];name(row.name,heldBones[b]->name.c_str());g::require(sameName(row.name,expected.boneNames[b]),"Sealed ordered bone map differs");
        row.local=transform(heldBones[b]->local);row.world=transform(heldBones[b]->world);row.bind=transform(data->GetBoneDataSkinToBone(b));}
    for(unsigned p=0;p<out.partitionCount;++p){
        const auto& input=partitions[p];auto& part=out.partitions[p];auto* buffer=input.buffData;
        g::require(buffer&&buffer->rawVertexData&&input.triList,"Missing attached CPU vertex/index buffer");
        part.vertices=input.vertices;part.triangles=input.triangles;part.bones=input.numBones;part.bonesPerVertex=input.bonesPerVertex;
        g::require(part.vertices&&part.vertices<=out.vertices&&part.bones<=out.boneCount&&part.bonesPerVertex==4,"Unsupported partition/palette extent");
        part.layout={buffer->vertexDesc.GetSize(),buffer->vertexDesc.GetAttributeOffset(RE::BSGraphics::Vertex::VA_POSITION),buffer->vertexDesc.GetAttributeOffset(RE::BSGraphics::Vertex::VA_SKINNING),static_cast<std::uint16_t>(buffer->vertexDesc.GetFlags())};
        auto descriptor=input.vertexDesc;g::validate(part.layout,out.vertices);g::require(descriptor.GetSize()==part.layout.stride,"Partition/attached descriptor stride differs");
        part.vertexMap=input.vertexMap!=nullptr;part.palette=input.bonePalette!=nullptr;part.localRows.fill(-1);
        if(input.bones)for(unsigned b=0;b<part.bones;++b){g::require(input.bones[b]<out.boneCount,"Partition bone map outside ordered skin bones");part.boneMap[b]=input.bones[b];}
        else g::require(!part.bones,"Missing partition bone map");
        for(unsigned v=0;v<part.vertices;++v){auto global=input.vertexMap?input.vertexMap[v]:v;g::require(global<out.vertices,"Partition vertex map out of bounds");
            for(unsigned point=0;point<out.pointCount;++point)if(global==expected.points[point]){g::require(part.localRows[point]<0,"Duplicate selected partition map row");part.localRows[point]=static_cast<int>(v);}}
        for(unsigned i=0;i<out.pointCount;++i){
            auto point=g::decode({buffer->rawVertexData,std::size_t(out.vertices)*part.layout.stride},part.layout,out.vertices,expected.points[i]);
            if(!p)out.points[i]=point;else g::require(std::memcmp(&out.points[i],&point,sizeof(point))==0,"Selected replicated partition bytes differ");
            if(input.bonePalette&&part.localRows[i]>=0){std::memcpy(part.paletteRows[i].data(),input.bonePalette+std::size_t(part.localRows[i])*4,4);
                for(auto index:part.paletteRows[i])g::require(index<part.bones,"Selected legacy palette index out of bounds");}
        }
        g::require(out.triangleRows+part.triangles<=g::maxTriangles,"Topology copy bound exceeded");
        for(unsigned t=0;t<part.triangles;++t){g::Triangle direct{},mapped{};
            for(unsigned c=0;c<3;++c){auto index=input.triList[std::size_t(t)*3+c];direct[c]=index;
                if(index>=out.vertices)out.directPossible=false;
                if(index>=part.vertices){out.mappedPossible=false;mapped[c]=0;}else mapped[c]=input.vertexMap?input.vertexMap[index]:index;
            }out.direct[out.triangleRows]=direct;out.mapped[out.triangleRows++]=mapped;
        }
    }
    out.triangles=out.triangleRows;g::require(out.triangles==expected.triangles,"Sealed total topology count differs");
    bool baseline=true,candidate=true;for(unsigned i=0;i<out.pointCount;++i){baseline&=g::support(out.points[i],{expected.baseline[i].data(),out.boneCount});candidate&=g::support(out.points[i],{expected.candidate[i].data(),out.boneCount});}
    g::require(baseline||candidate,"Packed point→bone support differs from both sealed NIF variants");out.supportVariant=baseline?(candidate?2:0):1;
    for(unsigned b=0;b<out.boneCount;++b)g::require(transform(heldBones[b]->local)==out.bones[b].local&&transform(heldBones[b]->world)==out.bones[b].world,"Bone pose changed during CPU copy");
    g::require(transform(geometry->local)==out.local&&transform(geometry->world)==out.world,"Geometry pose changed during CPU copy");
    g::require(geometry->GetGeometryRuntimeData().skinInstance.get()==skin.get()&&skin->skinPartition.get()==partition.get()&&skin->skinData.get()==data.get(),"Attached skin lease changed during copy");
}
std::unique_ptr<Sample> collect(std::uint32_t form,std::uint32_t base,std::uint64_t epoch,std::uint32_t previousHandle,std::uint64_t previousRoot,Json& rendererBusy) {
    auto out=std::make_unique<Sample>();out->started=now();
    auto* actor=RE::TESForm::LookupByID<RE::Actor>(form);g::require(actor&&actor->GetFormID()!=0x14&&actor->Is3DLoaded(),"Selected dynamic actor unavailable");
    auto* npc=actor->GetActorBase();auto* race=actor->GetRace();
    g::require(npc&&npc->GetFormID()==base&&npc->GetSex()==RE::SEX::kFemale&&race&&race->GetFormID()==g::beastRace,"Sealed female fixture/base/race differs");
    out->form=form;out->base=base;out->race=race->GetFormID();out->handle=actor->GetHandle().native_handle();g::require(out->handle,"Missing actual runtime handle");
    RE::NiPointer<RE::NiAVObject> root{actor->Get3D(false)};g::require(bool(root),"Selected third-person root absent");out->rootKey=reinterpret_cast<std::uintptr_t>(root.get());
    g::require((!previousHandle||previousHandle==out->handle)&&(!previousRoot||previousRoot==out->rootKey),"Actor/root lease turned over; new process required");
    out->rootLocal=transform(root->local);out->rootWorld=transform(root->world);
    std::array<RE::NiPointer<RE::BSGeometry>,2> selected{};std::vector<RE::NiAVObject*> pending{root.get()};unsigned visited=0;
    while(!pending.empty()){auto* object=pending.back();pending.pop_back();g::require(++visited<=g::maxObjects,"Scene traversal bound exceeded");
        if(auto* node=object->AsNode())for(const auto& child:node->GetChildren())if(child){g::require(pending.size()<g::maxObjects,"Scene traversal stack bound");pending.push_back(child.get());}
        auto* geometry=object->AsGeometry();if(!geometry)continue;
        for(unsigned i=0;i<2;++i)if(sameName(object->name.c_str(),sealed::shapes[i].role)){g::require(!selected[i],"Ambiguous geometry role");selected[i]=RE::NiPointer<RE::BSGeometry>{geometry};}
    }
    g::require(selected[0]&&selected[1],"Required fur_belly/HEAD roles absent");
    auto* renderer=RE::BSGraphics::Renderer::GetSingleton();g::require(renderer,"Renderer lock unavailable");
    std::array<MeshLease,2> leases{}; // Retained only until this main task finishes, never cached/published.
    bool rendererAcquired=false;
    try {
        TryCritical rendererLock(renderer->GetLock(),g::LockStage::renderer,g::LockRole::none);
        rendererAcquired=true;
        for(unsigned i=0;i<2;++i)meshCopy(selected[i].get(),i,out->meshes[i],leases[i]);
        for(unsigned i=0;i<2;++i){const auto& lease=leases[i];const auto& mesh=out->meshes[i];TryCritical skinLock(lease.skin->lock,g::LockStage::skinBracket,i?g::LockRole::head:g::LockRole::furBelly);
            g::require(selected[i]->GetGeometryRuntimeData().skinInstance.get()==lease.skin.get()&&lease.skin->skinPartition.get()==lease.partition.get()&&lease.skin->skinData.get()==lease.data.get(),"Attached two-mesh lease changed");
            g::require(transform(selected[i]->local)==mesh.local&&transform(selected[i]->world)==mesh.world&&lease.data->GetBoneCount()==mesh.boneCount,"Geometry/bone metadata changed across shared copy");
            for(unsigned b=0;b<mesh.boneCount;++b)g::require(lease.skin->bones[b]==lease.bones[b].get()&&transform(lease.bones[b]->local)==mesh.bones[b].local&&transform(lease.bones[b]->world)==mesh.bones[b].world,"Bone identity/pose changed across two-mesh copy");
        }
    } catch (const LockBusy&) {
        if (!rendererAcquired) {
            try { rendererBusy = rendererBusyDiagnostic(*renderer); } catch (...) {} // Keep the original refusal.
        }
        throw;
    }
    g::Lease before{form,base,race->GetFormID(),out->handle,epoch,out->rootKey};
    g::Lease after{actor->GetFormID(),actor->GetActorBase()?actor->GetActorBase()->GetFormID():0,actor->GetRace()?actor->GetRace()->GetFormID():0,actor->GetHandle().native_handle(),context->epoch.load(),reinterpret_cast<std::uintptr_t>(actor->Get3D(false))};
    g::require(g::sameLease(before,after)&&!context->loading.load()&&actor->GetActorBase()==npc&&actor->GetRace()==race,"World/actor/root changed during sample");
    g::require(transform(root->local)==out->rootLocal&&transform(root->world)==out->rootWorld,"Root pose changed during sample");
    for(unsigned a=0;a<out->meshes[0].boneCount;++a)for(unsigned b=0;b<out->meshes[1].boneCount;++b)
        if(sameName(out->meshes[0].bones[a].name,out->meshes[1].bones[b].name))g::require(out->meshes[0].bones[a].world==out->meshes[1].bones[b].world,"Shared bone pose changed between geometry copies");
    for(unsigned i=0;i<2;++i){auto& mesh=out->meshes[i];const auto hash=sealed::shapes[i].topologyHash;
        bool direct=mesh.directPossible&&g::topology({mesh.direct.data(),mesh.triangles})==hash;
        bool mapped=mesh.mappedPossible&&g::topology({mesh.mapped.data(),mesh.triangles})==hash;
        g::require(direct||mapped,"Runtime triangle mapping differs from sealed topology");mesh.topologyHash=hash;mesh.topologyMode=direct?(mapped?"direct-and-mapped-equivalent":"direct-global"):"partition-map";
    }
    out->finished=now();return out;
}
Json payload(const Sample& sample,std::uint32_t serial,std::uint32_t nonce,std::uint64_t epoch) {
    Json result={{"schema","claw-cpu-geometry-witness/1"},{"phase","skse_main_thread_task"},{"physicsPhase","not_synchronized"},{"renderPhase","not_synchronized"},
        {"observedCpuPreSkin",true},{"reconstructedSkinnedWorld",{{"status","not_implemented"}}},{"gpuPostSkinObserved",false},{"renderedAttachmentAccepted",false},
        {"pid",GetCurrentProcessId()},{"requestSerial",serial},{"nonce",nonce},{"loadEpoch",epoch},{"startedQpc",sample.started},{"finishedQpc",sample.finished},{"qpcFrequency",context->frequency},
        {"actorForm",sample.form},{"baseForm",sample.base},{"raceForm",sample.race},{"runtimeHandle",sample.handle},{"rootToken",1},
        {"rootIdentityBasis","sampled address checked; NiPointer retained only within task"},{"unobservedAddressReuseDetectable",false},
        {"rootLocal",sample.rootLocal},{"rootWorld",sample.rootWorld},{"baselineNif",sealed::baselineSha},{"candidateNif",sealed::candidateSha},{"tri",sealed::triSha},{"geometries",Json::array()}};
    for(unsigned i=0;i<2;++i){const auto& m=sample.meshes[i];Json mesh={{"role",sealed::shapes[i].role},{"observedName",m.name},{"positionSource","attached_partition_raw_float32_pre_skin"},
        {"vertexCount",m.vertices},{"triangleCount",m.triangles},{"topologyFingerprintFNV64",m.topologyHash},{"triangleMapping",m.topologyMode},
        {"supportVariant",m.supportVariant==2?"same-in-both":m.supportVariant==0?"baseline":"root578"},{"packedGlobalBoneMapVerifiedAgainstSealedSupport",true},
        {"local",m.local},{"world",m.world},{"rootParentToSkin",m.skinTransform},{"bones",Json::array()},{"partitions",Json::array()},{"points",Json::array()}};
        for(unsigned b=0;b<m.boneCount;++b){auto& bone=m.bones[b];mesh["bones"].push_back({{"index",b},{"name",bone.name},{"local",bone.local},{"world",bone.world},{"skinToBone",bone.bind}});}
        for(unsigned p=0;p<m.partitionCount;++p){auto& part=m.partitions[p];Json bones=Json::array();for(unsigned b=0;b<part.bones;++b)bones.push_back(part.boneMap[b]);
            mesh["partitions"].push_back({{"index",p},{"vertices",part.vertices},{"triangles",part.triangles},{"bonesPerVertex",part.bonesPerVertex},
                {"stride",part.layout.stride},{"positionOffset",part.layout.position},{"skinningOffset",part.layout.skinning},{"vertexFlags",part.layout.flags},
                {"vertexMapPresent",part.vertexMap},{"palettePresent",part.palette},{"boneMap",bones},{"selectedLocalRows",part.localRows},{"selectedPaletteRows",part.paletteRows}});}
        for(unsigned v=0;v<m.pointCount;++v){auto& point=m.points[v];mesh["points"].push_back({{"index",sealed::shapes[i].points[v]},{"cpuPreSkin",point.position},{"halfBits",point.halfWeights},{"decodedRawWeights",point.weights},{"packedBoneIndices",point.indices}});}
        result["geometries"].push_back(std::move(mesh));
    }return result;
}
Json envelope(const char* status){return {{"schema","claw-cpu-geometry-cache/1"},{"status",status},{"requestSerial",context->slot.serial},{"nonce",context->slot.nonce},{"pid",GetCurrentProcessId()},
    {"loadEpoch",context->slot.epoch},{"cachedImmutable",true},{"timeMeaning","capture time, not current read time"}};}
void task(std::uint32_t serial,std::uint32_t form,std::uint32_t base,std::uint32_t nonce,std::uint64_t epoch,std::uint32_t handle,std::uint64_t root) {
    std::string text,reason;Json rendererBusy;std::uint32_t actualHandle=0;std::uint64_t actualRoot=0;
    try{{std::lock_guard lock(context->mutex);g::require(context->slot.begin(serial,context->epoch.load(),now(),context->loading.load()),"Queued sample expired or world changed before start");}
        auto sample=collect(form,base,epoch,handle,root,rendererBusy);actualHandle=sample->handle;actualRoot=sample->rootKey;text=payload(*sample,serial,nonce,epoch).dump();g::require(text.size()<=256*1024,"Immutable response exceeds bound");
    }catch(const std::exception& e){reason=e.what();}
    std::lock_guard lock(context->mutex);const auto currentEpoch=context->epoch.load();const auto finished=now();const bool loading=context->loading.load();
    const bool current=context->slot.begin(serial,currentEpoch,finished,loading);
    const bool ok=context->slot.finish(serial,currentEpoch,finished,reason.empty()&&!loading);
    context->rendererBusy=current&&!ok?std::move(rendererBusy):Json{};
    context->payload=ok?std::move(text):std::string{};context->reason=ok?std::string{}:reason.empty()?"Sample finished after original deadline/world change":reason;
    if(ok){context->boundHandle=actualHandle;context->boundRoot=actualRoot;context->boundEpoch=epoch;}
}
std::string capture(RE::StaticFunctionTag*,std::int32_t formBits,std::int32_t baseBits,std::int32_t nonce) {
    std::lock_guard lock(context->mutex);auto form=std::bit_cast<std::uint32_t>(formBits),base=std::bit_cast<std::uint32_t>(baseBits);auto epoch=context->epoch.load();
    if(context->loading.load()||!g::sameBoundEpoch(context->boundEpoch,epoch)||!context->slot.request(form,base,static_cast<std::uint32_t>(nonce),epoch,now(),context->frequency*5)){auto out=envelope("refused");out["reason"]="Busy, consumed nonce, wrong fixed actor/base, changed bound world or sample bound";return out.dump();}
    auto serial=context->slot.serial;auto handle=context->boundHandle;auto root=context->boundRoot;context->payload.clear();context->reason.clear();context->rendererBusy=nullptr;
    try{SKSE::GetTaskInterface()->AddTask([=]{task(serial,form,base,static_cast<std::uint32_t>(nonce),epoch,handle,root);});}
    catch(...){context->slot.poisoned=true;context->reason="Queue outcome unavailable; process refuses further captures";}
    return envelope(context->slot.pending&&!context->slot.poisoned?"pending":"refused").dump();
}
bool validSerial(int serial){return serial>0&&static_cast<unsigned>(serial)==context->slot.serial&&context->slot.epoch==context->epoch.load()&&!context->loading.load();}
std::string readState(RE::StaticFunctionTag*,std::int32_t serial){std::lock_guard lock(context->mutex);if(!validSerial(serial)){auto out=envelope("refused");out["reason"]="Stale serial/world";return out.dump();}
    auto out=envelope(context->slot.poisoned?"refused":context->slot.pending?(now()<context->slot.deadline?"pending":"refused"):context->slot.ready?"ready":"refused");out["reason"]=context->reason;out["bytes"]=context->payload.size();out["chunks"]=(context->payload.size()+4095)/4096;
    if(!context->rendererBusy.is_null())out["rendererBusy"]=context->rendererBusy;return out.dump();}
std::string readChunk(RE::StaticFunctionTag*,std::int32_t serial,std::int32_t index){std::lock_guard lock(context->mutex);if(!validSerial(serial)||!context->slot.ready||index<0||std::size_t(index)*4096>=context->payload.size())return {};return context->payload.substr(std::size_t(index)*4096,4096);}
bool papyrus(RE::BSScript::IVirtualMachine* vm){if(!vm)return false;vm->RegisterFunction("Capture","CLAWGeometryWitness",capture);vm->RegisterFunction("ReadState","CLAWGeometryWitness",readState);vm->RegisterFunction("ReadChunk","CLAWGeometryWitness",readChunk);return true;}
void message(SKSE::MessagingInterface::Message* m){if(!m)return;if(m->type==SKSE::MessagingInterface::kPreLoadGame){context->loading.store(true);++context->epoch;}
    else if(m->type==SKSE::MessagingInterface::kNewGame){++context->epoch;context->loading.store(false);}
    else if(m->type==SKSE::MessagingInterface::kPostLoadGame)context->loading.store(!claw::mayActivateWorld(claw::WorldStart::postLoadGame,m->dataLen,reinterpret_cast<std::uintptr_t>(m->data)));}
bool supported(const SKSE::QueryInterface* s){return s&&!s->IsEditor()&&s->RuntimeVersion()==SKSE::RUNTIME_SSE_1_7_104&&s->SKSEVersion()>=REL::Version{2,3,1,0}.pack();}
}
extern "C" __declspec(dllexport) constinit SKSE::PluginVersionData SKSEPlugin_Version=[]{SKSE::PluginVersionData v;v.PluginVersion({0,0,2,0});v.PluginName("CLAWGeometryWitness");v.AuthorName("CLAW contributors");v.versionIndependenceEx=SKSE::PluginVersionData::kVersionIndependentEx_AddressLibraryV5;v.compatibleVersions[0]=SKSE::RUNTIME_SSE_1_7_104.pack();v.MinimumRequiredXSEVersion({2,3,1,0});return v;}();
extern "C" __declspec(dllexport) bool SKSEPlugin_Query(const SKSE::QueryInterface* s,SKSE::PluginInfo* info){if(!info)return false;info->infoVersion=SKSE::PluginInfo::kVersion;info->name="CLAWGeometryWitness";info->version=2;return supported(s);}
extern "C" __declspec(dllexport) bool SKSEPlugin_Load(const SKSE::LoadInterface* s){if(!supported(s))return false;try{SKSE::Init(s,{.log=false});LARGE_INTEGER frequency{};if(!QueryPerformanceFrequency(&frequency)||frequency.QuadPart<=0||!SKSE::GetTaskInterface()||!SKSE::GetPapyrusInterface()||!SKSE::GetMessagingInterface())return false;context=new Context;context->frequency=frequency.QuadPart;return SKSE::GetPapyrusInterface()->Register(papyrus)&&SKSE::GetMessagingInterface()->RegisterListener(message);}catch(...){return false;}}
