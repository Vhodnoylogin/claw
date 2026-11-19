#include "LeasePolicy.h"
#include <cstdlib>
#include <iostream>
#include <limits>

using namespace claw::npc_pose;

void verify(bool ok, const char* description) {
    if (!ok) {
        std::cerr << description << '\n';
        std::exit(1);
    }
}

int main() {
    constexpr std::uint32_t newNpc = 0xFF000802, base = 0x09000800, handle = 0xC00021,
                            cell = 0x0A01A5C6, addon = 0xCDD87;
    verify(validFixture(newNpc, base, handle, cell, addon), "accept the signed Int bit pattern for an owned NPC");
    verify(!validFixture(0x14, base, handle, cell, addon), "refuse the player");
    verify(!validFixture(0xFFFFFFFF, base, handle, cell, addon), "refuse the invalid FormID sentinel");
    verify(!validFixture(newNpc, 0, handle, cell, addon), "refuse missing base");
    verify(!validFixture(newNpc, newNpc, handle, cell, addon), "refuse dynamic base");
    verify(!validFixture(newNpc, base, 0, cell, addon), "refuse missing handle");
    verify(!validFixture(newNpc, base, handle, 0, addon), "refuse missing cell");
    verify(!validFixture(newNpc, base, handle, cell, 0), "refuse missing addon");
    verify(!nextSample(0, -1), "only Begin may create sample zero");
    verify(nextSample(1, 0), "sample one follows the Begin snapshot");
    verify(!nextSample(1, 1), "refuse replayed sequence");
    verify(!nextSample(3, 1), "refuse a skipped sequence");
    verify(nextSample(maximumSequence, maximumSequence - 1), "accept the last bounded sample");
    verify(!nextSample(maximumSequence + 1, maximumSequence), "refuse a sample past the cap");
    verify(!nextSample(0, std::numeric_limits<std::int32_t>::max()), "sequence validation cannot overflow");

    const Transform valid{{1,0,0,0,1,0,0,0,1}, {2,3,4}, 0.5f};
    verify(finite(valid), "accept a complete finite scaled pose");
    auto changed = valid;
    changed.rotation[8] = std::numeric_limits<float>::quiet_NaN();
    verify(!finite(changed), "refuse NaN rotation");
    changed = valid;
    changed.translation[2] = std::numeric_limits<float>::infinity();
    verify(!finite(changed), "refuse infinite translation");
    changed = valid;
    changed.scale = -1.f;
    verify(!finite(changed), "refuse negative scale");
    changed.scale = 0.f;
    verify(!finite(changed), "refuse zero scale");
    std::cout << "20 VR NPC pose policy controls passed\n";
}
