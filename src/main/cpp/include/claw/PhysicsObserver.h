#pragma once
#include <cmath>
#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

namespace claw {
// Provider values are sampled on separate main-task passes. A SKEE queued
// model update and our NiNode notification both invalidate the candidate; no
// Papyrus per-key summation or own-key cache is a substitute for GetBodyMorphs.
struct PhysicsObservation {
    std::uintptr_t root{};
    std::vector<float> candidate, published;
    float weight{-1}, publishedWeight{-1};
    unsigned stablePasses{};
    std::uint32_t sequence{};
    bool dirty{true};

    void invalidate() { candidate.clear(); stablePasses = 0; dirty = true; }
    bool observe(std::uintptr_t currentRoot, std::vector<float> values, float normalizedWeight = 0) {
        if (!currentRoot || values.empty() || !std::isfinite(normalizedWeight) || normalizedWeight < 0 || normalizedWeight > 1) { invalidate(); return false; }
        for (const auto value : values)
            if (!std::isfinite(value)) { invalidate(); return false; }
        if (root != currentRoot || candidate != values || weight != normalizedWeight) {
            if (root != currentRoot) dirty = true;
            root = currentRoot; weight = normalizedWeight; candidate = std::move(values); stablePasses = 1;
            return false;
        }
        if (stablePasses < 2) ++stablePasses;
        if (stablePasses < 2 || (!dirty && published == candidate && publishedWeight == weight)) return false;
        published = candidate; publishedWeight = weight; dirty = false;
        // The Papyrus mod event uses Float numArg: every token remains exact.
        sequence = sequence >= 0x00FFFFFFU ? 1 : sequence + 1;
        return true;
    }
};

inline bool validPhysicsNames(const std::vector<std::string>& names) {
    if (names.empty() || names.size() > 32) return false;
    for (std::size_t index = 0; index < names.size(); ++index) {
        const auto& name = names[index];
        if (!name.starts_with("CLAW") || name.size() > 96) return false;
        for (const auto c : name) if (!(c >= 'A' && c <= 'Z') && !(c >= 'a' && c <= 'z') && !(c >= '0' && c <= '9') && c != '_') return false;
        for (std::size_t before = 0; before < index; ++before) if (names[before] == name) return false;
    }
    return true;
}
}
