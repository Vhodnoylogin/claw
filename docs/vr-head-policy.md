# Head visibility and torso skinning

This page records the original read-only diagnostic and the separate opt-in
anatomical resource builders. None implements a runtime head-hiding policy.

## Selected composed resource family

The selected 26 October offline family is now one actual composition, rather than
an 85-node split and a separate 91-node breast experiment. The female carrier is
the canonical collar repair, recomputed existing-XP32 P1 rig, belly follower,
bounded shoulder continuation and localized chest-root palette correction. Its
source is `d04aced0...f1c33`. The male begins at canonical `cff0f62e...b0ef`.
Both receive distinct neutral weight endpoints, public MorphBench bounds and
the chosen anatomical split. No skeleton is written or replaced.

The completed output and exact six-file manifest are external:

```text
D:/Skyrim VR Modding/Builds/claw-anatomical-split-20261026/final-resource-manifest.json
D:/Skyrim VR Modding/Builds/claw-anatomical-split-20261026/final-composed-004/
```

| Sex | `_0` NIF SHA256 | `_1` NIF SHA256 | Shared remapped TRI SHA256 |
|---|---|---|---|
| Female | `030f6e48...6e23` | `3deb12cf...19d3` | `04cc835c...ac04` |
| Male | `88a1e7df...f311` | `86382761...b9c7` | `75472a4a...50e0` |

The female has 97 nodes/21 shapes; the male has 92 nodes/22 shapes. Six added
nodes in each are split shape pieces, not skeleton bones. Both endpoints retain
exactly the same topology, vertex order, UVs, packed weights and binds, with one
shared TRI. Native readback verifies the exact original material and three UV
corners for **every remapped triangle**. The chest/torso piece derived from
`head` retains its original head shader, `head.dds`/`head_n.dds` textures and UV
layout; it is not merged into the `body` material and no atlas is introduced.
The original material boundary is a deliberate texture/texel-layout boundary.

`scripts/compose-vr-body.py` and `recipes/composed-vr.json` build this family.
MorphBench's public `open`, `bounds`, `attach` and `bounds_write` interfaces fit
and write spheres. A caller-built analysis model adds a **nonserialized** neutral
weight direction to the original morph fields. Actual-bind LBS then encloses the
complete independent additive 0..1 morph/weight cube at 151 ordinary/held-out/P1
poses and nine explicit Head examples, in raw-packed and normalized modes.
Conservative per-vertex coordinate boxes and their convex hulls include all
coefficient combinations at those finite poses. Independent full-precision
readback checks every box against the stored spheres. Only sphere fields may
change during bounds stages, with byte reconstruction proving that constraint.
The writer tolerance is zero; the first attempt exposed a male genital-sphere
protrusion that the tool's ordinary 1% acceptance tolerance would have kept.
That attempt remains failed evidence; the selected second build encloses it.

Both endpoint splits pass exact native readback and ten controlled Head states
at six neutral/morph states, with zero exterior error and zero duplicated-seam
gap. This proves faithful composition and remapping, not visual or runtime
acceptance. The all-visible resource lists eleven head pieces for a future
selective visibility adapter. Head-bone shrinking can still move retained torso
vertices; it is not the intended visibility policy for these resources.

### Independent actor weight

`scripts/build-body-weight.py`, `scripts/body_weight.py` and
`recipes/body-weight.json` derive distinct endpoints from the actual installed
human `_0`/`_1` pairs. The frozen regional projections are the same engine used
by human morph calibration. The measured 3BA endpoint mainly changes forearm and
calf radius, while HIMBO also changes upper-arm and thorax dimensions. A broad
named-morph fit was rejected because it required unrelated counteracting torso
changes. Smooth bone-region radial/width/depth fields fit the observed endpoint
features instead. Residual norm changes from 0.027362 to 0.0000732 for female
and 0.151167 to 0.0002262 for male. Maximum neutral endpoint movement is
0.146024/0.879522 units; these deliberately follow the measured subtle human
endpoint semantics rather than inventing a dramatic heavy body.

The runtime contract is explicitly:

```text
w = clamp(actualHumanWeight / 100, 0, 1)
V(w,c) = V0 + w*(V1-V0) + sum(c[m] * absoluteTRI[m])
```

Human weight 30 maps to neutral interpolation 0.30. It never multiplies the
already-applied named morph coefficients. No actor-weight pseudo slider is added
to the shared TRI. Collar anchors follow their frozen skin triangles, whole fur
cards inherit the root translation and blend patches follow per vertex. Authored
normal/tangent frames are transported with the local deformation Jacobian;
their UV and skin slots remain exact. A continuous triangle-area calculation
over neutral weight 0..1 finds no collapse or normal reversal. Minimum own-rest
area ratios are 0.93765 female and 0.61461 male; all whole fur cards retain area
exactly under the neutral translation field.

An independent continuous weight-path audit on actual posed body/head triangles
also finds no area collapse at neutral or BreastSize1 across the 151 ordinary/P1
poses. Female has no normal turn beyond 90 degrees relative to the same posed
weight0 triangle. Male has two body and 19 head pose/triangle instances with such
a turn, despite nonzero area; minimum endpoint area ratios are 0.124/0.102.
Those witnesses motivated the selected local repair below. The original receipts
remain as historical `female-continuous-weight-poses.json` /
`male-continuous-weight-poses.json`; they do not describe the selected repaired
male high endpoint.

### Minimal male weight-path repair

Only 15 unique triangles/23 vertices caused the 21 primary pose instances:
two body triangles at the right shoulder and 13 head-material triangles at the
lower neck. Their vertices and one-ring neighbors do not intersect selected
ear/tail contact support; closest contact vertices are 40.26/15.82 units away.
`repair-body-weight.py`, `male_weight_guard.py` and `body-weight-guard.json`
apply a welded-geodesic zero-delta guard at those seeds. The shortest passing
smooth fade is 2.5 units; 1.5 and 2.0 failed the same gate. No whole-body scaling,
new seam or named morph alteration is used.

The selected repair changes 28 body/193 head stored positions and re-inherits
137 blend/55 back-fur/493 belly-fur stored positions. Both raw-packed and
normalized LBS pass the continuous neutral-weight path at all 151 ordinary/P1
poses, with no area collapse or own-pose-weight0 normal turn. An independent
check of every affected fur/blend triangle finds no newly introduced continuous
weight-path collapse/normal-turn instances. Actual final contact extraction
proves exact unchanged P0, independent weight delta, absolute TRI fields and
normalized skin matrices for every selected male ear/tail region. `_0`, all
female resources and both shared TRIs remain byte-identical to family002.

Male endpoint feature residual changes 0.00022621 -> 0.00052852 against the
measured human target, with maximum feature shift 0.00035582. This small local
cost is explicit; no global feature refit changes contact support. The public
MorphBench additive/weight/160-pose bound proof still passes without changing
protected `_0` bytes or its spheres. Family004 repeats the fixed 2.5 choice
against the current frozen selector helper; family003 remains a valid historical
build against the earlier helper. Earlier families and failed attempts are kept.

### Actual residuals and orientation limits

`audit-composed-geometry.py` records actual distances to posed frozen triangles,
signed outside gaps, interior depths, transported-offset residuals and local
orientation indicators for weights 0/0.3/1, nine morph states and all 160 poses.
The final receipts are `female-gap-audit-002/geometry-audit.json` and
`male-gap-audit-004/geometry-audit.json` next to the family.

For female BreastSize1 at weight0, the 55 collar anchors include 27 outside and
28 interior roots. Ordinary/held-out maximum transported-offset residual is
0.04645/0.06436 units. Maximum **outside** signed gap is 0.13560/0.13616; maximum
interior depth is 0.63963/0.63801. The large total triangle distance is therefore
not all an exterior gap. Pure P1 causes no collar normal-gap change. At weight1
the ordinary normal-gap change remains approximately 0.14971 versus 0.15001 at
weight0. The male collar is nearly coincident, with ordinary residual about
0.00000134 and held-out residual about 0.00000187 at weight0.

Across all selected fur/blend roots, residual ordinary motion remains. Female
chest/belly pure-P1 transported-root maxima are approximately 0.00150/0.02521;
these all-root values must not be replaced by the better changed-card-only
numbers from the fitting report. Neck rotations still produce chest/belly root
residuals around 1.0456/0.9633 units, and `ChestBlend` remains less coupled.
Fur roots already include intentional exterior stand-off and embedded roots at
rest; their absolute signed gap and unexpected side crossings are reported
separately. This family does **not** certify complete fur coverage or close every
ordinary-animation seam.

No sampled ROI triangle reaches area below 1e-8. Female neutral and isolated
BreastSize states have no transported-normal sign flags in the 151 ordinary/P1
poses. Girth combinations produce orientation warnings, including at Girth0.25
under some imposed poses; male source poses already have such warnings at
neutral. These are cumulative pose/triangle indicators, not distinct proven
self-intersections. They prevent calling the complete morph/animation range
visually safe. Full self-intersection freedom, real animation, selective head
visibility, camera clearance and appearance remain actual runtime/visual gates.

Ten split tests, seven weight tests, three guard checks and three composed-family checks pass with
the native outputs enabled, including the original-head-texture/triangle-UV
regression, corrupted TRI/bind rejection and actual paired endpoint/bounds checks.
The output is a reviewable offline resource family, not a live installation or
released VR body.

## Serialized anatomical split trial

`scripts/split-vr-body.py` and `recipes/head-split.json` now implement a separate
trial on the canonical SE female carrier `3d14a68f...e2be` / moderate TRI
`18840924...b15`, and published male `cff0f62e...b0ef` / TRI `ff1a66d5...0729`.
The existing XP32 skeleton is read only. No previous rejected head-weight transfer
is promoted: this stage changes no packed weight or skin bind.

Five candidate neck boundaries use normalized Head-descendant ownership of
0.25, 0.4, 0.5, 0.6 and 0.75 on existing triangle edges. The selected 0.5 boundary
minimizes area-weighted ownership error and has the shortest measured skin seam
among these alternatives for both sexes. A horizontal height cut was rejected
anatomically: the beast's jaw extends down to z98 while the posterior neck rises
to approximately z128, and the female breast surface lies at z87..100.
Ownership follows that slanted throat/neck instead of removing breasts with the
mixed shape or intersecting the jaw at a fixed height.

| Main `head` skin boundary | Female ownership error / seam length | Male ownership error / seam length |
|---|---:|---:|
| 0.25 | 366.890 / 187.372 | 389.136 / 191.836 |
| 0.4 | 308.116 / 181.511 | 325.448 / 186.304 |
| **0.5 chosen** | **295.084 / 147.270** | **311.881 / 150.204** |
| 0.6 | 306.355 / 202.631 | 323.574 / 209.387 |
| 0.75 | 353.043 / 152.349 | 372.624 / 158.651 |

Error is the triangle-area integral of absolute binary versus mean Head ownership;
length uses existing export edges, including their UV copies, in model units.
These are explicit selection criteria, not an aesthetic or camera-clearance score.
Only the chosen boundary is serialized. It retains all actual BreastSize-support
vertices in the torso. Main skin keeps 2,329 torso triangles and assigns 15,127
head triangles, with 137 duplicated seam vertices, in each sex. The female seam
bounds are x+-12.911, y30.408..41.714, z101.863..127.760; male bounds are
x+-12.851, y30.392..41.837, z100.484..128.358.

Six mixed shapes split: `head`, `ChestBlend`, `fur_back`, `fur_belly`, `fur_chest`
and `fur_shoulders`. Fur cards and blend islands are assigned whole by mean
ownership; no strip is cut through its interior. Torso pieces retain their original
names. Added pieces use `_CLAWHead`. The report lists the eleven complete/head
piece names a future visibility adapter may hide. All pieces remain visible in
this trial so the complete exterior can be compared directly.

The narrow SSE binary adapter duplicates only each split shape's skin instance,
skin data and partition plus its shape record. It copies packed vertex rows,
normals/tangents/UVs, bone palettes, floating and packed weights, skin frames,
bind matrices and conservative source bounds exactly; shared shader, texture,
alpha and BODYTRI records remain byte-identical. Every source triangle appears
exactly once across its two outputs, with original winding. Shared seam vertices
are duplicated without welding or moving them. Orphan source vertices remain
in the torso map. Both sparse TRIP scale bytes and packed signed offsets are
retained exactly and only indices/shape names remap. This preserves the public
25 female / 24 male morph-name unions. `_0` and `_1` output bytes are identical
after checking the corresponding source endpoints are identical.

The actual readback is
`D:/Skyrim VR Modding/Builds/claw-anatomical-split-20261026/verified-002/head-split-report.json`.
The adjacent sex-specific index maps record every original vertex and triangle ID.
Female output NIF/TRI are `a0ebf156...21b40` / `04cc835c...ac04`; male outputs
are `148ad62e...d6f4` / `75472a4a...50e0`. Native readback checks all arrays,
weights, materials/alpha, partitions, BODYTRI, original node ancestry/transforms
and binds. All untouched original NIF blocks are byte-identical.

Ten controlled Head states (including the scale/position visibility example),
six neutral/BreastSize/Girth states, and separate raw-packed/normalized LBS
evaluations give exactly zero all-vertex exterior error and zero duplicated-seam
gap relative to the source. This is split equivalence, **not** a repair of source
Head-influenced chest motion. Shrinking Head can still move the retained torso;
the intended next runtime policy hides the listed shapes while retaining ordinary
Head transforms. The open neck after hiding, near-plane clearance, real animation,
VRIK behavior and visual fur coverage require actual acceptance.

```powershell
python scripts/split-vr-body.py --body-root '<canonical-body-directory>' `
  --skeleton '<existing-XP32-skeleton.nif>' --out '<new-external-directory>'
$env:CLAW_HEAD_SPLIT_NATIVE='<completed-external-directory>'
python -m unittest discover -s tests -p test_head_split.py -v
```

Nine tests pass with the actual serialized candidate enabled, including actual
readback rejection of independently corrupted TRI offsets and a shifted skin
frame; seven run without those two native checks. Output is an explicitly marked external resource tree, never a live install,
skeleton replacement, runtime head policy or released package.

## Two separate problems

The female `head` shape includes breast geometry. Hiding that entire shape removes
the breast surface, which is why the revised VR resource retains it.

Hiding or moving only the Head bone is more selective, but it is not automatically
safe either. Some vertices participating in the published breast morph carry
Head-descendant weights. Their shape name or material does not prevent them from
following that bone. The local inspected VRIK visibility implementation changes
the Head transform; that is different from hiding a complete BSTriShape.

The diagnostic freezes the actual skeleton hierarchy, full skin-to-bone and stored
global-to-skin transforms, including scale. It imposes ten explicitly named states:
rest; a Head local scale of0.01 with local position multiplied by0.25; independent
local rotations of+/-15degrees about each axis; and local Y offsets of+/-20units.
The scale/position state represents the inspected visibility operation. The
rotation/offset states are controlled examples, not actual HMD traces or allowed
motion ranges. Which VRIK branch executes on this setup is unobserved.

Only Head and descendants move. Other original globals are retained exactly,
avoiding numerical reconstruction noise in unaffected joints. The audit reports
raw packed and per-vertex normalized LBS separately; neither is asserted to match
the renderer's weight handling. Female measurements select actual nonzero
BreastSize TRI support and evaluate coefficients0/0.5/1. Male measurements use an
explicit front-thorax ROI with Spine/Clavicle support; this is a comparison region,
not automatic anatomical recognition.

## Actual published female result

| Shape | BreastSize vertices | With Head-descendant weight | Maximum packed head weight | Maximum displacement in scale/position example at BreastSize1 |
|---|---:|---:|---:|---:|
| body | 197 | 0 | 0 | 0 |
| head | 590 | 79 | 0.0948486 | 2.13064 |
| fur_belly | 3484 | 422 | 0.2329102 | 5.94938 |
| fur_chest | 290 | 70 | 0.1579590 | 3.92233 |
| fur_shoulders | 55 | 0 | 0 | 0 |

Distances are model/game units under normalized LBS. The+20local-Y example moves
the affected head/belly/chest support by at most1.89741/4.65863/3.15858units.
This quantifies susceptibility to the declared transform; it is not an observed
in-game crack. In particular, the current pure head-bone approach cannot yet be
called breast-safe, and the five face visibility changes do not close this gate.
The moderate collar/P1 body has different support and needs its own qualification.

## Run and interpret

```powershell
python scripts/audit-vr-head.py --out '<new-external-directory>'
python -m unittest discover -s tests -p test_vr_head.py -v
```

The report records selected/worst vertex IDs, pose matrices, actual input/source/
dependency hashes and per-mode measurements. It refuses nonmatching body/skeleton
inputs and changed files. Output is a new external report directory. It writes no
NIF/TRI, flags, skeleton, game/profile file or configuration.

Five numerical regressions cover ancestry, nonidentity parent scale, partial-head
torso influence, raw-weight rest bias and explicit ROI selection. The final actual
report is `Builds/claw-vr-head-20261026-002/head-motion-report.json` outside Git.
It establishes a concrete weight-policy problem to solve, rather than a working
VR component. Preserve skin/fur joins, four-influence budgets, ordinary poses and
the correct TRI when evaluating a separate correction candidate.
