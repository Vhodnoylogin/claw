# TailBone02 controller preparation

The rest-pose search in `prepare_tail_refit_contrast.py` proposes a point in the
bone's frame. A controller held still in the room sees an animated bone. Run
`prepare_tail_refit_waypoint.py` to project both complete four-slot banks from
the retained basis into the recorded world frames.

```powershell
python src/test/components/contact-profiles/prepare_tail_refit_waypoint.py `
  --restored <stock-RESTORED.json> --evidence <stock-cbpc-contact/evidence.json> `
  --steps <stock-steps.jsonl> --basis <TAIL02-FIXED-SPHERE.json> `
  --out <new-external-waypoint-report.json>
```

The tool uses the original unobstructed and detached holds, both with the
same tracked left wand pose. The original stock command and subsequent world
readback corroborate the recorded three-axis projection. The predicted point
maximizes the worst gap across both banks and the observed frames, on a
uniform grid. Clearance is computed along the straight control path with
head/right held fixed. A grid cover bound checks the old stock-run controller
envelope independently of the proposed point.

In run `20261122-133309-807e55`, the archived controls support about 2.29 GU
of both separation and overlap at the proposed point. Reaching it would
require about 0.55 m of controller travel. The old 0.30 m envelope cannot
produce the required 0.75 GU margin for those recorded poses. The candidate
coordinates need their own live movement and geometry readback. The original
case reported the expected single-slot callbacks and an abnormal game exit.

Before a future adaptive capture, establish the same actor and actual native
model, return tracked controls to neutral, publish one reviewed fixed command,
and require the World Observer to show both margins at the reached point.
Use the currently loaded actor's original model and recapture all three
morph states on that actor. Once `BeginNpcContact` is ready, the test witness's
`ReadPhysicsSnapshot` can retrieve the matching actor's
`CLAWPhysics_Observation` token after explicit Distribution registration.
Check `SnapshotCurrent` before reading each bank. Stock r03 neither stages
this witness extension nor drives the RaceMenu morph. The adaptive scenario
can use `tail_refit_morph.run_states` with the existing typed Papyrus call
bridge and the owned actor guard. The helper first checks the runtime
RaceMenu function signatures and absence of its private key. It sets only
`CLAWTailLength` under `CLAWTest.TailRefit`, requests model updates, and
clears the one key afterwards. A write without confirmed completion ends the
trial without replay; the owning harness must retire that disposable game
without saving. Capture the full 15-node `BeginNpcContact` pose and effective
morph vector at each hold before and after its World Observer samples.

Use schema `claw-vr-tail02-refit-reads/2` for the raw index manifest.
Record the registry description plus initial presence/value reads under
`morph.describe` and `morph.initial`. Put each transition's change, update,
presence and value indices in `morph.apply` and `morph.restore`. Each phase's
`event` indexes the ready `ReadPhysicsSnapshot` reply. The verifier binds
these replies to the original fixture, pose sequence, native token and
exact slot bank. The one-node fixed-sphere stock witness cannot supply
those receipts.

The archived coordinates are evidence for setup and carry no adaptive contact result.

## Capture from the admitted VR fixture

The owning run prepares the disposable actor, loaded-module pins, a clean
native Distribution session with the automatic collider host disabled, and
one acknowledged fixed controller command. The capture never publishes
another controller command. Pass the fixed command's conservative deadline
and the original executor step path to the CLAW-specific runner:

```python
from run_tail_refit import Capture
from verify_tail_refit import Subject

subject = Subject(game_pid, actor_ref, actor_base, fixture_cell, generation)
capture = Capture.from_files(
    session.tool, session.dir / "steps.jsonl", subject, vr_profile, fixed_bank,
    deadline=hold_deadline,
)
index, verdict = capture.run(owned_fixture_receipt_sha256)
```

Save the returned index and verdict next to the original log. Sample zero
arms the pose listener before native registration. Each evidence sample
is requested afterwards, so the native snapshot event must precede the
phase's pose bracket. A completed capture confirms unregister, native
session retirement, pose witness retirement and the detached control. An
interruption or refusal leaves the outer runner responsible for retiring the
isolated game without saving. An unconfirmed mutation is never replayed.

The fixed-sphere replay supplied all 16 original control frames to the new
observer gate. Each failed the adaptive separation/overlap criterion under
the original controller command.
