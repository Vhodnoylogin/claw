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
