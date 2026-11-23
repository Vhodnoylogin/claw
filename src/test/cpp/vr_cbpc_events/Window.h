#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <string_view>

namespace cbpc {
using Ticks = std::uint64_t;
enum class Kind { male, female, other };
enum class State { idle, pending, armed, sealed, refused, expired, changedWorld, changedSubject, clockInvalid };
enum class Subject { fixtureNpc, equippedPlayer };

constexpr std::size_t capacity = 128;
constexpr std::size_t maxBone = 64;
constexpr Ticks seconds = 60;
constexpr std::string_view male = "CBPCPlayerCollisionWithMaleEvent";
constexpr std::string_view female = "CBPCPlayerCollisionWithFemaleEvent";

constexpr Kind kind(std::string_view name) {
    if (name == male) return Kind::male;
    if (name == female) return Kind::female;
    return Kind::other;
}

constexpr std::string_view name(Kind value) { return value == Kind::male ? male : female; }

constexpr bool dynamicActor(std::uint32_t form) {
    return (form & 0xFF000000u) == 0xFF000000u && form != 0xFFFFFFFFu;
}

struct Key {
    std::uint32_t nonce{}, generation{}, actor{}, cell{};
    bool operator==(const Key&) const = default;
};

struct Event {
    std::uint64_t sequence{};
    Ticks qpc{};
    Kind type{};
    float number{};
    std::array<char, maxBone> bone{};
    std::uint8_t boneSize{};
    bool operator==(const Event&) const = default;
};

struct Snapshot {
    Key key;
    State state{};
    Ticks frequency{}, requestedQpc{}, armedQpc{}, closedQpc{};
    std::uint32_t base{};
    std::uint64_t sequence{}, dropped{}, unattributed{};
    std::size_t count{};
    std::array<Event, capacity> events{};
    bool operator==(const Snapshot&) const = default;
};

// Caller serializes access. No engine context or owning pointer is retained.
class Window {
public:
    explicit Window(Ticks frequency, Subject subject = Subject::fixtureNpc) : subject_(subject) {
        snapshot_.frequency = frequency;
    }
    std::uint32_t generation() const { return generation_; }
    State state() const { return snapshot_.state; }
    void sinkReady() { sinkReady_ = true; }
    bool hasSink() const { return sinkReady_; }
    bool isLoading() const { return loading_; }

    void world(bool ready, Ticks now) {
        if (open()) close(State::changedWorld, now);
        ++generation_;
        loading_ = !ready;
    }

    void changeSubject(Ticks now) {
        tick(now);
        if (open()) close(State::changedSubject, now);
    }

    bool request(Key key, Ticks now) {
        const auto frequency = snapshot_.frequency;
        if (!sinkReady_ || loading_ || state() != State::idle || key.generation != generation_ ||
            !key.nonce || !accepts(key.actor) || !key.cell || !now || !frequency ||
            frequency > (std::numeric_limits<Ticks>::max() - now) / seconds) return false;
        snapshot_.key = key;
        snapshot_.requestedQpc = last_ = now;
        deadline_ = now + frequency * seconds;
        snapshot_.state = State::pending;
        return true;
    }

    bool activate(Key key, std::uint32_t base, std::uintptr_t sender, Ticks now) {
        tick(now);
        if (state() != State::pending || key != snapshot_.key) return false;
        if (!base || !sender) {
            close(State::refused, now);
            return false;
        }
        snapshot_.base = base;
        sender_ = sender;
        snapshot_.armedQpc = now;
        snapshot_.state = State::armed;
        return true;
    }

    void observe(Kind type, std::uint32_t id, std::uintptr_t sender, std::string_view bone, float number, Ticks now) {
        if (state() != State::armed || type == Kind::other) return;
        tick(now);
        if (state() != State::armed || (id && id != snapshot_.key.actor)) return;
        const auto sequence = ++snapshot_.sequence;
        if (!id || sender != sender_) {
            ++snapshot_.unattributed;
            ++snapshot_.dropped;
            return;
        }
        if (snapshot_.count == capacity || !validBone(bone) || !std::isfinite(number) || number < 0) {
            ++snapshot_.dropped;
            return;
        }
        auto& row = snapshot_.events[snapshot_.count++];
        row.sequence = sequence;
        row.qpc = now;
        row.type = type;
        row.number = number;
        row.boneSize = static_cast<std::uint8_t>(bone.size());
        std::ranges::copy(bone, row.bone.begin());
    }

    void tick(Ticks now) {
        if (!open()) return;
        if (!now || now < last_) close(State::clockInvalid, last_);
        else if (now >= deadline_) close(State::expired, now);
        else last_ = now;
    }

    bool seal(std::uint32_t nonce, std::uint32_t generation, Ticks now, bool sameSubject = true) {
        tick(now);
        if (state() != State::armed || !match(nonce, generation)) return false;
        close(sameSubject ? State::sealed : State::refused, now);
        return sameSubject;
    }

    const Snapshot* read(std::uint32_t nonce, std::uint32_t generation) const {
        if (open() || state() == State::idle || !match(nonce, generation)) return nullptr;
        return &snapshot_;
    }

private:
    bool accepts(std::uint32_t actor) const {
        return subject_ == Subject::equippedPlayer ? actor == 0x14 : dynamicActor(actor);
    }
    static bool validBone(std::string_view bone) {
        return !bone.empty() && bone.size() <= maxBone &&
               std::ranges::all_of(bone, [](unsigned char c) { return c >= 32 && c <= 126; });
    }
    bool open() const { return state() == State::pending || state() == State::armed; }
    bool match(std::uint32_t nonce, std::uint32_t generation) const {
        return nonce == snapshot_.key.nonce && generation == snapshot_.key.generation;
    }
    void close(State state, Ticks now) {
        snapshot_.state = state;
        snapshot_.closedQpc = std::max(now, last_);
        sender_ = 0;
    }

    Subject subject_;
    Snapshot snapshot_;
    Ticks last_{}, deadline_{};
    std::uint32_t generation_{1};
    std::uintptr_t sender_{};
    bool sinkReady_{}, loading_{};
};
}
