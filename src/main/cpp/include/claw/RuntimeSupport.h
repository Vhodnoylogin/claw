#pragma once
#include <SKSE/Version.h>
#include <array>
#include <cstdint>

namespace claw {
enum class RuntimeFamily { se, ae, vr };
struct RuntimeTarget {
    REL::Version game, minimumSKSE;
    RuntimeFamily family;
};
// Candidate load boundaries, independently of the runtime acceptance status.
inline constexpr std::array runtimeTargets{
    RuntimeTarget{SKSE::RUNTIME_SSE_1_5_97, {2, 0, 20, 0}, RuntimeFamily::se},
    RuntimeTarget{SKSE::RUNTIME_SSE_1_6_640, {2, 2, 3, 0}, RuntimeFamily::ae},
    RuntimeTarget{SKSE::RUNTIME_SSE_1_6_659, {2, 2, 3, 0}, RuntimeFamily::ae},
    RuntimeTarget{SKSE::RUNTIME_SSE_1_6_1170, {2, 2, 6, 0}, RuntimeFamily::ae},
    RuntimeTarget{SKSE::RUNTIME_SSE_1_6_1179, {2, 2, 6, 0}, RuntimeFamily::ae},
    RuntimeTarget{SKSE::RUNTIME_SSE_1_7_104, {2, 3, 1, 0}, RuntimeFamily::ae},
    RuntimeTarget{SKSE::RUNTIME_VR_1_4_15, {2, 0, 12, 0}, RuntimeFamily::vr}
};
inline constexpr const RuntimeTarget* runtimeTarget(REL::Version game, std::uint32_t skse, bool editor = false) {
    if (!editor) for (const auto& target : runtimeTargets)
        if (game == target.game && skse >= target.minimumSKSE.pack()) return &target;
    return nullptr;
}
}
