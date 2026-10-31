# First-person VR body: composed resources and engine qualification

The owner resumed parallel VR body development on 28 October 2026 after the
27 October pause. New offline candidates remain separate from the prepared
flat-game OBody and human-to-wolf test; game/headset qualification is still pending.

## Current implementation

The selected anatomical split now separates actual head-only triangles from the
upper torso while retaining the original shader, textures, UVs, skin binds and
absolute TRI fields. The torso cut from `head` keeps its original head-texture
material; it is not merged into a differently textured body shape. The selected
seam duplicates boundary vertices with the same position, weights and morph
offsets on both sides. Separate composed exports apply this split to the corrected
body/physics carrier and distinct weight endpoints. The builder and exact
preservation checks are described in [the head policy](vr-head-policy.md).
These offline resources still require actual VR graph/camera qualification.

The separate [composed visibility builder](../python/vr/README.md) now prepares
first-person-only copies of all four anatomical weight endpoints. It hides
eleven explicitly selected head-side shapes per NIF; the retained head-textured
torso, breast support and hands stay visible. Exact byte comparison permits
only the eleven hidden-bit changes, with both shared TRIs unchanged. These
files do not establish engine dispatch or runtime flag persistence. Existing
Head-bone influence on retained torso/fur is reported, so VRIK head scaling and
camera/neck clearance still need their own solution and qualification.

### First-person Neck attachment

The [Neck attachment builder](../python/vr/README.md) now prepares a separate candidate
which moves positive Head/Jaw/ear-descendant skin influence in visible torso and
fur to the existing XP32 Neck. This intentionally removes Head-local motion while
retaining parent Neck/Spine, arm and P1 motion. The new bind derives from the
original Head rest product and actual stored skin frame. Only missing mesh nodes
from the existing XP32 ancestry are grafted; no skeleton asset is replaced.

The broad native export is scratch only. The selected NIF preserves original
block/string IDs, geometry/UV/normal/tangent/material bytes, old nodes/binds and
foreign weights. A separately measured half-precision merge error remains:
the conservative desired-reference enclosure is at most 0.000968 normalized or
0.03251 raw model units over the public morph/weight cube at 160 declared poses.
These are numerical design guards, not engine or appearance acceptance.

In nine Head-local examples, transported attachment error in the measured visible
collar/mixed layers drops below 9e-14. Other defects remain: ordinary/held-out
ChestBlend errors still reach 4.49344 female and 3.24174 male model units. The
new attachment therefore solves the declared Head-local coupling, not every fur
or animation defect. Perspective camera/neck coverage, runtime skeleton binding,
IK and interaction still need actual VR qualification.

`src/main/python/vr/compose_neck_seam.py` combines admitted Neck NIFs with the separately verified
male WaistNarrow TRI extension, without changing any NIF byte. It requires the
full original source family and successful native preservation receipts, and
reconstructs the one-record extension exactly. On all 135 visible collar pairs,
neutral/half/full WaistNarrow, weights 0/0.5/1 and 160 declared poses, the composed
candidate's maximum distance is about 0.00002133 model units in both weighting
conventions. The hidden head-side cut is intentionally separate during Head
motion. This is still an external resource candidate, with no engine dispatch
plugin or install layout.

The added Neck bone has a separate NiSkinData sphere for each affected shape.
Native export initially computes these for rest vertices only; all 28 new
spheres missed actual morph/weight samples, by up to 9.656 model units. A further
`src/main/python/vr/expand_neck_bounds.py` stage widens only those new radii. It preserves their
float32 centres and every other byte, and encloses the complete serialized TRI
cube plus independent weight interpolation with outward rounding. The stored
bone-bound frame is the serialized skin-to-bone transform applied to mesh vertices;
it was checked against the native rest spheres and is distinct from the B*C
posed-LBS convention. Shape-bound success alone did not establish this property.
Old bone spheres remain untouched and are not certified by this Neck-only stage.

```powershell
python src/main/python/vr/compose_neck_seam.py --neck-root '<verified-neck-candidate>' `
  --seam-manifest '<male-seam-candidate>/artifact-manifest.json' `
  --skeleton '<reviewed-XP32>/skeleton.nif' `
  --morphbench '<frozen-Morphbench>' --out '<new-external-composition>'
python src/main/python/vr/expand_neck_bounds.py --resources '<composition>/resources' `
  --composition-report '<composition>/composition-report.json' `
  --morphbench '<frozen-Morphbench>' --out-dir '<new-external-Neck-bounds>'
```

### XP32 aliases and the actual weighted arm

The inspected VRIK0.8.7 reconstruction searches a preferred human node name
before a werewolf fallback, then searches the next arm bone below that result.
In the pinned XP32 skeleton, `NPC L Clavicle [LClv]` is an empty leaf alias below
`NPC L Clavicle [RClv]`, which carries the beast arm. Selecting the leaf makes
the subsequent upper-arm search fail. The same empty preferred aliases exist
for the upper arm, forearm, hand and fifteen finger nodes. The installed
Werewolf Body for VR reference omits those nineteen aliases.

`src/main/python/vr/prepare_ik_aliases.py` implements a smaller optional compatibility candidate:
rename the nineteen **unweighted leaf aliases**, preserving every node and all
their parent relationships. Each name changes one ASCII character in the
existing header string, with the same length. Morphbench supplies the block
table and public PyNifly independently supplies node ids and names. Serialized
readback checks the complete graph, and exact byte comparison proves that all
block/footer bytes remain unchanged. Thus all original XP32 transforms,
collisions, constraints and skin data are retained. No additional bones or
reference skeleton are copied into CLAW.

The 26October candidate at
`D:/Skyrim VR Modding/Builds/claw-vr-ik-20261026/aliases-004-final-body/`
changes nineteen bytes, retains all345nodes and resolves the left arm and all
fifteen fingers to branches with observed body influences. The report compares
the original, candidate and reference graph separately. This reproduces the
lookup mechanism offline; it does not establish equivalence between a source
reconstruction and the installed VRIK binary. An animation or another mod that
looks up the renamed empty aliases can be affected. The skeleton is not installed
or accepted for distribution. Retaining unmodified XP32 remains preferable if a
qualified VRIK-side resolver can avoid these aliases instead.

```powershell
python src/main/python/vr/prepare_ik_aliases.py --skeleton '<XP32>/skeleton.nif' `
  --skeleton-sha256 '<reviewed SHA256>' `
  --body '<male>/body_0.nif' --body '<female>/body_0.nif' `
  --reference '<optional reference>/skeleton.nif' --out-dir '<new external folder>'
```

### One actor morph vector, both loaded graphs

The pinned RaceMenu source's
[`VisitBipedNodes`](https://github.com/expired6978/SKSE64Plugins/blob/9ebcb733e17be695f994cd2e9cc383043446bc02/skee64/NifUtils.cpp#L888)
visits both biped roots and their current/buffered slot objects.
[`BodyMorphInterface`](https://github.com/expired6978/SKSE64Plugins/blob/9ebcb733e17be695f994cd2e9cc383043446bc02/skee64/BodyMorphInterface.cpp)
then locates BODYTRI data and applies the same actor aggregate to eligible shapes.
The intended VR route therefore reuses the actor's linked coefficients and
matching BODYTRI shape names, without a second set of beast presets or a copied
coefficient cache. The actual installed VR provider and loaded resources still
need observation; this source evidence alone is not a VR runtime pass.

VRIK's head visibility adjustment can move or scale the Head bone. Separating
head triangles alone cannot prevent its remaining weighted influence on torso
or fur. The composed carrier's attachment weights, camera clearance, hands,
sex/weight dispatch and physical contacts must consequently be verified together.

## Retained initial resource prototype

Status, revised 26 October 2026: both-sex resources are built and verified offline. They
are **not an installable CLAW VR mod**. No game, headset, profile, installed mod,
microphone or third-party source/configuration was changed. The published 0.6.2.0
base remains the only body input for this first prototype; the independent geometry,
breast-rig and fur-motion experiments are not silently composed into it.

## Established entry point and integration limits

The author of [Werewolf Body for VR](https://www.nexusmods.com/skyrimspecialedition/mods/56394)
documents a complete beast mesh replacing
`meshes/actors/character/character assets/1stperson_werewolf_hands.nif`, with VRIK
and adjustments to the werewolf skeleton. The installed reference contains that
full-body NIF, its skeleton and optional movement animations. The author's page
also documents an XP32-compatible skeleton option, head visibility options, and
a warning that weight-enabled werewolf records require a patch. These statements
were verified against the author's page and the installed `meta.ini` description.

CLAW enables the weight slider in `ARMA 0CDD87:Skyrim.esm`; its existing
`FirstPersonModel` entries are the male/female character body filenames. Thus
renaming a CLAW body to the floating-hands filename is **not sufficient evidence
of a working engine integration**. The exact weight patch, resolved record/path
dispatch, first-person morph application and sex selection have not been established
on this setup. This prototype does not create a guessed armor slot, redirect the
ARMA, install a native swap, disable the weight slider or introduce beast presets.
The future body must consume the actor's existing linked beast morph vector.

The local VRIK reconstruction was inspected read-only to confirm that its body
solver distinguishes beast states and handles beast hands/head visibility. No
reconstructed code is copied or made a build dependency. Its existence does not
qualify the prototype against the installed VRIK binary.

## Executable offline record resolver

[`vr/engine_audit.py`](../python/vr/engine_audit.py) now resolves actual records from an
explicit input order without consulting a live profile. The original read-only
reader handles master-relative FormKeys, nested groups, compressed records and
extended subrecord lengths. It verifies the exact installed Skyrim VR master,
published CLAW ESP and corrected five-byte resource NIF/TRI hashes. An optional
reference plugin is compared against vanilla separately; it does not silently
become an effective CLAW override.

The verified vanilla chain is:

`RACE 0CDD84 WerewolfBeastRace` → `WNAM` → `ARMO 0CDD86 SkinNakedWerewolfBeast`
→ `MODL` → `ARMA 0CDD87 NakedTorsoWerewolfBeast`.

The race, skin armor and addon all carry biped mask **0x00000004**, Body slot **32**.
The installed Werewolf Body for VR Tamaska patch retains that same addon slot.
There is no record evidence for changing this to the Hands slot. Spriggit's
`BodyTemplate.FirstPersonFlags` is the BODT/BOD2 biped mask; its name does not prove
which first-person filename the native VR branch loads.

| ARMA field | Vanilla | Published CLAW | Installed WBfVR Tamaska reference |
|---|---|---|---|
| Biped mask | Body 32, BODT | Body 32, BODT | Body 32, BOD2 |
| Male/female weight flags | false / false | true / true | false / false |
| Male world model | MaleBodyWereWolf_1 | MaleBodyWereWolf_1 | MaleBodyWereWolf_1 |
| Female world model | MaleBodyWereWolf_1 | FemaleBodyWereWolf_1 | FemaleBodyWereWolf_1 |
| Male first-person record model | 1stPersonMaleBody_1 | same human filename | same human filename |
| Female first-person record model | 1stPersonFemaleBody_1 | same human filename | same human filename |

The recorded `DNAM` values are `000000000200001700000000` for vanilla/reference
and `000002020200001700000000` for CLAW. Weight is bit `0x02` of sex-specific
bytes 2/3 in this checked layout. The auditor reports male/female `MOD2/MOD3`
world paths separately from stored `MOD4/MOD5` first-person paths; it never labels
the latter as an observed engine-selected path.

Static `NPC_ 000007 Player` has race `013746`, no explicit WNAM skin and a male
base flag in the master. These are static defaults, not a transformed player
snapshot. Runtime race, sex, NPC skin overrides, templates and the actual loaded
graph cannot be inferred from that base record alone.

The native filename `Actors\Character\Character Assets\1stPerson_Werewolf_Hands.nif`
exists in the inspected SkyrimVR.exe (SHA256
`6961efb4f4775a307b0fc9a3d637542c1e090be207d3b09467eab216b7f87971`),
at file offset `0x15BB6A0`, RVA `0x15BCCA0`. A separate bounded file inspection
found the executable's ordinary code region packed, with its entry point in
`.bind`. Missing direct references in that file do **not** prove that this path
is unused. No launch, unpacking or process-memory inspection was performed.
CommonLib's `InitWornArmorAddon` and `InitWornArmor` call native engine functions;
the available source does not expose the VR beast model/weight selection body.
VRIK's inspected graph setup consumes already-loaded player roots.

Consequently the auditor completes with status
`refused-unresolved-native-first-person-dispatch` and generates **no plugin and
no install layout**. Changing MOD4/MOD5 to protected sex-specific paths is not
justified until the native choice between that record path and the built-in beast
hands path is established, including weight-bit behavior, slot eligibility and
`_0/_1` filename construction/interpolation. JSON cannot unlock generation by
asserting native qualification. World models, sex fields, weight flags and all
live files remain untouched.

```powershell
python src/main/python/vr/engine_audit.py --master '<SkyrimVR>/Data/Skyrim.esm' `
  --resources '<external>/verified-resources-002' `
  --reference-plugin '<WBfVR>/Tamaska Werewolf.esp' `
  --out-dir '<new-external>/engine-record-audit'
```

The optional repeated `--override` arguments declare later input files in order;
this is not an observed active load order. Missing masters, deleted/ignored winners
and inherited/additional race selection outside the narrow werewolf resolver are
refused. Exit **2** means a completed, evidence-backed native-dispatch refusal;
exit **1** means invalid or unsupported input. A JSON report and refusal marker
are written only into a new external directory.

The completed 26 October audit is
`D:/Skyrim VR Modding/Builds/claw-vr-body-20261026/engine-record-audit-003/engine-record-audit.json`.
It records hashes and exact record offsets for the three compared sources,
the declared override history, resource pins and the native-dispatch refusal.

## Actual resource change

[`vr/profile.json`](../python/vr/profile.json) pins SHA256 for the published male/female
`_0` NIFs, their base TRIs and the existing XP32 donor skeleton. Both weight
endpoints are identical in this release. The builder accepts that reviewed profile
only and rejects changed inputs before creating output.

The body and its named morphs retain their original shape names and vertex indices.
The resource sets `NiAVObject::Flag::kHidden` on five verified face-only shapes:
`eyes`, `fur_face`, `FurfaceBlend`, `mouth` and `ScalpFurBlend`.
The flag definition is verified in the local CommonLibSSE-NG
[`NiAVObject.h`](https://github.com/alandtse/CommonLibSSE-NG/blob/ng/include/RE/N/NiAVObject.h).

Morphbench's existing `NifPatch` supplies the NIF block table. PyNifly supplies an
independent shape id, type and flag value. The builder checks those against the
fixed flag location in each Skyrim SE `BSTriShape`, then changes only the hidden
bit in the original file bytes. It does not re-export geometry or recalculate
weights. A serialized byte audit proves the output equals the input with exactly
those five bits changed; native readback independently verifies shape names,
vertices, triangles, UVs, weights, node count, visibility flags and BODYTRI values.
Keeping all other bytes identical also preserves materials, skin binds, node
transforms, partitions, bounds and any embedded collision records exactly.

The original TRI is copied byte for byte. Its shape names, public morph count,
vertex-index range and finite deltas are checked against the resulting NIF.
All original BODYTRI strings continue to refer to the sex's existing CLAW path
under `actors\werewolfbeast\character assets\`. The external resource folder
does not provide an engine load tree and cannot be installed by copying it wholesale.

### Actual offline result

The 26 October build wrote a marked external resource directory:
`D:/Skyrim VR Modding/Builds/claw-vr-body-20261026/verified-resources-002/`.
Its `vr-body-report.json` records source, builder and dependency hashes, exact
edit offsets, resulting hashes, native readback, morph names and skeleton diagnostics.

| Resource | NIF nodes / shapes | Changed bytes | Public morphs | Result SHA256 |
|---|---:|---:|---:|---|
| Male | 86 / 16 | 5 | 24 | `2eaeb0d32a740594d7b9418e18461f9f2758a015a058c514b497381ac0ad67a9` |
| Female | 85 / 15 | 5 | 25 | `302b5281e09e9b03fbbfe12d3ef223fc2c00bfb8cc79b149d0a87f01dad8a2f3` |

Both outputs retain all 846 vertices weighted to `NPC L Hand [RHnd]` and all
1,571 vertices weighted to `NPC R Hand [RHnd]` in the body shape. The whole-file
byte comparison proves their geometry and skinning did not change. This is resource
preservation, not an observed match between controller position and physical hands.

### Mixed head/torso shape is retained

The original six-shape experiment incorrectly classified `head` as a dedicated
head mesh. It is rejected. In the published female NIF, `head` is block **155**;
its TRI carries **590** nonzero `CLAWTorsoBreastSize` deltas, supported over
z **87.334..99.998** and y **14.533..34.172**. It also has **2,174** positive
Spine2 weights and bilateral clavicle, upper-arm, Spine1 and Spine0 contributions.
The published male `head`, block **163**, has the same torso skinning support
even though it has no BreastSize morph. Hiding either whole shape removes upper
torso anatomy; hiding the female shape also removes the visible breast lobe.

The revised profile retains both complete `head` blocks and their original
visible flags. All breast-morph-supporting shapes must remain visible according
to the file's shape and ancestor hidden flags; this is checked again after native
readback. The female head's 590 deltas and its byte-identical TRI remain usable.
All five female BreastSize-supporting shapes (`body`, `fur_belly`, `fur_chest`,
`fur_shoulders` and `head`) retain visible shape/ancestor hidden flags.
File attributes do not prove that VRIK, NiOverride or the engine will render them
correctly at runtime.

Whole-shape hiding is refused for any candidate containing a
`CLAWTorsoBreastSize` entry, any other `CLAWTorso*` morph entry, or a vertex at
z<=103 with positive non-head-descendant skin weight. The last condition detects
torso anatomy even without BreastSize. The bound is an explicit pinned torso
guard, not a camera volume. Actual mouth vertices below this z bound remain
eligible because they are Head/Jaw-owned. The five eligible shapes have no torso
morph entries and no such low non-head-owned vertices.

| Shape | Male block | Female block | Whole-shape action |
|---|---:|---:|---|
| eyes | 92 | 92 | Set hidden bit |
| fur_face | 131 | 123 | Set hidden bit |
| FurfaceBlend | 155 | 147 | Set hidden bit |
| mouth | 170 | 162 | Set hidden bit |
| ScalpFurBlend | 177 | 169 | Set hidden bit |
| head | 163 | 155 | Retain entire block and visible flag |

Earlier `resources/` and `verified-resources/` outputs remain as historical
diagnostics, marked rejected by the adjacent external
`historical-mixed-head-rejected.json`. Their previous six-byte result is not the
current candidate. No triangle removal, reindexing or degenerate geometry was used.

### Camera visibility remains a gate

The five face-only shapes read back as hidden. The complete mixed `head` shape
remains visible, including its face triangles. Mixed body/fur shapes
also contain positive head-descendant weights and remain visible:

| Shape | Distinct vertices with positive head-descendant weights, either sex |
|---|---:|
| head | 8,853 |
| body | 47 |
| ChestBlend | 1,116 |
| fur_back | 5,721 |
| fur_belly | 2,008 |
| fur_chest | 2,352 |
| fur_shoulders | 1,062 |

These counts are a conservative attachment audit, not intersections with a
camera volume. Hiding an entire mixed fur layer would remove useful body coverage;
deleting vertices would break the existing TRI indexing. Neither is done here.
No tracked camera pose, headset near plane or runtime animation was observed, so
camera clearance, neck appearance and visibility during morph updates remain
unqualified. Selective head masking is unimplemented; the current candidate must
not be described as headless or camera-safe. VRIK's existing head-bone visibility
behavior, or a future measured selective policy, must be qualified against this
mixed anatomy. No whole head bone/node is hidden by this builder. Runtime
reattachment may also replace resource flags and must be tested.
Even a head-bone-only visibility change cannot be assumed to preserve every
breast-support vertex: some mixed-shape breast morph vertices carry positive
Head weights. File visibility preservation is the only claim of this prototype;
head-only pose behavior needs a separate measured skinning audit.

## XP32 and interaction ownership

The prototype reads the pinned XP32 skeleton but produces **no skeleton output**.
All weighted bones used by the two published bodies exist in it. The optional
read-only comparison with the installed Werewolf Body for VR skeleton found:

- Pinned XP32: 345 nodes; installed reference: 327 nodes.
- The reference adds `SHIELD` and lacks 19 left-arm human aliases, including
  `NPC L Hand [LHnd]`. The actual beast hand names used by CLAW are retained.
- Two common tail nodes have different local transforms. No other common node's
  local transform or parent differs above the diagnostic tolerance of `1e-6`.
- No CLAW body-weighted bone is missing from the reference skeleton.

This comparison does not inspect or qualify every Havok body, constraint, animation
binding, alias consumer or runtime graph. It demonstrates that the two skeletons
are different, not that one can replace the other safely. A future adapter should
preserve XP32 and make only independently justified changes. The third-party
reference skeleton and animations are neither copied nor patched.

[HIGGS's hand implementation](https://github.com/Vhodnoylogin/higgs/blob/4b6b5e41774e0cb0fac6cbab117158d04b483dfa/src/hand.cpp)
owns beast-specific hand collision dimensions/offsets and their physical transform;
[PLANCK](https://github.com/Vhodnoylogin/activeragdoll/blob/cb78ef4399549a84c531c42704585aaab0062845/src/main.cpp)
owns NPC ragdoll/contact/hit processing and distinguishes the beast player controller
shape. A visible beast mesh does not retarget those physical hands or supply
qualified dense capsules. This builder changes no collision configuration, public
ABI or controller transform. Existing collider/physics candidates remain separate.

## Reproduce and verify

Configure the installed PyNifly directory and Morphbench path using the ignored
`build.local.json`, as for other CLAW tools. PyNifly's Python module/native DLL,
its TRI reader and Morphbench's header reader are hashed in the report.
Explicit `--pynifly` and `--morphbench` arguments can override the local paths.

```powershell
python src/main/python/vr/build_body.py --out-dir '<new-external-directory>/claw-vr-body'
python -m unittest discover -s src/test/python/vr -v
$env:CLAW_VR_NATIVE_TESTS='1'
python -m unittest discover -s src/test/python/vr -v
```

Optional `--reference-vr-skeleton '<installed-reference>/skeleton.nif'` adds only
a read-only structural diagnostic. Explicit `--body-root`, `--skeleton` and
`--profile` arguments locate copies of the exact pinned inputs; they do not admit
unreviewed body compositions.

The output must be new and outside Git, source directories and known live game/mod
manager trees. It contains `NOT_INSTALLABLE.txt`, each sex's resource NIF/TRI pair,
and the report. Existing destinations are rejected. Preflight handles both sexes
before output creation; a failure after creation leaves a report marked failed.
There is no package archive, ESP, SKSE plugin, skeleton override or live install step.

Twenty-eight checks, including three native published-resource regressions, cover
exact bit edits, independent byte corruption, truncation,
variable extra-data counts, duplicate/overlapping/missing shapes, flag disagreement,
unsupported profiles and inputs, output admission, visible hands, BODYTRI and invalid
TRI indices/deltas. The regressions reject hiding mixed torso/breast shapes,
verify actual published female/male head block identities and weights, preserve
the complete mixed-head blocks byte for byte, and check that breast morph support
remains visible in native file attributes. Set `CLAW_VR_NATIVE_TESTS=1` to include
these dependency-requiring native checks; otherwise the three native checks are
explicitly skipped. Both actual NIF/TRI pairs also passed the native offline build.

The record auditor adds 17 checks, bringing the complete suite to **45 passing
checks** when all installed inputs/native dependencies are explicitly supplied.
Its four installed-record checks verify the exact vanilla record offsets and
chain, actual CLAW sex/weight/path fields, reference slot compatibility and the
generation refusal. Its synthetic checks exercise compressed/extended records,
master remapping, winner/deletion semantics, malformed data and slot/race limits.
For those installed-record checks, additionally set `CLAW_VR_RECORD_MASTER` to
the exact Skyrim.esm, `CLAW_VR_RESOURCE_ROOT` to the corrected resource folder and
optionally `CLAW_VR_REFERENCE_PLUGIN` to the installed reference ESP. These four
checks are explicitly skipped without the corresponding inputs; the native body
checks still require `CLAW_VR_NATIVE_TESTS=1`.

The next useful implementation gate is a read-only trace of actual beast engine
record/path resolution and the loaded first-person graph on a separately authorized
VR session. Then qualify the smallest XP32 adaptation, sex-specific selection and
existing linked morph application before installing a body candidate. Head/camera
clearance, transformation return, save/load, both hands, HIGGS contacts and PLANCK
hits require actual headset acceptance; none is inferred from this offline build.
