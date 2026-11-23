#pragma once

#include "claw/MaterialLease.h"
#include <optional>

namespace claw::appearance {

enum class CoatTexturePreparation { ready, unavailable, pending };

constexpr bool coatTextureRetryDue(std::uint64_t failedAt, std::uint64_t now) {
    return now >= failedAt && now - failedAt >= 2000;
}

template<class TexturePaths>
struct CoatDonorContent {
    MaterialLeaseState state;
    TexturePaths paths;
    std::int32_t feature;
    std::optional<std::array<float, 3>> tint;

    bool matches(const CoatDonorContent& other) const {
        return feature == other.feature && tint == other.tint && paths == other.paths &&
            mayRestoreMaterial(state, other.state);
    }
};

} // namespace claw::appearance
