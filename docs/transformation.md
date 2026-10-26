# Human-to-werewolf morph linkage

Development candidate, 26 October 2026. The intended link is **morph to morph**:
actual applied human coefficients determine the corresponding beast proportions.
A preset supplies coefficients; its name does not select a paired wolf preset.
The native implementation remains a development candidate. This direct linked
mode has not been game-tested; provider behavior, save/load and actual SE/VR
transformations require independent verification.

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

There is no universal calibrated default profile in this candidate.
`recipes/distribution.json` contains illustrative equations, not accepted CBBE or
HIMBO geometry calibration. Author-chosen mappings require visual acceptance at
neutral, individual extremes and combinations. Do not infer a body profile from
sex, matching slider names or a preset name.

## Native developer API

`CLAWDistributionNative.psc` declares:

| Function | Meaning |
|---|---|
| `ConfigureMorphLink(actor, profile, sources[], targets[], gains[], caps[])` | Queue replacement of this reference's explicit mapping |
| `DisableMorphLink(actor)` | Queue return to the retained independent choice |

The four arrays must have identical lengths between 1 and 32. Profile and source
identifiers are bounded to 160 UTF-8 bytes. Sources beginning with `CLAW` are
rejected to prevent feedback from our own beast coefficients. Targets must be
recognized base morphs in the body domain: torso except breast, arm girth, thigh
girth and calf girth. Gains must be finite; caps must be finite in `(0, 1]`.
Duplicate source/target rows and inconsistent caps for one target are rejected.

Only configured targets become nonzero. Unmapped torso traits, ears, muzzle,
head, tail, paws, claws and digitigrade traits stay zero. Female breast linkage
stays zero pending shape qualification. For the same sex, profile and applied
source values, the complete own morph vector is identical regardless of former
beast assignments or actor weight. Clamping and unmapped source differences can
still make different human presets produce the same vector; distinct appearance
for every possible preset is not guaranteed.
No adult target is accepted. No OBody assignment or setting is written.
`GetBodyMorphs` is the provider's actual aggregation API; the implementation never
substitutes a sum of foreign keys or assumes all SKEE contributions add linearly.

The caller supplies the profile explicitly; configuring it does not prove that
the installed human resource matches the profile. This candidate has no automatic
profile discovery or user configuration menu. Those remain release work.

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

Actor co-save record v2 stores the explicit mapping and last captured sources.
The record layout is unchanged; development v2 linked records use these direct
neutral-baseline semantics on refresh, ignoring any retained independent choice.
Version 1 records migrate to independent mode; an old preset name never creates
an opt-in. Actual engine save/load migration has not been accepted from code
inspection. Source snapshots are audit/persistence data, not permission to skip
a fresh source read when SKEE is available.

## Release checks still required

Build and inspect both runtime variants, compile the Papyrus declarations, then
verify real applied source reads and distinct male/female transformations in SE
and VR. Test signed values, zero/unassignment, source changes while wolf, manual
opt-out, suppression, unloaded/reloaded 3D, independent foreign-key readback,
save/load and a refused invalid replacement. Separately qualify the configured
human resource profiles and their numeric ranges. AE receives static/API evidence
where unavailable; no game pass is implied.

## Retained offline references

`scripts/distribution.py` is the original morph-to-morph numerical prototype.
Its illustrated profiles are unqualified; it is not a second live writer.
`scripts/linked_presets.py` and `recipes/linked-presets.json` retain an older
optional exact-preset pairing experiment for historical/reference use. Pairing
is **not** the current transformation goal or a requirement for preset authors.
Its source-observation history bug is fixed: confirmed human unassignment or a
changed source prevents a stale cached pair from returning after provider loss.
Neither offline script is consumed by the native DLL.
