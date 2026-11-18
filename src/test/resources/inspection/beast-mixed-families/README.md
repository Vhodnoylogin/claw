# Beast-race and mixed-body acceptance scenario

This directory contains nonshipping authored Spriggit source and a scenario
specification. It is not a ready Polygon order, installed fixture, launch
authorization or game result. Resolve the current testing
workflow, installed inputs and shared custody before preparing an actual order.

Use the existing inspection kit's fixed QASmoke anchor, AI/collision state
verification, explicit locomotion hold and owned-reference/save lifecycle.
Do not replay toggles blindly or assume old runtime FormIDs. Keep test controls,
generated plugins, archives, actual body outputs and raw observations outside Git.

## Authored source fixture and current readiness

[`plugin-source/`](plugin-source/) defines six new NPC bases and six persistent,
initially disabled references in QASmoke. No original NPC is overridden, templated
or copied. The plugin contains no scripts, quests, spells, equipment, acquisition
logic or automatic enable commands. The source manifest is
[`fixture.json`](fixture.json); runtime load-order prefixes must be resolved from
the actual plugin, never inferred from the local IDs below.

| NPC local ID | Reference local ID | Human source | Skin |
| --- | --- | --- | --- |
| 000800 | 000900 | Khajiit male | Inherited from actual source race |
| 000801 | 000901 | Khajiit female | Inherited from actual source race |
| 000802 | 000902 | Argonian male | Inherited from actual source race |
| 000803 | 000903 | Argonian female | Inherited from actual source race |
| 000804 | 000904 | Nord female CBBE control | Inherited from actual source race |
| 000805 | 000905 | Nord female BHUNP control | Own skin ARMO 000820 |

All six bases have fixed weight50, height1 and authored scalar FaceMorph controls.
Those controls are deliberately synthetic, including supported zeros; they are
not measured faces from the master study. No categorical head parts, hair/feather
colour, face texture, FaceGen mesh or tint assets are supplied. Prepare appropriate
authored race/sex head parts and generate these bases' FaceGen/tints before any
visual/head acceptance. Static NAM9 fields do not establish engine FaceData
availability, root-face-NPC identity, likeness, coat colour or successful loading.

The custom female Nord skin declares three female-only, weight-enabled ARMA:
000810 body slot32, 000811 hands slot33 and 000812 feet slot37. Their independent
third-person paths begin `actors/test_CLAW/beast-mixed/bhunp/`. It deliberately
does not attach the ordinary CBBE hand or foot addons to a BHUNP torso. **No NIF,
TRI, texture or first-person model is included.** Prepare a complete compatible
BHUNP skin at these paths with both `_0.nif` and `_1.nif` endpoints for every part,
actual Build Morphs TRI/BODYTRI linkage, matching seams/partitions and compatible
UNP shader materials/textures. The source has no texture-set overrides: the
generated NIFs must reference the intended separately accounted materials.
Actual outputs may require additional biped partitions; inspect and reconcile
those with these declared slots before staging. This source shell is not a
claim of finished anatomy, UV compatibility, matching neck/limbs or skin rendering.

The same skin ARMO has a fourth armature link to the external
`0CDD87:Skyrim.esm` `NakedTorsoWerewolfBeast` addon. Only the three human addons
are authored here; no wolf ARMA override is copied into this fixture and the
sole plugin master remains `Skyrim.esm`. An explicit NPC skin can remain preferred
by parameterless `Actor::GetSkin()` after a race change. Its armature must therefore
include a compatible wolf body; this fixture assumes no automatic runtime skin
replacement. The installed CLAW override of that same master FormKey must win
and provide its actual body-slot32 WerewolfBeastRace `0CDD84` models/resources.
Read back the actual winning addon and the transformed actor's skin, race-filtered
armature and loaded model before claiming wolf rendering or family retention.

Ordinary CBBE body/hands/feet and the beast actors' race-specific hands, feet,
textures and separate tails remain separately installed dependencies. Verify
their actual winning skin records, NIF/TRI paths and material compatibility;
merely inheriting the race skin cannot establish those facts. No third-party
assets are copied into this fixture.

[`BodyFamilyBindings.xml`](BodyFamilyBindings.xml) explicitly maps ordinary female
body endpoints to `CLAW.CBBE.2.0.3.Geometry1` and unique test body endpoints to
`CLAW.BHUNP.3.34.AdvancedV4`. It is source input only, not automatically installed.
Prepare an accounted compatibility installation containing both actual female
profiles in `MorphLinks.xml`; the ordinary single-select FOMOD does not provide
both. This fixture supplies no morph provider, BodySlide preset distribution or
outfits. The eventual scenario must establish a shared-name nonzero control and
a supported-zero control and read all actual keyed contributions independently.

The CELL metadata mirrors the existing inspection lighting source's QASmoke
values, with an ordinary English cell name. It is not a byte-identical winning
CELL or active-profile compatibility claim. Compare the override before staging.
Storage positions retain the inspection probe's disabled-storage convention;
they are not verified floor positions. Use the fixed inspection anchor and move
only still-disabled owned references to qualified standing positions before
enabling. Installing the source's compiled plugin enables none of these actors.

## Offline compilation and independent readback

Run [`build_fixture.py`](build_fixture.py) with explicit `--spriggit`,
`--spriggit-assembly`, `--translation-cache` and a fresh external `--out` beneath
the workspace's `Builds/`. It requires the already installed, hash-pinned
Spriggit0.41.0 and existing Skyrim YAML translator cache; it acquires no tools or
providers. It compiles source, independently checks binary identities, sex/race,
weights, scalar face fields, isolated skin/slots/paths, and disabled persistent
reference ownership, including exactly three authored human armature links plus
the required external wolf addon, then performs official serialization/rebuild and requires
byte-identical ESP output. Commands, source/tool pins and missing preparation
are retained in the external build receipt. It never installs or starts a game.

The initial18November2026 compilation (3964-byte ESP, SHA-256
`b43928cb1d90f16ddc9019e3c8e033bd9da93172c255df5035ab8030336b8172`)
is superseded: its custom skin omitted the compatible wolf armature link.
Retain that evidence as an incomplete earlier source build.
Corrected source compilation/readback passed on 18 November 2026 (3974-byte ESP,
SHA-256 `ae2d3193efaad2f56e3ef3afd263c82c12370b2b46797f54fab748e8e11138e2`),
including the exact four-link skin and byte-identical official roundtrip.
This is structural source evidence only. The receipt always states
`readyToStage=false`, `installed=false`, `gameValidated=false`, and requires the
external preparation above. No SE/AE/VR loading, simultaneous actual family
selection, complete skin, visual result or transformation lifecycle is qualified.

Undo before a run by removing this uninstalled source build. After any separately
authorized run, disable the exact owned references under current custody and
restore the owned profile/save using the testing workflow. Never reuse saved
changeforms merely because the plugin/local IDs match. Unrelated source NPCs and
assets require no restoration because this fixture does not override them.

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
