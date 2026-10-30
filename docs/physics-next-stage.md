# Physics next stage: bind the collider model to the chosen body resources

The existing automatic pipeline already observes effective native SKEE morphs,
samples independent NPC weight, fits schema-3 capsules on a bounded worker and
rejects stale snapshots before the finite Papyrus host appends. Its defaults
remain disabled. The immediate reproducible gap is resource agreement: the
retained 128-slot ear/tail/female-P1 model was built for earlier anatomical-split
bodies, while the frozen 30 October core contains different body and TRI bytes.

`physics/preflight.py` now checks that gap without running or installing anything.
It requires a current-vector independent-weight model, validates its identity,
and compares seven explicitly bound files to the model's declared source pins.
It regenerates and compares the **whole** native model header and
`CLAWPhysicsData.psc`, including numeric support, ordered morphs, reserved indices,
slot order and female-only P1 gates. It also audits an explicitly supplied
baseline provider snapshot and requires a nonempty `cbp.dll` in that snapshot.
That presence check establishes no DLL version, behavior or source equivalence.

Resource roles are explicit because the fitter accepts arbitrary filenames.
There is no basename/hash inference or first-match selection. The external
bindings JSON has `schemaVersion: 1` and a `resources` object with exactly these
keys: `maleNif`, `maleWeight1Nif`, `maleTri`, `femaleNif`, `femaleWeight1Nif`,
`femaleTri`, `skeleton`. Each value contains exactly `modelSourcePath` (the exact
string from one model `sourceInputs` entry) and `actualPath` (the supplied file,
absolute or relative to the bindings JSON). Each role needs its own source and
actual path, even when both endpoint files contain identical bytes. Duplicate
pins, missing roles and unrecorded source paths fail. Role assignment is the
caller's declaration, not an independent NIF or armor-binding reconstruction.

```powershell
python physics/preflight.py --fitted-capsules '<fitted-capsules.json>' `
  --resources '<external-resource-bindings.json>' `
  --native-header '<selected-physics-fit-model.h>' `
  --host-data '<selected-CLAWPhysicsData.psc>' `
  --provider-snapshot '<baseline-SKSE/Plugins-snapshot>' `
  --out '<new-external-evidence-directory>'
```

The provider input is the baseline before adding CLAW's intended motion configs;
including those configs correctly reports existing private-alias ownership.
This uses the existing scanner and preserves its limits for XML selection,
archives and effective runtime bindings. Omitted resource/source/provider inputs
remain explicit blocking findings. The report records every consumed file's
size/hash and the provider inventory; final rereads catch changes or added files.
Existing, source and live game/mod destinations are refused. Nothing is copied
into a game or mod manager.

Exit `0` means `offline-inputs-matched-runtime-pending`; exit `2` means missing,
invalid or mismatched offline inputs. The output includes `physics-preflight.json`
and regenerated expected sources. Failure retains
`FAILED-unverified-do-not-install`. Every result keeps `runtimeQualified`,
`gameValidated` and `releaseReady` false. Schema-3 identity deliberately excludes
`sourceInputs` so a proven input-only rebase can preserve the numeric model;
editing those pins alone does not prove that new geometry has the same support.
This preflight compares declared pins and sources, without independently
reconstructing or approving their geometric derivation.

The 30 October offline evidence is retained outside Git under
`Builds/claw-postrelease-20261030/physics/`:

| Run | Result |
| --- | --- |
| `original-final020-preflight/physics-preflight.json` | Original seven resources, whole header, whole host data and retained provider baseline agree; runtime remains pending. |
| `frozen-core-preflight/physics-preflight.json` | All six frozen-core body NIF/TRI files differ from the model's pins. Existing XP32 bytes match. Header/host/provider agreement does not resolve the geometry mismatch. |
| `preflight-runs.json` | Exact external bindings, invocation arguments and exit codes for both runs. |
| `physics-tests.log` | All 106 offline physics tests passed, including eight preflight regressions and their mutation/missing-input cases. |

The source model is `final-020-stable-weight-P1-contact`: 128 slots and 19 ordered
morphs, identity
`CLAW.Physics.CurrentVector.e1ea23b3f3203a242379fdb4c7c64c78f7c2a1c646297fa809726cdc24cf016e`.
The frozen-core comparison reads the retained repository release resources,
not the live installation. The provider snapshot is retained historical evidence,
not a newly observed process configuration.

Next, choose the actual body/weight/TRI candidate after shape work. Reconstruct
support from those exact files with the existing XP32 skeleton. A changed
physical surface needs a new fit and measurements; use `rebase-contact-inputs.py`
only when its full oriented triangle/base/weight/TRI comparison proves the
physical support unchanged. Generate matching native and host artifacts and
rerun preflight before preparing any game trial.

Game acceptance still needs actual armor/race/VFS bindings; loaded provider/API,
single-writer and reserved-index qualification; compiled DLL/PEX provenance;
effective-morph/model-update ordering; lifecycle cleanup/reset checks; and node
traces plus visible ear/tail/P1 motion/contact with negative controls, both sexes,
weight/morph extremes and return to neutral. Fur following, animated poses,
scale, HIGGS/PLANCK and close-contact quality receive no new acceptance here.
