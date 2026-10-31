# Matrix and expressive-body candidate — 31 October 2026

These are preserved results for the exact candidate later used by 0.7.0.0.
Source paths below have moved, but the measurements and game receipts have not
been rerun for the source-only layout. The pinned
[original source/release cut](https://github.com/Vhodnoylogin/claw/tree/53e8f3872533f193483a4ee683d3bece1fe3eafa)
retains the historical package inputs. Fresh donor-build acceptance is tracked
separately in [rebuild.md](rebuild.md).

This is a new development candidate, separate from the published 30 October
technical Git release and the historical Nexus release. It combines one universal
CommonLib DLL, the shared native/WASM matrix kernel and reproducible expressive
TRIs. It does not include physics, a first-person VR body or test actors.

## Actual Skyrim SE checks

The installed candidate ran on Skyrim SE 1.7.104.0 / SKSE 2.3.1, with the official
installed RaceMenu, OBody NG and separate HIMBO/3BA dependencies. The exact source
profile and 1,173 installed inputs were pinned. No RaceMenu replacement was used.

| Attempt | Required checks | Result |
| --- | --- | --- |
| `claw-se-matrix-core105-20261031-universal1` | 104 passed, final read exceeded its 20-second bound | Retained failed attempt |
| `claw-se-matrix-born27-20261031-universal1` | 27 passed | Born-wolf mechanism passed |
| `claw-se-matrix-core105-20261031-universal2-read30` | 105 passed | Complete core mechanism passed |

Each run also recorded one auxiliary check. The replay changed only the 26 dense
read deadlines from 20 to their original 30 seconds, plus its unique identity and
explanation. It changed no installed byte, actor action or assertion. The complete
late response from the first attempt is retained; later analysis does not change
that attempt's failure. Every run ended through the game menu with identified
exit code zero, no forced stop, completed collection and completed restoration.

The core covers six ordinary human presets, both sexes, automatic source/profile
adoption, same-reference transformation and return, human source/key preservation,
and a real save/load of a mixed human/wolf cohort. Both thin actors exercised all
four new Lean fields. Born tests cover male and female actors created directly
as werewolves and one human control. No test action assigned their human morphs
or explicitly configured their morph families.

Independent postanalysis fed the actual SKEE human aggregates into the built
universal `claw-preset-tool matrix` command using the exact installed XML. All
26 replay captures and three born captures matched every public owned target
(28 male / 29 female), with maximum decimal difference below `4.94e-10`.
The tool's older linear derived expectations were deliberately ignored. Reads
also checked source presence and keyed storage, two stable samples and postload
identity remapping. The captured 61 male / 52 female conversion sources are not
the entire human TRI or preset.

The canonical immutable packets contain raw engine evidence. The order also
requested postanalysis outputs as collection items, but those outputs were
produced afterward in separate analysis files. Their packet coverage remains
`not_collected`, so canonical requested-data coverage remains incomplete. This is
an order/report design limitation; it neither erases the successful external
analysis nor turns a numeric match into rendered or artistic acceptance. No
packet or failed result was rewritten, and no self-delivery receipt was invented.

## Exact runtime payload

* DLL: `e7b238c82428f76cbefb58a322d25d05580519553ab3aa307d7ce6cc080ac3d5`
* Male TRI: `6ca67487b2ab8138696efe77a86c507fbf61e2fa285557dc062d1b68c799095b`
* Female TRI: `096b0a257d61eb3c64a5ac9af63a442d58867ce9bab6124defc4fc5db85263a9`
* Candidate03 working ZIP: `cc6e9ec89065715da422fc0ffb9ffafacb68051ef48e790cbabe615ccbeb7412`

The working FOMOD has 49 archive members and selects 33 files for the tested
HIMBO/3BA/OBody configuration. All native selections install the same DLL.
The unchanged `test_CLAW` archive remains separate (eight installed files).
Dependencies remain separate MO2 mods; no human body, texture, skeleton or test
NPC is hidden in the working mod. Actual native Installed accounting, VFS winners
and effective profile orders were reconciled after installation. After testing,
all 1,173 inputs were rehashed and the original Polygon host restored exactly.

## Offline and preview evidence

The universal CTest suite passed six tests. Native and WASM evaluations agreed
bit-for-bit on 3,123 float32 outputs across 208 matrices. One portable C++ source
provides the arithmetic; JavaScript only validates and marshals it. The
[runtime contract](universal-runtime.md) records the seven candidate boundaries.
AE and VR were not run in this check, and CBBE has offline rather than current
engine-fixture coverage.

The [body recipe](expressive-body.md) rebuilt all six resources twice identically.
Finite geometric checks cover the authored fields and real matrix fixtures,
including coat response. Actual Morphbench consumer checks opened male/female
human/wolf pairs, applied thin and muscular vectors, verified linked rotations
and downloaded a matrix. Its public geometry reads covered every model shape,
including 14,597 human and 99,909 wolf vertices in the male comparison.
Actual JSON/XML downloads also verified the edited matrix and complete native
catalog. An all-constant matrix kept the complete exported wolf model exactly unchanged while
the human changed from thin to muscular. Both approximately 16.2 MB geometry
snapshots were downloaded and independently checked for finite arrays, exact
current-minus-base deltas and unchanged wolf data. The pageable export viewer
passed 15 actual-SDK/DOM checks, including multi-megabyte reconstruction and
complete immutable downloads. These browser/native constant checks are separate
from the current game's default-profile coverage.

These previews are fixed NIFs with untextured, quantized model-space geometry.
They do not prove textured silhouette, animation, contact, arbitrary combination
safety or attractive proportions. The new range is ready for the owner's next
textured inspection. Breast naturalness, head/ear/tail/claw relationships and fur
colour remain next-release work; physics, fitted colliders and VR body follow.

Raw evidence remains outside Git under `Builds/claw-matrix-20261031/` and
`Builds/claw-matrix-plugin-20261031/`; generated binaries are not source commits.
