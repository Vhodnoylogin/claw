# CLAW — future plans

Owner-defined priorities, revised 26 October 2026. No release dates are promised.

1. Make working CLAW presets distributable as independent mods, as with human
   bodies. Determine whether stock OBody is sufficient; implement an optional
   companion when its family filtering/distribution APIs are insufficient.
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
Preset interoperability and a usable independent preset ecosystem come first;
human-to-beast coefficient mapping is fourth, not a prerequisite for distribution.
Prefer keeping XP32 and its existing bones. Replace the skeleton only if a
demonstrated requirement cannot be met otherwise.

- [Distribution reference core](distribution.md): implemented offline mapping,
  stable individual traits and transformation action plans; game controller pending.
- [Independent presets](presets.md): typed XML, optional VR native distributor,
  selector and authoring resources built; runtime acceptance pending.
- [Human/beast morph linkage](transformation.md): native signed coefficient
  conversion is implemented as a development candidate. Preset names do not
  select paired beast presets; real body-profile calibration and runtime
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

These development results do not change or requalify the published0.6.2.0 package.

## Remaining acceptance for the next functional release

The first bounded SE mechanics run on 26 October passed 21 of 68 required checks,
then stopped on a source-change read before the two-second refresh interval could
be guaranteed. One assertion mismatched and 46 checks were not run. This is not
evidence of a persistent mod defect or full runtime acceptance. A corrected
scenario must use bounded read-only polling for asynchronous results.

- Finish both-sex preset/link checks, clearing, suppression/resume, manual
  overrides and human/beast return transitions with independent keyed readback.
- Check several actor references, including shared NPC bases, stable population
  assignment, the selector, and save/load persistence without unintended rerolls.
- Check actual human OBody coexistence and calibrated human morph mapping;
  synthetic source values alone do not qualify a real body-resource profile.
- Inspect the repaired geometry in game for both sexes, representative poses and
  strong morph combinations, including breast underside, collar and fur seams.
- Verify the intended SE/VR runtime builds, final archives, fresh installation
  and upgrade behavior. Offline builds and mesh bounds do not replace game checks.

New physics, distinct weight-endpoint geometry, VR first-person body and adult
Anatomy remain later work; they do not block this functional release.
