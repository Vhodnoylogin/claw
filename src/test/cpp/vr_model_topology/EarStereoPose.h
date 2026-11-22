#pragma once

#include "StereoOptics.h"
#include "TorsoPose.h"
#include <bit>
#include <limits>

namespace claw::vr_diagnostic {
inline constexpr std::array earBones{
    "NPC Spine2 [Spn2]", "NPC Head [Head]", "NPC EarL [EarL]Bone01", "NPC EarL [EarL]Bone02",
    "NPC EarR [EarR]Bone01", "NPC EarR [EarR]Bone02"};
inline constexpr std::array earMorphs{
    "CLAWHeadEarSize", "CLAWHeadEarTilt", "CLAWHeadMuzzleLong", "CLAWHeadMuzzleWide", "CLAWHeadSize"};
inline constexpr std::string_view earShapeName = "head_CLAWHead_CLAWEars";

inline std::string_view earTriPath(bool female) {
    return female ? R"(actors\werewolfbeast\claw\firstperson\female\earworldtrial.tri)" :
                    R"(actors\werewolfbeast\claw\firstperson\male\earworldtrial.tri)";
}

struct StereoOpticsSample {
    RE::NiTransform opticWorld;
    std::array<EyeOptics, 2> eyes;
    bool operator==(const StereoOpticsSample&) const = default;
};

// Read the public, typed provider interface. The SDK's native per-eye
// NiMatrix44 array has no qualified element layout in this build.
template<class Readable>
StereoOpticsSample captureStereoOptics(const RE::NiCamera& camera, vr::IVRSystem& provider, Readable&& readable) {
    using detail::requireTorso;
    const auto& optical = camera.GetVRRuntimeData();
    const auto* frusta = optical.viewFrustumArray;
    const auto* ports = optical.eyeViewportRects.data();
    requireTorso(frusta && readable(frusta) && readable(frusta + 1) && optical.eyeViewportRects.size() == 2 &&
        ports && readable(ports) && readable(ports + 1), "Both engine eye frusta and viewports are required");
    StereoOpticsSample result{};
    result.opticWorld = camera.world;
    requireTorso(detail::validTorsoTransform(result.opticWorld), "Invalid engine optic world transform");
    for (std::size_t i = 0; i < result.eyes.size(); ++i) {
        auto& eye = result.eyes[i];
        const auto& f = frusta[i];
        eye.engineFrustum = {f.fLeft, f.fRight, f.fTop, f.fBottom, f.fNear, f.fFar};
        eye.engineOrthographic = f.bOrtho;
        eye.engineViewport = std::bit_cast<std::array<float, 4>>(ports[i]);
        auto& raw = eye.providerProjection;
        raw.fill(std::numeric_limits<float>::quiet_NaN());
        const auto providerEye = i == 0 ? vr::Eye_Left : vr::Eye_Right;
        provider.GetProjectionRaw(providerEye, &raw[0], &raw[1], &raw[2], &raw[3]);
        const auto transform = provider.GetEyeToHeadTransform(providerEye);
        for (std::size_t row = 0; row < eye.providerEyeToHead.size(); ++row)
            std::ranges::copy(transform.m[row], eye.providerEyeToHead[row].begin());
        requireTorso(eye.valid(), "Nonfinite or degenerate stereo optics");
    }
    return result;
}
}  // namespace claw::vr_diagnostic
