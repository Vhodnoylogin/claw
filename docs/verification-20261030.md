# Linked SE candidate: bounded game verification

On 30 October 2026 the installed contrast6 runtime set passed two actual Skyrim
SE 1.7.104.0 / SKSE 2.3.1 runs with official RaceMenu NG and OBody NG 5.2.2.
No third-party DLL replacement was required. Native source remains `078510a`;
the mapping/packaging source tested here is `f9162b19`.

| Scenario | Declared checks | Result |
| --- | ---: | --- |
| Six ordinary human presets, both-sex wolf/human roundtrips, source preservation, native ESS/SKSE save/load and postload reads | 117 | Passed |
| Fresh human control and male/female actors created directly as wolves | 33 | Passed |

All six human-derived numeric wolf vectors differed; same-sex pairs differed in
7–10 channels. Observed heavy belly values were approximately 0.796318 and 1.0;
the muscular male chest was 0.30000001. Independent recomputation matched actual
values within 5.43e-8. The observed human values and tested foreign morph keys
were preserved; the capture scope below limits the human-value claim.

Both born wolves obtained ordinary human OBody assignments without tester
source/family/race/morph writes. The intended automatic CLAW source host calls
`OBodyNative.GenActor`; actual Papyrus-channel events are consistent with that
architecture. The observer did not identify the precise Papyrus caller stack.
This proves the two tested paths, not OBody-alone creature support or universal
coverage of every external NPC configuration and blacklist.

Both processes exited with code 0 through the configured native Main Menu route,
without forced stop. Source profiles, owned snapshots and collected files were
independently verified; temporary test profiles were archived and removed.
Earlier abnormal shutdowns remain recorded and are not erased by these passes.

## Captured human-input scope

The later accepted twelve-actor scene established equal actor weights and equal
configured conversion sources within all six human/wolf pairs. The historical
readback covers 339 configured source values per side: 61 names for each male
type and 52 for each female type. It includes aggregate/keyed evidence for those
names, not every morph affecting the human body. The capture contains 20 negative
values across the six types. Equality inside this subset is not a complete
human-shape readback.

Offline reconciliation against the assigned current presets preserves all those
observations and reconstructs the complete six human preset vectors: 834 values,
including 22 negatives. Five nonzero female entries were outside the historical
capture: FThin `BigButt` and `Butt`, FMuscular `MuscleAbs`, and FHeavy `BigButt`
and `Butt`. They are currently unmapped, so they do not change these linked wolf
outputs. They must nevertheless be retained for full preset-based human-body comparisons
and labelled as preset reconstruction, never runtime-measured zeros. The external
`Builds/claw-morphbench-addon-20261030/real-pair-inputs/human-preset-reconciliation.json`
records the distinction; it does not authorize or represent a new game capture.
The [paired numeric table](morph-range-plan.md#latest-paired-game-evidence)
continues to describe the observed wolf output correctly.

## Frozen resources and later package verification

The tested native DLL SHA-256 is
`16543ae9ef459599bb02fd912d6ab70fe8af4155fa821a6b1a56e440bfbf6e92`.
Mapping source SHA-256 is
`d89166286f16822577a45b6c971ba508e333d58ef30ec51dfefbef278a20ee6f`.
All six repaired body resources reproduce the hashes in the frozen surface recipe.
Installation used the actual FOMOD selection and native MO2 archive accounting.

These results establish fundamental linkage and persistence. Distinct numbers
do not establish sufficiently expressive or natural rendered shapes. The owner
then inspected adjacent human/wolf pairs in the game, reported weak visible
differences and accepted a technical Git release with shape improvements in the
next development branch. The [dated release](../release/SE-Core-20261030.md)
preserves the runtime cut and known limitation. Natural rendered shape, physics,
VR and other executable versions are not certified. The native DLL's explicit
guard accepts only SE 1.7.104.0; CommonLib's enabled edition flags do not extend
that support. The separate VR DLL has offline compile evidence only.

GitHub release `429346812` now contains exactly two assets: the single working
installer (`4d58714f83e4dea70b52d0d2d2ea2fd0aff9f54b2cd1c321c02f7a97ae038a49`)
and isolated test data (`230c0264bc1748ffd1c726848f1e5c29361996276d386b06d467828c162a824d`).
The original tag `claw/se-core-20261030` still identifies runtime cut `689e5bd`.
The old four assets were replaced only after both new digests were verified.
Corresponding native source is nested under the working ZIP's uninstalled
`Source/` directory. The component archives are historical provenance, not the
current download/install split. Historical Nexus 0.6.2.0 remains base-only.

Offline verification checked the actual FOMOD schema, all five selections,
exact native game/dependency gates, unchanged frozen payload hashes, deterministic
ZIPs and zero production/test destination overlap. The subsequent native MO2
installation verified 33 working files for HIMBO + 3BA with the OBody host and
eight test files, persisted provenance and Downloads Installed accounting.
CLAW and the declared legacy SE-Testing profile use the two exact full mod names;
their runtime/configuration winners and three required plugins were checked.
Morphbench's enabled mod order was preserved.

The first old-folder native removal timed out without a successful response.
Recovery stopped the exact verified idle MO2 process, retained 15 remaining old
folders outside MO2 and restarted the manager without changing Bridge code.
All 16 original installations remain recoverable from 281 byte-verified backup
files, 543,148,741 bytes. The independent settlement audit found `errors=[]`,
confirmed the original Polygon host restored and the environment idle. Only
that preparation hold was then cleared. Evidence is retained under
`Builds/claw-release-20261030/consolidation-20261030/`; review SHA-256 is
`6c072c81b1f2730605afaa262c5803147398450cac7dc514d41005218fe7d9b9`.
`FINAL-SETUP.json` records completed settlement and hold clearance. This
consolidation/recovery work started no game; it does not add a gameplay pass or
erase the earlier manual session's abnormal exit. Nexus publication remains a
separate owner decision.
