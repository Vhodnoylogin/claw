// Test-only observation of one dynamic NPC's attached third-person graph.
#include <RE/Skyrim.h>
#include <SKSE/SKSE.h>
#include <Windows.h>
#include <nlohmann/json.hpp>
#include <IPluginInterface.h>
#include "LeasePolicy.h"
#include "claw/PhysicsObserver.h"
#include "claw/RuntimeSupport.h"
#include "claw/WorldStartPolicy.h"
#include <algorithm>
#include <atomic>
#include <bit>
#include <chrono>
#include <memory>
#include <mutex>
#include <span>
#include <stdexcept>
#include <string_view>
#include <unordered_set>
#include <vector>

#if !defined(SKYRIM_CROSS_VR)
#error Build with the same cross-runtime CommonLib ABI as the CLAW DLL.
#endif

namespace {
using Json = nlohmann::json;
using Object = RE::NiAVObject;
using Pin = RE::NiPointer<Object>;
using Clock = std::chrono::steady_clock;
using Path = std::vector<Pin>;
using claw::npc_pose::Scope;
using claw::npc_pose::Transform;

constexpr auto name = "CLAWVRNpcPose";
constexpr auto schema = "claw-vr-npc-pose/1";
constexpr std::size_t maxObjects = 4096, maxLinks = 8192, maxDepth = 64;
constexpr RE::FormID beastRace = 0xCDD84;
constexpr std::size_t motionNodeCount = 12;
constexpr std::array nodeNames{
    "NPC EarL [EarL]Bone01", "NPC EarL [EarL]Bone02", "NPC EarR [EarR]Bone01", "NPC EarR [EarR]Bone02",
    "TailBone01", "TailBone02", "TailBone03", "TailBone04", "TailBone05",
    "NPC Head [Head]", "Tails", "NPC Root [Root]",
    "NPC Spine2 [Spn2]", "NPC Pelvis [Pelv]", "NPC R Thigh [LThg]"
};

constexpr auto femaleNodeNames = [] {
    std::array<const char*, motionNodeCount + 4> names{};
    std::copy_n(nodeNames.begin(), motionNodeCount, names.begin());
    names[motionNodeCount] = "NPC L PreBreast P1";
    names[motionNodeCount + 1] = "NPC L Breast P1";
    names[motionNodeCount + 2] = "NPC R PreBreast P1";
    names[motionNodeCount + 3] = "NPC R Breast P1";
    return names;
}();
constexpr std::size_t maximumPoseNodes = std::max(nodeNames.size(), femaleNodeNames.size());

std::span<const char* const> nodeNamesFor(Scope scope) {
    if (scope == Scope::femaleMotion) return femaleNodeNames;
    auto names = std::span<const char* const>(nodeNames);
    return observesContact(scope) ? names : names.first(motionNodeCount);
}

std::atomic<IBodyMorphInterface*> effectiveSource;

void connectMorphSource() {
    InterfaceExchangeMessage exchange;
    SKSE::GetMessagingInterface()->Dispatch(InterfaceExchangeMessage::kMessage_ExchangeInterface,
        &exchange, sizeof(exchange), "skee");
    auto* queried = exchange.interfaceMap ? exchange.interfaceMap->QueryInterface("BodyMorph") : nullptr;
    if (queried && queried->GetVersion() >= IBodyMorphInterface::kPluginVersion4)
        effectiveSource.store(static_cast<IBodyMorphInterface*>(queried));
}

struct Fixture {
    RE::FormID actor{}, base{}, cell{}, addon{};
    std::uint32_t handle{};
    bool female{};
    unsigned weight() const { return female ? 100u : 50u; }
    bool operator==(const Fixture&) const = default;
};

Fixture fixtureBits(std::int32_t actor, std::int32_t base, std::int32_t handle,
                    std::int32_t cell, std::int32_t addon, bool female = false) {
    return {std::bit_cast<std::uint32_t>(actor), std::bit_cast<std::uint32_t>(base),
        std::bit_cast<std::uint32_t>(cell), std::bit_cast<std::uint32_t>(addon), std::bit_cast<std::uint32_t>(handle), female};
}

void require(bool condition, const char* reason) {
    if (!condition) throw std::runtime_error(reason);
}

Json readEffectiveMorphs(RE::Actor& actor, const std::vector<std::string>& names) {
    Json result = Json::object();
    if (names.empty()) return result;
    auto* provider = effectiveSource.load();
    require(provider, "effective SKEE body morph interface unavailable");
    auto* ref = reinterpret_cast<::TESObjectREFR*>(static_cast<RE::TESObjectREFR*>(&actor));
    for (const auto& name : names) {
        const float value = provider->GetBodyMorphs(ref, name.c_str());
        require(std::isfinite(value), "effective morph value is not finite");
        result[name] = value;
    }
    return result;
}

std::uint64_t qpc() {
    LARGE_INTEGER value{};
    require(QueryPerformanceCounter(&value) && value.QuadPart > 0, "QPC unavailable");
    return static_cast<std::uint64_t>(value.QuadPart);
}

RE::FormID form(const RE::TESForm* value) { return value ? value->GetFormID() : 0; }

class SnapshotEvents final : public RE::BSTEventSink<SKSE::ModCallbackEvent> {
public:
    void observe(const RE::TESForm* ownedActor) {
        std::lock_guard lock(mutex);
        actor = ownedActor;
        latest = {};
    }

    struct Entry {
        std::int32_t token{};
        std::uint64_t observedQpc{};
    };

    Entry readAfter(std::int32_t previous) {
        std::lock_guard lock(mutex);
        return latest.token > previous ? latest : Entry{};
    }

    RE::BSEventNotifyControl ProcessEvent(const SKSE::ModCallbackEvent* event,
            RE::BSTEventSource<SKSE::ModCallbackEvent>*) override {
        if (!event || !event->sender || event->eventName != "CLAWPhysics_Observation" ||
            event->strArg != "snapshot") return RE::BSEventNotifyControl::kContinue;
        const auto token = claw::npc_pose::physicsSnapshotToken(event->numArg);
        std::lock_guard lock(mutex);
        if (event->sender == actor && token > latest.token) {
            LARGE_INTEGER tick{};
            if (QueryPerformanceCounter(&tick) && tick.QuadPart > 0)
                latest = {token, static_cast<std::uint64_t>(tick.QuadPart)};
        }
        return RE::BSEventNotifyControl::kContinue;
    }

private:
    // The callback only compares the pinned sender address. It neither
    // dereferences the form nor holds or acquires the parent witness mutex.
    std::mutex mutex;
    const RE::TESForm* actor{};
    Entry latest;
};

Json pose(const RE::NiTransform& value) {
    Transform copied;
    for (std::size_t row = 0; row < 3; ++row)
        for (std::size_t column = 0; column < 3; ++column)
            copied.rotation[row * 3 + column] = value.rotate.entry[row][column];
    copied.translation = {value.translate.x, value.translate.y, value.translate.z};
    copied.scale = value.scale;
    require(claw::npc_pose::finite(copied), "nonfinite pose or nonpositive scale");
    return {{"rotationRowMajor", copied.rotation}, {"translation", copied.translation}, {"scale", copied.scale}};
}

bool childOf(Object& child, Object& parent) {
    if (child.parent != &parent) return false;
    auto* branch = parent.AsNode();
    if (!branch) return false;
    std::size_t matches{}, links{};
    for (const auto& entry : branch->GetChildren()) {
        if (++links > maxLinks) return false;
        if (entry.get() == &child) ++matches;
    }
    return matches == 1;
}

Path ownedPath(Object& start, Object& root) {
    Path result{Pin(&start)};
    while (result.back().get() != &root) {
        require(result.size() < maxDepth, "scene ancestry limit");
        auto* parent = result.back()->parent;
        require(parent && childOf(*result.back(), *parent), "object outside its actor root");
        for (const auto& entry : result) require(entry.get() != parent, "scene ancestry cycle");
        result.emplace_back(parent);
    }
    return result;
}

bool attached(const Path& path) {
    for (std::size_t i = 1; i < path.size(); ++i)
        if (!childOf(*path[i - 1], *path[i])) return false;
    return !path.empty();
}

bool sceneReady(RE::FormID expectedCell) {
    auto* player = RE::PlayerCharacter::GetSingleton();
    auto* ui = RE::UI::GetSingleton();
    auto* cell = player ? player->GetParentCell() : nullptr;
    return cell && form(cell) == expectedCell && cell->IsAttached() &&
           form(player) == 0x14 && player->Is3DLoaded() && player->Get3D(false) && ui &&
           !ui->IsMenuOpen(RE::LoadingMenu::MENU_NAME) && !ui->IsMenuOpen(RE::MainMenu::MENU_NAME);
}

std::array<Object*, maximumPoseNodes> findNodes(Object& root, std::span<const char* const> names) {
    std::array<Object*, maximumPoseNodes> result{};
    std::vector<Object*> pending{&root};
    std::unordered_set<Object*> seen;
    std::size_t links{};
    while (!pending.empty()) {
        auto* object = pending.back();
        pending.pop_back();
        require(seen.insert(object).second && seen.size() <= maxObjects, "scene repeated object or object limit");
        const auto* rawName = object->name.c_str();
        const std::string_view nodeName(rawName ? rawName : "");
        for (std::size_t i = 0; i < names.size(); ++i) {
            if (nodeName != names[i]) continue;
            require(!result[i], "required node name is ambiguous");
            result[i] = object;
        }
        if (auto* branch = object->AsNode()) {
            for (const auto& child : branch->GetChildren()) {
                require(++links <= maxLinks, "scene child-link limit");
                if (child) pending.push_back(child.get());
            }
        }
    }
    for (const auto* node : std::span(result).first(names.size()))
        require(node && node != &root, "required child node absent");
    return result;
}

// Created, observed and destroyed only by serialized SKSE engine tasks.
class Scene {
public:
    Scene(const Fixture& expected, Scope scope) : fixture(expected), names(nodeNamesFor(scope)) {
        require(sceneReady(fixture.cell), "loaded player in fixture cell required");
        auto* reference = RE::TESForm::LookupByID<RE::Actor>(fixture.actor);
        require(reference, "dynamic NPC not found");
        handle = reference->GetHandle();
        actorIdentity = handle.get();
        require(actorIdentity.get() == reference && validActor(*reference), "initial NPC identity or fixture mismatch");
        const auto& actor = actorIdentity;
        root = Pin(actor->Get3D(false));
        require(root && root->parent, "third-person root unattached");
        rootParent = Pin(root->parent);
        biped = actor->GetBiped(false);
        require(biped && biped->root && biped->actorRef.native_handle() == fixture.handle,
                "third-person biped owner absent or mismatched");
        bipedRootPath = ownedPath(*biped->root, *root);
        const auto& slot = biped->objects[RE::BIPED_OBJECTS::kBody];
        item = form(slot.item);
        require(item && form(slot.addon) == fixture.addon && slot.partClone,
                "expected active third-person body slot, addon or clone absent");
        clonePath = ownedPath(*slot.partClone, *root);
        require(clonePath.size() >= 2, "body clone is not a child of the actor world root");
        const auto observed = findNodes(*root, names);
        for (std::size_t i = 0; i < names.size(); ++i) nodes[i] = ownedPath(*observed[i], *root);
        check();
    }

    Json snapshot(const std::vector<std::string>& morphs) const {
        check();
        auto values = readEffectiveMorphs(*actorIdentity, morphs);
        const auto observed = findNodes(*root, names);
        Json rows = Json::array();
        for (std::size_t i = 0; i < names.size(); ++i) {
            const auto& path = nodes[i];
            require(observed[i] == path[0].get(), "required bone replaced");
            rows.push_back({{"name", names[i]}, {"local", pose(path[0]->local)},
                            {"world", pose(path[0]->world)}, {"parentWorld", pose(path[1]->world)}});
        }
        Json result{{"nodes", std::move(rows)}, {"rootWorld", pose(root->world)},
                    {"bodyCloneWorld", pose(clonePath[0]->world)}, {"bodyItem", item}};
        if (!morphs.empty()) {
            require(readEffectiveMorphs(*actorIdentity, morphs) == values, "effective morph vector changed during pose read");
            result["effectiveMorphs"] = std::move(values);
        }
        check();
        return result;
    }

    const RE::TESForm* eventSender() const { return actorIdentity.get(); }

private:
    bool validActor(RE::Actor& actor) const {
        const auto* base = actor.GetActorBase();
        return form(&actor) == fixture.actor && form(base) == fixture.base &&
               actor.GetHandle().native_handle() == fixture.handle && form(actor.GetParentCell()) == fixture.cell &&
               form(actor.GetRace()) == beastRace && form(base->race) == beastRace &&
               static_cast<std::uint32_t>(base->GetSex()) == static_cast<std::uint32_t>(fixture.female) &&
               base->weight == static_cast<float>(fixture.weight()) &&
               actor.Is3DLoaded() && !actor.IsDeleted() && !actor.IsDisabled() && !actor.IsDead();
    }

    void check() const {
        require(sceneReady(fixture.cell), "player left the loaded fixture cell");
        const auto actor = handle.get();
        require(actor && actor.get() == actorIdentity.get() && validActor(*actor), "NPC handle or fixture changed");
        require(actor->Get3D(false) == root.get() && childOf(*root, *rootParent),
                "third-person root replaced or detached");
        require(actor->GetBiped(false).get() == biped.get() && biped->root == bipedRootPath[0].get() &&
                biped->actorRef.native_handle() == fixture.handle && attached(bipedRootPath), "third-person biped changed");
        const auto& slot = biped->objects[RE::BIPED_OBJECTS::kBody];
        require(form(slot.item) == item && form(slot.addon) == fixture.addon &&
                slot.partClone.get() == clonePath[0].get() && attached(clonePath), "third-person body attachment changed");
        for (const auto& node : std::span(nodes).first(names.size()))
            require(attached(node), "required bone ancestry changed");
    }

    Fixture fixture;
    std::span<const char* const> names;
    RE::ActorHandle handle;
    RE::NiPointer<RE::Actor> actorIdentity;
    Pin root, rootParent;
    RE::BSTSmartPointer<RE::BipedAnim> biped;
    RE::FormID item{};
    Path bipedRootPath, clonePath;
    std::array<Path, maximumPoseNodes> nodes;
};

class Witness final : public RE::BSTEventSink<RE::TESObjectLoadedEvent> {
public:
    bool setup() {
        LARGE_INTEGER ticks{};
        if (!QueryPerformanceFrequency(&ticks) || ticks.QuadPart <= 0) return false;
        frequency = ticks.QuadPart;
        timer = CreateThreadpoolTimer(expire, this, nullptr);
        return timer != nullptr;
    }

    void closeTimer() { CloseThreadpoolTimer(timer); }

    void registerUnloads() {
        if (auto* source = RE::ScriptEventSourceHolder::GetSingleton()) {
            source->AddEventSink<RE::TESObjectLoadedEvent>(this);
            std::lock_guard lock(mutex);
            unloadsObserved = true;
        }
    }

    void registerSnapshots() {
        if (auto* source = SKSE::GetModCallbackEventSource()) {
            source->AddEventSink(&snapshots);
            std::lock_guard lock(mutex);
            snapshotsObserved = true;
        }
    }

    void world(bool available) {
        std::lock_guard lock(mutex);
        loading = !available;
        ++epoch;
        if (active() || unreleased()) queueRetirement("world changed");
    }

    std::string begin(std::int32_t requested, const Fixture& expected, Scope requestedScope,
                      std::vector<std::string> names = {}) {
        std::lock_guard lock(mutex);
        if (requested <= 0 || !claw::npc_pose::validFixture(
                expected.actor, expected.base, expected.handle, expected.cell, expected.addon))
            return response("refused", requested, 0, "positive nonce and exact dynamic NPC fixture required").dump();
        if (needsEffectiveMorphs(requestedScope) && !claw::validPhysicsNames(names))
            return response("refused", requested, 0, "invalid effective morph names").dump();
        if (nonce)
            return nonce == requested && fixture == expected && sameOpeningScope(scope, requestedScope, sequence) &&
                    morphNames == names
                ? readCurrent() : response("refused", requested, 0, "one NPC pose lease per process").dump();
        if (loading)
            return response("refused", requested, 0, "load in progress or failed").dump();
        if (!unloadsObserved)
            return response("refused", requested, 0, "unload observer unavailable").dump();

        nonce = requested;
        fixture = expected;
        scope = requestedScope;
        morphNames = std::move(names);
        watched.store(fixture.actor);
        leaseEpoch = epoch;
        deadline = Clock::now() + leaseLifetime(scope);
        // The deadline is enforced in each API/task. The one-shot watchdog also retires an abandoned lease.
        using FileTimeTicks = std::chrono::duration<std::int64_t, std::ratio<1, 10000000>>;
        ULARGE_INTEGER due{};
        due.QuadPart = static_cast<ULONGLONG>(-std::chrono::duration_cast<FileTimeTicks>(watchdogDelay(scope)).count());
        FILETIME relative{due.LowPart, due.HighPart};
        SetThreadpoolTimer(timer, &relative, 0, 0);
        queueSample();
        return readCurrent();
    }

    std::string sample(std::int32_t requested, std::int32_t index) {
        std::lock_guard lock(mutex);
        if (requested != nonce || !nonce || std::string_view(status) != "ready" || expired() ||
            !claw::npc_pose::nextSample(index, sequence))
            return response("refused", requested, index, "no ready lease or invalid next sequence").dump();
        sequence = index;
        queueSample();
        return readCurrent();
    }

    std::string read(std::int32_t requested, std::int32_t index) {
        std::lock_guard lock(mutex);
        if (!nonce || requested != nonce || index != sequence)
            return response("refused", requested, index, "unknown lease or sequence").dump();
        return readCurrent();
    }

    std::string readSnapshot(std::int32_t requested, std::int32_t previous) {
        std::lock_guard lock(mutex);
        if (!snapshotsObserved || !nonce || requested != nonce || previous < 0 ||
            !observesContact(scope) || !scene || !active() || expired() || unloaded.load() || leaseEpoch != epoch)
            return response("refused", requested, sequence, "active contact lease required").dump();
        const auto entry = snapshots.readAfter(previous);
        auto out = response(entry.token ? "ready" : "pending", nonce, sequence);
        out["actor"] = fixture.actor;
        out["base"] = fixture.base;
        out["runtimeHandle"] = fixture.handle;
        out["rootToken"] = nonce;
        out["loadEpoch"] = leaseEpoch;
        if (entry.token) {
            out["snapshotToken"] = entry.token;
            out["eventQpc"] = entry.observedQpc;
        }
        return out.dump();
    }

    std::string end(std::int32_t requested) {
        std::lock_guard lock(mutex);
        if (!nonce || requested != nonce) return response("refused", requested, 0, "unknown lease").dump();
        if (active()) queueRetirement(expired() ? "lease expired" : nullptr);
        else if (unreleased()) queueRetirement(reason);
        return readCurrent();
    }

    RE::BSEventNotifyControl ProcessEvent(const RE::TESObjectLoadedEvent* event,
                                          RE::BSTEventSource<RE::TESObjectLoadedEvent>*) override {
        if (event && !event->loaded && event->formID == watched.load()) {
            unloaded.store(true);
            try { SKSE::GetTaskInterface()->AddTask([this] { abortUnloaded(); }); }
            catch (...) {} // Flag already poisons every sample; watchdog still owns retirement.
        }
        return RE::BSEventNotifyControl::kContinue;
    }

private:
    static void CALLBACK expire(PTP_CALLBACK_INSTANCE, void* context, PTP_TIMER) {
        auto& witness = *static_cast<Witness*>(context);
        std::lock_guard lock(witness.mutex);
        if (witness.active() || witness.unreleased()) witness.queueRetirement("lease expired");
    }

    bool active() const { return std::string_view(status) == "ready" || std::string_view(status) == "pending"; }
    bool unreleased() const { return std::string_view(status) == "refused" && bool(scene); }
    bool expired() const { return Clock::now() >= deadline; }

    Json response(const char* state, std::int32_t requested, std::int32_t index, const char* why = nullptr) const {
        Json out{{"schema", schema}, {"status", state}, {"nonce", requested}, {"sequence", index},
                 {"pid", GetCurrentProcessId()}, {"qpcFrequency", frequency}};
        if (why) out["reason"] = why;
        return out;
    }

    std::string readCurrent() const {
        if (active() && (expired() || unloaded.load()))
            return response("refused", nonce, sequence, expired() ? "lease expired" : "NPC unloaded").dump();
        if (std::string_view(status) == "ready") return result;
        return response(status, nonce, sequence, reason).dump();
    }

    void failedQueue() {
        // Refuse every further sample. If a task was accepted despite the exception, it may retire the pins.
        status = "refused";
        reason = "SKSE main-task queue failed; release not confirmed";
        result.clear();
    }

    void queueSample() {
        const auto index = sequence;
        status = "pending";
        result.clear();
        try { SKSE::GetTaskInterface()->AddTask([this, index] { capture(index); }); }
        catch (...) { failedQueue(); }
    }

    void queueRetirement(const char* why) {
        status = "retiring";
        reason = why;
        result.clear();
        try {
            SKSE::GetTaskInterface()->AddTask([this] {
                std::lock_guard lock(mutex);
                retire(reason);
            });
        } catch (...) { failedQueue(); }
    }

    void abortUnloaded() {
        std::lock_guard lock(mutex);
        if (active() || unreleased()) retire("NPC unloaded");
    }

    void retire(const char* why) {
        snapshots.observe(nullptr);
        scene.reset(); // Engine ownership is released only in a main task.
        watched.store(0);
        SetThreadpoolTimer(timer, nullptr, 0, 0);
        result.clear();
        reason = why;
        status = why ? "refused" : "ended";
    }

    void capture(std::int32_t index) {
        std::lock_guard lock(mutex);
        if (unreleased()) retire(reason);
        if (std::string_view(status) != "pending" || index != sequence) return;
        try {
            require(leaseEpoch == epoch && !loading && !expired() && !unloaded.load(), "NPC pose lease invalidated");
            const auto first = qpc();
            if (!scene) {
                scene = std::make_unique<Scene>(fixture, scope);
                if (observesContact(scope) && snapshotsObserved) snapshots.observe(scene->eventSender());
            }
            auto sample = scene->snapshot(morphNames);
            const auto last = qpc();
            require(first <= last && !expired() && !unloaded.load(), "NPC pose expired or unloaded during sample");
            sample.update({{"phase", "skse_main_thread_task"}, {"threadID", GetCurrentThreadId()},
                {"qpcBegin", first}, {"qpcEnd", last}, {"loadEpoch", leaseEpoch}, {"rootToken", nonce},
                {"actor", fixture.actor}, {"base", fixture.base}, {"runtimeHandle", fixture.handle},
                {"cell", fixture.cell}, {"bodyAddon", fixture.addon},
                {"sex", static_cast<unsigned>(fixture.female)}, {"weight", fixture.weight()},
                {"race", beastRace}, {"view", "third_person"}});
            auto out = response("ready", nonce, index);
            out["sample"] = std::move(sample);
            result = out.dump();
            status = "ready";
        } catch (const std::exception& error) {
            refusal = error.what();
            retire(refusal.c_str());
        } catch (...) { retire("NPC pose snapshot failed"); }
    }

    std::mutex mutex;
    std::unique_ptr<Scene> scene;
    PTP_TIMER timer{};
    std::uint64_t frequency{}, epoch{1}, leaseEpoch{};
    Clock::time_point deadline{};
    std::atomic<RE::FormID> watched{};
    std::atomic<bool> unloaded{};
    SnapshotEvents snapshots;
    bool loading{}, unloadsObserved{}, snapshotsObserved{};
    Fixture fixture;
    Scope scope{Scope::motion};
    std::vector<std::string> morphNames;
    std::int32_t nonce{}, sequence{};
    const char* status{"idle"};
    const char* reason{};
    std::string result, refusal;
};

Witness* witness; // SKSE registration and the bounded watchdog share process lifetime.

std::string begin(RE::StaticFunctionTag*, std::int32_t nonce, std::int32_t actor, std::int32_t base,
                  std::int32_t handle, std::int32_t cell, std::int32_t addon) {
    return witness->begin(nonce, fixtureBits(actor, base, handle, cell, addon), Scope::motion);
}
std::string beginFemale(RE::StaticFunctionTag*, std::int32_t nonce, std::int32_t actor, std::int32_t base,
                       std::int32_t handle, std::int32_t cell, std::int32_t addon) {
    return witness->begin(nonce, fixtureBits(actor, base, handle, cell, addon, true), Scope::femaleMotion);
}
template <Scope scope>
std::string beginWithMorphs(RE::StaticFunctionTag*, std::int32_t nonce, std::int32_t actor, std::int32_t base,
                            std::int32_t handle, std::int32_t cell, std::int32_t addon,
                            const std::vector<RE::BSFixedString> input) {
    std::vector<std::string> names;
    if (input.size() <= 32) {
        names.reserve(input.size());
        for (const auto& name : input) names.emplace_back(name.c_str() ? name.c_str() : "");
    }
    return witness->begin(nonce, fixtureBits(actor, base, handle, cell, addon), scope, std::move(names));
}
std::string sample(RE::StaticFunctionTag*, std::int32_t nonce, std::int32_t index) { return witness->sample(nonce, index); }
std::string read(RE::StaticFunctionTag*, std::int32_t nonce, std::int32_t index) { return witness->read(nonce, index); }
std::string readSnapshot(RE::StaticFunctionTag*, std::int32_t nonce, std::int32_t previous) {
    return witness->readSnapshot(nonce, previous);
}
std::string end(RE::StaticFunctionTag*, std::int32_t nonce) { return witness->end(nonce); }

bool registerPapyrus(RE::BSScript::IVirtualMachine* vm) {
    if (!vm) return false;
    vm->RegisterFunction("BeginNpc", name, begin);
    vm->RegisterFunction("BeginFemaleNpc", name, beginFemale);
    vm->RegisterFunction("BeginNpcWithMorphs", name, beginWithMorphs<Scope::effectiveMorphs>);
    vm->RegisterFunction("BeginNpcContact", name, beginWithMorphs<Scope::earTailSupport>);
    vm->RegisterFunction("BeginNpcTailRefit", name, beginWithMorphs<Scope::tailRefit>);
    vm->RegisterFunction("SampleNpc", name, sample);
    vm->RegisterFunction("ReadNpc", name, read);
    vm->RegisterFunction("ReadPhysicsSnapshot", name, readSnapshot);
    vm->RegisterFunction("EndNpc", name, end);
    return true;
}

void message(SKSE::MessagingInterface::Message* data) {
    if (!data) return;
    using Message = SKSE::MessagingInterface;
    switch (data->type) {
    case Message::kPostPostLoad: connectMorphSource(); break;
    case Message::kDataLoaded:
        witness->registerUnloads();
        witness->registerSnapshots();
        break;
    case Message::kPreLoadGame: witness->world(false); break;
    case Message::kNewGame: witness->world(true); break;
    case Message::kPostLoadGame:
        witness->world(claw::mayActivateWorld(claw::WorldStart::postLoadGame, data->dataLen,
                                              reinterpret_cast<std::uintptr_t>(data->data)));
        break;
    }
}

bool supported(const SKSE::QueryInterface* skse) {
    if (!skse) return false;
    const auto* target = claw::runtimeTargetFromQuery(skse->RuntimeVersion(), skse->SKSEVersion(), skse->IsEditor());
    return target && target->family == claw::RuntimeFamily::vr;
}
}

extern "C" __declspec(dllexport) bool SKSEPlugin_Query(const SKSE::QueryInterface* skse, SKSE::PluginInfo* info) {
    if (!info) return false;
    *info = {SKSE::PluginInfo::kVersion, name, 1};
    return supported(skse);
}

extern "C" __declspec(dllexport) bool SKSEPlugin_Load(const SKSE::LoadInterface* skse) {
    if (!supported(skse)) return false;
    try {
        SKSE::Init(skse, {.log = false});
        auto* papyrus = SKSE::GetPapyrusInterface();
        auto* messages = SKSE::GetMessagingInterface();
        if (!SKSE::GetTaskInterface() || !papyrus || !messages) return false;
        auto value = std::make_unique<Witness>();
        if (!value->setup()) return false;
        witness = value.get();
        if (!messages->RegisterListener(message)) {
            value->closeTimer();
            witness = nullptr;
            return false;
        }
        // After the listener is registered its context must survive even if VM registration refuses.
        value.release();
        return papyrus->Register(registerPapyrus);
    } catch (...) { return false; }
}
