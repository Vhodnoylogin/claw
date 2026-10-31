# Female breast shape and rig development

The owner reports that the current enlargement looks unrealistic. A new shape is
required; adding bones or physics alone does not repair the static silhouette.
Prefer the existing XP32 skeleton. Replacement is a fallback only when existing
bones cannot meet a demonstrated requirement.

## Opt-in supported shape profile

`build-female.py --breast-shape src/main/resources/recipes/breast-shape.json` is a shape-only
development candidate. It also requires `--surface-collars
src/main/resources/recipes/surface-collars.json --slim 0.90`. No production build recipe enables it;
the build without this flag retains its previous behavior. The profile pins the
executable female BreastSize recipe, full-body recipe, collar recipe and repaired
neutral shape counts, triangle order and rest-frame bounds. An incompatible
recipe, missing repair or different SLIM amount fails before export.
All-zero coefficients are rejected at configuration validation. Empty, nonfinite,
float32-unrepresentable or all-subthreshold composed key deltas are rejected
before BreastSize key writes. PyNifly 28.1 `TripFile.set_morphs` uses a strict
per-axis 0.0001 cutoff and can omit the entire morph; the builder therefore reads
the actual written TRI through PyNifly's public `TripFile.from_filepath` API and
requires its CLAW name union to match the expected names before writing a success
report. A rejected export may leave candidate files; they are not an accepted
build. Standalone verification locates the dependency through ignored
`build.local.json`, while Blender uses its active add-on module.

The profile replaces only **CLAWTorsoBreastSize**. Its three private fields are
mass (up to 2.5 forward / 0.2 lateral units), lower projection (0.75 forward /
0.25 down) and sag (0.9 down). Their profile coefficients are bounded to 0..1;
they do not become additional TRI names. The base female public contract remains
25 morph names. This candidate deliberately changes the meaning of BreastSize:
its full displacement is about 3.45 units, compared with the old head-lobe peak
of 15.99. Existing values therefore produce a much more moderate change. This is
not a compatible amplitude replacement to enable silently in a released recipe.

The old repaired head field supplies a scalar influence mask. A two-unit
geodesic support band fixes the 55 lower attachment vertices, and a midline mask
avoids pulling the central thorax. Mirrored rest vertices within 0.01 units share
their influence; the donor's unmatched asymmetric collar vertices retain local
support rather than borrowing a different surface. The report counts these cases.
Mass, projection and gravity-looking sag affect only the local breast surface;
the face and neutral body remain unchanged. Sag is a static shape field, not a
simulation. The previous BreastSize body contribution is explicitly cleared, so
both head anchors and their body-triangle/barycentric attachments have zero
movement. Relative attachment offsets are checked at 0, 0.5 and 1 against both
current-neutral and frozen donor bindings.

The four local fur/blend layers inherit the combined body/head field through
the collar's current-neutral bindings. Full-weight cards translate as a unit;
fade cards receive only their weighted translation and can underfollow skin.
This does not establish fur coverage. The builder verifies that neutral vertex
coordinates, triangle order, UV loops and vertex-group weights remain unchanged.
It does not introduce bones or edit weights. The raw export still requires the
normal bounds/package pipeline before it could become an installable candidate.

The isolated local experiment and source candidate are not aesthetic, animation,
physics or game acceptance. The untextured shoulder join is a separate unresolved
condition, as are combined-morph extremes. No claim is made for Girth 0.5..1.
Review base, half and full from several views before choosing new production
defaults; retain the frozen source/recipe and NIF/TRI hashes with that decision.

The first combined source build passed nine profile regressions and read-only
PyNifly comparison with frozen collar v3: all 15 neutral shapes have exactly equal
vertices, triangles, UVs and skin weights, the same 85 node names, and exactly
equal deltas for every morph except BreastSize. The exported head peaks at
0 / 1.725633 / 3.451265 for coefficients 0 / 0.5 / 1, with no head-triangle normal
reversals in those isolated states. All 55 original donor triangle/barycentric
attachment offsets have zero change at all three values; body BreastSize is zero.
The pre-export mask has 228 matched pairs and two unmatched positive-X active
vertices; matched-pair displacement error is below 0.000002. TRI serialization
removes ten sub-threshold contributions (460 pre-export moved vertices versus
450 exported). This is an export tolerance detail, not proof of visible continuity.
Two additional regressions cover empty/tiny/overflowing composites and an actual
PyNifly binary round trip which drops an all-subthreshold BreastSize. The latter
requires the configured PyNifly dependency; it explicitly skips when unavailable.

After independent Morphbench tool qualification, a separate static bounds copy
passed all 15 shapes for the configured additive 0..1 morph envelope with 1.01
margin; the raw export passed only one. Raw NIF/TRI remain unchanged. Independent
PyNifly/byte comparison confirms only the fifteen 16-byte sphere fields changed
(199 bytes actually differ); geometry, topology, UVs and every other byte match.
All evaluated vertices stayed within the exhaustive-corner cap. This establishes
shape-local static coverage, not animation/physics displacement or game culling.
Keep the original wide references and do not promote the fitted copy automatically.

## Existing-bone rig experiment remains blocked

Offline inspection on 25 October verified existing XP32 `NPC L/R Breast P1`
ancestry through their respective PreBreast P1, Breast P1 and CME Spine2 nodes.
The selected P1 heads are approximately `(+-9.5, 28.993, 96.081)`; their local Y
axis points approximately `(0, 0.6646, -0.7472)` in the inspected mesh rest frame.
An explicit PyNifly export preserved ancestry with rest-matrix error below
0.000028. Copying missing mesh bone references did not change the pinned skeleton.
Export requires initialized nonzero edit-bone length before matrix assignment,
and `preserve_hierarchy=True, intuit_defaults=False`; inferred defaults otherwise
discarded the requested hierarchy in the isolated experiment.

That experiment discarded up to **0.11767578125** original influence while
fitting the four-influence budget. This blocks promotion of its weights or bone
references. A controlled three-degree imposed pose only checked the local motion
and fixed roots; it did not qualify a physics driver or existing 3BA settings.
The next rig source step is to redesign the patch/influence budget, then compare
original and proposed deformation across animation poses. Shape-only source
integration proceeds independently of that work.

## Verified starting point

Read-only PyNifly inspection on 11 October 2026 finds 345 nodes in the pinned XP32
werewolf skeleton, including bilateral PreBreast/Breast/Breast01 chains. The breast
heads are approximately `(+-8, 19.17, 90.014)` in the inspected rest frame. The
published female `_0` mesh contains 85 nodes and no breast nodes or weights.
Its current breast recipe gates deformation through Spine/Clavicle weights across
body, head, fur_chest, fur_belly, fur_shoulders and ChestBlend.

Importing existing bone matrices into a skinned mesh and assigning weights does
not itself add bones to the game's skeleton. Fit pivots and verify transforms in
the actual werewolf rest pose; human breast settings cannot be blindly copied.

## Chosen direction and alternative

First reshape the breast volume with a stable root, a smooth underside and a
controlled transition into the thorax. Separate volume, lower projection and sag
instead of one large swelling amplitude. Preserve the neutral body and UV/texture
continuity. Shape references and exact artistic proportions still need agreement.

Then use existing bilateral breast chains for local skin weights: firm attachment
near the thorax, progressively mobile tissue away from it, normalized weights and
smooth boundaries. Corresponding skin, fur cards and blend patches must share the
same deformation field at their joins. Keep Spine/Clavicle influence outside the
breast region. Dedicated colliders and physics are separate engine configurations;
their motion, contact and compatibility need runtime tests.

An independent breast mesh is a viable alternative, similar to an attached anatomy
part. It still needs skinning to existing dynamic bones for soft deformation; a
rigid attachment to one bone moves the entire part as one object. It also needs
matched thorax edges or controlled overlap, UV continuity, matching fur, normals
and removal/coverage of the old volume. Merely placing a new rounded part on top
would introduce clipping or another seam. Prototype one breast before selecting
integrated versus separate topology. No topology replacement is implemented here.

## First offline seam experiment

A local candidate changes CLAWTorsoBreastSize from separately deforming all six
shapes to a body-based field with explicit layer followers. At coefficient 0.5,
Morphbench reports p99 edge strain reductions: head 0.402->0.055, fur_belly
0.486->0.113, fur_chest 0.324->0.025. Body strain is unchanged. At full morph,
maximum head displacement drops from15.991 to5.711; this also changes the visible
volume, so the result is not a faithful shape-preserving repair. ChestBlend still
moves only0.007 units. The experiment identifies a mechanism for disagreement
between layers but does **not** establish that the reported underside gap is fixed.

Candidate recipe, NIF/TRI, command log, strain/layer tables and renders are retained
outside Git in the session's `roadmap-implementation-20261011` evidence. Production
`female.json`, build recipe and published assets remain unchanged. Future repair
must check neutral and morphed join distances/UVs, shared weight transitions, several
views and animated game poses. The known published gap remains disclosed.

## Opt-in post-export P1 source candidate

`src/main/python/build-tools/rig-breast.py` is a separate offline builder. Nothing in the default
pipeline calls it. It accepts an explicit raw body NIF, its moderate shape-only
TRI, an existing XP32 skeleton and `src/main/resources/recipes/breast-rig.json`. All three binary
inputs are SHA-256 pinned; the first profile accepts only the reviewed raw
85-node moderate candidate. A collar-weight work in progress is a different input
and is rejected. The profile contains our parameters and hashes, without a
prototype NIF, skin-weight blob or third-party settings.

For example, from the checkout root, with those pinned inputs already staged:

```powershell
python src/main/python/build-tools/rig-breast.py `
  --body 'D:/CLAW-input/femalebodywerewolf.nif' `
  --tri 'D:/CLAW-input/femalebodywerewolf.tri' `
  --skeleton 'D:/XP32-input/skeleton.nif' `
  --profile src/main/resources/recipes/breast-rig.json `
  --out 'D:/CLAW-offline/p1-new-candidate'
```

The output directory must be new and outside the checkout, input directories and
live game/MO2 trees. There is no install switch. The Python process needs numpy
and the public PyNifly API configured in ignored `build.local.json`, or supplied
with `--pynifly`. Blender, Morphbench, scipy and a game process are unnecessary.
Failure leaves a `FAILED-unverified-do-not-install` status when output creation
has started; only a completed report confirms the declared offline checks.

The pure numeric core projects the moderate BreastSize TRI onto its own
mass/projection/sag basis to recover a scalar mask. It applies bounded upper and
lower mobility roots, fixes the 55 collar anchors and face, and inherits the
scalar through public `surface_collar.Layer/Bindings` on current neutral geometry.
Its exact nearest-triangle projector uses AABB lower bounds and the existing
surface projection implementation. This reconstructed mask is a **new source
candidate**, not byte-identical reproduction of the older quantized prototype A.

The sole new skin influence comes from transferring part of Spine2 to the
appropriate existing P1. A smooth two-unit welded-geodesic capacity guard makes
P1 zero at every vertex already using four old influences. Other old influence
support is retained; serialized removal of a non-Spine2 influence rejects the
build. This avoids the earlier top-three pruning. Each layer has its own guard;
equal fur-root/skin motion is not established by this method.

The public PyNifly adapter adds exactly six existing XP32 ancestry nodes directly
after export, producing 91 nodes. The first added link includes the constant
compensation between the raw body's ancestor frame and donor global frame;
descendant donor matrices and all original node globals remain intact. Old skin
binds/global-to-skin are preserved. New P1 binds use
`inverse(G_P1_rest) * G_Spine2_rest * B_Spine2`, retaining the complete existing
skin frame. No skeleton file is written and no inferred human helper nodes are
introduced.

The builder reads its actual written NIF again. It requires unchanged vertices,
triangle order, UV and TRI bytes, the expected node graph/parents/matrices,
unchanged original binds, valid P1 bind products, nonnegative weights, at most
four influences and a bounded packed-weight sum error. Anchor weights remain
identical and anchor/face P1 weights remain zero. Pose metrics use the **entire
union of changed packed weights**, including tiny export changes outside the
desired mask. They cover moderate BreastSize 0, 0.5 and 1; ordinary Spine,
Clavicle, Neck, Head, upper-arm and twist rotations; unseen combined poses;
independent left/right P1 +/-3 degrees; same/opposite bilateral motion; and
combined ordinary/P1 poses. Exact pose matrices and changed vertex IDs are saved.
Both left and right head P1 must retain a positive stored weight on their own
side after actual NIF readback. A tiny mathematical field that half packing erases
is rejected as a no-op, even when the numerical plan/readback tolerance passes.

Raw packed-weight LBS and normalized LBS are separate reported calculations.
Normalization is not asserted to match the game shader. Half-weight sum changes
can produce a larger absolute raw-position bias, so the report also distinguishes
pure P1 motion from the candidate's own rest pose. These numbers cannot establish
an animated seam repair, fur coverage, aesthetics, a physics driver or runtime
behavior. The existing ordinary head/body attachment drift remains unresolved.

Before any later game candidate, audit effective P1 ownership: installed human
3BA/CBPC/SMP configurations might already drive these werewolf skeleton bones,
even though the released body has no P1 weights. Adding weights can expose that
existing driver without adding a new configuration. This builder does not edit
providers or add a runtime controller. Its verified output remains a development
candidate with driver, animation, collision, visual and game acceptance pending.

Run the core regressions with
`python -m unittest discover -s src/test/python/unit -p test_breast_rig.py -v`.

The first source build passed 11 regressions and all serialized checks on the
pinned inputs. Its reconstructed head field retains 271 mobile vertices, versus
269 in the local quantized-mask A. The written-weight change union contains
2,138 vertices across head and three fur layers. Across 151 poses, ordinary
baseline error reaches 0.001097 normalized / 0.053978 raw packed; unseen combined
ordinary poses reach 0.001145 / 0.052794. Pure P1 motion from its own rest reaches
0.152444 / 0.152430. An additional read-only check using frozen public Layer
bindings finds zero actual attachment-offset drift at all 55 head anchors in the
24 independent/same/opposite pure P1 poses. Full-card belly root offset drift
still reaches 0.043109, chest 0.007875 and shoulders 0.001903; this preserves the
layer-coupling limitation. Existing fixed-world attachment-offset vector change
still reaches 0.603888 in the selected combined poses. This includes natural
rotation of the rest offset and is not standalone proof of a gap. These are
offline measurements of this input
and profile, with independent source review and all runtime gates pending.

## Explicit composition after collar-weight repair

`src/main/resources/recipes/breast-rig-collar.json` is the separately measured composition profile.
Its only semantic changes from the original rig recipe are its name and the
input NIF pin `608448b9436827edd6534439fd79bcc1679f5477cc5427708cf62ce11e918d65`.
Use it with the output of `repair-collar-weights.py`, the same moderate TRI and
the same read-only XP32 skeleton. The stage recomputes capacity, mobility and
weights from that input; it does not transplant the older rig's weight blob.
The original recipe remains a separate experiment on the unreweighted carrier.
Neither recipe is enabled by the production build.

The composition CLI passed unchanged tolerances on all151 controlled poses and
the full2,136-vertex changed packed-weight union. Ordinary error is at most
0.001097 normalized /0.053978 raw packed, with held-out ordinary combinations
0.001145 /0.052794. Actual stored bilateral head P1 coverage is136left/133right.
Output contains91nodes, unchanged TRI and all25public morphs. All15source/output
shapes contain an actual stored global-to-skin matrix; calculations include the
small non-unit scales, rather than using the public matrix helper that omits
scale. Original skin binds remain exact; new P1 rest-product error is below
0.00000307. BODYTRI references and319,402finite/in-range/unique TRI pairs were
checked independently of the builder.

The resulting raw NIF is
`6792fc6c28c849c7a6279dedf2a7681abd154e7ad1327b4b4826285e1353e33d`, with TRI
`18840924604e974d166ab4f489311e66bcbff1852427eb0924b1242909099b15`.
This verifies file composition and the stated ordinary-LBS model. It does not
close the residual collar normal gap, fur-layer coupling, effective driver
ownership, real animation, physics or appearance gates. Static morph bounds are
a separate check and do not cover the controlled skeletal poses.

The qualified isolated Morphbench4bc01e41 tool subsequently ran the public
summary/morphs/bounds/write/readback path on this composition. A new copy passes
all15static spheres for range0..1, corner cap12, tolerance0.01 and margin1.01;
the raw input passes1of15. Full-precision readback and byte reconstruction verify
that only the15sphere fields changed (199bytes); every other byte, including
skin data, is retained. The bounded copy is
`05891e72862b5081e275f5360624860a95d549d27005b701c90cc4fe7838177f`.
The raw candidate and explicit TRI remain unchanged. This is the configured
additive file-space envelope, not a bound for P1/animation/physics displacement.

## Layer-only motion follower experiment

`src/main/python/build-tools/follow-fur-motion.py`, with `src/main/resources/recipes/fur-motion.json`, is a separate
post-export stage on the raw 91-node composition `6792fc6c...e33d`. It leaves the
repaired skin fixed and only considers full-weight `fur_belly` cards. Default
recipes, live assets, the static-bounds copy and the pending SE acceptance inputs
are unchanged. Use explicit `--body`, `--tri`, `--skeleton`, `--profile` and `--out`
arguments; the destination must be a new external directory. No install switch or
runtime controller is provided.

The stage freezes neutral card roots and skin triangles/barycentrics using the
existing Layer contract. Its target is the actual posed skin barypoint plus a
barycentrically weighted transport of the root's original offset. This permits
natural offset rotation and includes covariance from differently weighted skin
vertices. It is an explicit LBS transport model, not a contact or renderer oracle.

For each eligible card, a bounded scalar fit over 24 pure bilateral/independent P1
poses and BreastSize 0/0.5/1 adjusts the fraction of its existing Spine2/P1 pool.
No unrelated influence is removed, no bone reference is added and vertices with
four original influences and no spare P1 slot stay fixed. Exact half-float pairs
preserve each vertex's **existing packed sum**, including any original sum error;
this does not silently normalize the whole shape. A candidate card must reduce
normalized pure-P1 squared root error by more than 1% and an absolute 1e-8, avoid
raw/normalized pure-P1 maximum/squared regression, retain ordinary-pose budgets
and keep full-card edge-strain change below the declared experimental 0.01.

Measurements include all 151 poses at the three BreastSize states. Combined-pose
root values are retained in the whole-pose residual report; no separate combined
root nonregression rule is claimed. Bounds and other combined morphs are outside
this stage. Fade/disabled cards, unsupported palettes, chest/shoulder fur and
ChestBlend remain unchanged; this is not common motion for every layer.

Actual serialized readback checks the exact packed weight plan and detached
snapshots of all nodes/ancestry/transforms/extra data, vertices/triangles/UVs,
normals/colors/shape transforms, shaders/textures/alpha, partitions, skin
references/binds/frames and non-belly weights. TRI bytes are copied exactly.
This is selected-field protection, not a claim that every NIF byte is identical.
Executed source/helper/profile/dependency files are pinned before fitting and
rechecked before success; a changed input/source invalidates the build.

The 26 October second build accepted 138 cards, changing 753 stored belly vertices.
Among **those changed cards only**, maximum normalized pure-P1 transported-root
error falls from 0.0426480 to 0.00313483 game units. Maximum card-edge strain change
is 0.00753422, and normalized ordinary-pose deviation is below 0.000000169.
These values are not an all-layer improvement or an appearance guarantee.
The source/output contain the same 91 nodes and all 25 public morph names;
output NIF is `d99a1180ec4e6ebb0ba54033ecfdd7623b54c29850e60262b46412bcac19276d`,
with unchanged TRI `18840924...b15`. Seven regressions cover bounded fitting,
exact packed sums/support, a saturated palette, actual BODYTRI readback rejection,
detached-normal protection and an independently solved covariance example.

The first local diagnostic used weaker acceptance and incomplete source pinning;
its output is retained as historical diagnostic evidence, not the current candidate.
Neither output is installed or accepted for physics, animation or visible seams.

## Canonical SE carrier and further fur work

The 26 October canonical SE carrier is female `_0/_1`
`3d14a68f1683d8a9362bfda19b1a8fc74a8a792036f08bb9917dc9c3ea42e2be`,
with moderate TRI `18840924...b15`. Independent native comparison confirms that
all 15 shapes have exactly the same geometry and packed weights as the earlier
`608448b9...18d65` collar-weight repair. Thus the canonical carrier already
contains that actual attachment-weight correction; it is not the raw unrepaired
published female. This does not close its disclosed residual normal-gap gate.

`src/main/resources/recipes/breast-rig-canonical.json` explicitly pins this carrier. The actual
`rig-breast.py` rebuild recomputed its mask, capacity, P1 weights and existing-XP32
binds, then passed the unchanged 151-pose/readback checks. It reproduced
`6792fc6c...e33d` exactly. Running the original bounded belly follower on that
actual rebuild reproduced `d99a1180...276d` exactly. Results are retained in
`Builds/claw-anatomical-split-20261026/canonical-p1/` and `canonical-belly/`.
The installed canonical bodies, XP32 skeleton and default recipes remain unchanged.

`src/main/python/build-tools/continue-fur-motion.py` with `src/main/resources/recipes/fur-motion-continuation.json` now
continues the actual `d99a1180` carrier into full-weight chest and shoulder cards.
It uses the same numeric fitter, 151 poses, BreastSize0/0.5/1 and unchanged
raw-packed/normalized pure-P1, ordinary-motion and card-strain acceptance gates.
It is a separate explicit input contract; the earlier belly builder's frozen
contract is unchanged. No unrelated influence, skin surface, TRI delta, skeleton
node, bind, shader, normal, UV, partition or BODYTRI field may change. Actual
readback uses detached snapshots for every layer stage. Only the accepted card's
existing Spine2/P1 pool is redistributed with exact original packed sums.

Chest admits **no** card under those gates and stays unchanged. One shoulder
card admits two changed stored vertices: normalized pure-P1 transported-root
residual improves from0.000383410 to0.000269111 units; raw-packed residual changes
from0.000383597 to0.000269306. Ordinary-pose deviation remains below1.5e-9 and
maximum edge-strain change is0.000072084. These measurements concern that single
accepted card, not all shoulder or chest fur. This is a small actual continuation,
not a breast-gap closure or a new visual acceptance result.

The final raw 91-node NIF is
`da12437b16953eae0da2dcd841715a4110163702991b9a0912c17559a0a8f1d5`,
with unchanged moderate TRI. Both endpoint copies are staged under
`D:/Skyrim VR Modding/Builds/claw-anatomical-split-20261026/extended-fur/`;
its `report.json` contains pins, frozen roots/bindings, accepted-card metrics and
actual readback status. It retains the raw rig export's static bounds; a separate
bounds copy is required before any later install. No live files were written.
Chest/fade/ChestBlend coupling, the collar normal gap, other morph combinations,
animation, effective physics-driver ownership and appearance remain open.

```powershell
python src/main/python/build-tools/rig-breast.py --body '<canonical-female_0.nif>' `
  --tri '<moderate-female.tri>' --skeleton '<existing-XP32-skeleton.nif>' `
  --profile src/main/resources/recipes/breast-rig-canonical.json --out '<new-P1-directory>'
python src/main/python/build-tools/follow-fur-motion.py --body '<new-P1/femalebodywerewolf.nif>' `
  --tri '<moderate-female.tri>' --skeleton '<existing-XP32-skeleton.nif>' `
  --profile src/main/resources/recipes/fur-motion.json --out '<new-belly-directory>'
python src/main/python/build-tools/continue-fur-motion.py --body '<new-belly/femalebodywerewolf.nif>' `
  --tri '<moderate-female.tri>' --skeleton '<existing-XP32-skeleton.nif>' `
  --out '<new-extended-fur-directory>'
```

The existing breast-rig and fur-motion suites pass12and7checks respectively.
The anatomical head/torso split is independently serialized and qualified against
the canonical 85-node carrier in [vr-head-policy.md](vr-head-policy.md); these
91-node fur outputs have not silently replaced that split's input pins.

## Selected localized chest-root correction and full composition

The subsequent selected carrier is `d04aced0...f1c33`, retained in
`Builds/claw-anatomical-split-20261026/chest-attachment-003/`. This is a new
localized attachment stage in `src/main/python/build-tools/chest_attachment.py` /
`repair-chest-attachment.py` with `src/main/resources/recipes/chest-attachment.json`, not a weakening
of the older belly experiment's frozen contract.

The old full-card P1 fitter had no useful chest update because those roots
already followed pure P1 closely; considering the 56 fade cards also admitted
no P1 change under its existing gates. The larger mismatch was ordinary
Spine/Head/Jaw/Clavicle ownership at fur roots. The new stage fits only actual
root-related palette pairs against the posed frozen skin barypoint plus its
transported rest offset. Every stored P1 weight remains exact. All other shapes,
skin geometry/weights, skeleton nodes, binds, TRI, UVs, normals, materials and
partitions remain protected by detached native readback.

A common normalized pair correction is applied within each card. Scaling by
each vertex's pair pool was rejected as an unnecessary tip-motion amplifier.
An explicit line search reduces an infeasible correction while retaining the
same 0.01 card-strain ceiling, exact packed sums and the four-slot limit. Fitting
uses ordinary controls; held-out combinations and P1 states remain measurements.
The old-motion change is disclosed separately: an attachment repair intentionally
changes motion toward the actual skin target instead of treating every source
motion as correct. Related fitted support transfers are reported, with a maximum
removed support mass of 0.02734375; this is not silent capacity pruning.

The selected stage admits 97 cards and changes 389 stored chest vertices.
Changed-card normalized root squared error decreases 173.89325 -> 109.44056
(37.06%); raw-packed decreases 172.51604 -> 108.23192 (37.26%). The maximum
normalized card-strain change is 0.009985 and maximum old ordinary-motion change
is 0.234337 units. These selected-card improvements do not establish all-layer
common motion or a visually closed seam. The independent all-root audit retains
larger residuals, source stand-off/interior depths and `ChestBlend` limitations.
Its signed outside/interior results are summarized in
[vr-head-policy.md](vr-head-policy.md).

This selected 91-node carrier is actually composed with distinct calibrated
neutral weight endpoints, additive/weight/declared-pose bounds and the chosen
anatomical split in `final-composed-004/`. The final female has 97 total nodes
because six split shape pieces are added; its six existing XP32 ancestry nodes
and P1 weights remain the same. Exact final endpoint/TRI pins are recorded in
`Builds/claw-anatomical-split-20261026/final-resource-manifest.json`.
The 85-node split and raw 91-node experiments above remain historical independent
stages; they are not the selected final composition. No live files or skeleton
were written, and actual physics-driver, animation and appearance acceptance
remain open.
