# Female surface attachment candidate

This is an opt-in source candidate. It is not installed, released, or accepted in
game. The published 0.6.2.0 assets and the existing build recipe are unchanged.
No new skeleton, bones, UV layout, vertex order or topology is introduced.

## Measured cause

The lower breast surface is part of `head`, overlapping `body`; these are not one
unwelded vertex loop. In the investigated breast region, 76 body and 327 head
coincident UV-split pairs remain coincident through the published breast morph.
Welding those export vertices would not repair the observed separation and would
invalidate the existing TRI indices.

The female SLIM step changes `body` but omits `head`. The published head positions
remain equal to the Elegant donor while the torso moves by up to 2.136 NIF units.
Independent breast swelling then increases disagreement at the attachment.

For 55 lower head-boundary vertices, nearest-body-triangle distance has donor
median 0.0494 and p95 0.5276 units. Published neutral p95 is 2.0612; published
breast coefficient 1 p95 is 3.7626. These are geometric distances, not a visual
acceptance result. The earlier body-only field-follow experiment reduced breast
projection and retained the neutral separation; it is not adopted as a repair.

## Source contract

`scripts/surface_collar.py` is the numeric engine. It requires NumPy, already
available in the Blender build environment, and has no Blender/NIF dependency.
It supplies pinned geometry signatures, closest-triangle barycentric bindings,
an attachment metric and a narrow harmonic correction. `morphlib` adapts Blender
objects and uses its existing BVH for efficient projection; it does not add a NIF
parser or copy another mod's implementation.

`recipes/surface-collars.json` pins the female donor SHA-256, imported vertex and
triangle counts, triangle-index hashes, rest-frame bounds and an exact 55-anchor
count. Wrong donor/topology/frame is an error. A PyNifly import change that alters
the frame or layout needs an explicit new measured pin, not a larger tolerance.

Bindings are frozen before any SLIM coordinates change. Each lower `head`
boundary anchor retains its original offset from a donor `body` triangle. During
SLIM it follows that triangle's displacement. A two-unit geodesic collar blends
the correction to zero; the projecting breast interior remains unchanged.
Coincident UV copies share the solver graph and correction, while their original
export vertices and UVs remain separate.

After ordinary recipes are evaluated, every `>CLAW` morph with an attachment
disagreement receives the same local constraint. The source body's deltas are
unchanged. Each corrected key is written relative to the corrected Basis, so the
neutral correction is not counted twice. Existing keys, when present during a
neutral move, translate with Basis and retain their relative deltas. Constraints
are linear in the morph fields, including combined coefficients, up to solver and
TRI export rounding.

Breast-local fur uses the frozen combined `body` and `head` skin surface. Connected
fur cards inherit an attachment translation. Full replacement preserves their
internal shape; in a spatial/distance fade, a common per-card weight blends the
original per-vertex deformation with that translation, retaining some original
internal deformation. `ChestBlend` uses per-vertex bindings. Explicit fades bound
the replacement. An existing morph key is overwritten even when its newly
computed field is zero; only creation of a new all-zero key is skipped.
Unselected fur retains the legacy field sampled on an explicit
virtual deformed source snapshot, before actual Basis mutation. This prevents an
unrelated change to the tail from the corrected operation order. No skin weights
are edited.

## Rebuild and inspect

Use the ordinary female builder inputs, adding:

```text
blender --background --python-exit-code 1 --python scripts/build-female.py --
  <pinned-built-male.nif> <pinned-Elegant-female.nif>
  <external>/meshes/actors/werewolfbeast/character assets/femalebodywerewolf.nif
  recipes/full-body.json recipes/female.json --slim 0.90
  --surface-collars recipes/surface-collars.json
  --surface-report <external>/surface-collars.json
```

Pass the same repeated `--skip-morph` arguments as the base build to exclude adult
morphs. Preserve the `meshes` directory in the output path for correct BODYTRI.
Add `--dry-surface-collars` to validate pins and bindings without exporting.
Without `--surface-collars`, the original build behavior is retained.

The report records donor/male/recipe/source hashes, Blender version, attachment
metrics before/after, peak morph deltas and the unchanged attachment-weight
disagreement. Report `distance*` values measure the frozen triangle anchors;
nearest-surface distance is a separate measurement using `closest_surface`.

The first compiled candidate restores nearest-surface p95 to approximately 0.53
at neutral and 0.49 at breast coefficient 1, while preserving the published head
breast peak displacement of 15.990665. UV arrays and triangle indices remain
identical. These figures are candidate evidence, not a qualified visual range or
enclosed anatomical volume measurement.

The current two-unit collar has a known extreme-girth concern: head triangle
normals reverse relative to the published surface for 2 triangles at
`CLAWTorsoGirth=0.5`, 16 at 0.75, and 13 at 1. No such flags were measured at 0 or
0.25, or for the breast morph at 0/0.5/1. This flags a possible crease/fold, not a
proven self-intersection. Increasing collar width alone did not resolve the
orientation concern in the array investigation. Do not describe the whole 0..1
range as visually safe; inspect the actual distributed preset coefficients and
repair the extreme-girth transition before qualifying that range.

## Acceptance still required

Synthetic regression cases are in `tests/test_surface_collar.py`. Their execution
on 25 October 2026 passed all nine cases, including an actual adapter regression
for replacing an existing nonzero layer key with zero and a fade-region case
that retains internal card deformation. The retained offline report also
compares Morphbench CLI strain, layer and bound results against 0.6.2.0. At breast
coefficient 0.5, fur_belly p99 strain changes from 0.486 to 0 and fur_chest from
0.324 to 0; head p99 remains 0.402, with 14 additional edges over the 0.25 strain
threshold. At Girth 0.25, head p99 changes 0.177 to 0.174, with seven additional
edges over the threshold. These local tradeoffs need visual inspection; the
improvement in fur does not certify the head surface. Raw export bounds require
the normal post-export bounds stage, writing a separate file before use.
The head-based layer estimator also flags a limitation of translating cards by
their roots: `fur_shoulders` becomes adjacent (contact 0.032), with actual maximum
movement 0.177 versus estimated local expectation 1.773. For `fur_chest`, actual
maximum is 13.524 versus expected 14.911. The estimator is not a gap measurement,
but these differences must be inspected; low edge strain alone does not prove
that card tips maintain coverage. A separate bounded copy of the candidate passed
all 15 bound checks against the explicit base TRI; the raw export was preserved.
Inspect neutral, intermediate, extreme and combined torso morphs from several
views; check seams, fur coverage, triangle orientation/strain, normals, materials,
BODYTRI, bounds, both endpoints and base/adult geometry parity.

The donor has attachment skin-weight differences: L1 median approximately 0.035,
p95 0.183 and maximum 0.222. Static positional continuity therefore does not prove
animated continuity. Compare deformation in actual poses before acceptance; do
not replace XP32 or silently redistribute weights to hide that limitation.
This change repairs attachment behavior, not the owner's separate request for a
more natural breast sculpt and dedicated breast physics.

## Separate experimental post-export weight repair

The positional collar does not make the head/body skin weights agree. A separate
standalone candidate now addresses this: `scripts/repair-collar-weights.py` with
`recipes/collar-weights.json`. It is **not** a complete geometry fix, and no default
female flag, production build recipe or installed asset enables it. It introduces
no P1 weights, skeleton/bone references or fur weight changes.

```text
python scripts/repair-collar-weights.py
  --nif <surface-collar-v3-and-moderate-BreastSize-female.nif>
  --tri <explicit-moderate-female.tri>
  --skeleton <pinned-XP32-skeleton.nif>
  --profile recipes/collar-weights.json
  --out-dir <new-external-staging-directory>
```

Use one command line, or the shell's normal continuation syntax. Machine paths
come from ignored `build.local.json`; `--pynifly <add-on-directory>` overrides only
that dependency path. The output directory must be new, with an existing parent,
outside this checkout, configured live mods and Data/mods/Overwrite trees. There
is no overwrite option. A failed serialization/readback may leave rejected files
without a success report; those are not an accepted build.

This MVP deliberately pins exact input bytes: NIF `83037676...30b3`, TRI
`18840924...b15`, and XP32 `b64b614d...c2dd0`, with 85 carrier nodes and 25 public
morph names. The profile contains the 55 frozen body-triangle/barycentric bindings
and the two-unit geodesic band. Different geometric/sculpted/rigged inputs need an
explicit new measured composition profile; widening a tolerance does not qualify
them. Inputs remain unchanged and the TRI is copied byte-for-byte.
The canonical relative NIF/TRI filename is also pinned: renaming a copied TRI
would leave the unchanged embedded BODYTRI references pointing elsewhere, so an
alternative destination name is rejected before writing.

The numeric core `scripts/collar_weights.py` derives normalized body-bary target
weights. Thirteen targets need three influences, 33 need four, eight need five
and one needs six. Direct interpolation is therefore insufficient for the
four-slot format. Even with unlimited slots, averaging weights at a head vertex
differs from averaging the deformed body-triangle vertices: their position/weight
covariance leaves a residual. A nonnegative simplex fit uses 79 controlled
ordinary poses, with 36 deterministic combined poses held out for measurement.
The existing skin-to-bone/global-to-skin matrices are used, including the old
common-C frame; identity rest binds are not assumed.

The fitted anchor weights blend into the head over a two-unit welded solver graph.
Only 104 export vertices change. A bounded search chooses nearby half-float
weights that sum **exactly** to one with at most four influences. This is explicit
normalization of the permitted vertices only. All other packed weights remain
exactly original. The public PyNifly adapter first clears every permitted vertex's
old slots, then refills them: merely omitting a removed influence from a per-bone
map left a stale 0.1152344 slot in the rejected local writer experiment.

The written NIF is re-read. Any change to nodes/ancestry/matrices, shape vertices,
triangle/UV arrays, bone references, skin binds, other-shape weights or head
weights outside the band is an error. Readback must equal the exact-half plan;
the TRI hash/name union must remain unchanged. The report records support mass
removed, quantization adjustment, hashes, capacity and separate pose measurements.
Readback compares detached pre-write arrays/scalars, not the mutable NIF object
used by the writer. Node parents/globals, vertices, triangles, UVs, bone references,
global-to-skin and individual skin binds are captured before any setter runs.
The regression that shifts Spine2 bind by 0.25 in both the live writer carrier and
readback must still fail against this original snapshot; pose metrics also use
the detached original coordinates and bind products.

The first source CLI build reproduced the local candidate exactly: NIF SHA-256
`608448b9436827edd6534439fd79bcc1679f5477cc5427708cf62ce11e918d65`, unchanged
TRI `18840924604e974d166ab4f489311e66bcbff1852427eb0924b1242909099b15`.
Eleven regressions passed, plus actual CLI rejection of an existing output,
wrong NIF hash and wrong active count. An independently modified serialized NIF
with an outside-band weight change was rejected by the real readback guard.
The subsequent guard revision passed 13 regressions and six actual negative
checks. It also rejects a renamed BODYTRI destination before output creation and
the coupled 0.25 bind shift in both public NIF writer/readback RAM objects. The
recompiled default candidate retains exactly the NIF/TRI hashes above.

For normalized LBS, the maximum **weighted rotating-offset error** on ordinary /
unseen combined poses changes from 0.36788 / 0.60430 to 0.04613 / 0.06640.
The expected head point is the actual posed body barypoint plus the donor-bary
weighted `posedGlobal * inverse(restGlobal)` 3x3 applied to the original actual-bind
rest offset. This permits natural LBS rotation/stretch; the old difference from
a fixed world-space offset is not used alone as evidence of a gap. The direct
full-bary transfer residual is 0.02588 / 0.03739, not a global lower bound on all
possible fitted solutions.

These numbers are **not absolute gap distances**. Distance to the actual posed
frozen donor triangle has candidate p95/max of 0.52718/0.63963 on ordinary poses
and 0.52297/0.63801 on combined poses, retaining the donor's original rest offsets.
Maximum distance-change from rest improves from 0.35952/0.41329 to
0.12463/0.17147. Geometric normal-gap change still reaches 0.15001/0.19756;
normal-direction attachment is not perfect. Raw-packed LBS is reported separately:
normalizing the 104 imperfect-sum original vertices changes its rest-offset by up
to 0.02671, versus about 0.00000658 in normalized LBS. Neither mode claims how the
engine shader treats weights. Up to 0.11523 original support mass and 0.02712 of
the full bary target are removed in the explicit transfer/fit; this is disclosed
alongside the pose results rather than hidden as harmless pruning.

Stage ordering is geometry/collar + moderate shape export, **then this weight
repair**, then a separately qualified P1 stage. The corrected 55 anchors have 13
three-slot and 42 four-slot palettes. Recompute P1 capacity, masks, weights and
binds from this new carrier; never silently reuse frozen P1 weights from the old
base. Fur-root inheritance remains separate numeric research. Bounds, shoulder
join, fur coverage, other morph combinations, animation clips and game acceptance
remain open.

## Controlled morph combinations and rejected wider collar

Nine representative Girth/BreastSize combinations were evaluated on the moderate
width2 geometry, together with continuous triangle-area minima along the declared
morph paths. A negative dot product between rest/deformed normals was not treated
as proof of inversion. No zero-area path was found by the declared numerical
criteria; this does not certify self-intersections, a safe coefficient domain or
appearance. Static vertex geometry is distinct from animated/skinned game output.

The body triangle22897 reaches area0.004590282 (0.00463491 of its rest area) at
Girth0.888589. That strong flattening is identical to the published mesh and cannot
be corrected by widening the head collar. Head triangle1694 reaches0.009459227 at
Girth0.691186, versus0.08461107 in the published geometry. Its own-rest area ratio
changes0.08962436 to0.00850383. The corresponding absolute edge minima around the
collar are0.459140/0.446776, versus0.514836/0.511857 in the release; comparing only
ratios would exaggerate the difference because neutral lengths also changed.
The55anchor donor-triangle distances retain the improved attachment; moderate
BreastSize adds no anchor movement. These are localized remaining defects, not
evidence of a newly opened seam or a completed repair.

A single external width3 experiment was tested and **rejected**. First, a passive
capture reproduced the original width2 NIF/TRI byte-for-byte and the exact
pre-reconcile Girth field. The original published Girth could not substitute for
that field because recipes run after neutral Basis correction. The0.0003 geometry
reproduction gate remained unchanged; TRI int16 truncation/float32 multiplier
rounding was measured separately rather than disguised as a geometry tolerance.

The complete width3 build used explicit external recipe/profile copies, recomputing
all Basis-dependent fields. Only two measured fur_belly X bounds needed new input
pins; their movement was independently explained by the existing full-card
barycentric following law. Head/body pins, all tolerances, source/default recipes,
topology/UV/skin data,85nodes,25morph names and55anchors were preserved.

The selected edge minima improve to0.527279/0.553860, but triangle1694 minimum
area worsens to0.009298904. On the Girth0.5/BreastSize1 path, head ROI minimum area
worsens from0.069050328 to0.038134362, with triangle929 as the new worst case.
Inherited body22897 remains identical. There is no justified aggregate improvement,
so no width3 profile is promoted or installed and no further width tuning follows
from this experiment. The next repair needs a locally shaped deformation field
and visual/animation evidence, rather than assuming that a wider blend is enough.
