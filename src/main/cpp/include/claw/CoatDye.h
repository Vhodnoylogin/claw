#pragma once

#include "claw/CoatMatrix.h"

namespace claw::appearance {
struct CoatDye {
    std::optional<std::uint32_t> tint;
    float opacity{1};
};
struct CoatDyes {
    CoatDye body, hair;
    [[nodiscard]] bool active() const { return body.tint.has_value() || hair.tint.has_value(); }
};
inline const CoatDye& coatSurfaceDye(const CoatDyes& dyes, std::string_view surface) {
    return surface == "body" ? dyes.body : dyes.hair;
}

inline float coatLuma(const RGB& colour) {
    return .2126F * colour[0] + .7152F * colour[1] + .0722F * colour[2];
}

// FaceGen RGB overlay uses 0.5 as its neutral input. Adjust its lightness
// and chroma independently while leaving the original diffuse in the material.
inline std::uint32_t coatOverlay(const RGB& colour, float saturation) {
    const float luma = coatLuma(colour);
    const float lightness = .5F + .55F * (luma - .5F);
    RGB tint{};
    for (std::size_t i = 0; i < tint.size(); ++i)
        tint[i] = lightness + saturation * (colour[i] - luma);
    return pack(tint);
}

inline CoatDyes coatDyes(const CoatValues& outputs, const Colours& colours) {
    const auto unit = [&](std::string_view name) -> std::optional<float> {
        const auto found = outputs.find(name);
        if (found == outputs.end() || !std::isfinite(found->second) || found->second < 0 || found->second > 1) return {};
        return found->second;
    };
    const auto tint = [&](std::string_view red, std::string_view green, std::string_view blue,
                          std::string_view saturation) -> std::optional<std::uint32_t> {
        const auto r = unit(red), g = unit(green), b = unit(blue), s = unit(saturation);
        if (!r || !g || !b || !s) return {};
        return coatOverlay({*r, *g, *b}, *s);
    };
    CoatDyes result;
    if (colours.hasSkin)
        result.body.tint = tint("dye.body.red", "dye.body.green", "dye.body.blue", "dye.body.saturation");
    if (colours.hasHair) {
        result.hair.tint = tint("dye.hair.red", "dye.hair.green", "dye.hair.blue", "dye.hair.saturation");
        if (result.hair.tint)
            result.hair.opacity = std::max(.8F, unit("dye.hair.opacity").value_or(1.F));
    }
    return result;
}
}
