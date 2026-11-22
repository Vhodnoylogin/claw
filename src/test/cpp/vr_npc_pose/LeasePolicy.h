#pragma once

#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>

namespace claw::npc_pose {

constexpr std::int32_t maximumSequence = 16;

enum class Scope { motion, effectiveMorphs, earTailSupport, femaleMotion, tailRefit };

constexpr bool observesContact(Scope scope) {
    return scope == Scope::earTailSupport || scope == Scope::tailRefit;
}

constexpr bool needsEffectiveMorphs(Scope scope) {
    return scope == Scope::effectiveMorphs || observesContact(scope);
}

constexpr std::chrono::seconds leaseLifetime(Scope scope) {
    return std::chrono::seconds(scope == Scope::tailRefit ? 30 : 12);
}

constexpr std::chrono::seconds watchdogDelay(Scope scope) {
    return leaseLifetime(scope) + std::chrono::seconds(1);
}

constexpr bool sameOpeningScope(Scope active, Scope requested, std::int32_t sequence) {
    return active == requested && sequence == 0;
}

constexpr bool validFixture(std::uint32_t actor, std::uint32_t base, std::uint32_t handle,
                            std::uint32_t cell, std::uint32_t addon) {
    return actor >= 0xFF000000u && actor < 0xFFFFFFFFu && base > 0 && base < 0xFF000000u &&
           handle != 0 && cell > 0 && cell < 0xFF000000u && addon > 0 && addon < 0xFF000000u;
}

constexpr bool nextSample(std::int32_t sequence, std::int32_t previous) {
    return previous >= 0 && previous < maximumSequence && sequence == previous + 1;
}

inline std::int32_t physicsSnapshotToken(float argument) {
    // Match the production authority's nonzero, exactly representable range.
    if (!std::isfinite(argument) || argument < 1.f || argument >= 16777216.f ||
        std::trunc(argument) != argument) return 0;
    return static_cast<std::int32_t>(argument);
}

struct Transform {
    std::array<float, 9> rotation{};
    std::array<float, 3> translation{};
    float scale{};
};

inline bool finite(const Transform& transform) {
    for (const auto value : transform.rotation) if (!std::isfinite(value)) return false;
    for (const auto value : transform.translation) if (!std::isfinite(value)) return false;
    return std::isfinite(transform.scale) && transform.scale > 0;
}

}
