# Male12 offline physics readback

`male12_readback.py` is a pure component-local adapter for the exact original
male ear/tail plus neutral-anatomy composition. It accepts twelve dynamic roles
and three kinematic anchors. `WWD 2` attaches to `WWD 1`; `WWLB 1` and `WWRB 1`
attach to `WWD 2`. It changes no standard male9/female11 role list, parser,
motion threshold, package gate or game state.

The source graph is parsed by the existing component `compose_motion.inspect_xml`
and checked against the original combined XML SHA-256 `7cb169385c37b28038643c406c07d6b91937672b872c908420e2172822647d8e`.
The native configuration reader reuses the existing witness validator, body
type checks, float32 Spring2 comparisons and motion scorer. Named scene rows
must identify the same actor/root and match all fifteen solver poses uniquely.
Mass/inertia and linear-limit/stiffness scaling follow the existing uniform
scale contract for the observed float32 1.13 fixture. The scene sample is a
quiet spatial bracket, not a synchronized render or physics frame.

`evaluate_configuration` requires a real named WORLD observation and two
advancing, unchanged schema-4 SE native solver windows. It checks the full
directed constraint catalogue, scaled mass/inertia and observed Spring2 fields.
Frame transforms and equilibria remain authored XML declarations because this
native schema does not expose them. `evaluate_motion` reuses the existing
same-step immediate-parent movement check with its unchanged default floors.
Neither function grants direct provider ownership, collision, deformation,
rendering, lifecycle or runtime acceptance.

## Retained failed case

The small authored metadata file `male12-retained-20261113.json` pins the six
consumed archive documents and four actual candidate files. Raw observations,
logs, NIF/TRI and provider files remain local under `Builds/` and are not copied
into source control. Replay captures these bytes before evaluation and checks
them again afterward. Its report also pins the consumed current reader sources.

Run from the CLAW repository with a new external output filename:

```powershell
python src/test/components/adult-anatomy/male12_readback.py replay `
  --case-root 'D:/Skyrim VR Modding/Builds/claw-graphless-fsmp-anatomy-diagnostic-20261113-04' `
  --candidate 'D:/Skyrim VR Modding/Builds/claw-fsmp-anatomy-compose-20261112/candidate-01/candidate' `
  --output 'D:/Skyrim VR Modding/Builds/claw-male12-replay-20261122-01.json'
```

Exit zero means the replay reproduced the archived diagnostic exactly. The
historical run `20261113-064151-968880` remains **failed**: all twelve drivers
lacked the required selective contrast and observation timing was not comparable.
The binding previous-state arrays passed, but those arrays do not prove motion.
The scene reference protocol uses the original ultimate-anchor contrast, retains
immediate-parent metrics separately and makes no independent child-joint claim.
The archive has no current schema-4 solver/constraint bracket, so direct joint
configuration readback is explicitly **unavailable**, rather than inferred from
its console output or successful toggles. No failed result is rescored as a pass.

For a separately collected current quiet bracket, require all actual inputs:

```text
python src/test/components/adult-anatomy/male12_readback.py readback
  --xml <exact-combined-XML> --world <named-WORLD.json>
  --native-before <native-schema4-before.json> --native-after <native-schema4-after.json>
  --reference <owned-actor> --base <owned-base> --pid <process> --nonce <window>
  --output <new-external-report.json>
```

This command only reads supplied files. It supplies no collector, activation,
installation, launch permission or replacement for independent provider/VFS
admission. Missing observations are an error. A configured rig is separate from
its measured movement and from any anatomy collision implementation; the
original combined XML contains no collision shapes.

## Focused checks

```powershell
python -m unittest discover -s src/test/components/adult-anatomy -p test_male12_readback.py -v
```

Pure tests use explicitly synthetic native bodies and named poses. The retained
archive replay is opt-in; set **both** `CLAW_MALE12_CASE_ROOT` and
`CLAW_MALE12_CANDIDATE` to the two directories above before that command.
Selecting only one, missing files or changed pins fails. Without either input,
the actual-case test reports a skip, not actual evidence coverage.

## Neutral contact fit

Run `visibility_probe.py` in background Blender with the same explicit NIF,
skeleton, generator and PyNifly as the neutral visibility check. Add
`--fit-contact --primary-capsules 4` after Blender's `--` separator. Repeat
with `--primary-capsules 1` and a new external report to compare budgets.

The probe uses the existing body's five-ray parity mask to select exposed
vertices. It fits in the three actual driver-bone frames, rounds the output
to the attachment's float32 fields, then checks all selected vertices against
the resulting capsules. Fully exposed triangles supply sampled distances in
both directions. It also measures the capsule samples beyond the torso and
reports triangles that cross the exposure boundary separately.

The retained three-driver and combined twelve-driver meshes produced identical
fit data. With four primary capsules, the largest sampled external distance
to the primary exposed patch fell from 3.3121 to 1.6424 owner-local units.
Each lateral region retained one capsule. The six-capsule candidate covered
all 107 exposed vertices and the 144 fully exposed triangles in the sampled
rest pose. The particular geometry, pose, body parity rule and finite surface
samples limit the result. Provider attachment, pose following and actual
contacts still require separate observations.
