#pragma once
#include "claw/MorphLink.h"

namespace claw {
// At most 64 active named kernel outputs, plus the legacy neutral metadata.
// Only nonzero outputs are written to SKEE, so neutral metadata cannot alter
// its aggregate source calculation or claim additional actual morph keys.
inline constexpr std::size_t maxLinkedCacheMorphs = 64 + 29;
inline constexpr std::size_t maxObservedOwnMorphs = 128;

inline bool validMorphCache(const Morphs& values, Sex sex, bool linked) {
    if (values.size() > maxLinkedCacheMorphs) return false;
    std::set<std::string> identities;
    for (const auto& [name, value] : values)
        if (!morphNameIdentifier(name) || !identities.emplace(morphProviderIdentity(name)).second || !std::isfinite(value) || value < 0 || value > 1 ||
            (!linked && !recognizedMorph(name, sex))) return false;
    return true;
}

// Called by a snapshot visitor, never while clearing/mutating SKEE storage.
// The exact key comparison preserves other providers even on the same name.
inline void observeOwnMorph(Morphs& values, std::string_view name, std::string_view key,
                            float value, std::string_view ownKey) {
    if (morphProviderIdentity(key) != morphProviderIdentity(ownKey)) return;
    if (!morphNameIdentifier(name) || values.size() >= maxObservedOwnMorphs || !values.emplace(name, value).second)
        throw std::runtime_error("invalid or excessive exact-key morph snapshot");
}

inline bool verifyOwnedMorphs(const Morphs& expected, const Morphs& observed, float tolerance) {
    if (!std::isfinite(tolerance) || tolerance < 0 || expected.size() > maxLinkedCacheMorphs || observed.size() > maxObservedOwnMorphs) return false;
    Morphs normalizedExpected, normalizedObserved;
    for (const auto& [name, wanted] : expected) {
        if (!morphNameIdentifier(name) || !std::isfinite(wanted) || !normalizedExpected.emplace(morphProviderIdentity(name), wanted).second) return false;
    }
    for (const auto& [name, actual] : observed)
        if (!morphNameIdentifier(name) || !std::isfinite(actual) || !normalizedObserved.emplace(morphProviderIdentity(name), actual).second) return false;
    for (const auto& [name, wanted] : normalizedExpected) {
        const auto found = normalizedObserved.find(name);
        if ((wanted == 0) != (found == normalizedObserved.end())) return false;
        const float actual = found == normalizedObserved.end() ? 0 : found->second;
        if (!std::isfinite(actual) || std::abs(actual - wanted) > tolerance) return false;
    }
    for (const auto& [name, actual] : normalizedObserved) {
        const auto found = normalizedExpected.find(name);
        if (found == normalizedExpected.end() || found->second == 0) return false;
        const float wanted = found->second;
        if (std::abs(actual - wanted) > tolerance) return false;
    }
    return true;
}

template <class Clear, class Snapshot>
bool clearOwnedMorphs(const Morphs& observed, Clear&& clear, Snapshot&& snapshot, float tolerance) {
    (void)tolerance; // Key absence is structural, not a coefficient tolerance.
    // Enumeration completed before any mutation. Include stale custom names and
    // nonfinite values: cleanup must recover them, not forget their ownership.
    for (const auto& [name, value] : observed) { (void)value; clear(name); }
    return snapshot().empty();
}
}
