# Post-0.7 abdomen dome candidate

This is unfinished work for the next body-quality release. It is not selected by
the 0.7.0.0 installer or its build recipe, and has not been installed or game-tested.

## Problem and bounded change

The released abdomen field has a full-support plateau across X ±12 and roughly
Z 73–88. Increasing its coefficient mostly translates that plateau forwards.
It can add bulk without establishing a round abdominal centre. A larger input
value alone therefore does not resolve the shape problem.

[The opt-in recipe](../resources/recipes/expressive-abdomen-dome-v1.json) adds a smooth
elliptical dome centred at Z 80.5, with X/Z standard widths 16/18 model units.
Its finite Gaussian profile multiplies the existing compact support, retaining
the existing zero boundaries and face exclusion. The forward/down/lateral
endpoint parameters change from 13/2.2/0.12 to 16/2.7/0.15: central growth rises
while the upper/lower periphery tapers, instead of scaling the whole field.
The same profile bends the long belly coat cards. Existing collar reconciliation
still retains each attachment's original rest offset.

Only `CLAWTorsoBellyRound` records change. Human conversion coefficients, other
named fields, vertex order, topology, materials, UVs, skinning and NIF bytes are
unchanged. The released `expressive-body-v1.json` remains the default. This does
not author new anatomy, physics or different weight endpoints.

## Reproduce and inspect

Configure PyNifly in ignored `build.local.json`. Use the source pipeline's repaired
stage with the recipe's exact baseline hashes and choose new external destinations.
The 0.7 comparison directory may be the verified source-built result or an
extracted release used only as reference evidence; no release binary is tracked.

```powershell
$base = '<fresh-body-build>/repaired/Meshes/Actors/WerewolfBeast/Character Assets'
$released = '<verified-0.7-body-directory>'
$candidate = '<new-external-candidate-dir>'
python src/main/python/build-tools/expressive_body.py --base "$base" --recipe src/main/resources/recipes/expressive-abdomen-dome-v1.json --vectors src/main/resources/recipes/expressive-fixture-vectors-v1.json --out "$candidate"
python src/main/python/build-tools/expressive_verify.py --base "$base" --candidate "$candidate/Meshes/Actors/WerewolfBeast/Character Assets" --out '<new-external-public-reader-report.json>'
python src/main/python/build-tools/abdomen_compare.py --reference "$released" --candidate "$candidate/Meshes/Actors/WerewolfBeast/Character Assets" --out '<new-external-comparison.json>' --plot '<new-external-profile.png>'
python src/main/python/build-tools/expressive_preview.py --candidate "$candidate/Meshes/Actors/WerewolfBeast/Character Assets" --out '<new-external-rest-preview.png>'
python -m unittest discover -s src/test/python/unit -p test_expressive_body.py
```

For a Morphbench check, index the candidate's two NIF/TRI pairs as separate
resources; do not overwrite the installed 0.7 entries. Select the same sex, fixed
weight endpoint and human vector in the CLAW comparison plugin, once with the
released wolf and once with this candidate. Compare the side and front views,
especially Runa/Grom and isolated belly values 0/.25/.5/.75/1. Keep model framing
and orientation equal. The human and conversion matrix must stay unchanged.

## Measurements on the serialized candidate

`abdomen_compare.py` samples Z 64..96 at four-unit intervals. The neutral
triangle-centroid ROI is fixed: |X| < 8, 0 < Y < 40, 58 < Z < 104. It records
skin and coat front envelopes separately. A dome-prominence proxy is the added
front shift at Z 80 minus the mean added shifts at Z 68 and 92.

| Full isolated belly | 0.7 skin proxy | Candidate skin proxy | 0.7 coat proxy | Candidate coat proxy |
| --- | ---: | ---: | ---: | ---: |
| Male | 2.441 | 6.562 | 4.593 | 8.089 |
| Female | 2.808 | 7.063 | 3.143 | 8.618 |

Values are model units, not percentages or an attractiveness score. At Z 80 the
skin-front shift changes 13.729→16.897 male and 13.646→16.825 female. The changing
outline can exceed an individual vertex's Y displacement because downward
movement changes which triangles intersect a fixed plane.

Both sexes passed 54 finite sampled states, including six matrix-fixture states
across the sexes and their frozen-field comparisons. No newly collapsed triangle
or neutral-normal turn appeared. The independent public TRIP reader accepted
both files. All 143 male / 150 female decoded fields outside the abdomen target
remain exact against 0.7. Four NIF endpoint byte streams remain exact.

The full-endpoint maximum collar rest-offset residual is 0.000427 male and
0.000576 female units. The female donor already has a nonzero collar attachment
offset; residual is measured against that offset, not a demand to weld it to zero.

These are rest-space geometric checks. Opaque coat rendering, numeric envelope
prominence and a preserved join do not establish alpha-texture appearance,
perceived roundness, posed skinning, global intersection safety or game acceptance.
Review in Morphbench, then verify exact installed resources in the paired SE
scene before choosing this recipe for a release. Preserve the 0.7 release cut.
