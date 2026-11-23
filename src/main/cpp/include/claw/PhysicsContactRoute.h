#pragma once

#include <algorithm>
#include <cstdint>
#include <optional>
#include <string_view>

namespace claw {

enum class PhysicsContactRoute { stock, equipped };

struct ContactArmorForms {
    std::uint32_t item{}, addon{};
    bool operator==(const ContactArmorForms&) const = default;
};

inline constexpr ContactArmorForms stockContactForms{0xCDD86, 0xCDD87};
inline constexpr std::uint32_t equippedContactItem = 0x801, equippedContactAddon = 0x800;
inline constexpr std::string_view equippedContactPlugin = "test_CLAW - VR Player Body32.esp";
inline constexpr std::string_view equippedEarShape = "head_CLAWHead_CLAWEars";
inline constexpr std::string_view dispatchMarkerPrefix = "CLAW_VR_DISPATCH_PROBE_";

constexpr bool samePhysicsAssetPath(std::string_view observed, std::string_view expected) {
    const auto normalize = [](char c) {
        if (c == '/') return '\\';
        return c >= 'A' && c <= 'Z' ? static_cast<char>(c - 'A' + 'a') : c;
    };
    return std::ranges::equal(observed, expected, {}, normalize, normalize);
}

constexpr std::string_view equippedContactModelPath(bool female) {
    return female ? R"(Actors\WerewolfBeast\CLAW\FirstPerson\female\EarWorldTrial.nif)" :
                    R"(Actors\WerewolfBeast\CLAW\FirstPerson\male\EarWorldTrial.nif)";
}

constexpr std::string_view equippedWorldMarker(bool female) {
    return female ? "CLAW_VR_DISPATCH_PROBE_W_F" : "CLAW_VR_DISPATCH_PROBE_W_M";
}

// The engine adapter resolves and verifies the optional fixture pair from its own ESP.
constexpr std::optional<PhysicsContactRoute> contactRoute(ContactArmorForms active,
        const std::optional<ContactArmorForms>& fixture, bool isPlayer, bool bufferedEmpty,
        std::string_view worldPath, bool female) {
    if (active == stockContactForms) return PhysicsContactRoute::stock;
    if (!fixture || !isPlayer || !bufferedEmpty || active != *fixture ||
        active.item >> 24 == 0 || active.item >> 24 >= 0xFE ||
        (active.item & 0xFFFFFF) != equippedContactItem || active.addon != active.item - 1 ||
        !samePhysicsAssetPath(worldPath, equippedContactModelPath(female))) return std::nullopt;
    return PhysicsContactRoute::equipped;
}

} // namespace claw
