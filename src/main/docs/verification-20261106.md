# 6 November: mixed-origin coat lifecycle

The alpha repair uses the universal minimal game DLL SHA256
`6e2998f2b5049ef804895810f2904f463433f65cd24cb6803ec43674288291fc`.
Its compiled source is the isolated `86d76a3` tree, including the captured-stature
correction from `c209d006`. The matching code was transferred to the existing
development branch as `60e2679` and `65aefd6`; released `main` is unchanged.
No fitted-physics model or altered RaceMenu library is included.

## Reproduced defect and correction

Q10, run `20261106-164049-08f525`, reproduced loss of a born-female coat. The first
failed predicate observed BODY property alpha changing from `0.92416644`
(`0x3f6c962c`) to `1` (`0x3f800000`). The observation does not identify its writer.
The old complete-state comparison treated this opacity change as lost ownership;
rollback consequently left the changed BODY private material while restoring other
surfaces. Q10's operator baseline failed; its successful tooling bootstrap is not
coat acceptance.

Coat ownership now separates finite live property alpha from coat content.
Material alpha, flags, material/property/guard identities, tint and texture checks
remain strict. Rollback carries current opacity on a private donor-property and
material copy where necessary, without changing the retained shared donor.
The engine setup callback is followed by property/material identity checks before
the opacity write; a later replacement is preserved on either callback outcome.

Eight native CTests passed, including the actual alpha pair and failure/foreign
replacement cases. An actual-header probe rejects that pair with the old lease
comparison and accepts it with the new comparison. These checks use fake engine
objects; real shader behavior is covered only by the following game trial.

## Q11 game evidence

Run `20261106-172028-514f48` used Skyrim SE, the dedicated CLAW profile at
1920×1080, HIMBO/classic UNP, 20 enabled mods and 21 plugins. Physics remained
disabled. Its born female and human-origin male were independently created and
frozen; only the male received the human refresh and race-change sequence.

All 13 prelude commands and eight operator phases passed, with 124 unique
commands/events within the declared limit of 152:

- Automatic choices: born female Valley Black, transformed male Himalayan.
- Independent manual overrides: male Black; female Black, then Timber.
- Model refresh preserved both requested and applied choices.
- One owned ESS/SKSE pair was saved and loaded; both current actor remaps and
  new world/model generations were verified.
- Clearing the female override restored exactly Valley Black while the male
  retained its explicit Black choice.

Fourteen fresh, chunked material audits were independently decoded and checked.
Every audit covered all 12 managed surfaces, actual diffuse paths **and bound
resources**, private ownership/guards, neutral tint and finite alpha. Maximum
sample age was 1217 ms within the unchanged 2-second limit. Actual excluded
surface multisets contained 3 or 8 entries; preservation was compared only within
the same observed root and world. Refresh retained the same roots; loading
created the separately witnessed new generations. No first-yield event occurred.
The trial did not directly record a new numerical fade pair.

The game ended through normal menu shutdown. Independent review verified 121
restored targets and backups, all 5874 registered pin rows, packet/archive files,
owned process termination, original profile/INI/FHD and RootBuilder restoration.
The exact reservation was then released. The formal packet projects one tooling
bootstrap; the operator checks above have separate raw evidence and review.

Technical review SHA256:
`19bf2d7c4ecf33d56b088a638f0d5503caa0dca4e106f89da18a8553e12a8292`.
Restoration review SHA256:
`056999471e93afc84a06e956c849f7953d12ff26f83030707d5bc7dc9cb159ac`.

## Saved source and deterministic choices

A separate bounded parser checked the actual owned ESS/SKSE hashes, actor/base/VM
identities and saved colour/automatic records. The born female had no CCLR record
or hair choice and retained `natural / valley-black`; the male retained human hair
RGB `[48,35,33]` and `dark-brown / himalayan`. Both saved namespace/identity seeds
agreed with the retained independent Python selector. Manual CCPT overrides
coexisted with those cached automatic choices in the save.

The actual compiled serialization sections were compared with the retained
decoder's layout before analysis. Twenty-three retained parser tests and six Q11
negative cases passed. This is independent Python arithmetic, not execution of
the native codec/selector. Saved desired choices alone do not prove a shader or
absence of earlier human history; the creation/prelude/audit evidence supplies
the separate live association.

Source analysis SHA256:
`1b9618d4b1b39e27ef7aab3a1c2ef86292450bf27d687593b6bd63d8db6086fc`.

This qualifies the bounded SE composition and observed patterns. It does not
establish all 34 patterns in-game, AE/VR behavior, visual quality, physics or
collision fit. The separate stature check below completes the explicit SE
reference-scale transfer check.

## Captured human stature: low/high game contrast

The same minimal DLL was used for the low run `20261106-203611-39301c` and
the high run `20261106-212754-bcce02`. These are different disposable actors in
different native sessions. The base actor, race, sex, HIMBO family, build, all
61 ordinary source/key maps, weight and available head traits were independently
matched before comparing the two runs.

`SetScale` takes a reference multiplier, whereas `GetScale` includes the NPC/race
size. The high run measured that factor instead of assuming those API units
were identical. Its final reference multiplier of `1` restored both human
`GetScale` and the cached human height to `1.0299999714`.

| Measured value | Low run | High run |
|---|---:|---:|
| Human height / combined scale | 0.7724999785 | 1.2874999046 |
| Combined wolf scale | 0.8474999666 | 1.4125000238 |
| `CLAWHeadEarSize` | 0 | 0.4312498569 |
| `CLAWTailLength` | 0 | 0.5749998093 |
| `CLAWArmClawLong` | 0 | 0.3593748808 |
| `CLAWLegClawLong` | 0 | 0.3593748808 |

After transformation, the captured input remained the human height rather than
the wolf race's combined scale. All 31 independent SKEE target values matched
the shared compiled evaluator: maximum errors were `2.965e-11` at low stature
and `2.6514e-10` at high stature. The high run also checked the four featured
cached target values, completed human return and original-scale restoration,
and cleared CLAW's wolf keys on the human model.

The low caller stopped after finding its own incorrect absolute-scale assertion;
its immutable overall result remains failed, with no high-wolf or original-scale
cleanup acceptance. Its completed low-human/low-wolf evidence remains usable.
The corrected high run completed all six phases and 163 commands, then exited
normally with native and child code 0. Both environments were restored and their
reservations settled separately. These results establish the bounded mechanical
transfer, not aesthetic quality, physics or AE/VR behavior.

High-run technical review SHA256:
`7dccdb134e73e575fd6b915d253197f55c2670cc2c9d811a44a914c9632bd181`.
High-run restoration SHA256:
`1afdabe15836ea3a8040adcc32715e728a369ce321e905889830a3821a0756ff`.

## CBPC motion: still unconfirmed

Motion06 (`20261106-222912-5421d5`) and Motion07
(`20261106-231605-6922ea`) used the unchanged minimal DLL and the dedicated
22-mod CLAW profile with the separately installed CBPC motion adapter. A frozen
control and an AI-enabled, movement-held transformed female were sampled in
three stationary windows of 20 observations: active, selected bones stopped,
and selected bones restarted. Both reference and model-root transforms stayed
stationary; every window met the fixed cadence limits.

Motion07 added exactly one documented per-actor
`CBPCPluginScript.RefreshActorBounceSettings` call after AI activation and before
the baseline. It did not change coefficients, reload global configuration or
modify CBPC. Ear rotation was present but not selectively suppressed by the
stop request; tail and breast transforms remained constant. Thus neither run
establishes CBPC influence. Void callbacks establish receipt only; the observer
samples a main-thread task without a synchronized physics/render phase or a
readback of CBPC's actual node/container ownership.

Both native sessions ended normally and were collected/restored. Further fixture
variations are deferred until the instrumentation can distinguish provider
simulation from animation. No fitted-physics candidate is installed or activated
by these runs, and no solver, collision or VR acceptance is claimed.

## Whole-body contact candidate: offline scope

The separate opt-in coarse model extends support beyond the older ear/tail/P1
regions. Its recipe declares actual skeleton attachment nodes and sex masks;
the fitter resolves every selected skin influence through the measured skeleton
ancestry, applies full normalized rest skinning and keeps complete mixed-weight
triangles at region seams. It does not alter body meshes or TRI fields.

The 128-slot r1 allocation assigns all 58,563 selected triangles per sex exactly
once, with 120 active male and 128 active female capsules. Its measured support
uses 30 male / 31 female nonzero morph dependencies, including limb and claw
fields absent from the earlier regional model. A separate native build passed
254 numerical cases and 32,512 slot outputs, with maximum error `9.024e-13`.
The two retained low/high male game vectors are included as explicit offline
fixtures; their game runs remain distinct.

Morphbench's existing public Physics API imported the separately evaluated
capsule snapshot for each of eight matching mesh/vector cases. All 984 active
contacts resolved; radii were finite and positive, exported text was unchanged,
and maximum local/world coordinate errors were `3.55e-15` / `2.84e-14` against
the actual loaded skeleton frames. Four standalone inspection pages and complete
capsule-coordinate exports are retained outside Git. This verifies display and
export coordinates, not simulation or runtime attachment.

Increasing only the head and upper-spine partition counts reduced whole-union
unsigned surface P95 mismatch by 10–16% and sampled maxima by 19–47% in the eight
compared forms. The remaining sampled maximum is still **14.51 game units**;
contact fit is not accepted. Unsigned mismatch does not uniformly imply outward
protrusion on this open skin/fur surface. A cheap pelvis comparison of five
existing partition methods found no alternative improving every tested state,
so no additional full model was generated from that comparison.

The frozen r1 manifest is `ad0689dfab90dfb659a7c87c797d86d6dfcb9ea1877b18f17b979855930037c8`.
Morphbench placement review is
`18bd50550cf6579183a211224419d78deeb7a2323f45633817af06b4f775ac4b`.
The model and generated header remain external build artifacts. They are not
installed, provider-qualified or part of a released archive.
