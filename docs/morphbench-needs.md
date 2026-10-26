# Morphbench improvements identified during CLAW development

Analysis against Morphbench `4bc01e41d0cbab8aa99c4aeaa6b713069c4a92da`,
26 October 2026. These are proposals, not implemented Morphbench features. The
tool remains a separate repository; CLAW experiments below do not modify it.

## 1. Evaluate skeletal poses using actual serialized skin frames

Morphbench already reads skin weights, node/skeleton matrices and ragdoll frames,
and evaluates additive TRI morphs. Its model does not retain each shape's complete
skin-to-bone and stored global-to-skin matrices. Static morph evaluation cannot
predict whether a join opens when the breast, spine or clavicle rotates.

Propose `skin_frames()` and `pose_evaluate(recipe, weighting="rawPacked"|"normalized")`:
explicit local pose matrices, preserved scale/ancestry, actual B/C matrices,
rest-product errors, missing-frame refusals and influence/weight-sum audits.
Do not merge mesh-skin frames with Havok ragdoll coordinates or assume that the
engine normalizes weights. This is the first prerequisite for the next items.

Acceptance: independently solved two-bone strip with nonidentity skin frame,
different per-shape binds and nonunit scale. Test rest and rotations, missing bind
rejection, and different raw/normalized results for an imperfect packed sum.

## 2. Frozen skin/fur attachment measurements

Existing `Proximity` analysis maps to a nearest vertex and measures morph amplitude
and contact fractions. A card root over a triangle interior needs a frozen
triangle/barycentric correspondence, not a moving nearest-vertex assignment.

Propose `attachment_bind(...)` and `attachment_report(bindings, states, poses)`:
explicit card groups/root rule, expected fade factor, normal/tangent separation,
attachment-distance change, transported-offset residual and full-card edge change,
with worst face/root IDs. Retain intended overlap and natural rotation of an
offset; a world-fixed offset error alone is not a hole. Never nearest-rebind after
the deformation being measured.

Acceptance: coarse-triangle interior, rigid common rotation, independently weighted
root that separates, and distant card tip. CLAW's `fur_motion.py` is one bounded
subject experiment; a general implementation belongs behind Morphbench's facade.

## 3. Topology and declared seam contracts

TRI/UV/stored normals and normal recalculation already exist. Add explicit boundary
loops, nonmanifold edges, coincident split vertices and a declared cross-shape join
contract through `surface_topology()` / `seam_report(...)`. Report matched-edge
gap, normal angle, UV discontinuity and mismatched weight support separately.
A topology boundary can be an intended opening; a UV island edge is not by itself
a visible crack. A geometric report cannot diagnose a texture's painted seam.

Acceptance: closed cube, missing face, intentional cuff, UV-split cylinder, matching
patches with different normals/UVs, and a join that opens only under a morph/pose.

## 4. Intersections independent of edge strain

Single/set/pair strain and conservative additive bounds already exist. They do not
detect two otherwise rigid patches crossing. Propose accelerated triangle-contact
tests with explicit shape pairs, adjacency exclusions and crossing witnesses.
Classify intended coplanar fur overlap separately. Include degenerate/flipped face
IDs, but do not equate a normal's dot product with an intersection.

Acceptance: rigid intersecting patches with unchanged edge lengths, shared-edge
neighbors, coplanar fur and an intersection at an intermediate coefficient that
endpoint checks miss. Finite state samples must retain their coverage limits.

## 5. First-person perspective/camera clearance

Orbit/focus views and orthographic raster previews already exist. Collider coverage
is not eye or near-plane clearance. Propose `camera_clearance(eye_frames,
projection, states, poses, exclusions)` with nearest-triangle eye clearance,
near-plane crossings and directional occlusion witnesses in explicit units.

Acceptance: safe eye-sphere distance but near-plane crossing, muzzle entering a
forward ray on head turn, and invariance under a common rigid camera/body move.
Imported eye frames remain geometry evidence; real VRIK/HIGGS/runtime visibility
requires separate VR acceptance.

## Delivery boundaries

Implement numerical operations in the existing public facade/CLI first, with
source-pinned inputs and new-file output rules. The current HTTP interface exposes
catalog/payload operations; numerical HTTP calls need a documented extension.
Do not invent endpoints or turn these measurements into automatic artistic fixes.
The highest-value sequence for CLAW is poses, frozen attachments, then seam and
intersection reports. Camera clearance can follow the VR resource prototype.

Primary local source review: Morphbench `morphbench/model.py`, `api.py`,
`analysis.py`, `view.py`, its raster presenter and `docs/http.md`, together with
the existing CLAW [breast rig](breast-rig.md), [geometry repair](geometry-repair.md)
and layer motion experiments. No game or Morphbench release was started by this
analysis.
