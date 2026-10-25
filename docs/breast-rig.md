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
