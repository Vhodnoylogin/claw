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
        // Actual SKSEVR 2.0.12 ABI prefix from PluginManager's SKSEInterface,
        // decoded through the pinned CommonLib QueryInterface getters.
        SKSE::Impl::SKSEInterface vrProbe{};
        vrProbe.skseVersion = 0x020000C0;  // MAKE_EXE_VERSION(2, 0, 12)
        vrProbe.runtimeVersion = 0x010400F1;  // MAKE_EXE_VR_VERSION(1, 4, 15)
        const auto* query = reinterpret_cast<const SKSE::QueryInterface*>(&vrProbe);
        auto fromQuery = [&] { return claw::runtimeTargetFromQuery(query->RuntimeVersion(), query->SKSEVersion(), query->IsEditor()); };
        require(query->RuntimeVersion() == REL::Version{1, 4, 15, 1}, "actual VR query subtype not reproduced");
        require(query->SKSEVersion() == REL::Version{2, 0, 12, 0}.pack(), "actual VR SKSE minimum encoding differs");
        require(!claw::runtimeTarget(query->RuntimeVersion(), query->SKSEVersion()), "canonical policy unexpectedly accepts query subtype");
        const auto* vrTarget = fromQuery();
        require(vrTarget && vrTarget->family == claw::RuntimeFamily::vr && vrTarget->game == SKSE::RUNTIME_VR_1_4_15,
            "actual SKSEVR query ABI refused or canonical module boundary changed");
        vrProbe.skseVersion = 0x020000B0;
        require(!fromQuery(), "VR query alias bypassed SKSE minimum");
        vrProbe.skseVersion = 0x020000C0; vrProbe.isEditor = 1;
        require(!fromQuery(), "VR query alias admitted editor");
        vrProbe.isEditor = 0;
        for (const auto unknown : {0x010400F2U, 0x01040101U, 0x01050611U, 0x01070681U}) {
            vrProbe.runtimeVersion = unknown;
            require(!fromQuery(), "unknown subtype/future query runtime accepted");
        }
        // Both exported metadata and Query/Load use the same source policy.
        SKSE::PluginVersionData metadata;
        for (std::size_t index = 0; index < claw::runtimeTargets.size(); ++index)
            metadata.compatibleVersions[index] = claw::runtimeTargets[index].game.pack();
        require(metadata.compatibleVersions[claw::runtimeTargets.size()] == 0, "metadata list unterminated");
        std::cout << "Universal runtime policy: seven exact versions, actual VR query ABI, per-runtime SKSE minima, editor/future rejection passed\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
