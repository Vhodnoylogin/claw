# Head visibility and torso skinning

Read-only offline diagnostic, 26 October 2026. This does not implement a runtime
head-hiding policy or modify body weights. Its inputs are the pinned published
0.6.2.0 bodies/TRIs and XP32 skeleton, independently of later collar/P1 experiments.

## Two separate problems

The female `head` shape includes breast geometry. Hiding that entire shape removes
the breast surface, which is why the revised VR resource retains it.

Hiding or moving only the Head bone is more selective, but it is not automatically
safe either. Some vertices participating in the published breast morph carry
Head-descendant weights. Their shape name or material does not prevent them from
following that bone. The local inspected VRIK visibility implementation changes
the Head transform; that is different from hiding a complete BSTriShape.

The diagnostic freezes the actual skeleton hierarchy, full skin-to-bone and stored
global-to-skin transforms, including scale. It imposes ten explicitly named states:
rest; a Head local scale of0.01 with local position multiplied by0.25; independent
local rotations of+/-15degrees about each axis; and local Y offsets of+/-20units.
The scale/position state represents the inspected visibility operation. The
rotation/offset states are controlled examples, not actual HMD traces or allowed
motion ranges. Which VRIK branch executes on this setup is unobserved.

Only Head and descendants move. Other original globals are retained exactly,
avoiding numerical reconstruction noise in unaffected joints. The audit reports
raw packed and per-vertex normalized LBS separately; neither is asserted to match
the renderer's weight handling. Female measurements select actual nonzero
BreastSize TRI support and evaluate coefficients0/0.5/1. Male measurements use an
explicit front-thorax ROI with Spine/Clavicle support; this is a comparison region,
not automatic anatomical recognition.

## Actual published female result

| Shape | BreastSize vertices | With Head-descendant weight | Maximum packed head weight | Maximum displacement in scale/position example at BreastSize1 |
|---|---:|---:|---:|---:|
| body | 197 | 0 | 0 | 0 |
| head | 590 | 79 | 0.0948486 | 2.13064 |
| fur_belly | 3484 | 422 | 0.2329102 | 5.94938 |
| fur_chest | 290 | 70 | 0.1579590 | 3.92233 |
| fur_shoulders | 55 | 0 | 0 | 0 |

Distances are model/game units under normalized LBS. The+20local-Y example moves
the affected head/belly/chest support by at most1.89741/4.65863/3.15858units.
This quantifies susceptibility to the declared transform; it is not an observed
in-game crack. In particular, the current pure head-bone approach cannot yet be
called breast-safe, and the five face visibility changes do not close this gate.
The moderate collar/P1 body has different support and needs its own qualification.

## Run and interpret

```powershell
python scripts/audit-vr-head.py --out '<new-external-directory>'
python -m unittest discover -s tests -p test_vr_head.py -v
```

The report records selected/worst vertex IDs, pose matrices, actual input/source/
dependency hashes and per-mode measurements. It refuses nonmatching body/skeleton
inputs and changed files. Output is a new external report directory. It writes no
NIF/TRI, flags, skeleton, game/profile file or configuration.

Five numerical regressions cover ancestry, nonidentity parent scale, partial-head
torso influence, raw-weight rest bias and explicit ROI selection. The final actual
report is `Builds/claw-vr-head-20261026-002/head-motion-report.json` outside Git.
It establishes a concrete weight-policy problem to solve, rather than a working
VR component. Preserve skin/fur joins, four-influence budgets, ordinary poses and
the correct TRI when evaluating a separate correction candidate.
