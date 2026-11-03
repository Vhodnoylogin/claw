#include "claw/MaterialLease.h"
#include <iostream>
#include <limits>
#include <stdexcept>

namespace {
void require(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
}
int main() {
    using namespace claw::appearance;
    try {
        MaterialLeaseState initialized;
        initialized.uvScale = {1, 1, 1, 1};
        initialized.specularColour = {0.6F, 0.7F, 0.8F};
        initialized.materialAlpha = initialized.propertyAlpha = 1;
        initialized.specularPower = 0.25F; initialized.specularScale = 1;
        initialized.diffuseTarget = -1; initialized.clampMode = 3;
        initialized.textures = {1, 2, 3, 4}; initialized.textureSet = 5;
        require(mayRestoreMaterial(initialized, initialized), "Unchanged initialized material lost rollback authority");
        // These are same-property, same-material, same-tint/guard takeovers.
        // The earlier ownership test did not inspect any of these mutations,
        // then restored the entire old property and discarded the new value.
        const auto yields = [&](auto change) {
            auto current = initialized; change(current);
            require(!mayRestoreMaterial(initialized, current), "A later in-place material change was overwritten");
        };
        yields([](auto& s) { s.specularPower = 16; });
        yields([](auto& s) { s.specularColour[1] = 0.1F; });
        yields([](auto& s) { s.specularScale = 0.5F; });
        yields([](auto& s) { s.textures[1] = 20; });
        yields([](auto& s) { s.textures[2] = 30; });
        yields([](auto& s) { s.textures[3] = 40; });
        yields([](auto& s) { s.materialAlpha = 0.4F; });
        yields([](auto& s) { s.propertyAlpha = 0.6F; });
        yields([](auto& s) { s.uvOffset[2] = 0.25F; });
        yields([](auto& s) { s.uvScale[3] = 2; });
        yields([](auto& s) { s.flags ^= 1ULL << 36; }); // two-sided shader flag
        yields([](auto& s) { s.effectData = 60; });
        yields([](auto& s) { s.textureSet = 50; });
        yields([](auto& s) { s.diffuseTarget = 1; });
        yields([](auto& s) { s.clampMode = 0; });
        yields([](auto& s) { s.refractionPower = 0.2F; });
        yields([](auto& s) { s.subSurfaceRolloff = 0.3F; });
        yields([](auto& s) { s.rimPower = 0.7F; });
        yields([](auto& s) { s.specularPower = std::numeric_limits<float>::quiet_NaN(); });
        auto invalid = initialized; invalid.propertyAlpha = std::numeric_limits<float>::quiet_NaN();
        require(!mayRestoreMaterial(invalid, invalid), "NaN material witness manufactured rollback authority");
        std::cout << "Material rollback preserves later normal/specular/alpha/UV/flags/effect changes\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
