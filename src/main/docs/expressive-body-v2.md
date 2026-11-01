# Opposed body fields v2: one measured candidate

[The opt-in recipe](../resources/recipes/expressive-body-v2.json) increases the
contrast between authored lean and growth endpoints on the same accepted neutral
meshes. It is not selected by the released installer, installed or game-tested.
The v1 recipe and the earlier [abdomen-dome candidate](abdomen-dome.md) remain
unchanged. Human matrices, new morph names, physics, VR and breast redesign are
outside this bounded change.

## Parameter choice

A direct 1.30 multiplication of existing fields produced the desired measured
contrast but also new normal turns at compact-support boundaries. That trial was
rejected. The chosen recipe retains the continuous field implementation and
widens its transitions before accepting larger amplitudes:

| Region | v1 | v2 |
|---|---|---|
| Arm lean / growth | -0.32 / 0.44 | -0.416 / 0.572 |
| Arm radial fade | 14 | 19 |
| Thigh lean / growth | -0.30 / 0.34 | -0.495 / 0.442 |
| Thigh radial / centre fade | 14 / 6 | 20 / 9 |
| Torso lean X/Y | -0.24 / -0.22 | -0.312 / -0.286 |
| Torso growth X/Y | 0.32 / 0.30 | 0.416 / 0.39 |
| Torso width fade | 14 | 20 |
| Belly forward / down / lateral | 13 / 2.2 / 0.12 | 18 / 2.7 / 0.15 |

The abdomen uses the previously developed elliptical dome, centre Z=80.5 and
X/Z widths 16/18, instead of the flat central plateau. Increasing the thigh's
centre fade protects the medial transition; the stronger lean endpoint then
recovers the required contrast without increasing that transition's growth.
The shoulder field shares the arm radial support, so its transition also changes;
its amplitude remains 0.16. Calf, chest and dedicated breast parameters remain
unchanged. Only eight existing body-field names change; no new name is added.

## What the metric means

[`expressive_contrast.py`](../python/build-tools/expressive_contrast.py) applies
the actual decoded TRI fields to the accepted NIF vertices. Regions use frozen
neutral triangle-centroid masks and fixed planes: upper arm X33, right thigh Z62,
torso Z84 and central abdomen Z80. Skin, coat-only and skin-plus-coat envelopes
are reported separately. A missing coat section remains missing; the thigh has
no separate coat-card cross-section at this plane.

For arm, thigh and torso the primary measurement is effective envelope diameter
`2*sqrt(convexHullArea/pi)`: contrast is growth-at-1 minus lean-at-1. The abdomen
uses forward silhouette at belly=1 minus neutral. The acceptance ratio is v2
contrast divided by v1 contrast, at least 1.25 in each sex/region. This measures
larger separation of endpoints, not a claim that the maximum body is 25% wider.

| Sex / region | v1 minimum → maximum | v2 minimum → maximum | Contrast increase |
|---|---:|---:|---:|
| Male arm | 12.944 → 24.976 | 11.593 → 27.124 | 29.08% |
| Female arm | 12.636 → 24.285 | 11.329 → 26.376 | 29.17% |
| Male thigh | 15.622 → 28.935 | 13.191 → 29.991 | 26.20% |
| Female thigh | 15.379 → 28.353 | 12.981 → 29.369 | 26.30% |
| Male torso | 26.419 → 38.849 | 24.883 → 41.077 | 30.29% |
| Female torso | 28.849 → 38.572 | 27.675 → 40.365 | 30.52% |
| Male abdomen front | 11.780 → 27.750 | 11.780 → 32.785 | 31.53% |
| Female abdomen front | 8.821 → 22.467 | 8.821 → 29.069 | 48.38% |

Values are model units. Arm/thigh/torso rows use the combined outer envelope;
abdomen rows use forward Y. Frozen masks, alpha-ignorant coat cards and convex
hulls are geometric proxies, not true occupied area, volume or appearance with
the actual fur textures. They do not establish attractiveness or posed safety.

## Serialized and independent checks

The four NIF endpoints remain byte-identical, retaining topology, UVs, materials,
weights and bind transforms. Against v1, 92 male / 101 female protected decoded
shape-fields remain exact. The public PyNifly reader accepts both TRIs and the
global name inventory remains 28 male / 29 female. All original non-body records
remain exact against the repaired input.

The existing authoring audit covers 51 candidate states per sex: neutral, quarter
steps of each of 11 fields, three combined states and three human-fixture vectors.
Three additional repaired-baseline fixture comparisons are retained separately.
No new collapsed triangle or neutral-normal turn appears. Protected face-region
movement is zero. The original collar attachment offset is preserved within
0.000622 model units after quantization; the female original offset is not zero
and is not falsely treated as a welded seam.

Independent Morphbench 0.8.5 public `open`, `set_sliders`, `deformed`, `strain_set`
and file-visibility calls checked 72 geometry states across v1/v2 and both sexes.
All 16 male / 15 female shapes are native-file-visible. Candidate vertex differences
from the direct serialized calculation stay below 0.0001 model units, within the
public TRIP reader's documented subthreshold filtering.

**Strain remains a tradeoff, not a passed universal threshold.** Under all growth
fields at 1, maximum edge strain rises 1.400→1.627 male and 1.390→1.612 female;
Morphbench's worst per-shape P99 rises 1.189→1.401 and 1.009→1.175 respectively.
Both v1 and v2 exceed the diagnostic 0.25 threshold. The existing authoring gate
rejects new normal turns/collapses but sets no hard strain ceiling. Do not turn
the absence of flips into a claim of safe UV appearance, animation or contacts.

## Reproduce

Build the pinned donor stages first; use their repaired directory as input and
the verified v1 expressive result as comparison. Choose new output destinations:

```powershell
python src/main/python/build-tools/expressive_body.py --base '<fresh-build>/repaired/Meshes/Actors/WerewolfBeast/Character Assets' --recipe src/main/resources/recipes/expressive-body-v2.json --vectors src/main/resources/recipes/expressive-fixture-vectors-v1.json --out '<new-candidate-directory>'
python src/main/python/build-tools/expressive_verify.py --base '<fresh-build>/repaired/Meshes/Actors/WerewolfBeast/Character Assets' --candidate '<candidate>/Meshes/Actors/WerewolfBeast/Character Assets' --out '<new-public-reader-report.json>'
python src/main/python/build-tools/expressive_contrast.py --reference '<verified-v1>/Meshes/Actors/WerewolfBeast/Character Assets' --candidate '<candidate>/Meshes/Actors/WerewolfBeast/Character Assets' --out '<new-contrast-report.json>'
python -m unittest discover -s src/test/python/unit -p test_expressive_contrast.py
```

Keep generated NIF/TRI, reports, temporary probe scripts and previews outside Git. Inspect
the textured v1/v2 endpoints and the same human fixture values in Morphbench
before a separate installed-game comparison. Dedicated breast naturalness and
more complex poses remain later work; this candidate does not qualify a release.
