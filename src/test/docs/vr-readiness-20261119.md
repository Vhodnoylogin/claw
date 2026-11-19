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
