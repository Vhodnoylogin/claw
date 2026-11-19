#pragma once
#include <cstdint>

namespace claw {
enum class WorldStart { newGame, postLoadGame };

// SKSE SE/AE/VR encodes the returned LoadGame bool in the pointer VALUE,
// dataLen=1: 0 is failure, 1 is success. It is not bool* storage.
// NewGame instead carries a quest pointer and has no load-success payload.
constexpr bool mayActivateWorld(WorldStart start, std::uint32_t dataLength, std::uintptr_t dataValue) {
    return start == WorldStart::newGame ||
        (start == WorldStart::postLoadGame && dataLength == 1 && dataValue == 1);
}

enum class InitialWorldMenu { main, loading };
enum class InitialWorldStage { awaitingMain, mainOpen, mainClosed, loadingOpen, complete };
enum class InitialWorldDisarm {
    none, preLoad, serializationLoad, revert, refusedPostLoad, authoritativeWorld, menuRestart, committed
};
enum class InitialWorldCheck {
    disarmed, stale, awaitingMenus, notVR, noUI, blockedMenu,
    noWorldRoot, noPlayer, wrongPlayer, unloadedCell, unidentifiedCell, playroom, unloaded3D,
    firstObservation, ready
};

constexpr const char* initialWorldName(InitialWorldStage value) {
    switch (value) {
    case InitialWorldStage::awaitingMain: return "awaiting-main";
    case InitialWorldStage::mainOpen: return "main-open";
    case InitialWorldStage::mainClosed: return "main-closed";
    case InitialWorldStage::loadingOpen: return "loading-open";
    case InitialWorldStage::complete: return "menu-transition-complete";
    }
    return "unknown";
}
constexpr const char* initialWorldName(InitialWorldDisarm value) {
    switch (value) {
    case InitialWorldDisarm::none: return "none";
    case InitialWorldDisarm::preLoad: return "pre-load";
    case InitialWorldDisarm::serializationLoad: return "serialization-load";
    case InitialWorldDisarm::revert: return "revert";
    case InitialWorldDisarm::refusedPostLoad: return "refused-post-load";
    case InitialWorldDisarm::authoritativeWorld: return "authoritative-world";
    case InitialWorldDisarm::menuRestart: return "menu-restart";
    case InitialWorldDisarm::committed: return "committed";
    }
    return "unknown";
}
constexpr const char* initialWorldName(InitialWorldCheck value) {
    switch (value) {
    case InitialWorldCheck::disarmed: return "disarmed";
    case InitialWorldCheck::stale: return "stale";
    case InitialWorldCheck::awaitingMenus: return "awaiting-menu-transition";
    case InitialWorldCheck::notVR: return "not-vr";
    case InitialWorldCheck::noUI: return "ui-unavailable";
    case InitialWorldCheck::blockedMenu: return "blocking-menu";
    case InitialWorldCheck::noWorldRoot: return "world-root-unavailable";
    case InitialWorldCheck::noPlayer: return "player-unavailable";
    case InitialWorldCheck::wrongPlayer: return "wrong-player";
    case InitialWorldCheck::unloadedCell: return "cell-unloaded";
    case InitialWorldCheck::unidentifiedCell: return "cell-unidentified";
    case InitialWorldCheck::playroom: return "vr-playroom";
    case InitialWorldCheck::unloaded3D: return "player-3d-unloaded";
    case InitialWorldCheck::firstObservation: return "awaiting-matching-observation";
    case InitialWorldCheck::ready: return "ready";
    }
    return "unknown";
}

// Opaque identities only. The adapter reads these on the main task, never on
// the timer or menu callback. Equality means two matching observations, not
// continuous world readiness between them.
struct InitialWorldObservation {
    std::uint64_t epoch{};
    std::uintptr_t player{}, cell{}, playerRoot{}, worldRoot{};
    std::uint32_t playerForm{}, cellForm{};
    bool vr{}, uiAvailable{}, blockedMenu{}, cellAttached{}, cellIdentified{}, playroom{};
    bool operator==(const InitialWorldObservation&) const = default;
};

// A process's initial VR world can lack the quest-specific NewGame message.
// This fallback is deliberately unavailable after any load/revert uncertainty.
// DataLoaded and menu reopening cannot reset or rearm it.
class InitialWorldPolicy {
public:
    constexpr bool pending() const { return disarm_ == InitialWorldDisarm::none; }
    constexpr InitialWorldStage stage() const { return stage_; }
    constexpr InitialWorldDisarm disarmReason() const { return disarm_; }
    constexpr std::uint64_t revision() const { return revision_; }

    constexpr bool disarm(InitialWorldDisarm reason) {
        if (!pending() || reason == InitialWorldDisarm::none) return false;
        disarm_ = reason;
        changed();
        return true;
    }
    constexpr void menu(InitialWorldMenu menu, bool opening) {
        if (!pending()) return;
        if (menu == InitialWorldMenu::main) {
            if (opening) {
                if (stage_ == InitialWorldStage::awaitingMain) {
                    stage_ = InitialWorldStage::mainOpen; changed();
                } else if (stage_ != InitialWorldStage::mainOpen) {
                    disarm(InitialWorldDisarm::menuRestart);
                }
            } else if (stage_ == InitialWorldStage::mainOpen) {
                stage_ = InitialWorldStage::mainClosed; changed();
            }
        } else if (opening && stage_ == InitialWorldStage::mainClosed) {
            stage_ = InitialWorldStage::loadingOpen; changed();
        } else if (!opening && stage_ == InitialWorldStage::loadingOpen) {
            stage_ = InitialWorldStage::complete; changed();
        } else if (opening && stage_ == InitialWorldStage::complete) {
            disarm(InitialWorldDisarm::menuRestart);
        }
        // VR bootstrap can open/close Loading Menu before Main Menu. Those
        // events never satisfy the required post-main loading transition.
    }

    constexpr InitialWorldCheck observe(const InitialWorldObservation& value, std::uint64_t revision, bool current) {
        const auto result = check(value, revision, current);
        if (result != InitialWorldCheck::ready) { matches_ = 0; return result; }
        if (!matches_ || value != previous_) { previous_ = value; matches_ = 1; return InitialWorldCheck::firstObservation; }
        matches_ = 2;
        return InitialWorldCheck::ready;
    }
    // The adapter refreshes the engine snapshot outside its locks, then checks
    // the original epoch and this revision again while committing actor state.
    constexpr bool commit(const InitialWorldObservation& refreshed, std::uint64_t revision, bool current) {
        if (check(refreshed, revision, current) != InitialWorldCheck::ready || matches_ != 2 || refreshed != previous_) {
            matches_ = 0;
            return false;
        }
        return disarm(InitialWorldDisarm::committed);
    }

private:
    constexpr void changed() { ++revision_; matches_ = 0; }
    constexpr InitialWorldCheck check(const InitialWorldObservation& value, std::uint64_t revision, bool current) const {
        if (!pending()) return InitialWorldCheck::disarmed;
        if (!current || revision != revision_) return InitialWorldCheck::stale;
        if (stage_ != InitialWorldStage::complete) return InitialWorldCheck::awaitingMenus;
        if (!value.vr) return InitialWorldCheck::notVR;
        if (!value.uiAvailable) return InitialWorldCheck::noUI;
        if (value.blockedMenu) return InitialWorldCheck::blockedMenu;
        if (!value.worldRoot) return InitialWorldCheck::noWorldRoot;
        if (!value.player) return InitialWorldCheck::noPlayer;
        if (value.playerForm != 0x14) return InitialWorldCheck::wrongPlayer;
        if (!value.cell || !value.cellForm || !value.cellAttached) return InitialWorldCheck::unloadedCell;
        if (!value.cellIdentified) return InitialWorldCheck::unidentifiedCell;
        if (value.playroom) return InitialWorldCheck::playroom;
        if (!value.playerRoot) return InitialWorldCheck::unloaded3D;
        return InitialWorldCheck::ready;
    }
    InitialWorldStage stage_{InitialWorldStage::awaitingMain};
    InitialWorldDisarm disarm_{InitialWorldDisarm::none};
    std::uint64_t revision_{};
    unsigned matches_{};
    InitialWorldObservation previous_;
};
}
