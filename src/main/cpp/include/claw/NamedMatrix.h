#pragma once
#include "claw/Preset.h"
#include "MatrixKernel.h"
#include <span>
#include <stdexcept>

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
    [[nodiscard]] bool active() const { return claw_matrix_gain_active(gain) != 0; }
    [[nodiscard]] double transform(double input) const {
        return claw_matrix_transform(input, static_cast<std::uint32_t>(function), exponent, value);
    }
};
// The engine adapters decide which names are available. Outputs never mutate the input snapshot.
inline Morphs evaluateNamed(std::span<const MorphLinkRule> rules, const Morphs& sourceValues) {
    Morphs result;
    std::map<std::string, std::uint32_t> targets;
    for (const auto& rule : rules) if (rule.active()) targets.emplace(rule.target, 0);
    std::uint32_t next{};
    for (auto& [name, index] : targets) index = next++;
    std::vector<CLAWMatrixRule> matrix;
    matrix.reserve(rules.size());
    for (const auto& rule : rules) {
        if (!rule.active()) continue;
        matrix.push_back({targets.at(rule.target), static_cast<std::uint32_t>(rule.function), rule.exponent,
            rule.constant() ? 0.F : sourceValues.at(rule.source), rule.gain, rule.cap, rule.value});
    }
    std::vector<float> output(targets.size());
    std::vector<double> sums(targets.size());
    if (claw_matrix_evaluate(matrix.data(), static_cast<std::uint32_t>(matrix.size()), output.data(), sums.data(), next))
        throw std::runtime_error("morph matrix kernel rejected profile/arithmetic");
    for (const auto& [target, index] : targets) result.emplace(target, output.at(index));
    return result;
}
}
