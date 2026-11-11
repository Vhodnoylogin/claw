# Owned CBPC selective-response probe

`cbpc_probe.py` is a pure test plan/scorer. It does not install, launch, call
DevBench, reload CBPC, restore a previous physics state or qualify a release.
Its sibling FSMP module supplies tested World Observer parsing, incarnation/root
guards, inverse transforms, anchor calibration and the inspected skeleton node
inventory. The FSMP previous-state/binding protocol is deliberately not reused.

The separately declared `cbpc_pulse.py` path evaluates read-only response after
an anchor returns to zero. It requires the pinned XP32 immediate-parent paths,
both current and base werewolf races, exact per-node Start/Stop/Start completions
and every requested driver's own local **and** immediate-parent-relative motion.
A child merely inheriting a bound parent's motion cannot pass. Dynamic local
writes are CBPC outputs; independent torso/CME controls must remain quiet.
Void calls leave binding state unknown. This scorer has offline counterexample
coverage; no actual CBPC pulse run or release acceptance is implied.

## Owned pulse transport

`cbpc_owned_case.run(session, reference, sex)` executes the pulse case only
inside an already owned bounded Session. The caller must qualify a fresh
born-beast fixture, actual resources, provider ownership and live function
signatures before invoking it. The callback checks current/base race, sex,
incarnation, root and advancing raw observations. It calls only node-scoped
`CBPCPluginScript.StartPhysics(actor, node)` / `StopPhysics(actor, node)`;
both require exact completed void receipts. An uncertain Start/Stop stops the
case without replay, global reload or compensating provider calls. Original
state and binding remain unknown even when all pulse channels respond.

`owned_anchors.py` is shared with the FSMP callback. It encapsulates run-key
capture, individually guarded/journaled anchor mutations, zero-return read-only
sampling and original local-transform restoration. Only mass-zero Head/Tails
and female PreBreast P1 anchors are written. The pulse module declares each
family's offset before execution; P1 uses the smaller `.1` offset, ears/tail `.5`.
The FSMP callback retains its separate previous-state bool-array protocol.

Keep all test-source dependencies in the run's hash inventory:
`cbpc_owned_case.py`, `cbpc_probe.py`, `cbpc_pulse.py`, `owned_anchors.py`,
`fsmp_probe.py` and `fsmp_pulse.py`. The callback records small intent journals
and immutable raw observations under `cbpc-probe/`, then writes full `state.json`
and separate `cleanup.json` at case end. These are development test sources;
no gameplay archive or runtime provider is changed by their import.

The owning harness must call `cbpc_owned_case.dispose_fixture(...)` from its
own finalization path using the retained admitted baseline, including after a
failed case. This disables only that still-guarded disposable actor and verifies
actual disabled state plus explicit null crosshair. It restores no guessed CBPC
state. Keep ordinary Session shutdown/process observation afterward. A human-base
or replacement actor is never qualified by changing the supplied sex/race label.

```powershell
python -m unittest discover -s src/test/python/physics -p test_cbpc_owned_case.py
python -m unittest discover -s src/test/python/physics -p test_cbpc_pulse.py
```

## Retained moving-anchor probe

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
