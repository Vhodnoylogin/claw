# CLAW VR add-on 0.5.0 inspection scene

[Scene inputs](scene.json) define the operator checkpoints and the controlled
profile changes for this nonshipping inspection. They are consumed as a run
sheet. The existing runners cover the listed individual diagnostic arms.

## Prepare one disposable TEST VR session

1. Use the dedicated TEST VR instance and the current `CLAW VR` source. Assign a
   fresh copied profile to each independent case. Use `New Game` in the pinned
   Realm of Lorkhan setup. Verify the live cell editor ID, the player reference
   `0x14`, base `0x7`, sex and owner handle. `0x0A01A5C6` is the observed cell form
   in the retained load order. Freeze the first stable standing root in that
   cell as the room anchor. Use that floor position and neutral HMD and hands
   for all comparisons. Re-measure the available reach at run time.
2. Pin Skyrim VR, SKSEVR, RaceMenu VR/SKEE, XP32, the installed core ZIP and DLL,
   the exact body candidate, both TRI families, the MO2 load order and the
   controlled overlays. Build and read back the package against the selected
   core archive. Obtain visible textures from the official installed Elegant
   files. The existing TEST VR Randomized 4K reference has ten PlayerOnly base
   and 100 Randomized textures with the Coop plugin inactive. Reconcile the
   actual winners after every profile change. [VR body builder](../../../../main/components/vr-body/README.md)
3. Before starting, use Morphbench on the same NIF, TRI, skeleton, collision
   configuration and optional motion XML. Retain the target bones, slot
   geometry, selected morphs, rig version and positions. For virtual tracking,
   verify the admitted driver and neutral head/left/right readback. For manual
   use, verify headset output and safe standing reach before transformation.
   Record the mapped collector DLLs separately from optional gameplay providers.
4. Keep the historical profiles, fixture captures and source saves immutable.
   The current owned profile supplies the runtime FormIDs and process identity.
   Retain the current run's roster, VFS pins and native log even if the subject
   aborts before a checkpoint.

## Same-character human and wolf checkpoints

Use a fresh male Nord reference for the existing automated Body32 arm. The female
Nord reference and the HIMBO/CBBE weight-70 contrasts in `scene.json` need fresh
admitted operator runs. Before each cast, capture the actual human body family,
weight, human morphs, face traits, hair and skin that the selected matrix reads.
Evaluate the expected named wolf outputs from the exact installed matrix. Pick a
normal human morph with a nonzero output on that build, such as a HIMBO body
channel or a CBBE breast channel. Retain the chosen input and expected result.
Use this human-origin case to verify mapping. Use separately staged test-key
changes to isolate collider refit.

| Checkpoint | Record and inspect |
| --- | --- |
| Human baseline | Standing pose, race, sex and weight. Look down and confirm ordinary hands in the headset. Record the active and buffered views, current materials, source traits and effective human values. |
| Ordinary transformation | Wait for the Companions initializer to reach stage 1 and run. Use the ordinary Beast Form power once. Wait for the wolf race and for both startup effects to clear. Confirm the same actor and a valid CLAW target. |
| Body in headset | At the same standing anchor, look down at hands, chest, torso and legs, then turn the head left and right. Check camera clearance, consistent hand tracking and visible material. Capture native route, model, geometry ownership and cull separately from the operator's headset result. |
| Wolf morphs and coat | Read the loaded NIF/TRI route and actual named wolf values. Compare with the frozen expectation from the human baseline. Recheck after a model refresh or reroute. Record body/head material binding and outcome after dwell alongside the headset observation. |
| Contacts and motion | Verify the selected arm below. Repeat supported contact checks with each tracked hand. Record exact missing axes, bones, views, or reach separately. |
| Human return | Let the ordinary transformation end without `SetRace`. The stock `PlayerWerewolfQuest` starts with a 150-second duration. Keep the world unpaused and budget separately for transformation, expiry and human post-effects. Verify the original human race, gear and body route, cleared wolf morphs, and loss of any enabled contact and FSMP registrations. Record game exit, collection and exact profile restoration. |

Use the same neutral placement and field of view for both body settings. Run the
separate save/load case only after the no-save lifecycle passes in a disposable
save directory. Recheck the actor and model after loading the owned save.

## Provider and installer controls

Prepare the `core-control` and `static-body` arms first. Then isolate contact and
tail motion in separate profiles. Use the combined arm after both individual
paths are qualified. Test Off with the applicable provider loaded to distinguish
the option from provider absence. Also record launch/body availability when an
optional provider is absent. The existing core **None** choice suppresses core
motion during the initial isolated VR arms. Pin any final add-on switch and its
actual installed payload before running it. The 0.5.0 target keeps optional FSMP
on the five tail links and tests ear, muzzle and chest interaction through
contact. Historical XML with ear or breast motion is its own control.

| VRIK | HIGGS | Retained evidence and next check |
| --- | --- | --- |
| Off | Off | `20261124-175324-4213ef` completed ordinary Beast Form and the world diagnostic on core 0.11.0. Use this arm as the fallback control. |
| On | Off | `20261124-180301-0e5e1e` completed the core diagnostic. `20261124-181745-0ebb2c` loaded the actual male fixed-profile 0.5.0 body in the world and verified the same nonzero `CLAWTorsoGirth` value from both CLAW and RaceMenu. |
| On | On | `20261124-180753-e45674` completed the core diagnostic with both providers loaded. Check HIGGS hand contacts and headset visibility separately. |
| Off | On | `20261124-180514-37822d` completed the core diagnostic with HIGGS alone. Qualify add-on body and hands separately. |

All four core runs covered the player world graph. The exact body run reported
an unloaded first-person armor graph. Headset presentation, applied vertex
displacement and natural return still require separate captures.

An absent HIGGS callback leaves the post-HIGGS collector unavailable. Use the
admitted topology and ordinary World Observer for the fallback path. Keep the
observed fallback scope separate from qualified body display, solver contacts
and optional HIGGS functionality. PLANCK is outside this scene's provider matrix.

## Contact checkpoints

- Keep the head and opposite controller steady while the tracked hand approaches
  each named region. Use the actual latched bone transform to project the
  fitted bank into the room. Calibrate the wand offset using the staged source
  sphere. The reference uses local center `[0,-6,-2]` and radius 3 game units
  for the left wand. Use the actual configured right-hand geometry for the
  mirrored check.
- Use unattached, near, far, near again and detached holds. In the isolated
  stock CBPC reference, seek at least 0.75 GU clearance or overlap and score the
  exact actor/bone event in the corresponding hold. Verify silence in the
  unattached, far and detached holds. The installed body and collider bank must
  remain attached to the same actor. Return to neutral after each target.
- For the refit arm keep the same controller pose over neutral, morphed and
  restored inputs. Keep the three witnessed effective TRI samples, their
  matching full native ACK banks and the independently observed hand pose.
  Compare signed clearances of the complete tested bone bank at the same
  observed transform. Retain the event window and cleanup. A provider's
  bone-level callback identifies the group. The signed gap and operator note
  identify the specific surface tested.
- `scene.json` lists exact reference slots for both ears, muzzle, upper chest,
  female breast and tail. The existing equipped automated control covers the
  first left ear bone and `TailBone02`. Right ear, muzzle, upper chest, female
  breast and the right-hand counterpart need their own isolated collector or
  explicit operator observation; keep the latter labeled manual. Previous
  stock-player left-ear attempts reached the world model, then refused the
  contact hold because the target skin bone could not be matched to its live
  palette. Establish that match before using scope-specific contact assertions.

## Reuse and report

- [Split Body32 probe](../../../components/vr-body/probe_player_dispatch.py)
  is called by an existing admitted executor session. It casts Beast Form,
  records stock/equipped/restored topology and retires the temporary outfit.
  It currently expects the male reference in the pinned Realm cell. Use the
  [paired replay](../../../components/vr-body/verify_dispatch_markers.py)
  for a schema-8 capture plus independently resolved fixture forms. Use the
  [Hands33 scorer](../../../components/vr-body/hands33_readback.py) for its
  distinct older diagnostic. Its raw inputs are human, stock wolf, equipped
  wolf and restored wolf.
- [Waypoint retargeting](../../../components/contact-profiles/retarget_player_contact.py),
  [fixed equipped contact replay](../../../components/contact-profiles/verify_player_contact.py),
  [morph-refit replay](../../../components/contact-profiles/verify_player_morph_contact.py)
  and [NPC tail preparation](../../../components/contact-profiles/tail-refit-preparation.md)
  have separate exact input contracts. Reuse the appropriate arm. Use the
  [native FSMP guide](../../../python/integration/fsmp_probe.md) to keep
  skin attachment, provider registration and movement evidence distinct.
- Reuse setup from archived Builds packets `claw-vr-ear-palette-20261124/human-firstperson-control/PLAN.json`,
  `claw-vr-ear-palette-20261124/wolf-hands33-live/PLAN.json` and
  `claw-vr-body32-vrik-split-20261124/run-01/PLAN.json`. Preserve their inputs
  as references. Re-pin the current profile, game, assets, providers and
  fixture before starting a fresh disposable session in TEST VR.
- The executor's success means the collector finished. The task verdict still
  comes from the stated checkpoint. Save topology, transforms, fitted ACK,
  callbacks, material observations and headset notes with the owned run ID.
  Compare the exact Morphbench evidence. Retain the Morphbench, MO2 Bridge and
  Autotest records in separate local collections outside Git for batch handoff
  when requested.
