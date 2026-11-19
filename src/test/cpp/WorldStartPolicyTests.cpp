#include "claw/WorldStartPolicy.h"
#undef NDEBUG
#include <array>
#include <cassert>
#include <iostream>

int main() {
    using Start = claw::WorldStart;
    // Raw SKSE message contracts: successful load, failed load, and malformed
    // post-load messages. An attempted load alone never admits an active world.
    struct Message { Start kind; std::uint32_t length; std::uintptr_t data; bool activates; };
    constexpr std::array messages{
        Message{Start::postLoadGame, 1, 0, false},
        Message{Start::postLoadGame, 1, 1, true},
        Message{Start::postLoadGame, 0, 0, false},
        Message{Start::postLoadGame, 0, 1, false},
        Message{Start::postLoadGame, 8, 1, false},
        Message{Start::postLoadGame, 1, 2, false},
        Message{Start::postLoadGame, 1, 0x1234, false},
        // New-game notification is independent of load result/quest presence.
        Message{Start::newGame, 0, 0, true},
        Message{Start::newGame, 8, 0x1234, true},
        Message{Start::newGame, 1, 0, true},
    };
    for (const auto& message : messages)
        assert(claw::mayActivateWorld(message.kind, message.length, message.data) == message.activates);

    // Actual dispatch casts bool to void*, emitting only 0/1. A real address is
    // malformed even when the boolean stored at that address happens to be true.
    const bool trueAtAddress = true;
    const auto nonnull = reinterpret_cast<std::uintptr_t>(&trueAtAddress);
    assert(!claw::mayActivateWorld(Start::postLoadGame, 1, nonnull));

    // A successful A -> failed B -> successful A sequence must admit only the
    // successful notifications; no prior success is sticky across an attempt.
    constexpr std::array results{std::uintptr_t{1}, std::uintptr_t{0}, std::uintptr_t{1}};
    unsigned admitted{};
    for (const auto result : results) admitted += claw::mayActivateWorld(Start::postLoadGame, 1, result);
    assert(admitted == 2);

    using Policy = claw::InitialWorldPolicy;
    using Menu = claw::InitialWorldMenu;
    using Stage = claw::InitialWorldStage;
    using Disarm = claw::InitialWorldDisarm;
    using Check = claw::InitialWorldCheck;
    const auto menus = [](Policy& policy) {
        policy.menu(Menu::main, true); policy.menu(Menu::main, false);
        policy.menu(Menu::loading, true); policy.menu(Menu::loading, false);
    };
    const claw::InitialWorldObservation world{
        .epoch = 17, .player = 0x1000, .cell = 0x2000, .playerRoot = 0x3000, .worldRoot = 0x4000,
        .playerForm = 0x14, .cellForm = 0x123, .vr = true, .uiAvailable = true,
        .blockedMenu = false, .cellAttached = true, .cellIdentified = true, .playroom = false
    };
    const auto observe = [](Policy& policy, const auto& value) { return policy.observe(value, policy.revision(), true); };

    // VR bootstrap Loading events, close-only events and loading that begins
    // before Main closes never establish the required ordered transition.
    {
        Policy policy;
        policy.menu(Menu::loading, true); policy.menu(Menu::loading, false);
        policy.menu(Menu::main, false);
        assert(policy.stage() == Stage::awaitingMain);
        assert(observe(policy, world) == Check::awaitingMenus);
        policy.menu(Menu::main, true);
        policy.menu(Menu::loading, true); policy.menu(Menu::loading, false);
        assert(policy.stage() == Stage::mainOpen);
        policy.menu(Menu::main, false); policy.menu(Menu::loading, false);
        assert(policy.stage() == Stage::mainClosed);
        assert(observe(policy, world) == Check::awaitingMenus);
        policy.menu(Menu::loading, true);
        assert(observe(policy, world) == Check::awaitingMenus);
        const auto staleRevision = policy.revision();
        policy.menu(Menu::loading, false);
        assert(policy.observe(world, staleRevision, true) == Check::stale);
        assert(observe(policy, world) == Check::firstObservation);
        assert(!policy.commit(world, policy.revision(), true)); // One observation cannot commit.
        assert(observe(policy, world) == Check::firstObservation);
        assert(observe(policy, world) == Check::ready);
        assert(policy.commit(world, policy.revision(), true));
        assert(policy.disarmReason() == Disarm::committed);
        assert(!policy.commit(world, policy.revision(), true));
        menus(policy);
        assert(observe(policy, world) == Check::disarmed); // No second session from menu events.
    }

    // Each eligibility predicate fails closed and breaks the consecutive pair.
    // These are independent physical identities/readiness facts, not a status
    // getter or a test-cell allowlist.
    struct Block { claw::InitialWorldObservation value; Check reason; };
    std::array<Block, 12> blocks;
    for (auto& block : blocks) block.value = world;
    blocks[0].value.vr = false; blocks[0].reason = Check::notVR;
    blocks[1].value.uiAvailable = false; blocks[1].reason = Check::noUI;
    blocks[2].value.blockedMenu = true; blocks[2].reason = Check::blockedMenu;
    blocks[3].value.worldRoot = 0; blocks[3].reason = Check::noWorldRoot;
    blocks[4].value.player = 0; blocks[4].reason = Check::noPlayer;
    blocks[5].value.playerForm = 0x15; blocks[5].reason = Check::wrongPlayer;
    blocks[6].value.cell = 0; blocks[6].reason = Check::unloadedCell;
    blocks[7].value.cellForm = 0; blocks[7].reason = Check::unloadedCell;
    blocks[8].value.cellAttached = false; blocks[8].reason = Check::unloadedCell;
    blocks[9].value.cellIdentified = false; blocks[9].reason = Check::unidentifiedCell;
    blocks[10].value.playroom = true; blocks[10].reason = Check::playroom;
    blocks[11].value.playerRoot = 0; blocks[11].reason = Check::unloaded3D;
    for (const auto& block : blocks) {
        Policy policy; menus(policy);
        assert(observe(policy, world) == Check::firstObservation);
        assert(observe(policy, block.value) == block.reason);
        assert(!policy.commit(block.value, policy.revision(), true));
        assert(observe(policy, world) == Check::firstObservation);
        assert(observe(policy, world) == Check::ready);
        assert(policy.commit(world, policy.revision(), true));
    }

    std::array<claw::InitialWorldObservation, 6> changed;
    changed.fill(world);
    ++changed[0].epoch; ++changed[1].player; ++changed[2].cell;
    ++changed[3].playerRoot; ++changed[4].worldRoot; ++changed[5].cellForm;
    for (const auto& replacement : changed) {
        Policy policy; menus(policy);
        assert(observe(policy, world) == Check::firstObservation);
        assert(observe(policy, replacement) == Check::firstObservation);
        assert(observe(policy, world) == Check::firstObservation);
        assert(observe(policy, world) == Check::ready);
        assert(!policy.commit(replacement, policy.revision(), true)); // Fresh read must still match.
        assert(observe(policy, world) == Check::firstObservation);
    }

    // Both the original epoch/run ownership and policy revision must remain
    // current. A refusal resets the pair, even if identities match later.
    for (const bool current : {false, true}) {
        Policy policy; menus(policy);
        assert(!policy.commit(world, policy.revision(), true));
        assert(observe(policy, world) == Check::firstObservation);
        assert(observe(policy, world) == Check::ready);
        const auto revision = policy.revision() + (current ? 1 : 0);
        assert(policy.observe(world, revision, current) == Check::stale);
        assert(!policy.commit(world, revision, current));
        assert(observe(policy, world) == Check::firstObservation);
    }

    constexpr std::array disarms{Disarm::preLoad, Disarm::serializationLoad, Disarm::revert,
        Disarm::refusedPostLoad, Disarm::authoritativeWorld};
    for (const auto reason : disarms) for (const unsigned observations : {0U, 1U, 2U}) {
        Policy policy;
        // Zero models callbacks before DataLoaded/menu registration. There is
        // deliberately no DataLoaded/rearm operation in the pure policy.
        if (observations) menus(policy);
        if (observations >= 1) assert(observe(policy, world) == Check::firstObservation);
        if (observations == 2) assert(observe(policy, world) == Check::ready);
        assert(policy.disarm(reason));
        assert(!policy.disarm(Disarm::none));
        assert(!policy.disarm(Disarm::authoritativeWorld));
        menus(policy);
        assert(!policy.pending());
        assert(policy.disarmReason() == reason);
        assert(observe(policy, world) == Check::disarmed);
        assert(!policy.commit(world, policy.revision(), true));
    }
    for (const auto menu : {Menu::main, Menu::loading}) {
        Policy policy; menus(policy);
        assert(observe(policy, world) == Check::firstObservation);
        assert(observe(policy, world) == Check::ready);
        policy.menu(menu, true);
        assert(policy.disarmReason() == Disarm::menuRestart);
        menus(policy);
        assert(!policy.commit(world, policy.revision(), true));
        assert(observe(policy, world) == Check::disarmed);
    }
    // An authoritative successful message can still activate after fallback
    // refusal; the existing strict load-result contract remains independent.
    assert(claw::mayActivateWorld(Start::newGame, 8, 0x1234));
    assert(claw::mayActivateWorld(Start::postLoadGame, 1, 1));
    assert(!claw::mayActivateWorld(Start::postLoadGame, 1, 0));
    std::cout << "World start message contracts and conservative initial VR policy passed\n";
}
