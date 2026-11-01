#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <optional>

namespace claw::appearance {
using RGB = std::array<float, 3>;
inline bool valid(const RGB& rgb) {
    return std::all_of(rgb.begin(), rgb.end(), [](float x) { return std::isfinite(x) && x >= 0 && x <= 1; });
}
inline RGB unpack(std::uint32_t rgb) {
    return {float((rgb >> 16) & 255) / 255, float((rgb >> 8) & 255) / 255, float(rgb & 255) / 255};
}
inline std::uint32_t pack(const RGB& rgb) {
    std::uint32_t value{};
    for (float x : rgb) value = (value << 8) | static_cast<std::uint32_t>(std::lround(std::clamp(x, 0.0F, 1.0F) * 255));
    return value;
}
// CCLR v1 persists the source palette as RGB bytes. Use that same precision
// before the first application, so saving/loading cannot change a final tint.
inline std::optional<RGB> paletteColour(const RGB& rgb) {
    if (!valid(rgb)) return std::nullopt;
    return unpack(pack(rgb));
}
// SKEE's immediate key7 write unpacks an RGB integer to the material. Compare
// at that transport's precision, while rejecting non-finite shader values.
inline bool matchesPackedTint(const RGB& actual, std::uint32_t expected) {
    return expected <= 0xFFFFFF && valid(actual) && pack(actual) == expected;
}
// Multiplicative material tint, not replacement albedo. Keep enough light to
// read dark fur; it cannot turn a baked dark diffuse into a white texture.
inline RGB coatTint(const RGB& human, bool fur) {
    RGB result{};
    const float floor = fur ? 0.28F : 0.45F;
    for (unsigned i = 0; i != 3; ++i) result[i] = floor + (1 - floor) * human[i];
    return result;
}
struct Colours {
    RGB skin{}, hair{};
    bool hasSkin{}, hasHair{}, renderedHair{};
    bool operator==(const Colours&) const = default;
};
inline bool valid(const Colours& value) {
    return (!value.hasSkin || valid(value.skin)) && (!value.hasHair || valid(value.hair)) &&
        (!value.renderedHair || value.hasHair);
}
}
