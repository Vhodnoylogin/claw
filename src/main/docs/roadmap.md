# CLAW development roadmap

Owner priorities, 8 November 2026. This replaces the earlier 0.8.5 plan and
historical queue numbering. A source implementation is distinct from an installed
game result and from artistic acceptance.

## 0.9.0: core mechanics and individual coats

- Release classic UNP Renewal 4.6 weight/head/stature conversion alongside the
  existing HIMBO, CBBE, 3BA, BHUNP and both Vanilla matrices.
- Include all 34 qualified Elegant coats, deterministic hair-group/seed selection,
  source-less natural-pool fallback, explicit assignment/reset and persistence.
- Release the live-opacity material-ownership and human reference-scale fixes.
- Validate all installer combinations, exact native installation and all coat
  resources before publication. Keep Elegant credited and required on Nexus.

## 0.10.0: motion physics

Complete actual CBPC and FSMP provider binding, actor-scoped activation,
refresh/rebinding, cleanup and motion. Prefer provider-specific adapters and the
existing XP32 skeleton. Compilation, a void callback and animation-driven node
changes do not prove physics simulation. Establish actual provider state and
controlled motion in the game; do not mask uncertainty with qualification flags.

## After 0.10.0: VR body and contact colliders

Implement first-person VR body dispatch, visibility and synchronization. Then
complete morph-responsive contact colliders for both flat and VR gameplay:
coarse useful flat-game contacts and detailed hand-consistent VR contacts.
Static Morphbench placement and numerical fitting support development but do not
replace actual engine collision and headset tests.

## After the VR body and colliders: separate adult supplement

Plan a separate optional adult werewolf anatomy supplement, including penile
anatomy and its integration. It follows working VR body and contact mechanics;
it is not part of 0.9.0 or 0.10.0 and is not being implemented in this slice.

## Deferred

The independent Morphbench comparison-plugin UI/public update, artistic breast
and musculature refinement, attractive lean/bulky extremes, cosmetic
self-intersection tuning and new morph authoring remain deferred. Fix functional
defects such as missing textures or broken animation as they are found.

No separate neutral _0/_1 authoring task or synthetic age input is implied.
Every matrix retains actor weight as an explicit input. Human presets remain
OBody's responsibility; CLAW does not randomly distribute conversion matrices.

Testing is performed in the CLAW chat in its dedicated test environment. Retain
launch/tool defects locally for a later owner-approved handoff; send no messages
to other chats during this work. Keep FHD and the accepted paired-scene rules.
