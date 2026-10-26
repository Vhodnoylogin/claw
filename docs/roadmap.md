# CLAW — future plans

Owner-defined priorities, revised 26 October 2026. No release dates are promised.

1. Use real human preset mods and OBody to define each actor's beast morphology
   through shared body-resource conversion rules. The latest owner direction
   requires no separate beast presets. Retain independent beast assignment only
   as an optional compatibility route; qualify the human-driven route first.
2. Repair geometry gaps, including the known underside breast/body separation.
3. Add motion and collision physics for ears and tail. Correct the female breast
   shape and rig before adding its physics. Prefer existing XP32 bones.
   Alongside this stage, add distinct low/high-weight body shapes for both sexes
   (`_0` and `_1`). This is a low-priority enhancement, not a blocker for the next
   preset/distribution, geometry and transformation release. Verify intermediate
   weights, morph combinations, seams and physics against both endpoints.
4. Link human and beast morphology during transformation, preserving both forms
   and other mods' contributions.

After these goals, develop the first-person VR body if the remaining work budget
allows it. Morph-responsive colliders and the optional adult Anatomy/physics
add-on remain later goals; they do not displace the ordered priorities above.

The published resource package remains the starting point for this work. The
known female breast underside gap was accepted for that release; its repair is
future work.

## Development priorities and first work

The 25 October order supersedes the 11 October sequence that placed VR second.
The 26 October manual-session request refines preset interoperability: ordinary
human presets must determine the wolf through morph-to-morph conversion, without
an additional beast preset. Resource-specific mapping is therefore part of this
session's preparation. The earlier independent beast route remains optional.
Prefer keeping XP32 and its existing bones. Replace the skeleton only if a
demonstrated requirement cannot be met otherwise.

- [Distribution reference core](distribution.md): implemented offline mapping,
  stable individual traits and transformation action plans; game controller pending.
- [Independent presets](presets.md): typed XML, optional VR native distributor,
  selector and authoring resources built; runtime acceptance pending.
- [Human/beast morph linkage](transformation.md): native signed coefficient
  conversion is implemented as a development candidate. Linked actors start
  from neutral owned coefficients and bypass beast catalogs, saved choices and
  actor-weight interpolation. Real body-profile calibration and runtime
  transformation/persistence acceptance remain pending.
- [Surface attachment repair](geometry-repair.md): opt-in female candidate built
  with topology/UV data retained. A separate post-export stage repairs the narrow
  head/body skin-weight collar; controlled pose errors improve, while actual
  seams, fur coverage and animation still need qualification.
- [Ear/tail physics source candidate](../physics/README.md): isolated CBPC motion
  maps and actor capsule helper compile; host integration/contact qualification pending.
- [Collider candidates](colliders.md): reproducible offline fitting and measured
  male/female candidates; installation and runtime physics qualification pending.
- [Breast shape and rig](breast-rig.md): verified existing bones, missing mesh
  weights and a separate-part alternative. A moderate shape-only BreastSize profile
  and a separate opt-in P1 skinning stage are implemented. The latter reuses six
  existing XP32 nodes, retains the four-weight budget and verifies serialized
  weights/binds against controlled poses. It does not replace the skeleton.
  A separate pinned composition with the repaired collar passes the offline
  pose checks. Common fur motion, effective physics driver ownership and
  visual/game acceptance remain separate gates.
- [Human-driven morph expansion](morph-expansion.md): proposed localized forearm,
  glute, abdomen and thorax targets have real 3BA/HIMBO sources. Additional head/
  ear conversion needs a separate readable human head-data contract.
- [Morphbench needs](morphbench-needs.md): pose-aware binds, frozen skin/fur joins,
  seam/intersection reports and perspective camera clearance are proposed tool
  improvements, rather than claimed existing measurements.

The owner added first-person VR body work to parallel development on 26 October.
It can proceed beside the remaining source candidates without changing the frozen
SE test environment. The separate [VR body prototype](vr-body.md) records its
resource and runtime-integration boundaries. No manual game or microphone launch
is implied; that still waits for the owner's direct command.
The [head-bone audit](vr-head-policy.md) additionally finds Head-weighted breast
and fur vertices: preserving the mixed shape alone does not qualify head hiding.

These development results do not change or requalify the published0.6.2.0 package.

## Remaining acceptance for the next functional release

The first bounded SE mechanics run on 26 October passed 21 of 68 required checks,
then stopped on a source-change read before the two-second refresh interval could
be guaranteed. One assertion mismatched and 46 checks were not run. This is not
evidence of a persistent mod defect or full runtime acceptance. A corrected
scenario must use bounded read-only polling for asynchronous results.

A later core run on the current direct-link build performed one of ten checks:
catalogs passed, the real male OBody assignment was observed, and source-key
reading became unavailable because the origin/platform binding used the wrong
native function name (`GetBodyMorphKeys` rather than observed `GetMorphKeys`).
Eight checks did not run; no coefficient conversion or race change was reached.
The game ended and restoration was verified. Its later crash exit has an unknown
cause and is not attributed to CLAW. A data-only binding correction is prepared;
the original attempt remains consumed, with no automatic replay or acceptance.

- Finish both-sex direct link checks, clearing, suppression/resume and human/beast
  return transitions with independent keyed readback. Keep optional independent
  preset compatibility checks separate from the human-driven acceptance.
- Check several actor references, including shared NPC bases, human OBody
  assignment/selection and save/load persistence without unintended rerolls.
- Check actual human OBody coexistence and calibrated human morph mapping;
  synthetic source values alone do not qualify a real body-resource profile.
- Inspect the repaired geometry in game for both sexes, representative poses and
  strong morph combinations, including breast underside, collar and fur seams.
- Verify the SE runtime build, final archive, fresh installation and upgrade
  behavior in this round. The owner excluded VR testing from this session.
  Offline builds and mesh bounds do not replace game checks.

New physics, distinct weight-endpoint geometry, VR first-person body and adult
Anatomy remain later work; they do not block this functional release.
