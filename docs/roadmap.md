# CLAW — future plans

Owner-defined roadmap, updated 11 October 2026 after publication of the first
0.6.2.0 modder-resource release. These are planned features and fixes for later
updates; no release dates or version assignments have been set.

1. Align the colliders with the visible body surface.
2. Add physics and dedicated colliders for the ears and breasts.
3. Make colliders adapt to the body shape as morphs change.
4. Fix texture seams and visible gaps, including the known gap beneath the female breasts.
5. Add support for OBody or an equivalent body distribution system.
6. Add a first-person werewolf body for VR.
7. Add adult anatomy and physics for it in the separate Anatomy add-on.

The published resource package remains the starting point for this work. The
known female breast underside gap was accepted for that release; its repair is
future work.

## Development priorities and first work

Owner clarification on 11 October 2026: automatic variety across the werewolf
population (OBody or an equivalent) is the primary goal; first-person VR is second.
Prefer keeping XP32 and its existing bones. Replace the skeleton only if a
demonstrated requirement cannot be met otherwise.

- [Distribution reference core](distribution.md): implemented offline mapping,
  stable individual traits and transformation action plans; game controller pending.
- [Collider candidates](colliders.md): reproducible offline fitting and measured
  male/female candidates; installation and runtime physics qualification pending.
- [Breast shape and rig](breast-rig.md): verified existing bones, missing mesh
  weights, separate-part alternative and a measured local layer-follow experiment.
  Shape/rig repair remains pending.

These development results do not change or requalify the published0.6.2.0 package.
