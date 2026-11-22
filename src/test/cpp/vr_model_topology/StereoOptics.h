#pragma once

#include <algorithm>
#include <array>
#include <cmath>

namespace claw::vr_diagnostic {
struct EyeOptics {
    std::array<float, 6> engineFrustum; // left, right, top, bottom, near, far
    std::array<float, 4> engineViewport; // left, right, top, bottom
    std::array<float, 4> providerProjection; // OpenVR raw left, right, top, bottom
    std::array<std::array<float, 4>, 3> providerEyeToHead;
    bool engineOrthographic{};

    bool operator==(const EyeOptics&) const = default;

    [[nodiscard]] bool valid() const {
        const auto finite = [](const auto& values) {
            return std::ranges::all_of(values, [](float value) { return std::isfinite(value); });
        };
        const auto aperture = [](const auto& values) { return values[0] != values[1] && values[2] != values[3]; };
        return finite(engineFrustum) && aperture(engineFrustum) && engineFrustum[4] > 0 && engineFrustum[5] > engineFrustum[4] &&
            finite(engineViewport) && aperture(engineViewport) && finite(providerProjection) && aperture(providerProjection) &&
            std::ranges::all_of(providerEyeToHead, [&](const auto& row) {
                return finite(row) && (row[0] != 0 || row[1] != 0 || row[2] != 0);
            });
    }
};
}  // namespace claw::vr_diagnostic
