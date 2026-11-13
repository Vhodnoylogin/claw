# CLAW 0.10.0 technical verification

The shipping motion mode is Faster HDT-SMP, with None as the installer default.
The evidence below qualifies that mode. CBPC is excluded after its first-transform
binding test failed; it is not an unverified choice in the working installer.
Final archive/source identities and publication receipts are maintained externally.

## Native core and resource scope

The universal CommonLib build produced CLAWDistribution.dll SHA-256
`ccf7718d90f99ebc176b4231566fa6cc1cbbb117741de6e1babe267ab508503b`.
Seventeen native suites passed. The build consumed explicit source pins and the
reviewed external SDK; final clean-commit equivalence must be checked separately.
All actual new game runs use the dedicated TEST SE environment at FHD.
SE game evidence does not establish AE/VR runtime acceptance.

The motion cut uses the normal v4 male/female bodies and existing XP32 skeleton.
It contains no contact host, contact model, VR body or adult geometry. Core
male/female NIF hashes are 6a7fa9e2/6638401e; append-only FSMP hooks produce
7abd6560/e5a9d6b5 without changing original geometry, skin, materials or BODYTRI.
The male/female TRI hashes remain 3ff00f50/34744d55 and the existing skeleton b64b614d.
Exact full digests are recorded in the source/build and installed-input receipts.

## FSMP — passed normal models and human-origin lifecycle

Provider SHA-256:
`5290e2a8c3ddc4c13fecfd08234ff455f50c6a9ca42dcd381cde158631446672`.

- Run121036-aca348: nine male dynamic WORLD transforms matched the solver twice.
- Run122704-e56fe3: eleven female transforms, including breast P1, matched twice
  on the current 0.10 DLL.
- Run132921-ea509a: two actual initially human persistent NPCs completed human,
  wolf, Refresh, human return, second wolf, Disable/unload/Enable and real owned
  save/load with fresh reference/root/epoch readback. No physics Start/Toggle or
  Reload call activated their systems.

The last run's final window recorded 900 coherent solver pairs and 48 objects.
Two advancing paused observations matched all 20 dynamic roles to 20 distinct
positive-mass bodies with exactly zero translation and rotation error. Six
kinematic anchors were recorded separately because FSMP does not write them.
Male actor/root/world scale 1.13 and local scale 1; female uniform scale 1 were
observed, not forced. Original human weights and actual selected families
persisted: male HIMBO at ≈0.3 and female Vanilla at 0.5.

FSMP writes WORLD, while the ordinary engine hierarchy can subsequently
recompute it. The bounded existing TFC1 pause holds cached solver poses and
allows exact engine writeback comparison; LOCAL-only observation is insufficient.
Actual joint-relative pre/post changes also exclude mere whole-actor translation.
This is mechanism/writeback evidence, not pixel quality, contact acceptance or a
measurement at every earlier lifecycle boundary.

Both owned NPCs were disabled, camera/time restored, own normal menu exit 0
observed and existing CDB collector stopped. Collection and restoration had no
errors; 333 original files and 32 profile directories were independently exact.
The ported test source and unchanged witness live under src/test; all 435 actual
case receipts replay in exact request order through the retained operator and
repository port with equal semantic results. The port itself was not game-launched.

The source audit additionally matched the exact provider PDB checksums for the
normal frame path. In the actual03 log, 68 FrameSync metric records were observed,
15 within armed unpaused intervals. PostStep sets the pending-write flag before
its event; normal FrameSync waits the worker and invokes the same registered-system
and dynamic-bone writer as the paused branch. No normal-only skip condition was
found. This connects observed ordinary simulation and normal writer execution to
the measured engine-bone writeback without inventing a synchronized renderer sample.

## Retained unsuccessful cases

Run130509-abc2e7 sent a bare race string instead of a typed Race form. Void ACK
did not transform either NPC. Run131612-051821 used the correct argument but
refused an actual valid transformation because the test wrongly required an
immutable Nord baseRace. Actual SetRace changes both current/base race fields;
original ancestry is retained separately and identity/baseForm/sex/weight remain
strict. Neither run armed the solver window. Both later exited C0000005 after
quarantined cleanup; cause was not established. Their failures and raw records
are preserved, not rescored. The corrected full lifecycle ended normally.

## CBPC — excluded from the working installer

The tested provider is 1.7.3, SHA-256
`4996c85ee00e051a903c15746e8686a2357b70c9b27957f8ef3026dbc62d5387`.
Actual run142827-3a903c completed human source capture and transformation (CLAW
status5→2), but the fresh provider log contained no constructors or updates for
any of the eleven selected wolf drivers. It continued updating human Things.
The failed case stopped before Refresh, save/load, motion windows or provider
Start/Stop/Reload calls. Normal exit 0 and restoration succeeded. One inherited
collection request incorrectly expected an FSMP log in this CBPC-only profile;
that absent-file collection error remains in the failed result.

The VM-facing display name also had reversible encoding damage while the log
contained correct UTF-8. Correcting that diagnostic join still finds zero wolf
drivers. Name-independent constructor counts corroborate the binding failure.
Exact public-interface analysis found parameter refresh, not a proven per-actor
rebind. No guessed refresh notification, global reload workaround or provider
private hook was added. Male CBPC remained unlaunched. Reproduction and API
records are retained in [the CBPC record](cbpc-rebind-20261113.md).

## Installer and source checks

The actual FSMP-only candidate has 47 members and 40 independent installation
plans: 2 male families × 5 female families × OBody on/off × None/FSMP. Body aliases reuse
identical sources; each selected destination has exactly one source. Both choices
share the core TRI files. No external DDS, provider DLL, developer source archive
or testing fixture is in the runtime ZIP. The actual builder receipt integration
and transitive FSMP source pins were repaired without changing produced runtime
bytes. The final package must be rebuilt from the matching clean source commit;
the inherited old source companion was rejected and requires a complete refresh.

Meaningful raw evidence is external under Builds/claw-fsmp-step-witness-20261113,
Builds/claw-fsmp-human-origin-lifecycle-20261113 and
Builds/claw-010-physics-release-20261113. These are local evidence locations,
not public downloadable assets. The current retained physics-case family contains 15 physical starts, including
all unsuccessful attempts. Only the shipping FSMP result is used as its motion
acceptance; excluding CBPC does not rescore its failure. Final archive/source
checks and publication readback are separate gates.

The full default Python source run passed: 407 unit tests (13 skipped), 187
physics tests and 82 existing VR-source tests (17 skipped). The latter is source
coverage, not a VR game run. Additional focused actual-transport and witness
parser/replay checks are recorded with their exact source receipts. No new game
was launched for the repository test port.
