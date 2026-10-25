// Own implementation. Engine access and every SKEE write/read run in SKSE tasks.
#include "claw/Preset.h"
#include "claw/RequestOwnership.h"
#include <IPluginInterface.h>  // official pinned external API, never vendored
#include <spdlog/sinks/basic_file_sink.h>
#include <atomic>
#include <array>
#include <chrono>
#include <cmath>
#include <cstring>
#include <filesystem>
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

namespace {
#if defined(CLAW_RUNTIME_SE) && !defined(CLAW_RUNTIME_VR)
constexpr auto supportedRuntime = SKSE::RUNTIME_SSE_1_7_104;
#elif defined(CLAW_RUNTIME_VR) && !defined(CLAW_RUNTIME_SE)
constexpr auto supportedRuntime = SKSE::RUNTIME_VR_1_4_15;
#else
#error Select exactly one CLAW runtime through CMake.
#endif

bool supportsRuntime(const SKSE::QueryInterface* skse) {
    return skse && !skse->IsEditor() && skse->RuntimeVersion() == supportedRuntime;
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
    claw::Morphs cache;
    Status status{Status::pending};
    std::string error;
    std::uintptr_t lastRoot{};
    RE::VMHandle vmHandle{};
    float lastWeight{-1};
    bool dirty{true};
    RE::ActorHandle runtimeHandle; // Weak engine witness; created/resolved only in tasks.
    RE::Actor* runtimePointer{}; // Cached comparison only, never dereferenced by getters.
    std::uint64_t runtimeSerial{}; // Fresh after load; never serialized.
    claw::RequestBinding latestRequest; // Non-owning, process-local terminal request witness.
    bool quarantined{};
};

constexpr std::uint32_t serializationID = 0x444C5743; // CWLD, exclusive to this companion
constexpr std::uint32_t sessionRecord = 0x534C5743;
constexpr std::uint32_t actorRecord = 0x414C5743;
constexpr std::size_t maxActors = 8192;
constexpr float epsilon = 0.0001F;
claw::Catalog catalog;
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
void logError(State& state, std::string reason, Status status = Status::error);

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

State* stateFor(RE::Actor* actor, bool create) {
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
    state.identity = nextIdentity++;
    state.vmHandle = handle;
    state.runtimeHandle = runtime; state.runtimePointer = actor; state.runtimeSerial = nextRuntimeSerial++;
    state.sex = actor->GetActorBase()->GetSex() == RE::SEX::kFemale ? claw::Sex::female : claw::Sex::male;
    return &states.emplace(id, std::move(state)).first->second;
}

::TESObjectREFR* skeeReference(RE::Actor* actor) {
    // The official SKSE64 API uses global forward declarations; CommonLib uses RE.
    return reinterpret_cast<::TESObjectREFR*>(actor);
}

bool readback(RE::Actor* actor, const claw::Morphs& expected) {
    return claw::verifyOwnMorphs(expected, [actor](std::string_view name) {
        return morphs->GetMorph(skeeReference(actor), name.data(), claw::morphKey);
    }, epsilon);
}

bool clearOwn(RE::Actor* actor) {
    // Only the exact key and the public base-resource morph allowlist are touched.
    for (const auto name : claw::recognizedMorphs(claw::Sex::female))
        morphs->ClearMorph(skeeReference(actor), name.data(), claw::morphKey);
    for (const auto name : claw::recognizedMorphs(claw::Sex::female)) {
        const float value = morphs->GetMorph(skeeReference(actor), name.data(), claw::morphKey);
        if (!std::isfinite(value) || std::abs(value) > epsilon) return false;
    }
    return true;
}

void refreshActor(RE::Actor* actor, bool force = false) {
    // Called exclusively from a task. Do not move this into a native/event/timer.
    if (!currentOwner(actor) || !actor->GetActorBase()) return;
    const bool beast = beastRace && actor->GetRace() == beastRace; // current race, never NPC base race
    State* state = stateFor(actor, beast);
    if (!state || state->quarantined || !boundTo(*state, actor)) return;
    if (!actor->Is3DLoaded() || !actor->Get3D()) { state->status = Status::unloaded; state->dirty = true; return; }
    if (!morphs) { logError(*state, "SKEE BodyMorph API is unavailable", Status::providerUnavailable); return; }
    const auto root = reinterpret_cast<std::uintptr_t>(actor->Get3D());
    if (!beast || state->suppressed) {
        bool hasOwnValue = false;
        for (const auto name : claw::recognizedMorphs(claw::Sex::female))
            hasOwnValue |= morphs->GetMorph(skeeReference(actor), name.data(), claw::morphKey) != 0;
        if (force || state->dirty || hasOwnValue || state->lastRoot != root) {
            if (!clearOwn(actor)) { logError(*state, "own-key cleanup readback failed"); return; }
            morphs->ApplyBodyMorphs(skeeReference(actor), false);
        }
        state->status = state->suppressed ? Status::cleared : Status::human;
        state->error.clear(); state->cache.clear(); state->lastRoot = root; state->dirty = false;
        return;
    }
    const auto sex = actor->GetActorBase()->GetSex();
    if (sex != RE::SEX::kMale && sex != RE::SEX::kFemale) { logError(*state, "actor has no readable NPC sex"); return; }
    const auto desiredSex = sex == RE::SEX::kFemale ? claw::Sex::female : claw::Sex::male;
    if (!catalog.valid()) { logError(*state, "CLAW preset catalog is invalid or empty"); return; }
    if (state->preset.empty() || state->sex != desiredSex) {
        const auto identity = std::to_string(saveNamespace) + "/" + std::to_string(state->identity);
        const auto* preset = catalog.choose(identity, desiredSex);
        if (!preset) { logError(*state, "no presets for this actor's sex"); return; }
        state->preset = preset->name; state->sex = desiredSex; state->dirty = true;
    }
    const auto* preset = catalog.find(state->preset, desiredSex);
    if (!preset) { logError(*state, "saved preset missing or has wrong family: " + state->preset); return; }
    const float weight = actor->GetActorBase()->weight;
    claw::Morphs expected;
    try { expected = claw::interpolate(*preset, weight); }
    catch (const std::exception& error) { logError(*state, error.what()); return; }
    const bool matching = readback(actor, expected);
    if (force || state->dirty || state->lastRoot != root || state->lastWeight != weight || !matching) {
        state->status = Status::pending;
        if (!clearOwn(actor)) { logError(*state, "own-key preparation readback failed"); return; }
        // Recheck race/model immediately before writes; all operations stay on this main-thread task.
        if (!currentOwner(actor) || actor->GetRace() != beastRace || !actor->Is3DLoaded() || !actor->Get3D()) {
            state->dirty = true; state->status = Status::pending; return;
        }
        for (const auto& [name, value] : expected)
            morphs->SetMorph(skeeReference(actor), name.c_str(), claw::morphKey, value);
        morphs->ApplyBodyMorphs(skeeReference(actor), false);
        if (!readback(actor, expected)) { logError(*state, "SKEE own morph readback differs from requested values"); return; }
    }
    state->cache = std::move(expected); state->lastRoot = root; state->lastWeight = weight;
    state->dirty = false; state->status = Status::applied; state->error.clear();
}

void scan() {
    std::lock_guard lock(mutex);
    collectPins();
    if (!enabled) return;
    checkRuntimeInstances();
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
        // Zero is already an unavailable VM identity in record v1. Preserve hard
        // quarantine across saves without inventing a new persistence format.
        Bytes row; u32(row, id); u64(row, state.identity); u64(row, state.quarantined ? 0 : state.vmHandle); string(row, state.preset);
        u32(row, static_cast<std::uint32_t>(state.sex)); u32(row, state.suppressed ? 1 : 0);
        u32(row, static_cast<std::uint32_t>(state.cache.size()));
        for (const auto& [name, value] : state.cache) {
            string(row, name); std::uint32_t bits; std::memcpy(&bits, &value, sizeof(bits)); u32(row, bits);
        }
        if (!interface->WriteRecord(actorRecord, 1, row.data(), static_cast<std::uint32_t>(row.size()))) SKSE::log::error("Actor {:08X} serialization failed", id);
    }
}

void revert(SKSE::SerializationInterface*) {
    enabled = false; ++epoch;
    {
        std::lock_guard lock(mutex);
        states.clear(); requests.clear(); saveNamespace = 0; nextIdentity = 1;
    }
    queuePinCollection(); // Never release the last intrusive pin on a VM callback.
}

void load(SKSE::SerializationInterface* interface) {
    enabled = false; ++epoch;
    std::lock_guard lock(mutex);
    states.clear(); requests.clear(); saveNamespace = 0; nextIdentity = 1;
    std::uint32_t type{}, version{}, length{};
    bool sessionFound = false;
    std::set<std::uint64_t> identities;
    while (interface->GetNextRecordInfo(type, version, length)) {
        if (type != sessionRecord && type != actorRecord) continue;
        if (version != 1 || length > 16384) { SKSE::log::error("Unsupported/corrupt CLAW record"); continue; }
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
            if (sex > 1 || suppressed > 1 || count > 25 || !state.identity || state.identity == std::numeric_limits<std::uint64_t>::max() || !identities.insert(state.identity).second)
                throw std::runtime_error("invalid actor identity/family/cache");
            state.sex = static_cast<claw::Sex>(sex); state.suppressed = suppressed != 0;
            for (std::uint32_t index = 0; index < count; ++index) {
                const auto name = reader.string(); const auto bits = reader.u32(); float value; std::memcpy(&value, &bits, sizeof(value));
                if (!claw::recognizedMorph(name, state.sex) || !std::isfinite(value) || value < 0 || value > 1 || !state.cache.emplace(name, value).second)
                    throw std::runtime_error("invalid serialized morph");
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

enum class Operation { assign, clear, refresh };
bool actorRequest(RE::Actor* actor, Operation operation, std::string presetName = {}) {
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
            found->second.status = Status::pending;
            found->second.latestRequest = {*ticket, found->second.runtimeSerial};
        }
    }
    // The pool keeps an intrusive pin even if this task is disposed before the
    // native callback's final shared_ptr copy dies. Only task collection erases it.
    tasks->AddTask([id, owner = std::move(owner), ticket = *ticket, operation, presetName = std::move(presetName)] {
        std::lock_guard lock(mutex);
        if (!enabled || !requests.owns(id, ticket, epoch.load())) return;
        auto fail = [&](std::string error) { requests.finish(id, ticket, epoch.load(), std::move(error)); };
        auto* target = owner->actor.get();
        if (!claw::mayRunActorRequest(target, RE::TESForm::LookupByID<RE::Actor>(id), target->formID == id, target->IsDeleted()) ||
            !target->GetActorBase()) { fail("original actor reference is deleted or no longer owns its FormID"); return; }
        auto* state = stateFor(target, true);
        if (!state) { fail("actor identity unavailable or reference/pin state limit reached"); return; }
        if (state->quarantined || !boundTo(*state, target)) { fail("actor assignment identity is quarantined"); return; }
        state->latestRequest = {ticket, state->runtimeSerial};
        if (operation == Operation::assign) {
            const auto sex = target->GetActorBase()->GetSex() == RE::SEX::kFemale ? claw::Sex::female : claw::Sex::male;
            if (!beastRace || target->GetRace() != beastRace) { fail("AssignPreset requires the current WerewolfBeastRace"); return; }
            if (!catalog.find(presetName, sex)) { fail("preset family does not match actor sex"); return; }
            state->preset = presetName; state->sex = sex; state->suppressed = false;
        } else if (operation == Operation::clear) state->suppressed = true;
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
    return state && !state->quarantined ? RE::BSFixedString(state->preset) : RE::BSFixedString{};
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
bool clearRequest(RE::StaticFunctionTag*, RE::Actor* actor) { return actorRequest(actor, Operation::clear); }
bool refreshRequest(RE::StaticFunctionTag*, RE::Actor* actor) { return actorRequest(actor, Operation::refresh); }
bool registerPapyrus(RE::BSScript::IVirtualMachine* vm) {
    constexpr auto script = "CLAWDistributionNative";
    vm->RegisterFunction("GetPresetNames", script, presetNames);
    vm->RegisterFunction("AssignPreset", script, assignPreset);
    vm->RegisterFunction("GetAssigned", script, assigned);
    vm->RegisterFunction("GetStatus", script, getStatus);
    vm->RegisterFunction("GetLastError", script, lastError);
    vm->RegisterFunction("GetOwnMorph", script, ownMorph);
    vm->RegisterFunction("ClearOwn", script, clearRequest);
    vm->RegisterFunction("Refresh", script, refreshRequest);
    return true;
}

void exchange() {
    InterfaceExchangeMessage message;
    SKSE::GetMessagingInterface()->Dispatch(InterfaceExchangeMessage::kMessage_ExchangeInterface,
        &message, sizeof(message), "skee");
    if (message.interfaceMap) {
        auto* interface = message.interfaceMap->QueryInterface("BodyMorph");
        if (interface && interface->GetVersion() >= 1) morphs = static_cast<IBodyMorphInterface*>(interface);
    }
    SKSE::log::info("SKEE body morph API {}", morphs ? "available" : "unavailable");
}

std::filesystem::path presetDirectory() {
    std::array<wchar_t, 32768> executable{};
#if defined(CLAW_RUNTIME_SE)
    const auto length = GetModuleFileNameW(nullptr, executable.data(), static_cast<std::uint32_t>(executable.size()));
#else
    const auto length = GetModuleFileName(nullptr, executable.data(), static_cast<std::uint32_t>(executable.size()));
#endif
    if (!length || length >= executable.size()) throw std::runtime_error("cannot locate game executable directory");
    return std::filesystem::path(std::wstring(executable.data(), length)).parent_path() / "Data" / claw::presetRelativePath;
}

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
    case Type::kPostPostLoad: exchange(); break;
    case Type::kPreLoadGame:
        enabled = false; ++epoch;
        {
            std::lock_guard lock(mutex);
            requests.clear(); // Pool keeps pins until main-task collection.
        }
        break;
    case Type::kDataLoaded:
        {
            std::lock_guard lock(mutex);
            try { catalog.loadDirectory(presetDirectory()); }
            catch (const std::exception& error) { catalog.clear(); SKSE::log::error("CLAW preset path: {}", error.what()); }
            for (const auto& error : catalog.diagnostics()) SKSE::log::error("{}: {}", error.source, error.reason);
            SKSE::log::info("CLAW catalog contains {} presets", catalog.size());
        }
        if (auto* source = RE::ScriptEventSourceHolder::GetSingleton()) {
            source->AddEventSink<RE::TESObjectLoadedEvent>(&events);
            source->AddEventSink<RE::TESSwitchRaceCompleteEvent>(&events);
        }
        if (auto* source = SKSE::GetNiNodeUpdateEventSource()) source->AddEventSink(&events);
        if (auto* source = SKSE::GetModCallbackEventSource()) source->AddEventSink(&events);
        timer = std::jthread([](std::stop_token stop) {
            while (!stop.stop_requested()) { std::this_thread::sleep_for(std::chrono::seconds(2)); if (!stop.stop_requested()) queueScan(); }
        });
        break;
    case Type::kNewGame:
        enabled = false; ++epoch;
        {
            std::lock_guard lock(mutex);
            states.clear(); requests.clear(); saveNamespace = newNamespace(); nextIdentity = 1;
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

#if defined(CLAW_RUNTIME_SE)
extern "C" __declspec(dllexport) constinit SKSE::PluginVersionData SKSEPlugin_Version = [] {
    SKSE::PluginVersionData version;
    version.PluginVersion({0, 1, 0, 0});
    version.PluginName("CLAWDistribution");
    version.AuthorName("CLAW contributors");
    version.versionIndependenceEx = SKSE::PluginVersionData::kVersionIndependentEx_AddressLibraryV5;
    version.CompatibleVersions({supportedRuntime});
    version.UsesUpdatedStructs();
    version.MinimumRequiredXSEVersion({2, 3, 1, 0});
    return version;
}();
#endif

extern "C" __declspec(dllexport) bool SKSEPlugin_Query(const SKSE::QueryInterface* skse, SKSE::PluginInfo* info) {
    if (!info) return false;
    info->infoVersion = SKSE::PluginInfo::kVersion; info->name = "CLAWDistribution"; info->version = 1;
    return supportsRuntime(skse);
}

extern "C" __declspec(dllexport) bool SKSEPlugin_Load(const SKSE::LoadInterface* skse) {
    if (!supportsRuntime(skse)) return false;
    try {
        const auto directory = SKSE::log::log_directory();
        if (directory) {
            auto logger = std::make_shared<spdlog::logger>("CLAWDistribution",
                std::make_shared<spdlog::sinks::basic_file_sink_mt>((*directory / "CLAWDistribution.log").string(), true));
            spdlog::set_default_logger(std::move(logger)); spdlog::set_level(spdlog::level::info); spdlog::flush_on(spdlog::level::warn);
        }
#if defined(CLAW_RUNTIME_SE)
        SKSE::Init(skse, {.log = false}); // Keep this plugin's existing logger.
#else
        SKSE::Init(skse);
#endif
        tasks = SKSE::GetTaskInterface();
        const auto* serial = SKSE::GetSerializationInterface();
        if (!tasks || !serial || !SKSE::GetPapyrusInterface() || !SKSE::GetMessagingInterface()) return false;
        serial->SetUniqueID(serializationID); serial->SetSaveCallback(save); serial->SetLoadCallback(load); serial->SetRevertCallback(revert);
        serial->SetFormDeleteCallback(deleted);
        return SKSE::GetPapyrusInterface()->Register(registerPapyrus) && SKSE::GetMessagingInterface()->RegisterListener(message);
    } catch (const std::exception&) { return false; }
}
