# Female breast shape and rig development

The owner reports that the current enlargement looks unrealistic. A new shape is
required; adding bones or physics alone does not repair the static silhouette.
Prefer the existing XP32 skeleton. Replacement is a fallback only when existing
bones cannot meet a demonstrated requirement.

## Opt-in supported shape profile

`build-female.py --breast-shape recipes/breast-shape.json` is a shape-only
development candidate. It also requires `--surface-collars
recipes/surface-collars.json --slim 0.90`. No production build recipe enables it;
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

`scripts/rig-breast.py` is a separate offline builder. Nothing in the default
pipeline calls it. It accepts an explicit raw body NIF, its moderate shape-only
TRI, an existing XP32 skeleton and `recipes/breast-rig.json`. All three binary
inputs are SHA-256 pinned; the first profile accepts only the reviewed raw
85-node moderate candidate. A collar-weight work in progress is a different input
and is rejected. The profile contains our parameters and hashes, without a
prototype NIF, skin-weight blob or third-party settings.

For example, from the checkout root, with those pinned inputs already staged:

```powershell
python scripts/rig-breast.py `
  --body 'D:/CLAW-input/femalebodywerewolf.nif' `
  --tri 'D:/CLAW-input/femalebodywerewolf.tri' `
  --skeleton 'D:/XP32-input/skeleton.nif' `
  --profile recipes/breast-rig.json `
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
`python -m unittest discover -s tests -p test_breast_rig.py -v`.

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

`recipes/breast-rig-collar.json` is the separately measured composition profile.
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
