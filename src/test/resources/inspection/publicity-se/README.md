# SE reference photos

These two nonshipping scenes use the same lit wall bay in QASmoke. One copy
of each actor stays human. The second starts as an identical human and
transforms after the source readback. The camera and standing marks remain
fixed across the series. The script hides the HUD for capture and restores it
before the standard session shutdown.

## Automatic coat colour

The [regional coat fixture](../regional-coats/pairs.json) supplies the four
stock Nord bases in a two-by-two design. The saved photos follow fixture order.

| Photo | NPC | Skin group | Hair group |
| --- | --- | --- | --- |
| `coat-01.png` | Olda | Medium | Dark |
| `coat-02.png` | Idgrod the Younger | Pale | Dark |
| `coat-03.png` | Argi Farseer | Medium | Blond |
| `coat-04.png` | Angi | Pale | Blond |

Compare 01/02 or 03/04 for skin. Compare 01/03 or 02/04 for hair. The runner
confirms both copies' actual human colours and both material path fields
around each capture. The torso uses the skin-selected pattern. The head
and fur use the hair-selected pattern. Some patterns share individual DDS.
Idgrod is also photographed with only the room lights, with a single
neutral fill, and with all three fills. The applied coat and camera are
checked again in every lighting state.

For the 0.11.1 automatic black restriction, run the `black-gate` case with
`PublicityScene(session, appearance, black_gate=True)`. Use the paired
skin/hair inputs above and admit Anwen's Redguard base and race too. Olda and
Idgrod must use Valley Grey on the head and fur. Anwen has the same dark hair
and a deep skin tone, and must retain Valley Black. No actor in this case
receives a manual coat selection.

## Full coat gallery

Use the same release profile and QASmoke bootstrap, then call
`PublicityCoatCatalog(session, appearance).run('coat')`. The gallery retains
one copy of Angi and one transformed twin for all ten canonical Elegant
patterns, in serialized range order. It uses the room's original lights.
Every frame checks the requested and applied manual choice and the managed
material paths on the same wolf. Aliases share existing textures and are
not additional gallery entries.

## Light-coat morph transfer

Use the same stock NPC and measured weight within each family. Hod exercises
HIMBO belly, shoulder, bicep and tricep transfer. Angi exercises CBBE chest,
hips and legs. The baseline starts at zero for each tested slider. The expressive
variant applies the declared human values to both twins before transformation.
All wolves explicitly use Valley White. The front and profile shots share the
camera and standing marks, with a different subject heading. The runner checks
the selected CLAW matrix and reads each declared output through CLAW and RaceMenu.

Use `PublicityMorphSeries(session, appearance, coat).run_series(family)`
for the continuous comparison. It preserves the same two references
and takes front and profile views at zero, half and full stimulus. One
twin returns to human form before its next RaceMenu edit. The runner
requires actual human status and verifies that CLAW's own wolf key was cleared
before editing. `family` is `himbo` or `cbbe`. Choose a canonical coat ID from
the full gallery and hold it for the entire session.

## Execution

Use a disposable TEST SE Autotest session with the exact CLAW 0.11.0 release
payload (HIMBO/CBBE, physics None), original Elegant 4K Randomized, NeverNude
human builds with TRI data, the inspection lighting, RaceMenu and an admitted
DevBench/World Observer setup. Disable independent model, body and texture
writers such as OBody or the Elegant Model Swapper plugin for this scene.
Configure the owned QASmoke bootstrap and admit only the five NPC bases in
the scene data plus the Nord and WerewolfBeast races. The callback needs the
existing guarded `morph_race` binding to `Actor.SetRace`.

Invoke `PublicityScene(session, appearance).run(case)` after the QASmoke bootstrap
from the prepared Autotest run. Use `coat` for the seven colour and lighting
frames. Run `himbo-baseline`, `himbo-expressive`, `cbbe-baseline` and
`cbbe-expressive` in separate disposable sessions with the same asset and room
inputs. A temporary actor created after a same-base twin transforms can already
inherit the beast race. One transform per morph session keeps state isolated.

`appearance` is the effective release directory containing `CoatMapping.xml`
and `CoatLibrary.xml`. Each case records its 1920×1080 frames and a
`CAPTURE_COMPLETE` report with the material readbacks, input values, morph output,
placement and image hashes.
Inspect the actual frames for composition and technical image defects. Keep
the originals, installed dependency paths, saves and runner logs outside Git.
