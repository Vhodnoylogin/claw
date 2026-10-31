# Human-to-werewolf morph linkage

Development candidate, updated 30 October 2026. The link is **morph to morph**:
actual applied human coefficients determine the corresponding beast proportions.
A preset supplies coefficients; its name does not select a paired wolf preset.
The native implementation remains a development candidate. Actual SE checks have
exercised six actors of both sexes, human/beast roundtrips, source preservation,
mixed-state save/load and two actors created as wolves. The current runtime set
passed 117 core checks and 33 fresh-world born-wolf checks, with normal exits in
both sessions. Final textured visual acceptance remains pending. See the
[bounded verification summary](verification-20261030.md).
These SE results do not establish VR or other executable-version compatibility.

### Contrast trial 6 — coefficient-only candidate

The 30 October manual measurements found a nearly disconnected HIMBO pecs signal
and weak visible bellies. Trial 6
raises belly response by 1.75 within the existing 0..1 bound, sets HIMBO
PecsMass/PecsSize chest gains to 0.3/0.45. The observed muscular actor's chest
changes from 0.000950 to 0.3; the observed
male/female heavy belly values change from 0.455/0.573 to 0.796/1.0.

This changes configuration only: the repaired meshes, morph names, caps, native
DLL, source ownership and save format stay unchanged. Static skin-and-fur checks
on the six measured source vectors found no new triangles below 10% of their
current area for the chosen coefficients. A 0.4 chest candidate and larger torso
caps failed that screen and were rejected. This screen does not establish textured
appearance or all possible morph combinations. Actual SE trial 6 values match the
mapping within 5.43e-8; the owner's final visual acceptance remains separate.

The opposing Muscle-to-waist rule is retained: independent human geometry shows
that muscle widens this region while TorsoWaistSize narrows it. Their cancellation
is therefore meaningful, rather than a reason to force a narrow muscular waist.

Slim limb reductions still reach the neutral limb shape because this catalog has
positive growth targets and a nonnegative composition contract. Independent
head/ear/tail traits and more natural belly, breast and muscle shapes remain
post-release work. Automatic linkage is not a claim of identical proportions.

## Explicit calibrated mapping

Different human body resources give their sliders different geometry and ranges.
Configure an explicit versioned profile for the actual CBBE/3BA/HIMBO resource in
use. A profile consists of source morph, CLAW target morph, gain and target cap.
Multiple sources may contribute to one target with the same cap:

```
beast[target] = clamp(sum(appliedHuman[source] * gain), 0, 1) * cap
```

Source values are signed, finite **already applied SKEE coefficients**. They are
not XML percentages or low/high endpoints. Combine signed contributions before
clamping. The native conversion applies no actor weight factor: the human
provider has already performed its weight interpolation. Linked mode starts from
the complete neutral public morph vector for the actor's sex, then replaces only
the configured targets. It does not read actor weight or select, load or
interpolate a beast preset. No CLAW preset XML, including a neutral preset, is
required for a linked actor. An absent or invalid independent catalog does not
block this mode.

`src/main/resources/profiles/MorphLinks.xml` contains measured candidate conversions
for CBBE2.0.3, 3BA2.48 and HIMBO5.8. The calibrator reads actual human OSD
deformations and wolf TRI deformations, projects them onto frozen anatomical
regions, and compares logical combinations against a single-target baseline.
Its explicit final skin selection includes the separated head. Exact duplicate
physical responses with the same skin frame are counted once, preserving the
regional metric when a split duplicates seam vertices.
Multiple human fields can drive a target and one field can drive several targets.
Signs come from actual geometry: increasing human `Arms`, for example, narrows
the measured limb rather than widening it. Signed contributions combine before
the final target clamp. Unsupported opposed directions and residuals are reported.
This is an explicit numerical objective, not proof of the best artistic result.

The shipped file has no universal default. Bind the actual body resource through
`ConfigureMorphFamily` or an explicit setup-level `Defaults` declaration, described
in [the family catalog](../resources/profiles/README.md). Automatic adoption
applies only to newly discovered states after successful source capture. It does
not overwrite existing, restored, suppressed or manually chosen states. Preset
names and actor sex alone never infer the installed body family. Combined
appearance still needs visual acceptance at neutral, extremes and combinations.
The older equations in `src/main/resources/recipes/distribution.json` remain illustrative references.

## Native developer API

`CLAWDistributionNative.psc` declares:

| Function | Meaning |
|---|---|
| `ConfigureMorphLink(actor, profile, sources[], targets[], gains[], caps[])` | Queue replacement of this reference's explicit mapping |
| `GetMorphFamilies(female)` | Enumerate the validated typed resource-family IDs for this sex |
| `ConfigureMorphFamily(actor, profileId)` | Capture current source values and bind a loaded resource-family mapping |
| `GetHumanWeight(actor)` / `GetBeastWeight(actor)` | Last actually observed normalized NPC weight in each form; `-1` means unknown |
| `DisableMorphLink(actor)` | Queue return to the retained independent choice |

The four arrays must have identical lengths between 1 and 128. Profile and source
identifiers are bounded to 160 UTF-8 bytes. Sources beginning with `CLAW` are
rejected to prevent feedback from our own beast coefficients. Targets must be
recognized base morphs in the body domain: torso, arm girth, thigh girth and calf
girth. `CLAWTorsoBreastSize` is allowed only for females. Gains must be finite;
caps must be finite in `(0, 1]`.
Duplicate source/target rows and inconsistent caps for one target are rejected.

Only configured targets become nonzero. Unmapped torso traits, ears, muzzle,
head, tail, paws, claws and digitigrade traits stay zero. Female breast linkage
requires an explicit matching resource family; the generated female profiles
include measured breast fields. For the same sex, profile and applied
source values, the complete own morph vector is identical regardless of former
beast assignments or actor weight. Clamping and unmapped source differences can
still make different human presets produce the same vector; distinct appearance
for every possible preset is not guaranteed.
No adult target is accepted. No OBody assignment or setting is written.
`GetBodyMorphs` is the provider's actual aggregation API; the implementation never
substitutes a sum of foreign keys or assumes all SKEE contributions add linearly.

The caller or setup declares the profile explicitly; configuring it does not
prove that the installed human resource matches the profile. There is no automatic
body-resource discovery or user configuration menu.

## Shared actor weight and separate geometry interpolation

For an ordinary same-reference race transformation, human and beast use the same
NPC weight property. CLAW does not call `SetWeight`, change a base NPC, or choose
a second wolf weight. A human weight of 30 therefore selects wolf `u=0.30`.
The distinct body resources interpolate as
`P0 + u*(P1-P0) + sum(effectiveMorph*absoluteTRIdelta)`. Named TRI fields remain
absolute displacements and their already effective SKEE coefficients receive no
second weight multiplication. Equal named morph vectors can consequently produce
different neutral body proportions at different weights, as intended.

The native coordinator records an observed weight independently in each form for
diagnostics. An actor first seen as a beast has no invented human observation.
These cached observations do not override the actual current weight used by the
physics fit. A separate-reference transformation, or another mod deliberately
changing the NPC property, needs its own integration; it is not covered by the
same-reference guarantee.

## One writer and lifecycle

The existing native Distribution coordinator remains the **only writer** and
continues using `CLAW.Distribution`. It reads actual source coefficients through
SKEE's `GetBodyMorphs` in its existing main-thread tasks. It reads again on every
loaded refresh in either form, including after an OBody application event. It
therefore handles a human coefficient changing while the actor is already a wolf.
A returned zero is a legitimate absent/zero coefficient; it does not revive a
previous nonzero snapshot. SKEE unavailability remains an explicit provider error.

Configuration first validates and captures all finite source values before
replacing an existing valid profile. Failed reads retain the old complete
snapshot, but no beast application is attempted using it after a current read
fails. Human and suppressed cleanup still runs if a source value is nonfinite;
its own cleanup is not dependent on successful conversion. Unloaded actors defer
writes. Existing actor pins, runtime identity checks, epoch, request serials and
current-race/3D checks govern every operation.

Every API Boolean means queue admission. Wait for `GetStatus` to leave pending
and inspect `GetLastError` before issuing the next request; existing coalescing
can supersede an earlier unfinished request. `GetOwnMorph` retains its verified
cache semantics and is not an independent rendering oracle. `GetAssigned`
returns an empty string in linked mode: there is no assigned beast preset.

Normal `AssignPreset` disables linkage, expressing a manual independent choice.
`ClearOwn` suppresses the actor while retaining the mapping. A valid explicit
configuration resumes linkage; disabling a mapping does not clear suppression.
An older independent choice may remain stored solely for `DisableMorphLink` to
resume the optional independent route; it never contributes to linked output.
That independent route still requires its catalog and uses actor weight once.
Human return clears only this
companion's own beast contributions; foreign keys and human provider state remain
unchanged. A later beast transformation resumes the same identity and traits.

Actor co-save v4 stores the mapping, captured sources and optional actual weight
observations. Readers preserve v1/v2/v3: v2 retains its original 32-row budget;
v3/v4 support 128 rows. Version1 records migrate to independent mode; an old
preset name never creates an opt-in. Development linked records use the direct
neutral-baseline semantics on refresh, ignoring a retained independent choice.
Current-state engine save/load has been exercised in SE; migration from every
historical state format has not. Source/weight
observations are diagnostic persistence data, not permission to skip current
provider or NPC reads.

## Release checks still required

Build and inspect both runtime variants, compile the Papyrus declarations, then
verify real applied source reads and distinct male/female transformations in SE
and VR. Test signed values, zero/unassignment, source changes while wolf, manual
opt-out, suppression, unloaded/reloaded 3D, independent foreign-key readback,
save/load and a refused invalid replacement. Separately qualify the configured
human resource profiles and their numeric ranges. AE receives static/API evidence
where unavailable; no game pass is implied.

## Retained offline references

`src/main/python/build-tools/distribution.py` is the original morph-to-morph numerical prototype.
Its illustrated profiles are unqualified; it is not a second live writer.
`src/main/python/build-tools/linked_presets.py` and `src/main/resources/recipes/linked-presets.json` retain an older
optional exact-preset pairing experiment for historical/reference use. Pairing
is **not** the current transformation goal or a requirement for preset authors.
Its source-observation history bug is fixed: confirmed human unassignment or a
changed source prevents a stale cached pair from returning after provider loss.
Neither offline script is consumed by the native DLL.
