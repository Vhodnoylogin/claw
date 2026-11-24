# CLAW VR player and mirrors

This scene places a human reference on the left and its werewolf reference on
the right. A fresh Nord player, the human mirror and the wolf mirror start
with the same preset, body resources and RaceMenu morph values. The player uses
ordinary Beast Form. The NPC wolf uses the disposable actor fixture's separate
race change. Each NPC has its own base record so changing the wolf cannot change
the human mirror's race.

## Prepare the isolated case

1. Start from a fresh owned copy of `CLAW VR` in TEST VR. Use the real VR core
   0.11.0, matched SKSEVR/RaceMenu VR, VRIK, the matching 0.5.0 Body32 add-on
   and the existing `CLAWVRModelTopology` test capture. This is the body
   inspection arm. Select **None** for the independent physics options.
2. For the primary HIMBO arm, use **Nord male preset 1** and leave its weight at
   75. Use HIMBO 5.8 `malebody_0.nif`, `malebody_1.nif` and their linked
   `malebody.tri` as winning world meshes. Stage matching Nord hand/foot meshes
   and skin if the profile otherwise mixes body versions. For the independent
   3BA arm select **Nord female preset 1** at weight 50 and its built 3BA 2.48
   `femalebody_0.nif`, `femalebody_1.nif` and `femalebody.tri`. Keep OBody and
   other morph writers out of this profile. Before launch, pin and resolve the
   exact NIF/TRI winners and verify nonempty deltas for both source channels.
3. Generate the ESP from the installed VR `Skyrim.esm` and the exact
   `MorphLinks.xml` selected in the core package. Keep generated files out of Git.

   ```powershell
   python -B src/test/resources/inspection/vr-addon/player-mirror/prepare.py --master <VR-Skyrim.esm> --matrix <installed-MorphLinks.xml> --out <fresh-build-dir> --variant himbo
   ```

4. Give only the generated ESP to the copied profile. Resolve the file's two
   runtime FormIDs and freeze `native_session.nativeBindings` with
   `run.native_policy({'human': runtime_human_base, 'wolf': runtime_wolf_base})`.
   HIMBO uses local IDs `0x800` and `0x801`. The 3BA alternative uses `0x802`
   and `0x803`. Use the copied profile's effective load order and verify both
   resolutions from the actual game. Each variant's ESP contains two new NPC bases.
5. Use the owned VR launcher with ordinary character creation. Call
   `room.position_player(session, 'mirror')` using [test_room.py](../test_room.py)
   to enter `QASmoke`, then call `run(session, 'himbo')`. Both mirrors are placed
   on measured points in the west row and the scene records their stable coordinates.
   `Mirrors.stage()` and `Mirrors.transform_player()` are separate when an
   operator wants to inspect the morphed human before the cast. Keep the game
   open with the owned launcher for that inspection interval.

## Check the scene

- Check both copies while everyone is human. The native trace compares loaded
  identity, head parts, sampled face sliders/presets, height, weight and actual
  skin/hair tints. Slot 18 is recorded separately because the stock preset can
  return an unset sentinel on the player. A failed match of the supported face
  values blocks the transformation. Compare the visible face and skin in the
  headset as a separate result.
- The scene writes only its own RaceMenu test key for the two strong source
  values shown in [scene.json](scene.json). It reads each value back and requests
  a model update on all three subjects. Look down before the cast to see the
  human base. The normal CLAW conversion reads those inputs in Beast Form.
- The live player and right-hand NPC must have the same nonzero CLAW and
  RaceMenu wolf morph values. Record any difference in automatic coats before
  applying one shared installed coat to both disposable subjects for comparison.
- As the wolf, look down at the abdomen, chest, legs and hands. Compare their
  proportions with the wolf standing on the right and the human on the left.
  Sweep the head and hands across ordinary viewing angles. Record visible seams,
  clipping, placement and tracking separately from the native topology captured
  in `claw-vr-player-mirrors.json`. The same scene records both native view
  inventories even if one lacks a loaded root. Use the headset pass to verify
  visible deformation and tracking.
- The normal transformation expires after the vanilla duration. Retire the
  disposable world without saving. For an uncertain write, preserve the receipt
  and retire the attempt without replaying actor creation or Beast Form.
