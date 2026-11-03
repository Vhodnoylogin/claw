#pragma once
#include <array>
#include <cstdint>

namespace claw::appearance {
// Only readable author-facing state whose later replacement must survive our
// whole-property rollback. This is deliberately not an engine-object hash:
// reference counts, padding, render caches and synchronization fields vary.
struct MaterialLeaseState {
    std::array<float, 4> uvOffset{}, uvScale{};
    std::array<float, 3> specularColour{};
    float materialAlpha{}, refractionPower{}, specularPower{}, specularScale{},
        subSurfaceRolloff{}, rimPower{}, propertyAlpha{};
    std::int32_t diffuseTarget{}, clampMode{};
    std::uint64_t flags{};
    std::array<std::uintptr_t, 4> textures{};
    std::uintptr_t textureSet{}, effectData{};
    bool operator==(const MaterialLeaseState&) const = default;
};

// A changed value conservatively yields the entire property to its later
// owner. Numeric equality also refuses a nonfinite NaN witness.
inline bool mayRestoreMaterial(const MaterialLeaseState& accepted, const MaterialLeaseState& current) {
    return accepted == current;
}
}
