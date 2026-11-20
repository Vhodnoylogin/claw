#include "Window.h"
#include <cassert>
#include <iostream>
#include <string>

namespace {
using namespace cbpc;
constexpr Key key{109, 1, 0xFF000123, 0x0A01A5C6};
constexpr std::uint32_t base = 0x0B000800;
constexpr std::uintptr_t owner = 37;
constexpr Ticks initial = 1000;
constexpr Ticks frequency = 100;

Window armed() {
    Window window(frequency);
    window.sinkReady();
    assert(window.request(key, initial));
    assert(window.activate(key, base, owner, initial + 1));
    return window;
}

void readinessAndSingleArm() {
    Window window(frequency);
    assert(!window.request(key, initial));
    window.sinkReady();
    for (const auto bad : {Key{}, Key{0,1,key.actor,key.cell}, Key{1,2,key.actor,key.cell},
                            Key{1,1,0x14,key.cell}, Key{1,1,0xFE000901,key.cell},
                            Key{1,1,0xFFFFFFFFu,key.cell}, Key{1,1,key.actor,0}}) {
        assert(!window.request(bad, initial));
    }
    assert(!window.request(key, 0));
    assert(!window.request(key, std::numeric_limits<Ticks>::max() - frequency));
    assert(window.request(key, initial));
    assert(window.state() == State::pending);
    assert(!window.request({103,1,key.actor,key.cell}, initial + 1));
    assert(!window.seal(key.nonce, key.generation, initial + 1));
    assert(!window.read(key.nonce, key.generation));
    assert(!window.activate({103,1,key.actor,key.cell}, base, owner, initial + 2));
    assert(window.activate(key, base, owner, initial + 3));
    assert(window.state() == State::armed);
}

void exactSenderAndPayload() {
    auto window = armed();
    assert(kind("CBPCPlayerCollisionWithFemaleEvent") == Kind::female);
    assert(kind("CBPCPlayerCollisionWithMaleEvent") == Kind::male);
    assert(kind("cbpcPlayerCollisionWithMaleEvent") == Kind::other);
    assert(kind("PlayerCollision") == Kind::other);
    window.observe(Kind::other, key.actor, owner, "TailBone01", .3f, initial + 2);
    window.observe(Kind::male, 0xFF000124, 39, "TailBone01", .3f, initial + 3);
    std::string bone("TailBone01");
    window.observe(Kind::male, key.actor, owner, bone, .31f, initial + 4);
    bone[4] = 'T';
    window.observe(Kind::female, key.actor, owner, "NPC EarL [EarL]Bone01", .61f, initial + 4);
    assert(!window.seal(key.nonce, key.generation + 1, initial + 5));
    assert(window.seal(key.nonce, key.generation, initial + 6));
    const auto* captured = window.read(key.nonce, key.generation);
    assert(captured && captured->base == base && captured->key == key);
    assert(captured->requestedQpc == initial && captured->frequency == frequency &&
           captured->armedQpc == initial + 1 && captured->closedQpc == initial + 6);
    assert(captured->sequence == 2 && captured->count == 2 && captured->dropped == 0);
    const auto& first = captured->events[0];
    assert(first.qpc == initial + 4 && first.sequence == 1 && first.type == Kind::male && first.number == .31f);
    assert(std::string_view(first.bone.data(), first.boneSize) == "TailBone01");
    assert(captured->events[1].type == Kind::female && captured->events[1].number == .61f);
}

void wrongKeysAndSealedImmutability() {
    auto window = armed();
    assert(!window.read(key.nonce, key.generation));
    assert(!window.seal(key.nonce + 1, key.generation, initial + 2));
    assert(window.seal(key.nonce, key.generation, initial + 3));
    const auto sealed = *window.read(key.nonce, key.generation);
    assert(sealed.state == State::sealed && sealed.count == 0);
    assert(!window.read(key.nonce, key.generation + 1));
    assert(!window.read(key.nonce + 1, key.generation));
    window.observe(Kind::male, key.actor, owner, "TailBone01", .3f, initial + 10);
    assert(!window.seal(key.nonce, key.generation, initial + 11));
    window.world(false, initial + 12);
    assert(!window.request({key.nonce + 1, 2, key.actor, key.cell}, initial + 13));
    assert(*window.read(key.nonce, key.generation) == sealed);
}

void reasonOnBadIdentityOrWorldChange() {
    Window window(frequency);
    window.sinkReady();
    window.world(false, initial);
    assert(window.isLoading() && window.generation() == 2);
    assert(!window.request({key.nonce, 2, key.actor, key.cell}, initial + 1));
    window.world(true, initial + 2);
    const Key newKey{key.nonce, 3, key.actor, key.cell};
    assert(window.request(newKey, initial + 3));
    assert(!window.activate(newKey, base, 0, initial + 4));
    assert(window.read(key.nonce, 3)->state == State::refused);

    for (const auto phase : {State::pending, State::armed}) {
        Window current(frequency);
        current.sinkReady();
        assert(current.request(key, initial));
        if (phase == State::armed) assert(current.activate(key, base, owner, initial + 1));
        current.world(false, initial + 2);
        assert(!current.seal(key.nonce, 1, initial + 3));
        assert(!current.activate(key, base, owner, initial + 4));
        assert(current.read(key.nonce, 1)->state == State::changedWorld);
        assert(!current.read(key.nonce, 2));
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
    assert(window.seal(key.nonce, key.generation, initial + 150));
    const auto& s = *window.read(key.nonce, key.generation);
    assert(s.count == capacity && s.dropped == 9 && s.unattributed == 2);
    assert(s.sequence == capacity + 9 && s.events[0].sequence == 9 &&
           s.events[capacity - 1].sequence == capacity + 8);
}

void cutoffAndRegressedClock() {
    auto case1 = armed();
    const auto cutoff = initial + frequency * seconds;
    case1.observe(Kind::female, key.actor, owner, "TailBone01", .31f, cutoff - 1);
    case1.observe(Kind::female, key.actor, owner, "TailBone01", .31f, cutoff);
    assert(!case1.seal(key.nonce, key.generation, cutoff + 1));
    const auto& expired = *case1.read(key.nonce, key.generation);
    assert(expired.state == State::expired && expired.count == 1 && expired.closedQpc == cutoff);

    for (const auto invalid : {Ticks{0}, initial}) {
        auto current = armed();
        assert(!current.seal(key.nonce, key.generation, invalid));
        assert(current.read(key.nonce, key.generation)->state == State::clockInvalid);
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
    std::cout << "6 categories passed: one arm, payload, immutable scope, lifecycle, dropped recovery, clock\n";
}
