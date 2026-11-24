# Stationary VR wolf collider inspection

The disposable TEST VR fixture equips a male werewolf with colored outline
geometry for all 120 active capsules on 25 nodes. The single-node CBPC groups
use both controller spheres. Use the other VR inspection scene for first-person
body and shape comparison.

| Color | Capsule area |
| --- | --- |
| Gold | Both ears |
| Green | Muzzle and head |
| Violet | Tail |
| Cyan | Chest and trunk |
| Orange | Arms and forepaws |
| Pink | Legs and hind paws |

## Build and preflight

From the repository root, run:

~~~text
python -B src/test/resources/inspection/vr-addon/collider-showcase/stage.py --profile <fitted-capsules.json> --fixture <test_CLAW - VR CBPC Contact Fixture.esp> --tuning <CBPConfig_CLAWCBPCBench.txt> --skeleton <werewolf XP32 skeleton.nif> --pynifly <PyNifly addon> --morphbench <Morphbench checkout> --out <new detached directory>
~~~

The input hashes in the builder admit the rebuilt CLAW 0.11.0 stock-world
profile and the previously qualified bounded male contact fixture and CBPC
tuning. Use the exact pinned wolf body, RaceMenu VR provider and skeleton in a
fresh profile. Keep the standalone CBPC provider installed. Stage the generated
mod so the four listed CBPC configs and authored scene assets win.
Disable competing CBPC overrides for the run, including the adaptive CLAW
physics host, and select the core **None** motion option to isolate contacts.
Use the existing local provider setup and full profile restoration.

The builder computes weight 50, neutral TRI geometry, then converts the bank
to Float32 once. That bank supplies both the CBPC text and wire geometry.
Morphbench builds the displayed capsule surface. The harness tests that the
surface is on the fitted capsule and that all emitted vertices, skin owners,
weights and six emissive material colors survive NIF reread. The offline
receipt pins the body inputs, exact staged files and this tool's sources.
The 120 outlines contain 17,216 triangles. They never generate collision.

## Prepare the live scene

Use the owned VR launcher with its normal New Game bootstrap. After verifying
VFS and gameplay readiness, invoke the shared [room setup](../test_room.py)
to enter `QASmoke`, then spawn the wolf at the fixed west-floor point.

~~~python
room.position_player(session, 'collider')
prepare(session, cell_form=int(room.CELL, 16), floor_position=room.COLLIDER_WOLF,
        stage_receipt=receipt_path)
~~~

The runner resolves the exact normal-index fixture base and overlay item
through typed game calls, admits only a newly created dynamic wolf with the
expected race, sex and weight, applies the stationary controls and positions
it facing the player. It verifies that the actor root remains within
0.15 game units and checks the slot 60 wearable through show, hide and
show-again. The final state leaves the wires equipped. The on-disk receipt is
claw-vr-collider-showcase.json in the owned run directory. Retire a disposable
game with any uncertain write through the owning launcher.

## Headset acceptance

1. Stand at the review anchor. Walk around the wolf, confirm the body remains
   visible and inspect all six colored areas, including both ears and the tail.
2. Approach a surface with each real controller, hold briefly on the surface,
   then withdraw. Check both ears, muzzle, chest and tail first. Keep the
   opposite controller away. Compare the visible wire boundary with actual
   movement or sustained contact. If the witness is installed, arm it for the
   exact fixture actor, use one bounded contact sequence, and retain its raw
   result with independently observed controller and node transforms.
3. Compare contact on the same wolf with the showcase armor unequipped. The
   physics config stays loaded. Re-equip the wires to show their placement.
4. Retire the disposable session and verify profile restoration.

The stationary result records root stability. The skinned outlines can follow
bone movement from animation and contact. The stock CBPC API exposes scoped
contact callbacks without post-solver capsule enumeration. This scene displays
the configured fixed bank, so keep render observation, actual controller
overlap and contact callbacks as distinct evidence. The production adaptive
fit still has its own lifecycle and provider checks.
