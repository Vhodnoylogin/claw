#pragma once
#include "claw/Preset.h"
#include "MatrixKernel.h"
#include <algorithm>
#include <cmath>
#include <functional>
#include <set>
#include <stdexcept>
#include <utility>

namespace claw {
enum class MorphFunction : std::uint32_t { linear, positive, negative, smoothstep, power, constant };
inline std::string_view morphFunctionName(MorphFunction value) {
    switch (value) {
    case MorphFunction::linear: return "linear";
    case MorphFunction::positive: return "positive";
    case MorphFunction::negative: return "negative";
    case MorphFunction::smoothstep: return "smoothstep";
    case MorphFunction::power: return "power";
    case MorphFunction::constant: return "constant";
    }
    return {};
}
inline MorphFunction parseMorphFunction(std::string_view value) {
    for (std::uint32_t index = 0; index <= 5; ++index) {
        const auto function = static_cast<MorphFunction>(index);
        if (morphFunctionName(function) == value) return function;
    }
    throw std::invalid_argument("Unknown morph function");
}
struct MorphLinkRule {
    std::string source, target;
    float gain{}, cap{};
    MorphFunction function{MorphFunction::linear};
    std::uint32_t exponent{2};
    float value{};
    [[nodiscard]] bool constant() const { return function == MorphFunction::constant; }
    [[nodiscard]] double transform(double input) const {
        return claw_matrix_transform(input, static_cast<std::uint32_t>(function), exponent, value);
    }
};
inline bool morphLinkIdentifier(std::string_view value) {
    if (value.empty() || value.size() > 160 || static_cast<unsigned char>(value.front()) <= 32 || static_cast<unsigned char>(value.back()) <= 32) return false;
    for (const unsigned char c : value) if (c < 32 || c == 127) return false;
    return true;
}
inline bool linkedBodyMorph(std::string_view name) {
    return name.starts_with("CLAWTorso") || name == "CLAWArmGirth" || name == "CLAWLegCalfGirth" || name == "CLAWLegThighGirth" ||
        name == "CLAWArmLean" || name == "CLAWLegCalfLean" || name == "CLAWLegThighLean";
}
struct MorphLink {
    std::string profile;
    std::vector<MorphLinkRule> rules;
    Morphs sourceValues;
    bool captured{};
    [[nodiscard]] bool enabled() const { return !profile.empty(); }
    [[nodiscard]] bool valid(Sex sex) const {
        if (!enabled()) return rules.empty() && sourceValues.empty() && !captured;
        if (!morphLinkIdentifier(profile) || rules.empty() || rules.size() > 128) return false;
        std::set<std::pair<std::string, std::string>> pairs;
        std::map<std::string, float> caps;
        std::set<std::string> sources;
        for (const auto& rule : rules) {
            if ((rule.constant() ? !rule.source.empty() : (!morphLinkIdentifier(rule.source) || rule.source.starts_with("CLAW"))) ||
                morphFunctionName(rule.function).empty() || !std::isfinite(rule.value) ||
                (rule.function == MorphFunction::power ? (rule.exponent < 1 || rule.exponent > 8) : rule.exponent != 2) ||
                (!rule.constant() && rule.value != 0) || !recognizedMorph(rule.target, sex) || !linkedBodyMorph(rule.target) ||
                !std::isfinite(rule.gain) || !std::isfinite(rule.cap) || rule.cap <= 0 || rule.cap > 1 ||
                !pairs.emplace(rule.source, rule.target).second) return false;
            const auto [it, inserted] = caps.emplace(rule.target, rule.cap);
            if (!inserted && it->second != rule.cap) return false;
            if (!rule.constant()) sources.emplace(rule.source);
        }
        if (!captured) return sourceValues.empty();
        if (sourceValues.size() != sources.size()) return false;
        for (const auto& [name, value] : sourceValues) if (!sources.contains(name) || !std::isfinite(value)) return false;
        return true;
    }
    void capture(const std::function<float(std::string_view)>& read) {
        Morphs observed;
        for (const auto& rule : rules) if (!rule.constant() && !observed.contains(rule.source)) {
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
        std::map<std::string, std::uint32_t> targets;
        std::uint32_t next{};
        for (const auto& [name, value] : result) targets.emplace(name, next++);
        std::vector<CLAWMatrixRule> matrix;
        matrix.reserve(rules.size());
        for (const auto& rule : rules) {
            matrix.push_back({targets.at(rule.target), static_cast<std::uint32_t>(rule.function), rule.exponent,
                rule.constant() ? 0.F : sourceValues.at(rule.source), rule.gain, rule.cap, rule.value});
        }
        std::vector<float> output(result.size()); std::vector<double> sums(result.size());
        if (claw_matrix_evaluate(matrix.data(), static_cast<std::uint32_t>(matrix.size()), output.data(), sums.data(), next))
            throw std::runtime_error("morph matrix kernel rejected profile/arithmetic");
        for (auto& [target, value] : result) value = output.at(targets.at(target));
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
