# First-person VR body: bounded offline resource prototype

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

## Actual resource change

[`vr/profile.json`](../vr/profile.json) pins SHA256 for the published male/female
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
python vr/build_body.py --out-dir '<new-external-directory>/claw-vr-body'
python -m unittest discover -s vr/tests -v
$env:CLAW_VR_NATIVE_TESTS='1'
python -m unittest discover -s vr/tests -v
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

The next useful implementation gate is a read-only trace of actual beast engine
record/path resolution and the loaded first-person graph on a separately authorized
VR session. Then qualify the smallest XP32 adaptation, sex-specific selection and
existing linked morph application before installing a body candidate. Head/camera
clearance, transformation return, save/load, both hands, HIGGS contacts and PLANCK
hits require actual headset acceptance; none is inferred from this offline build.
