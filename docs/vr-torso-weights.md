# Optional VR torso weight isolation experiment

`scripts/repair-vr-torso.py` is an offline experiment on the raw, repaired
collar/P1 composition. It is absent from the production build and has no install
switch. It does not replace a skeleton, write physics settings or change which
geometry the game renders.

The problem is an influence relationship, not the shape's name: some breast and
thorax vertices in the shape called `head`, and some overlying fur cards, carry
actual Head/Jaw skin weights. A head-only scale/position visibility operation can
therefore displace breast geometry. The related read-only `audit-vr-head.py`
diagnostic imposes such mathematical examples; it does not qualify the active
VRIK runtime branch or supply an HMD trace.

## Fixed source and correction region

`recipes/vr-torso-weights.json` pins raw NIF
`6792fc6c28c849c7a6279dedf2a7681abd154e7ad1327b4b4826285e1353e33d`, TRI
`18840924604e974d166ab4f489311e66bcbff1852427eb0924b1242909099b15` and read-only
XP32 skeleton `b64b614d06eb854512ef4a9d6b08777fe0f9580f47d495d20db16dabb9fc2dd0`.
The composition has91nodes and25public morph names. Published/installed release
assets are not inputs to this experiment.

The head-shape core is the actual nonzero moderate `CLAWTorsoBreastSize` support
inside `[-25,8,82]..[25,45,108]`, with `y<45`. A two-unit welded-geodesic band
smoothly fades removal outside those seeds, still inside the explicit region.
The55collar anchors and all face vertices remain fixed. This is an explicit
measured region, not automatic anatomy recognition.

Head descendants are identified by actual XP32 ancestry, including Jaw where
weighted. Their mass transfers conservatively into the shape's existing Spine2
palette entry. P1, Clavicle and every other packed weight remain exactly equal.
No new bone reference is allowed. Each half-precision pair retains its exact old
packed sum; an unrepresentable zero Head value can leave a positive residual.
That residual is measured and can reject admission. Normalization is never used
to conceal a packing error.

Fur groups use frozen neutral triangle/barycentric skin bindings from public
`surface_collar.Layer`. Only full-weight cards whose skin-root field is at least
0.5, whose root lies in the explicit region and whose whole group stays below
`faceMinY` are rewritten. These groups receive full Head-descendant removal.
Faded/disabled cards, unselected groups and the vertex-mode ChestBlend remain
unchanged. All affected bindings are measured, including unchanged groups over
changed skin; preserving a root alone cannot prove that its card follows.

## Measurements and admission

The independent declared limits were set before looking at the built result:

- Core head-hide displacement at most0.0001units and at least90%reduction.
- Ordinary/held-out motion change at most0.25normalized or0.325raw-packed units,
  and RMS at most0.05units. Ordinary motion equality is not asserted.
- Pure P1 motion change at most0.005units.
- Collar attachment-offset drift increase at most0.01units.
- Fur transported-root residual and root-distance drift increase at most0.02units.
- Full affected card edge-length change at most1%of its original rest edge length.

All151existing controlled ordinary/held-out/P1 poses and nine imposed head-only
examples are evaluated at BreastSize0,0.5,1 in separate raw-packed and normalized
LBS models, using actual serialized bind/global-to-skin frames and scale. The
head-only examples are the inspected scale0.01/position0.25 operation, six local
rotations of+/-15degrees, and local Y offsets of+/-20units. They are not accepted
safe ranges or runtime observations. Root offsets are transported using the
binding's barycentrically blended joint transforms so natural rotation does not
become a false fixed-world gap.

The written NIF is reopened before measurements. Node graph/transforms/extra
data, geometry, topology, UVs, normals, colors, shape transforms, render metadata,
BODYTRI/extra data, partitions, skin palettes/binds and stored skin frames are
compared with a detached pre-write snapshot. Actual packed weights must equal
the plan exactly; unplanned shapes' weights remain identical. The TRI is copied
byte-for-byte. Inputs, executed local helpers/profiles and PyNifly dependencies
are hashed before work and checked again before a report can succeed.

Writing and file verification do not constitute admission. A measured failure
retains its diagnostic NIF/TRI/report with `REJECTED-measured-do-not-install` and
CLI exit2. A technical failure is `FAILED-unverified-do-not-install`, exit1.
An admitted result is still only an offline candidate. No camera clearance,
physics, collision, appearance, actual animation or game acceptance follows.

## Running

Supply the three pinned binary inputs explicitly and a new external output
directory. Paths and dependencies can also use the configured ignored
`build.local.json` PyNifly location:

```powershell
python scripts/repair-vr-torso.py --body '<raw composition NIF>' `
  --tri '<matching moderate TRI>' --skeleton '<pinned XP32 NIF>' `
  --profile recipes/vr-torso-weights.json `
  --out 'D:/Skyrim VR Modding/Builds/<new external directory>'
python -m unittest discover -s tests -p test_vr_torso_weights.py -v
```

The next decision is based on the rejection/admission measurements, not merely
whether a NIF was written. If conservative Spine2 transfer exceeds the declared
budgets, retain that result and design a separately reviewed torso-palette fit
or selective VR resource with new evidence. Do not weaken the existing limits.

## First measured rejection,26October2026

The first binary run wrote/reopened its NIF successfully and rejected admission.
The immutable local evidence is
`D:/Skyrim VR Modding/Builds/claw-vr-torso-20261026-001/report.json`.
Its diagnostic NIF is
`0732e1569ef9773498a53472b1c68d7a2e36882c4bcf5be381b6f44e2b51b308`;
the TRI retains the input hash. It changed98head,212belly and36chest vertices.
All serialized protection checks passed. Pure P1 motion change remained below
0.00000000000003units; collar anchor drift did not increase.

In the normalized model, the imposed head-hide maximum fell from2.11449to0.012449
on the head core,15.84389to0.016510on changed belly vertices and12.61162to0.016107
on changed chest vertices. Residuals violate the declared0.0001gate. These latter
two selections include whole eligible cards, so they are not interchangeable
with the older published-body morph-support diagnostic's selection.

Ordinary changes reached0.69633/5.07603/4.08610units for head/belly/chest, with RMS
0.10355/0.53149/0.77609. Belly root-distance drift increased1.30623units, and full
card edge-length change reached1.63233belly/1.66728chest. The unchanged admission
budgets reject these changes. Full Head-to-Spine2 transfer is therefore not a
qualified correction even though it substantially reduces the imposed hide
movement. It must not be installed or substituted into the frozen SE test.

A separately retained `revision-2` run verifies a stricter measurement fix:
fur-root residual increase is compared point-by-point, so improvement in an
unrelated group's global maximum cannot conceal a newly worse join. That run
also explicitly reports all151controlled and12combined-P1 changed-motion
samples. It uses the same correction/limits and leaves the first report/NIF
untouched; this is measurement verification, not a new fit or optimization.
