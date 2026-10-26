#pragma once
#include "claw/Preset.h"
#include <algorithm>
#include <cmath>
#include <functional>
#include <set>
#include <stdexcept>
#include <utility>

namespace claw {
struct MorphLinkRule {
    std::string source, target;
    float gain{}, cap{};
};
inline bool morphLinkIdentifier(std::string_view value) {
    if (value.empty() || value.size() > 160 || static_cast<unsigned char>(value.front()) <= 32 || static_cast<unsigned char>(value.back()) <= 32) return false;
    for (const unsigned char c : value) if (c < 32 || c == 127) return false;
    return true;
}
inline bool linkedBodyMorph(std::string_view name) {
    return (name.starts_with("CLAWTorso") && name != "CLAWTorsoBreastSize") || name == "CLAWArmGirth" || name == "CLAWLegCalfGirth" || name == "CLAWLegThighGirth";
}
struct MorphLink {
    std::string profile;
    std::vector<MorphLinkRule> rules;
    Morphs sourceValues;
    bool captured{};
    [[nodiscard]] bool enabled() const { return !profile.empty(); }
    [[nodiscard]] bool valid(Sex sex) const {
        if (!enabled()) return rules.empty() && sourceValues.empty() && !captured;
        if (!morphLinkIdentifier(profile) || rules.empty() || rules.size() > 32) return false;
        std::set<std::pair<std::string, std::string>> pairs;
        std::map<std::string, float> caps;
        std::set<std::string> sources;
        for (const auto& rule : rules) {
            if (!morphLinkIdentifier(rule.source) || rule.source.starts_with("CLAW") || !recognizedMorph(rule.target, sex) || !linkedBodyMorph(rule.target) ||
                !std::isfinite(rule.gain) || !std::isfinite(rule.cap) || rule.cap <= 0 || rule.cap > 1 ||
                !pairs.emplace(rule.source, rule.target).second) return false;
            const auto [it, inserted] = caps.emplace(rule.target, rule.cap);
            if (!inserted && it->second != rule.cap) return false;
            sources.emplace(rule.source);
        }
        if (!captured) return sourceValues.empty();
        if (sourceValues.size() != sources.size()) return false;
        for (const auto& [name, value] : sourceValues) if (!sources.contains(name) || !std::isfinite(value)) return false;
        return true;
    }
    void capture(const std::function<float(std::string_view)>& read) {
        Morphs observed;
        for (const auto& rule : rules) if (!observed.contains(rule.source)) {
            const auto value = read(rule.source);
            if (!std::isfinite(value)) throw std::runtime_error("nonfinite applied human morph");
            observed.emplace(rule.source, value);
        }
        sourceValues = std::move(observed); captured = true;
    }
    [[nodiscard]] Morphs compose(Sex sex) const {
        if (!valid(sex) || !captured) throw std::runtime_error("morph link profile/source is unavailable or invalid");
        // Linked output starts neutral. Independent presets, actor weight and
        // unmapped traits cannot contribute to this mode.
        Morphs result;
        for (const auto name : recognizedMorphs(sex)) result.emplace(name, 0.F);
        std::map<std::string, double> sums;
        std::map<std::string, float> caps;
        for (const auto& rule : rules) {
            sums[rule.target] += static_cast<double>(sourceValues.at(rule.source)) * rule.gain;
            caps[rule.target] = rule.cap;
        }
        for (const auto& [target, sum] : sums) {
            if (!std::isfinite(sum)) throw std::runtime_error("morph link arithmetic overflow");
            result[target] = static_cast<float>(std::clamp(sum, 0.0, 1.0) * caps.at(target));
        }
        return result;
    }
};

// Keep catalog lookup, selection and weight interpolation lazy: linked actors
// need none of them, including when the independent catalog is absent/invalid.
template <class Independent>
[[nodiscard]] Morphs resolveMorphs(const MorphLink& link, Sex sex, Independent&& independent) {
    if (link.enabled()) return link.compose(sex);
    return std::forward<Independent>(independent)();
}
}
