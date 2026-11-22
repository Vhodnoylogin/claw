# VR NPC pose witness

This standalone, read-only SKSEVR test plugin observes the VR FSMP fixtures.
It uses the dynamic NPC FormID, exact base, runtime handle, cell and vanilla
werewolf armor addon supplied by the test harness. The standard male fixture
uses weight 50. The separate female motion fixture uses weight 100. Both
require beast race `000CDD84` on the actor and base.
The harness still owns the single spawn, addon pin and fixture provenance.

1. Call `CLAWVRNpcPose.BeginNpc(nonce, actor, base, handle, cell, addon)` once per
   process after the fixture is loaded. Use the signed Papyrus Int carrying the
   actual 32-bit FormID or handle bits. Poll `ReadNpc(nonce, 0)` for sample zero.
   `BeginNpcWithMorphs` takes the same six arguments followed by a `String[]`
   of canonical CLAW morph names. Each accepted snapshot contains
   `effectiveMorphs`, read twice through RaceMenu's versioned BodyMorph
   interface. The witness requires the same finite values around the pose read.
   It preserves signed and out-of-range values for the caller to validate.
   `BeginNpcContact` takes the same typed array and adds three required
   named transforms for the remaining ear and tail support partitions.
   `BeginNpcTailRefit` takes the same arguments and uses the same 15-node
   capture for a single neutral, changed and returned tail-morph trial.
   After either contact lease is ready, `ReadPhysicsSnapshot(nonce, previousToken)`
   polls the latest Distribution `CLAWPhysics_Observation` snapshot for its
   exact pinned actor. Use zero for the first token. A ready response contains
   `snapshotToken`, `eventQpc` and the lease identity. Verify currentness with
   `CLAWPhysicsNative.SnapshotCurrent` using the same actor and generation
   before reading any capsules. The observer neither registers the actor
   with Distribution nor acknowledges its snapshot.
   The two original entry points retain the twelve-node output order.
   `BeginFemaleNpc` takes the same six integers as `BeginNpc`. The female
   witness adds both pre-P1 anchors and both P1 drivers at the end of the
   original twelve-name list. The witness requires explicit sex and weight
   for the selected fixture at every observation.
2. Call `SampleNpc(nonce, i)` with successive indices 1–16. Poll
   `ReadNpc(nonce, i)` after each request and retain the sample before requesting
   the next index. The deadline is 30 seconds for `BeginNpcTailRefit` and 12
   seconds for the other entry points. All use the same single lease per
   process. A repeated opening with the exact same scope and arguments can
   read sample zero without extending its deadline.
3. Call `EndNpc(nonce)`, then poll `ReadNpc` for the final sequence until
   `ended`. Any refusal or
   missing end evidence leaves the harness without a qualified run. A one-shot
   watchdog also queues main-thread retirement at 31 seconds for tail refit
   and 13 seconds for the other entry points.

Each `claw-vr-npc-pose/1` sample brackets engine reads with QPC ticks and
reports the process, frequency, world epoch and opaque root token. The lease
retains the actual actor, third-person root, biped, active body clone and
required bone paths. Graph membership, exact active slot and ownership are
checked before and after each read. Missing or detached body slot 2, absent
or ambiguous nodes, target unload and world changes refuse the lease.
During an initial VR alternate start, the native NewGame message can be
absent. Each main task checks the actual loaded player and the same attached
fixture cell with main/loading menus closed. An observed load in progress
or failed load remains a separate refusal.
Each pose provides row-major rotation, translation and scale. The requested
drivers, anchors and root control include both world and local transforms
plus the actual parent's world transform. No raw pointers leave
the engine task context. The historical `skse_main_thread_task` field names
the SKSE task path. `threadID` is the actual per-sample Windows thread.
SKSEVR 2.0.12 serializes its delegate queue and drains it at two call sites.
VR63 retained different thread IDs in two coherent native samples. Use the
opaque actor/slot lease and advancing QPC plus independent observer brackets
when comparing snapshots. Two snapshots carry no renderer synchronization.

An observation establishes ownership at the sampled times. It does not
establish continuity during unobserved frames or associate a scene node
with an anonymous FSMP rigid body. For the latter, bracket known
pre/post callback windows, retain the provider data and prove the COM
basis and unique match. Provider causality needs a controlled contrast
or typed provider ownership evidence. An unconfirmed SKSE cleanup queue
refuses the case; the witness never releases engine objects on a timer
or Papyrus thread.

Build `Plugin.cpp` and the adjacent PSC as `CLAWVRNpcPose.dll` and
`CLAWVRNpcPose.pex`. Use the pinned cross-runtime CommonLib/JSON build and
legacy Query/Load exports used by the VR model topology witness. Add
`src/main/cpp/include` and the official pinned RaceMenu API header directory
to the include path. The standalone DLL and PEX
belong in an isolated test build. They have no linkage or packaging path
to CLAW production. Compile `LeasePolicyTests.cpp` alone with a C++20
compiler for the portable fixture, sequence and pose controls.
