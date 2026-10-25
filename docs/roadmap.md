# CLAW — future plans

Owner-defined priorities, revised 25 October 2026. No release dates are promised.

1. Make working CLAW presets distributable as independent mods, as with human
   bodies. Determine whether stock OBody is sufficient; implement an optional
   companion when its family filtering/distribution APIs are insufficient.
2. Repair geometry gaps, including the known underside breast/body separation.
3. Add motion and collision physics for ears and tail. Correct the female breast
   shape and rig before adding its physics. Prefer existing XP32 bones.
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
- [Human/beast pairs](transformation.md): exact-pair resolver and exclusive-key
  policy planner implemented offline; native integration remains disabled.
- [Surface attachment repair](geometry-repair.md): opt-in female candidate built
  with topology/UV/skin data retained; visual/animation qualification pending.
- [Collider candidates](colliders.md): reproducible offline fitting and measured
  male/female candidates; installation and runtime physics qualification pending.
- [Breast shape and rig](breast-rig.md): verified existing bones, missing mesh
  weights, separate-part alternative and a measured local layer-follow experiment.
  Shape/rig repair remains pending.

These development results do not change or requalify the published0.6.2.0 package.
