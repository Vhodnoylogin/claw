// One owned NPC's process-local CBPC ModCallbackEvent observation.
#include <RE/Skyrim.h>
#include <SKSE/SKSE.h>
#include <Windows.h>
#include <nlohmann/json.hpp>
#include <bit>
#include <mutex>
#include <optional>
#include "Window.h"
#include "claw/RuntimeSupport.h"
#include "claw/WorldStartPolicy.h"

#if !defined(SKYRIM_CROSS_VR)
#error Build with the retained cross-runtime CommonLib ABI.
#endif

namespace {
using Json = nlohmann::json;
using cbpc::State;
constexpr auto plugin = "CLAWVRCBPCEvents";
constexpr auto schema = "claw-vr-cbpc-events/1";
constexpr auto fixture = "test_CLAW - VR CBPC Contact Fixture.esp";
constexpr RE::FormID fixtureLocalBase = 0x800;

std::optional<cbpc::Window> window;
std::mutex gate;

cbpc::Ticks counter() {
    LARGE_INTEGER tick{};
    return QueryPerformanceCounter(&tick) && tick.QuadPart > 0 ? static_cast<cbpc::Ticks>(tick.QuadPart) : 0;
}

const char* status(State state) {
    switch (state) {
    case State::idle: return "idle";
    case State::pending: return "pending";
    case State::armed: return "armed";
    case State::sealed: return "sealed";
    case State::refused: return "refused_identity";
    case State::expired: return "expired";
    case State::changedWorld: return "changed_world";
    case State::clockInvalid: return "clock_invalid";
    }
    return "unavailable";
}

RE::FormID id(const RE::TESForm* form) { return form ? form->GetFormID() : 0; }

std::pair<RE::FormID, std::uintptr_t> observeSubject(cbpc::Key key) {
    auto* ui = RE::UI::GetSingleton();
    if (!ui || ui->IsMenuOpen(RE::LoadingMenu::MENU_NAME) || ui->IsMenuOpen(RE::MainMenu::MENU_NAME))
        return {};
    auto* handler = RE::TESDataHandler::GetSingleton();
    auto* base = handler ? handler->LookupForm<RE::TESNPC>(fixtureLocalBase, fixture) : nullptr;
    auto* actor = RE::TESForm::LookupByID<RE::Actor>(key.actor);
    auto* player = RE::PlayerCharacter::GetSingleton();
    auto* cell = player ? player->GetParentCell() : nullptr;
    if (!base || !cell || id(cell) != key.cell || !cell->IsAttached() ||
        !player->Is3DLoaded() || !actor || actor == player || id(actor) != key.actor ||
        actor->GetActorBase() != base || actor->GetParentCell() != cell ||
        actor->IsDisabled() || actor->IsDeleted() || !actor->Is3DLoaded() || !actor->Get3D(false))
        return {};
    return {id(base), reinterpret_cast<std::uintptr_t>(static_cast<const RE::TESForm*>(actor))};
}

bool arm(RE::StaticFunctionTag*, std::int32_t nonce, std::int32_t generation, std::int32_t actor, std::int32_t cell) {
    if (nonce <= 0 || generation <= 0) return false;
    const cbpc::Key key{static_cast<std::uint32_t>(nonce), static_cast<std::uint32_t>(generation),
                        std::bit_cast<std::uint32_t>(actor), std::bit_cast<std::uint32_t>(cell)};
    try {
        {
            std::lock_guard lock(gate);
            if (!window->request(key, counter())) return false;
        }
        SKSE::GetTaskInterface()->AddTask([key] {
            std::pair<RE::FormID, std::uintptr_t> subject;
            try { subject = observeSubject(key); }
            catch (...) { subject = {}; }
            std::lock_guard lock(gate);
            window->activate(key, subject.first, subject.second, counter());
        });
        return true;
    } catch (...) {
        std::lock_guard lock(gate);
        window->activate(key, 0, 0, counter());
        return false;
    }
}

bool seal(RE::StaticFunctionTag*, std::int32_t nonce, std::int32_t generation) {
    if (nonce <= 0 || generation <= 0) return false;
    std::lock_guard lock(gate);
    return window->seal(static_cast<std::uint32_t>(nonce), static_cast<std::uint32_t>(generation), counter());
}

std::string getState(RE::StaticFunctionTag*) {
    std::uint32_t generation{};
    bool registered{}, loading{};
    State state;
    {
        std::lock_guard lock(gate);
        window->tick(counter());
        generation = window->generation();
        state = window->state();
        registered = window->hasSink();
        loading = window->isLoading();
    }
    return Json({{"schema", schema}, {"pid", GetCurrentProcessId()}, {"generation", generation},
                 {"status", status(state)}, {"sinkRegistered", registered}, {"loading", loading}}).dump();
}

std::string read(RE::StaticFunctionTag*, std::int32_t nonce, std::int32_t generation) {
    if (nonce <= 0 || generation <= 0) return {};
    std::optional<cbpc::Snapshot> captured;
    {
        std::lock_guard lock(gate);
        window->tick(counter());
        const auto* snapshot = window->read(static_cast<std::uint32_t>(nonce), static_cast<std::uint32_t>(generation));
        if (snapshot) captured = *snapshot;
    }
    if (!captured) return {};
    const auto& s = *captured;
    auto events = Json::array();
    for (std::size_t i = 0; i < s.count; ++i) {
        const auto& row = s.events[i];
        events.push_back({{"sequence", row.sequence}, {"qpc", row.qpc}, {"eventName", cbpc::name(row.type)},
                          {"senderFormId", s.key.actor}, {"strArg", std::string_view(row.bone.data(), row.boneSize)},
                          {"numArg", row.number}});
    }
    return Json({{"schema", schema}, {"pid", GetCurrentProcessId()}, {"status", status(s.state)},
                 {"nonce", s.key.nonce}, {"generation", s.key.generation}, {"actorFormId", s.key.actor},
                 {"baseFormId", s.base}, {"cellFormId", s.key.cell}, {"qpcFrequency", s.frequency},
                 {"requestedQpc", s.requestedQpc}, {"armedQpc", s.armedQpc}, {"closedQpc", s.closedQpc},
                 {"lastSequence", s.sequence}, {"dropped", s.dropped}, {"unattributed", s.unattributed},
                 {"sealedWithoutLocalDrops", s.state == State::sealed && s.dropped == 0},
                 {"observation", "skse_mod_callback"}, {"events", std::move(events)}}).dump();
}

class Listener final : public RE::BSTEventSink<SKSE::ModCallbackEvent> {
    RE::BSEventNotifyControl ProcessEvent(const SKSE::ModCallbackEvent* event,
        RE::BSTEventSource<SKSE::ModCallbackEvent>*) override {
        if (event) {
            const auto type = cbpc::kind({event->eventName.c_str(), event->eventName.length()});
            if (type != cbpc::Kind::other) {
                std::lock_guard lock(gate);
                window->observe(type, id(event->sender), reinterpret_cast<std::uintptr_t>(event->sender),
                                {event->strArg.c_str(), event->strArg.length()}, event->numArg, counter());
            }
        }
        return RE::BSEventNotifyControl::kContinue;
    }
} listener;

void message(SKSE::MessagingInterface::Message* data) {
    if (!data) return;
    std::lock_guard lock(gate);
    using Message = SKSE::MessagingInterface;
    switch (data->type) {
    case Message::kDataLoaded:
        if (!window->hasSink()) {
            if (auto* source = SKSE::GetModCallbackEventSource()) {
                source->AddEventSink(&listener);
                window->sinkReady();
            }
        }
        break;
    case Message::kPreLoadGame: window->world(false, counter()); break;
    case Message::kNewGame: window->world(true, counter()); break;
    case Message::kPostLoadGame:
        window->world(claw::mayActivateWorld(claw::WorldStart::postLoadGame, data->dataLen,
                                            reinterpret_cast<std::uintptr_t>(data->data)), counter());
        break;
    }
}

bool registerPapyrus(RE::BSScript::IVirtualMachine* vm) {
    if (!vm) return false;
    vm->RegisterFunction("GetCaptureState", plugin, getState);
    vm->RegisterFunction("Arm", plugin, arm);
    vm->RegisterFunction("Seal", plugin, seal);
    vm->RegisterFunction("Read", plugin, read);
    return true;
}

bool supported(const SKSE::QueryInterface* skse) {
    if (!skse) return false;
    const auto* target = claw::runtimeTargetFromQuery(skse->RuntimeVersion(), skse->SKSEVersion(), skse->IsEditor());
    return target && target->family == claw::RuntimeFamily::vr;
}
}

extern "C" __declspec(dllexport) bool SKSEPlugin_Query(const SKSE::QueryInterface* skse, SKSE::PluginInfo* info) {
    if (!info) return false;
    *info = {SKSE::PluginInfo::kVersion, plugin, 1};
    return supported(skse);
}

extern "C" __declspec(dllexport) bool SKSEPlugin_Load(const SKSE::LoadInterface* skse) {
    if (!supported(skse)) return false;
    try {
        SKSE::Init(skse, {.log = false});
        auto* papyrus = SKSE::GetPapyrusInterface();
        auto* messages = SKSE::GetMessagingInterface();
        LARGE_INTEGER frequency{};
        if (!papyrus || !messages || !SKSE::GetTaskInterface() ||
            !QueryPerformanceFrequency(&frequency) || frequency.QuadPart <= 0) return false;
        window.emplace(static_cast<cbpc::Ticks>(frequency.QuadPart));
        return messages->RegisterListener(message) && papyrus->Register(registerPapyrus);
    } catch (...) {
        return false;
    }
}
