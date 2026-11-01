#include "claw/ColourMath.h"
#include <iostream>
#include <limits>
#include <stdexcept>
int main() {
    using namespace claw::appearance;
    const auto require = [](bool yes) { if (!yes) throw std::runtime_error("colour contract violated"); };
    try {
        for (std::uint32_t rgb : {0U, 0xFFFFFFU, 0x184A2CU, 0xAA00FFU}) require(pack(unpack(rgb)) == rgb);
        for (std::uint32_t rgb : {0U, 0xFFFFFFU, 0x184A2CU, 0xAA00FFU}) require(matchesPackedTint(unpack(rgb), rgb));
        require(!matchesPackedTint(unpack(0x184A2C), 0x184B2C));
        require(!matchesPackedTint({std::numeric_limits<float>::quiet_NaN(), 0, 0}, 0));
        require(!matchesPackedTint({std::numeric_limits<float>::infinity(), 0, 0}, 0));
        require(!matchesPackedTint({0, 0, 1.001F}, 0x0000FF));
        require(!matchesPackedTint({0, 0, 0}, 0x1000000));
        require(!paletteColour({std::numeric_limits<float>::quiet_NaN(), 0, 0}));
        require(!paletteColour({0, 1.001F, 0}));
        // A real free-float HairTint counterexample used to change the final
        // fur byte after CCLR v1 packed only its source during save.
        const RGB freeHair{0.0005493247881531715F, 0, 0};
        require(pack(coatTint(freeHair, true)) == 0x484747);
        require(pack(coatTint(unpack(pack(freeHair)), true)) == 0x474747);
        const auto firstPalette = paletteColour(freeHair);
        require(firstPalette.has_value());
        require(pack(coatTint(*firstPalette, true)) == pack(coatTint(unpack(pack(*firstPalette)), true)));
        require(!valid(RGB{std::numeric_limits<float>::quiet_NaN(), 0, 0}));
        require(!valid(RGB{0, -0.001F, 1}));
        require(!valid(Colours{{}, {}, false, false, true}));
        require(valid(Colours{{}, {}, false, false, false}));
        require(pack(coatTint({1, 1, 1}, true)) == 0xFFFFFF);
        const auto dark = coatTint({0, 0, 0}, true);
        require(dark[0] > 0 && dark[0] < 0.5F);
        const auto red = coatTint({1, 0.2F, 0.1F}, true);
        require(red[0] > red[1] && red[1] > red[2]);
        require(coatTint({0,0,0}, false)[0] > dark[0]);
        for (int i = 0; i <= 255; ++i) {
            const RGB input{float(i)/255, float(255-i)/255, 0.5F};
            for (bool fur : {true, false}) require(valid(coatTint(input, fur)));
            // Every representable source byte survives repeated captures and
            // co-save round trips without tint drift, for both material groups.
            for (unsigned channel = 0; channel != 3; ++channel) {
                RGB byteInput{0.25F, 0.5F, 0.75F}; byteInput[channel] = float(i)/255;
                const auto palette = paletteColour(byteInput);
                require(palette && paletteColour(*palette) == palette);
                const auto restored = unpack(pack(*palette));
                for (bool fur : {true, false}) require(pack(coatTint(*palette, fur)) == pack(coatTint(restored, fur)));
            }
        }
        std::cout << "Colour roundtrip, invalid sources, skin/fur separation and dark-coat floor passed\n";
        return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
