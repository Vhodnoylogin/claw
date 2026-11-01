# Local arm anatomy and bounded secondary traits

Tags: CLAW, anatomy, calibration, matrices

This development candidate separates soft arm mass from two local muscle fields:
`CLAWArmBiceps` for the upper-arm front and `CLAWArmTriceps` for its rear.
`CLAWArmGirth` remains soft/neutral-size bulk. The public catalog now has 30 male
and 31 female fields, while linked targets remain generic model-provided names.
Nothing in this change updates a running game or an existing saved matrix.

## Response-normalized arm mappings

The geometry audit measured each unit field on the actual v4 body skin. The
front/back upper-arm ROIs use right-arm model X 28..40 and radial direction
Y greater than 0.25 or less than -0.25; the deltoid ROI uses X 16..25.

| Unit target, intended region | Male mean radial movement | Female mean radial movement |
|---|---:|---:|
| Biceps, front | 3.092951 | 3.331405 |
| Triceps, rear | 2.613949 | 2.577757 |
| ShoulderGirth, deltoid | 1.185115 | 1.200941 |

Both new muscle fields have exactly zero unit support in the measured deltoid
and forearm regions. Cross-lobe mean response is below 0.009. These are frozen
unposed model-space measurements, not a claim of rendered anatomy or skinning.
The measured responses and authored source budgets are pinned in
[the calibration input](../resources/profiles/anatomy-v4-calibration.json).

Each new muscle/edited shoulder gain is an authored desired mean radial movement
per unit human source divided by the measured target response for its sex/region.
Thus the target geometry sets the coefficient scale. The desired source budgets
are artistic choices; this is not a fresh human-resource least-squares fit.
The external measurement JSON and its hash are retained in the calibration input.

HIMBO Biceps/Brachio feed only the front field, BicepsBack feeds only the rear,
and broad Muscle feeds both. Actual Delts inputs feed the shoulder field with
modest regional budgets. ArmsFore no longer inflates the whole arm; it supplies
the small declared claw analogy. ArmsSide, BodyMass, Chubby and the existing
signed neutral-size/lean relation remain distinct soft-size inputs. CBBE/3BA
MuscleArms and MuscleMoreArms feed both local fields; ChubbyArms and generic
Arms size remain soft-size inputs. Generic back/chest contributions to shoulder
bulk are reduced; the direct shoulder-width source remains explicit.

Offline native evaluation of actual retained live inputs gives:

| Fixture | Soft ArmGirth | Biceps | Triceps | ShoulderGirth |
|---|---:|---:|---:|---:|
| Kedr / MMuscular | 0 | 0.442943 | 0.239102 | 0.265797 |
| Mira / FMuscular | 0.294316 | 0.600347 | 0.620695 | 0.423002 |
| Grom / MHeavy | 0.254726 | 0 | 0 | 0.029533 |
| Runa / FHeavy | 0.799703 | 0 | 0 | 0 |

These preserve actual SKEE inputs, trait availability and raw NPC weights. They
are expected v4 coefficients, not observations from an installed v4 game. The
tests require soft-only fixtures to have zero local muscle, front/rear controls
to remain independent, and actual muscular fixtures to avoid immediate cap 1.
Combined-field geometry and rendered acceptance remain separate checks.

## Ears, tail and claws

All six retained humans have the same captured height ratio, about 1.03. Height
alone therefore cannot differentiate their ears, tail or claws by changing gains.
The candidate retains height and adds explicit secondary analogies:

- Positive jaw/chin breadth adds modest ear size and outward tilt. These are
  face-proportion projections, not measurements of human ears.
- Real soft/muscle body-mass sources add tail radial bulk through `TailFluff`.
  This target is not a hair-length or physics-stiffness control.
- Real forearm/arm or lower-limb strength/size sources add small claw-length
  contributions. These are strength analogies, not measured human nails.

HIMBO uses its actual Chubby/BodyMass/ArmsSide/Muscle and forearm/calf channels;
CBBE/3BA use their actual Chubby/Muscle/ForearmSize channels. Vanilla adds only a
centered explicit weight-to-tail-bulk term and the shared face inputs. It invents
no missing body morph names or muscle observation. Tail posture and paw size
remain neutral by default. The six typed human sources are unchanged.

## Capacity, persistence and adoption

The shared kernel now accepts 256 structural edges and 64 active targets. Its
`max_rules`/`max_targets` exports let the WASM adapter allocate the same bounded
buffers. The 28-byte rule ABI and ordered arithmetic are unchanged. Default
profiles use 137 HIMBO, 116 CBBE/3BA, and 41 Vanilla edges.

Co-save v8 retains the v7 byte layout and increases rule/source capacity to 256
with a 262144-byte record bound. Readers keep historical 32/128 rule bounds and
byte limits for v1..v7. Existing saved rules remain authoritative until explicit
family rebind. The legacy parallel-array `ConfigureMorphLink` API retains its
128-row transport bound; file families and the shared evaluator use 256. No saved
v7 source changes meaning and no body source is multiplied by weight again.
