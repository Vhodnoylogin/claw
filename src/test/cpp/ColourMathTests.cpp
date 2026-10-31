#include "claw/ColourMath.h"
#include <iostream>
#include <limits>
#include <stdexcept>
int main() {
    using namespace claw::appearance;
    const auto require = [](bool yes) { if (!yes) throw std::runtime_error("colour contract violated"); };
    try {
        for (std::uint32_t rgb : {0U, 0xFFFFFFU, 0x184A2CU, 0xAA00FFU}) require(pack(unpack(rgb)) == rgb);
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
        }
        std::cout << "Colour roundtrip, invalid sources, skin/fur separation and dark-coat floor passed\n";
        return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
