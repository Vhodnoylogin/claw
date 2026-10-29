# Human-driven morph expansion

Design research and measured family conversion, 26 October 2026. The additional
geometry targets below remain proposals. Existing targets now have measured
CBBE2.0.3, 3BA2.48 and HIMBO5.8 family conversions in
`distribution/profiles/MorphLinks.xml`; see [transformation.md](transformation.md).
The public 24 shared / 25 female names and frozen live SE inputs remain unchanged.

## Rule

A linked werewolf is a deterministic conversion of the actor's **actual applied
human coefficients**. Presets supply those coefficients; neither a wolf preset
nor an independent random trait is needed. Different human body families require
explicit conversion tables: equal strings or equal slider percentages do not
establish equal physical dimensions. Missing body coefficients remain zero.

The existing link reads RaceMenu/SKEE body morphs. Human head/FaceGen sliders and
node transforms use different data paths; their presence in the RaceMenu UI does
not make them readable through `IBodyMorphInterface::GetBodyMorphs`.

## Candidates backed by current human body resources

All artistic meanings and gains below need measured shape calibration. A source
name's existence does not establish current actor value or UI registration.

| Priority | Proposed wolf target | Female 3BA 2.48 sources | Male HIMBO 5.8 sources | Purpose |
|---|---|---|---|---|
| First | `CLAWArmForearmGirth` | `ForearmSize` | `ArmsFore` | Separate forearm strength from the current whole-arm girth |
| First | `CLAWTorsoGluteSize` | `BigButt`, `Butt`, `ChubbyButt` | `ButtBooty`, `BubbleButt`, `LegsGlutes` | Local hip/glute volume without enlarging the entire thigh |
| First | `CLAWTorsoAbDefinition` | `MuscleAbs`, `MuscleMoreAbs_v2` | `TorsoFlatAbs` | Abdominal surface definition; this is not a muscularity simulation |
| Next | `CLAWTorsoRibDepth` | `ChestDepth`; inspect `SternumDepth` separately | `TorsoSterDepth` is only a local sternum source | Separate whole thorax depth, sternum contour and pectoral volume; no equivalent whole-thorax HIMBO source is established |
| Next | `CLAWTorsoRibWidth` | `ChestWidth` | regionally calibrated `TorsoWidth` | `RibsMore_v2`, `TorsoSterWidth` and `TorsoRibsDefinition` need distinct local contour targets, not automatic cage-width substitution |
| Next | paired shoulder widen/narrow targets | `ShoulderWidth` | `TorsoShoulderInc`, `TorsoShoulderDec` | Lateral width separately from shoulder mass |
| Later | `CLAWTorsoGluteRoundness` | `RoundAss`, `ButtShape2`, `ButtSaggy_v2` | `ButtRoundy`, `ButtCurve`, `ButtSaggy` | Separate roundness/sag from volume; opposing meanings require separate fields |
| After the breast rig | separate chest/breast sag fields | `BreastGravity2` | `PecsSaggy` | Soft-tissue position with stable roots and corresponding fur motion |

The present composer clamps each target to nonnegative 0..1. An opposing human
source with a negative gain can cancel widening, but cannot make a neutral wolf
narrower. Genuine narrowing therefore needs its own geometric target (or an
explicitly redesigned signed target contract), rather than an invented offset.

Do not map arbitrary muscle or belly values to ears/tail just to populate every
existing wolf slider. A human ear-size/ear-angle source could justify an ear
mapping; nose/jaw sources could justify muzzle/jaw proportions. No such source
is established in the inspected body catalogs. The inspected RaceMenu 0.5.0-b6
public plugin header offers body reads and face-preset import/export, but no
direct named FaceGen slider reader. A head adapter is separate research, with
race/sex/version handling and capture before transformation. No human `Tail`
source was identified; tail-specific controls stay outside this conversion until
an explicit human-derived rule is selected and justified.

## Many-to-many conversion: what is already possible

The owner explicitly permits many human inputs per wolf output and one human
input driving several wolf outputs. The native composer already supports both:
each distinct `(source, target)` pair is a rule, and each source is captured once.
It sums signed contributions for each target before a single clamp. This does
not require preset pairs or an OBody fork. It still needs a qualified family
profile and the actual target geometry.

For illustration only, let `m` and `f` be calibrated arm-muscle and arm-soft-volume
measurements, relative to the human family's neutral body:

```
upper_arm = clamp(0.7*m + 0.4*f, 0, 1)
forearm   = clamp(0.4*m + 0.2*f, 0, 1)
```

One human trait contributes to two wolf regions; two traits contribute to each
region. The numbers explain the rule and are **not measured production gains**.
Current native rules read raw named SKEE coefficients, not these intermediate
measurements. A flat linear version can be expressed now, subject to the 128-row
limit and existing target allowlist. Shared nonlinear measurements, source
curves, conditional corrections and signed output pairs are a future contract,
not features of `ConfigureMorphLink` today.

Deterministic does not mean invertible. Clamping, deliberately omitted cosmetic
traits and human differences invisible on a furred wolf may yield the same wolf.
The link must not attempt to reconstruct human values from that result: the
original human morph state remains owned by RaceMenu/OBody.

## Recommended anatomical decomposition

These are proposed semantic controls, not an enabled public morph list. Prefer
the few independently useful fields over many controls which deform the same
vertices in the same direction.

| Region | Improve or add | Human evidence to use | Important separation |
|---|---|---|---|
| Arms | Upper-arm girth, forearm girth, local muscle definition | 3BA `MuscleArms`, `ChubbyArms`, `ForearmSize`; HIMBO `ArmsBiceps`, `ArmsBicepsBack`, `ArmsFore` | Whole-arm girth should not silently prescribe the same enlargement at the elbow, wrist and shoulder |
| Shoulder/back | Shoulder width, deltoid mass, upper-back width | 3BA `ShoulderWidth`, `MuscleArms`, `Back`; HIMBO shoulder/back controls after geometric inspection | Lateral joint width, soft volume and the latissimus silhouette are different changes |
| Thorax | Rib width, rib depth, pectoral volume | 3BA `ChestWidth`, `ChestDepth`; HIMBO regionally calibrated `TorsoWidth`, `PecsSize`, `PecsMass`; sternum sources separately | Skeletal cage size must not become breast size or stretch the muzzle; local sternum shaping is not whole-cage depth/width |
| Waist/belly | Waist widen/narrow, belly projection, later lower-belly droop | 3BA waist/belly inputs; HIMBO waist/belly inputs | Side-to-side waist width and a belly protruding forward should remain distinguishable |
| Pelvis/glutes | Pelvis width, glute volume, glute projection; sag separately | 3BA `BigButt`, `Butt`, `ChubbyButt`, `RoundAss`; HIMBO `ButtBooty`, `BubbleButt`, `LegsGlutes`, `ButtRoundy` | Do not represent every buttock source by enlarging both thighs or the whole pelvis |
| Legs | Thigh/calf girth, local muscle definition; opposed slim fields | Existing human thigh/calf and muscle controls in the selected catalog | Preserve knee/ankle transitions and foot contact; an outline change is not a new gait |
| Abdomen | Abdominal definition independent of waist size | 3BA `MuscleAbs`, `MuscleMoreAbs_v2`; HIMBO `TorsoFlatAbs` | Geometry can change relief; it does not automatically change textures, normals or the visibility through fur |
| Female breast | Volume, lower projection, resting sag, later root spacing/height | Separate size, shape/forward and gravity/position human inputs | Static shape, skinning mobility, simulator stiffness and collider size are four distinct outputs |

Measure the selected source resources before interpreting a name. `Back`, for
example, is a catalog input, not a promise that its field isolates upper-back
width. Two similarly named glute/breast controls can be different shape bases;
do not merge them as aliases or add their percentages as physical volume.
Conversely, registered alternate names must not count the same deformation
twice. Alias selection belongs in the versioned resource adapter and requires
actual data evidence.

## Ears, muzzle, paws and tail

The existing body-only reader cannot justify every visible wolf trait. Add them
in stages rather than inventing human body inputs which do not exist:

| Wolf trait | Logical human relation | Availability / limit |
|---|---|---|
| Ear length, width and outward angle | Human ear dimensions and angle; separate signed controls where available | Requires an independently qualified head/FaceGen source adapter. Current body catalogs do not establish these inputs |
| Muzzle length/width, jaw depth, brow | Corresponding nose/jaw/head proportions, blended as a documented artistic translation | Future head adapter; capture human race/sex/source state before transformation. A body-muscle slider is not a substitute |
| Paw width/length | Human hand/foot proportions | Some changes may be body morphs; many RaceMenu dimensions are node transforms. Verify the actual provider before enabling a rule |
| Tail thickness | A modest anatomical analogy to overall soft-tissue/body bulk | Possible future derived body rule, explicitly identified as an artistic analogy. Author a true thickness field and check the root; current `TailFluff` must not be assumed equivalent |
| Tail relative length | Human relative limb length or stature proportions | Requires measured proportion/node-scale input and a declared scale convention. Do not apply actor scale twice if the engine already inherits it |
| Tail fur length/fluff | No reliable body-morph counterpart established | Leave neutral in automatic linkage until a defensible source exists. Human hair choice is not an applied body morph |
| Tail lift, digitigrade angle, claw length | No verified static human counterpart in current adapters | Keep neutral in this path; posture/animation or cosmetic controls must not be manufactured from unrelated belly/muscle values |

Not every target needs a human counterpart in the next release. Existing public
resource morphs can remain available to explicit mod integrations while the
automatic human-driven path uses only qualified targets. This does not reintroduce
an independently selected wolf preset.

## Signed inputs and neutral preservation

Negative human values are meaningful. The inspected 3BA and HIMBO RaceMenu source
registrations expose signed ranges; the current native conversion preserves
their sign until the target clamp. A negative widening input can reduce positive
widening but cannot shrink a neutral `0..1` target. The existing
`CLAWTorsoWaistNarrow` is already a geometrically shrinking positive target;
equivalent opposed fields are needed for regions which currently only grow.

For a calibrated signed width deviation `w`, a possible future pair is:

```
widen  = max( w, 0)
narrow = max(-w, 0)
```

Clamp to the pair's qualified envelope after its input contributions have been
combined. Zero maps to zero, only one side is active, and widening/narrowing do
not fight each other. Do not add an arbitrary baseline offset just to make a
negative coefficient visible. The fields must be authored and qualified; a
negative coefficient on an arbitrary old growth TRI is not automatically safe.

The inspected source geometry also demonstrates why a label cannot choose a
gain's sign: the literal positive 3BA `ShoulderWidth` field moves its active
vertices inward laterally, and HIMBO `TorsoWaistSize` does so around the waist.
These are measurements of the selected source fields, not assumptions about all
versions or fully combined in-game shapes. Source menu bounds, OSP flags and
actual built TRI coverage must be checked together before publishing the adapter.
The selected source slots all have `invert=false` and no zap/clamp attributes.
Independent current-TRI readback cross-checks every 3BA main-body and HIMBO field
against the corresponding OSD vector within quantization tolerance; the key
3BA/HIMBO sign findings are therefore not based solely on slider labels or OSD
metadata. Stock CBBE findings remain source-field evidence without a built-TRI
cross-check in this research.

## Calibration and versioning

Use one explicit adapter per actual human body resource/version and sex, rather
than per preset. Its reproducibility identity includes the source resource
fingerprint, adapter/mapping revision and target geometry revision. Preset names,
actor IDs and random seeds do not enter the conversion.

1. Freeze neutral human/wolf geometry, attachment regions and a local anatomical
   frame. Audit already baked body shape: zero live coefficients are not proof
   of a neutral resource, and rebuilding a non-neutral base cannot be recovered
   from absent RaceMenu values.
2. Measure human source deltas at negative/zero/positive controls and selected
   combinations. Use fixed region widths/depths/landmarks, projection and shape
   moments. Open disconnected meshes need a defined regional measure; do not
   label a bounding-box change or open-surface tetrahedron sum as tissue volume.
3. Fit a small family-level response table to those measurements. Separate bulk,
   width, projection, definition and resting position. Preserve real independent
   sources; resolve proven aliases once. Sum the raw signed contributions before
   output clamps, with an explicitly documented saturation policy.
4. Fit wolf targets to comparable *relative* proportions in its own rest frame,
   rather than copying human centimeters into the hunched beast. Purely linear
   mappings are the initial implementation. Add bounded curves/interactions only
   for measured residuals such as volume-dependent sag and combined-shape repair.
5. Verify the same input snapshot gives the same complete output regardless of
   former wolf assignment, actor weight and request history. Version upgrades
   must explicitly migrate or retain mappings instead of silently changing saved
   actors. Preserve human state and foreign morph keys on return.

An adapter must distinguish an unsupported resource from a supported source with
a legitimate zero value. Failure to read the provider is an error, not zero or
permission to choose another wolf. Face/node sources need their own lifecycle
snapshot and recapture rules; querying the beast's current face/skeleton must not
overwrite the human source snapshot. Current body refresh behavior remains as
documented in [transformation.md](transformation.md).

The current 128-row budget counts **edges**, not independent source names or output
names. Native validation, public API, typed family files and co-savev3/v4 support
that bound together; older v2 records keep their original 32-row reader. This
larger graph supports the measured combinations without introducing wolf presets.
A nonlinear stage or signed target format would still need coordinated API,
validation, persistence, geometry bounds and migration work.

## Current wolf fields: measured improvement candidates

A read-only 26 October audit of actual published and staged TRI files measured
unit fields on `body` and `head`. Euclidean delta cosine finds where fields overlap;
it is **not a visual similarity score, anatomical proof or defect verdict**.

| Pair | Published male / female cosine | Interpretation to investigate |
|---|---|---|
| MuzzleLong / HeadSize | 0.841 / 0.838 | Inspect whether head scaling can preserve muzzle length as an independent choice |
| BackWide / WaistNarrow | -0.605 / -0.832 | Localize upper-back width so it does not primarily act as the opposite waist field |
| BellyRound / Girth | 0.514 / 0.551 | Separate a projected belly from general torso bulk and avoid doubling the same silhouette change |
| TailFluff / TailLift | -0.782 / -0.781 | Inspect the local tail-axis/root convention before using Fluff as an anatomical thickness control |

The staged female repair's BreastSize head peak is 3.4513 model units versus
15.9907 in published 0.6.2.0, with zero body delta instead of a 6.4128 peak. It is
a deliberately different moderate shape, not a silently compatible amplitude
replacement. Its mass/projection/sag components are still baked into one public
TRI control; separating them needs new targets and calibration. See the
[breast rig](breast-rig.md) for the fixed attachment and fur-motion limitations.

External evidence: `Builds/claw-morph-research-20261026/wolf-field-evidence.json`
and its reproducible read-only audit. All sparse serialized pairs were checked
against the independent public TRI reader, accounting explicitly for that
reader's subthreshold filtering. No mesh, TRI or installed profile was changed.

## Reproducible static quality audit

`scripts/audit-morph-quality.py` now makes that investigation reusable on explicit
NIF/TRI inputs. It writes diagnostic JSON to a **new external directory** and has
no mesh writer, installation switch, game dependency or Morphbench dependency:

```powershell
python scripts/audit-morph-quality.py --low '<female_0.nif>' `
  --high '<female_1.nif>' --tri '<female.tri>' `
  --skin body head head_CLAWHead --out '<new-external-audit-directory>'
python -m unittest discover -s tests -p test_morph_quality.py -v
```

Use only actual existing primary skin shapes with `--skin`; an unsplit resource
uses `body head`. All shapes, including fur and blend patches, receive individual
surface diagnostics. The explicit skin selection defines the combined-field
comparison and cross-shape boundary join candidates; a shape called `head` is
not assumed to contain only anatomical head tissue. Stored normalized bone
weights allocate delta energy to named bone families as a leakage **proxy**.
These allocations are not an anatomical segmentation or a proof of leakage.

The audit independently decodes every serialized sparse pair, checks vertex
indices and exact agreement with the public PyNifly TRI reader, and retains
subthreshold pairs which that reader omits. Inputs, executed local sources,
PyNifly Python sources/DLL and environment versions are pinned in the report and
rechecked before success. Geometry and TRI vectors are transformed into the same
global shape/file coordinates, without evaluating skin binds or skeletal poses.
The audit reports field cosine, support overlap and best scalar-fit residual;
none alone establishes aliases, redundancy, artistic quality or physical volume.

It samples neutral, each unit field, pairs whose absolute skin-field cosine is
at least 0.4, and all fields together at 0.5 and 1. With `--high`, each state is
measured at normalized weights 0, 0.5 and 1 against that weight's own neutral.
Triangle area, negative dot against its neutral normal, edge strain and exact
triangle IDs are retained. A normal turn can be a legitimate large rotation;
these indicators do not certify inversion, collision or a continuous safe cube.
Boundary vertex pairs within the explicit neutral distance (default 0.0001 model
units) are frozen before deformation. Their relative motion is reported without
nearest-neighbor reassignment. Zero candidates means that join was **not
measured**; it does not certify a closed seam. Existing female collar gaps and
fur-root/skin distances still require the separate attachment audit.

The 28 October run on `final-composed-004` and published 0.6.2.0 found a concrete
male join issue: both have 135 neutral-coincident `body`/`head` boundary pairs.
`CLAWTorsoWaistNarrow=1` separates `body[99]` and `head[18]` by 4.137988914 model
units, at all three sampled weights. The male head field is entirely zero while
the body peak is 4.137988914. The current `full-body.json` WaistNarrow carry list
contains belly/back/chest fur but omits the attached skin head. This is direct
static join evidence, unlike the overlap scores. A bounded collar-follow repair
must protect the other fields, complete corresponding layer motion and check
both endpoints and poses before any visual acceptance. No production geometry
or recipe was changed by this audit.

Both selected sexes also retain 141 exactly coincident `head`/`head_CLAWHead`
boundary pairs in every sampled state; this checks that specific split join,
not the original body/head collar. Selected female BackWide/WaistNarrow cosine
is -0.8542 and male -0.6048. Their scalar-fit residuals are respectively 52.0%
and 79.6%, so the fields cannot be treated as interchangeable. Complete decode
counts are 319,963 female / 319,604 male, including 54 female subthreshold pairs.
The selected female audit samples 36 states at three weights; male samples 32
at three weights. Neither selected skin family has a newly zero-area triangle
at these samples, but normal turns and large strains remain investigation gates.
Reports and exact hashes are retained under
`Builds/claw-parallel-20261028/morph-quality/{selected,published}-{female,male}/`.

### Opt-in male WaistNarrow collar candidate

`scripts/repair-morph-seam.py` stages a separate TRI-only candidate on the actual
selected male endpoints. It appends the missing `head/CLAWTorsoWaistNarrow` record
while reconstructing the original TRI stream exactly after removing that one
record and restoring the head morph count. Every original serialized record,
both NIFs and every public name remain unchanged. No production recipe enables
this stage. Its artifact manifest references the two unchanged NIFs and the new
TRI; this is not an installation package.

These authoring tools require Python, NumPy and the locally configured PyNifly
Python bindings/DLL. The seam solver also requires SciPy. These are development
dependencies, not additional runtime requirements for players; the reports retain
the versions used for the measured candidates.

The correction samples the actual frozen nearest-body-triangle field, with a C1
geodesic taper on exact-coordinate welded head vertices. All 135 coincident
collar pairs constrain the exact body packed triples. All 141 split pairs and
vertices outside the collar band remain exactly zero. The new record uses the
body field's unchanged scale, so anchor equality survives int16 serialization;
interior values use round-to-nearest-even quantization. Conflicting duplicate
constraints, changed endpoint binds or a changed source contract are rejected.

The 9-unit band was the smallest passing tested band in the declared production
candidate sweep, against an explicit **numerical** guard: no isolated half/full
normal turns or collapsed triangles, and maximum head edge strain no greater
than the original body WaistNarrow strain at weights 0, 0.5 and 1. Narrower tested
bands failed that strain guard. The maximum 0.631028 strain is forced by an
already constrained seam edge; it is not a claimed appearance threshold.
Rejected harmonic-only trials remain external diagnostics, not exported variants.

The frozen `male-waist-seam-001` candidate changes 303 stored head vertices.
The new TRI is `a6087d542776888ee03a7884a311e005d33b537b7eb794769d93a45042767467`.
`male-waist-seam-002-current-source` is the same payload rebuilt after adding
duplicate-endpoint-name and endpoint-bind guards. Its TRI bytes and complete
static/pose/fur metrics match 001 exactly; `payload-equivalence.json` retains the
comparison and current executed-source pins. This refresh changes provenance,
not the shape or its acceptance status.
At all three weights, isolated unit WaistNarrow closes every frozen collar pair
exactly (previous worst gap 4.137989). The selected split remains exactly closed.
Other old fields retain their tiny pair mismatches: the all-fields stress state
still reaches 0.000869 model units. Across 160 declared existing-skeleton LBS
poses, isolated WaistNarrow's maximum collar distance decreases from 4.139004 to
0.000021321 raw packed, or 4.137994 to 0.000021318 normalized. These are imposed
offline poses, not observed animations or physics acceptance.

One indicator remains at weight 1 with every field at 1: head triangle 17 gains
a negative dot against its **neutral** normal. Its old and new stress normals
have cosine 0.99997419 (about 0.412 degrees apart); area changes 0.397187 to
0.389916 and its shortest edge stays 0.264217. The old stress normal was already
almost perpendicular to neutral. This is a disclosed threshold crossing, not
proof of inversion, and does not establish full stress-shape nonregression.
The exact vertices, normals, areas and interpolation samples are retained in
`male-waist-seam-001-normal-turn-review.json` alongside the immutable candidate.

Existing frozen `Layer` root/barycentric rules provide a separate static fur
check. Among 188 belly roots whose skin attachment is affected, unit-field
offset drift maximum decreases 3.700812 to 3.011569 and squared sum 462.551078
to 281.893822. Six chest roots improve slightly; shoulder and ChestBlend roots
are unaffected under these rules. Fur TRI fields remain exact. Residual drift,
fade cards, posed offset transport, coverage and appearance remain open; this
does not establish common skin/fur motion.

Bounds, geometry/model bindings, family morph calibration and physics/VR resource
hash contracts require a separate rebind or recalibration assessment for the new
TRI identity. Earlier model identities and acceptance are not inherited. Frozen
SE test inputs, installation profiles, meshes, shaders and skeleton were not
changed. Run the five seam regressions with
`python -m unittest discover -s tests -p test_morph_seam.py -v`.

## Implementation order

First qualify current OBody/body-source linkage and calibrated signed torso/limb
profiles. Then split upper arm/forearm and rib cage/pectoral fields, repair the
overlapping back/waist intent, and add glute volume/projection. Integrate the
moderate breast shape and separate its controls with the existing-bone rig and
common fur motion. Head/ear and node-proportion adapters come later; tail-thickness
analogy requires its own review. Preserve existing public names/semantics or
provide an explicit compatibility migration.

Morph-driven collider sizes must be derived from the resulting **wolf geometry**,
including combined morphs, rather than separately copying human gains. Size is
not physics stiffness: rest shape, skin weights, motion settings and collision
coverage need independent checks. Keeping the existing XP32 skeleton remains the
preferred route.

## Required implementation before enabling a target

1. Measure the human source geometry at representative values, including negative
   input if the source family permits it. Select the wolf anatomical region and
   direction; calibrate a family-level rule independent of preset names.
2. Author neutral-preserving wolf deltas for both sexes and every following fur,
   claw or blend surface; check shared seams, weights and both weight endpoints.
3. Extend the public name catalog, native recognized-name allowlist, linked-target
   policy, authoring resources and documentation together. `CLAWArmForearmGirth`,
   for example, is currently rejected by both target recognition and link policy.
4. Stay inside the current 128-edge profile limit or explicitly review a larger
   bounded format. Each source-to-target pair consumes a row.
5. Verify actual coefficients/readback and human-return cleanup, then inspect the
   rendered shape. TRI presence and an offline morph preview are separate evidence.

## Verified source evidence

The private 26 October neutral human asset manifest pins official 3BA 2.48 and
HIMBO 5.8 resources. Main female body TRI SHA-256 is
`924762114705422af5fcf9372adc800113532afa859b42b07cc376588bf92dcf`
(154 names on its main body shape; 156 across its body/hand/foot resource union).
Male body TRI SHA-256 is
`3c4d393e70f8ee86160b5571b69e8f894d1f67f0ed2d7d1067f72b1939a5df7f`
(124 names). The proposed source names above were checked against these catalogs.
HIMBO's supplied `_RaceMenuMorphsHIMBO.psc` independently registers its menu names;
the earlier lack of a female menu audit is superseded by the additional source
inspection below.

The pinned 3BA 2.48 RaceMenu menu registers body sources at -1..1, while HIMBO 5.8
registers -1..1; stock CBBE 2.0.3 uses -2..2. These are source menu limits, not
guarantees that OBody/other providers constrain applied coefficients to them.
The OSP catalogs contain UV-only controls omitted from body TRI, and HIMBO's
menu lists `BellyUpper` which is absent from the selected body OSP/TRI. The
inspected human ear integration selects a HeadPart; it does not supply a
continuous ear-size body coefficient. UI presence alone is insufficient.

Literal source-field comparisons found no byte-identical nonzero geometry
aliases within the selected 3BA, HIMBO or CBBE resource. 3BA `BreastGravity2` and
`PushUp` have cosine -0.9896 but still leave a 14.35% relative field residual after
the best scalar fit; HIMBO `PecsMass` / `PecsSize` have cosine 0.7666 with a 64.21%
residual. These are independent authored fields, not interchangeable names.
Do not infer physiological volume from these vector statistics. Exact source
paths/hashes/line references and limitations remain in the external
`Builds/claw-morph-research-20261026/human-source-review.md` and its measurement
JSON/script. Human assets are not copied into this repository.
`human-source-evidence-compact.json` and `human-source-tri-crosscheck.json` retain
the bounded source/sign/range and independent serialized cross-check evidence.

Current implementation contracts are [MorphLink.h](../distribution/include/claw/MorphLink.h),
[Preset.cpp](../distribution/src/Preset.cpp), [full-body.json](../recipes/full-body.json)
and [female.json](../recipes/female.json). No human third-party mesh or slider
implementation is copied into these proposals.
The public [SKEE interface](https://github.com/expired6978/SKSE64Plugins/blob/9ebcb733e17be695f994cd2e9cc383043446bc02/skee64/IPluginInterface.h)
separates body morphs, node transforms and face-preset operations; it does not
turn a head or node control into an `IBodyMorphInterface` source.

A concrete breast example follows from those source measurements:
`BreastsFantasy` would contribute to wolf volume, forward projection **and**
resting height; `BreastGravity2` would contribute to lowering and retraction as
well as a volume correction. Combining them can preserve projection while
lowering the tissue. Independent wolf volume/projection/lift/sag fields express
this, whereas one averaged BreastSize cannot. Fit the actual coefficients in
the wolf's breast frame, keep roots/fur attached and test combinations; neither
source's menu percentage specifies simulator stiffness or collider radius.


### 29 October manual-scene waist direction correction

Independent readback of the actual installed HIMBO NIF/TRI pair measured positive
`TorsoWaistSize` lateral responses of -0.10086448 (`_0`) and -0.10154594 (`_1`).
The published male CLAW `WaistNarrow` field measured -0.03953668 on the same frozen
bone-supported waist-width definition. Both positive fields therefore narrow.
The previous unconstrained multiregion projection chose a negative gain to reduce
its combined depth/belly residual; this reversed the primary lateral meaning.

The source mapping now changes only that gain from -3.8354787 to +3.8354787. The
calibration recipe preserves its fitted magnitude and other rules but constrains
this one independently qualified primary direction. It records both the old
unconstrained error and the new actual error; a better composite fit cannot
justify narrowing the Heavy actor while discarding the Slim narrowing source.
Actual scene inputs +0.2 and -0.4 now produce WaistNarrow 0.76709574 and 0,
respectively. Neutral remains zero. These are offline next-candidate changes;
the active manual game and installed XML are unchanged.

This does not create genuinely thinner arms/legs, improve muscular chest
calibration, remove upper saturation or establish rendered acceptance. Opposed
geometry and regional calibration still need their separate measured work.
