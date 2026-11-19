// Test-only VR scene-graph observation. No model mutation or render hooks.
#include <RE/Skyrim.h>
#include <SKSE/SKSE.h>
#include <Windows.h>
#include <nlohmann/json.hpp>
#include "../../../main/cpp/include/claw/RuntimeSupport.h"
#include "../../../main/cpp/include/claw/TargetModelAvailability.h"
#include "../../../main/cpp/include/claw/WorldStartPolicy.h"
#include <chrono>
#include <mutex>
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
constexpr std::size_t slotCount = RE::BIPED_OBJECTS::kTotal;
constexpr std::size_t maximumRoots = 48;
constexpr std::size_t requestLimit = 8;
constexpr auto lifetime = std::chrono::seconds(3);
constexpr std::size_t diagnosticMaxObjects = 4096, diagnosticMaxGeometries = 128;
constexpr std::size_t diagnosticMaxChildLinks = 2 * diagnosticMaxObjects;
constexpr std::size_t modelPathLimit = 260;
constexpr std::size_t maxShapeDetailsPerRoot = 16;
constexpr std::size_t shapeNameLimit = 64;
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
        std::array<RE::BSFixedString, claw::targetModelRoles.size()> roles;
        for (std::size_t role = 0; role < roles.size(); ++role)
            roles[role] = RE::BSFixedString{claw::targetModelRoles[role].data()};
        for (std::size_t index = 0; index < leases.size(); ++index) {
            require(Clock::now() < deadline, "capture expired");
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
                              {"roleObjects", actual.roleObjects}, {"roleGeometries", actual.roleGeometries},
                              {"geometryDetails", std::move(geometryDetails)},
                              {"geometryDetailsComplete", actual.collection == claw::TargetModelCollection::complete &&
                                  actual.geometries <= maxShapeDetailsPerRoot},
                              {"availability", static_cast<unsigned>(claw::targetModelAvailability(actual))}});
        }
        return result;
    }

private:
    std::vector<RE::NiPointer<Object>> leases;
};

RE::FormID id(const RE::TESForm* value) { return value ? value->GetFormID() : 0; }

Json collect(Clock::time_point deadline) {
    auto* actor = RE::PlayerCharacter::GetSingleton();
    auto* ui = RE::UI::GetSingleton();
    require(actor && actor->GetFormID() == 0x14 && actor->Is3DLoaded() && ui &&
                !ui->IsMenuOpen(RE::LoadingMenu::MENU_NAME) &&
                !ui->IsMenuOpen(RE::MainMenu::MENU_NAME), "loaded player required");
    const auto handle = actor->GetHandle();
    const auto race = id(actor->GetRace());
    const auto base = id(actor->GetActorBase());
    const auto cell = id(actor->GetParentCell());
    const auto weaponState = actor->GetWeaponState();
    require(handle && race == 0xCDD84 && base && cell, "loaded wolf owner required");
    const auto before = routes(*actor);
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
    require(RE::PlayerCharacter::GetSingleton() == actor && actor->GetHandle() == handle &&
                id(actor->GetRace()) == race && id(actor->GetActorBase()) == base &&
                id(actor->GetParentCell()) == cell && actor->Is3DLoaded() &&
                before == routes(*actor) && actor->GetWeaponState() == weaponState,
                "player or model route changed during capture");
    return {{"actor", 0x14}, {"race", race}, {"base", base}, {"cell", cell},
            {"roots", std::move(roots)}, {"views", std::move(views)}, {"vrRoots", std::move(vrRoots)},
            {"weaponState", static_cast<unsigned>(weaponState)},
            {"roles", claw::targetModelRoles}, {"distinctRoots", std::move(rootDetails)}};
}

class Capture {
public:
    std::string request(std::int32_t nonce) {
        std::unique_lock lock(mutex);
        if (nonce <= highest || busy || poisoned || loading || requests == requestLimit)
            return reply(nonce, "refused", "busy, stale, loading or request limit").dump();
        const auto generation = epoch;
        highest = nonce;
        ++requests;
        busy = true;
        result.clear();
        deadline = Clock::now() + lifetime;
        const auto expires = deadline;
        lock.unlock();
        try {
            SKSE::GetTaskInterface()->AddTask([=, this] { run(nonce, generation, expires); });
        } catch (...) {
            lock.lock();
            poisoned = true;
            result.clear();
            return reply(nonce, "refused", "queue outcome unknown").dump();
        }
        return read(nonce);
    }

    std::string read(std::int32_t nonce) const {
        std::lock_guard lock(mutex);
        if (nonce <= 0 || nonce != highest || poisoned || loading)
            return reply(nonce, "refused", "stale nonce or world").dump();
        if (!result.empty()) return result;
        if (busy && Clock::now() < deadline) return reply(nonce, "pending").dump();
        return reply(nonce, "refused", "capture expired or invalidated").dump();
    }

    void loadingWorld(bool loadingNow) {
        std::lock_guard lock(mutex);
        ++epoch;
        loading = loadingNow;
        result.clear();
    }

private:
    static Json reply(std::int32_t nonce, const char* status, const char* reason = "") {
        return {{"schema", "claw-vr-model-topology/3"}, {"pid", GetCurrentProcessId()},
                {"nonce", nonce}, {"status", status}, {"reason", reason}};
    }

    void run(std::int32_t nonce, std::uint64_t generation, Clock::time_point expires) {
        {
            std::lock_guard lock(mutex);
            if (epoch != generation || poisoned || loading || Clock::now() >= expires) {
                busy = false;
                return;
            }
        }
        std::string captured;
        try {
            auto response = reply(nonce, "ready");
            response["epoch"] = generation;
            response["sample"] = collect(expires);
            captured = response.dump(-1, ' ', true, Json::error_handler_t::replace);
            require(captured.size() <= 32768, "capture byte limit");
        } catch (const Refusal& error) {
            captured = reply(nonce, "refused", error.what()).dump();
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
    bool busy{}, poisoned{}, loading{};
    Clock::time_point deadline{};
    std::string result;
};

Capture capture;
std::string request(RE::StaticFunctionTag*, std::int32_t nonce) { return capture.request(nonce); }
std::string read(RE::StaticFunctionTag*, std::int32_t nonce) { return capture.read(nonce); }

bool registerPapyrus(RE::BSScript::IVirtualMachine* vm) {
    if (!vm) return false;
    vm->RegisterFunction("Capture", name, request);
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
