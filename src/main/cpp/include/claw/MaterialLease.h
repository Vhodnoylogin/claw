#pragma once
#include <array>
#include <bit>
#include <charconv>
#include <cmath>
#include <cstdint>
#include <string>
#include <string_view>
#include <type_traits>
#include <utility>
#include <vector>

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

// Property alpha is live per-geometry fade state, independent of coat content.
// Every other author-facing value remains an exact cooperative ownership check.
// Rollback must carry the current finite alpha instead of restoring its old value.
inline bool mayRestoreMaterial(const MaterialLeaseState& accepted, const MaterialLeaseState& current) {
    if (!std::isfinite(accepted.propertyAlpha) || !std::isfinite(current.propertyAlpha)) return false;
    auto content = current;
    content.propertyAlpha = accepted.propertyAlpha;
    return accepted == content;
}

// The caller has checked the complete owned content/guard/tint lease. Keep the
// animated alpha without ever writing a retained, potentially shared donor.
// Clone must provide a private donor-material copy; Initialize runs the engine's
// geometry setup while that replacement is bound. Refusal leaves the old owned
// property, or a property installed by another writer during initialization.
template<class Pointer, class Clone, class Initialize>
bool restoreMaterialWithAlpha(Pointer& current, const Pointer& owned, const Pointer& donor,
    Clone&& clone, Initialize&& initialize) {
    if (!current || !owned || !donor || current.get() != owned.get() || owned.get() == donor.get() ||
        !std::isfinite(current->alpha) || !std::isfinite(donor->alpha)) return false;
    const float alpha = current->alpha;
    if (donor->alpha == alpha) { current = donor; return true; }
    auto replacement = std::forward<Clone>(clone)(donor);
    if (!replacement || replacement.get() == donor.get() || replacement.get() == owned.get() ||
        !replacement->material || replacement->material == donor->material || replacement->material == owned->material) return false;
    const auto privateMaterial = replacement->material;
    replacement->alpha = alpha;
    current = replacement;
    const auto stillPrivate = [&] {
        return current.get() == replacement.get() && replacement->material && replacement->material == privateMaterial &&
            replacement->material != donor->material && replacement->material != owned->material;
    };
    const auto failed = [&] {
        if (stillPrivate()) current = owned;
        return false;
    };
    const bool initialized = std::forward<Initialize>(initialize)(replacement);
    if (!stillPrivate()) return false;
    if (!initialized) return failed();
    // FinishSetupGeometry can recalculate fade. Carry the observed live value
    // after it completes, on this private property only.
    replacement->alpha = alpha;
    if (!stillPrivate()) return false;
    if (replacement->alpha != alpha) return failed();
    return true;
}

// Diagnostic only: preserve exact float bits (including nonfinite witnesses)
// and all 64 flag/pointer bits. These observations never relax the lease test.
struct MaterialLeaseDifference { std::string field, expected, observed; };
inline std::string materialLeaseDiagnosticValue(float value) {
    char text[64]{}, bits[16]{};
    const auto [end, ec] = std::to_chars(text, text + sizeof(text), value);
    const auto [bitEnd, bitError] = std::to_chars(bits, bits + sizeof(bits), std::bit_cast<std::uint32_t>(value), 16);
    return (ec == std::errc{} ? std::string(text, end) : "unavailable") + " [bits=0x" +
        (bitError == std::errc{} ? std::string(bits, bitEnd) : "unavailable") + ']';
}
template<class Integer> requires std::is_integral_v<Integer>
inline std::string materialLeaseDiagnosticValue(Integer value) { return std::to_string(value); }
inline std::string materialLeaseDiagnosticValue(std::string_view value) { return std::string(value); }
inline std::vector<MaterialLeaseDifference> materialLeaseDifferences(const MaterialLeaseState& expected, const MaterialLeaseState& observed) {
    std::vector<MaterialLeaseDifference> result;
    const auto compare = [&](std::string field, auto before, auto after) {
        if (!(before == after)) result.push_back({std::move(field), materialLeaseDiagnosticValue(before), materialLeaseDiagnosticValue(after)});
    };
    for (unsigned i = 0; i < 4; ++i) {
        compare("uvOffset[" + std::to_string(i) + ']', expected.uvOffset[i], observed.uvOffset[i]);
        compare("uvScale[" + std::to_string(i) + ']', expected.uvScale[i], observed.uvScale[i]);
        compare("textures[" + std::to_string(i) + ']', expected.textures[i], observed.textures[i]);
    }
    for (unsigned i = 0; i < 3; ++i)
        compare("specularColour[" + std::to_string(i) + ']', expected.specularColour[i], observed.specularColour[i]);
    compare("materialAlpha", expected.materialAlpha, observed.materialAlpha);
    compare("refractionPower", expected.refractionPower, observed.refractionPower);
    compare("specularPower", expected.specularPower, observed.specularPower);
    compare("specularScale", expected.specularScale, observed.specularScale);
    compare("subSurfaceRolloff", expected.subSurfaceRolloff, observed.subSurfaceRolloff);
    compare("rimPower", expected.rimPower, observed.rimPower);
    compare("propertyAlpha", expected.propertyAlpha, observed.propertyAlpha);
    compare("diffuseTarget", expected.diffuseTarget, observed.diffuseTarget);
    compare("clampMode", expected.clampMode, observed.clampMode);
    compare("flags", expected.flags, observed.flags);
    compare("textureSet", expected.textureSet, observed.textureSet);
    compare("effectData", expected.effectData, observed.effectData);
    return result;
}
}
