# Functional anatomy fields v4

V4 preserves the v1–v3 recipes and adds separate `CLAWArmBiceps` and
`CLAWArmTriceps` public channels. `CLAWArmGirth` now describes soft arm mass.
The two new channels affect opposite radial sides of the upper arm, with zero
support at the authored deltoid and forearm measurement regions. They do not
use the shoulder field as a substitute for upper-arm muscles. Both sexes use
the same continuous anatomical supports and their own serialized geometry.

The arm fields preserve arm length. Soft mass supplies broad radial padding
with partial radial equalization, rather than the muscle lobe function. The
current matrix partitions actual muscle and fat sources into these channels;
coefficient and function evaluation remains in the shared native evaluator.
This is an implemented distinction between input mechanisms, not visual acceptance.

The bounded hip correction suppresses BellyRound on thigh-weighted skin, using
a smooth transition between 0.02 and 0.65 total thigh weight. It also retains
the already-authored upper abdominal dome, hip crease and upper-thigh forward
transition. The full upper abdominal forward amplitude remains 18 units; the
correction is not a uniform reduction of the maximum belly. V4 coat cards follow
their frozen skin-triangle roots for the belly field too.

**The abdomen/thigh intersection defect remains incomplete.** The earlier
normal/collapse checks did not detect nonadjacent surface crossings. The new
`body_clearance.py` diagnostic measures triangle/triangle distance and proper
edge/face piercings on the body skin after actual serialized LBS. It excludes
adjacent triangles, including neutral UV-weld equivalents. Its frozen masks
cover the abdomen and thigh-weighted surface, not the entire body or coat.
In the captured owner stance, the first frozen correction still has proper
crossings. Source generation or a passed normal test must not be presented as
collision safety. Further aesthetic/proportion iteration was stopped at the
owner's request; the remaining technical counts belong in the build checkpoint.

The actual pose comes from the retained 1 November observer capture of Grom
and Runa: pelvis, both thighs, both calves and Spine0/1/2. Globals are transformed
from world space by the inverse actor-root transform. For the real XP32
right-side aliases, the observed standard-name child's world transform times
inverse local transform reconstructs its weighted parent exactly. Other bones
retain pinned rest-local relations beneath the observed ancestors; this is not
a full live skeleton capture. Separate stress cases apply local-X hip/knee
edits at ±10, ±25 and ±45 degrees. The right controls intentionally use the
donor's `[LThg]` and `[LClf]` alias names to move the full descendant chain.

The new distance diagnostic requires NumPy, SciPy and Numba (measured environment:
2.5.3, 1.18.1 and 0.68.0). Its narrow phase tests all AABB-overlapping nonadjacent
pairs for proper piercings. AABB distance bounds safely prune exact minimum-distance
work. A zero clearance can also mean touching/coplanarity; that is reported separately
from proper piercing. No penetration-volume, renderer, collision-solver or whole-body
guarantee is inferred.

The fresh pipeline selects v4 by default and retains explicit v1/v2/v3 routes:

```powershell
python src/main/python/build-tools/fresh-body-pipeline.py --out '<new-build>' --expressive-version v4
```

Its current native fixture vectors live in
`src/test/resources/geometry/expressive-fixture-vectors-v4.json`. The female TRI
has 31 global morph names and the male 30. The separate current-TRI P1 profile
uses the exact v4 TRI while preserving the v3 profile and old artifacts. Final
`runtime/` carriers include named-morph and nominal motion bounds; their scope
and assumptions remain in their separate reports. They do not solve self-contact.
