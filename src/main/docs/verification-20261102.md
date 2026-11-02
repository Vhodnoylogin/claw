# CLAW 0.8 technical verification - 2 November 2026

This record concerns the runtime whose native source matches
`267f38933e61f6552146e81ecc49915ae25b60e5` and the unchanged final archive:

- Universal DLL SHA-256: `6b7f73173300d63eaa4e3497e0288ef9ec4efe2df88f5512f1eb6c4c9e9eb0be`.
- Runtime ZIP SHA-256: `5589014dafeb8ae6561c59480995b3f51e3dbf13fd66f0f6dd0d8325026cc234`.
- Actual engine: Skyrim SE 1.7.104 / SKSE 2.3.1, official RaceMenu/SKEE and OBody NG.

Later documentation and portable test-fixture changes do not change that runtime.
No Morphbench acceptance is required or claimed by this game-mod record.

## Vanilla male and female bodies

Run `20261102-104207-b24951` (physical start 13) passed the complete technical
lifecycle for six human actors: transformation, explicit model refresh, a real
save and load with six distinct saved references resolved through native FormID
and VM witnesses after load, and return to the original human races. The loose-
file source audit found no enabled replacement body/hand/foot winners; the
corresponding model paths were verified in the pinned official BSA. The two
Vanilla matrices used the captured actor weight and available human face/stature
inputs. Vanilla body deformation does not require human TRI morphs.

The five checkpoints were the human baseline, wolves, refreshed wolves, loaded
wolves and returned humans. Their exact verification counts were:

| Check | Count |
| --- | ---: |
| Own-target checks across all five checkpoints | 915 |
| Wolf-phase float32 comparisons with the shared native evaluator | 549 |
| Human-phase zero/structural-absence checks | 366 |
| Preserved human aggregate values | 1,695 |
| Preserved human contribution-key sets | 1,695 |
| Available human trait/value pairs | 180 |

The 549 wolf comparisons include 333 checks that a zero contribution is also
structurally absent; these are overlapping checks, not additional comparisons.
All checks passed. The game exited through its own menu with code 0 and no
forced stop. The original 0.7.1 installation, profile and supporting state were
restored exactly; all 16,186 original physical game files were SHA-identical,
with no extras or missing files.

Final summary SHA-256:
`261c85c82f50fb4a3cc96acd15fde11aa4f0bdd858e13e7f5060174efe2d795c`.
Independent final review SHA-256:
`ec2ebda95580eab608db852e3e3c49df7fa909f883538b395a29b8ed994fad0e`.
Raw evidence remains outside Git under
`Builds/claw-mechanics-20261101/game-13/result-evidence/`.

## BHUNP and HIMBO

Run `20261102-143104-724077` (physical start 17) completed all five mechanical
checkpoints for three HIMBO males and three BHUNP females: their own human
baselines, wolf forms, refreshed wolf forms, loaded wolf forms and returned
humans. All six transformations, refreshes, save/load reference resolutions and
returns passed. This establishes the measured mechanisms; the later process
termination was abnormal, so the overall run remains failed.

| Check | Count |
| --- | ---: |
| Own-target checks across all five checkpoints | 915 |
| Wolf-phase float32 comparisons with the shared native evaluator | 549 |
| Human-phase zero/structural-absence checks | 366 |
| Preserved human aggregate values | 1,620 |
| Preserved human contribution-key sets | 1,620 |
| Available human trait/value pairs | 180 |

The 549 wolf comparisons include 285 structural-absence checks; these overlap
the comparisons and are not an additional count. The two human checkpoints
account for the other 366 own-target checks. In particular, 915 is not a count
of wolf-phase evaluator comparisons.

The required source proof independently confirmed three actual BHUNP preset
assignments and 47 ordinary body keys per female, including the intended
nonzero Low/High controls and their OBody contributions. The 22 generated
NeverNude resource winners were checked against the reviewed BHUNP resources.
With each actor's measured weight and traits held fixed, zeroing only ordinary
body inputs changed wolf body outputs. This excludes a weight-only fallback
from being mistaken for BHUNP morph support. It does not test every BHUNP preset
or establish artistic quality.

After the completed checks and a finish request, the process exited with
`0xC0000005`. The recorded termination is `abnormal_exit`, with
`ownQuitRequest=false`; the planned menu-quit request was not attempted because
the menu flow was unavailable and `crosshairRelease=false`. This was not a
confirmed normal menu quit or a forced game stop. No captured second-chance
exception stack establishes the cause or attributes it to CLAW. The facts remain
`mechanicalCoveragePassed=true` and `overallRunPassed=false`.

Native and external restoration completed: the original 0.7.1 runtime, all 11
source-profile files, manager INI, host and four optional custody folders were
restored, and all 2,075 baseline inputs matched. The physical-game baseline also
matched without extras or missing files. The four separately installed test
dependencies remained installed and disabled.

Final summary SHA-256:
`6915f919114c37b8db655025edf093521848f8d5c0b27403452decfa2929755c`.
Required BHUNP source-proof SHA-256:
`279aeccdb8294b018506dad7d5437c37ea019880cca2f5a918548749f6de917e`.
Independent source-proof review SHA-256:
`cfd51f301ba9834fc99ff0f855b2017631c0e072d2d693c34b228d0be39e1275`.
Independent final technical-coverage/restoration review SHA-256:
`dec45d15e39e1e450ea1178eb10b6b3c0b481726079a847186af7f05daf40dd4`.
That review preserves the abnormal termination and failed overall-run result.
Raw evidence remains outside Git under
`Builds/claw-mechanics-20261101/game-17/result-evidence/`.

## Retained unsuccessful attempts

The preceding Vanilla run `20261102-101810-418fe2` (start 12) passed six
transformations and initial wolf-value checks. A typed-read deadline guard
blocked later collection before the native call. Its full lifecycle result stays
incomplete; the new complete run does not replace its report. That game also
exited normally through its menu with code 0 and its original environment was
restored. The new run narrowed only the request budget from 30 to 29 seconds;
the game DLL and runtime resources were unchanged.

BHUNP start 14 stopped before actor creation because the tool rejected repeated
names in OBody's blacklisted catalog. Separate tool qualification 15 verified
that catalog correction; it was not a mod-acceptance run. Start 16 reached six
real human preset assignments but stopped before transformation when an external
inline-result decoder exceeded its supported JSON depth. Both incomplete
attempts remain retained. Start 17 used the existing file-backed result route
through a scenario-only request change, with the same game DLL and resources.

## Limits

These are technical mechanism checks, not acceptance of artistic shape quality,
self-intersection quality, rendered tint accuracy, physics or the first-person
VR body. SE execution does not establish AE or VR engine acceptance. The earlier
HIMBO/3BA and born-werewolf evidence remains separately dated in the repository;
it does not replace these new body-family checks. Generated saves, logs, DLLs,
archives and human body assets are not committed to this source repository.
