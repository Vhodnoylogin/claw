# Owned CBPC selective-response probe

`cbpc_probe.py` is a pure test plan/scorer. It does not install, launch, call
DevBench, reload CBPC, restore a previous physics state or qualify a release.
Its sibling FSMP module supplies tested World Observer parsing, incarnation/root
guards, inverse transforms, anchor calibration and the inspected skeleton node
inventory. The FSMP previous-state/binding protocol is deliberately not reused.

Use a fresh owned **born-beast** NPC with verified sex/race, current mesh and skin
influences, matching skeleton and sole CBPC motion ownership. Keep it 3D-loaded,
within the effective CBPC bounce range and under the existing bounded Session's
admission, per-mutation guards and teardown. Capture effective provider/config
hashes externally. This source does not prove their application in the game.

`prepare(reference, sex)` returns the exact snapshot query, node-scoped native
requests, 25-point two-cycle anchor offsets and **predeclared 0.85-second point
period, ±0.15-second diagnostic jitter**. Persist the plan before execution. The
three windows must have identical stimulus/cadence; the scorer also compares
corresponding actual producer-clock gaps. Do not change the declaration after
observing a slow run. Use the existing qualified anchor transport and cleanup:
Head for ears, Tails for tail, left/right PreBreast P1 for female P1. Prime the
private key, read actual +0.25/reset movement, and never write a driver transform.

Input `score(document)` schema:

```text
schemaVersion: 1
reference: current owned hex reference
sex: male | female
declaredPointPeriodSeconds: 0.85
baseline: raw World Observer snapshot
receipts:
  start:   one receipt per driver, in prepare().calls.start order
  stop:    one receipt per driver, in prepare().calls.stop order
  restart: one receipt per driver, in prepare().calls.restart order
stimulusBaseline: raw primed-zero snapshot
anchorCalibration: {moved: raw +0.25 snapshot, reset: raw zero snapshot}
windows: {active: 25 raw snapshots, stopped: 25 raw snapshots,
          restarted: 25 raw snapshots}
```

Each native receipt contains `request` (the exact generated Papyrus argument
object), fresh raw `before`/`after` snapshots and the original DevBench
`nativeResult: {called: true, returnedType: "none", returned: null}`. The actual
order is baseline → each Start receipt → stimulus baseline → calibration moved/
reset → active → each Stop receipt → stopped → each Start receipt → restarted.
All snapshots must advance and keep the same session, load epoch, actor/base/
incarnation, weight, sex, race and sampled root. Missing/uncertain/boolean native
results fail; they cannot be substituted with invented FSMP-style state bits.

Start/Stop use exact ConfigMap **left-hand node names**, not `CLAW_*` aliases.
They return no previous state or binding inventory. Starting a fresh test fixture
is explicit initialization; it cannot be claimed to restore an unknown previous
state. An uncertain completion stops the case and requires owned teardown, not a
blind replay. Cleanup outcomes remain separate retained Session evidence.

CBPC may write driver **local** transforms. Only unaffected torso/root and CME
local controls must remain quiet; CME world motion inherited from a dynamic
ancestor is allowed. Anchor calibration independently verifies actual world
movement including rotation/scale. The score measures inverse anchor world ×
driver world, so common inherited movement is insufficient. A stopped driver may
hold a nonzero displacement: discrimination uses within-window variation.

Only channels with response in both active windows above four noise floors and
stopped variation below a quarter of the smaller active response (or its floor)
are listed. Control drift or incomparable cadence leaves status `unconfirmed`.
`sampled-selective-contrast-observed` reports sampled contrast, with
`bindingState: "unknown"`, `physicsPhaseObserved`, `solverQualified` and
`contactQualified` still false. It does not establish every driver, contacts,
appearance, root recreation, transformation or reload compatibility, exclude
undisclosed direct driver writers, or prove public-source/binary equivalence.

After a fresh-beast contrast, human→beast/root-recreation is a **separate** case.
Actor refresh semantics in installed CBPC 1.7.3 remain unproved; no global
`ReloadConfig` production workaround or additional provider API is introduced.

```powershell
python -m unittest discover -s src/test/python/physics -p test_cbpc_probe.py
python src/test/python/integration/cbpc_probe.py '<retained-document.json>' `
  --output '<new-external-diagnostic.json>'
```

Synthetic fixtures test the scorer only and are never runtime evidence.
