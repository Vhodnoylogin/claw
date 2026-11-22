#pragma once

#include <RE/Skyrim.h>
#include <IPluginInterface.h>

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <stdexcept>
#include <string_view>
#include <vector>

#if !defined(SKYRIM_CROSS_VR)
#error Build with the same cross-runtime CommonLib ABI as the CLAW DLL.
#endif

namespace claw::vr_diagnostic {
using TorsoClock = std::chrono::steady_clock;

// Positive skin weights and named TRI fields of the retained HEAD torso from
// the pinned VR assets. The female asset adds two bones and six morph fields.
inline constexpr std::array torsoBones{
    "NPC Spine2 [Spn2]", "NPC L Clavicle [RClv]", "NPC L UpperarmTwist1 [LUt1]",
    "NPC Spine1 [Spn1]", "NPC L UpperArm [RUar]", "NPC L UpperarmTwist2 [LUt2]",
    "NPC Spine [Spn0]", "NPC R Clavicle [RClv]", "NPC R UpperarmTwist1 [RUt1]",
    "NPC R UpperarmTwist2 [RUt2]", "NPC R UpperArm [RUar]", "NPC Neck [Neck]"};
inline constexpr std::array femaleTorsoBones{"NPC L Breast P1", "NPC R Breast P1"};
inline constexpr std::array torsoMorphs{
    "CLAWArmGirth", "CLAWArmLean", "CLAWTorsoBackWide", "CLAWTorsoBellyRound", "CLAWTorsoChestSize",
    "CLAWTorsoGirth", "CLAWTorsoLean", "CLAWTorsoNeckGirth", "CLAWTorsoShoulderGirth", "CLAWTorsoWaistNarrow"};
inline constexpr std::array femaleTorsoMorphs{
    "CLAWHeadMuzzleLong", "CLAWHeadMuzzleWide", "CLAWHeadSize",
    "CLAWLegThighGirth", "CLAWLegThighLean", "CLAWTorsoBreastSize"};

struct NamedTorsoTransform {
    const char* name;  // Static observation-plan name.
    RE::NiTransform world;
};

struct NamedTorsoMorph {
    const char* name;  // Static observation-plan name.
    float value;
};

struct TorsoPose {
    std::vector<NamedTorsoTransform> bones;
    std::vector<NamedTorsoMorph> effectiveMorphs;
};

namespace detail {
inline void requireTorso(bool condition, const char* reason) {
    if (!condition) throw std::runtime_error(reason);
}

inline bool torsoRoute(const RE::NiAVObject& object, const RE::NiAVObject& root, bool visible = false) {
    auto* node = &object;
    for (unsigned depth = 0; node && depth != 32; ++depth, node = node->parent) {
        if (visible && node->GetAppCulled()) return false;
        if (node == &root) return true;
    }
    return false;
}

inline bool validTorsoTransform(const RE::NiTransform& transform) {
    if (!std::isfinite(transform.scale) || transform.scale <= 0 ||
        !std::isfinite(transform.translate.x) || !std::isfinite(transform.translate.y) ||
        !std::isfinite(transform.translate.z)) return false;
    return std::ranges::all_of(transform.rotate.entry, [](const auto& row) {
        return std::ranges::all_of(row, [](float value) { return std::isfinite(value); });
    });
}
}  // namespace detail

// The outer post-phase observer owns the stable player, exact active Body32,
// admitted asset hashes and camera. This returns a numerical sample only.
// Engine references are retained locally and never leave the callback.
inline TorsoPose captureTorsoPose(RE::Actor& actor, RE::NiAVObject& actorRoot, RE::NiAVObject& bodyClone,
    RE::BSGeometry& torso, IBodyMorphInterface& morphs, TorsoClock::time_point deadline) {
    using detail::requireTorso;
    auto* base = actor.GetActorBase();
    requireTorso(base && morphs.GetVersion() >= IBodyMorphInterface::kPluginVersion4,
        "Expected an owned actor and the SKEE BodyMorph ABI");
    const auto sex = base->GetSex();
    requireTorso(sex == RE::SEX::kMale || sex == RE::SEX::kFemale, "Unknown torso palette sex");
    const bool female = sex == RE::SEX::kFemale;
    const std::string_view name = torso.name.c_str();
    requireTorso(name == "HEAD" || name == "head", "Expected the retained HEAD torso geometry");
    const auto currentRoute = [&] {
        return actor.GetActorBase() == base && base->GetSex() == sex && actor.Get3D(false) == &actorRoot &&
            detail::torsoRoute(torso, bodyClone, true) && detail::torsoRoute(bodyClone, actorRoot, true);
    };
    requireTorso(currentRoute(), "Retained torso is not in the admitted active world body");

    const auto skin = torso.GetGeometryRuntimeData().skinInstance;
    const auto data = skin ? skin->skinData : RE::NiPointer<RE::NiSkinData>{};
    const auto count = data ? data->GetBoneCount() : 0U;
    auto* const palette = skin ? skin->bones : nullptr;
    constexpr std::size_t maxPaletteBones = 64;
    requireTorso(palette && count > 0 && count <= maxPaletteBones, "Invalid retained torso skin palette");
    std::array<RE::NiPointer<RE::NiAVObject>, maxPaletteBones> bound;
    for (std::size_t i = 0; i < count; ++i) bound[i].reset(palette[i]);

    TorsoPose result;
    result.bones.reserve(torsoBones.size() + (female ? femaleTorsoBones.size() : 0));
    result.effectiveMorphs.reserve(torsoMorphs.size() + (female ? femaleTorsoMorphs.size() : 0));
    for (auto field : torsoMorphs) result.effectiveMorphs.push_back({field, 0});
    if (female) for (auto field : femaleTorsoMorphs) result.effectiveMorphs.push_back({field, 0});
    auto* reference = reinterpret_cast<::TESObjectREFR*>(static_cast<RE::TESObjectREFR*>(&actor));
    const auto readMorph = [&](const char* field) {
        requireTorso(TorsoClock::now() < deadline, "Torso capture budget expired");
        const float value = morphs.GetBodyMorphs(reference, field);
        requireTorso(std::isfinite(value), "Nonfinite effective torso morph");
        return value;
    };
    for (auto& field : result.effectiveMorphs) field.value = readMorph(field.name);

    std::array<RE::NiAVObject*, torsoBones.size() + femaleTorsoBones.size()> captured{};
    const auto captureBone = [&](const char* bone) {
        requireTorso(TorsoClock::now() < deadline, "Torso capture budget expired");
        RE::NiAVObject* selected = nullptr;
        for (std::size_t i = 0; i < count; ++i) {
            if (!bound[i] || std::string_view(bound[i]->name.c_str()) != bone) continue;
            requireTorso(!selected, "Ambiguous retained torso skin bone");
            selected = bound[i].get();
        }
        requireTorso(selected && detail::torsoRoute(*selected, actorRoot), "Missing owned torso skin bone");
        const auto world = selected->world;
        requireTorso(detail::validTorsoTransform(world), "Invalid torso skin bone transform");
        captured[result.bones.size()] = selected;
        result.bones.push_back({bone, world});
    };
    for (auto bone : torsoBones) captureBone(bone);
    if (female) for (auto bone : femaleTorsoBones) captureBone(bone);
    for (const auto& field : result.effectiveMorphs)
        requireTorso(readMorph(field.name) == field.value, "Effective torso morphs changed during capture");

    requireTorso(TorsoClock::now() < deadline && currentRoute() &&
        torso.GetGeometryRuntimeData().skinInstance == skin && skin->skinData == data &&
        skin->bones == palette && data->GetBoneCount() == count, "Retained torso skin changed during capture");
    for (std::size_t i = 0; i < count; ++i)
        requireTorso(palette[i] == bound[i].get(), "Retained torso bone palette changed during capture");
    for (std::size_t i = 0; i < result.bones.size(); ++i) {
        const auto& bone = result.bones[i];
        requireTorso(detail::torsoRoute(*captured[i], actorRoot) && captured[i]->name == bone.name &&
            captured[i]->world == bone.world, "Retained torso bone changed during capture");
    }
    requireTorso(TorsoClock::now() < deadline, "Torso capture budget expired");
    return result;
}
}  // namespace claw::vr_diagnostic
