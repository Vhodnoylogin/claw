// Test-only VR scene-graph observation. No model mutation or render hooks.
#include <RE/Skyrim.h>
#include "CullObservation.h"
#include "DispatchMarkerObservation.h"
#include <SKSE/SKSE.h>
#include <Windows.h>
#include <nlohmann/json.hpp>
#include "../../../main/cpp/include/claw/RuntimeSupport.h"
#include "../../../main/cpp/include/claw/TargetModelAvailability.h"
#include "../../../main/cpp/include/claw/WorldStartPolicy.h"
#include <chrono>
#include <cmath>
#include <cstddef>
#include <mutex>
#include <optional>
#include <stdexcept>
#include <vector>

#if !defined(SKYRIM_CROSS_VR)
#error Build with the same cross-runtime CommonLib ABI as the CLAW DLL.
#endif

namespace {
using Json = nlohmann::json;
using Object = RE::NiAVObject;
using Clock = std::chrono::steady_clock;
constexpr auto name = "CLAWVRModelTopology";
constexpr auto bodySlot = static_cast<std::size_t>(RE::BIPED_OBJECTS::kBody);
static_assert(bodySlot == 2);
constexpr std::size_t slotCount = RE::BIPED_OBJECTS::kTotal;
constexpr std::size_t maximumRoots = 48;
constexpr std::size_t requestLimit = 8;
constexpr auto lifetime = std::chrono::seconds(3);
constexpr std::size_t diagnosticMaxObjects = 4096, diagnosticMaxGeometries = 128;
constexpr std::size_t diagnosticMaxChildLinks = 2 * diagnosticMaxObjects;
constexpr std::size_t modelPathLimit = 260;
constexpr std::size_t maxShapeDetailsPerRoot = 16;
constexpr std::size_t shapeNameLimit = 64;
constexpr std::size_t ancestorDepthLimit = 16;
constexpr std::array<const char*, 12> vrRouteNames = {
    "playerWorld", "room", "heightOffset", "headset", "leftWand", "rightWand",
    "leftMeleeOffset", "rightMeleeOffset", "leftHand", "rightHand", "leftClavicle", "rightClavicle"
};

struct Refusal : std::runtime_error { using std::runtime_error::runtime_error; };

void require(bool condition, const char* reason) {
    if (!condition) throw Refusal(reason);
}

struct Slot {
    Object* clone{};
    RE::FormID item{}, addon{};
    std::string modelPath;
    bool partHandlePresent{};
    bool operator==(const Slot&) const = default;
};

using Slots = std::array<Slot, slotCount>;

struct View {
    RE::BSTSmartPointer<RE::BipedAnim> biped;
    Object* bipedRoot{};
    Slots active{}, buffered{};

    bool operator==(const View& other) const {
        return biped.get() == other.biped.get() && bipedRoot == other.bipedRoot &&
               active == other.active && buffered == other.buffered;
    }
};

std::string modelPath(const RE::TESModel* model) {
    if (!model) return {};
    const auto* value = model->GetModel();
    if (!value) return {};
    const auto length = strnlen_s(value, modelPathLimit);
    require(length < modelPathLimit, "selected biped model path exceeds diagnostic bound");
    return std::string(value, length);
}

Slots slots(const RE::BIPOBJECT (&source)[slotCount]) {
    Slots copy;
    for (std::size_t index = 0; index < slotCount; ++index) {
        const auto& part = source[index];
        copy[index] = {
            part.partClone.get(),
            part.item ? part.item->GetFormID() : 0,
            part.addon ? part.addon->GetFormID() : 0,
            modelPath(part.part),
            bool(part.partHandle),
        };
    }
    return copy;
}

View view(RE::Actor& actor, bool firstPerson) {
    auto biped = actor.GetBiped(firstPerson);
    if (!biped) return {};
    return {biped, biped->root, slots(biped->objects), slots(biped->bufferedObjects)};
}

struct Routes {
    std::array<Object*, 3> roots;
    std::array<View, 2> views;
    std::array<Object*, vrRouteNames.size()> vrRoots;
    bool operator==(const Routes&) const = default;
};

Routes routes(RE::PlayerCharacter& actor) {
    Routes result{{actor.Get3D(), actor.Get3D(false), actor.Get3D(true)},
                  {view(actor, false), view(actor, true)}, {}};
    if (const auto* vr = actor.GetVRNodeData()) {
        result.vrRoots = {vr->PlayerWorldNode.get(), vr->RoomNode.get(), vr->HeightOffsetNode.get(),
                         vr->HmdNode.get(), vr->LeftWandNode.get(), vr->RightWandNode.get(),
                         vr->LeftMeleeWeaponOffsetNode.get(), vr->RightMeleeWeaponOffsetNode.get(),
                         vr->NPCLHnd.get(), vr->NPCRHnd.get(),
                         vr->NPCLClv.get(), vr->NPCRClv.get()};
    }
    return result;
}

Json describeGeometry(RE::BSGeometry& shape) {
    const auto* name = shape.name.c_str();
    Json result = {{"name", name ? std::string(name, strnlen_s(name, shapeNameLimit)) : ""},
                   {"type", shape.GetType().underlying()}, {"appCulled", shape.GetAppCulled()}};
    if (const auto* tri = shape.AsTriShape()) {
        const auto& data = tri->GetTrishapeRuntimeData();
        result["vertices"] = data.vertexCount;
        result["triangles"] = data.triangleCount;
    }
    return result;
}

static_assert(offsetof(RE::NiAVObject, parent) == 0x30);
static_assert(offsetof(RE::TESCamera, currentState) == 0x28);
static_assert(offsetof(RE::TESCameraState, id) == 0x18);

using Cull = claw::vr_diagnostic::CullObservation<Object, ancestorDepthLimit>;

Cull collectCull(const Object& root) {
    return claw::vr_diagnostic::observeCull<ancestorDepthLimit>(root,
        [](const Object& object) -> const Object* { return object.parent; },
        [](const Object& object) { return object.GetAppCulled(); });
}

Json describeCull(const Cull& observation) {
    using claw::vr_diagnostic::ParentEnd;
    Json ancestors = Json::array();
    for (std::size_t i = 0; i < observation.ancestorCount; ++i)
        ancestors.push_back(observation.ancestorFlags[i]);
    const auto effective = observation.effective();
    const char* end = observation.end == ParentEnd::complete ? "complete" :
        observation.end == ParentEnd::depthLimit ? "depth_limit" : "cycle";
    return {{"root", observation.rootFlag}, {"ancestors", std::move(ancestors)},
            {"end", end}, {"effective", effective ? Json(*effective) : Json(nullptr)}};
}

struct CameraObservation {
    const RE::TESCameraState* state{};
    std::optional<std::uint32_t> id;
    bool operator==(const CameraObservation&) const = default;
};

CameraObservation readCamera() {
    const auto* camera = RE::PlayerCamera::GetSingleton();
    const auto* state = camera ? camera->currentState.get() : nullptr;
    return {state, state ? std::optional<std::uint32_t>(static_cast<std::uint32_t>(state->id)) : std::nullopt};
}

class Inventory {
public:
    std::size_t identify(Object* object) {
        if (!object) return 0;
        const auto found = std::find_if(leases.begin(), leases.end(),
            [object](const auto& lease) { return lease.get() == object; });
        if (found != leases.end()) return static_cast<std::size_t>(found - leases.begin()) + 1;
        require(leases.size() < maximumRoots, "distinct root limit");
        leases.emplace_back(object);
        return leases.size();
    }

    Json summarizeSlots(const Slots& values) {
        Json result = Json::array();
        for (std::size_t index = 0; index < values.size(); ++index) {
            const auto& slot = values[index];
            if (!slot.clone && !slot.item && !slot.addon && slot.modelPath.empty() && !slot.partHandlePresent)
                continue;
            result.push_back({{"slot", index}, {"clone", identify(slot.clone)},
                              {"item", slot.item}, {"addon", slot.addon}, {"modelPath", slot.modelPath},
                              {"partHandlePresent", slot.partHandlePresent}});
        }
        return result;
    }

    Json summarizeView(const View& actual) {
        return {{"available", bool(actual.biped)}, {"bipedRoot", identify(actual.bipedRoot)},
                {"active", summarizeSlots(actual.active)}, {"buffered", summarizeSlots(actual.buffered)}};
    }

    Json summarizeRoots(Clock::time_point deadline) const {
        Json result = Json::array();
        std::vector<Cull> culling;
        culling.reserve(leases.size());
        std::array<RE::BSFixedString, claw::targetModelRoles.size()> roles;
        for (std::size_t role = 0; role < roles.size(); ++role)
            roles[role] = RE::BSFixedString{claw::targetModelRoles[role].data()};
        for (std::size_t index = 0; index < leases.size(); ++index) {
            require(Clock::now() < deadline, "capture expired");
            culling.push_back(collectCull(*leases[index]));
            Json geometryDetails = Json::array();
            const auto actual = claw::collectTargetModel<
                diagnosticMaxObjects, diagnosticMaxGeometries, diagnosticMaxChildLinks>(
                leases[index].get(), [&](Object* object) {
                require(Clock::now() < deadline, "capture expired during graph walk");
                auto* geometry = object->AsGeometry();
                claw::TargetModelObject item{geometry != nullptr};
                if (geometry && geometryDetails.size() < maxShapeDetailsPerRoot)
                    geometryDetails.push_back(describeGeometry(*geometry));
                const auto match = std::find(roles.begin(), roles.end(), object->name);
                if (match != roles.end()) item.role = static_cast<std::size_t>(match - roles.begin());
                return item;
            }, [](Object* object, auto&& push) {
                if (const auto* node = object->AsNode())
                    for (const auto& child : node->GetChildren())
                        if (!push(child.get())) return false;
                return true;
            });
            result.push_back({{"id", index + 1}, {"objects", actual.objects},
                              {"geometries", actual.geometries}, {"childLinks", actual.childLinks},
                              {"collection", static_cast<unsigned>(actual.collection)},
                              {"appCull", describeCull(culling.back())},
                              {"roleObjects", actual.roleObjects}, {"roleGeometries", actual.roleGeometries},
                              {"geometryDetails", std::move(geometryDetails)},
                              {"geometryDetailsComplete", actual.collection == claw::TargetModelCollection::complete &&
                                  actual.geometries <= maxShapeDetailsPerRoot},
                              {"availability", static_cast<unsigned>(claw::targetModelAvailability(actual))}});
        }
        for (std::size_t index = 0; index < leases.size(); ++index) {
            require(Clock::now() < deadline, "capture expired during parent verification");
            require(collectCull(*leases[index]) == culling[index], "root parent chain or app-cull changed during capture");
        }
        return result;
    }

private:
    std::vector<RE::NiPointer<Object>> leases;
};

RE::FormID id(const RE::TESForm* value) { return value ? value->GetFormID() : 0; }

using claw::vr_diagnostic::Body32Forms;

std::optional<Body32Forms> resolvePlayerBody32Fixture() {
    constexpr auto fileName = "test_CLAW - VR Player Body32.esp";
    auto* data = RE::TESDataHandler::GetSingleton();
    if (!data) return std::nullopt;
    const auto* file = data->LookupModByName(fileName);
    if (!file) return std::nullopt;
    const auto* item = data->LookupForm<RE::TESObjectARMO>(0x801, fileName);
    const auto* addon = data->LookupForm<RE::TESObjectARMA>(0x800, fileName);
    if (!item || !addon || item->GetFile(0) != file || addon->GetFile(0) != file ||
        item->armorAddons.size() != 1 || item->armorAddons[0] != addon) return std::nullopt;
    return Body32Forms{id(item), id(addon)};
}

struct BodyMarkerRoute {
    Object* clone{};
    claw::vr_diagnostic::DispatchMarkers<Object> markers;
    std::string_view classification;
    bool traversed{};
    bool operator==(const BodyMarkerRoute&) const = default;
};

std::array<BodyMarkerRoute, 4> observeBodyMarkers(const Routes& scene, std::uint32_t handle,
                                                 const std::optional<Body32Forms>& fixture, Clock::time_point deadline) {
    using namespace claw::vr_diagnostic;
    std::array<BodyMarkerRoute, 4> result{};
    std::array<RE::BSFixedString, dispatchMarkerNames.size()> names;
    for (std::size_t i = 0; i < names.size(); ++i) names[i] = RE::BSFixedString{dispatchMarkerNames[i].data()};
    const auto linked = [](const RE::NiNode& parent, const Object* child) {
        return std::ranges::any_of(parent.GetChildren(), [child](const auto& current) {
            return current.get() == child;
        });
    };
    for (std::size_t i = 0; i < result.size(); ++i) {
        require(Clock::now() < deadline, "capture expired during Body32 marker observation");
        const auto viewIndex = i / 2;
        const auto& view = scene.views[viewIndex];
        const auto& slot = (i % 2 ? view.buffered : view.active)[bodySlot];
        auto& row = result[i];
        row.clone = slot.clone;
        if (!slot.clone) { row.classification = "unloaded"; continue; }
        if (!approvedBody32Forms({slot.item, slot.addon}, fixture) || !view.biped ||
            view.biped->actorRef.native_handle() != handle) {
            row.classification = "foreign_slot"; continue;
        }
        if (!belongsToGraph(slot.clone, scene.roots[viewIndex + 1], ancestorDepthLimit, linked)) {
            row.classification = "detached"; continue;
        }
        const auto earlier = std::find_if(result.begin(), result.begin() + i, [&](const auto& other) {
            return other.traversed && other.clone == row.clone;
        });
        if (earlier != result.begin() + i) { row = *earlier; continue; }
        const auto scan = claw::collectTargetModel<
            diagnosticMaxObjects, diagnosticMaxGeometries, diagnosticMaxChildLinks>(slot.clone,
            [&](Object* object) {
                require(Clock::now() < deadline, "capture expired during Body32 graph walk");
                const auto match = std::find(names.begin(), names.end(), object->name);
                if (match != names.end()) {
                    const auto* node = object->AsNode();
                    const bool valid = object != slot.clone && node && node->GetChildren().empty() &&
                        belongsToGraph(object, slot.clone, ancestorDepthLimit, linked);
                    row.markers.record(static_cast<std::size_t>(match - names.begin()), object, object->parent, valid);
                }
                return claw::TargetModelObject{object->AsGeometry() != nullptr};
            }, [](Object* object, auto&& push) {
                if (const auto* node = object->AsNode())
                    for (const auto& child : node->GetChildren())
                        if (!push(child.get())) return false;
                return true;
            });
        row.classification = row.markers.classify(scan.collection == claw::TargetModelCollection::complete);
        row.traversed = true;
    }
    return result;
}

std::int64_t qpc() {
    LARGE_INTEGER counter{};
    require(QueryPerformanceCounter(&counter) && counter.QuadPart > 0, "performance counter unavailable");
    return counter.QuadPart;
}

std::optional<float> actorWeight(const RE::TESNPC* actor) {
    if (!actor || !std::isfinite(actor->weight) || actor->weight < 0 || actor->weight > 100) return std::nullopt;
    return actor->weight;
}

Json collect(Clock::time_point deadline, bool dispatch) {
    auto* actor = RE::PlayerCharacter::GetSingleton();
    auto* ui = RE::UI::GetSingleton();
    require(actor && actor->GetFormID() == 0x14 && actor->Is3DLoaded() && ui &&
                !ui->IsMenuOpen(RE::LoadingMenu::MENU_NAME) &&
                !ui->IsMenuOpen(RE::MainMenu::MENU_NAME), "loaded player required");
    const auto handle = actor->GetHandle();
    const auto race = id(actor->GetRace());
    auto* actorBase = actor->GetActorBase();
    const auto base = id(actorBase);
    const auto cell = id(actor->GetParentCell());
    const auto weaponState = actor->GetWeaponState();
    require(handle && race == 0xCDD84 && base && cell, "loaded wolf owner required");
    const auto began = dispatch ? qpc() : 0;
    const auto sex = dispatch ? static_cast<int>(actorBase->GetSex()) : -1;
    const auto weight = dispatch ? actorWeight(actorBase) : std::nullopt;
    require(!dispatch || sex == 0 || sex == 1, "wolf NPC sex unavailable");
    const auto before = routes(*actor);
    const auto camera = readCamera();
    Inventory inventory;
    Json roots = {{"default", inventory.identify(before.roots[0])},
                  {"thirdPerson", inventory.identify(before.roots[1])},
                  {"firstPerson", inventory.identify(before.roots[2])}};
    Json views = {{"thirdPerson", inventory.summarizeView(before.views[0])},
                  {"firstPerson", inventory.summarizeView(before.views[1])}};
    Json vrRoots = Json::object();
    for (std::size_t i = 0; i < before.vrRoots.size(); ++i)
        vrRoots[vrRouteNames[i]] = inventory.identify(before.vrRoots[i]);
    auto rootDetails = inventory.summarizeRoots(deadline);
    Json markers;
    std::optional<Body32Forms> fixture;
    if (dispatch) {
        fixture = resolvePlayerBody32Fixture();
        const auto observation = observeBodyMarkers(before, handle.native_handle(), fixture, deadline);
        markers = Json::array();
        for (std::size_t i = 0; i < observation.size(); ++i) {
            const auto& row = observation[i];
            markers.push_back({{"view", i < 2 ? "thirdPerson" : "firstPerson"},
                {"bank", i % 2 ? "buffered" : "active"}, {"slot", bodySlot}, {"clone", inventory.identify(row.clone)},
                {"counts", row.markers.counts}, {"classification", row.classification}});
        }
        const auto recheckedFixture = resolvePlayerBody32Fixture();
        require(fixture == recheckedFixture, "player Body32 fixture pair changed during capture");
        require(observation == observeBodyMarkers(before, handle.native_handle(), recheckedFixture, deadline),
                "Body32 marker attachment changed during capture");
    }
    require(RE::PlayerCharacter::GetSingleton() == actor && actor->GetHandle() == handle &&
                id(actor->GetRace()) == race && id(actor->GetActorBase()) == base &&
                id(actor->GetParentCell()) == cell && actor->Is3DLoaded() &&
                before == routes(*actor) && actor->GetWeaponState() == weaponState && camera == readCamera(),
                "player, model route, or camera changed during capture");
    Json sample = {{"actor", 0x14}, {"race", race}, {"base", base}, {"cell", cell},
            {"roots", std::move(roots)}, {"views", std::move(views)}, {"vrRoots", std::move(vrRoots)},
            {"weaponState", static_cast<unsigned>(weaponState)},
            {"cameraStateId", camera.id ? Json(*camera.id) : Json(nullptr)},
            {"roles", claw::targetModelRoles}, {"distinctRoots", std::move(rootDetails)}};
    if (dispatch) {
        require(actor->GetActorBase() == actorBase && static_cast<int>(actorBase->GetSex()) == sex &&
                actorWeight(actorBase) == weight, "wolf sex or actor weight changed during capture");
        LARGE_INTEGER frequency{};
        const auto ended = qpc();
        require(QueryPerformanceFrequency(&frequency) && frequency.QuadPart > 0 && ended > began,
                "timing bracket unavailable");
        sample.update({{"body32Markers", std::move(markers)}, {"sex", sex}, {"weight", weight ? Json(*weight) : Json(nullptr)},
            {"runtimeHandle", handle.native_handle()}, {"qpcBegin", began}, {"qpcEnd", ended},
            {"playerBody32Fixture", fixture ? Json{{"item", fixture->item}, {"addon", fixture->addon}} : Json(nullptr)},
            {"qpcFrequency", frequency.QuadPart}});
    }
    return sample;
}

class Capture {
public:
    std::string request(std::int32_t nonce, bool dispatch = false) {
        std::unique_lock lock(mutex);
        if (nonce <= highest || busy || poisoned || loading || requests == requestLimit)
            return reply(nonce, dispatch, "refused", "busy, stale, loading or request limit").dump();
        const auto generation = epoch;
        highest = nonce;
        ++requests;
        busy = true;
        dispatch_ = dispatch;
        result.clear();
        deadline = Clock::now() + lifetime;
        const auto expires = deadline;
        lock.unlock();
        try {
            SKSE::GetTaskInterface()->AddTask([=, this] { run(nonce, generation, expires, dispatch); });
        } catch (...) {
            lock.lock();
            poisoned = true;
            result.clear();
            return reply(nonce, dispatch, "refused", "queue outcome unknown").dump();
        }
        return read(nonce);
    }

    std::string read(std::int32_t nonce) const {
        std::lock_guard lock(mutex);
        if (nonce <= 0 || nonce != highest || poisoned || loading)
            return reply(nonce, dispatch_, "refused", "stale nonce or world").dump();
        if (!result.empty()) return result;
        if (busy && Clock::now() < deadline) return reply(nonce, dispatch_, "pending").dump();
        return reply(nonce, dispatch_, "refused", "capture expired or invalidated").dump();
    }

    void loadingWorld(bool loadingNow) {
        std::lock_guard lock(mutex);
        ++epoch;
        loading = loadingNow;
        result.clear();
    }

private:
    static Json reply(std::int32_t nonce, bool dispatch, const char* status, const char* reason = "") {
        return {{"schema", dispatch ? "claw-vr-model-topology/8" : "claw-vr-model-topology/4"}, {"pid", GetCurrentProcessId()},
                {"nonce", nonce}, {"status", status}, {"reason", reason}};
    }

    void run(std::int32_t nonce, std::uint64_t generation, Clock::time_point expires, bool dispatch) {
        {
            std::lock_guard lock(mutex);
            if (epoch != generation || poisoned || loading || Clock::now() >= expires) {
                busy = false;
                return;
            }
        }
        std::string captured;
        try {
            auto response = reply(nonce, dispatch, "ready");
            response["epoch"] = generation;
            response["sample"] = collect(expires, dispatch);
            captured = response.dump(-1, ' ', true, Json::error_handler_t::replace);
            require(captured.size() <= 32768, "capture byte limit");
        } catch (const Refusal& error) {
            captured = reply(nonce, dispatch, "refused", error.what()).dump();
        } catch (...) {
            captured.clear();
        }
        std::lock_guard lock(mutex);
        if (epoch == generation && !poisoned && !loading && Clock::now() < expires)
            result = std::move(captured);
        busy = false;
    }

    mutable std::mutex mutex;
    std::uint64_t epoch{1};
    std::int32_t highest{};
    std::size_t requests{};
    bool busy{}, poisoned{}, loading{}, dispatch_{};
    Clock::time_point deadline{};
    std::string result;
};

Capture capture;
std::string request(RE::StaticFunctionTag*, std::int32_t nonce) { return capture.request(nonce); }
std::string requestDispatch(RE::StaticFunctionTag*, std::int32_t nonce) { return capture.request(nonce, true); }
std::string read(RE::StaticFunctionTag*, std::int32_t nonce) { return capture.read(nonce); }

bool registerPapyrus(RE::BSScript::IVirtualMachine* vm) {
    if (!vm) return false;
    vm->RegisterFunction("Capture", name, request);
    vm->RegisterFunction("CaptureDispatch", name, requestDispatch);
    vm->RegisterFunction("Read", name, read);
    return true;
}

void message(SKSE::MessagingInterface::Message* data) {
    if (!data) return;
    switch (data->type) {
    case SKSE::MessagingInterface::kPreLoadGame: capture.loadingWorld(true); break;
    case SKSE::MessagingInterface::kNewGame: capture.loadingWorld(false); break;
    case SKSE::MessagingInterface::kPostLoadGame:
        capture.loadingWorld(!claw::mayActivateWorld(claw::WorldStart::postLoadGame, data->dataLen,
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
        return SKSE::GetTaskInterface() && papyrus && messages &&
               messages->RegisterListener(message) && papyrus->Register(registerPapyrus);
    } catch (...) {
        return false;
    }
}
