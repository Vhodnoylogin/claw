#pragma once
#include "claw/MorphLink.h"
#include <bit>

namespace claw {
inline constexpr std::uint32_t actorMatrixRecordVersion = 6;
// The byte layout is unchanged, but pre-v6 names were all SKEE morphs. Never
// reinterpret an old source/output from the now-reserved actor namespace.
inline bool legacyActorInputNeedsRebind(const MorphLink& link, std::uint32_t version) {
    if (version >= actorMatrixRecordVersion) return false;
    const auto reserved = [](std::string_view name) { return morphNameIdentifier(name) && morphSourceKind(name) != 0; };
    return std::any_of(link.rules.begin(), link.rules.end(), [&](const auto& rule) {
        return reserved(rule.source) || reserved(rule.target);
    });
}
// Shared by the actual SKSE record path and offline migration/roundtrip checks.
template <class WriteString, class WriteInteger>
void writeMorphRule(const MorphLinkRule& rule, WriteString&& string, WriteInteger&& u32) {
    string(rule.source); string(rule.target);
    u32(std::bit_cast<std::uint32_t>(rule.gain)); u32(std::bit_cast<std::uint32_t>(rule.cap));
    u32(static_cast<std::uint32_t>(rule.function)); u32(rule.exponent);
    u32(std::bit_cast<std::uint32_t>(rule.value));
}
template <class Reader>
MorphLinkRule readMorphRule(Reader& reader, std::uint32_t version) {
    MorphLinkRule rule;
    rule.source = reader.string(); rule.target = reader.string();
    rule.gain = std::bit_cast<float>(reader.u32()); rule.cap = std::bit_cast<float>(reader.u32());
    if (version >= 5) {
        rule.function = static_cast<MorphFunction>(reader.u32()); rule.exponent = reader.u32();
        rule.value = std::bit_cast<float>(reader.u32());
    } // v2..v4 retain initialized linear/2/0 defaults.
    return rule;
}
}
