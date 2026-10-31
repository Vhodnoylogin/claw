# Human head traits and independent wolf controls

Tags: CLAW, head, face, morphs, transformation

## Implemented candidate, 1 November 2026

The development DLL now captures five vanilla FaceGen values and human stature,
and the five default resource-family matrices explicitly link them. These are
read-only engine record inputs. They are not invented RaceMenu body morphs,
custom face slider names, sculpt measurements or a claim to reproduce baked NPC
FaceGen geometry. The earlier research and frozen geometry audit below remain
the limits of the available resource evidence; installed-game acceptance is
still required for the new candidate.

| Matrix source | Read while actually human | Authored default use |
|---|---|---|
| `$human.face.noseLength` | Root face NPC `FaceData::morphs[kNose_LongShort]` | Positive side adds muzzle length at gain 0.35 |
| `$human.face.jawForward` | `kJaw_ForwardBack` | Negative side adds muzzle length at gain 0.2 |
| `$human.face.chinForward` | `kChin_UnderbiteOverbite` | Negative side adds muzzle length at gain 0.1 |
| `$human.face.jawWidth` | `kJaw_NarrowWide` | Positive side adds muzzle width at gain 0.3 |
| `$human.face.chinWidth` | `kChin_NarrowWide` | Positive side adds muzzle width at gain 0.15 |
| `$human.height` | NPC `height` (NAM6) multiplied once by the current human race's sex-specific height | Above ratio 1: head/ears gain 1.5, tail length gain 2, both claw lengths gain 1.25 |

The raw signed face values retain their engine representation. The default gains
and sign interpretation are authored projections, pending race/resource visual
qualification. They are not measured anatomical dimensions. Height omits actor
reference scale and skeleton/node overrides. The height-to-ear/tail/claw relation
is an explicit artistic stature analogy, not a claim that humans have a tail or
that stature measures nails. Height 1 gives zero on these rows; height 1.1 gives
head/ear 0.15, tail 0.2 and claw 0.125. Shorter values cannot shrink these existing
nonnegative targets below their donor neutral. The [v4 projection](anatomy-v4.md)
also uses real face breadth for modest ear size/tilt, real body mass for tail
radial bulk, and forearm/limb strength for modest claws. These are explicitly
authored analogies, not measured human ear/nail anatomy. Tail lift and paw
size retain zero unless an owner authors rules for actual supported inputs.
No categorical HeadPart index is converted into a continuous trait.

`HumanTraits` preserves source race, base NPC, root face NPC, sex, and a map of
available values separately from the matrix's numeric input snapshot. A present
zero is supported neutral data. Null FaceData, the engine default sentinel,
nonfinite values or missing provenance remain unavailable. Missing face inputs
use arithmetic neutral 0; missing height uses ratio 1. A warning lists unavailable
declared channels when that list changes. These fallbacks do not mark a channel
available and do not stop the existing body/weight conversion.

Source capture requires a current non-werewolf race carrying `ActorTypeNPC`;
other creature forms retain the preceding human snapshot and cannot overwrite
it with creature records. Within this eligible form, human refresh atomically
replaces the snapshot, including removals and changed
race/face/sex. Wolf refresh reads the retained snapshot and never reads the wolf
face as human. A new born wolf has no human snapshot; OBody body bootstrap cannot
create one. A changed NPC identity invalidates the retained snapshot. Existing sex
binding still refuses a different sex until explicit rebind. Co-save v7 appends
the snapshot, remaps its FormIDs, and invalidates it if provenance cannot resolve.
The next human refresh recaptures it. Existing v1..v6 ordinary/weight matrices
remain authoritative and receive no new rows until explicit family rebind. A
pre-v7 `$human.` token is retained suppressed until rebind rather than silently
changing from an old SKEE name to an engine source.

The shared native/WASM source-kind validator reserves the case-insensitive
`$human.` namespace and accepts only the six exact spellings above. Targets cannot
use it. Ordinary SKEE names remain data-driven. There is no unsafe private
FaceMorph ABI call and no export-file polling. The game adapter checks the slot
indices against the pinned CommonLib enum at compile time. Focused offline tests
cover availability, real neutral values, explicit routing, lifecycle replacement,
default sentinels, co-save roundtrip and old namespace migration.

The candidate also scales every CBBE/3BA breast-target calibrated gain by 0.55,
preserving relative signs and cancellation, for the larger expressive-v3 breast
field. This prevents the retained high fixture saturating before the new field
can express differences; it is an authored geometry-dependent change, not a new
measured calibration. A zero breast coefficient retains the nonzero donor mesh.

## Earlier research and frozen audit

Research and implementation proposal, 30 October 2026. Historical baseline: CLAW
`689e5bdbbdf74ab524e16153a8af74becf581b25`, development branch
`feature/shape-physics-fur`. No runtime adapter, mapping gains or new targets are
enabled by this document. The running game and frozen release are unchanged.

## Two configuration modes

**Morph Link Profile** describes relative human-to-wolf conversion: versioned
source adapters, many-to-many rules, gains and qualified output bounds. An actor's
actual supported human state supplies values; the profile contains no fixed wolf
assignment. The current body implementation is `MorphLink::capture/compose` in
[`MorphLink.h`](../cpp/include/claw/MorphLink.h), family data in
[`MorphLinks.xml`](../resources/profiles/MorphLinks.xml), and
`refreshActor` in [`Plugin.cpp`](../cpp/src/Plugin.cpp).

**Standalone Werewolf Preset** assigns fixed named wolf morph coefficients and
ignores human morphs. It is a separate explicit mode, including for a wolf with no
human history. The existing independent `Preset` format has low/high coefficient
pairs and interpolates them with NPC weight; it is only fixed when each pair is
equal. A new fixed-vector format or validated equal endpoints can implement this
mode. Fixed coefficients still coexist with the body's ordinary `_0`/`_1` mesh
interpolation. Selecting either mode must clear the previous mode's owned vector;
do not silently add a standalone preset to linked output or silently fall back.

## Head and face: actual source channels

The following are distinct data channels, not interchangeable slider names:

| Channel | Verified source and capability | Limit |
|---|---|---|
| Body morphs | `IBodyMorphInterface::GetBodyMorphs` and visitors in SKEE `IPluginInterface.h` | Actor/key body coefficients; the current CLAW path. No generic face/sculpt reader here. |
| Vanilla FaceGen | CommonLib `TESNPC::FaceData::morphs`, `parts`, `Morphs` and `Parts` | Named enum indices include nose length, jaw width/position, chin, eyes and brows. `parts` are discrete selections. Resource/race/sex geometry determines meaning and sign; handle missing/default data explicitly. |
| RaceMenu custom face values | SKEE registers `"FaceMorph"` in `main.cpp`; `FaceMorphInterface::GetMorphValueByName(TESNPC*, SKEEFixedString)` is virtual, interface version 1 | This interface exists in the inspected implementation header, but has no corresponding public class declaration in `IPluginInterface.h`. A version-pinned optional ABI adapter needs qualification; it is not already supported by CLAW. Missing entries return zero, so this getter alone cannot distinguish unsupported from neutral. |
| Head/node overrides | `INiTransformInterface::VisitNodes/GetNodeTransformScale/Position/Rotation` | Keyed overrides, not a complete anatomical head measurement or proof of the final evaluated transform. Avoid applying inherited actor/head scale twice. |
| Preset export and sculpt | `IPresetInterface::SavePreset`; `PresetInterface::SaveJsonPreset` serializes default arrays, named custom values, HeadParts and per-host vertex deltas | An export is a snapshot of several channels, not a preset-name mapping. Sculpt is topology/host-specific and is not a semantic scalar. Do not copy human vertex indices to wolf meshes. |

The custom getter must not be described as nonexistent merely because the public
exchange header omits its declaration. Conversely, registration does not prove
compatibility with the installed official DLL, NPC coverage, current rendered
FaceGen or SE/AE/VR behavior. The inspected `SavePreset` implementation returns
false even after requesting a save; qualification must inspect an actual complete
export rather than infer success from that boolean. Export remains a research
route, not a per-frame capture design.

## Candidate head/face conversions

The public catalog in [`Preset.cpp`](../cpp/src/Preset.cpp) contains the
five head targets below. [`full-body.json`](../resources/recipes/full-body.json) defines
their actual geometry. Table entries are proposed measured relations, not enabled
source identifiers or calibrated gains. No verified installed custom ear catalog
was established in this research.

| Human information, after resource qualification | Existing wolf targets | Relation and qualification |
|---|---|---|
| Nose long/short plus jaw forward/back and chin underbite/overbite | `CLAWHeadMuzzleLong`; possibly `CLAWHeadMuzzleWide` | Logical many-to-many facial projection. The existing Long field scales both skull and jaw along its forward axis; it cannot isolate a nose or jaw. |
| Jaw narrow/wide plus chin narrow/wide, measured lower-face breadth | `CLAWHeadMuzzleWide`; secondary `CLAWHeadSize` only if measured | Logical combined breadth. Wide also changes vertical scale. Avoid counting the same region twice. |
| Measured skull dimensions or qualified head-scale override | `CLAWHeadSize`, with bounded muzzle corrections if needed | Logical overall-head relation; current HeadSize and MuzzleLong strongly overlap. A node override and geometry-derived size must not duplicate one effect. |
| Qualified continuous ear length/area and outward angle, from custom face geometry or measured sculpt | `CLAWHeadEarSize`, `CLAWHeadEarTilt` | Direct dimensional analogy. EarSize extends both ears from their bases; Tilt rotates both outward. No independent left/right or width target currently exists. A categorical ear HeadPart needs measured geometry, not its selection index as a percentage. |
| Eye spacing/height, brows, cheeks, lips or independent jaw depth | No matching independent public target | Retain as unsupported until actual wolf geometry justifies another target. HeadSize is not a universal substitute. |

Current targets are nonnegative. Negative source deviations can cancel growth but
cannot create shorter/narrower/inward shapes below neutral. Measure the endpoint
failure first; preserve current names and add opposed fields only where needed.
Head/ear targets currently fail `linkedBodyMorph`, even though the public resource
catalog recognizes them. Enabling them needs a qualified source adapter and an
explicit policy change, not XML rows alone.

## Tail, claws and paws

`CLAWTailLength`, `CLAWTailLift`, `CLAWTailFluff`, `CLAWArmClawLong` and
`CLAWLegClawLong` are public targets. TailLength scales along two axes; TailLift is
a root rotation; Fluff is a radial field, not a verified independent fur-length or
tail-thickness control. ClawLong extends claw islands from their bases.

Ordinary human head/body sources establish no direct tail length, tail posture,
tail fur or claw-length counterpart. Keep these neutral in automatic conversion
until a separately declared relation has evidence. Relative human limb length to
tail length, or soft bulk to tail thickness, would be artistic analogies requiring
measured sources and target geometry, not direct anatomical matches. Nail length
could justify claw length only if a real continuous applied nail source is found;
a manicure mesh selection or hand scale is insufficient. No belly-to-ear rule is
justified. Existing `CLAWArmPawSize`/`CLAWLegPawSize` could use qualified hand/foot
proportions; that requires its own body/node source adapter.

Standalone presets can explicitly set these public traits without inventing
human counterparts. Tail/ear rest morphs remain separate from physics ownership,
stiffness, animation and morph-responsive collision fitting.

## Frozen trait-field geometry audit

The 30 October offline audit measured thirteen actual fields in both sexes:
the five `CLAWHead*` controls above, three `CLAWTail*` controls,
`CLAWArmClawLong`, `CLAWLegClawLong`, `CLAWArmPawSize`, `CLAWLegPawSize` and
`CLAWLegDigitigrade`. All 31 stored shapes received support counts/bounds,
maximum/P95 unit displacement, skin/fur summaries and cross-field overlap.
The staged four NIFs and two TRIs matched the SHA-256/size records in
`target/references/releases/se-core-20261030/claw-build.json`; each sex's `_0`/`_1` files
were also verified byte-identical. Exact resource SHA-256 values are:

| Frozen resource | SHA-256 |
|---|---|
| Male `_0` and `_1` NIF | `cff0f62e9c089cf8618e39cb4012be5d9041535d7a101c4242bfb87f8b25b0ef` |
| Female `_0` and `_1` NIF | `033c9828661e371d4d9eadbf85202235391ccd31408777e149631d57baafa3ff` |
| Male TRI | `1e2dd49812870620072d3a426124a957486f292504d5173978fd3b5edb8db285` |
| Female TRI | `3fd1ce64adafa5d77a510d1829077b9b3aa06a23eb741377a4803432416fb28b` |

Primary PyNifly NIF/TRIP reads were cross-checked by the existing complete
`morph_quality.decode_fields` decoder. Every primary-retained record agreed;
203 tiny serialized pairs omitted by the primary reader across the female TRI
were retained. That reader omits triples whose components are all at most
0.0001 in magnitude. Support here means exact nonzero decoded displacement.

The **breast-expansion-support** witness consists of the 6,690 vertices with
nonzero actual `CLAWTorsoBreastSize` displacement, spanning `head`, `body` and
four fur/blend surfaces. It is not a complete anatomical breast segmentation;
neither the shape name `head` nor Head-bone weights define anatomical head.
Overlap alone cannot establish which field extends outside its intended region:
the breast field may also include neck/head transition vertices. Do not zero
the entire witness as an automatic repair. First curate anatomical/protected
regions and test continuity of both fields separately and together.

| Head field on this witness | Vertices moved | Maximum unit displacement |
|---|---:|---:|
| EarSize / EarTilt | 0 | 0 |
| MuzzleLong | 1,594 | 1.734167 |
| MuzzleWide | 1,596 | 2.255332 |
| HeadSize | 4 | 0.438434 |

Both muzzle fields move witness skin and multiple fur/blend layers; HeadSize
moves four `fur_belly` witness vertices. Ear fields avoiding this witness do not
certify the remaining breast or its attachments. Future head links and plugin
controls therefore require an explicit anatomical region, protected torso/witness
vertices and frozen fur-root correspondences before unrestricted exposure.
Require zero unintended movement on those protected regions and check combined
head/muzzle fields. Paw/claw overlap also requires combined-field checks; tail
and claw mapping still needs justified human inputs. Full human face/head capture
is outside the current body fixtures.

All thirteen traits were zero in the six historical linked wolf observations:
this is a latent future constraint, not an established current runtime failure.
Measurements are unskinned NIF-root model units at coefficient 1, with shape
global transforms applied and material alpha ignored. No posed, rendered,
attachment, animation or contact result is claimed.

External evidence, relative to the workspace root:
`Builds/claw-morphbench-addon-20261030/trait-field-audit/report.md`,
`trait-field-audit.json`, `input-hashes.json` and `validation.json` in that folder.
The compact audit JSON SHA-256 is
`07f360526bdeb4e0bcbb8178800cfda1098d09676f6ac55eca0f63482913f932`.
Input hashes and shape/surface/support totals were rechecked. Generated geometry
and audit data remain outside Git.

## Capture, persistence and implementation order

1. Inventory one pinned human head resource per race/sex: base mesh/TRIs, HeadParts,
   custom slider definitions and supported providers. Measure negative/zero/positive
   fields in neutral expression. Treat baked NPC FaceGen and sculpt as potential
   extra geometry, not proof that the scalar arrays describe the visible head.
2. Implement bounded read-only head capture while the actor is actually human,
   before transformation. Store source race/sex, resolved face-resource identity,
   provider/runtime version, channel availability and values separately from the
   existing body snapshot. Do not reread the wolf face as human. The current body
   reread in both forms is intentional actor-level SKEE behavior and need not change.
3. Persist the human snapshot and mapping/target revisions through co-save, with
   explicit refresh/invalidation after supported human appearance changes. Missing,
   unsupported, stale and legitimate zero are distinct. Save/load, form-ID remapping,
   race/sex changes and actor destruction need coordinated lifecycle checks.
4. Fit family-level many-to-many rules from measured human dimensions to measured
   wolf dimensions. Extend the linked-target policy, typed source namespaces,
   validation and persistence together; retain the existing 128-edge budget or
   review an explicit revision. Keep skin, teeth, jaw and fur attached at both
   weights, combined morphs and poses; verify serialized readback and visible seams.
5. A born-wolf actor has no invented human head snapshot. Linked head output stays
   neutral/unavailable with a diagnostic until a qualified explicit source exists.
   An explicitly selected Standalone Werewolf Preset supplies fixed wolf values.
   The existing body-source bootstrap is not evidence of human facial history.
   Returning human clears only CLAW's owned wolf key; never import a human preset
   or mutate face/sculpt state merely to calculate the wolf.

## Pinned source evidence

Local source inspection, no game/API calls: SKEE fork commit
`2d8df66dcffb702fa67a702c7b26ae9f8854e918`; the custom FaceMorph virtual getter was
also confirmed in its upstream base `eb39bdd185f0ee5b3154b2ae1910d2465b2627ed`.

- [SKEE public exchange interfaces](https://github.com/expired6978/SKSE64Plugins/blob/eb39bdd185f0ee5b3154b2ae1910d2465b2627ed/skee64/IPluginInterface.h): `IBodyMorphInterface`, `INiTransformInterface`, `IPresetInterface`.
- [SKEE face implementation contract](https://github.com/expired6978/SKSE64Plugins/blob/eb39bdd185f0ee5b3154b2ae1910d2465b2627ed/skee64/FaceMorphInterface.h): `FaceMorphInterface`, `ValueMap`, `SculptStorage`, `SliderInternal`.
- [Inspected registration](https://github.com/Vhodnoylogin/SKSE64Plugins/blob/2d8df66dcffb702fa67a702c7b26ae9f8854e918/skee64/main.cpp): `g_interfaceMap.AddInterface("FaceMorph", ...)`.
- [Inspected extraction/export](https://github.com/Vhodnoylogin/SKSE64Plugins/blob/2d8df66dcffb702fa67a702c7b26ae9f8854e918/skee64/PresetInterface.cpp): `SaveJsonPreset`, `SavePreset`; [value lookup](https://github.com/Vhodnoylogin/SKSE64Plugins/blob/2d8df66dcffb702fa67a702c7b26ae9f8854e918/skee64/FaceMorphInterface.cpp): `ValueMap::GetMorphValueByName`, `ValueSet::GetValue`.
- [CommonLib NPC layout](https://github.com/Vhodnoylogin/CommonLibSSE-NG/blob/a898f469851c464d05137bb74b069dd234897643/include/RE/T/TESNPC.h): `TESNPC::FaceData`, `Morphs`, `Parts`; source-layout evidence, not live behavioral qualification.
