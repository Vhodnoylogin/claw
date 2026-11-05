#pragma once
#include "claw/MorphLink.h"
#include <array>
#include <bit>
#include <cmath>
#include <optional>

namespace claw {
// Raw NPC NAM6, current-race sex height and reference scale percent. Do not pass
// GetBaseHeight/GetHeight here: they already include some or all of these terms.
inline std::optional<float> humanReferenceHeight(float npcHeight, float raceSexHeight, float referenceScalePercent) {
    if (!std::isfinite(npcHeight) || npcHeight <= 0 || !std::isfinite(raceSexHeight) || raceSexHeight <= 0 ||
        !std::isfinite(referenceScalePercent) || referenceScalePercent <= 0) return std::nullopt;
    const auto height = (npcHeight * raceSexHeight) * (referenceScalePercent / 100.F);
    return std::isfinite(height) && height > 0 ? std::optional<float>{height} : std::nullopt;
}
// Raw vanilla FaceGen slots, not SKEE body/custom-face controls. These indices
// are checked against the pinned CommonLib enums by the game adapter.
inline constexpr std::array<std::pair<std::string_view, std::uint32_t>, 5> humanFaceChannels{{
    {"$human.face.noseLength", 0}, {"$human.face.jawWidth", 3}, {"$human.face.jawForward", 4},
    {"$human.face.chinWidth", 14}, {"$human.face.chinForward", 16}
}};
struct HumanTraits {
    std::uint32_t race{}, npc{}, faceNPC{};
    Sex sex{};
    Morphs values; // Presence is availability; a present zero is a real neutral value.
    [[nodiscard]] bool observed() const { return race != 0 && npc != 0; }
    [[nodiscard]] bool valid() const {
        if (!observed()) return race == 0 && npc == 0 && faceNPC == 0 && values.empty();
        if (sex != Sex::male && sex != Sex::female) return false;
        for (const auto& [name, value] : values)
            if (!humanTraitSource(name) || !sourceValueWellFormed(name, value) ||
                (morphSourceKind(name) == 2 && !faceNPC)) return false;
        return values.size() <= humanFaceChannels.size() + 1;
    }
    // Refresh the complete human snapshot atomically, including unavailable
    // channels. A missing field cannot revive an older face/race/sex's value.
    void observe(std::uint32_t sourceRace, std::uint32_t sourceNPC, std::uint32_t sourceFaceNPC, Sex sourceSex,
        std::optional<float> height, const std::function<std::optional<float>(std::uint32_t)>& face) {
        HumanTraits staged{sourceRace, sourceNPC, sourceFaceNPC, sourceSex, {}};
        if (height && sourceValueWellFormed("$human.height", *height)) staged.values.emplace("$human.height", *height);
        if (sourceFaceNPC) for (const auto& [name, slot] : humanFaceChannels)
            if (const auto value = face(slot); value && sourceValueWellFormed(name, *value)) staged.values.emplace(name, *value);
        if (!staged.observed() || !staged.valid()) throw std::runtime_error("invalid human trait provenance");
        *this = std::move(staged);
    }
    [[nodiscard]] bool available(std::string_view source, Sex boundSex) const {
        return observed() && sex == boundSex && values.contains(std::string(source));
    }
    [[nodiscard]] float input(std::string_view source, Sex boundSex) const {
        if (!humanTraitSource(source)) throw std::runtime_error("not an explicit human source");
        if (available(source, boundSex)) return values.at(std::string(source));
        // These arithmetic neutrals do not create an available snapshot entry.
        return claw_matrix_source_neutral(morphSourceKind(source));
    }
    [[nodiscard]] std::string unavailable(const MorphLink& link, Sex boundSex) const {
        std::set<std::string> missing;
        for (const auto& rule : link.rules)
            if (rule.active() && !rule.constant() && humanTraitSource(rule.source) && !available(rule.source, boundSex)) missing.emplace(rule.source);
        std::string result;
        for (const auto& source : missing) { if (!result.empty()) result += ", "; result += source; }
        return result;
    }
};
template <class WriteInteger, class WriteString>
void writeHumanTraits(const HumanTraits& traits, WriteInteger&& u32, WriteString&& string) {
    if (!traits.valid()) throw std::runtime_error("invalid human trait snapshot");
    u32(traits.race); u32(traits.npc); u32(traits.faceNPC); u32(static_cast<std::uint32_t>(traits.sex));
    u32(static_cast<std::uint32_t>(traits.values.size()));
    for (const auto& [name, value] : traits.values) { string(name); u32(std::bit_cast<std::uint32_t>(value)); }
}
template <class Reader>
HumanTraits readHumanTraits(Reader& reader) {
    HumanTraits traits;
    traits.race = reader.u32(); traits.npc = reader.u32(); traits.faceNPC = reader.u32();
    const auto sex = reader.u32();
    if (sex > static_cast<std::uint32_t>(Sex::female)) throw std::runtime_error("invalid human trait sex");
    traits.sex = static_cast<Sex>(sex);
    const auto count = reader.u32();
    if (count > humanFaceChannels.size() + 1) throw std::runtime_error("excessive human trait snapshot");
    for (std::uint32_t index = 0; index < count; ++index) {
        const auto name = reader.string(); const auto value = std::bit_cast<float>(reader.u32());
        if (!traits.values.emplace(name, value).second) throw std::runtime_error("duplicate human trait snapshot value");
    }
    if (!traits.valid()) throw std::runtime_error("invalid human trait snapshot");
    return traits;
}
}
