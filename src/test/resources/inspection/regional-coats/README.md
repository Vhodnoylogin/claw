# Regional coat comparisons in Skyrim SE

The [palette and placement](pairs.json) use four stock Skyrim NPC bases. The
[scene runner](../../../python/integration/coat_regional_scene.py) creates
two disposable copies of each, keeps the first human and transforms the second.
It uses separated spawn lanes, checks skin and hair on the human copies, removes
the wolf copy's recorded equipment and holds the four pairs at the QASmoke wall.

| Pair | Hair | Skin |
| --- | --- | --- |
| Olda | Dark | Medium |
| Argi Farseer | Blond | Medium |
| Idgrod the Younger | Dark | Light |
| Angi | Blond | Light |

The two left pairs isolate hair at the same medium skin tone. The two right
pairs do the same for light skin. Compare Olda with Idgrod or Argi with Angi
to isolate skin with the same hair input.

## Five skin tones with one hair colour

The [five-tone palette](skin-pairs.json) uses five female stock Skyrim.esm
characters with the same BlueBlack hair colour, RGB `[20, 20, 24]`. Humans can
have different hairstyles. The wolf coats all use the same Grey body source and
ValleyBlack head and fur source, so the visible patterns are held constant for
the five-way comparison. The diffuse changes come from the human skin input.

| Left to right | Character | Skin RGB from Skyrim.esm |
| --- | --- | --- |
| Very pale | Idgrod the Younger | 221, 221, 221 |
| Warm beige | Olda | 185, 179, 170 |
| Medium rosy brown | Aia Arria | 143, 114, 101 |
| Tan | Seren | 113, 87, 68 |
| Very dark | Anwen | 67, 44, 33 |

Prepare the local appearance maps with `prepare_coat_harmonized_scene.py` and
pass `--palette src/test/resources/inspection/regional-coats/skin-pairs.json`
to both that command and the scene runner. Use `--coat-mode harmonized` and
`--generated-coats '<local appearance directory>/generated-coats.json'` with
the scene runner. Update the disposable profile admission to exactly those
five NPC bases and the Nord, Imperial, Redguard and werewolf races. Keep the
derived textures local and stage the prepared `texture-pins.json` paths into
the disposable MO2 profile before launching.

`skinComparison` records the five measured input colours and the shared hair
colour from both human instances of each base before any transformations.
The normal material readback verifies the actual path and bound diffuse resource
on all twelve wolf surfaces. With `--capture`, bracketed `lightTones.png` and
`darkTones.png` supplement the panorama, which is restored for inspection.

## Run the scene

Use a prepared Skyrim SE test profile with the matching CLAW candidate and its
matching assets, Elegant Randomized, the inspection lighting, DevBench and
World Observer. Bind `PYTHONPATH` to the qualified Autotest source. The local
Autotest configuration needs a disposable profile, the selected palette bases in
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
  --coat-mode discrete --capture
```

`preview` leaves the scene ready for manual inspection until Skyrim exits.
`check` returns to the runner for ordinary teardown. `preflight` checks
admission without starting the game. `discrete` checks the automatic choice
for each surface in the separate skin and hair palettes. `skin-pairs` is a
control for the earlier tint candidate with one explicit base per skin tone.
`fixed` records automatic assignments then uses Valley Grey for all wolves.
`automatic` leaves the earlier automatic tint choices in place. Use `--dwell 90` in a diagnostic
run to check for changes after the initial sample. The run directory contains
`claw-regional-scene.json` with the owned references and material observations.
On Windows, `--capture` requires Pillow with window capture support and an
owned 1920×1080 Skyrim SE window. It saves game frames locally with each frame
bracketed by material audits. It does not need to activate the game window.

## What counts as a pass

The technical check reads the surface texture, shader type, RGB and material alpha. Check
the PNGs separately to establish the visible result. In the first owner review,
all four wolves reported Valley Grey but the screenshots showed three black
wolves and one white wolf. A later run reproduced this with audits on both
sides of the frame. Matching material fields alone cannot pass the scene.
Compare fixed and automatic coats separately, using the earlier distinct Brown
and White fixtures as visible controls if they are present in the bootstrap.

## Softer local texture comparison

Use the same row, camera and light when comparing the harmonized and discrete
variants. The generator combines the verified skin and hair RGB from each pair
in OKLab. Skin sets the main lightness. A soft limit pulls extreme head and fur
tones toward it, with varying hair influence by material. The source material's
alpha is retained at the preview resolution. The weights operate per material.
An authored UV mask would be needed to control the transition within a material.

```powershell
python -B src/test/python/integration/prepare_coat_harmonized_scene.py `
  --installed '<local Elegant Randomized texture directory>' `
  --appearance '<discrete candidate appearance directory>' `
  --output '<new local preview directory outside Git>'
```

Stage the two generated appearance XMLs and the DDS destinations in
`texture-pins.json` only in a disposable TEST SE run. Use `--coat-mode harmonized`
with `--appearance` pointing to the output and `--generated-coats` pointing to
its `generated-coats.json`. The scene checks the exact source human colours and
bound per-actor DDS. The colour calculation runs offline. The scene binds those
local materials to the verified fixtures and captures the game rendering.
Keep generated textures local and out of the installer, repository and release.
