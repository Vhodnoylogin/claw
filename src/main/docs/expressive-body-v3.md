# Expressive bodies v3

The development recipe [expressive-body-v3.json](../resources/recipes/expressive-body-v3.json)
retains the stronger, wider-transition limb, torso and elliptical abdomen fields
from v2, replaces the female `CLAWTorsoBreastSize` field and isolates the two
muzzle fields from the torso. V1 and v2 remain
unchanged, reproducible historical recipes. No public slider is added by v3.

The breast field uses broad continuous chest support, including the sternum and
axillary transition. It adds lateral mass and moves the lower lobe chiefly down
the torso. Forward growth fades at the existing projecting apex. At full value,
decoded head displacements reach 2.500 lateral, 1.445 forward and 4.797 downward
model units. Skin and coat use frozen triangle bindings; the body/head repair
preserves the donor attachment offset. Zero BreastSize retains the original,
nonzero donor breasts: the field does not define breast absence.

The neutral NIFs, topology, UVs, materials and weights are unchanged in
`expressive/`. Existing records outside the authored body, breast and two muzzle
fields remain exact. The original muzzle fields follow Head/Jaw weights that
extend into the breast/neck. A continuous forward mask now fixes points at
Y<=44, fades from 44 to 56 and retains the original displacement at Y>=56. The
same rest-frame mask applies to skin, mouth and coat; the actual projecting jaw
retains the original field. HeadSize and ear records remain protected.

The authoring audit covers 64 male and 71 female states, including three
repaired-baseline fixture comparisons per sex and quarter-step, paired and
body-growth-combined muzzle states. Both muzzle fields produce exactly zero
decoded motion on 1,780 male / 1,833 female protected head-shape chest vertices.
Female samples add quarter-step breast values, breast with all growth, breast
with all lean and breast with chest growth. No new normal reversal or collapse
was found; body fields keep the protected face region fixed. Maximum decoded donor collar
offset error stays below 0.000622 units. The female donor's original gap is
preserved and is not represented as a welded seam.

The v1-to-v3 outer-envelope contrast ratios remain those of v2: arm 1.291/1.292,
thigh 1.262/1.263, torso 1.303/1.305 and abdomen 1.315/1.484 (male/female).
These are frozen-plane, alpha-ignorant geometric proxies. They do not establish
appearance, posed safety, contact safety or artistic acceptance. Female full
breast plus full growth has maximum absolute edge strain 1.616; body-only v2
was 1.612. Absence of triangle flips is not a passed strain or UV-quality gate.

The retained live human handoff showed Lada `BreastsSmall=0.4`, Mira
`Breasts=0.15` and Runa `Breasts=0.28`; prior outputs were 0, 0.540 and saturated
1. The corresponding breast-target gains are reduced uniformly to 55% for the
new field, preserving their relative signs and cancellation. The resulting Mira
and Runa values are 0.297 and 0.554. On a frozen breast ROI, convex-hull envelope
growth is approximately 5.1% and 9.9% respectively, compared with 4.1% for the old
full endpoint. This hull encloses empty space and is not anatomical volume.

## Rebuild and derived runtime carriers

```powershell
python src/main/python/build-tools/fresh-body-pipeline.py --out '<new-external-build>' --expressive-version v3
```

The fresh builder reads pinned original donors, rebuilds legacy and repaired
stages, authors v3 and independently reads the serialized TRI. It then authors
the current P1 breast rig from this exact v3 TRI, using the existing donor XP32
skeleton as read-only input. The profile pins the actual 53 collar anchors and
29 morph names; it does not load an old moderate TRI or copied weight blob. An explicit
`--expressive-version v1` retains the strict historical comparison; it does not
silently substitute the new recipe.

Stronger morph combinations can leave the old serialized shape spheres. The
explicit `morph-runtime/` stage therefore copies the TRI and derives new NIF carriers
using the public Morphbench `bounds` command with `--shrink --margin 1.01`.
It checks that all bytes outside each shape's 16-byte sphere remain exact. The
two weight endpoints are copied only after verifying their source bytes match.
The final `runtime/` stage adds conservative spheres for the nominal small-motion
adapter envelope. Use that final output for packaging; retain `expressive/` as
frozen authoring evidence. Named-morph spheres cover coefficients 0..1. The motion
extension covers five joint corrections, each at most 0.5 units per translation
axis and 0.0105 radians per Euler axis, with lever-arm and packed-weight margins.
It assumes unit scale/amplitude, no external driver and no additional collision
or animation displacement. Solver constraint overshoot still requires game tracing.

For a separately composed or rigged carrier, rerun the same derivation against
its actual NIFs and the v3 TRI:

```powershell
python src/main/python/build-tools/runtime_bounds.py --source '<six-current-body-files>' --out '<new-derived-directory>'
```

The P1 rig preserves rest geometry, current TRI, UVs and material data while
adding the existing bilateral P1 bones and transferring bounded Spine2 weights.
Independent serialized readback covers 151 controlled poses at current
BreastSize 0, 0.5 and 1; normalized ordinary-skinning error is 0.001208 against
the existing 0.005 gate. This does not establish common skin/fur motion, visually
closed axilla seams or runtime physics quality.
