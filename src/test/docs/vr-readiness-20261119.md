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
- Shipped-script analysis: `claw-vr20-transformation-analysis-20261119-01/{REPORT.md,ANALYSIS.json,BSA-EXTRACTION.json}`.
