#pragma once
#include "claw/NamedMatrix.h"
#include <algorithm>
#include <cmath>
#include <functional>
#include <set>
#include <stdexcept>
#include <utility>

namespace claw {
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
    for (auto& ch : result) ch = static_cast<char>(MorphNameLess::fold(static_cast<unsigned char>(ch)));
    return result;
}
inline std::int32_t morphSourceKind(std::string_view name) {
    if (name.size() > 160) return -1;
    return claw_matrix_source_kind(name.data(), static_cast<std::uint32_t>(name.size()));
}
inline bool actorWeightSource(std::string_view name) { return morphSourceKind(name) == 1; }
inline bool humanTraitSource(std::string_view name) { return morphSourceKind(name) >= 2; }
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
    [[nodiscard]] std::string_view bindingError(Sex boundSex, Sex currentSex) const {
        return enabled() && boundSex != currentSex ?
            "linked profile sex differs from the actor; restore the bound sex or explicitly rebind the morph policy" : "";
    }
    [[nodiscard]] bool hasProviderSources() const {
        return std::any_of(rules.begin(), rules.end(), [](const auto& rule) {
            return rule.active() && !rule.constant() && morphSourceKind(rule.source) == 0;
        });
    }
    [[nodiscard]] std::string validationError(Sex sex) const {
        if (!enabled()) return rules.empty() && sourceValues.empty() && !captured ? "" : "disabled morph link contains state";
        if (!morphLinkIdentifier(profile) || rules.size() > CLAW_MATRIX_MAX_RULES) return "invalid profile identifier or excessive rules";
        std::set<std::pair<std::string, std::string>> pairs;
        std::map<std::string, float, MorphNameLess> caps;
        (void)sex; // The model's available names, not a compiled sex whitelist, determine geometry support.
        std::set<std::string, MorphNameLess> sources;
        std::map<std::string, std::string> sourceIdentities, outputIdentities;
        for (const auto& rule : rules) {
            if (!morphRuleWellFormed(rule)) return "invalid morph rule identifier, finite parameter or function";
            if (!rule.active()) continue;
            outputIdentities.emplace(morphProviderIdentity(rule.target), rule.target);
            if (!rule.constant()) sourceIdentities.emplace(morphProviderIdentity(rule.source), rule.source);
            if (!pairs.emplace(morphProviderIdentity(rule.source), morphProviderIdentity(rule.target)).second)
                return "duplicate active source/target edge";
            const auto [it, inserted] = caps.emplace(rule.target, rule.cap);
            if (!inserted && it->second != rule.cap) return "inconsistent active target caps";
            if (!rule.constant()) sources.emplace(rule.source);
        }
        if (outputIdentities.size() > CLAW_MATRIX_MAX_TARGETS) return "excessive linked output targets";
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
        if (rules.size() > CLAW_MATRIX_MAX_RULES) return fail("excessive morph link rules");
        if (!captured && !sourceValues.empty()) return fail("uncaptured morph link contains source values");
        MorphLink staged = *this;
        std::set<std::string, MorphNameLess> declared, activeSources;
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
        for (const auto& rule : rules) if (rule.active() && !rule.constant() && morphSourceKind(rule.source) == 0)
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
            if (humanTraitSource(source)) throw std::runtime_error("human trait requires the explicit human snapshot adapter");
            return actorWeightSource(source) ? normalizedActorWeight(rawNPCWeight) : readMorph(source);
        });
    }
    void captureActor(const std::function<float(std::string_view)>& readMorph, float rawNPCWeight,
        const std::function<float(std::string_view)>& readHuman) {
        capture([&](std::string_view source) {
            if (humanTraitSource(source)) return readHuman(source);
            return actorWeightSource(source) ? normalizedActorWeight(rawNPCWeight) : readMorph(source);
        });
    }
    void captureActor(const std::function<float(std::string_view)>& readMorph, float rawNPCWeight,
        Sex boundSex, Sex currentSex) {
        if (const auto error = bindingError(boundSex, currentSex); !error.empty()) throw std::runtime_error(std::string(error));
        captureActor(readMorph, rawNPCWeight);
    }
    [[nodiscard]] Morphs compose(Sex sex) const {
        if (!valid(sex) || !captured) throw std::runtime_error("morph link profile/source is unavailable or invalid");
        // Linked output starts neutral. Independent presets and unmapped traits
        // cannot contribute; actor weight contributes only as a declared input.
        auto result = evaluateNamed(rules, sourceValues);
        std::set<std::string> activeIdentities;
        for (const auto& [name, value] : result) activeIdentities.emplace(morphProviderIdentity(name));
        for (const auto name : recognizedMorphs(sex))
            if (!activeIdentities.contains(morphProviderIdentity(name))) result.emplace(name, 0.F);
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
