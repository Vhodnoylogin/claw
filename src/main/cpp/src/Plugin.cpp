// Own implementation. Engine access and every SKEE write/read run in SKSE tasks.
#include "claw/Preset.h"
#include "claw/RequestOwnership.h"
#include "claw/MorphLink.h"
#include "claw/MorphRuleSerialization.h"
#include "claw/MorphOwnership.h"
#include "claw/PhysicsObserver.h"
#include "claw/MorphProfiles.h"
#include "claw/SourceBootstrapPolicy.h"
#include "claw/RuntimeSupport.h"
#if defined(CLAW_PHYSICS_MODEL_HEADER)
#include "claw/PhysicsFit.h"
#include CLAW_PHYSICS_MODEL_HEADER
#endif
#include <IPluginInterface.h>  // official pinned external API, never vendored
#if defined(CLAW_OBODY_API_HEADER)
#include CLAW_OBODY_API_HEADER // Official public protocol, optional external SDK.
#endif
#include <spdlog/sinks/basic_file_sink.h>
#include <atomic>
#include <array>
#include <chrono>
#include <condition_variable>
#include <cmath>
#include <cstring>
#include <deque>
#include <filesystem>
#include <exception>
#include <limits>
#include <map>
#include <memory>
#include <mutex>
#include <random>
#include <set>
#include <thread>
#include <utility>

#ifdef interface
#undef interface
#endif

#if !defined(ENABLE_SKYRIM_SE) || !defined(ENABLE_SKYRIM_AE) || !defined(ENABLE_SKYRIM_VR) || !defined(HAS_SKYRIM_MULTI_TARGETING)
#error The universal CLAW DLL requires CommonLib SE, AE and VR multi-targeting together.
#endif

namespace {
// One binary uses CommonLib's runtime-selected relocations, virtual dispatch,
// object-layout accessors and Papyrus bindings. This explicit candidate list is
// a load boundary, not a claim that all listed engines passed game tests.
const claw::RuntimeTarget* runtimeTarget(const SKSE::QueryInterface* skse) {
    return skse ? claw::runtimeTarget(skse->RuntimeVersion(), skse->SKSEVersion(), skse->IsEditor()) : nullptr;
}

// CommonLib 3.7 enumerates references; 9.1 enumerates nullable pointers.
RE::Actor* highActorPointer(RE::Actor* actor) { return actor; }
RE::Actor* highActorPointer(RE::Actor& actor) { return &actor; }

enum class Status : std::int32_t {
    unknown = 0, pending = 1, applied = 2, unloaded = 3,
    error = 4, human = 5, cleared = 6, providerUnavailable = 7
};
struct ActorPin {
    explicit ActorPin(RE::Actor* value, std::uint64_t number) : actor(value), serial(number) {}
    RE::NiPointer<RE::Actor> actor;
    std::uint64_t serial;
};
using Pin = std::shared_ptr<ActorPin>;
struct State {
    std::uint64_t identity{};
    std::string preset;
    claw::Sex sex{};
    bool suppressed{};
    claw::MorphLink link;
    claw::Morphs cache;
    Status status{Status::pending};
    std::string error;
    std::uintptr_t lastRoot{};
    RE::VMHandle vmHandle{};
    float lastWeight{-1};
    float humanWeight{-1}, beastWeight{-1}; // Last observed normalized NPC property, never an input override.
    bool dirty{true};
    RE::ActorHandle runtimeHandle; // Weak engine witness; created/resolved only in tasks.
    RE::Actor* runtimePointer{}; // Cached comparison only, never dereferenced by getters.
    std::uint64_t runtimeSerial{}; // Fresh after load; never serialized.
    claw::RequestBinding latestRequest; // Non-owning, process-local terminal request witness.
    bool quarantined{};
    // Optional source bootstrap lease: deliberately transient, never restored.
    bool adoptedDefault{}, firstSeenBeast{}, observedHuman{}, sourceRevoked{};
    bool sourceAdvertised{}, sourceValidationPending{}, sourceReady{}, sourceClaimed{};
    std::uint32_t sourceToken{};
    std::uint64_t sourceWorld{}, sourceRuntime{};
    std::uint64_t sourceProviderEpoch{};
    std::uintptr_t defaultRoot{}, sourceRoot{};
    claw::Sex sourceSex{};
    std::string sourceProfile;
};

constexpr std::uint32_t serializationID = 0x444C5743; // CWLD, exclusive to this companion
constexpr std::uint32_t sessionRecord = 0x534C5743;
constexpr std::uint32_t actorRecord = 0x414C5743;
constexpr std::size_t maxActors = 8192;
constexpr float epsilon = 0.0001F;
claw::Catalog catalog;
claw::MorphProfileCatalog morphProfiles;
std::map<RE::FormID, State> states;
claw::RequestLedger<Pin> requests{maxActors};
// One intrusive pin per physical Actor, shared by pending tasks/requests/natives.
// Native callbacks never remove entries: a task can finish before its callback
// returns, so use_count alone is safe only when THIS pool keeps the last pin.
// Deliberately process-lifetime storage: DLL/static teardown has no qualified
// engine thread. Normal releases happen ONLY through collectPins in SKSE tasks.
auto& pins = *new std::map<RE::Actor*, Pin>();
std::uint64_t nextPinSerial{1}, nextRuntimeSerial{1};
std::recursive_mutex mutex;
std::uint64_t saveNamespace{};
std::uint64_t nextIdentity{1};
std::atomic<std::uint64_t> epoch{};
std::atomic<bool> enabled{}, scanPending{};
const SKSE::TaskInterface* tasks{};
IBodyMorphInterface* morphs{};
RE::TESRace* beastRace{};
std::jthread timer;
struct PhysicsBinding {
    RE::ActorHandle actor;
    RE::Actor* pointer{};
    std::uint64_t runtime{}, world{}, registration{};
    std::int32_t generation{};
    std::vector<std::string> names;
    std::string model, evidence, condition;
    claw::PhysicsObservation observation;
    std::uint32_t snapshot{};
    bool female{}, ready{}, delivered{}, active{true};
#if defined(CLAW_PHYSICS_MODEL_HEADER)
    std::vector<claw::physics::Capsule> capsules;
    bool needsFit{}, fitPending{};
#endif
};
std::map<RE::FormID, PhysicsBinding> physicsBindings;
bool physicsPopulationEnabled{};
bool obodySourcePopulationEnabled{};
std::uint32_t nextSourceBootstrapToken{1};
std::atomic<bool> obodyApiReady{};
std::atomic<bool> obodyApiAvailable{};
std::atomic<std::uint64_t> obodyProviderEpoch{};
std::atomic<std::uint64_t> obodyStockGenerationEpoch{std::numeric_limits<std::uint64_t>::max()};
std::atomic<bool> obodyActorListenerRegistered{};
#if defined(CLAW_OBODY_API_HEADER)
OBody::API::IPluginInterface* obodyAPI{};
class OBodyStockGeneration final : public OBody::API::IActorChangeEventListener {
public:
    using Generated = struct OBody::API::IActorChangeEventListener::OnActorGenerated;
    Generated::Response OnActorGenerated(::Actor*, Generated::Flags, Generated::Payload& payload) override {
        const auto providerEpoch = obodyProviderEpoch.load();
        if (obodyApiReady.load() && payload.responsiblePluginInterface == nullptr &&
            obodyStockGenerationEpoch.exchange(providerEpoch) != providerEpoch && tasks) {
            // The provider's internal CanDistribute path established the actual
            // save's distribution key. No actor or provider operation crosses here.
            tasks->AddTask([providerEpoch] {
                if (!enabled || !obodyApiReady || obodyProviderEpoch != providerEpoch ||
                    obodyStockGenerationEpoch != providerEpoch) return;
                if (auto* source = SKSE::GetModCallbackEventSource()) {
                    SKSE::ModCallbackEvent event;
                    event.eventName = "CLAWDistribution_OBodySourceAvailable";
                    event.strArg = "stock-generation-readiness"; event.numArg = 0; event.sender = nullptr;
                    source->SendEvent(&event);
                }
            });
        }
        return Generated::Response::None;
    }
} obodyStockGeneration;
class OBodyReadiness final : public OBody::API::IOBodyReadinessEventListener {
public:
    void OBodyIsReady() override {
        obodyApiAvailable = obodyAPI != nullptr;
        if (obodyAPI && !obodyActorListenerRegistered) obodyActorListenerRegistered = obodyAPI->RegisterEventListener(obodyStockGeneration);
        obodyApiReady.store(obodyAPI != nullptr);
    }
    void OBodyIsNoLongerReady() override {
        obodyApiReady.store(false); ++obodyProviderEpoch;
        obodyStockGenerationEpoch = std::numeric_limits<std::uint64_t>::max();
    }
} obodyReadiness;
#endif
bool sourceProviderReady() {
    return obodyApiReady.load() && obodyActorListenerRegistered.load() &&
        obodyStockGenerationEpoch.load() == obodyProviderEpoch.load();
}
std::map<RE::FormID, std::uint64_t> physicsPopulationBlocked;
std::map<RE::Actor*, std::uint64_t> physicsRegistrationRequests;
std::uint64_t nextPhysicsRegistration{1};
std::uint32_t nextPhysicsSnapshot{1};
#if defined(CLAW_PHYSICS_MODEL_HEADER)
struct PhysicsFitWork {
    RE::FormID id{}; // Numeric routing token; no engine object crosses to worker.
    std::uint64_t world{}, registration{};
    std::uintptr_t root{};
    std::int32_t generation{};
    bool female{};
    std::vector<float> values;
    float weight{};
};
std::mutex physicsWorkMutex;
std::condition_variable_any physicsWorkReady;
std::deque<PhysicsFitWork> physicsWork;
std::jthread physicsWorker;
#endif
void observePhysics(RE::Actor* actor);
void invalidatePhysics(RE::FormID id) {
    if (const auto it = physicsBindings.find(id); it != physicsBindings.end()) {
        it->second.observation.invalidate(); it->second.ready = false;
    }
}
void logError(State& state, std::string reason, Status status = Status::error);
void offerSourceBootstrap(RE::Actor* actor);
void revokeSourceBootstrap(State& state) {
    state.sourceRevoked = true; state.sourceReady = false;
    state.sourceValidationPending = false; state.sourceToken = 0;
}

Pin pinActor(RE::Actor* actor) {
    if (!actor) return {};
    if (const auto found = pins.find(actor); found != pins.end()) return found->second;
    if (pins.size() >= maxActors || nextPinSerial == std::numeric_limits<std::uint64_t>::max()) return {};
    auto pin = std::make_shared<ActorPin>(actor, nextPinSerial++);
    pins.emplace(actor, pin);
    return pin;
}

// Called only in SKSE tasks. State owns no intrusive pin. The pool protects
// pending/native owners until their final main-safe collection.
void collectPins() {
    claw::collectUnshared(pins);
}
void queuePinCollection() {
    if (tasks) tasks->AddTask([] { std::lock_guard lock(mutex); collectPins(); });
}

bool currentOwner(RE::Actor* actor) {
    return actor && !actor->IsDeleted() && RE::TESForm::LookupByID<RE::Actor>(actor->GetFormID()) == actor;
}
bool boundTo(const State& state, const RE::Actor* actor) {
    return state.runtimeSerial && state.runtimePointer == actor;
}
void quarantine(State& state, std::string error) {
    revokeSourceBootstrap(state);
    state.quarantined = true; state.runtimeSerial = 0; state.runtimePointer = nullptr;
    state.runtimeHandle.reset(); state.cache.clear();
    logError(state, std::move(error));
}
void checkRuntimeInstances() {
    for (auto it = states.begin(); it != states.end();) {
        auto& state = it->second;
        if (!state.runtimeSerial || state.quarantined) { ++it; continue; }
        const auto actor = std::as_const(state.runtimeHandle).get(); // Const resolution; strong temporary lives only in this main task.
        if (!claw::sameRuntimeActor(state.runtimePointer, actor.get(), state.runtimePointer)) {
            quarantine(state, "runtime actor handle expired or changed; saved assignment quarantined");
        } else if (actor->IsDeleted()) {
            if (const auto pin = pins.find(actor.get()); pin != pins.end()) requests.eraseOwner(it->first, pin->second->serial);
            it = states.erase(it);
            continue;
        } else if (RE::TESForm::LookupByID<RE::Actor>(it->first) != actor.get()) {
            quarantine(state, "runtime actor no longer owns saved FormID; assignment quarantined");
        } else if (!actor->Is3DLoaded() || !actor->Get3D()) {
            state.status = Status::unloaded; state.dirty = true;
            if (state.defaultRoot) revokeSourceBootstrap(state);
        }
        ++it;
    }
}
const claw::RequestLedger<Pin>::Request* actorRequest(RE::Actor* actor) {
    if (!actor) return nullptr;
    const auto pin = pins.find(actor);
    const auto found = states.find(actor->formID);
    const State* state = found != states.end() && boundTo(found->second, actor) && !found->second.quarantined ? &found->second : nullptr;
    return claw::resolveActorRequest(requests, actor->formID, epoch.load(), pin == pins.end() ? 0 : pin->second->serial,
        state ? &state->latestRequest : nullptr, state ? state->runtimeSerial : 0);
}

bool pendingActorRequest(RE::Actor* actor) {
    const auto* request = actorRequest(actor);
    return request && request->error.empty();
}

bool sourcePolicyAllows(const State& state, RE::Actor* actor) {
    return claw::SourceBootstrapPolicy{state.adoptedDefault, state.firstSeenBeast, state.observedHuman,
        state.humanWeight >= 0, state.sourceRevoked, state.suppressed, state.quarantined,
        state.sourceClaimed, pendingActorRequest(actor)}.allows();
}

void logError(State& state, std::string reason, Status status) {
    if (state.error != reason) SKSE::log::warn("CLAW Distribution: {}", reason);
    state.error = std::move(reason);
    state.status = status;
}

std::uint64_t newNamespace() {
    std::random_device random;
    const auto value = (static_cast<std::uint64_t>(random()) << 32) | random();
    return value ? value : 1;
}

::TESObjectREFR* skeeReference(RE::Actor* actor);
void captureSources(RE::Actor* actor, claw::MorphLink& link);
State* stateFor(RE::Actor* actor, bool create, bool adoptDefaults = true) {
    if (!currentOwner(actor) || !actor->GetActorBase()) return nullptr;
    const auto id = actor->GetFormID();
    auto found = states.find(id);
    RE::VMHandle handle{};
    if (auto* vm = RE::BSScript::Internal::VirtualMachine::GetSingleton()) {
        if (auto* policy = vm->GetObjectHandlePolicy()) {
            handle = policy->GetHandleForObject(actor->GetFormType(), actor);
            if (handle == policy->EmptyHandle()) handle = 0;
        }
    }
    if (found != states.end()) {
        auto& state = found->second;
        if (state.quarantined) return &state;
        if (!claw::mayBindRestoredIdentity(state.vmHandle, handle, false)) {
            quarantine(state, "actor VM deletion identity unavailable or changed; assignment quarantined");
            return &state;
        }
        if (state.runtimeSerial) {
            const auto witness = std::as_const(state.runtimeHandle).get();
            if (!claw::sameRuntimeActor(state.runtimePointer, witness.get(), actor))
                quarantine(state, "actor runtime identity conflicts with saved FormID; assignment quarantined");
            return &state;
        }
        if (nextRuntimeSerial == std::numeric_limits<std::uint64_t>::max()) return nullptr;
        const auto runtime = actor->GetHandle();
        const auto witness = runtime.get();
        if (!witness || witness.get() != actor) {
            quarantine(state, "restored runtime actor handle unavailable; assignment quarantined");
            return &state;
        }
        state.runtimeHandle = runtime; state.runtimePointer = actor; state.runtimeSerial = nextRuntimeSerial++;
        return &state;
    }
    if (!create || !handle || states.size() >= maxActors || nextIdentity == std::numeric_limits<std::uint64_t>::max() ||
        nextRuntimeSerial == std::numeric_limits<std::uint64_t>::max()) return nullptr;
    const auto runtime = actor->GetHandle();
    const auto witness = runtime.get();
    if (!witness || witness.get() != actor) return nullptr;
    if (!saveNamespace) saveNamespace = newNamespace();
    State state;
    const auto newSex = actor->GetActorBase()->GetSex();
    if (newSex != RE::SEX::kMale && newSex != RE::SEX::kFemale) return nullptr;
    state.sex = newSex == RE::SEX::kFemale ? claw::Sex::female : claw::Sex::male;
    if (adoptDefaults) if (const auto* profile = morphProfiles.defaultFor(state.sex)) {
        if (!morphs) return nullptr; // No empty identity is minted before a full source capture.
        auto link = profile->link;
        try { captureSources(actor, link); }
        catch (const std::exception& error) { SKSE::log::warn("CLAW default family source capture: {}", error.what()); return nullptr; }
        state.link = std::move(link);
        state.adoptedDefault = true;
        if (!beastRace) if (auto* data = RE::TESDataHandler::GetSingleton())
            beastRace = data->LookupForm<RE::TESRace>(0xCDD84, "Skyrim.esm");
        state.firstSeenBeast = beastRace && actor->GetRace() == beastRace;
        state.defaultRoot = reinterpret_cast<std::uintptr_t>(actor->Get3D());
        for (const auto& [name, value] : state.link.sourceValues) {
            (void)value;
            if (value != 0 || morphs->HasBodyMorphName(skeeReference(actor), name.c_str())) { revokeSourceBootstrap(state); break; }
        }
    }
    state.identity = nextIdentity++;
    state.vmHandle = handle;
    state.runtimeHandle = runtime; state.runtimePointer = actor; state.runtimeSerial = nextRuntimeSerial++;
    return &states.emplace(id, std::move(state)).first->second;
}

::TESObjectREFR* skeeReference(RE::Actor* actor) {
    // SKEE's ABI takes the actual reference object, never a Papyrus handle or an
    // Actor sub-interface. First perform the SDK's typed base conversion; only
    // the official header's opaque global namespace spelling needs bridging.
    auto* reference = static_cast<RE::TESObjectREFR*>(actor);
    return reinterpret_cast<::TESObjectREFR*>(reference);
}

void physicsEvent(RE::Actor* actor, std::string_view kind, std::uint32_t sequence = 0) {
    if (auto* source = SKSE::GetModCallbackEventSource()) {
        SKSE::ModCallbackEvent event;
        event.eventName = "CLAWPhysics_Observation"; event.strArg = kind.data();
        event.numArg = static_cast<float>(sequence); event.sender = actor;
        source->SendEvent(&event);
    }
}

void sourceBootstrapEvent(RE::Actor* actor, State& state, bool ready) {
    if (auto* source = SKSE::GetModCallbackEventSource()) {
        SKSE::ModCallbackEvent event;
        event.eventName = ready ? "CLAWDistribution_OBodySourceReady" : "CLAWDistribution_OBodySourceCandidate";
        event.strArg = state.sourceProfile;
        event.numArg = static_cast<float>(state.sourceToken); event.sender = actor;
        source->SendEvent(&event);
    }
}

bool sourceBootstrapLive(RE::Actor* actor, State& state) {
    if (!enabled || !obodySourcePopulationEnabled || !morphs || !sourceProviderReady() ||
        !sourcePolicyAllows(state, actor) ||
        !currentOwner(actor) || !boundTo(state, actor) || state.quarantined || state.suppressed ||
        !state.adoptedDefault || !state.firstSeenBeast || state.observedHuman || state.humanWeight >= 0 ||
        state.sourceRevoked || state.sourceClaimed || !state.link.enabled() || !state.link.captured ||
        state.beastWeight < 0 || state.status != Status::applied || actor->GetRace() != beastRace ||
        !actor->Is3DLoaded() || !actor->Get3D()) return false;
    const auto witness = std::as_const(state.runtimeHandle).get();
    const auto* base = actor->GetActorBase();
    const auto* declared = morphProfiles.defaultFor(state.sex);
    const auto root = reinterpret_cast<std::uintptr_t>(actor->Get3D());
    const float rawWeight = base ? base->weight : std::numeric_limits<float>::quiet_NaN();
    if (!witness || witness.get() != actor || !base || !std::isfinite(rawWeight) || rawWeight < 0 || rawWeight > 100 ||
        (base->GetSex() != RE::SEX::kMale && base->GetSex() != RE::SEX::kFemale) ||
        (base->GetSex() == RE::SEX::kFemale) != (state.sex == claw::Sex::female) ||
        !declared || declared->id != state.link.profile || state.lastRoot != root ||
        (state.defaultRoot && state.defaultRoot != root) || state.link.sourceValues.empty()) return false;
    for (const auto& [name, value] : state.link.sourceValues) {
        (void)value;
        // Name presence protects zero-valued keys too; a sum of zero is not unassigned.
        if (value != 0 || morphs->HasBodyMorphName(skeeReference(actor), name.c_str())) { revokeSourceBootstrap(state); return false; }
    }
    try { captureSources(actor, state.link); }
    catch (const std::exception&) { return false; }
    for (const auto& [name, value] : state.link.sourceValues)
        if (value != 0 || morphs->HasBodyMorphName(skeeReference(actor), name.c_str())) { revokeSourceBootstrap(state); return false; }
    return true;
}

void offerSourceBootstrap(RE::Actor* actor) {
    if (!actor) return;
    const auto found = states.find(actor->GetFormID());
    if (found == states.end() || !boundTo(found->second, actor)) return;
    auto& state = found->second;
    if (pendingActorRequest(actor)) return; // Includes accepted intent before State creation.
    if (!state.adoptedDefault || state.sourceRevoked || state.sourceClaimed) return;
    const auto root = reinterpret_cast<std::uintptr_t>(actor->Get3D());
    if (state.observedHuman || (state.defaultRoot && state.defaultRoot != root)) { revokeSourceBootstrap(state); return; }
    if (state.sourceAdvertised && state.sourceProviderEpoch != obodyProviderEpoch) { revokeSourceBootstrap(state); return; }
    if (!state.defaultRoot && root) state.defaultRoot = root;
    if (!obodySourcePopulationEnabled) return;
    if (!sourceBootstrapLive(actor, state)) {
        if (state.sourceAdvertised) revokeSourceBootstrap(state);
        return;
    }
    if (state.sourceAdvertised) return; // No event retry loop, even without a consumer.
    if (nextSourceBootstrapToken >= 0x01000000U) { revokeSourceBootstrap(state); return; }
    state.sourceAdvertised = true; state.sourceToken = nextSourceBootstrapToken++;
    state.sourceWorld = epoch.load(); state.sourceRuntime = state.runtimeSerial;
    state.sourceProviderEpoch = obodyProviderEpoch.load();
    state.sourceRoot = root; state.sourceSex = state.sex; state.sourceProfile = state.link.profile;
    sourceBootstrapEvent(actor, state, false);
}

void publishPhysics(RE::Actor* actor, PhysicsBinding& binding) {
    if (nextPhysicsSnapshot >= 0x01000000U) { binding.condition = "token-limit"; binding.ready = false; return; }
    binding.snapshot = nextPhysicsSnapshot++; binding.ready = true; binding.delivered = false;
    physicsEvent(actor, "snapshot", binding.snapshot);
}

#if defined(CLAW_PHYSICS_MODEL_HEADER)
void startPhysicsWorker() {
    physicsWorker = std::jthread([](std::stop_token stop) {
        while (!stop.stop_requested()) {
            PhysicsFitWork job;
            {
                std::unique_lock lock(physicsWorkMutex);
                if (!physicsWorkReady.wait(lock, stop, [] { return !physicsWork.empty(); })) return;
                job = std::move(physicsWork.front()); physicsWork.pop_front();
            }
            std::vector<claw::physics::Capsule> capsules;
            std::string error;
            try {
                capsules = claw::physics::Evaluate(claw::physics::CompiledModel(job.female),
                    std::vector<double>(job.values.begin(), job.values.end()), static_cast<double>(job.weight));
            } catch (const std::exception& failure) { error = failure.what(); }
            if (stop.stop_requested()) return;
            tasks->AddTask([job = std::move(job), capsules = std::move(capsules), error = std::move(error)]() mutable {
                std::lock_guard lock(mutex);
                const auto found = physicsBindings.find(job.id);
                if (found == physicsBindings.end() || found->second.registration != job.registration) return;
                auto& binding = found->second; binding.fitPending = false;
                if (!enabled || job.world != epoch || binding.world != job.world || !binding.active ||
                    binding.generation != job.generation || !binding.condition.empty() ||
                    binding.observation.root != job.root || binding.observation.published != job.values ||
                    binding.observation.publishedWeight != job.weight) return;
                const auto witness = std::as_const(binding.actor).get();
                auto* actor = witness.get();
                const auto state = states.find(job.id);
                if (!actor || actor != binding.pointer || !currentOwner(actor) || state == states.end() ||
                    state->second.quarantined || !boundTo(state->second, actor) || state->second.runtimeSerial != binding.runtime ||
                    !actor->Is3DLoaded() || reinterpret_cast<std::uintptr_t>(actor->Get3D()) != job.root || actor->GetRace() != beastRace) return;
                const auto* base = actor->GetActorBase();
                const float rawWeight = base ? base->weight : std::numeric_limits<float>::quiet_NaN();
                if (!base || !std::isfinite(rawWeight) || rawWeight < 0 || rawWeight > 100 ||
                    rawWeight / 100.0F != job.weight) return;
                const auto actualSex = base->GetSex();
                if ((actualSex != RE::SEX::kMale && actualSex != RE::SEX::kFemale) ||
                    (actualSex == RE::SEX::kFemale) != binding.female) return;
                // A writer can change a foreign key while the pure fit runs.
                // Re-read the exact provider aggregate before publishing it.
                for (std::size_t index = 0; index < binding.names.size(); ++index)
                    if (morphs->GetBodyMorphs(skeeReference(actor), binding.names[index].c_str()) != job.values[index]) {
                        binding.observation.invalidate(); binding.ready = false; return;
                    }
                binding.needsFit = false;
                if (!error.empty()) {
                    binding.ready = false; binding.condition = "domain";
                    physicsPopulationBlocked.insert_or_assign(job.id, binding.runtime);
                    SKSE::log::warn("CLAW physics fit: {}", error); physicsEvent(actor, "domain"); return;
                }
                binding.capsules = std::move(capsules); publishPhysics(actor, binding);
            });
        }
    });
}

void queuePhysicsFit(RE::FormID id, PhysicsBinding& binding) {
    if (binding.fitPending || !binding.needsFit || binding.observation.stablePasses < 2 ||
        binding.observation.candidate != binding.observation.published ||
        binding.observation.weight != binding.observation.publishedWeight) return;
    std::lock_guard lock(physicsWorkMutex);
    if (physicsWork.size() >= 16) return; // Bounded; the next main scan retries.
    physicsWork.push_back({id, binding.world, binding.registration, binding.observation.root,
        binding.generation, binding.female, binding.observation.published, binding.observation.publishedWeight});
    binding.fitPending = true;
    physicsWorkReady.notify_one();
}
#endif

void observePhysics(RE::Actor* actor) {
    if (!actor) return;
    const auto found = physicsBindings.find(actor->GetFormID());
    if (found == physicsBindings.end()) return;
    auto& binding = found->second;
    if (!binding.active) return;
    const auto state = states.find(actor->GetFormID());
    const auto witness = std::as_const(binding.actor).get();
    const auto* observedBase = actor->GetActorBase();
    const float rawWeight = observedBase ? observedBase->weight : std::numeric_limits<float>::quiet_NaN();
    if (binding.pointer != actor) {
        binding.ready = false; binding.observation.invalidate();
        if (binding.condition != "identity" && witness && witness.get() == binding.pointer)
            physicsEvent(witness.get(), "identity");
        binding.condition = "identity";
        return;
    }
    auto condition = [&]() -> std::string {
        if (!enabled || binding.world != epoch || !currentOwner(actor) || !witness || witness.get() != actor ||
            binding.pointer != actor || state == states.end() || state->second.quarantined ||
            !boundTo(state->second, actor) || state->second.runtimeSerial != binding.runtime) return "identity";
        if (!beastRace || actor->GetRace() != beastRace) return "human";
        if (!actor->Is3DLoaded() || !actor->Get3D()) return "unloaded";
        if (!morphs) return "provider";
        const auto* base = observedBase;
        if (!base) return "identity";
        if (!std::isfinite(rawWeight) || rawWeight < 0 || rawWeight > 100) return "weight";
        const auto sex = base->GetSex();
        if ((sex != RE::SEX::kMale && sex != RE::SEX::kFemale) || (sex == RE::SEX::kFemale) != binding.female) return "identity";
        return {};
    }();
    const auto root = reinterpret_cast<std::uintptr_t>(actor->Get3D());
    if (condition.empty() && binding.observation.root && binding.observation.root != root) condition = "model";
    if (condition == "model") physicsPopulationBlocked.insert_or_assign(actor->GetFormID(), binding.runtime);
    if (!condition.empty()) {
        if (condition == "weight" || condition == "identity" || condition == "provider")
            physicsPopulationBlocked.insert_or_assign(actor->GetFormID(), binding.runtime);
        binding.ready = false; binding.observation.invalidate();
        binding.observation.root = 0;
        if (binding.condition != condition) binding.delivered = false;
        binding.condition = condition;
        if (!binding.delivered) physicsEvent(actor, condition);
        return;
    }
    if (!binding.condition.empty()) {
        if (binding.condition == "domain" || binding.condition == "weight" || binding.condition == "provider" ||
            binding.condition == "identity" || binding.condition == "token-limit") {
            physicsEvent(actor, binding.condition); return; // Requires fresh explicit qualification.
        }
        if (binding.condition != "waiting") binding.delivered = false;
        binding.condition = "waiting";
        if (!binding.delivered) physicsEvent(actor, "ready");
        return; // Host must renew the exact generation after a lifecycle change.
    }
    std::vector<float> values;
    const float normalizedWeight = rawWeight / 100.0F;
    for (const auto& name : binding.names) values.push_back(morphs->GetBodyMorphs(skeeReference(actor), name.c_str()));
    // Apply the provider's current effective coefficients on this main task.
    // The pinned SKEE implementation joins morph workers and executes partition
    // updates before returning on its main thread. Sample again on a later pass.
    if (binding.observation.candidate != values || binding.observation.weight != normalizedWeight) {
        binding.ready = false;
        physicsEvent(actor, "refit", binding.snapshot); // Old capsules are no longer current geometry.
        morphs->ApplyBodyMorphs(skeeReference(actor), false);
        if (!currentOwner(actor) || actor->GetRace() != beastRace || reinterpret_cast<std::uintptr_t>(actor->Get3D()) != root) {
            invalidatePhysics(actor->GetFormID()); return;
        }
    }
    if (!binding.observation.observe(root, std::move(values), normalizedWeight)) {
        if (!binding.ready) physicsEvent(actor, "refit", binding.snapshot);
#if defined(CLAW_PHYSICS_MODEL_HEADER)
        queuePhysicsFit(actor->GetFormID(), binding);
#endif
        if (binding.ready && !binding.delivered) physicsEvent(actor, "snapshot", binding.snapshot);
        return;
    }
#if defined(CLAW_PHYSICS_MODEL_HEADER)
    binding.ready = false; binding.needsFit = true;
    queuePhysicsFit(actor->GetFormID(), binding);
#else
    publishPhysics(actor, binding);
#endif
}

claw::Morphs ownMorphSnapshot(RE::Actor* actor) {
    struct Visitor final : IBodyMorphInterface::MorphValueVisitor {
        claw::Morphs values;
        std::exception_ptr error;
        void Visit(::TESObjectREFR*, const char* name, const char* key, float value) noexcept override {
            if (error) return;
            try {
                if (!name || !key) throw std::runtime_error("null morph name/key in SKEE snapshot");
                claw::observeOwnMorph(values, name, key, value, claw::morphKey);
            } catch (...) { error = std::current_exception(); }
        }
    } visitor;
    morphs->VisitMorphValues(skeeReference(actor), visitor);
    if (visitor.error) std::rethrow_exception(visitor.error);
    return std::move(visitor.values);
}

void captureSources(RE::Actor* actor, claw::MorphLink& link) {
    const auto previous = ownMorphSnapshot(actor);
    if (const auto conflict = link.sourceConflict(previous); !conflict.empty())
        throw std::runtime_error("human source overlaps an existing CLAW-owned output; clear before rebinding: " + conflict);
    link.capture([actor](std::string_view name) { return morphs->GetBodyMorphs(skeeReference(actor), name.data()); });
}

bool readback(RE::Actor* actor, const claw::Morphs& expected) {
    try { return claw::verifyOwnedMorphs(expected, ownMorphSnapshot(actor), epsilon); }
    catch (const std::exception&) { return false; }
}

bool clearOwn(RE::Actor* actor) {
    // Snapshot first, then mutate only this exact key. Removed/custom names do
    // not depend on whichever matrix or compiled public list is installed now.
    try {
        return claw::clearOwnedMorphs(ownMorphSnapshot(actor), [actor](const std::string& name) {
            morphs->ClearMorph(skeeReference(actor), name.c_str(), claw::morphKey);
        }, [actor] { return ownMorphSnapshot(actor); }, epsilon);
    } catch (const std::exception&) { return false; }
}

void refreshActor(RE::Actor* actor, bool force = false) {
    // Called exclusively from a task. Do not move this into a native/event/timer.
    if (!currentOwner(actor) || !actor->GetActorBase()) return;
    const bool beast = beastRace && actor->GetRace() == beastRace; // current race, never NPC base race
    const auto actorSex = actor->GetActorBase()->GetSex();
    const bool defaultDeclared = (actorSex == RE::SEX::kMale || actorSex == RE::SEX::kFemale) &&
        morphProfiles.defaultFor(actorSex == RE::SEX::kFemale ? claw::Sex::female : claw::Sex::male);
    State* state = stateFor(actor, beast || defaultDeclared);
    if (!state || state->quarantined || !boundTo(*state, actor)) return;
    const auto* weightBase = actor->GetActorBase();
    const float rawNPCWeight = weightBase ? weightBase->weight : std::numeric_limits<float>::quiet_NaN();
    const float observedWeight = std::isfinite(rawNPCWeight) && rawNPCWeight >= 0 && rawNPCWeight <= 100 ? rawNPCWeight / 100.0F : -1.0F;
    if (beast) state->beastWeight = observedWeight;
    else { state->humanWeight = observedWeight; state->observedHuman = true; revokeSourceBootstrap(*state); }
    if (!actor->Is3DLoaded() || !actor->Get3D()) { state->status = Status::unloaded; state->dirty = true; return; }
    if (!morphs) { logError(*state, "SKEE BodyMorph API is unavailable", Status::providerUnavailable); return; }
    // Human coefficients already include the provider's weight interpolation.
    // Re-read during both forms: source deletion/zero must not revive cached values.
    std::string sourceError;
    if (state->link.enabled()) {
        try {
            captureSources(actor, state->link);
            if (state->adoptedDefault && !state->sourceRevoked) for (const auto& [name, value] : state->link.sourceValues) {
                (void)value;
                if (value != 0 || morphs->HasBodyMorphName(skeeReference(actor), name.c_str())) { revokeSourceBootstrap(*state); break; }
            }
        } catch (const std::exception& error) { sourceError = error.what(); }
    }
    const auto root = reinterpret_cast<std::uintptr_t>(actor->Get3D());
    if (!beast || state->suppressed) {
        bool hasOwnValue = false;
        // Zero-valued names can still affect a provider's aggregate policy.
        try { hasOwnValue |= !ownMorphSnapshot(actor).empty(); }
        catch (const std::exception&) { hasOwnValue = true; }
        if (force || state->dirty || hasOwnValue || state->lastRoot != root) {
            if (!clearOwn(actor)) { logError(*state, "own-key cleanup readback failed"); return; }
            morphs->ApplyBodyMorphs(skeeReference(actor), false);
            invalidatePhysics(actor->GetFormID());
        }
        state->status = state->suppressed ? Status::cleared : Status::human;
        state->error.clear(); state->cache.clear(); state->lastRoot = root; state->dirty = false;
        if (!sourceError.empty()) logError(*state, sourceError); // Cleanup already completed.
        return;
    }
    if (!sourceError.empty()) { logError(*state, sourceError); return; }
    const auto sex = actor->GetActorBase()->GetSex();
    if (sex != RE::SEX::kMale && sex != RE::SEX::kFemale) { logError(*state, "actor has no readable NPC sex"); return; }
    const auto desiredSex = sex == RE::SEX::kFemale ? claw::Sex::female : claw::Sex::male;
    if (state->sex != desiredSex) revokeSourceBootstrap(*state);
    const bool linked = state->link.enabled();
    float weight = -1; // Linked mode never reads or interpolates actor weight.
    claw::Morphs expected;
    try {
        expected = claw::resolveMorphs(state->link, desiredSex, [&] {
            if (!catalog.valid()) throw std::runtime_error("CLAW preset catalog is invalid or empty");
            const auto otherSex = desiredSex == claw::Sex::male ? claw::Sex::female : claw::Sex::male;
            // A retained independent choice can predate a sex change in linked mode.
            if (state->preset.empty() || state->sex != desiredSex || catalog.find(state->preset, otherSex)) {
                const auto identity = std::to_string(saveNamespace) + "/" + std::to_string(state->identity);
                const auto* preset = catalog.choose(identity, desiredSex);
                if (!preset) throw std::runtime_error("no presets for this actor's sex");
                state->preset = preset->name; state->sex = desiredSex; state->dirty = true;
            }
            const auto* preset = catalog.find(state->preset, desiredSex);
            if (!preset) throw std::runtime_error("saved preset missing or has wrong family: " + state->preset);
            weight = actor->GetActorBase()->weight;
            return claw::interpolate(*preset, weight);
        });
    }
    catch (const std::exception& error) { logError(*state, error.what()); return; }
    const bool matching = readback(actor, expected);
    if (force || state->dirty || state->lastRoot != root || (!linked && state->lastWeight != weight) || !matching) {
        state->status = Status::pending;
        if (!clearOwn(actor)) { logError(*state, "own-key preparation readback failed"); return; }
        // Recheck race/model immediately before writes; all operations stay on this main-thread task.
        if (!currentOwner(actor) || actor->GetRace() != beastRace || !actor->Is3DLoaded() || !actor->Get3D()) {
            state->dirty = true; state->status = Status::pending; return;
        }
        for (const auto& [name, value] : expected) if (value != 0)
            morphs->SetMorph(skeeReference(actor), name.c_str(), claw::morphKey, value);
        morphs->ApplyBodyMorphs(skeeReference(actor), false);
        invalidatePhysics(actor->GetFormID());
        if (!readback(actor, expected)) { logError(*state, "SKEE own morph readback differs from requested values"); return; }
    }
    state->sex = desiredSex; state->cache = std::move(expected); state->lastRoot = root; state->lastWeight = weight;
    state->dirty = false; state->status = Status::applied; state->error.clear();
}

void scan() {
    std::lock_guard lock(mutex);
    collectPins();
    if (!enabled) return;
    checkRuntimeInstances();
    for (auto it = physicsPopulationBlocked.begin(); it != physicsPopulationBlocked.end();) {
        const auto state = states.find(it->first);
        if (state == states.end() || state->second.runtimeSerial != it->second) it = physicsPopulationBlocked.erase(it);
        else ++it;
    }
    if (!beastRace) {
        if (auto* data = RE::TESDataHandler::GetSingleton())
            beastRace = data->LookupForm<RE::TESRace>(0xCDD84, "Skyrim.esm");
    }
    if (!beastRace) { SKSE::log::error("WerewolfBeastRace unavailable; distribution disabled"); return; }
    std::set<RE::FormID> actors;
    if (auto* player = RE::PlayerCharacter::GetSingleton()) actors.insert(player->GetFormID());
    if (auto* processes = RE::ProcessLists::GetSingleton()) {
        processes->ForEachHighActor([&](auto&& value) {
            auto* actor = highActorPointer(value);
            if (actor && actors.size() < maxActors) actors.insert(actor->GetFormID());
            return RE::BSContainer::ForEachResult::kContinue;
        });
    }
    for (const auto& [id, state] : states) { (void)state; actors.insert(id); }
    for (const auto id : actors) {
        auto* actor = RE::TESForm::LookupByID<RE::Actor>(id);
        refreshActor(actor);
        observePhysics(actor);
        offerSourceBootstrap(actor);
    }
    if (physicsPopulationEnabled) {
        unsigned emitted{};
        for (const auto& [id, state] : states) {
            if (emitted >= 16) break;
            if (!state.runtimeSerial || state.quarantined || physicsBindings.contains(id)) continue;
            const auto blocked = physicsPopulationBlocked.find(id);
            if (blocked != physicsPopulationBlocked.end() && blocked->second == state.runtimeSerial) continue;
            const auto witness = std::as_const(state.runtimeHandle).get();
            auto* actor = witness.get();
            if (!actor || actor != state.runtimePointer || !currentOwner(actor) || actor->GetRace() != beastRace ||
                !actor->Is3DLoaded() || !actor->Get3D()) continue;
            if (auto* source = SKSE::GetModCallbackEventSource()) {
                SKSE::ModCallbackEvent event;
                event.eventName = "CLAWPhysics_Candidate"; event.strArg = "known-loaded-beast";
                event.numArg = 0; event.sender = actor; source->SendEvent(&event); ++emitted;
            }
        }
    }
    collectPins();
}

void queueScan() {
    if (!tasks || !enabled || scanPending.exchange(true)) return;
    const auto token = epoch.load();
    tasks->AddTask([token] {
        if (enabled && token == epoch) scan();
        scanPending = false;
    });
}

void queueActor(RE::FormID id, bool force = false) {
    if (!id || !tasks) return;
    const auto token = epoch.load();
    tasks->AddTask([id, force, token] {
        if (!enabled || token != epoch) return;
        std::lock_guard lock(mutex);
        // Events carrying only an ID are rescan hints, never actor-specific intent.
        refreshActor(RE::TESForm::LookupByID<RE::Actor>(id), force);
        if (force) invalidatePhysics(id);
        observePhysics(RE::TESForm::LookupByID<RE::Actor>(id));
        offerSourceBootstrap(RE::TESForm::LookupByID<RE::Actor>(id));
    });
}

class Events final : public RE::BSTEventSink<RE::TESObjectLoadedEvent>,
                     public RE::BSTEventSink<RE::TESSwitchRaceCompleteEvent>,
                     public RE::BSTEventSink<SKSE::NiNodeUpdateEvent>,
                     public RE::BSTEventSink<SKSE::ModCallbackEvent> {
public:
    RE::BSEventNotifyControl ProcessEvent(const RE::TESObjectLoadedEvent* event, RE::BSTEventSource<RE::TESObjectLoadedEvent>*) override {
        if (event) queueActor(event->formID, true);
        return RE::BSEventNotifyControl::kContinue;
    }
    RE::BSEventNotifyControl ProcessEvent(const RE::TESSwitchRaceCompleteEvent* event, RE::BSTEventSource<RE::TESSwitchRaceCompleteEvent>*) override {
        if (event && event->subject) queueActor(event->subject->formID, true);
        return RE::BSEventNotifyControl::kContinue;
    }
    RE::BSEventNotifyControl ProcessEvent(const SKSE::NiNodeUpdateEvent* event, RE::BSTEventSource<SKSE::NiNodeUpdateEvent>*) override {
        // A node notification caused by our own update must not create an
        // update->notification->update loop. Root changes/readback still refresh.
        if (event && event->reference) queueActor(event->reference->formID);
        return RE::BSEventNotifyControl::kContinue;
    }
    RE::BSEventNotifyControl ProcessEvent(const SKSE::ModCallbackEvent* event, RE::BSTEventSource<SKSE::ModCallbackEvent>*) override {
        if (event && event->sender && event->eventName == "Obody_ApplyMorph") queueActor(event->sender->formID, true);
        return RE::BSEventNotifyControl::kContinue;
    }
} events;

// Versioned little-endian records, no serialized compiler padding or pointers.
using Bytes = std::vector<std::uint8_t>;
void u32(Bytes& out, std::uint32_t value) { for (int shift = 0; shift < 32; shift += 8) out.push_back(static_cast<std::uint8_t>(value >> shift)); }
void u64(Bytes& out, std::uint64_t value) { u32(out, static_cast<std::uint32_t>(value)); u32(out, static_cast<std::uint32_t>(value >> 32)); }
void string(Bytes& out, const std::string& value) { u32(out, static_cast<std::uint32_t>(value.size())); out.insert(out.end(), value.begin(), value.end()); }
struct Reader {
    const Bytes& data; std::size_t offset{};
    std::uint32_t u32() {
        if (data.size() - offset < 4) throw std::runtime_error("truncated serialized integer");
        std::uint32_t value{};
        for (int shift = 0; shift < 32; shift += 8) value |= static_cast<std::uint32_t>(data[offset++]) << shift;
        return value;
    }
    std::uint64_t u64() { const auto low = u32(); return low | (static_cast<std::uint64_t>(u32()) << 32); }
    std::string string() {
        const auto length = u32();
        if (length > 160 || length > data.size() - offset) throw std::runtime_error("invalid serialized string length");
        std::string result(data.begin() + offset, data.begin() + offset + length); offset += length; return result;
    }
};

void save(SKSE::SerializationInterface* interface) {
    std::lock_guard lock(mutex);
    Bytes session; u64(session, saveNamespace); u64(session, nextIdentity);
    if (!interface->WriteRecord(sessionRecord, 1, session.data(), static_cast<std::uint32_t>(session.size()))) SKSE::log::error("Session serialization failed");
    for (const auto& [id, state] : states) {
        auto savedLink = state.link;
        std::string normalizationError;
        if (!savedLink.canonicalize(state.sex, &normalizationError)) {
            SKSE::log::error("CLAW actor {:08X} cannot save invalid morph link: {}", id, normalizationError);
            continue;
        }
        // Zero is already an unavailable VM identity in record v1. Preserve hard
        // quarantine across saves without inventing a new persistence format.
        Bytes row; u32(row, id); u64(row, state.identity); u64(row, state.quarantined ? 0 : state.vmHandle); string(row, state.preset);
        u32(row, static_cast<std::uint32_t>(state.sex)); u32(row, state.suppressed ? 1 : 0);
        u32(row, static_cast<std::uint32_t>(state.cache.size()));
        for (const auto& [name, value] : state.cache) {
            string(row, name); std::uint32_t bits; std::memcpy(&bits, &value, sizeof(bits)); u32(row, bits);
        }
        string(row, savedLink.profile); u32(row, static_cast<std::uint32_t>(savedLink.rules.size()));
        for (const auto& rule : savedLink.rules) {
            claw::writeMorphRule(rule, [&](const auto& value) { string(row, value); }, [&](auto value) { u32(row, value); });
        }
        u32(row, savedLink.captured ? 1 : 0); u32(row, static_cast<std::uint32_t>(savedLink.sourceValues.size()));
        for (const auto& [name, value] : savedLink.sourceValues) {
            string(row, name); std::uint32_t bits; std::memcpy(&bits, &value, sizeof(bits)); u32(row, bits);
        }
        for (const float weight : {state.humanWeight, state.beastWeight}) {
            std::uint32_t bits; std::memcpy(&bits, &weight, sizeof(bits)); u32(row, bits);
        }
        if (!interface->WriteRecord(actorRecord, 5, row.data(), static_cast<std::uint32_t>(row.size()))) SKSE::log::error("Actor {:08X} serialization failed", id);
    }
}

void revert(SKSE::SerializationInterface*) {
    enabled = false; ++epoch;
    {
        std::lock_guard lock(mutex);
        states.clear(); requests.clear(); physicsBindings.clear(); physicsRegistrationRequests.clear(); saveNamespace = 0; nextIdentity = 1;
        physicsPopulationEnabled = false; physicsPopulationBlocked.clear();
        obodySourcePopulationEnabled = false;
    }
    queuePinCollection(); // Never release the last intrusive pin on a VM callback.
}

void load(SKSE::SerializationInterface* interface) {
    enabled = false; ++epoch;
    std::lock_guard lock(mutex);
    states.clear(); requests.clear(); physicsBindings.clear(); physicsRegistrationRequests.clear(); saveNamespace = 0; nextIdentity = 1;
    physicsPopulationEnabled = false; physicsPopulationBlocked.clear();
    obodySourcePopulationEnabled = false;
    std::uint32_t type{}, version{}, length{};
    bool sessionFound = false;
    std::set<std::uint64_t> identities;
    while (interface->GetNextRecordInfo(type, version, length)) {
        if (type != sessionRecord && type != actorRecord) continue;
        if ((version != 1 && !(type == actorRecord && (version >= 2 && version <= 5))) ||
            length > (type == actorRecord && version >= 3 ? 131072U : 16384U)) { SKSE::log::error("Unsupported/corrupt CLAW record"); continue; }
        Bytes bytes(length);
        if (interface->ReadRecordData(bytes.data(), length) != length) { SKSE::log::error("Truncated CLAW record"); continue; }
        try {
            Reader reader{bytes};
            if (type == sessionRecord) {
                if (sessionFound) throw std::runtime_error("duplicate session record");
                const auto loadedNamespace = reader.u64(), loadedNext = reader.u64();
                if (!loadedNamespace || !loadedNext || loadedNext == std::numeric_limits<std::uint64_t>::max() || reader.offset != bytes.size())
                    throw std::runtime_error("invalid session record");
                saveNamespace = loadedNamespace; nextIdentity = loadedNext; sessionFound = true;
                continue;
            }
            const auto oldID = reader.u32(); State state; state.identity = reader.u64();
            const auto oldHandle = reader.u64(); state.preset = reader.string();
            const auto sex = reader.u32(), suppressed = reader.u32(), count = reader.u32();
            if (sex > 1 || suppressed > 1 || count > claw::maxLinkedCacheMorphs || !state.identity || state.identity == std::numeric_limits<std::uint64_t>::max() || !identities.insert(state.identity).second)
                throw std::runtime_error("invalid actor identity/family/cache");
            state.sex = static_cast<claw::Sex>(sex); state.suppressed = suppressed != 0;
            for (std::uint32_t index = 0; index < count; ++index) {
                const auto name = reader.string(); const auto bits = reader.u32(); float value; std::memcpy(&value, &bits, sizeof(value));
                if (!claw::morphNameIdentifier(name) || !std::isfinite(value) || value < 0 || value > 1 || !state.cache.emplace(name, value).second)
                    throw std::runtime_error("invalid serialized morph");
            }
            if (version >= 2) {
                state.link.profile = reader.string(); const auto ruleCount = reader.u32();
                const std::uint32_t maxLinkEntries = version >= 3 ? 128U : 32U;
                if (ruleCount > maxLinkEntries) throw std::runtime_error("excessive morph link rules");
                for (std::uint32_t index = 0; index < ruleCount; ++index) {
                    state.link.rules.push_back(claw::readMorphRule(reader, version));
                }
                const auto captured = reader.u32(), sourceCount = reader.u32();
                if (captured > 1 || sourceCount > maxLinkEntries) throw std::runtime_error("invalid morph source snapshot");
                state.link.captured = captured != 0;
                for (std::uint32_t index = 0; index < sourceCount; ++index) {
                    const auto name = reader.string(); const auto bits = reader.u32(); float value; std::memcpy(&value, &bits, sizeof(value));
                    if (!state.link.sourceValues.emplace(name, value).second) throw std::runtime_error("duplicate linked source");
                }
                std::string reason;
                if (!state.link.canonicalize(state.sex, &reason)) throw std::runtime_error("invalid saved morph link profile: " + reason);
            } // Old v1 state remains independent; a preset name never opts into linkage.
            if (!claw::validMorphCache(state.cache, state.sex, state.link.enabled()))
                throw std::runtime_error("invalid saved linked/independent morph cache");
            if (version >= 4) {
                for (float* weight : {&state.humanWeight, &state.beastWeight}) {
                    const auto bits = reader.u32(); std::memcpy(weight, &bits, sizeof(bits));
                    if (!std::isfinite(*weight) || (*weight != -1 && (*weight < 0 || *weight > 1)))
                        throw std::runtime_error("invalid saved NPC weight observation");
                }
            }
            if (reader.offset != bytes.size()) throw std::runtime_error("trailing serialized actor bytes");
            RE::FormID id{};
            if (interface->ResolveFormID(oldID, id)) {
                if (!id || states.contains(id) || states.size() >= maxActors) throw std::runtime_error("duplicate/excessive actor record");
                if (!oldHandle || !interface->ResolveHandle(oldHandle, state.vmHandle) || !state.vmHandle) {
                    state.quarantined = true;
                    logError(state, "saved VM deletion identity cannot be resolved; assignment quarantined");
                }
                states.emplace(id, std::move(state));
            }
        } catch (const std::exception& error) { SKSE::log::error("CLAW co-save: {}", error.what()); }
    }
    if (!sessionFound) { states.clear(); saveNamespace = newNamespace(); nextIdentity = 1; }
    for (const auto& [id, state] : states) { (void)id; nextIdentity = std::max(nextIdentity, state.identity + 1); }
}

void deleted(RE::VMHandle handle) {
    if (!handle || !tasks) return;
    struct Receipt { RE::FormID id; std::uint64_t identity, runtime, requestOwner; RE::ActorHandle witness; RE::Actor* pointer; };
    std::vector<Receipt> receipts;
    {
        std::lock_guard lock(mutex);
        for (auto& [id, state] : states) {
            if (state.vmHandle != handle) continue;
            if (!state.runtimeSerial) {
                quarantine(state, "deletion receipt for unbound saved identity; assignment quarantined");
            } else {
                const auto pin = pins.find(state.runtimePointer);
                receipts.push_back({id, state.identity, state.runtimeSerial,
                    pin == pins.end() ? 0 : pin->second->serial, state.runtimeHandle, state.runtimePointer});
            }
        }
    }
    const auto token = epoch.load();
    for (const auto& receipt : receipts) tasks->AddTask([receipt, token] {
        if (token != epoch) return;
        std::lock_guard lock(mutex);
        const auto found = states.find(receipt.id);
        if (found == states.end() || found->second.identity != receipt.identity ||
            found->second.runtimeSerial != receipt.runtime || found->second.runtimePointer != receipt.pointer) return;
        const auto actor = receipt.witness.get();
        // VM handle format/order is not assumed unique across reuse. A late old
        // receipt cannot retire a live current actor just sharing that VM handle.
        if (actor && actor.get() != receipt.pointer) {
            quarantine(found->second, "deletion runtime witness changed; saved assignment quarantined"); return;
        }
        if (actor && !actor->IsDeleted() && RE::TESForm::LookupByID<RE::Actor>(receipt.id) == actor.get()) return;
        if (receipt.requestOwner) requests.eraseOwner(receipt.id, receipt.requestOwner);
        states.erase(found);
    });
    if (!receipts.empty()) queuePinCollection();
}

enum class Operation { assign, clear, refresh, configureMorphLink, disableMorphLink };
bool actorRequest(RE::Actor* actor, Operation operation, std::string presetName = {}, claw::MorphLink link = {}, std::optional<claw::Sex> requiredSex = {}) {
    if (!actor || !tasks || !enabled) return false;
    const auto id = actor->formID;
    Pin owner;
    std::optional<claw::RequestToken> ticket;
    {
        std::lock_guard lock(mutex);
        if (!enabled) return false;
        if (operation == Operation::assign && !catalog.find(presetName, claw::Sex::male) && !catalog.find(presetName, claw::Sex::female)) return false;
        owner = pinActor(actor);
        if (!owner) return false;
        ticket = requests.begin(id, epoch.load(), owner->serial, owner);
        if (!ticket) return false;
        if (auto found = states.find(id); found != states.end() && boundTo(found->second, actor)) {
            if (operation != Operation::refresh) {
                revokeSourceBootstrap(found->second); found->second.adoptedDefault = false;
            }
            found->second.status = Status::pending;
            found->second.latestRequest = {*ticket, found->second.runtimeSerial};
        }
    }
    // The pool keeps an intrusive pin even if this task is disposed before the
    // native callback's final shared_ptr copy dies. Only task collection erases it.
    tasks->AddTask([id, owner = std::move(owner), ticket = *ticket, operation, presetName = std::move(presetName), link = std::move(link), requiredSex]() mutable {
        std::lock_guard lock(mutex);
        if (!enabled || !requests.owns(id, ticket, epoch.load())) return;
        auto fail = [&](std::string error) { requests.finish(id, ticket, epoch.load(), std::move(error)); };
        auto* target = owner->actor.get();
        if (!claw::mayRunActorRequest(target, RE::TESForm::LookupByID<RE::Actor>(id), target->formID == id, target->IsDeleted()) ||
            !target->GetActorBase()) { fail("original actor reference is deleted or no longer owns its FormID"); return; }
        auto* state = stateFor(target, true, false); // Explicit manual policy never adopts a population default.
        if (!state) { fail("actor identity unavailable or reference/pin state limit reached"); return; }
        if (state->quarantined || !boundTo(*state, target)) { fail("actor assignment identity is quarantined"); return; }
        if (operation != Operation::refresh) {
            // A queued scan can create/adopt State after the native callback
            // accepted this request but before this task gets its turn.
            revokeSourceBootstrap(*state); state->adoptedDefault = false;
        }
        state->latestRequest = {ticket, state->runtimeSerial};
        if (operation == Operation::assign) {
            const auto sex = target->GetActorBase()->GetSex() == RE::SEX::kFemale ? claw::Sex::female : claw::Sex::male;
            if (!beastRace || target->GetRace() != beastRace) { fail("AssignPreset requires the current WerewolfBeastRace"); return; }
            if (!catalog.find(presetName, sex)) { fail("preset family does not match actor sex"); return; }
            state->preset = presetName; state->sex = sex; state->suppressed = false; state->link = {};
        } else if (operation == Operation::configureMorphLink) {
            const auto actorSex = target->GetActorBase()->GetSex();
            if (actorSex != RE::SEX::kMale && actorSex != RE::SEX::kFemale) { fail("actor has no readable NPC sex"); return; }
            const auto sex = target->GetActorBase()->GetSex() == RE::SEX::kFemale ? claw::Sex::female : claw::Sex::male;
            if (requiredSex && *requiredSex != sex) { fail("morph family does not match the actor's readable NPC sex"); return; }
            std::string reason;
            if (!link.canonicalize(sex, &reason)) { fail("invalid morph-to-morph profile: " + reason); return; }
            if (!morphs) { fail("SKEE BodyMorph API is unavailable; previous link retained"); return; }
            try { captureSources(target, link); }
            catch (const std::exception& error) { fail(error.what()); return; }
            state->link = link; state->suppressed = false; // Explicit opt-in resumes this policy.
        } else if (operation == Operation::disableMorphLink) state->link = {};
        else if (operation == Operation::clear) state->suppressed = true;
        state->dirty = true;
        refreshActor(target, true); // Use the pinned object, never a second ID lookup.
        requests.finish(id, ticket, epoch.load());
    });
    return true;
}

std::vector<RE::BSFixedString> presetNames(RE::StaticFunctionTag*, bool female) {
    std::lock_guard lock(mutex); std::vector<RE::BSFixedString> result;
    for (const auto& name : catalog.names(female ? claw::Sex::female : claw::Sex::male)) result.emplace_back(name);
    return result;
}

bool assignPreset(RE::StaticFunctionTag*, RE::Actor* actor, RE::BSFixedString name) {
    return actorRequest(actor, Operation::assign, name.c_str());
}

const State* cachedState(RE::Actor* actor) {
    if (!enabled || !actor) return nullptr;
    const auto found = states.find(actor->formID);
    return found != states.end() && boundTo(found->second, actor) ? &found->second : nullptr;
}
RE::BSFixedString assigned(RE::StaticFunctionTag*, RE::Actor* actor) {
    std::lock_guard lock(mutex);
    const auto* state = cachedState(actor);
    return state && !state->quarantined && !state->link.enabled() ? RE::BSFixedString(state->preset) : RE::BSFixedString{};
}
std::int32_t getStatus(RE::StaticFunctionTag*, RE::Actor* actor) {
    std::lock_guard lock(mutex);
    if (enabled) if (const auto* request = actorRequest(actor))
        return static_cast<std::int32_t>(request->error.empty() ? Status::pending : Status::error);
    const auto* state = cachedState(actor);
    return static_cast<std::int32_t>(state ? state->status : Status::unknown);
}
RE::BSFixedString lastError(RE::StaticFunctionTag*, RE::Actor* actor) {
    std::lock_guard lock(mutex);
    if (enabled) if (const auto* request = actorRequest(actor)) return RE::BSFixedString(request->error);
    const auto* state = cachedState(actor);
    return state ? RE::BSFixedString(state->error) : RE::BSFixedString{};
}
float ownMorph(RE::StaticFunctionTag*, RE::Actor* actor, RE::BSFixedString name) {
    std::lock_guard lock(mutex);
    const auto* state = cachedState(actor);
    if (actorRequest(actor) || !state || state->quarantined || state->status != Status::applied) return 0;
    const auto value = state->cache.find(name.c_str());
    return value == state->cache.end() ? 0 : value->second;
}
float humanWeight(RE::StaticFunctionTag*, RE::Actor* actor) {
    std::lock_guard lock(mutex); const auto* state = cachedState(actor);
    return state && !state->quarantined ? state->humanWeight : -1.0F;
}
float beastWeight(RE::StaticFunctionTag*, RE::Actor* actor) {
    std::lock_guard lock(mutex); const auto* state = cachedState(actor);
    return state && !state->quarantined ? state->beastWeight : -1.0F;
}
bool clearRequest(RE::StaticFunctionTag*, RE::Actor* actor) { return actorRequest(actor, Operation::clear); }
bool refreshRequest(RE::StaticFunctionTag*, RE::Actor* actor) { return actorRequest(actor, Operation::refresh); }
bool configureMorphLink(RE::StaticFunctionTag*, RE::Actor* actor, RE::BSFixedString profile,
    std::vector<RE::BSFixedString> sources, std::vector<RE::BSFixedString> targets, std::vector<float> gains, std::vector<float> caps) {
    if (sources.size() > 128 || targets.size() != sources.size() || gains.size() != sources.size() || caps.size() != sources.size()) return false;
    claw::MorphLink link; link.profile = profile.c_str();
    if (!claw::morphLinkIdentifier(link.profile)) return false;
    for (std::size_t index = 0; index < sources.size(); ++index)
        link.rules.push_back({sources[index].c_str(), targets[index].c_str(), gains[index], caps[index]});
    if (!link.canonicalize(claw::Sex::male)) return false;
    return actorRequest(actor, Operation::configureMorphLink, {}, std::move(link));
}
bool disableMorphLink(RE::StaticFunctionTag*, RE::Actor* actor) { return actorRequest(actor, Operation::disableMorphLink); }
bool configureMorphFamily(RE::StaticFunctionTag*, RE::Actor* actor, RE::BSFixedString profileID) {
    std::lock_guard lock(mutex);
    const auto* profile = morphProfiles.find(profileID.c_str(), claw::Sex::male);
    if (!profile) profile = morphProfiles.find(profileID.c_str(), claw::Sex::female);
    if (!profile) return false;
    return actorRequest(actor, Operation::configureMorphLink, {}, profile->link, profile->sex);
}
std::vector<RE::BSFixedString> morphFamilies(RE::StaticFunctionTag*, bool female) {
    std::lock_guard lock(mutex); std::vector<RE::BSFixedString> result;
    for (const auto& name : morphProfiles.names(female ? claw::Sex::female : claw::Sex::male)) result.emplace_back(name);
    return result;
}

State* sourceCandidateCached(RE::Actor* actor, std::int32_t token, bool ready) {
    if (!actor || token <= 0 || !enabled || !obodySourcePopulationEnabled || !morphs || !sourceProviderReady()) return nullptr;
    const auto found = states.find(actor->formID);
    if (found == states.end()) return nullptr;
    auto& state = found->second;
    return sourcePolicyAllows(state, actor) && boundTo(state, actor) && !state.quarantined && !state.suppressed && state.adoptedDefault && state.firstSeenBeast &&
        !state.observedHuman && state.humanWeight < 0 && !state.sourceRevoked && !state.sourceClaimed && state.sourceAdvertised &&
        state.sourceToken == static_cast<std::uint32_t>(token) && state.sourceWorld == epoch &&
        state.sourceProviderEpoch == obodyProviderEpoch &&
        state.sourceRuntime == state.runtimeSerial && state.sourceSex == state.sex && state.sourceProfile == state.link.profile &&
        state.sourceRoot == state.lastRoot && state.status == Status::applied && (!ready || state.sourceReady) ? &state : nullptr;
}

bool enableOBodySourcePopulation(RE::StaticFunctionTag*, bool optIn) {
    std::lock_guard lock(mutex);
    if (optIn && (!enabled || !tasks || !morphs || !sourceProviderReady() ||
        !morphProfiles.valid() || (!morphProfiles.defaultFor(claw::Sex::male) && !morphProfiles.defaultFor(claw::Sex::female)))) return false;
    obodySourcePopulationEnabled = optIn;
    if (!optIn) for (auto& [id, state] : states) { (void)id; if (state.sourceAdvertised) revokeSourceBootstrap(state); }
    return true;
}

std::int32_t oBodySourceStatus(RE::StaticFunctionTag*) {
#if defined(CLAW_OBODY_API_HEADER)
    if (!obodyApiAvailable) return 0;
    if (!enabled || !obodyApiReady) return 1;
    if (!sourceProviderReady()) return 2;
    std::lock_guard lock(mutex);
    return obodySourcePopulationEnabled ? 4 : 3;
#else
    return 0;
#endif
}

bool requestSourceBootstrap(RE::StaticFunctionTag*, RE::Actor* actor, std::int32_t token) {
    std::lock_guard lock(mutex);
    auto* state = sourceCandidateCached(actor, token, false);
    if (!state || !tasks || state->sourceValidationPending || state->sourceReady) return false;
    auto owner = pinActor(actor);
    if (!owner) return false;
    state->sourceValidationPending = true;
    const auto world = epoch.load();
    const auto runtime = state->runtimeSerial;
    tasks->AddTask([owner = std::move(owner), token, world, runtime] {
        std::lock_guard lock(mutex);
        auto* actor = owner->actor.get();
        if (world != epoch) return;
        auto* state = sourceCandidateCached(actor, token, false);
        if (!state || state->runtimeSerial != runtime || !state->sourceValidationPending) return;
        state->sourceValidationPending = false;
        if (!sourceBootstrapLive(actor, *state) || reinterpret_cast<std::uintptr_t>(actor->Get3D()) != state->sourceRoot) {
            revokeSourceBootstrap(*state); return;
        }
        state->sourceReady = true;
        sourceBootstrapEvent(actor, *state, true);
    });
    return true;
}

bool claimSourceBootstrap(RE::StaticFunctionTag*, RE::Actor* actor, std::int32_t token) {
    std::lock_guard lock(mutex);
    auto* state = sourceCandidateCached(actor, token, true);
    if (!state) return false;
    state->sourceClaimed = true; state->sourceReady = false; // One atomic lease claim, never an OBody/SKEE transaction.
    return true;
}

bool physicsRegister(RE::StaticFunctionTag*, RE::Actor* actor, std::int32_t generation,
    std::vector<RE::BSFixedString> names, RE::BSFixedString model, RE::BSFixedString evidence) {
    if (!actor || generation < 0 || !tasks || !enabled || !model.c_str()[0] || !evidence.c_str()[0] ||
        std::strlen(model.c_str()) > 160 || std::strlen(evidence.c_str()) > 1024) return false;
    std::vector<std::string> ordered;
    for (const auto& name : names) ordered.emplace_back(name.c_str());
    if (!claw::validPhysicsNames(ordered)) return false;
    std::lock_guard lock(mutex);
    auto pin = pinActor(actor);
    if (!pin || nextPhysicsRegistration == std::numeric_limits<std::uint64_t>::max()) return false;
    const auto request = nextPhysicsRegistration++;
    physicsRegistrationRequests.insert_or_assign(actor, request);
    const auto token = epoch.load();
    tasks->AddTask([pin = std::move(pin), generation, ordered = std::move(ordered),
        model = std::string(model.c_str()), evidence = std::string(evidence.c_str()), token, request] {
        std::lock_guard lock(mutex);
        auto* target = pin->actor.get();
        const auto pending = physicsRegistrationRequests.find(target);
        if (pending == physicsRegistrationRequests.end() || pending->second != request) return;
        physicsRegistrationRequests.erase(pending);
        if (!enabled || token != epoch || !currentOwner(target) || !target->GetActorBase()) return;
        auto* state = stateFor(target, true);
        if (!state || state->quarantined || !boundTo(*state, target)) return;
        if (!physicsBindings.contains(target->GetFormID()) && physicsBindings.size() >= 16) return;
        const auto sex = target->GetActorBase()->GetSex();
        if (sex != RE::SEX::kMale && sex != RE::SEX::kFemale) return;
#if defined(CLAW_PHYSICS_MODEL_HEADER)
        const auto& compiled = claw::physics::CompiledModel(sex == RE::SEX::kFemale);
        if (compiled.identity != model || compiled.morphs != ordered) {
            SKSE::log::warn("CLAW physics host/model identity or ordered morph names differ from compiled fit"); return;
        }
#endif
        PhysicsBinding binding;
        binding.actor = target->GetHandle(); binding.pointer = target;
        binding.runtime = state->runtimeSerial; binding.world = token; binding.registration = request; binding.generation = generation;
        binding.names = ordered; binding.model = model; binding.evidence = evidence;
        binding.female = sex == RE::SEX::kFemale;
        physicsBindings.insert_or_assign(target->GetFormID(), std::move(binding));
        observePhysics(target);
    });
    return true;
}

bool physicsSetPopulation(RE::StaticFunctionTag*, bool optIn) {
    std::lock_guard lock(mutex);
    if (optIn && !enabled) return false;
    physicsPopulationEnabled = optIn;
    if (optIn) physicsPopulationBlocked.clear(); // Fresh explicit current-session qualification.
    return true;
}

void physicsUnregister(RE::StaticFunctionTag*, RE::Actor* actor, bool retainForCleanup) {
    if (!actor) return;
    std::lock_guard lock(mutex);
    physicsRegistrationRequests.erase(actor);
    const auto found = physicsBindings.find(actor->formID);
    if (found != physicsBindings.end() && found->second.pointer == actor) {
        if (retainForCleanup) { found->second.active = false; found->second.ready = false; }
        else physicsBindings.erase(found);
    }
}

bool physicsActorCurrent(RE::StaticFunctionTag*, RE::Actor* actor) {
    if (!actor || !enabled) return false;
    std::lock_guard lock(mutex);
    const auto found = physicsBindings.find(actor->formID);
    const auto state = states.find(actor->formID);
    return found != physicsBindings.end() && found->second.pointer == actor && found->second.world == epoch &&
        found->second.condition != "identity" && found->second.condition != "provider" && state != states.end() &&
        !state->second.quarantined && boundTo(state->second, actor) && state->second.runtimeSerial == found->second.runtime;
}

const PhysicsBinding* physicsSnapshot(RE::Actor* actor, std::int32_t generation, std::int32_t snapshot) {
    if (!enabled || !actor || snapshot <= 0) return nullptr;
    const auto found = physicsBindings.find(actor->formID);
    if (found == physicsBindings.end()) return nullptr;
    const auto& binding = found->second;
    const auto state = states.find(actor->formID);
    return binding.pointer == actor && binding.world == epoch && binding.ready && binding.generation == generation &&
        binding.snapshot == static_cast<std::uint32_t>(snapshot) && state != states.end() && !state->second.quarantined &&
        boundTo(state->second, actor) && state->second.runtimeSerial == binding.runtime ? &binding : nullptr;
}

bool physicsSnapshotCurrent(RE::StaticFunctionTag*, RE::Actor* actor, std::int32_t generation, std::int32_t snapshot) {
    std::lock_guard lock(mutex); return physicsSnapshot(actor, generation, snapshot) != nullptr;
}
bool physicsRefitPending(RE::StaticFunctionTag*, RE::Actor* actor, std::int32_t generation, std::int32_t previousSnapshot) {
    if (!actor || !enabled || previousSnapshot < 0) return false;
    std::lock_guard lock(mutex);
    const auto found = physicsBindings.find(actor->formID);
    return found != physicsBindings.end() && found->second.pointer == actor && found->second.world == epoch &&
        found->second.active && !found->second.ready && found->second.generation == generation &&
        found->second.snapshot == static_cast<std::uint32_t>(previousSnapshot) && found->second.condition.empty();
}
void physicsAcknowledge(RE::StaticFunctionTag*, RE::Actor* actor, std::int32_t generation, std::int32_t snapshot) {
    std::lock_guard lock(mutex);
    if (physicsSnapshot(actor, generation, snapshot)) physicsBindings.at(actor->formID).delivered = true;
}
void physicsAcknowledgeLifecycle(RE::StaticFunctionTag*, RE::Actor* actor, RE::BSFixedString condition) {
    if (!actor) return;
    std::lock_guard lock(mutex);
    const auto found = physicsBindings.find(actor->formID);
    if (found != physicsBindings.end() && found->second.pointer == actor && found->second.world == epoch &&
        found->second.condition == condition.c_str()) found->second.delivered = true;
}
std::vector<float> physicsValues(RE::StaticFunctionTag*, RE::Actor* actor, std::int32_t generation, std::int32_t snapshot) {
    std::lock_guard lock(mutex);
    const auto* binding = physicsSnapshot(actor, generation, snapshot);
    return binding ? binding->observation.published : std::vector<float>{};
}
float physicsWeight(RE::StaticFunctionTag*, RE::Actor* actor, std::int32_t generation, std::int32_t snapshot) {
    std::lock_guard lock(mutex);
    const auto* binding = physicsSnapshot(actor, generation, snapshot);
    return binding ? binding->observation.publishedWeight : -1.0F;
}
std::vector<float> physicsCapsule(RE::StaticFunctionTag*, RE::Actor* actor, std::int32_t generation, std::int32_t snapshot, std::int32_t slot) {
    std::lock_guard lock(mutex);
    const auto* binding = physicsSnapshot(actor, generation, snapshot);
#if defined(CLAW_PHYSICS_MODEL_HEADER)
    if (binding && slot >= 0 && static_cast<std::size_t>(slot) < binding->capsules.size() &&
        claw::physics::CompiledModel(binding->female).slots[slot].active) {
        const auto& cap = binding->capsules[slot];
        return {static_cast<float>(cap.p1[0]), static_cast<float>(cap.p1[1]), static_cast<float>(cap.p1[2]),
            static_cast<float>(cap.p2[0]), static_cast<float>(cap.p2[1]), static_cast<float>(cap.p2[2]), static_cast<float>(cap.radius)};
    }
#else
    (void)binding; (void)slot;
#endif
    return {};
}
RE::BSFixedString physicsModel(RE::StaticFunctionTag*) {
#if defined(CLAW_PHYSICS_MODEL_HEADER)
    return RE::BSFixedString(claw::physics::CompiledModel(false).identity);
#else
    return {};
#endif
}

bool registerPapyrus(RE::BSScript::IVirtualMachine* vm) {
    constexpr auto script = "CLAWDistributionNative";
    vm->RegisterFunction("GetPresetNames", script, presetNames);
    vm->RegisterFunction("AssignPreset", script, assignPreset);
    vm->RegisterFunction("GetAssigned", script, assigned);
    vm->RegisterFunction("GetStatus", script, getStatus);
    vm->RegisterFunction("GetLastError", script, lastError);
    vm->RegisterFunction("GetOwnMorph", script, ownMorph);
    vm->RegisterFunction("GetHumanWeight", script, humanWeight);
    vm->RegisterFunction("GetBeastWeight", script, beastWeight);
    vm->RegisterFunction("ClearOwn", script, clearRequest);
    vm->RegisterFunction("Refresh", script, refreshRequest);
    vm->RegisterFunction("ConfigureMorphLink", script, configureMorphLink);
    vm->RegisterFunction("DisableMorphLink", script, disableMorphLink);
    vm->RegisterFunction("ConfigureMorphFamily", script, configureMorphFamily);
    vm->RegisterFunction("GetMorphFamilies", script, morphFamilies);
    vm->RegisterFunction("EnableOBodySourcePopulation", script, enableOBodySourcePopulation);
    vm->RegisterFunction("GetOBodySourceStatus", script, oBodySourceStatus);
    vm->RegisterFunction("RequestSourceBootstrap", script, requestSourceBootstrap);
    vm->RegisterFunction("ClaimSourceBootstrap", script, claimSourceBootstrap);
    vm->RegisterFunction("RegisterActor", "CLAWPhysicsNative", physicsRegister);
    vm->RegisterFunction("SetPopulationEnabled", "CLAWPhysicsNative", physicsSetPopulation);
    vm->RegisterFunction("UnregisterActor", "CLAWPhysicsNative", physicsUnregister);
    vm->RegisterFunction("ActorCurrent", "CLAWPhysicsNative", physicsActorCurrent);
    vm->RegisterFunction("SnapshotCurrent", "CLAWPhysicsNative", physicsSnapshotCurrent);
    vm->RegisterFunction("RefitPending", "CLAWPhysicsNative", physicsRefitPending);
    vm->RegisterFunction("AcknowledgeSnapshot", "CLAWPhysicsNative", physicsAcknowledge);
    vm->RegisterFunction("AcknowledgeLifecycle", "CLAWPhysicsNative", physicsAcknowledgeLifecycle);
    vm->RegisterFunction("GetValues", "CLAWPhysicsNative", physicsValues);
    vm->RegisterFunction("GetWeight", "CLAWPhysicsNative", physicsWeight);
    vm->RegisterFunction("GetCapsule", "CLAWPhysicsNative", physicsCapsule);
    vm->RegisterFunction("GetModelIdentity", "CLAWPhysicsNative", physicsModel);
    return true;
}

void exchange() {
    InterfaceExchangeMessage message;
    SKSE::GetMessagingInterface()->Dispatch(InterfaceExchangeMessage::kMessage_ExchangeInterface,
        &message, sizeof(message), "skee");
    if (message.interfaceMap) {
        auto* interface = message.interfaceMap->QueryInterface("BodyMorph");
        // All used methods belong to the stable v4 prefix. The v5-only trailing
        // callback is not called. An older interface cannot qualify this ABI.
        if (interface && interface->GetVersion() >= IBodyMorphInterface::kPluginVersion4)
            morphs = static_cast<IBodyMorphInterface*>(interface);
    }
    SKSE::log::info("SKEE body morph API {}", morphs ? "available" : "unavailable");
}

void exchangeOBodyReadiness() {
    obodyApiReady = false;
#if defined(CLAW_OBODY_API_HEADER)
    OBody::API::SKSEMessages::RequestPluginInterface request{};
    request.version = OBody::API::PluginAPIVersion::v1;
    request.pluginInterface = &obodyAPI;
    request.readinessEventListener = &obodyReadiness;
    SKSE::GetMessagingInterface()->Dispatch(decltype(request)::type, &request, sizeof(request), "OBody");
    obodyApiAvailable = obodyAPI != nullptr;
    SKSE::log::info("OBody public readiness interface {}", obodyAPI ? "available" : "unavailable");
#else
    SKSE::log::info("OBody source bootstrap unavailable: optional public API SDK was not selected at build time");
#endif
}

std::filesystem::path dataDirectory() {
    std::array<wchar_t, 32768> executable{};
    const auto length = GetModuleFileNameW(nullptr, executable.data(), static_cast<std::uint32_t>(executable.size()));
    if (!length || length >= executable.size()) throw std::runtime_error("cannot locate game executable directory");
    return std::filesystem::path(std::wstring(executable.data(), length)).parent_path() / "Data";
}
std::filesystem::path presetDirectory() { return dataDirectory() / claw::presetRelativePath; }

void notifyLoaded() {
    if (!tasks) return;
    const auto token = epoch.load();
    tasks->AddTask([token] {
        if (!enabled || token != epoch) return;
        if (auto* source = SKSE::GetModCallbackEventSource()) {
            SKSE::ModCallbackEvent event;
            event.eventName = "CLAWDistribution_Loaded";
            event.strArg = "0.1.0";
            event.numArg = 1;
            event.sender = nullptr;
            source->SendEvent(&event);
        }
    });
}

void message(SKSE::MessagingInterface::Message* event) {
    using Type = SKSE::MessagingInterface;
    switch (event->type) {
    case Type::kPostPostLoad: exchange(); exchangeOBodyReadiness(); break;
    case Type::kPreLoadGame:
        enabled = false; ++epoch;
        {
            std::lock_guard lock(mutex);
            requests.clear(); // Pool keeps pins until main-task collection.
            physicsBindings.clear(); physicsRegistrationRequests.clear();
            physicsPopulationEnabled = false; physicsPopulationBlocked.clear();
            obodySourcePopulationEnabled = false;
        }
        break;
    case Type::kDataLoaded:
        {
            std::lock_guard lock(mutex);
            try { catalog.loadDirectory(presetDirectory()); }
            catch (const std::exception& error) { catalog.clear(); SKSE::log::error("CLAW preset path: {}", error.what()); }
            for (const auto& error : catalog.diagnostics()) SKSE::log::error("{}: {}", error.source, error.reason);
            SKSE::log::info("CLAW catalog contains {} presets", catalog.size());
            try { morphProfiles.loadFile(dataDirectory() / claw::morphProfilesRelativePath); }
            catch (const std::exception& error) { SKSE::log::error("CLAW morph family catalog: {}", error.what()); }
            if (!morphProfiles.valid()) SKSE::log::warn("CLAW morph family catalog: {}", morphProfiles.error());
        }
        if (auto* source = RE::ScriptEventSourceHolder::GetSingleton()) {
            source->AddEventSink<RE::TESObjectLoadedEvent>(&events);
            source->AddEventSink<RE::TESSwitchRaceCompleteEvent>(&events);
        }
        if (auto* source = SKSE::GetNiNodeUpdateEventSource()) source->AddEventSink(&events);
        if (auto* source = SKSE::GetModCallbackEventSource()) source->AddEventSink(&events);
#if defined(CLAW_PHYSICS_MODEL_HEADER)
        startPhysicsWorker();
#endif
        timer = std::jthread([](std::stop_token stop) {
            while (!stop.stop_requested()) { std::this_thread::sleep_for(std::chrono::seconds(2)); if (!stop.stop_requested()) queueScan(); }
        });
        break;
    case Type::kNewGame:
        enabled = false; ++epoch;
        {
            std::lock_guard lock(mutex);
            states.clear(); requests.clear(); physicsBindings.clear(); physicsRegistrationRequests.clear(); saveNamespace = newNamespace(); nextIdentity = 1;
            physicsPopulationEnabled = false; physicsPopulationBlocked.clear();
            obodySourcePopulationEnabled = false;
        }
        [[fallthrough]];
    case Type::kPostLoadGame:
        {
            std::lock_guard lock(mutex);
            enabled = true; ++epoch;
        }
        queueScan(); notifyLoaded(); break;
    default: break;
    }
}
}

extern "C" __declspec(dllexport) constinit SKSE::PluginVersionData SKSEPlugin_Version = [] {
    SKSE::PluginVersionData version;
    version.PluginVersion({0, 1, 0, 0});
    version.PluginName("CLAWDistribution");
    version.AuthorName("CLAW contributors");
    version.versionIndependenceEx = SKSE::PluginVersionData::kVersionIndependentEx_AddressLibraryV5;
    for (std::size_t index = 0; index < claw::runtimeTargets.size(); ++index)
        version.compatibleVersions[index] = claw::runtimeTargets[index].game.pack();
    // CommonLib selects both pre/post629 struct layouts. As in CommonLib's
    // StructCompatibility::Independent declaration, this bit means no fixed
    // incompatible layout assumption. SKSE minima differ by runtime below.
    version.versionIndependenceEx |= SKSE::PluginVersionData::kVersionIndependentEx_NoStructUse;
    version.MinimumRequiredXSEVersion({0, 0, 0, 0});
    return version;
}();

extern "C" __declspec(dllexport) bool SKSEPlugin_Query(const SKSE::QueryInterface* skse, SKSE::PluginInfo* info) {
    if (!info) return false;
    info->infoVersion = SKSE::PluginInfo::kVersion; info->name = "CLAWDistribution"; info->version = 1;
    return runtimeTarget(skse) != nullptr;
}

extern "C" __declspec(dllexport) bool SKSEPlugin_Load(const SKSE::LoadInterface* skse) {
    const auto* target = runtimeTarget(skse);
    if (!target) return false;
    try {
        const auto directory = SKSE::log::log_directory();
        if (directory) {
            auto logger = std::make_shared<spdlog::logger>("CLAWDistribution",
                std::make_shared<spdlog::sinks::basic_file_sink_mt>((*directory / "CLAWDistribution.log").string(), true));
            spdlog::set_default_logger(std::move(logger)); spdlog::set_level(spdlog::level::info); spdlog::flush_on(spdlog::level::warn);
        }
        SKSE::Init(skse, {.log = false}); // Keep this plugin's existing logger.
        if (REL::Module::get().version() != target->game ||
            REL::Module::IsVR() != (target->family == claw::RuntimeFamily::vr) ||
            REL::Module::IsAE() != (target->family == claw::RuntimeFamily::ae) ||
            REL::Module::IsSE() != (target->family == claw::RuntimeFamily::se)) return false;
        SKSE::log::info("Universal CommonLib candidate runtime {} / SKSE {:08X}; engine qualification is separate", target->game.string(), skse->SKSEVersion());
        tasks = SKSE::GetTaskInterface();
        const auto* serial = SKSE::GetSerializationInterface();
        if (!tasks || !serial || !SKSE::GetPapyrusInterface() || !SKSE::GetMessagingInterface()) return false;
        serial->SetUniqueID(serializationID); serial->SetSaveCallback(save); serial->SetLoadCallback(load); serial->SetRevertCallback(revert);
        serial->SetFormDeleteCallback(deleted);
        return SKSE::GetPapyrusInterface()->Register(registerPapyrus) && SKSE::GetMessagingInterface()->RegisterListener(message);
    } catch (const std::exception&) { return false; }
}
