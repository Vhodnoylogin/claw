#pragma once

#include <array>
#include <atomic>
#include <charconv>
#include <cmath>
#include <cstdint>
#include <string_view>

namespace claw::contact {

using Key = std::uintptr_t;  // Comparison only. Never published.
using Tick = std::uint64_t;
using Vec3 = std::array<float, 3>;

struct Pair {
    std::uint32_t surfaceRef{}, surfaceAddon{}, probeRef{}, probeAddon{};
    Key surface{}, probe{}, surfaceSkeleton{}, probeSkeleton{};
    bool control{};
    bool operator==(const Pair&) const = default;
};

struct Row {
    std::uint32_t step{};
    Tick qpc{};
    unsigned driver{};
    float depth{};
    Vec3 normalToSurface{}, surfaceLocal{}, probeLocal{};
};

struct Trial {
    std::uint32_t nonce{}, callerEpoch{}, frames{};
    Tick qpcFrequency{};
};

enum class State { idle, armed, complete, refused };

inline bool hasAddonId(std::string_view node, std::uint32_t expected) noexcept {
    // Skyrim armor-node names put ARMA first and ARMO later: (ARMA)[n]/ (ARMO) [weight%].
    if (node.size() < 11 || node.front() != '(' || node.substr(9, 2) != ")[" || !expected) return false;
    const auto* last = node.data() + 9;
    std::uint32_t found{};
    const auto parsed = std::from_chars(node.data() + 1, last, found, 16);
    return parsed.ec == std::errc{} && parsed.ptr == last && found == expected;
}

// The provider serializes control, Begin/End and reads with its existing
// simulation lock. Contacts may be reported by parallel narrow-phase workers.
// Their fixed slots are disjoint and joined by the caller before End.
class Window {
public:
    static constexpr std::uint32_t maxFrames = 120;
    static constexpr std::uint32_t capacity = 384;

    bool arm(Trial request, Pair pair) noexcept {
        if (state_ == State::armed || !request.nonce || request.nonce <= trial_.nonce
            || !request.callerEpoch || !request.frames || request.frames > maxFrames
            || !request.qpcFrequency || !pair.surfaceRef || !pair.probeRef
            || pair.surfaceRef == pair.probeRef || !pair.surfaceAddon || !pair.probeAddon
            || !pair.surface || !pair.probe || pair.surface == pair.probe
            || !pair.surfaceSkeleton || !pair.probeSkeleton || pair.surfaceSkeleton == pair.probeSkeleton)
            return false;
        trial_ = request;
        pair_ = pair;
        steps_ = 0;
        first_ = last_ = 0;
        count_.store(0, std::memory_order_relaxed);
        fault_.store(false, std::memory_order_relaxed);
        state_ = State::armed;
        return true;
    }

    bool begin(bool exactPairPresent, Tick clock) noexcept {
        if (state_ != State::armed) return false;
        if (!exactPairPresent || !clock || clock <= last_ || accepting_.load()) {
            refuse();
            return false;
        }
        if (!first_) first_ = clock;
        begin_ = clock;
        stepStart_ = count_.load(std::memory_order_relaxed);
        ++steps_;
        accepting_.store(true, std::memory_order_release);
        return true;
    }

    void note(Key a, Key b, unsigned driver, Tick clock, float depth, const Vec3& normalOnB,
              const Vec3& localA, const Vec3& localB) noexcept {
        if (!accepting_.load(std::memory_order_acquire)) return;
        const bool ordered = a == pair_.surface && b == pair_.probe;
        if (!ordered && !(a == pair_.probe && b == pair_.surface)) return;
        if (driver < 1 || driver > 3 || !std::isfinite(depth) || depth >= 0
            || clock < begin_ || !finite(normalOnB) || !finite(localA) || !finite(localB)
            || std::abs(normalOnB[0] * normalOnB[0] + normalOnB[1] * normalOnB[1]
                       + normalOnB[2] * normalOnB[2] - 1.0f) > 0.002f) {
            fault_.store(true, std::memory_order_relaxed);
            return;
        }
        const auto index = count_.fetch_add(1, std::memory_order_relaxed);
        if (index >= capacity) {
            fault_.store(true, std::memory_order_relaxed);
            return;
        }
        const auto normal = ordered ? normalOnB : Vec3{-normalOnB[0], -normalOnB[1], -normalOnB[2]};
        rows_[index] = {steps_, clock, driver, depth, normal,
                       ordered ? localA : localB, ordered ? localB : localA};
    }

    void end(Tick clock) noexcept {
        if (!accepting_.exchange(false, std::memory_order_acq_rel)) return;
        if (!clock || clock < begin_ || fault_.load(std::memory_order_relaxed)) {
            refuse();
            return;
        }
        const auto filled = count_.load(std::memory_order_relaxed);
        for (auto i = stepStart_; i < filled; ++i) {
            if (rows_[i].qpc > clock) {
                refuse();
                return;
            }
        }
        last_ = clock;
        if (steps_ == trial_.frames) state_ = State::complete;
    }

    void refuse() noexcept {
        accepting_.store(false, std::memory_order_release);
        state_ = State::refused;
    }

    [[nodiscard]] State state() const noexcept { return state_; }
    [[nodiscard]] bool accepting() const noexcept { return accepting_.load(std::memory_order_acquire); }
    [[nodiscard]] const Trial& trial() const noexcept { return trial_; }
    [[nodiscard]] const Pair& pair() const noexcept { return pair_; }
    [[nodiscard]] Tick first() const noexcept { return first_; }
    [[nodiscard]] Tick last() const noexcept { return last_; }
    [[nodiscard]] std::uint32_t steps() const noexcept { return steps_; }
    [[nodiscard]] std::uint32_t count() const noexcept {
        return state_ == State::complete ? count_.load(std::memory_order_relaxed) : 0;
    }
    [[nodiscard]] const Row* row(std::uint32_t index) const noexcept {
        return index < count() ? &rows_[index] : nullptr;
    }

private:
    static bool finite(const Vec3& xyz) noexcept {
        return std::isfinite(xyz[0]) && std::isfinite(xyz[1]) && std::isfinite(xyz[2]);
    }

    std::atomic<bool> accepting_{}, fault_{};
    std::atomic<std::uint32_t> count_{};
    std::array<Row, capacity> rows_{};
    Pair pair_{};
    Trial trial_{};
    Tick first_{}, begin_{}, last_{};
    State state_{State::idle};
    std::uint32_t steps_{}, stepStart_{};
};
}
