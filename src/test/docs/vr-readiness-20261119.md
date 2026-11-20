# VR readiness verification — 19 November 2026

Tags: CLAW, VR, verification

This records bounded development evidence, not general VR or rendered-body acceptance.
Original failed results remain authoritative; source/unit checks and runtime coverage are separate.

## Query and tooling boundaries

Commit `954811a00505b25fb4a8c55b7f40019659e39e9b` fixes the actual SKSEVR Query encoding:
SKSEVR 2.0.12 reports runtime `0x010400F1`, which CommonLib exposes as `1.4.15.1`.
The last nibble is the VR subtype; the executable/canonical runtime is `1.4.15.0`.
Only that exact Query encoding is normalized; unsupported versions, subtypes and editor calls still refuse.
The earlier Query candidate DLL was
`0171479474c39558e76e754d3db94c6239cb239a17f91b6f20af367f8d656e1c`.
Its offline actual-export probes did not invoke SKSE Load or establish game/body acceptance.

The private DevBench 1.36 DLL is
`39a85b56b0b11d286cdbd7020438284b317450ac12018ef696e924be10932573`.
Its CommonLib TypeInfo repair preserves whole-script metadata decoding and uses only bit0 for tagged object arrays.
VR17 and VR18 each completed all15 prerequisite steps:10 passed and5 metadata observations.
This qualifies those observed prerequisites with this private provider, not the stock provider or three-action body route.

The reviewed mapped-backing adapter uses the owned process handle, complete Toolhelp inventories,
MEM_IMAGE allocation bases, mapped NT names and opened backing-file identities/hashes; no expected-source/VFS fallback.
VR17 qualified four DLLs; VR18 qualified five reads of the same four expected DLLs.
This is bracketed mapped-name/opened-file evidence, not an atomic memory image, historical load-byte proof,
or a claim of liveness at the instant of return. Caller custody, original deadlines and commit guards remain mandatory.

## Initial-world candidate and actual VR18

The reviewed initial-world source was delivered in `da08918c7e9a1cb6140d124eebb1567b42c2f310`.
The build recorded HEAD `b2f361cb1ea338341e4a5e37cd49fc61f3489379` plus the approved production delta;
the compiled/test archives match that build. Documentation added afterward is not a compiled-source change.
Candidate DLL: `fc5c9564c08035061b5d796db4b64cbaa5b2873b67bba4febb495708c8d4886c` (3304448 bytes).
Matching PDB: `e337d0a145d86ba31e201b6532643cffb5ccacef1992b948e4107de62fc309f8` (38981632 bytes).
The retained build passed22 CTests and12 offline actual Query-export cases.

| Archived source at build | SHA256 |
| --- | --- |
| `src/main/cpp/include/claw/WorldStartPolicy.h` | `8c5078bb2c8fe3419f9f515b2206648f379a3d1e976073129590c14d2adfbf6e` |
| `src/main/cpp/src/Plugin.cpp` | `0d130e3b8c7d58dfb4df5a3cf56cccabc95fdf2fac05c302ce9f26b23aa3fc32` |
| `src/test/cpp/WorldStartPolicyTests.cpp` | `fe6462e0ff06be561a5c8a05901e20d970c7e37c7bcaf17be8ef73e402bc5f78` |

VR18 run `20261119-113913-ada828` logged matching-observation activation at11:39:55.423, epoch1,
player14/cell0A01A5C6. Initial human status5, empty error and `CLAW.VanillaMale.Weight1` were observed.
SetWeight(0) on ActorBase7 and SetRace(wolf) on player14 both returned known typed completions;
engine readback then observed wolf race and base weight0. The next CLAW status was4.
The provider reported `body=missing; head=missing; claws=missing; fur_tailtip=missing` near SetRace.
That is an availability refusal; the underlying asset/binding cause remains unproven.
No human return or carrier classification followed; the result remains failed, with two actions and no unknown mutation.

The initial-world activation is qualified only for this observed owned new-game boundary.
Save/load and failed-load disarming/refusal paths remain source/unit-test policy, not runtime-qualified paths.
VR17's110 known status0 reads and separate final15ms timeout remain preserved in its failed result.
VR18 preserved all99 snapshots,231 cold pins and30 staged VFS observations; its temporary profile was archived/removed.
The exact retained SkyrimVR handle exited0; the executor returned1. Aggregate termination fields remain null.
Cumulative factual accounting after VR18:42 actual Skyrim starts,10 actual VR starts,15 VR platform attempts.

## Bounded model observation in VR20

Packet19 was refused during admission, before any execution intent or game start:
two wrapper pins included an extra `bytes` field that the unchanged strict validator rejects.
Packet20 corrects that metadata and adds complete-freeze validation controls; no runtime guard was weakened.

Run `20261119-122313-478b43` retains the original status4 failure.
Eleven complete status/error pairs span27.078 seconds inside the original30-second interval;
the diagnostic stops partial at that deadline without starting a twelfth pair.
One fresh geometry audit reports29 human-named surfaces while the actor race is wolf.
Two later typed-empty caches remain unknown. Six dual-view snapshots each report all18
requested role/marker nodes not found. These observations do not establish rendered pixels,
root-pointer equivalence or permanently absent geometry.

Only the original two setters ran; there was no human return or unknown mutation.
The retained game exited0;99 snapshot preimages,231 cold pins and30 VFS entries restored.
Accounting after VR20 is43 actual starts,11 actual VR starts and16 platform attempts.
The shipped VR transformation scripts also prepare beast state, camera, controls, FX and animation
around `SetRace`; this primitive fixture does not qualify that complete route.
A separately declared mesh-rebuild probe can test rebuild sensitivity, without changing
CLAW's model requirement or substituting for a normal-transformation check.

## Single mesh-rebuild probe in VR22

Packet21 remained offline: review found that its private post-command unloaded-state
reader needed exact integer checks for the handle and load generation. Packet22
adds those checks without changing the production observer or general command guards.
Its36 current controls passed before execution; historical364 controls belong to
the separately retained packet20 proof and are not added to that count.

Run `20261119-130412-7ea102` retains the original status4 failure. Three native
commands completed knowingly: weight, race and exactly one `QueueNiNodeUpdate`.
Two fresh `IsOnMount=false` observations guarded the queued update. Native
completion does not prove that the scene graph was rebuilt.

One complete pre-Queue status/error pair and eight complete post-Queue pairs
reported4. A further read exhausted its remaining31ms budget; that read timeout
does not replace the original model-availability failure. Three typed-empty audit
caches remain unknown; all108 requested nodes across six dual-view snapshots
were not found. Eight post-Queue identity observations reported loaded3D with the
same exact typed actor identity. None establishes rendered wolf geometry.

No human return, unknown mutation or Queue retry occurred. The retained game
exited0, and independent replay verified99 snapshot preimages,231 cold pins,
30 staged VFS entries and the archived/removed temporary profile. Accounting is
44 actual Skyrim starts,12 VR starts and17 VR platform attempts. Further work
must investigate the complete shipped transformation route, rather than repeat
the same rebuild or weaken required-model availability.

## Fresh Realm quest state in VR25

Run `20261119-162431-7701ae` completed all 15 startup and self-test observations.
The read-only C00 probe verified the initial owned human player, then read the
quest at stage 0. The player was outside the Companions faction. The typed
answers were `IsStarting=true`, `IsRunning=false`, `IsStopped=false`, and
`IsStopping=false`. This disproves the scenario's assumption of a stopped C00
at that point in this fixture. The controller stopped before calling
`GetIndexFromRadiantQuest`. The actual initialized property values, including
the original race and first-transformation flag, remain unverified.

No body or quest mutation was issued, and no transformation was attempted.
The game exited with code 0; 99 snapshot preimages, 231 cold files and 29 cold
VFS winners were independently checked, and the temporary profile was archived
and removed. Accounting at this boundary is 49 actual Skyrim starts, 14 actual
VR starts and 19 VR platform attempts. Continue by establishing a suitable
natural fixture or source-supported lifecycle observation before another
transformation diagnostic. No quest setter or weaker body requirement follows
from this result.

## Natural initializer and CR01 lookup in VR26

The shipped C00 stage-0 fragment calls `SetUpCompanions`. It waits 60 seconds
outside menu mode before finishing initialization and setting stage 1.
The earlier probes read C00 before 54 seconds of total process lifetime.

Run `20261119-171248-516f18` retained the original fresh Realm fixture and used
one bounded read-only wait. It recorded 16 complete groups at starting stage 0.
The first stage-1 observation arrived 32.43 seconds after the first probe read.
Two consecutive groups confirmed running stage 1, outside menu mode and the
Companions faction. A single typed `GetIndexFromRadiantQuest(CR01)` returned
integer 1, and a final same-owner observation confirmed the same state.
The 15 self-tests and 20 four-module observations passed.

This confirms natural initialization and one bound property in this test.
The fixture did not issue a body or quest command, acquire the Beast Form power,
or attempt transformation. A future normal-spell diagnostic can use the
observed stage-1 state as its precondition while keeping model acceptance
and the transformation pipeline as separate runtime observations.

The retained game handle exited with code 0. Independent replay verified 99
restored snapshots, 231 cold files, 29 original and 30 staged VFS winners, and
archive and removal of the temporary profile. Accounting at this boundary is
51 Skyrim starts, 15 VR starts and 20 VR platform attempts.

## Normal spell pipeline and model refusal in VR27

Run `20261119-173455-e84bf1` observed fresh C00 stage 1 and exact CR01 index 1
in the same owned process. The original guards then admitted the declared
ActorBase weight-0 assignment and one vanilla Beast Form cast. Both commands
returned known completions. No quest commands or inverse actor mutation were
sent by the test.

The first two pipeline samples showed human race, quest stage 0 and CLAW
status 5. The observed werewolf race appeared at stage 1 with loaded 3D.
The tracking quest advanced to stage 10, confirming that the normal spell
pipeline reached StartTracking. Both werewolf samples returned CLAW status 4
with the required roles body, head, claws and fur_tailtip missing. The
unchanged model gate refused and ended the scenario. This records the roles
missing from CLAW's selected model observation at those points. Rendered wolf
geometry and first-person body behavior remain unverified.

The retained handle exited normally. Independent replay verified restoration
of 99 snapshots, 231 cold files, 29 original and 30 staged VFS winners, and
archive and removal of the temporary profile. Accounting advanced to 53 Skyrim
starts, 16 VR starts and 21 VR platform attempts.

## Early normal-route geometry audit in VR28

Run `20261119-175652-947fba` used the same normal spell and retained the first
status 4. One additional read-only audit finished within its two-second cap.
At 8.94 seconds after the Cast request, the selected graph's inventory held
only `pBloodStrings03`, `pBloodBigSpray03` and `pBloodDrops10`. All 18 requested
names were absent in each explicit observer view before and after the audit.
The observations bound the same actor, cell and loaded-3D identity. These
observations cannot classify a later graph or its rendered body.

The three geometries match names in the vanilla BloodSprayWerewolfEat01
resource. The audit does not expose their actual attachment or lifetime.
At that time the main and visual effects were still within their nominal
10- and 15-second durations. CLAW already requests automatic refreshes
on a two-second scan, as well as from load, race and node events. If more
evidence is needed, the next diagnostic should distinguish the post-effect
graph within the original window without issuing another refresh.

The retained game exited normally. Independent verification checked 99
restored snapshots, 231 cold files, 29 original and 30 staged VFS winners
and the temporary profile archive and removal. Accounting advances to
55 Skyrim starts, 17 VR starts and 22 VR platform attempts.

## Late normal-route geometry audit in VR29

Run `20261119-182358-8fe5e7` completed 15 self-tests, observed the natural
C00 initializer and issued one normal cast under the original body guards.
The original early audit again saw only three blood-effect geometries.
Both typed transformation effects were inactive in two same-owner groups
at Cast +16.004 and +18.004 seconds. The wolf race and stage 10 remained,
with the same model-availability status 4 and all four roles missing.

The single late audit returned a fresh sample 2 (32 ms old). It contained
the same three blood-effect geometries, and both explicit views still lacked
all 18 names in both brackets. This rules out a problem limited to the
observed active lifetime of those two effects. The observations do not show
where the engine attached the wolf skin, whether a biped or alternate route
holds it, or what reached the headset. The written state and the retained
tool return still carry the original status 4 refusal. No forced refresh
or extra transformation occurred.

The game returned normally. Independent verification checked 99 restored
snapshots, 231 cold files, 29 original and 30 staged VFS winners and normal
cleanup of the temporary profile. Accounting is now 57 Skyrim starts,
18 VR starts and 23 VR platform attempts. The next diagnostic should
separate root and biped routes without changing model selection.

## Retained evidence

External paths below are relative to `D:/Skyrim VR Modding/Builds/`; no runtime payload is stored in this record.

- Query proof: `claw-vr-query-20261119/{build-receipt.json,query-export-proof.json}`.
- New build/source/probes: `claw-vr-initial-world-20261119/{RESULT.json,build-receipt.json,query-export-proof.json,source/}`.
- Backing contract: `claw-loaded-module-backing-20261119/revision02/{FREEZE.json,README.md}`.
- Original VR17: `claw-vr-readiness-20261119/current-case-17-preparation/runtime/runs/20261119-105632-fb9bb5/`.
- Original VR18: `claw-vr-readiness-20261119/current-case-18-preparation/runtime/runs/20261119-113913-ada828/` (`result.json`, `state.json`, `steps.jsonl`, `evidence/CLAWDistribution.log`).
- VR17 replay: `claw-case17-review-20261119/result-review-02-root-replay/ROOT-VR17-INDEPENDENT-RESULT-RESTORATION.json`.
- VR18 replay: `claw-case18-review-20261119/result-review-02-root-replay/ROOT-VR18-INDEPENDENT-RESULT-RESTORATION.json`.
- VR20 replay: `claw-case20-review-20261119/result-review-02-root-replay/ROOT-VR20-INDEPENDENT-RESULT-RESTORATION.json`.
- VR22 replay: `claw-case22-review-20261119/result-review-02-root-replay/ROOT-VR22-INDEPENDENT-RESULT-RESTORATION.json` (SHA256 `6b2c88c955c0a648a161153a52ae0d06177c85bebbaa31527cb4e3f9497a403c`).
- VR25 replay: `claw-agent-workflow-20261119/vr25-root-restoration.json`.
- VR26 replay: `claw-agent-workflow-20261119/VR26-INDEPENDENT-RESULT-RESTORATION.json` (SHA256 `4af35f1f54f55df8de7ceec1b53aaf402af49ed8ef081f1dce3918a46b56b96e`).
- VR27 replay: `claw-agent-workflow-20261119/VR27-INDEPENDENT-RESULT-RESTORATION.json` (SHA256 `dbe03faa18e1d3d8f0b6104e6fa65ca0a901343dba24a68e13e82581e5498444`).
- Shipped-script analysis: `claw-vr20-transformation-analysis-20261119-01/{REPORT.md,ANALYSIS.json,BSA-EXTRACTION.json}`.
- VR28 replay: `claw-agent-workflow-20261119/VR28-INDEPENDENT-RESULT-RESTORATION.json` (SHA256 `aed2e6e296286318cbf30b5c4877318f2389793f0a561e992d839377c9e4ff6a`).
- VR28 graph and effects review: `claw-vr28-audit-analysis-20261119/EVIDENCE.json` (SHA256 `7043b51086d73df3d0a26699c5895f16bc0bef49b51d02317f84cdf20cf2999c`).
- VR29 replay: `claw-agent-workflow-20261119/VR29-INDEPENDENT-RESULT-RESTORATION.json` (SHA256 `eccef5ef7ced8cf089bf651b592fdaf49c0b6b9a4cdf7abfe4401abc7568616e`).


## Same-task graph and biped observation

VR30 20261119-233016-be40bc ran the 15 baseline checks and stopped before
a body command. SKSEVR 2.0.12 reported the witness incompatible at query;
its runtime integer encodes the VR subtype in the final nibble. Reusing
CLAW's existing query normalization retained the VR-only filter and fixed
the witness load.

VR31 20261119-233721-ed1bea used the repaired probe with all five mapped
DLLs verified and the same normal spell. After the two transition effects
were observed inactive, the default and explicit third-person roots
aliased. Their complete 124-object tree contained three geometries and none
of the four required wolf roles. The distinct third-person biped root also
had three geometries and zero target roles. Across active and buffered
clones of both views only third-person slot 2 retained a naked-skin
registration (item CDD86, addon CDD87). Its clone was absent. The first-person
root and biped root exceeded the 512-object diagnostic cap. Those first-person
inventory results are incomplete. Changing the selected Get3D overload cannot
explain the missing third-person roles in this sample.

The original model-availability failure remains status 4. Both runs used
their retained game handles to establish exit code 0. Independent restoration
reconciled 101 snapshots, 231 cold resources and 29 cold / 32 staged VFS
entries per run. No visible wolf model or game contact result follows from
this graph observation.

Local VR31 receipt SHA-256 7b2f96d6b8c1636c3002d55039138b80b26a5986785c5ee7d80b6dc8c094aafb. The next separate diagnostic distinguishes
the selected CDD87 model path and whether a model handle is present, and
collects a strictly bounded deeper first-person topology. No fallback
selection or unsupported model-attachment intervention is enabled.


## Selected asset and complete first-person inventory

VR32 20261119-234734-c8f341 retained the same post-effect wolf slot and
identified its actual selected model path as
Actors/WerewolfBeast/Character Assets/MaleBodyWereWolf_1.NIF. The part handle
and clone were both absent. All four graph trees completed at the expanded
diagnostic limit, including the two 695/693-object first-person trees. No
CLAW role was present in any route. The temporary five payload files and
101 profile/overwrite snapshots were restored and independently verified.
Receipt SHA-256 09da4445e133621a30a29b0d0a9b504e6d6b0098b64159ae8da9f6cae0018283.

The active CDD87 ARMA candidate differs from the stock Skyrim VR record in
the two model-range bytes: the installed marker uses 02 for male and female
where the stock record uses 00. A new private test changes only the male
byte to 00, keeping the selected paths, resource bytes and actor workflow.
No product weight-slider setting is changed by the test.

VR33 `20261119-235435-9a052a` changed only the male range byte (`02` to
`00`) in the test ARMA. The normal spell again reached stage 10. The male
world model applied, and five successive model checks returned status 2.
The post-apply diagnostic stayed inconclusive on the first-person marker.

VR34 `20261120-000411-f3725a` repeated that result and used one read-only
snapshot after two samples observed both transition effects inactive. All
four roles were present in the default/third-person graph and the third-person
slot 2 clone. The first-person roots completed without any of those roles;
the first-person active and buffered slot lists were empty. The engine still
selected the same third-person `_1` model path. This qualifies male world-body
attachment under the tested byte change. The first-person model, HMD rendering,
female selection and other weights need separate tests.

Both games exited normally. Independent replay matched 102 snapshots, 231
cold files, 29 cold and 32 staged VFS entries each time. Accounting after VR34
is 65 Skyrim starts, 23 Skyrim VR starts and 28 VR platform attempts. Local
receipt SHA-256 values are `39271c47455d6c7000cbfc403ef5ea43d7cdcbbef1b0e69a5ddf08993681f88c`
and `4eade9d30ac60996f2ad6c8666a119954b836b6be27d8dd77f62be586da647e5`.

## Female range-byte control

VR35 `20261120-001841-bf28a4` created a fresh female player with one
player-base sex flag in the private alternate-start overlay. Fifteen
self-tests completed, including the typed sex readback. With the original
female CDD87 range byte `02`, the engine selected the expected female
world path. Status remained 4, the slot had no clone and all complete
graphs lacked the four wolf geometry roles.

VR39 `20261120-003926-2ae912` used the same female fixture, body assets,
test marker paths and workflow. The ARMA differs by only the female
range byte (`02` to `00`); the male byte is `02` in both. The corrected
test executor additionally records exact Windows SteamVR launcher exit
time to handle a pre-game startup race. The female beast returned status
2 with empty error and the same selected female world path. The default
and explicit third-person graphs and active slot 2 clone each contained
the complete body, head, claws and tail-tip set. The first-person marker
stayed inconclusive.

Independent replay verified exit code 0 and 103 snapshot, 232 cold-file,
30 cold VFS and 33 post-staging checks for both games. Female baseline
receipt SHA-256 `52ace7c96309188e319cbdabe064dffef06ea5a0898eb0fb7b6c16b612c26315`.
Female range-disabled receipt SHA-256
`253b7b9cc62e79eb006fc77ae431aa15affd7b7b10ce34406231ee5c65519d85`.

Three attempts stopped during the earlier SteamVR process-start handoff,
before Skyrim or either body action. The test environment was restored
and independently reconciled in all three cases. Their retained receipts
are VR36, VR37 and VR38 `PRELAUNCH-RESTORATION.json` in
`claw-agent-workflow-20261119`. The successful paired game observations
bring accounting to 67 Skyrim starts, 25 VR starts and 33 platform attempts.

## VRIK controls and rebuilt companion at high source weight

VR40 `20261120-004252-a3cc28` confirmed the new executor's exact Windows
parent-lifetime recovery on two late SteamVR child processes. Skyrim
started and exited normally. The Root Builder plan still expected the
source modlist and stopped before actor checks when the owned clone added
VRIK. VR41 `20261120-005157-1e5040` projected that one modlist edit into
the expected plan. All 17 Root Builder file winners stayed the same.
The active VRIK 0.8.8 variant passed world-body attachment. Its first-person
graphs and slots still lacked the diagnostic role and marker evidence.

VR42 `20261120-005709-fbcc65` also staged the official XP32 Vanilla-tail
skeleton in the temporary profile. The male world model applied. The
first-person marker still did not qualify. The temporary archive's
character height offset changed from the pre-scenario 4.0 to 1.0 by
shutdown. A direct runtime calibration and first-person conclusion remain
open. The original profile stayed intact and independent replay verified
115 snapshots, 253 cold files and 47 staged VFS entries.

VR43 `20261120-010730-2cc57d` used the actual compiled
`CLAW - VR Body.esp` with both range bytes clear. The temporary profile
activated the real companion at regular plugin index 11 and disabled
the test marker ESP. The owned player changed from weight 75 to 100
before one normal transformation. The human weight refreshed to 1, the
wolf used the same source weight, and the third-person body and all four
geometry roles attached. All 11 weight-only morph values matched the
independent installed matrix oracle, including ArmGirth .5,
LegCalfGirth .375 and TorsoGirth .25. It exited 0. Independent replay
matched 102 snapshots, 231 cold files, 29 cold and 33 staged VFS entries.
Receipt SHA-256 `a1e43b6cd743d2b0b6b642497f9354d32f5e643964ea8458f65a532585610433`.

This result qualifies the tested player's world model and weight
calculation with the rebuilt companion. First-person model selection,
rendering and contact still have separate acceptance work. Accounting
after VR43 is 71 Skyrim starts, 29 VR starts and 37 platform attempts.

## Legacy alias control and complete weight-100 pair

VR44 `20261120-011406-295719` and VR45 `20261120-011743-c45812` retained
the same male scenario, VRIK and the same XP32 Vanilla-tail reference
skeleton. The only staged asset difference was the loose
`Meshes/Actors/character/character assets/1stperson_werewolf_hands.nif`.
Both recorded weapon state 0 (sheathed). With the current CLAW alias, the
third-person slot 2 clone contained 22 geometries and applied the four CLAW
roles. With the unmodified reference headless alias, that clone contained
five geometries with the reference shape names and lacked all four roles;
CLAW returned status 4. The selected third-person ARMA path still reported
`MaleBodyWereWolf_1.NIF` in both cases. This identifies where the substituted
asset was observed in this precise setup, independent of its name or the
selected ARMA metadata.

Both explicit first-person trees contained the same four RaceMenu hand
overlays. Headset and wand routes contained the same UI or controller
geometry; the separate hand, clavicle and melee-offset routes contained no
geometry. The broad PlayerWorld inventory hit its cap. Skinned triangle and
vertex counts in the wolf clone were zero in this readback; the five-shape
attribution uses complete names and the single file change. Neither run
established a first-person wolf mesh or what reached the headset. The
temporary calibration archive changed from 4.0 to 1.0 in each run. Source
profile bytes stayed intact. Both games exited 0 and replay matched 116
snapshots, 253 cold files, 30 cold and 47 staged VFS entries.

VR46 `20261120-012329-f1920d` ran the corresponding female high-weight
control with the same compiled companion as VR43. A fresh female player
changed to weight 100 before one normal spell. The transfer retained source
and final weight 1 and matched all 11 independently computed coefficients.
The active third-person slot reported `FemaleBodyWereWolf_1.NIF` and all
four roles. Its 22 geometries and 23 objects match the later male alias
control, while the authored female variant has 21 geometries. This V2 run
qualifies female source and coefficients only. The actual female mesh
needs a named geometry comparison. Exit code was 0; replay matched 103 snapshots, 232 cold
files, 30 cold and 34 staged VFS entries. The diagnostic profile still
provided a loose legacy alias from its enabled marker mod, even though the
marker ESP was inactive. A full companion archive run with that mod absent
is a separate check.

Retained independent receipts under `Builds/claw-agent-workflow-20261119`
are VR44 `8075feaaf255336f7cc35379b417665403c9d49c0022b5315a51112e36c06021`,
VR45 `98f54335463b1b8c1767209dff08cad3f67d7555458d4b47c0dca5d9b3cb0a8e`
and VR46 `56e427c68bc59a9b9577670e3437899d5caed5239ddf4db9d9f6822f43e0b50f`.
Accounting after VR46 is 74 Skyrim starts, 32 VR starts and 40 VR platform
attempts.

## Clean payload and first-person diagnostic controls

VR47 `20261120-013132-968fb6` had a ready world body. V3 sampled the raw
weapon state as 0. A typed `Actor.IsWeaponDrawn` read 1.466 seconds later
returned true, so the additional DrawWeapon call was never sent. These
different instants do not establish a native enum discrepancy. The owned
test exited 0 and restored its snapshots. The independent receipt digest
is `4d0f77ddd1169a476bb171b44eb1d0ada28d666088d816a201f74a25470dd1c4`.

The complete seven-member VR Body ZIP was tested with the exact ESP and
both namespaced NIF/TRI families. Two preparation attempts initially
refused on MO2 line-ending representation, before the game started.
Their original profiles and staged files were restored. The startup
validator now compares the exact logical modlist through MO2's CRLF
serialization, while keeping the activation, order and locked-file
checks. Only the disposable profile disabled the old diagnostic mod.
The stock XP32 skeleton and all remaining enabled mods were retained.

VR49 `20261120-014929-420d9a` checked 32 actual positive VFS winners,
including all seven ZIP files. Native resolve and origins confirmed
loose absence of both the disabled marker ESP and its legacy hands NIF.
One ordinary transformation produced a third-person slot-2 clone, but the
clone contained only one engine-named geometry. The four CLAW roles were
absent, CLAW returned status 4, and the morph oracle was not evaluated.
The namespaced archive is insufficient in this profile. The stock packed
asset remains outside the loose VFS absence claim. The game exited 0 and
replay checked 108 restored files, four temporary directories, 232 cold
files and 30 original VFS winners. Receipt SHA-256
`7dd56204855bb6cc9803eefab6735778bf76093c44455cf8b9a95ec419ca639b`.

The stock werewolf script calls `Game.ForceThirdPerson()` and then
`Game.ShowFirstPersonGeometry(false)` during the transformation. VR50
`20261120-015426-e043c2` used the accepted current-alias control and called
only the typed `Game.ShowFirstPersonGeometry(true)` once after both
transition effects cleared. Two same-owner V3 captures retained the active
third-person body and identical slots, geometry names and mesh-local flags.
The first-person routes still contained four RaceMenu overlays. V3 does
not inspect parent-node culling or prove headset rendering. The later
scenario readiness check and archived calibration did not qualify.
The game exited 0 and 116 files restored. Receipt SHA-256
`06a586c1060743d9c72e6e3c6902485da73bd5aabd7e1dcb65f1e1419a481cea`.

## FSMP dependency and event handshake in VR

VR48 `20261120-014613-3d1cca` loaded the exact FSMP 4.1.1 No AVX DLL,
the Menu Framework DLL from the 3.18 archive (internal log version 3.14)
and the VR observer, with VR Address Library 0.293.0. The same process
verified the public startup interface 2.0.0 and two fresh `ReadState`
snapshots, separated by about 1.175 seconds. Both pre and post counts
stayed zero while that fresh human scene had no authored wolf test actor.
Provider callback advancement and CLAW motion remain separate checks.

No actor or model command was issued and the Bullet object window was
idle. Exit code 0 and 143 file snapshots, 231 cold files, 29 original
and 72 staged VFS entries were reconciled independently. The exact
restoration receipt lives under
`Builds/claw-vr-fsmp-provider-verification-20261120` and has SHA-256
`50b60beab17f7d97b44f4b18ba24adcc84046a1894199499fa3e1648d2fab99b`.

## One-file restoration of male body and VR root-cull observation

VR51 `20261120-020000-4b654d` repeated the complete private ZIP control.
The profile still disabled the diagnostic mod. The only additional stage
file was the unchanged current authored male carrier at
`Meshes/Actors/character/character assets/1stperson_werewolf_hands.nif`.
All 33 positive resource observations and native absence of the old ESP
passed. V3 established the complete 22-geometry default/third-person
body. Source weight 100 and all 11 typed morph outputs passed. This is a
verified legacy path dependency for the tested male player. The fixed
path offers no automatic sex split and does not select the namespaced
first-person geometry by itself. Reconciliation matched 109 files, four
scoped directories, 232 cold and 30 cold VFS entries, with game exit 0.
Receipt SHA-256 `78b1c2409fc40db26b3de735d9b94ca22f0bdc9bd6943807e80f62756293d3ff`.

VR53 `20261120-021423-9e4553` repeated the single Show(true) diagnostic
with V4 under the same tested current-alias VRIK profile. The exact typed
command returned once after the ordinary transformation effects cleared.
The same-owner samples agreed on a raw camera state ID of 9 and the
complete first-person actor root cull chain. Its own app-cull flag was set
before and after. The first-person biped root inherited that exclusion;
the default/third-person world clone remained present and unculled at
the sampled roots. The first-person geometry and slots agreed. The
later original scenario deadline and archived calibration still refused
qualification. Scoped comparison and game exit 0 were verified
independently, including 116 snapshot preimages. Receipt SHA-256
`44b0e2a79f843d3dc045a5d0b1388fcc8a482150c0a0b2fd30dafabdc32e57e2`.

The first male NPC FSMP pilot, VR52 `20261120-020517-e0bdbe`, rechecked
the load and baseline callback counts. The ordinary fixture registered
at base `0x0B000800`. Its VR observer request refused the SE-style
`actors` field before any PlaceAtMe, window or gameplay operation. The
observer query must use the actual VR schema and separately verify the
owned target. The environment exited 0 and restored 144 files and six
created directories. Receipt SHA-256
`223b941088fa65c4cda626d199a59c194d97f6902ea97572a6e95d49b55e172b`.

## Female world-body carrier at the same legacy path

VR54 `20261120-021827-f56de9` used the complete seven-member VR Body ZIP,
an owned female source and the exact authored female `_1` NIF staged at
the legacy hands filename. The old marker ESP was absent in the native
VFS. All 34 staged positive VFS observations passed. The actual slot-2
clone contained 21 geometries and 22 objects with all four CLAW roles.
The first 16 names reported by the bounded observer matched the authored
female NIF in order. This distinguishes it from the 22-geometry male
carrier while retaining the independent 11-coefficient weight-100 oracle.

Together, VR51 and VR54 establish the tested male and female mappings
with a matching asset installed at the same legacy path. Each run used
a separate disposable profile with a single fixed winner at that path.
Automatic selection, simultaneous actors and first-person rendering are
still open. The exit code was 0. Restoration reconciled 110 files, four
temporary directories, 233 cold files and 31 original VFS winners.
Receipt SHA-256 `c3cd4b23df89ca0301c2faf350b39da7cdbffaa28233d092278551c0a5661b2f`.

## Registered NPC physics and the camera transition control

VR55 `20261120-022441-2dbd2e` ran the VR-specific Observer query and
placed one nonpersistent owned fixture after a complete 12-actor census.
The same dynamic actor `FF000863` retained its male werewolf base
`0B000800` and engine handle 1112352 across four increasing samples.
The third-person tree had the thirteen required objects, including nine
driven ear and tail bones. FSMP's typed API reported the exact
`SKSE/Plugins/hdtSkinnedMeshConfigs/CLAW/CLAWMotionMale.xml` registration.
The global pre/post counters advanced by 41 each in the measured interval.
The first human baseline had zero advancement. No anonymous Bullet object
window was armed, so target movement, writeback and contacts remain open.

SkyrimVR exited with `0xC0000005` after the scenario completed. Retained
handle and Windows Application event 102793 agree on the process and
exception. The fault address was `SkyrimVR.exe+0xE3ED1D`. The cleanup path
queues `qqq` and may also post `WM_CLOSE`. The evidence cannot attribute
the exception to either path or to FSMP. All 144 snapshots, six temporary
directories, 46 staged paths and 73 native VFS observations reconciled.
Receipt SHA-256 `7ab6d8a9ff0bdc88dab33af3a65c13ee23a7acdfd187aaf1d0042ce4f47f5d3d`.

VR56 `20261120-023337-716fc2` changed the one-action camera experiment
to typed `Game.ForceFirstPerson()` after stock transformation. Both V4
captures retained raw camera state 9, the same first-person root cull,
the same biped routes, and the three complete world-body routes. The
typed call returned `None` once. No native transition was observed.
The outer carrier classification and archived calibration still refused
qualification. Exit code 0 and all 116 snapshot preimages matched.
Receipt SHA-256 `31e93286b625154d0e77c020ab5ce6d07bc67b54da7c21b456eab4e59dc57aab`.

## Clean male package selection

VR57 `20261120-023808-544b5a` staged the eight exact files selected by the
male profile's diagnostic FOMOD recipe. The seven common files matched
VR51. The only changed in-game bytes were the loose alias, which now
contained the original authored NIF without a diagnostic marker.
The male body retained the same 22 geometries and 23 objects, all four
CLAW roles and all eleven weight-100 expected coefficients. The other
FOMOD choice has the same eight-file layout and female content as VR54.
This is native VFS validation of selected files with the game closed for
staging. The interactive MO2 wizard and dynamic sex routing are separate.
The game exited 0 and all 109 snapshots and 33 native VFS observations
reconciled. Receipt SHA-256
`2b8e547c692a7baacfd84c31bf2a5a3b7a63d3f7836fdecc9e402cf220d8089b`.

## NPC model lifetime and two measured poses

VR58 `20261120-024339-bdf469` repeated the exact male FSMP composition
and bounded the one allowed `Disable(false)` to its new owned NPC. Two
advancing reads confirmed the same actor was disabled and the body 3D
was absent. The game exited 0 and restored all 144 snapshots, 46 staged
paths, six temporary directories and 73 native VFS winners. This control
separates model unload from restoration and does not prove the cause of
VR55 or provider deregistration. Receipt SHA-256
`a957de48c4b83ecc2a731fedb2835f3f324ca8ce9164eb3929b9ef858e63e88d`.

VR59 `20261120-025259-d7185f` loaded the original standalone pose witness.
It observed the registered NPC via the inherited VR observer, but BeginNpc
refused before acquiring a lease. EndNpc reported unknown lease. The
CLAW runtime log confirms the initial VR alternate-start fallback reached
the expected cell without an authoritative NewGame activation. This run
later exited with `0xC0000005` at the same `SkyrimVR.exe+0xE3ED1D` offset as
VR55. It restored all 146 snapshots, 48 staged paths, 75 native VFS
winners and six temporary directories. Receipt SHA-256
`e1f67f5121c1e9f717b7fb2de08ad4d9b7bbb8951f23fb663177f3e3e8470be7`.

VR60 `20261120-030241-c232b2` used the witness with a main-task check of
the current loaded fixture cell. It read two complete third-person poses
from the same `FF000861` actor, engine handle 1112348, Body item `CDD86`
and addon `CDD87`. The 12 bone/anchor/control reads retained the same
opaque root lease, load epoch and task thread. The native pose intervals
are both inside the corresponding VR observer intervals on the same
10 MHz QPC clock. The end of the first pose and start of the second are
0.6768104 seconds apart. The model and body-clone origins were unchanged.
`EndNpc` confirmed retirement before the sole verified unload. The game
exited 0 and all 146 snapshots, 48 staged paths, 75 native VFS winners
and six directories reconciled. These observations establish actor model
ownership at the measured times. A provider object window and the
association of anonymous solver objects remain pending. Receipt SHA-256
`988fdbcc0fcbf225df59b10cd91cd533cc4266e6780b9068075850212ba05aa2`.

## VR61 actor-associated FSMP ears and tail

VR61 `20261120-031312-b666ab` recorded a public FSMP object window on the
same 10 MHz QPC timeline as two native poses of one scoped male wolf
`FF000844`, handle 1112346, Body `CDD86`, addon `CDD87`. The window begins
after the first completed pose and its last matched Post and readback
precede the second pose. It contains 28 complete pairs over 0.7946113 s,
11 rigid objects and nine enabled Spring2 constraints. The provider
reports the exact effective male motion XML. The restoration receipt
SHA-256 is `261a63e03e297b52858d38fb192a1ff6e3ab0369f31cbd47204545963d7cfd3b`.

The offline `fsmp_vr_actor_binding` replay uses the pinned source XML,
the two raw native replies and raw provider frame. The two kinematic
positions match the model's head and tail anchors exactly at both
endpoints. Their rotation matrices match within 1e-5 per component.
Opposite head-local signs distinguish the ear branches, and the
directed graph covers every declared role and edge. Dynamic inverse mass
agrees with the source mass at the observed 1.13 scale. The nine Spring2
limit and damping vectors agree with the XML after scaling the linear
limits. For the last complete pair the nine parent-local translations
changed by 0.0064477 to 0.0466536 unscaled game units, measured at Pre and
Post for each role and its parent. Direct provider actor ownership is
unavailable. The replay measures one matched solver pair and establishes
neither rendered motion, quantitative response under controlled
excitation, nor contact. The raw and computed evidence SHA-256 values
are `be5a43be5c82607b4ec6b5a3497f2eb1e7eee1839dac61039145e40f29cc73f2`
and `d87c827bbbddfc1fc0b032e97bd6979a5a9e57b15f94994c41561056eb6df6f8`.

EndNpc completed before the two-sample unload check. The game exited 0.
Restoration reconciled 146 file snapshots, 48 staged paths, 75 native
VFS winners and six temporary directories.

## VR62 independent controller-to-world-hand check

VR62 `20261120-032311-3fcac0` used full VRIK with the pinned XP32
Vanilla-tail skeleton and the same world model route. One tracked 20 cm
left-controller pulse and one return occurred before the ordinary
transformation. Another occurred afterward with the exact same player
identity. The observed left wand and skeletal hand displacement were
13.99920 and 13.99762 game units as a human, then 15.40009 and 15.39830
as a wolf. The right wand and HMD stayed fixed; the right hand displaced
0 and 0.00403 respectively. After neutral return the left residuals were
0.00049 and 0.00428. The four logical publications have matching Protocol
2 ACKs. The exact post-turn third-person volume and slot were observed.
A controller-to-skeleton association does not establish HMD rendering
or that the two results require VRIK. A stock counterfactual is separate.

The outer candidate status remains failed due to ambiguous carrier
classification and an archived calibration height mismatch. Exit0,
collected and restored, 116 snapshots, 253 cold files, 30 cold resource
winners and 47 staged native VFS winners. Independent receipt SHA-256
`41fbafcb91a95c49e2a086561063abedb6c7c1368587a16827471f8b825ff896`.

## VR63 effective RaceMenu input and task-thread guard

VR63 `20261120-033003-d642a5` forwarded one exact Papyrus String array
of 31 canonical names through the pinned DevBench. Both native reads
returned 31 finite zeros for `FF000855`, handle 1112344, body `CDD86`,
addon `CDD87`, weight 50, epoch 1 and the same opaque lease. QPC advanced
at 10 MHz. The consumer refused the pair because Windows thread IDs
changed 34020 to 20236; the second native sample then lacked the
successor independent observer bracket. The official SKSEVR 2.0.12
`Hooks_Threads.cpp` drains a serialized task queue from two call sites.
A per-sample OS thread identifier is distinct from actor/root ownership
and from a render-synchronized producer. The VR61 replay now permits
different valid task thread IDs while retaining the same ownership and
temporal checks.

EndNpc explicitly retired the lease. The strict joint-sample tripwire
withheld Disable. The owned executable later hit
`0xC0000005` at `SkyrimVR.exe+0xE3ED1D`, Windows Application record 102806.
The same offset previously occurred in VR55 and VR59. Event ordering
alone does not establish its cause. All 146 file snapshots, 48 staged
paths, 75 native VFS winners and six directories reconciled. Receipt
SHA-256 `26a209ed7e8b5b68f7f0c0fc3696b94f4d1364d79cf6f2e07fd97a0294e568a4`.

An offline replay of the serialized support geometry uses the fully
independently bracketed first pose and its native zero vector. Exact
actual VFS endpoint NIFs differ from the archive in file bytes but
match the body/head vertices, faces, weights and bind data; the TRI is
byte-identical. The 24 sufficiently observed slots are an offline
measurement from the native pose. See the contact-profile test notes
for the measured excess and limits. Observed nonzero morph response,
a fresh two-pose qualification and live contact remain open.

## Closed VR63b and full ear/tail support in VR65

VR63b `20261120-033854-af922d` repeated the effective morph read with
two independently verified QPC brackets. The same NPC `FF0008C8`
returned 31 finite zeros twice and actor weight 50. Actual task threads
were 37556 and 56168. Explicit EndNpc retirement preceded one owned
Disable and observations 14/15 of unloaded 3D. Exit0 and complete
restoration. Receipt SHA-256
`b582fb711620963da5dd8714164c2077a60569d60b6b123261b75974536192f7`.

VR64 `20261120-034216-6b2349` repeated the controller experiment under
the stock profile. Native resolution and two complete mapped module
inventories show VRIK absent. The observed human left wand traveled
13.99828 game units, while left and right hand movement were .17750 and
.17405. The two driver commands and independent neutral return were
confirmed. The wolf pulse was withheld by the previous human-positive
condition. Third-person world attachment was observed and the outer
carrier still failed. Exit0 and restored 116/253/30/33, two negative
VFS routes. Receipt SHA-256
`c38bdd2e3553f4ec6c8115961987f7f0511ff76358e552241df6a9e0ac47ecf1`.

VR65 `20261120-035112-948956` added the three exact support bones through
the test-only `BeginNpcContact` entry point. The known `FF0008BE` male
NPC returned both complete 15-transform snapshots and 31 zero-valued
morphs, with independently bracketed owner reads 9/10/11. EndNpc then one
Disable, unload observations 14/15 and exit0 were all confirmed. Receipt
`62223c67e0f4baa8cca45f7adefea82833ab55e6f4100ae2f4d817a2086396d4`;
raw typed pose/observer/model archive and input hashes
`4023ec337c2e07b4cd68e5e207ab1c48c7e1c35d3d44cc851cde40dffb77f14f`.
The independent offline geometry replay now covers all 32 male ear/tail
capsules. At both observed poses 13 assigned partitions had vertex
excess above .01 owner-local units. The largest was .517791 in slot
107 on TailBone01. An enclosing fit built separately for each observed
pose restored assigned coverage to floating-point tolerance. This is
geometric reconstruction from engine observations, with no holdout,
renderer synchronization or actual contacts. Receipt
`82f24894a151043156bba61ec7903850d535f071cfab9a4f2f817afa6010b8a5`.

## VR66 stock werewolf hand route

VR66 `20261120-035616-9914ee` retains the exact stock actor/profile,
carrier and observer from VR64. It allows a wolf pulse only after the
human virtual wand has been independently observed moving and returning
under the same ownership, even when the human hand does not follow.
The fresh test again measured limited human skeletal movement:
13.99828 units at the wand, .43745 left hand and .30957 right hand.

The same stock player's wolf world hand `NPC L Hand [RHnd]` moved
13.99895 units against the observed 13.99828-unit wand pulse. The
opposite hand moved .00207. After neutral return, the left/right
residuals were .00249/.00049, with the wand at its original position.
All four device commands matched protocol ACKs. The HMD/right
controller did not move. VRIK was absent from loaded plugins, native
VFS routes and two-sided mapped-module inventories. VRIK is optional
for this measured stock werewolf skeletal route; renderer and
hardware/HMD placement are unverified. The older carrier id gate
still produced the outer failed candidate status. Exit0 and exact
restoration were independently verified. Receipt SHA-256
`3b60445200240d0dd8785686f4fbb89cd8257a8540de4621dbabfb85ca057b9e`.

## Slot107 rigid ownership control

The exact support that escaped in VR65 was replayed with the same
capsule dimensions and rest placement, carrying it on the pelvis
instead of TailBone01. Both observed frames worsened from .517791 to
2.059871 owner-local units. At the original worst vertex 8415, stored
influences were .31519 pelvis, .51855 TailBone01 and .16614
TailBone02. The predefined alternate also regressed synthetic
tail-negative and both combined tail/thigh stress states. This
experiment rejects rigid re-anchoring to the pelvis. The original
52/128-slot allocations and runtime geometry are retained. The
private result SHA-256 is
`3f8f4f20407774b73849de5db2af9d503b4f74394b1615e7f0a44be2fabecbb1`.

## VR67 nonzero RaceMenu input and geometry replay

VR67 `20261120-040157-12071a` used the same fifteen-bone contact
witness and one exact dynamically spawned male NPC `FF000871`. One
official NiOverride write of the isolated test key changed the
effective `CLAWHeadEarSize` from zero to .5. One targeted Clear
returned zero and the keyed getter returned absent. The other 30
values stayed zero. All three native samples have independent QPC
brackets from the same owned actor. The test did not request a model
refresh. EndNpc retired before verified unload 20/21 and exit0.
146/48/75/6 and cold231+29 restored. Receipt SHA-256
`9d22ae51374febbe3cb3b2cce11d8b456085e86ff64687c37947d2a162ce7982`.

A numerical counterfactual compared .5 to zero at the exact same
measured second pose and VFS geometry. The recalculated 16 ear
capsules all changed; all 16 tail capsules were identical. Maximum
unordered endpoint displacement was 7.31684 owner-local units and
maximum absolute radius change was 1.88737. The test establishes
correct selection and mathematical materialization of the morph
input. It does not report a changed in-game mesh, host fit delivery
or contact. Geometry evidence SHA-256
`261df80ab65b00c1c7eabd8c328ea380eb9345ca9180a27746515d1e957c9d17`.

The optional native numerical replay of the exact VR65 pose input
uses 1525 unique support vertices and 3292 positive influences for
2085 memberships across the 32 slots. All 64 fitted capsules matched
the independent Python coordinates within 4.985e-12. On this machine
six Release batches took 55.64–63.05 microseconds per reconstruct
and fit, including 7.08–9.63 microseconds for world-vertex
reconstruction. These times omit external pose/morph reads,
projection-cache rebuild, provider work and gameplay overhead.
Replay source and external input instructions are in
`src/test/components/contact-profiles/posed-contact.md`. Repo-built
timing stdout SHA-256
`3d21d6174abb320e1997e823ac0211639444d522f39168c6a33f962c65b2f133`.

## Actor-scoped CBPC event qualification preparation

The installed TEST VR stock CBPC candidate is 1.7.2 with DLL SHA-256
`9585f78b2e4f1e09a3a33e1c7789e353caecd368738939b70ecd832b7792d729`.
Its public typed Papyrus contract has actor-scoped sphere/capsule
attach and detach. Exact PE and matching PDB expose the paired CBPC
ModCallback event names; published older source provides event
payload semantics and their limitations. The event group key refers
to its first bone, so a whole multi-link group cannot by itself
assign a collision to an individual link.

The independent test listener and single-NPC test plugin build
successfully. The listener binds to the exact fixture and selected
dynamic NPC, then captures a disjoint QPC window with explicit
sequence and drop counts. Portable test coverage includes wrong
actor/cell, unavailable source, clock and overflow. The fixture
has no preplaced references. Compile/runtime bindings and
stationarity remain independently checked before contact trials.
The DLL/PEX and ESP are external build outputs. Exact tool/ABI
pins are retained beside the candidate. Source listener build
receipt SHA-256 `06a8ff3492fe3dee87637e3d4994e0d8951c605d107740d6aa21babe76195643`
and authored test ESP verification
`e41089b636ee41db6c183d6ed8ac346625e0817048ef2b45f0b1c44702753c13`.

The raw same-task VR65 left controller and tail origins were
215.700–223.091 game units apart. With the checked stock controller
offset and a prospective isolated sphere pair, a 13.998-unit
perfectly aligned pulse still leaves at least about 196 units
between centers in the closest measured case. The existing spawn
is unsuitable as a positive contact control. The next case needs
a measurably stationary owned NPC close enough for a separated
far interval and two qualified near intervals. Silent callback
intervals alone do not report whether a solver pair was evaluated.

## VR68/VR69 female FSMP binding and solver parameters

VR68 `20261120-041429-745650` directly observed the ordinary female
world slot and exact `CLAWMotionFemale.xml` on a born-female NPC at
weight 100. The observer read 17 expected world names, including both
P1 anchors and both drivers. Global FSMP callback counters advanced
41/41 after spawn. One guarded Disable confirmed absent 3D, exit0 and
restored 144/46/74/6. Independent receipt SHA-256
`c98f171fb2b391063af1c4b8f680eaaaa5cbe9afbd2d08f421847ca5222e6fce`.

VR69 `20261120-042451-b8e015` added two independently bracketed
16-transform reads of a fresh female actor `FF00087C`. A single
public FSMP window within their QPC bounds retained 29 complete
pairs, 15 rigid bodies and 11 enabled Spring2 edges. Head, tail
and both P1 kinematic anchor poses had unique exact endpoint
positions and a compatible rotation basis. This resolves the
bilateral P1 ambiguity left by topology alone. The actual left and
right P1 roles map to local tokens 14 and 15, respectively. The
shared replay also validates the exact inertia and stiffness
under the observed uniform scale, along with inverse mass,
signed linear/angular limits and damping. The joint frame must
match the authored side. Official source documents cubic linear
stiffness and fifth-power angular stiffness scaling.
[FSMP constraint implementation](https://github.com/DaymareOn/hdtSMP64/blob/e52ad960048c14e637d14fcbd65314ca017fc3b8/src/hdtSkinnedMesh/hdtGeneric6DofConstraint.cpp#L21)

The last complete pair showed ear and tail owner-relative
translations up to .036593 game units. Left and right P1 relative
translations measured .000691 and .000488, close to the sampled
world-coordinate granularity. This cannot establish meaningful visible
P1 response or a controlled amplitude. The numeric correspondence
depends on observed poses, XML and graph uniqueness. Direct provider
ownership, synchronized skin rendering and contacts are separate.

The pose lease ended before one verified Disable, exit0 and 146/48/76/6
restoration. Independent receipt SHA-256
`7ffe488789079f33b9aba2d4ba299b955070d4b418ce3c647524ed52241ef5f2`,
raw inputs `da20816197738faf93ee3a92a93c1e3d2ac24af7cef0d02b39fbd8044e65f19d`,
numerical association `efbcfe47b0eb794953f916ac8d6a5d590b661a29d54b1452728585b695555b0b`.

## Morphbench configuration comparison and next female trial

Morphbench `623c2e28144ad8d4251601e187e51f20aa047fde` imported and
exported both exact VR61/VR69 XML files byte for byte. The editor exposed
344 male and 422 female editable fields. All 9 male and 11 female
constraints reproduced the source limits, damping, stiffness and frame
selectors used by the corresponding live solver replay. The mass and
inertia fields matched as well. With the recorded actor frames supplied
to the editor, every configured linear limit endpoint used its declared
joint origin and basis. This checks the static projection with observed
VR frames. Motion amplitude still requires a controlled game measurement.

Changing the left P1 linear damping X from 0.4 to 0.0 in the editor
changed only that number in the exported female XML. In the completed
[SE damping comparison](physics-damping-response-20261119.md#controlled-se-damping-contrast-completed),
that setting was the sole configured difference. The edited VR export
was checked offline. Local `Builds/claw-morphbench-physics-replay-20261120/`
retains `REST-FRAME-RESULT.json` SHA-256
`6fde4f811957feb34a2d63c79cb972eca95598effb23e3da4abcbdda351cc695` and
`verify_editor_rest_frames.py` SHA-256
`84a782e2985be8ae8ec313dae468619cf79d7db6975075c2de8af30282a8b2a8`.

The exact VR67 NiOverride metadata exposes `GetNodeTransformKeys`,
`HasNodeTransformPosition`, `GetNodeTransformPosition`,
`AddNodeTransformPosition`, `RemoveNodeTransformPosition` and
`UpdateNodeTransform`. This establishes typed runtime availability.
Use these in one fresh guarded VR run to qualify the anchor update and
its undo before measuring P1 amplitude. The SE `CLAWTestFsmpPulse.psc`
hardcodes a different actor base and cell. Its compiled script must stay
out of the VR trial. Reuse the existing [owned anchor operations](../python/integration/owned_anchors.py)
and [paired FSMP trace](../cpp/fsmp_step_witness/README.md#optional-paired-pose-trace)
after confirming their bindings in that run.

Start with empty transform keys and an observed quiet pair for both
P1 joints. Map the four trace tokens to the new actor, apply one keyed
left-anchor step and witness the right anchor as a control. Retain
the continuous provider pairs, independent world samples, and exact
removal and return. Require response clearly above measured coordinate
granularity. The scoped pose lease need only cover its actual native
reads. Continuous world-owner evidence must bracket the held interval.
The editor shows configured limits and geometry. Comparing its predicted
waveform to the game would require an equivalent solver and host-time
and kinematic inputs, which the editor does not currently implement.

## 20 November continuation: controlled test preparation

The paired-trace reader now accepts both native v4 envelope variants. It
retains the same nonce, epoch, PID, token order and terminal-pose checks.
The historic SE A1 replay retained 837 complete pairs across 53 pages.
The new P1 readback test requires an independently bracketed left-anchor
step and return with a quiet right control. It measures the left driver
in world and joint coordinates and requires a difference in the same
provider pre/post pair above the position precision bound. A stale held
pose with identical pre/post data does not pass. The next fixture uses
a declared .04 local-unit test input within the .15 authored X limits.

Three new TEST VR sessions exited normally and restored 146 snapshot
paths, 48 staged paths, 76 VFS winners and six staging directories each.

- `20261120-105559-6e3599` created one disposable actor, whose 3D never
  became available during the bounded wait. No trace arm or anchor write
  was forwarded.
- `20261120-110247-b62204` loaded the female fixture and read its correct
  FSMP attachment. The test refused before the trace arm because it
  looked for the XML in Overwrite. The next controller reads and hashes
  the actual native VFS winner. Offline replay also found motion between
  the early actor pose and first provider pair. The next controller
  requires a stable independently observed anchor cohort before arming
  the original strict two-endpoint association.
- `20261120-110741-129d76` did not leave the startup calibration menu.
  The driver consumed each of the four candidate commands and there was
  no menu transition. No CLAW fixture, trace arm or body write occurred.

The second session confirmed that the owned SkyrimVR process was both
SteamVR's scene owner and last-frame renderer. The compositor advanced
from frame 2087 to 2096. Its frame timing reported zero presents in both
samples. No eye image or visible model content was captured. The stock
CBPC geometry gate was also checked offline on three retained VR65
frames. At that position the sphere centres were 215–218 units apart
with a combined radius of 6.39 units, requiring a closer stationary
target for the contact trial.

The three independent local restoration reports are under
`Builds/claw-vr-fsmp-p1-20261120/`,
`Builds/claw-vr-fsmp-p1-reposition-20261120/` and
`Builds/claw-vr-fsmp-p1-vfs-20261120/`. Total accounting is 101 Skyrim
starts, 59 VR starts and 68 SteamVR platform attempts. Controlled P1
response, stock CBPC emission contrast, HMD image content and dynamic
first-person sex selection remain unverified.

## Prepared contact and renderer trials

The next P1 trial observes a quiet calibration screen after the startup fade,
sends one right-trigger press for up to 1.25 seconds and releases it even if
the observation fails. Acceptance requires the actual Main Menu transition.
The successful and failed earlier starts used identical archived calibration
preferences and both recorded driver acknowledgement. Ten offline checks
cover the revised startup and inherited female actor gates. The new preflight
found another running Steam application and stopped before writing admission
or launching MO2, SteamVR or Skyrim. The prepared trial is under
`Builds/claw-vr-fsmp-p1-startup-20261120/`.

The private CBPC trial uses one disposable male NPC and the stock controller
sphere at the tail. It verifies placement and attachment, observes four holds
with approaching, separating, approaching and detached geometry, then checks
the scoped CBPC events and ordinary teardown independently. Its cadence covers
the minimum dwell even with a fast observer. All six offline controls pass.
The trial stages 23 files and requires 50 positive VFS winners and five absent
competing modules. It is prepared under
`Builds/claw-vr-cbpc-near-far-20261120/`; the callback comparison is unrun.
If the installed MO2 API Bridge advertises batch verification, this trial also
checks all 55 paths together against the exact copied profile and Bridge boot.
Three offline reply checks cover the profile scope, changed hashes and missing
providers. The previously installed Bridge still uses the existing per-path
route. The new Bridge candidate and its batch path await live verification.

Slot 107 still uses its original TailBone01 capsule. A fixed-size translation
enclosed both VR65 samples that had .517791 units of assigned excess. In three
independent recorded VR67 samples it increased the sampled outer-surface P95
distance by .565627 units. Two withheld compound bends also retained assigned
excess of .080903 and .160943. The candidate failed the coverage and surface
gate. The retained result under `Builds/claw-contact-slot107-fixed-radius-20261120/`
has SHA-256 `da6d42765bf999f3168f39aaea6671bed12211e55d7619ac1f62d9313ac53166`.

The new external eye capture used a real D3D11 WARP texture in its offline
copy and PNG check. A separate paired reader checks live process identity,
the measured body route, advancing frame observations and held neutral and
downward views. Its six offline checks include a control with no CLAW world
roles. Pixels from a Skyrim VR compositor and body visibility still require
the live run. See `Builds/claw-vr-render-capture-20261120/`.

The VR resource loader now resolves both the current Morphbench source layout
and historical flat snapshots. It loads the NIF reader from the selected
source in a private namespace and checks the source digest before and after
dependency loading. The real current and historical NIF readers opened the
same 490-block donor. The current VR-body component passed 17 checks, the
broader VR suite with exact archived resources passed 88 of 89 (one optional
reference missing), and the existing native Release suite passed 24 checks.

## Bridge 2.3.7 test-instance observation

The same Bridge 2.3.7 route file was present in all four installations.
One owned TEST VR manager was opened with the original CLAW VR profile for
readback only. The live batch verified the five exact CLAW files selected
from the retained profile and the modal route returned an empty list. The
manager exited with code 0 and the six protected profile files matched their
initial hashes. The manager rewrote the general ModOrganizer.ini during its
session. The game, selected profile and offline-mode values read the same
before and after. The full-byte guard therefore failed for the general INI.
The local receipt is `Builds/claw-vr-bridge-237-preflight-20261120/RESULT.json`.

The prepared P1 case retains batch evidence for its 76 staged VFS paths.
It also reads the exact owned Bridge's dialogs before dispatch or on startup
failure and correlates the known SKSE operation with the SkyrimVR
PID, process creation time and executable. A terminal Bridge observation
is compared with the existing independent game exit handle when available.
These diagnostic calls share bounded original phase time and never authorize
dispatch. The prepared case passed 14 offline checks. Its game observations
are pending.

## 20 November live follow-up

All six additional TEST VR cases reached the intended SkyrimVR process. The
latest independently reconciled accounting is 107 Skyrim starts, 65 VR
starts and 74 SteamVR platform attempts. The retained test profiles and
staged assets were restored after each case. Two exits returned the Windows
access-violation code instead of zero. These are separate teardown failures.

- **FSMP P1, 122643.** Bridge 2.3.7 checked 76 game paths, reported no
  active Qt modal at dispatch and identified the exact SkyrimVR process for
  the SKSE operation. Its terminal exit code 0 matched the independent
  process handle. The female NPC loaded and the witness retained 29
  coherent passive solver pairs. The original association rejected the
  moving pose bracket before any P1 write.
- **FSMP association replay.** Independently sampled WorldObserver poses
  immediately around the solver window uniquely identify head, tail and
  both P1 parents. Head and ears retain the exact graph checks. The tail's
  unique five-link chain and exact positions identify the tail anchor;
  the cross-reader rotation residual is recorded separately. The next
  frame shows an animated shift, and the new pre-arm check refuses it.
  The ten offline controls qualify association and refusal only. The
  actual anchor pulse and its return are still open.
- **CBPC, 122840 and 123130.** The first run refused a Windows extended-path
  prefix mismatch on otherwise equal provider backing. With both ordinary
  and extended paths normalized, the second run reached NPC placement.
  Destination XY was within half a unit. The NPC settled about 6.7 units
  below the initial player-height guess. The case stopped before arming.
  Exit code 0xC0000005 was observed after the shutdown command.
- **Stock renderer, 123506.** At 16.813 seconds the CLAW status was 2 and
  one of two transformation effects was still active. The two-sample
  post-effect topology requirement was not reached. No headset tilt or
  image capture was attempted. Exit was 0 and all 116 snapshots matched.
- **RaceMenu attachment, 123854.** The owned female wolf, observer and
  actual VFS backing were verified. The direct NiOverride.AttachMesh
  transport returned None despite advertising bool. The observer lease
  retired, the game exited 0 and the case restored 147 snapshots, 49
  staged paths and 77 VFS winners. Native completion and geometry remain
  unknown. The test-only CLAWTestSkeeAttachment.psc uses a Papyrus stack
  for the two latent calls and returns the completed response as a typed
  integer. The compiled script must still be tested in a fresh run.
- **CBPC, 124245.** Actual floor settling and isolated left-controller
  lowering passed. The test armed the event witness and attached one
  test sphere. The eight held near frames had 9.04–11.16 units of
  separation, exceeding the combined 6.39-unit radius while the wand
  remained fixed. The sphere was detached and the baseline input restored.
  The game again exited with 0xC0000005 after shutdown. No sustained
  contact, callback contrast or release contact set is qualified.
  A phase-aware offline fit including the pre-arm frame retained at least
  1.73 units of overlap on the nine recorded frames at the same radius
  and within the original local-offset bound. A fit using only later
  frames missed the pre-arm control. New trajectories, the far phase and
  teardown require independent live validation.

The private receipts are under Builds/claw-vr-fsmp-p1-startup-20261120,
Builds/claw-vr-fsmp-p1-pose-binding-20261120,
Builds/claw-vr-cbpc-near-far-20261120,
Builds/claw-vr-cbpc-module-path-20261120,
Builds/claw-vr-render-qualification-20261120,
Builds/claw-vr-skee-attachment-case-20261120,
Builds/claw-vr-cbpc-floor-anchor-20261120 and
Builds/claw-vr-cbpc-tail-motion-study-20261120. The compiled latent
attachment fixture and any live output stay outside the mod archive.
