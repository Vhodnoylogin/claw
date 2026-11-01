# Expressive body candidate, 31 October 2026

This retains the original candidate's authoring measurements and replay results.
The independently released Morphbench tool now lives in
[claw-morphbench-plugin](https://github.com/Vhodnoylogin/claw-morphbench-plugin).
Reference bodies needed by this finite-field replay are external/ignored inputs;
rebuilding their full donor pipeline in the reorganized tree has separately
passed through all six 0.7 body destinations, as described in
[rebuild.md](rebuild.md). This does not add another game run.

This offline candidate adds independently authored lean arms, thighs, calves and
torso to the immutable 30 October technical core. It replaces the existing arm,
thigh, calf, torso, belly, shoulder and chest growth fields with bounded smooth
rest-frame fields. Zero remains neutral, and every effective coefficient remains
in `0..1`. No negative TRI coefficient, weight-endpoint trick or extrapolation
of the frozen fields supplies the new range.

The four new public names are `CLAWArmLean`, `CLAWLegThighLean`,
`CLAWLegCalfLean` and `CLAWTorsoLean`. The coordinated native/preview matrix
implements the opposed human projections; see [the matrix contract](matrix-contract.md).
The two NIF weight endpoints remain equal per sex. Named coefficients are never
multiplied by actor weight a second time.

## Rebuild

Configure PyNifly in ignored `build.local.json`, as in [rebuild.md](rebuild.md).
Run from this repository into a new external directory:

```powershell
python src/main/python/build-tools/expressive_body.py --out <new-external-directory> --vectors src/main/resources/recipes/expressive-fixture-vectors-v1.json
python src/main/python/build-tools/expressive_verify.py --candidate "<new-external-directory>/Meshes/Actors/WerewolfBeast/Character Assets" --out <new-external-verification.json>
python src/main/python/build-tools/expressive_preview.py --candidate "<new-external-directory>/Meshes/Actors/WerewolfBeast/Character Assets" --out <new-external-image.png>
python -m unittest discover -s src/test/python/unit -p test_expressive_body.py
```

The recipe is [expressive-body-v1.json](../resources/recipes/expressive-body-v1.json).
It binds all six frozen NIF/TRI inputs by SHA-256, rejects source drift, live
mod-manager/game destinations and existing output directories, and writes six
resources plus a decoded-geometry report. The four NIFs are exact byte copies:
topology, vertex order, UV coordinates, normals, materials, partitions, XP32
skin weights, binds, bounds and BODYTRI references are preserved. Only named TRI
records change. Frozen release files are never written. No plugin, DLL, texture,
installation or game action is part of this builder.

The fixed vector fixture records the six final `Geometry1` matrix outputs on
31 October. These are derived conversion results, not a new game capture.
Keeping them as explicit input makes the same finite combination audit replayable
without an installed human mod or a running game. An explicitly supplied
`--vectors` file is hashed and retained in the report. Omitting that argument
still builds identical geometry, but omits the six-fixture combination checks.

## Authored supports and coat

Arms grow transversely around a measured bent arm axis, with separate broad
upper-arm and forearm peaks. Lean reduces those cross-sections without shortening
the bones. Thighs and calves use separate axes and smooth joint fades. Torso
width and depth change around the existing body axis. The belly field distributes
mass forward, laterally and slightly down over the abdomen. The chest field
provides a smooth pectoral mass field; the existing breast-size target is unchanged.

Skin uses continuous spatial supports shared by coincident vertices. The head
shape contains chest as well as the actual head; smooth front cutoffs exclude
the face rather than treating the entire shape as a skull. The final serialized
fields move none of the 6,787 male / 6,788 female head vertices ahead of Y49.
The frozen collar attachment solver preserves each original rest offset at its
body-triangle attachment, including the female collar which has no exact
coincident boundary pairs at the strict `1e-4` join tolerance.

Limb, torso, shoulder and chest coat cards translate with frozen skin-triangle
root followers. Each connected card retains its internal geometry for those
fields. ChestBlend follows per vertex. Root projection uses the candidate
triangles incident on the nearest twelve skin vertices and exact local
point/triangle distance; it is explicitly a local projection rather than a
globally exact nearest-triangle claim. All related coat layers are included.

The belly field deliberately bends the long downward coat cards along the
abdomen support. Rigid root translation alone leaves upper female belly coat
tips fixed because their roots are above the abdomen. The decoded field and its
finite combinations pass the same orientation checks after this bending.

## Measured result

The final six resources were built twice byte-identically (r7/r8 external
evidence). Both sexes passed eleven authored fields independently at
`.25/.5/.75/1`, all lean endpoints, all growth endpoints, the mixed half state,
and the six fixed matrix vectors. Every sampled shape had zero neutral-normal
turns and zero new collapsed triangles. Equal NIF endpoints make actor weights
`0/.5/1` exactly the same geometry for each vector.

The separate PyNifly public TRIP reader accepted both outputs and agreed with
the complete independent decoder across 437,828 male / 440,090 female serialized
offset rows, including its explicitly accounted subthreshold omissions. The
83 male / 92 female records outside these eleven authored names remain exact.

The section figures below are changes in convex-hull section area from the same
neutral skin. They are alpha-ignorant, model-space geometric proxies rather than
true concave section areas or visible volume. Arm sections intersect X33 and
measure transverse Y/Z; thighs intersect Z62; calves Z31; waist Z84. Neutral
triangle-centroid masks stay fixed while a field changes geometry.

| Isolated endpoint | Male skin area change | Female skin area change |
| --- | ---: | ---: |
| Arm lean | -57.3% | -57.3% |
| Arm growth | +118.1% | +117.9% |
| Thigh lean | -48.7% | -48.4% |
| Thigh growth | +75.8% | +75.2% |
| Calf lean | -48.2% | -48.2% |
| Calf growth | +90.6% | +90.6% |
| Torso lean | -38.5% | -39.2% |
| Torso growth | +66.6% | +68.3% |

The same real-pair vectors now produce these skin changes. This table uses the
new matrix output, not newly observed runtime state:

| Fixture | Arm | Thigh | Calf | Waist |
| --- | ---: | ---: | ---: | ---: |
| Iney / MThin | -39.0% | -36.8% | -30.9% | -31.8% |
| Kedr / MMuscular | +149.2% | +22.1% | +39.5% | +1.3% |
| Grom / MHeavy | +35.3% | +37.5% | +15.1% | +86.4% |
| Lada / FThin | -37.2% | -33.4% | -26.2% | -15.5% |
| Mira / FMuscular | +152.6% | +30.7% | +42.3% | -8.9% |
| Runa / FHeavy | +91.6% | +54.4% | +47.9% | +94.8% |

At the isolated belly endpoint, Z84 / X±10 skin-front movement is +15.195 male
and +15.605 female model units. Coat-front movement is +17.035 male and +17.277
female. The frozen female coat endpoint was zero at this section; its skin
endpoint was +8.592. These values use the complete triangles selected by the
frozen neutral mask; they must not be confused with live world lengths.

Coat response is smaller than skin response in some lean regions. Upper-arm coat
section area changes -16.1% male / -20.8% female at full lean, versus -57.3% skin.
Female waist coat area changes -14.8% at full torso lean, versus -39.2% skin.
Long cards retain their length in the root-following fields. There are no coat
triangles at the selected thigh/calf sections; those measurements are `null`,
not invented zeros.

The maximum serialized collar rest-offset residual across candidate states is
0.000217 male / 0.000557 female model units. The smallest sampled triangle-area
ratio to its own neutral is 0.1895 male / 0.1756 female. Maximum edge-length
increase is about 140% / 139%; UV coordinates are byte-preserved, but large
geometric texture stretching remains a visual concern. Unchanged skin weights
were also checked finite and nonnegative. No claim of new normal/UV recalculation
is made; the runtime morph-normal behavior requires a rendered engine check.

The same fixed vectors on the frozen fields produced body-normal turns in both
muscular and heavy fixtures (male 68/59, female 60/74). The final candidate has
zero in these samples. Those static normal-direction indicators are not a full
global intersection test.

## Remaining acceptance

The orthographic preview is actual triangle rendering of the candidate, with
opaque coat cards and no alpha textures. It makes the endpoint contrast
inspectable, but does not establish texture quality, posed skinning, lighting,
animation, collisions or owner artistic acceptance. Skin/coat collisions and
global self-intersections have not been certified. No desired human/wolf
dimensionless response interval has been validated against the human meshes.
The endpoint strength therefore remains an authored candidate, not a proven
anatomical calibration.

The exact installed candidate now passed SE core105 and born27 mechanism checks;
all four lean outputs were active on both thin actors. See the separate
[runtime verification](verification-20261031.md). Those numeric and lifecycle
checks do not establish textured appearance.

Next: inspect the textured paired scene and choose proportions. Head/ear/tail/claw traits,
coat colour, breast redesign, physics and VR remain separate later work.

The post-0.7 [abdomen dome candidate](abdomen-dome.md) is a separate opt-in recipe
and profile measurement tool. It does not change this released default.
