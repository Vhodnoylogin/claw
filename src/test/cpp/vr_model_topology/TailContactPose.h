#pragma once

#include "TorsoPose.h"

namespace claw::vr_diagnostic {
// Positive influences and nonzero TRI records on the body triangles owned
// by TailBone02, slots 108–111, for the equipped models of both sexes.
inline constexpr std::array tailContactBones{
    "NPC Pelvis [Pelv]", "TailBone01", "TailBone02", "TailBone03", "TailBone04"};
inline constexpr std::array tailContactMorphs{
    "CLAWLegThighGirth", "CLAWLegThighLean", "CLAWTailFluff", "CLAWTailLength", "CLAWTailLift",
    "CLAWTorsoFlankWidth", "CLAWTorsoGirth", "CLAWTorsoLean"};
inline constexpr SkinPoseFields tailContactFields{tailContactBones, tailContactMorphs, {}, {}, 65, "TailBone02"};
inline constexpr std::string_view tailContactShape = "body";
inline constexpr unsigned tailContactVertices = 18359;
inline constexpr unsigned tailContactTriangles = 34195;

inline bool hasTailContactTopology(RE::BSGeometry& body) {
    const auto* shape = body.AsTriShape();
    if (!shape) return false;
    const auto& extent = shape->GetTrishapeRuntimeData();
    if (extent.vertexCount == tailContactVertices && extent.triangleCount == tailContactTriangles) return true;
    if ((extent.vertexCount && extent.vertexCount != tailContactVertices) ||
        (extent.triangleCount && extent.triangleCount != tailContactTriangles)) return false;
    const auto skin = body.GetGeometryRuntimeData().skinInstance;
    const auto partition = skin ? skin->skinPartition : RE::NiPointer<RE::NiSkinPartition>{};
    if (!partition || partition->vertexCount != tailContactVertices || !partition->numPartitions ||
        partition->numPartitions > 256 || partition->numPartitions != partition->partitions.size()) return false;
    std::size_t triangles{};
    for (const auto& row : partition->partitions) {
        if (row.strips || !row.triangles || !row.triList) return false;
        triangles += row.triangles;
    }
    return triangles == tailContactTriangles;
}
}  // namespace claw::vr_diagnostic
