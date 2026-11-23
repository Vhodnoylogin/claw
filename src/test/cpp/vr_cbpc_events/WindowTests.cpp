#include "Window.h"
#include <iostream>
#include <source_location>
#include <stdexcept>
#include <string>

namespace {
using namespace cbpc;
constexpr Key key{109, 1, 0xFF000123, 0x0A01A5C6};
constexpr std::uint32_t base = 0x0B000800;
constexpr std::uintptr_t owner = 37;
constexpr Ticks initial = 1000;
constexpr Ticks frequency = 100;

void require(bool condition, const std::source_location& location = std::source_location::current()) {
    if (!condition)
        throw std::runtime_error("CBPC witness control failed at line " + std::to_string(location.line()));
}

const Snapshot& terminal(const Window& window, std::uint32_t generation = key.generation) {
    const auto* snapshot = window.read(key.nonce, generation);
    require(snapshot != nullptr);
    return *snapshot;
}

Window armed() {
    Window window(frequency);
    window.sinkReady();
    require(window.request(key, initial));
    require(window.activate(key, base, owner, initial + 1));
    return window;
}

void readinessAndSingleArm() {
    Window window(frequency);
    require(!window.request(key, initial));
    window.sinkReady();
    for (const auto bad : {Key{}, Key{0,1,key.actor,key.cell}, Key{1,2,key.actor,key.cell},
                            Key{1,1,0x14,key.cell}, Key{1,1,0xFE000901,key.cell},
                            Key{1,1,0xFFFFFFFFu,key.cell}, Key{1,1,key.actor,0}}) {
        require(!window.request(bad, initial));
    }
    require(!window.request(key, 0));
    require(!window.request(key, std::numeric_limits<Ticks>::max() - frequency));
    require(window.request(key, initial));
    require(window.state() == State::pending);
    require(!window.request({103,1,key.actor,key.cell}, initial + 1));
    require(!window.seal(key.nonce, key.generation, initial + 1));
    require(!window.read(key.nonce, key.generation));
    require(!window.activate({103,1,key.actor,key.cell}, base, owner, initial + 2));
    require(window.activate(key, base, owner, initial + 3));
    require(window.state() == State::armed);
}

void exactSenderAndPayload() {
    auto window = armed();
    require(kind("CBPCPlayerCollisionWithFemaleEvent") == Kind::female);
    require(kind("CBPCPlayerCollisionWithMaleEvent") == Kind::male);
    require(kind("cbpcPlayerCollisionWithMaleEvent") == Kind::other);
    require(kind("PlayerCollision") == Kind::other);
    window.observe(Kind::other, key.actor, owner, "TailBone01", .3f, initial + 2);
    window.observe(Kind::male, 0xFF000124, 39, "TailBone01", .3f, initial + 3);
    std::string bone("TailBone01");
    window.observe(Kind::male, key.actor, owner, bone, .31f, initial + 4);
    bone[4] = 'T';
    window.observe(Kind::female, key.actor, owner, "NPC EarL [EarL]Bone01", .61f, initial + 4);
    require(!window.seal(key.nonce, key.generation + 1, initial + 5));
    require(window.seal(key.nonce, key.generation, initial + 6));
    const auto* captured = window.read(key.nonce, key.generation);
    require(captured && captured->base == base && captured->key == key);
    require(captured->requestedQpc == initial && captured->frequency == frequency &&
           captured->armedQpc == initial + 1 && captured->closedQpc == initial + 6);
    require(captured->sequence == 2 && captured->count == 2 && captured->dropped == 0);
    const auto& first = captured->events[0];
    require(first.qpc == initial + 4 && first.sequence == 1 && first.type == Kind::male && first.number == .31f);
    require(std::string_view(first.bone.data(), first.boneSize) == "TailBone01");
    require(captured->events[1].type == Kind::female && captured->events[1].number == .61f);
}

void wrongKeysAndSealedImmutability() {
    auto window = armed();
    require(!window.read(key.nonce, key.generation));
    require(!window.seal(key.nonce + 1, key.generation, initial + 2));
    require(window.seal(key.nonce, key.generation, initial + 3));
    const auto sealed = terminal(window);
    require(sealed.state == State::sealed && sealed.count == 0);
    require(!window.read(key.nonce, key.generation + 1));
    require(!window.read(key.nonce + 1, key.generation));
    window.observe(Kind::male, key.actor, owner, "TailBone01", .3f, initial + 10);
    require(!window.seal(key.nonce, key.generation, initial + 11));
    window.world(false, initial + 12);
    require(!window.request({key.nonce + 1, 2, key.actor, key.cell}, initial + 13));
    require(terminal(window) == sealed);
}

void reasonOnBadIdentityOrWorldChange() {
    Window window(frequency);
    window.sinkReady();
    window.world(false, initial);
    require(window.isLoading() && window.generation() == 2);
    require(!window.request({key.nonce, 2, key.actor, key.cell}, initial + 1));
    window.world(true, initial + 2);
    const Key newKey{key.nonce, 3, key.actor, key.cell};
    require(window.request(newKey, initial + 3));
    require(!window.activate(newKey, base, 0, initial + 4));
    require(terminal(window, 3).state == State::refused);

    for (const auto phase : {State::pending, State::armed}) {
        Window current(frequency);
        current.sinkReady();
        require(current.request(key, initial));
        if (phase == State::armed) require(current.activate(key, base, owner, initial + 1));
        current.world(false, initial + 2);
        require(!current.seal(key.nonce, 1, initial + 3));
        require(!current.activate(key, base, owner, initial + 4));
        require(terminal(current).state == State::changedWorld);
        require(!current.read(key.nonce, 2));
    }
}

void boundAndUnattributedDrops() {
    auto window = armed();
    window.observe(Kind::male, key.actor, owner + 1, "TailBone01", .3f, initial + 2);
    window.observe(Kind::female, 0, 0, "TailBone01", .3f, initial + 3);
    std::string oversized(maxBone + 1, 'a');
    window.observe(Kind::male, key.actor, owner, oversized, .3f, initial + 4);
    window.observe(Kind::male, key.actor, owner, {}, .3f, initial + 5);
    window.observe(Kind::female, key.actor, owner, "Tail\x01" "Bone", .3f, initial + 6);
    window.observe(Kind::male, key.actor, owner, "TailBone01", -1, initial + 7);
    window.observe(Kind::male, key.actor, owner, "TailBone01", std::numeric_limits<float>::quiet_NaN(), initial + 8);
    window.observe(Kind::male, key.actor, owner, "TailBone01", std::numeric_limits<float>::infinity(), initial + 9);
    for (std::size_t i = 0; i <= capacity; ++i)
        window.observe(Kind::male, key.actor, owner, "TailBone01", .3f, initial + 10 + i);
    require(window.seal(key.nonce, key.generation, initial + 150));
    const auto& s = terminal(window);
    require(s.count == capacity && s.dropped == 9 && s.unattributed == 2);
    require(s.sequence == capacity + 9 && s.events[0].sequence == 9 &&
           s.events[capacity - 1].sequence == capacity + 8);
}

void cutoffAndRegressedClock() {
    auto case1 = armed();
    const auto cutoff = initial + frequency * seconds;
    case1.observe(Kind::female, key.actor, owner, "TailBone01", .31f, cutoff - 1);
    case1.observe(Kind::female, key.actor, owner, "TailBone01", .31f, cutoff);
    require(!case1.seal(key.nonce, key.generation, cutoff + 1));
    const auto& expired = terminal(case1);
    require(expired.state == State::expired && expired.count == 1 && expired.closedQpc == cutoff);

    for (const auto invalid : {Ticks{0}, initial}) {
        auto current = armed();
        require(!current.seal(key.nonce, key.generation, invalid));
        require(terminal(current).state == State::clockInvalid);
    }
}

void equippedPlayerRequiresExplicitScopeAndMatchingSeal() {
    constexpr Key player{109, 1, 0x14, key.cell};
    for (const bool sameSubject : {false, true}) {
        Window window(frequency, Subject::equippedPlayer);
        window.sinkReady();
        require(!window.request(key, initial));
        require(window.request(player, initial));
        require(window.activate(player, 7, owner, initial + 1));
        window.observe(Kind::male, key.actor, owner, "TailBone02", .4f, initial + 2);
        window.observe(Kind::male, player.actor, owner, "TailBone02", .4f, initial + 3);
        require(window.seal(player.nonce, player.generation, initial + 4, sameSubject) == sameSubject);
        const auto& result = terminal(window);
        require(result.key == player && result.base == 7 && result.count == 1);
        require(result.state == (sameSubject ? State::sealed : State::refused));
    }
    for (const auto phase : {State::pending, State::armed}) {
        Window window(frequency, Subject::equippedPlayer);
        window.sinkReady();
        require(window.request(player, initial));
        if (phase == State::armed) require(window.activate(player, 7, owner, initial + 1));
        window.changeSubject(initial + 2);
        require(!window.activate(player, 7, owner, initial + 3));
        require(!window.seal(player.nonce, player.generation, initial + 4));
        require(terminal(window).state == State::changedSubject);
    }
}
}

int main() {
    readinessAndSingleArm();
    exactSenderAndPayload();
    wrongKeysAndSealedImmutability();
    reasonOnBadIdentityOrWorldChange();
    boundAndUnattributedDrops();
    cutoffAndRegressedClock();
    equippedPlayerRequiresExplicitScopeAndMatchingSeal();
    std::cout << "7 categories passed: one arm, payload, immutable scope, lifecycle, drops, clock, player scope\n";
}
