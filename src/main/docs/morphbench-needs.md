# Morphbench improvements identified during CLAW development

## Owner correction, 30 October 2026

Do not add a CLAW-specific built-in tab. A future Morphbench extension system
should register user tabs through a general interface; a separate CLAW add-on
would own human-preset conversion. Neither extension work is required now.
For current development, calculate actual human-to-wolf values externally and
use ordinary Morphbench facade calls to render/inspect frozen human and wolf
states. Keep values, resource identities, weight handling and camera limitations
with the comparison. This does not require executing the SKSE DLL outside Skyrim.

The owner requested direct coordination with the Morphbench chat on 28 October
2026. Use its current capability handoff and exact source revision, rather than
assuming the public archive contains development features. The tool remains a
separate repository; CLAW measurements and authoring stages do not modify it.

## Verified current use, 28 October 2026

The first frozen tool export is Morphbench
`3ddc3afa0c45b74e69210d26d45df40cfe1eac5b`, branch
`feature/collider-physics-ppb`. Its source has working additive morphs, file bounds,
edge-strain/layer diagnostics, node-frame chain capsule fitting, skeleton capsule
coverage, and source-preserving PPB editing. These measurements do not establish
posed skinning, independent NPC-weight interpolation or actual game contact.

CLAW used the actual CLI on four composed endpoints, with the repaired male TRI
explicitly selected. All 86 parts remain inside their stored spheres throughout
the configured additive morph cube 0..1: `overCap=0`, and the largest excess in
each endpoint is negative (-0.0145 to -0.0154). This is file-bound evidence, not
runtime culling acceptance or a proof about animation/physics displacements.
It concerns shape spheres. Separate new Neck NiSkinData spheres were found to
be rest-only and are widened by a CLAW authoring stage; the current Morphbench
command does not certify per-bone bounds. That concrete fixture and the validated
stored B-frame convention were supplied to its owner for a future diagnostic.

```powershell
python '<frozen-morphbench>/mb.py' bounds '<body_0.nif>' --tri '<selected.tri>' --json
python '<frozen-morphbench>/mb.py' binding '<body_0.nif>' --tri '<selected.tri>' `
  --morph CLAWTorsoWaistNarrow --shape head --json
```

Use `MorphBench.chain_capsules(...)` for its documented node-local rest-point
contract. Its raw deformed NIF vertices differ from actual normalized rest-LBS
on these donors. In the female EarSize=1 witness, the difference is 0.278 model
units; a capsule comparison must establish the frame/skin contract first. CLAW
then independently mapped the same vertex into its normalized-LBS region and
confirmed an actual remaining undercoverage witness. Do not reinterpret the
node-local CBPC model as an HKX ragdoll fit.

File visibility is another explicit boundary of this export. Native flags hide
eleven first-person head-side shapes, but the facade's initial `visible_shapes()`
still returns all parts. That viewer inspection policy cannot prove file or
runtime hiding. A concrete fixture and a request for local/inherited visibility
metadata plus a separate respect-file-visibility policy were sent to the
Morphbench chat. Retained torso and hand selection currently uses independently
read NIF flags and the reviewed CLAW profile, not the viewer's default selection.

That focused request is now implemented in Morphbench
`80d8972766e1784b608973f442e94bedd3b93077`. Its public `file_visibility()` reports
native local/inherited state and completeness, while
`respect_file_visibility(on=True, show_hidden=False)` selects an independent
inspection policy. Unknown ancestry remains distinct and excluded under that
policy; ordinary inspection defaults remain available. On all four final CLAW
resources, the exact committed source reports 10/10 female and 11/11 male visible
parts, eleven hidden parts each, and no unknown rows. Explicit show-hidden and
viewer-only selection were checked independently. This closes the tool feedback
loop without treating static NIF visibility as runtime camera evidence.

```python
bench.open(nif_path, tri=tri_path, skeleton="")
native_metadata = bench.file_visibility()
bench.respect_file_visibility(True)
file_visible_parts = bench.visible_shapes()
```

Reproducible source export, actual command output and tool feedback are under
`Builds/claw-morphbench-20261028/`. The remaining proposals below originated in
the 26 October review of `4bc01e41d0cbab8aa99c4aeaa6b713069c4a92da`;
they are not claims that the current tool already supplies those APIs.

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

## 6. Import actual runtime CBPC observations

The owner requested this integration on26October. Morphbench should consume and
compare immutable game observations; a qualified in-game observer must collect
provider-owned CBPC state at a declared update phase. NIF/HKX capsules, configuration
files, Attach success and CLAW's requested-output ledger remain separate evidence.

Reuse `Capsule.mesh/transformed`, facade collider methods and the Web/PNG overlay,
but keep observed, predicted and offline-reference layers distinct. An observation
must retain raw precision rather than the three-decimal authoring serialization.
Do not reinterpret a CBPC node frame as a Havok ragdoll frame, silently substitute
an identity for a missing node, or filter observations through dominant-weight
visibility. Observed records must not enter skeleton saving/editing implicitly.

The capture contract needs actor/runtime/root generation, perspective, provider
DLL/config and collector identities, qualification reference, frame/phase/sequence,
units/axes/space/matrix convention, applied transforms/scales, effective morphs,
actual raw/normalized weight, resource hashes and completeness/truncation. Each
capsule retains its provider-scoped id, node, enabled state, endpoints and radius.
Predictions retain their own model/input identity. Schema details remain a proposal
to agree with the observer implementation, not an invented existing endpoint.

The current model adds TRI offsets but does not retain complete bind matrices,
posed LBS or independent weight-endpoint interpolation. Initially accept captured
skin from the same phase; otherwise show an explicitly labelled reference mesh
and withhold actual capsule-to-rendered-skin fit results. Capsule geometry alone
does not establish contact or solver participation. Neither Blender nor MO2 can
replace in-game provider-state collection.

Read-only review at Morphbench main4bc01e4: `morphbench/colliders.py`, `api.py`,
`model.py`, `placements.py`, `presenters/cbpc.py`, `presenters/web.py`,
`presenters/raster.py` and `web/js/render.js`. No Morphbench source was modified.

## Delivery sequence

Implement numerical operations in the existing public facade/CLI first, with
source-pinned inputs and new-file output rules. The current HTTP interface exposes
catalog/payload operations; numerical HTTP calls need a documented extension.
Do not invent endpoints or turn these measurements into automatic artistic fixes.
The highest-value sequence for CLAW is poses, frozen attachments, then seam and
intersection reports. Camera clearance can follow the VR resource prototype.

Primary local source review: Morphbench `morphbench/model.py`, `api.py`,
`analysis.py`, `view.py`, its raster presenter and its historical `docs/http.md`, together with
the existing CLAW [breast rig](breast-rig.md), [geometry repair](geometry-repair.md)
and layer motion experiments. No game or Morphbench release was started by this
analysis.
