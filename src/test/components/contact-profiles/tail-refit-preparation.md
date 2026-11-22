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
still needs a scoped write with cleanup and aggregate readback.
The archived coordinates are evidence for setup and carry no adaptive contact result.
