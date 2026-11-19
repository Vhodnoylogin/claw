#pragma once

#include <array>
#include <cmath>
#include <cstdint>

namespace claw::npc_pose {

constexpr std::int32_t maximumSequence = 16;

constexpr bool validFixture(std::uint32_t actor, std::uint32_t base, std::uint32_t handle,
                            std::uint32_t cell, std::uint32_t addon) {
    return actor >= 0xFF000000u && actor < 0xFFFFFFFFu && base > 0 && base < 0xFF000000u &&
           handle != 0 && cell > 0 && cell < 0xFF000000u && addon > 0 && addon < 0xFF000000u;
}

constexpr bool nextSample(std::int32_t sequence, std::int32_t previous) {
    return previous >= 0 && previous < maximumSequence && sequence == previous + 1;
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
