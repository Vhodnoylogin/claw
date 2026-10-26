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
