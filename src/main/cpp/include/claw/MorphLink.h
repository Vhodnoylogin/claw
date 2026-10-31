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
    [[nodiscard]] bool active() const { return claw_matrix_gain_active(gain) != 0; }
    [[nodiscard]] double transform(double input) const {
        return claw_matrix_transform(input, static_cast<std::uint32_t>(function), exponent, value);
    }
};
inline bool morphLinkIdentifier(std::string_view value) {
    if (value.empty() || value.size() > 160 || static_cast<unsigned char>(value.front()) <= 32 || static_cast<unsigned char>(value.back()) <= 32) return false;
    for (const unsigned char c : value) if (c < 32 || c == 127) return false;
    return true;
}
inline bool morphNameIdentifier(std::string_view value) {
    if (!morphLinkIdentifier(value)) return false;
    return std::all_of(value.begin(), value.end(), [](unsigned char ch) { return ch >= 32 && ch < 127; });
}
inline std::string morphProviderIdentity(std::string_view value) {
    // SKEE interns names case-insensitively. Restrict bound names to ASCII and
    // fold deterministically; never use process-locale-dependent tolower.
    std::string result(value);
    for (auto& ch : result) if (ch >= 'A' && ch <= 'Z') ch = static_cast<char>(ch + ('a' - 'A'));
    return result;
}
inline std::int32_t morphSourceKind(std::string_view name) {
    if (name.size() > 160) return -1;
    return claw_matrix_source_kind(name.data(), static_cast<std::uint32_t>(name.size()));
}
inline bool actorWeightSource(std::string_view name) { return morphSourceKind(name) == 1; }
inline float normalizedActorWeight(float rawNPCWeight) {
    if (!std::isfinite(rawNPCWeight) || rawNPCWeight < 0.F || rawNPCWeight > 100.F)
        throw std::runtime_error("actor weight is unavailable or outside0..100");
    return rawNPCWeight / 100.F;
}
inline bool sourceValueWellFormed(std::string_view name, float value) {
    return claw_matrix_source_value_valid(morphSourceKind(name), value) != 0;
}
inline bool morphRuleWellFormed(const MorphLinkRule& rule) {
    return (rule.constant() ? rule.source.empty() : morphSourceKind(rule.source) >= 0) &&
        morphSourceKind(rule.target) == 0 && !morphFunctionName(rule.function).empty() &&
        std::isfinite(rule.gain) && std::isfinite(rule.cap) && std::isfinite(rule.value) &&
        rule.cap > 0 && rule.cap <= 1 && (rule.constant() || rule.value == 0) &&
        (rule.function == MorphFunction::power ? rule.exponent >= 1 && rule.exponent <= 8 : rule.exponent == 2);
}
struct MorphLink {
    std::string profile;
    std::vector<MorphLinkRule> rules;
    Morphs sourceValues;
    bool captured{};
    [[nodiscard]] bool enabled() const { return !profile.empty(); }
    [[nodiscard]] bool hasProviderSources() const {
        return std::any_of(rules.begin(), rules.end(), [](const auto& rule) {
            return rule.active() && !rule.constant() && morphSourceKind(rule.source) == 0;
        });
    }
    [[nodiscard]] std::string validationError(Sex sex) const {
        if (!enabled()) return rules.empty() && sourceValues.empty() && !captured ? "" : "disabled morph link contains state";
        if (!morphLinkIdentifier(profile) || rules.size() > 128) return "invalid profile identifier or excessive rules";
        std::set<std::pair<std::string, std::string>> pairs;
        std::map<std::string, float> caps;
        (void)sex; // The model's available names, not a compiled sex whitelist, determine geometry support.
        std::set<std::string> sources;
        std::map<std::string, std::string> sourceIdentities, outputIdentities;
        for (const auto& rule : rules) {
            if (!morphRuleWellFormed(rule)) return "invalid morph rule identifier, finite parameter or function";
            if (!rule.active()) continue;
            const auto [output, newOutput] = outputIdentities.emplace(morphProviderIdentity(rule.target), rule.target);
            if (!newOutput && output->second != rule.target) return "case-ambiguous wolf target: " + rule.target;
            if (!rule.constant()) {
                const auto [source, newSource] = sourceIdentities.emplace(morphProviderIdentity(rule.source), rule.source);
                if (!newSource && source->second != rule.source) return "case-ambiguous human source: " + rule.source;
            }
            if (!pairs.emplace(rule.source, rule.target).second) return "duplicate active source/target edge";
            const auto [it, inserted] = caps.emplace(rule.target, rule.cap);
            if (!inserted && it->second != rule.cap) return "inconsistent active target caps";
            if (!rule.constant()) sources.emplace(rule.source);
        }
        if (outputIdentities.size() > 64) return "excessive linked output targets";
        for (const auto& rule : rules)
            if (rule.active() && sourceIdentities.contains(morphProviderIdentity(rule.target))) return "active human source overlaps a wolf output: " + rule.target;
        if (!captured) return sourceValues.empty() ? "" : "uncaptured morph link contains source values";
        if (sourceValues.size() != sources.size()) return "source snapshot does not match active rules";
        for (const auto& [name, value] : sourceValues)
            if (!sources.contains(name) || !sourceValueWellFormed(name, value)) return "invalid active source snapshot";
        return "";
    }
    [[nodiscard]] bool valid(Sex sex) const { return validationError(sex).empty(); }
    // Atomic configuration/load normalization. Old co-saves can retain values
    // for now-inactive sources; only those declared by the old rules may be
    // removed. Unrelated/missing active/nonfinite entries remain errors.
    bool canonicalize(Sex sex, std::string* error = nullptr) {
        auto fail = [&](std::string reason) { if (error) *error = std::move(reason); return false; };
        if (!enabled() && (!rules.empty() || !sourceValues.empty() || captured)) return fail("disabled morph link contains state");
        if (rules.size() > 128) return fail("excessive morph link rules");
        if (!captured && !sourceValues.empty()) return fail("uncaptured morph link contains source values");
        MorphLink staged = *this;
        std::set<std::string> declared, activeSources;
        for (const auto& rule : rules) {
            if (!morphRuleWellFormed(rule)) return fail("invalid morph rule identifier, finite parameter or function");
            if (!rule.constant()) {
                declared.emplace(rule.source);
                if (rule.active()) activeSources.emplace(rule.source);
            }
        }
        for (const auto& [name, value] : sourceValues)
            if (!declared.contains(name) || !sourceValueWellFormed(name, value)) return fail("invalid declared source snapshot");
        std::erase_if(staged.rules, [](const auto& rule) { return !rule.active(); });
        std::erase_if(staged.sourceValues, [&](const auto& row) { return !activeSources.contains(row.first); });
        if (auto reason = staged.validationError(sex); !reason.empty()) return fail(std::move(reason));
        *this = std::move(staged);
        if (error) error->clear();
        return true;
    }
    [[nodiscard]] std::string sourceConflict(const Morphs& previousOutputs) const {
        for (const auto& rule : rules) if (rule.active() && !rule.constant() && !actorWeightSource(rule.source))
            for (const auto& [name, value] : previousOutputs) {
                (void)value;
                if (morphProviderIdentity(name) == morphProviderIdentity(rule.source)) return rule.source;
            }
        return {};
    }
    void capture(const std::function<float(std::string_view)>& read) {
        Morphs observed;
        for (const auto& rule : rules) if (rule.active() && !rule.constant() && !observed.contains(rule.source)) {
            const auto value = read(rule.source);
            if (!sourceValueWellFormed(rule.source, value)) throw std::runtime_error("invalid applied morph or explicit actor scalar");
            observed.emplace(rule.source, value);
        }
        sourceValues = std::move(observed); captured = true;
    }
    // Game adapter only: provider values are already effective. Raw NPC weight
    // is read only for an explicitly declared scalar and normalized once.
    void captureActor(const std::function<float(std::string_view)>& readMorph, float rawNPCWeight) {
        capture([&](std::string_view source) {
            return actorWeightSource(source) ? normalizedActorWeight(rawNPCWeight) : readMorph(source);
        });
    }
    [[nodiscard]] Morphs compose(Sex sex) const {
        if (!valid(sex) || !captured) throw std::runtime_error("morph link profile/source is unavailable or invalid");
        // Linked output starts neutral. Independent presets and unmapped traits
        // cannot contribute; actor weight contributes only as a declared input.
        Morphs result;
        std::set<std::string> activeIdentities;
        for (const auto& rule : rules) if (rule.active()) activeIdentities.emplace(morphProviderIdentity(rule.target));
        for (const auto name : recognizedMorphs(sex))
            if (!activeIdentities.contains(morphProviderIdentity(name))) result.emplace(name, 0.F);
        for (const auto& rule : rules) if (rule.active()) result.emplace(rule.target, 0.F);
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
        std::vector<float> output(targets.size()); std::vector<double> sums(targets.size());
        if (claw_matrix_evaluate(matrix.data(), static_cast<std::uint32_t>(matrix.size()), output.data(), sums.data(), next))
            throw std::runtime_error("morph matrix kernel rejected profile/arithmetic");
        for (const auto& [target, index] : targets) result.at(target) = output.at(index);
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
