#include <RE/Skyrim.h>
#include <SKSE/SKSE.h>
#include "claw/RuntimeSupport.h"
#include <iostream>
#include <stdexcept>

int main() {
    try {
        auto require = [](bool value, const char* message) { if (!value) throw std::runtime_error(message); };
        std::uint32_t families{};
        for (const auto& target : claw::runtimeTargets) {
            require(claw::runtimeTarget(target.game, target.minimumSKSE.pack()) == &target, "supported runtime/minimum refused");
            require(!claw::runtimeTarget(target.game, target.minimumSKSE.pack() - 1), "older SKSE accepted");
            require(!claw::runtimeTarget(target.game, target.minimumSKSE.pack(), true), "editor accepted");
            families |= 1U << static_cast<unsigned>(target.family);
        }
        require(families == 7 && claw::runtimeTargets.size() == 7, "not all three runtime families covered");
        require(!claw::runtimeTarget(REL::Version{1, 7, 105, 0}, 0xffffffff), "unknown future runtime accepted");
        require(!claw::runtimeTarget(REL::Version{1, 4, 16, 0}, 0xffffffff), "unknown VR accepted");
        // Both exported metadata and Query/Load use the same source policy.
        SKSE::PluginVersionData metadata;
        for (std::size_t index = 0; index < claw::runtimeTargets.size(); ++index)
            metadata.compatibleVersions[index] = claw::runtimeTargets[index].game.pack();
        require(metadata.compatibleVersions[claw::runtimeTargets.size()] == 0, "metadata list unterminated");
        std::cout << "Universal runtime policy: seven exact versions, per-runtime SKSE minima, editor/future rejection passed\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
