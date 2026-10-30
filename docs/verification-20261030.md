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
values within 5.43e-8. Human values and foreign morph keys were preserved.

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

The tested native DLL SHA-256 is
`16543ae9ef459599bb02fd912d6ab70fe8af4155fa821a6b1a56e440bfbf6e92`.
Mapping source SHA-256 is
`d89166286f16822577a45b6c971ba508e333d58ef30ec51dfefbef278a20ee6f`.
All six repaired body resources reproduce the hashes in the frozen surface recipe.
Installation used the actual FOMOD selection and native MO2 archive accounting.

These results establish fundamental linkage and persistence. Distinct numbers
do not establish sufficiently expressive or natural rendered shapes. The owner
then inspected adjacent human/wolf pairs in the game, reported weak visible
differences and requested a Git release freeze with shape improvements in the
next development branch. The [dated baseline](../release/SE-Core-20261030.md)
preserves those exact payloads and the known limitation. Natural rendered shape,
physics, VR and other executable versions are not certified. Nexus publication
is a separate owner decision.
