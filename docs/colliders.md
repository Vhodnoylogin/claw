# Offline collider candidates

`scripts/fit-colliders.py` implements the first bounded development step of the
collider roadmap. It fits the **existing** XP32 collision bodies to a selected CLAW
mesh through Morphbench's documented `mb.py` batch interface. The result is a
development candidate requiring game physics validation. It is not part of
`build-all.py`, a release, or an installed mod. CLAW still ships no skeleton.
The owner prefers retaining XP32. These candidate files are measurement/prototype
artifacts, not a decision to ship a replacement skeleton. Prefer existing bones
and separately configured colliders; replacement requires a demonstrated need.

From the CLAW checkout:

```powershell
python scripts/fit-colliders.py --sex male
python scripts/fit-colliders.py --sex female --out 'D:/offline-evidence/claw-female-new-run'
```

`build.local.json` supplies the installed mod root and Morphbench entry point using
`scripts/locate.py`. Defaults select the released `_0` body: in 0.6.2.0 the `_1`
endpoint is identical for each sex. A selected body can instead be named with
`--body`, its morph file with `--tri`, the XP32 NIF with `--skeleton`, and its HKX
with `--hkx`. `--morphbench` and `--python` select the tool and interpreter. When
no machine configuration exists, provide body, skeleton and HKX explicitly.

The default output is a unique, ignored directory below
`work/collider-candidates/`. `--out` must be a new directory outside live MO2,
game Data, archive/download and source locations. Resolved paths also catch
junctions/symlinks. Existing output directories are refused, including an empty
one. Inside this repository only a new descendant of `work/collider-candidates/`
is accepted. There is no install switch. Each of five tool calls has a 60-second
timeout; `--timeout` can reduce it.

## The recipe and its assumptions

`recipes/colliders.json` records every explicit fit option: `body,head,claws`,
percentile 90, one capsule per existing collision body, axis splitting and zero
morph slider values. To investigate another static shape, copy/edit the recipe
and pass `--recipe`; named slider values become repeated documented `--slider`
options. This fits one pose, not a morph envelope or runtime changing colliders.

Fur cards and blend patches contribute to the visible silhouette; they are not
automatically solid skin. Eyes, mouth and internal anatomy are also excluded from
the default fit. This is an explicit initial collision assignment to review,
not an established game requirement. A different recipe may select other parts.
Every selected shape must exist before the skeleton is written.

Morphbench assigns each vertex to its dominant bone, with a minimum weight of
0.5. Skin held by descendant bones without their own collision body is assigned
to the nearest ancestor that has one. This is a fitting ownership rule, not
observed runtime collision ownership. The recipe verifies `colliderMinWeight`
and `bundleMinPoints` in Morphbench's local settings before invoking the CLI.
It records that settings file and the tool revision rather than silently taking
different machine defaults. Bundle count one keeps the initial experiment small.

The HKX is mandatory and must provide a readable ragdoll with no unmatched
collision bodies. Capsules are fitted in their ragdoll body's coordinate frame,
not merely the NIF node frame. This matters for XP32 werewolf head/neck/feet; the
head frame differs by 90 degrees. The original skeleton NIF and HKX remain inputs.

## Evidence and interpretation

Each run retains the exact argument arrays, return codes, stdout/stderr, shape
inventory, source summary, before/after collision tables, fit report, candidate
`skeleton.nif`, and `collider-candidate.json`. The manifest records recipe, input
paths, byte counts, SHA-256 hashes, tool/repository revisions and dirty state,
time, unmatched/unfitted bodies and per-body coverage changes. It verifies input
hashes again after fitting and rejects changes to the reported collision body
properties or ragdoll frames. The controller script is hash-pinned too.
Morphbench's own local log must be disabled or named `morphbench.log` beside its
settings; the wrapper never redirects that log into a live/game folder.
Failed runs retain a failed manifest and available
logs; only status `offline-candidate` means the offline steps finished.

**Coverage scope differs from fit scope.** The documented `colliders --clearance`
CLI accepts neither `--only` nor `--slider`. Before/after measurements therefore
include every visible mesh part at rest, including fur and patches, even when
the fit recipe uses only body/head/claws or nonzero sliders. They compare the
original and candidate skeleton against the same rest geometry. They do not
measure selected-part or morphed-pose coverage. Point counts must remain equal;
unmeasured bodies stay explicitly listed.

`outside` is a rounded vertex-count fraction, not surface area. The aggregate
weights those fractions by the reported point counts; it is approximate because
the per-body fractions are rounded. A 90th-percentile radius is an outlier policy,
not a promise that 90% of all visible surfaces are enclosed, and neither zero
outside vertices nor an improved aggregate proves contacts in animated poses.

Before considering distribution, review layer/ownership choices, male and female
coverage, ragdoll axes, contact distances, collision filters, constraints and
inertia, locomotion, grabs and strikes in an authorized game test with the actual
interaction stack. Ear/breast physics, dynamic morph following, VR body integration
and release acceptance remain separate work.

The public tool contract is in the neighboring Morphbench repository's
`README.md`, `docs/cli.md` (Collision capsules), and `docs/physics.md`; this script
imports no Morphbench internals and contains no NIF/Havok parser.

Run offline safety checks with:

```powershell
python -m unittest discover -s tests -p test_collider_recipe.py
```

## Morph-state audit with actual serialized skin frames

`scripts/audit-morph-colliders.py` is a separate offline diagnostic and candidate
builder. Supply explicit `--body`, `--tri`, `--skeleton`, `--hkx`, `--morphbench`
(repository), `--pynifly` (dependency directory) and a new external `--out`.
It preserves the original skeleton and uses only public PyNifly readers and
Morphbench's facade to inspect, allocate and write candidate capsule bundles.
The default is two capsules per fitted body at percentile95; these are explicit
approximation parameters, not a promise of close contact.

Mesh vertex coordinates are not assumed to be skeleton-world coordinates.
The audit evaluates each selected vertex using all serialized skin weights,
`restNode * skinToBone * globalToSkin`, with TRI offsets applied before that
transform. It records normalization, bind frames and unassigned vertices.
Ragdoll-body transforms are recovered on a disposable facade instance and
checked independently before converting fitted endpoints into those frames.
This avoids importing Havok body frames as CBPC node frames. Exact engine
weight normalization and animated skinning remain separate runtime questions.

Every available field is sampled alone, together with explicit mixed states
and return to neutral. For each state the report compares original capsules,
the neutral candidate and a refit to that state's selected skin. Both saved
neutral and mixed-state skeletons are reopened and their geometry/properties
checked. Omitted skin, unfitted bodies and observation precision remain explicit.
Finite state samples do not bound arbitrary morph combinations or animation.

Outside distance and membership in a capsule union are measured directly.
The minimum of individual signed capsule distances is only an **interior proxy**
when capsules overlap; it is not the distance to the union's outer boundary.
Vertex-depth diagnostics therefore do not certify that every capsule surface
lies close to the skin. A complete contact-fit criterion still needs explicit
surface sampling/triangle distances and real contact acceptance.

The accompanying `physics/fit-capsules.py` builds a different, node-local CBPC
ear/tail model using actual TRI dependencies, affine endpoints/radii and fixed
triangle assignments. Its source candidate can follow coefficient changes
through the explicit physics-host API, but requires a qualified effective-morph
reader/coordinator. See [physics/README.md](../physics/README.md). It changes no
Havok ragdoll, movement cylinder or weapon collision body. Neither experiment
installs a skeleton, changes a live profile or establishes release readiness.

## Current-vector refit and actual skin-triangle distances

`physics/fit-capsules.py --current-vector` emits schema 3, a separate native
model. It retains a fixed assignment of complete triangles and their actual
normalized rest-LBS points and signed TRI fields. It first deforms that support
by the current effective coefficient vector, then recomputes each capsule's
centroid, covariance axis, radius and shortened endpoints. No radius enclosing
unrelated coefficient combinations is carried into the current state. Grow,
shrink, mixed states and return to neutral therefore change the actual capsule
geometry. The dependency-free C++ evaluator is
`distribution/include/claw/PhysicsFit.h`; the generated `physics-fit-model.h`
contains immutable male/female support, exact ordered morph names and a shared
model identity. `physics-fit-fixtures.h` supplies matching numeric fixtures.

The triangle assignment includes every face touching a vertex whose dominant
ear/tail influence is at least 0.5. Mean target-bone influence assigns each such
face once, and **all three vertices** are retained with their complete skin
weights. This fixes the old omission of mixed ownership faces. In the pinned
26 October body inputs, TailBone03 owns 44 complete faces per sex; all 44 were
previously excluded boundaries. TailBone04 has no assigned face under this
rule; the adjacent assigned regions cover those source faces. Absence of a
TailBone04 capsule is not evidence of an uncovered hole or animated conformity.
The newly retained boundary support adds `CLAWLegThighGirth` to the effective
ear/tail dependency list. Dependence is discovered from the actual serialized
TRI fields rather than inferred from slider names.

For any one supplied vector, each freshly fitted convex capsule encloses its
support vertices and hence each whole assigned skin triangle. This property
does not certify tightness. In particular, more capsules can worsen an outer
surface by breaking a solid tail volume into bumps around its circumference.
`--current-counts` supplies nine explicit requested group counts, up to 128
total. `--partition-method auto` compares compact spatial groups and strips on
each neutral PCA axis using measured surface distance. This finite neutral
partition choice is not an optimization proof for other states or animation.

`physics/contact_fit.py` measures the exposed surface of the **capsule union**:
samples inside another capsule are removed, then every retained sample is
compared with the exact nearest point on a skin triangle, including triangle
interiors and edges. The other direction samples skin vertices, edge midpoints
and face centroids against the capsule union. All node-local geometry is
transformed to the same supplied skeleton rest frame before a whole-region
union is measured. Isolated regional seam/endcap distances remain diagnostic;
they can count a surface hidden by an adjacent node's capsule. These are finite
sample distances, not a continuous Hausdorff bound, signed protrusion volume
or contact onset test. Negative skin-to-capsule distances remain interior proxy
fields and must not be called union-boundary distances.

The external `current-005-128-auto` candidate has 128 stable slots and 11 actual
dependencies. Across neutral, all-one, mixed-0.35 and alternating states for both
sexes it retains zero outside skin samples. Its exposed-union capsule-to-skin
P95 is 2.18–3.15 game units and its maximum sampled distance is 3.43–5.18 units.
Consequently `surfaceFitAccepted` remains **false**. Its 44 male/female numeric
fixtures compare 5,632 capsules between Python and optimized C++ with maximum
coordinate/radius difference below 1.1e-13. An offline 200-repeat timing measured
0.263 ms per evaluation on this machine; this excludes Papyrus, native attach/
detach, CBPC broadphase, actor count scaling and actual game scheduling.

`physics/compare-contact-fit.py` compares an explicit affine schema-2 baseline
and schema-3 current model on the **same complete mixed-boundary triangles**.
Besides both surface directions it estimates actual capsule-union volume with
paired seeded samples and a standard error for the difference. This is not a
sum of overlapping capsule volumes and is not the volume outside closed skin.
Neither the numeric fitter nor that comparison changes an installed NIF,
skeleton, provider configuration or game profile.

The newer `--contact-passes` family changes the construction objective itself.
It minimizes a symmetric sampled maximum plus 0.2 times RMS over actual skin
triangles and capsule surfaces, moving all six endpoint coordinates and radius
at the current vector. It can leave a measured amount of skin outside; it does
not re-label an enclosing fit as close contact. The 128-slot `current-009`
trial reduced capsule-to-skin P95 to 1.28–1.73 units and sampled maximum to
2.54–3.57 units. Its tradeoff was 25–26% outside skin samples, with maximum
sampled gaps of 1.45–2.07 units. The one-unit construction goal was still not
met. Ten native/Python fixtures compared 1,280 capsules with coordinate/radius
error below 1.1e-13. The symmetric objective cost 113 ms per vector in the
offline optimized native benchmark; it must run as bounded pure worker work,
then revalidate the actor, model, generation, coefficient snapshot and weight
before publishing on the main thread. Static-PCA timing does not apply to it.

Independent actor weight is an explicit input to schema-3 evaluation. When
reviewed distinct low/high endpoints are supplied, the fitter verifies identical
selected topology and normalized rest-skin matrices at both endpoints, and
byte-identical evaluated absolute TRI fields. It evaluates
`P0 + u*(P1-P0) + sum(c_m*Delta_m)`, where `u` is normalized actor weight and
`c_m` are the actual effective morph coefficients. Weight does not rescale those
coefficients. Numeric fixtures include `u=0,0.5,1`. A model identity includes
the independent weight contract and endpoint fields. The source tool accepts
explicit `--male-nif-1` and `--female-nif-1`; no actor weight mutation is involved.

Optional `--female-p1-counts L,R` selects actual positive, side-matched P1
**skin** support. The rig deliberately gives P1 a minority mobility weight, so
the ear/tail dominant-weight threshold would incorrectly omit it. All weights
still contribute to its actual skin deformation. P1 slots are explicitly
female-only, with `male:null` and stable shared indices; a male compiled model
has inactive placeholders that cannot be attached as invented male anatomy.
Fur and blend-layer motion remains a separate provider/geometry qualification.

`physics/contact_diagnostics.py` adds full signed-field distributions and exact
worst-sample witnesses. Capsule-to-skin sign uses the nearest oriented triangle
and explicitly records ambiguous signs: selected skin patches are open, so this
is not a closed-solid winding classification or signed outside-skin volume.
Skin-to-capsule positive distance and membership are exact; negative overlapping
capsule fields retain their interior-proxy limitation. P95 values are over the
stated finite samples, without an area-uniform or continuous maximum claim.
`physics/verify-contact-support.py` compares actual full-LBS neutral ear/tail
triangles and every signed TRI field across a resource split, in a shared rest
frame. Its actor-weight-zero equivalence claim keeps changed weight endpoints
and newly added female P1 regions explicit and separate.

The final-resource candidate `final-020-stable-weight-P1-contact` uses 128 stable
indices: 96 active ear/tail capsules for males and those 96 plus 32 female-only
P1 capsules. It has 19 actual morph inputs and an independent actor-weight input.
Its 90 coefficient/weight states provide male and female numeric fixtures;
24 state/sex combinations have complete sampled surface and signed-field QA.
Across weight 0, 0.5 and 1, capsule-to-skin sample P95 is 1.408–2.006 units,
maximum sampled separation is 3.725 units, maximum sampled skin outside distance
is 2.224 units, and absolute skin-to-capsule-field P95 is 0.720–1.415 units.
The one-unit construction goal remains unmet and `surfaceFitAccepted` remains
false. Both growth and shrink changes are present; all six sex/weight return
checks restore identical neutral capsule geometry, with 32 inactive male slots.

This candidate was fitted afresh from the qualified `final-composed-004` family,
including the repaired male high-weight endpoint. Its separate actual input
comparison maps all 6,169 selected oriented triangles across 18 regions to the
preview: P0, independent P1-P0 and all absolute TRI fields have exactly zero
coordinate difference. Numeric capsule results were regenerated after an
optimizer sampling-frame repair. Ordered numerical tie rules for the PCA seed,
axis sign and least-axis surface basis prevent roundoff from rotating the
42-point objective grid. The complete 180 sex/state fixtures compare 23,040
slot outputs, including 20,160 active capsule outputs, with maximum native/Python
coordinate/radius difference below 6.1e-14. Per-vector optimized native timing is
111.7–111.9 ms for males and 138.5–138.7 ms for females over weight 0, 0.5 and 1
(40 repeats per case). These timings do not measure CBPC collision cost.

Actual nearest-triangle QA uses exact AABB pruning with an inclusive bound.
Equal/near-equal distances retain the lowest original triangle index within a
stated squared numerical tie tolerance of 1e-12. Regression comparisons check
the nearest triangle, closest point, distance and oriented normal against the
unpruned calculation, including coincident opposite-facing triangles. The
open-surface sign limitations remain unchanged.

`physics/rebase-contact-inputs.py` remains an input-only qualification tool for
preserving an existing fixed physical partition after a resource rewrite. It
captures inputs before parsing the model or executing selected own helpers,
uses their captured bytes, revalidates at completion, and records a bijective
cyclic oriented-triangle/full-field mapping. A topology, winding, endpoint,
skin-frame or TRI-field mismatch stops qualification. The latest candidate
uses fresh actual resource inputs rather than transferring an older optimizer's
results. Its renderer pose, multibone animation and CBPC parent-motion alignment
remain unqualified; dynamic whole-body Havok updates are not implemented.

`physics/audit-contact-triangle-bounds.py` provides an additional continuous
skin-side bound at each saved input vector. Since distance to one convex
capsule is convex, the maximum of its assigned triangle's vertex distances
bounds every barycentric point of that whole triangle. The final sidecar's
maximum is 3.543 node-local units across all 180 sex/state inputs. This is a
conservative undercoverage bound, not a capsule-protrusion bound or a proof for
all unsampled coefficient/weight combinations. Common-world use must account
for node-frame scale. Provider and game acceptance remain separate.
