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
morph states on that actor. Once `BeginNpcTailRefit` is ready, the test witness's
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
without saving. Capture the full 15-node `BeginNpcTailRefit` pose and effective
morph vector at each hold before and after its World Observer samples.

Use schema `claw-vr-tail02-refit-reads/3` for the raw index manifest with
the fixed driver publication, status receipts and a hash of the capture's
original ledger prefix. The verifier still reads schema 2 for older evidence
without driver custody.
Record the registry description plus initial presence/value reads under
`morph.describe` and `morph.initial`. Put each transition's change, update,
presence and value indices in `morph.apply` and `morph.restore`. Each phase's
`event` indexes the ready `ReadPhysicsSnapshot` reply. The verifier binds
these replies to the original fixture, pose sequence, native token and
exact slot bank. The one-node fixed-sphere stock witness cannot supply
those receipts.

The archived coordinates are evidence for setup and carry no adaptive contact result.

## Detached subject staging

Run `freeze_tail_refit_subject.py --help` for the file inputs. Use the original
stock r03 case directory, the paired native fit receipt and the dedicated
tail-refit pose build receipt. Supply the prior stage receipt for the two
Papyrus facades that match the retained Distribution DLL. Supply the authored
VR fit, r03 waypoint replay with `--max-travel-metres 0.40`, XP32 werewolf
skeleton and RaceMenu assets.
The script compares both archived carrier NIF endpoints and the TRI against the
authored fit, and stages the exact reviewed CBPC overlay, NPC fixture and current
native/Papyrus interfaces. The output records file pins and the archived waypoint
separately from runtime checks. It is detached staging. Recheck installed VFS
winners and loaded identities under the actual game session.

The bounded replay proposes about 0.397 m of travel with 1.73 GU of neutral
separation and 1.66 GU of morphed overlap. A runtime host must qualify and read
back this move, then confirm clearance for the active scene. The archived static
setup defines the target group with no declared shapes and the old run confirms
functional detachment. The native provider's internal shape inventory was not
observed in that run.

## Capture from the admitted VR fixture

The owning run prepares the disposable actor, loaded-module pins and a clean
native Distribution session with the automatic collider host disabled. It
also supplies the calibrated reference pose for the same loaded actor, the
three acknowledged probe pairs, and the exact owned driver instance. The
archived candidate reaches tracking Y = 0.817 m. The previous 0.90 m floor
excludes it. Use a separately admitted movement envelope or choose a new point
that meets the original envelope and both measured geometry margins.

The CLAW runner uses bounded calibrated moves and independently measures
arrival before issuing the single final 30-second logical hold. The capture
needs at least 28 seconds after admission and reserves one second before
the fixed command expires. The 30-second native pose lease starts at the
dedicated opening. The caller reserves time after capture for the return to
neutral and then for executor restoration. The recorded capture verifies the
original driver ACKs through the sealed read, before the neutral return.

```python
from run_tail_refit import Capture
from verify_tail_refit import Subject

subject = Subject(game_pid, actor_ref, actor_base, fixture_cell, generation)
capture = Capture.from_files(
    session.tool, session.dir / "steps.jsonl", subject, vr_profile, fixed_bank,
    deadline=capture_deadline,
)
index, verdict = capture.run_calibrated(
    owned_fixture_receipt_sha256, approved_world_waypoint,
    state=session.state, reference_frame=restored_reference_command,
    reference=reference_observation, probes=measured_probe_pairs,
    driver_instance=owned_driver_instance, limits=approved_movement_limits,
    restore_deadline=neutral_return_deadline,
)
```

Save the returned index and verdict next to the original log. Sample zero
arms the pose listener before native registration. Each evidence sample
is requested afterwards, so the native snapshot event must precede the
phase's pose bracket. A completed capture confirms unregister, native
session retirement, pose witness retirement and the detached control. An
interruption or refusal leaves the outer runner responsible for retiring the
isolated game without saving. Loss of driver ownership or an unconfirmed
mutation stops further case commands. Preserve the executor's independent
process exit and restoration records alongside the capture result.

The fixed-sphere replay supplied all 16 original control frames to the new
observer gate. Each failed the adaptive separation/overlap criterion under
the original controller command.
