# Human resource-family conversion profiles

`MorphLinks.xml` is own measured conversion data for 3BA2.48, CBBE2.0.3 and
HIMBO5.8. Install it as `SKSE/Plugins/CLAW/MorphLinks.xml` alongside the native
companion. It contains no human assets, independent wolf presets or OBody choices.
Each profile identifies a human body-resource version, sex and calibration.

The development catalog also includes the separate female
`CLAW.UNP.4.6.Weight1` profile for classic **UNP Female Body Renewal 4.6**.
That original archive supplies fixed `_0`/`_1` meshes but no BodySlide OSP/OSD
or runtime TRI. This profile therefore reuses the female Vanilla weight rules
and generic available FaceGen/stature inputs exactly; it does not read invented
UNP sliders, imply BHUNP/UUNP compatibility or claim a new geometric calibration.
Skin/hair source capture remains the existing independent appearance mechanism.
The installer offers UNP as a manual female choice: shared `femalebody` paths
and the archive's optional `SGEyebrows.esp` are not unique body markers.
No human UNP assets are bundled. An installed classic-UNP game check is pending;
source/kernel tests and other families' game records do not establish it.

The source tools are `scripts/calibrate-morph-links.py` and
`scripts/morph_calibration.py`. Supply explicit human OSP/NIF/shape/set, target
NIF/TRI and PyNifly inputs. Source OSD fields are read through public PyNifly.
The report pins the exact sources and compares logical target combinations
against the best single-target regional projection. This is numerical anatomy
calibration; combined appearance and the actual game provider require acceptance.
The final split uses explicit `--wolf-shapes body,head,head_CLAWHead`. Exact
coordinate/weight/target-response/bind-frame duplicates are counted once, so
duplicating a seam while splitting the head does not reweight the anatomical
regions. Coincident points with different binds or responses remain distinct.

Bind an actor explicitly with
`CLAWDistributionNative.ConfigureMorphFamily(actor, profileId)` and inspect its
normal asynchronous status. `GetMorphFamilies(female)` exposes available IDs.
Binding names describe resources, not human preset names. Any ordinary preset
for the declared resource supplies its own coefficients. Gains may be negative:
positive source `Arms`, for example, reduces rather than increases human girth.

The shipped catalog has no automatic defaults. A setup explicitly using HIMBO5.8
for male bodies and 3BA2.48 for female bodies can add this child immediately
under `MorphLinkProfiles`:

```xml
<Defaults male="CLAW.HIMBO.5.8.Geometry1" female="CLAW.3BA.2.48.Geometry1"/>
```

This is the setup author's resource declaration. It is not body-family inference
from sex. A missing or wrong-sex family rejects the catalog. Native adoption only
targets new automatically discovered states, after successful source capture;
existing/restored/suppressed/manual states are preserved. Without the declaration,
the explicit per-actor API remains available.

Female profiles explicitly drive `CLAWTorsoBreastSize`. The current development
candidate adds five vanilla FaceGen sources and human stature to every family;
see [the exact source and mapping contract](../../docs/human-head-traits.md).
These are explicit `$human.*` engine inputs, not SKEE body morph names. Muzzle
rows use captured human face records. Head/ear size, tail length and claw length
use a documented artistic stature analogy centered at height ratio 1. Missing
human history remains unavailable with neutral arithmetic and a diagnostic.
V4 adds face-breadth ear size/tilt and real body/forearm source analogies for tail
radial bulk and modest claw variation. Tail posture and paw controls remain
neutral by default. Local Biceps/Triceps separate muscle from soft ArmGirth;
[the v4 calibration input](anatomy-v4-calibration.json) and
[mapping rationale](../../docs/anatomy-v4.md) record measured target responses,
authored source budgets and the 256-edge shared capacity.
A shape with no opposed wolf deformation
cannot reproduce both human directions; such clipping is recorded, not hidden
by an invented neutral offset.

The interpolation of `_0`/`_1` geometry is separate from named TRI morphs.
Applied human morph coefficients are never multiplied by actor weight again.
