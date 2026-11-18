# Beast-race and mixed-body acceptance scenario

This is a nonshipping scenario specification, not a ready Polygon order, installed
fixture, launch authorization or game result. Resolve the current testing
workflow, installed inputs and shared custody before preparing an actual order.

Use the existing inspection kit's fixed QASmoke anchor, AI/collision state
verification, explicit locomotion hold and owned-reference/save lifecycle.
Do not replay toggles blindly or assume old runtime FormIDs. Keep test controls,
generated plugins, archives, actual body outputs and raw observations outside Git.

## Beast-race source cases

Use a Khajiit and an Argonian of each sex, with independently resolved current
source race, NPC/root-face-NPC and skin identity. The normal and vampire race
identifiers, inspected torso/tail paths and available raw face channels are in
[`beast-races-20261118.md`](../../../docs/beast-races-20261118.md). Those are pinned
master-record observations, not substitutes for actual winning records.

1. Before transformation, collect all keyed SKEE source contributions, weight,
   raw NPC/race/reference height factors, supported FaceGen values and availability,
   hair/feather and body tint, and actual naked body NIF/BODYTRI identity. Separate
   zero values from missing channels. Observe separate source race-tail parts.
2. Transform one owned reference, wait for actual race/model completion and compare
   every target against the shared native evaluator using that actor's measured
   inputs and its actual `GetMorphFamily` binding. Do not compare to a hand-picked
   desired wolf preset or infer a colour source from the screenshot.
3. Repeat for the remaining actors, then model refresh and an owned save/load.
   Verify human snapshots, provider keys, race/face provenance and source-tail
   restoration on return to the actual retained original race.
4. Add the normal/vampire variants as a separate bounded group when the basic
   four-actor lifecycle passes. Include unavailable FaceData/zero-source cases.

Expected current limitations: only five raw face slots plus stature are typed
inputs; categorical head parts and source-tail measurements are absent. Current
coat selection uses the captured hair channel, including Argonian HCLF feather
colour. This run must report that behavior, not assert an unimplemented pelt/scale
policy. Facial/hue resemblance remains a separate quality assessment.

## Simultaneous resource-family cases

Prepare two actual human female NPCs at the same time: one CBBE/3BA default skin
and one BHUNP custom skin with its own body NIF/TRI, matching hands/feet, compatible
UV textures and outfit output. Dependencies stay separately source-accounted;
do not copy selected third-party source assets into a generic test fixture.
Generated BodySlide outputs may be independently accounted as generated mods.

1. Pin the custom NPC skin ARMO, race-compatible body-slot ARMA, both endpoint
   model paths, actual built NIF/TRI and full profile catalog. Install the explicit
   compatibility map documented in [mixed-body-families.md](../../../../main/docs/mixed-body-families.md).
   Both profiles must exist; a normal FOMOD's selected pair alone is insufficient.
2. First test automatic human-form adoption without calling ConfigureMorphFamily.
   Require two distinct actual family bindings from GetMorphFamily. Capture
   actual inputs, including a shared-name nonzero control and a zero-valued
   supported control; compare each actor to its own matrix, never their sum.
3. Transform both, refresh, save/load and return; repeat exact family/source/target
   checks. Equip different clothing while human and confirm clothing alone never
   changes the stored body-family assignment.
4. Run isolated negative cases: conflicting mapped skin addons; a missing or
   wrong-sex profile; malformed present map; no optional map; an unmapped body;
   and an actor first seen as a wolf. Invalid bindings withhold new automatic
   adoption; unmapped/absent and valid-map first-seen wolf use the declared default.
   Previously stored/manual matrices remain authoritative throughout.
5. Explicitly rebind one existing actor through ConfigureMorphFamily; require
   completion, correct actual family and preservation of the other actor and
   foreign SKEE keys. Do not silently migrate saved actors when XML changes.

Only after this full installation/lifecycle evidence should the installer offer
mixed-family profile selection. The current installer remains single-select.
Exit normally and verify native/profile/save restoration; retain any failed or
unrun phases with their actual status.
