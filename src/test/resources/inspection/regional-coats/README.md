# Four-pair coat comparison in Skyrim SE

The [palette and placement](pairs.json) use four stock Skyrim NPC bases. The
[scene runner](../../../python/integration/coat_regional_scene.py) creates
two disposable copies of each, keeps the first human and transforms the second.
It uses separated spawn lanes, checks skin and hair on the human copies, removes
the wolf copy's recorded equipment and holds the four pairs at the QASmoke wall.

| Pair | Hair | Skin |
| --- | --- | --- |
| Olda | Dark | Medium |
| Idgrod the Younger | Dark | Light |
| Argi Farseer | Blond | Medium |
| Angi | Blond | Light |

Compare Olda with Idgrod and Argi with Angi for skin. Compare Olda with Argi
and Idgrod with Angi for hair.

## Run the scene

Use a prepared Skyrim SE test profile with the regional-tint CLAW DLL and its
matching assets, Elegant Randomized, the inspection lighting, DevBench and
World Observer. Bind `PYTHONPATH` to the qualified Autotest source. The local
Autotest configuration needs a disposable profile, the four bases in
`fixtureActorBases`, their human and wolf races in `allowedRaceForms` and the
guarded `morph_race` binding for `Actor.SetRace`. Run the usual VFS and native
payload checks when preparing that configuration. The scene script checks live
actor and material identity through the admitted runner.

Keep the reusable bootstrap JSON in the local test directory. It requires
`schemaVersion` 1, `cell` `QASmoke`, and a `fixture` with the qualified
`saveStem`, `essSha256` and `skseSha256`. Its single step uses `tool` `platform`,
`args` `{"operation":"state.read"}`, and the assertion
`{"path":"world.ready","equals":true}`. Use the same bootstrap across scene runs.

```powershell
python -B src/test/python/integration/coat_regional_scene.py preview `
  --config '<local Autotest config.json>' --profile '<TEST SE profile>' `
  --scenario '<local QASmoke bootstrap.json>' --appearance '<candidate appearance directory>' `
  --coat-mode fixed
```

`preview` leaves the scene ready for manual inspection until Skyrim exits.
`check` returns to the runner for ordinary teardown. `preflight` checks
admission without starting the game. `fixed` records the automatic assignments
and then uses Valley Grey for all wolves. `automatic` leaves each automatic
coat in place for an end-to-end comparison. Use `--dwell 90` in a diagnostic
run to check for changes after the initial sample. The run directory contains
`claw-regional-scene.json` with the owned references and material observations.

## What counts as a pass

The technical check reads the surface texture, RGB and material alpha twice.
It does not sample the rendered frame. In the first owner review, all four
wolves reported Valley Grey before handoff. Later screenshots showed three
black wolves and one white wolf, so the rendered comparison failed. That run
has no material capture synchronized to the screenshots. For a follow-up,
sample the same four references and capture the frame together. Compare fixed
and automatic coats separately, using the earlier distinct Brown and White
fixtures as visible controls if they are present in the bootstrap.
