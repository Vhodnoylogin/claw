# Private CBPC event witness

This Windows x64 SKSEVR test plugin subscribes to the public SKSE mod-callback source. It copies only CBPCPlayerCollisionWithMaleEvent and CBPCPlayerCollisionWithFemaleEvent for one exact admitted dynamic NPC. Each row retains the event name, sender FormID, raw bone or group string and the raw finite numeric argument.

The eventual owned test profile must supply test_CLAW - VR CBPC Contact Fixture.esp with the test NPC base at local FormID 0x800. The game harness must pin the fixture bytes and qualify the CBPC module, callback source, actor incarnation, stationary target, actual cell and collision source.

## Papyrus contract

- GetCaptureState() returns JSON with process ID, current load-boundary generation, status, sink registration and reported loading state. Before a SKSE NewGame notification, the startup epoch can be used only when the native queued scene checks pass.
- Arm(nonce, generation, actorFormBits, cellFormBits) accepts one attempt per process. Pass signed 32-bit Papyrus representations for unsigned FormIDs. The queued main-thread task checks fixture identity, the dynamic actor FormID, current shared attached cell and loaded 3D. Wait for status armed before starting a test action. The true result means it entered the queue.
- Seal(nonce, generation) closes the exact armed capture. Call it after disjoint test holds and any scoped cleanup, within 60 seconds of the arm request.
- Read(nonce, generation) returns an immutable JSON snapshot only for the original terminal key. Re-reading an exact previous key returns the same historical snapshot after a load boundary. GetCaptureState() exposes the current generation separately.
- Terminal statuses changed_world, expired, refused_identity and clock_invalid describe interruptions. Status sealed with dropped=0 establishes zero known drops in the selected local listener. Each retained row carries a sequence and serialized capture QPC. Sequence gaps include malformed payloads, unmatched opaque identity on the same FormID, missing sender and capacity overflow. The maximum retained row count is 128.

The older published CBPC source passes the first registered bone name of an affected group and a cumulative engine-time value. Use a single-node affected group to identify a single bone. The stock provider's callback means that it produced a sustained-contact event. Its event interface has no solver pair-coverage, continuous contact or render evidence. Dwell timing, callback provenance and actor continuity need qualification in the owned scene.

The test fixture is stored under `src/test/resources/plugins/`. Build it with
the repository's Spriggit workflow. It contains one NPC base plus the plugin
header. A fresh engine-created reference is required. The original male probe
record retains its no-combat AI dispositions. This fixture sets movement speed
and AI energy to zero. Check the actor's loaded identity, combat state and node
motion through each measured hold. New attached geometry is not inferred from
the actor record or a sphere radius typed by the caller.

Use `src/test/python/physics/cbpc_event_readback.py` to score a sealed window
against independently observed near, far, and repeat near holds. A post-detach
near hold can be included. Keep the minimum wall hold in QPC ticks and the
configured engine collision duration as separate inputs. Missing callbacks
under those conditions establish a scoped emission observation only.

For the stock left-wand fixture, `cbpc_vr_geometry.admit_holds` consumes the
same-task VR Observer snapshots of the player, target, tail and both
controllers. It verifies a stationary actor, nominal overlap/separation,
an independently observed return and sufficient sampling cadence. Its
inward-rounded QPC bounds feed `cbpc_event_readback.score`. The geometry
gate uses scene transforms while the event reader uses CBPC callbacks.

Build the standalone DLL and external PEX with the pinned cross-runtime
CommonLib and Papyrus toolchain used by the VR pose witness. The portable
window tests run in the standard CTest suite.

## Equipped VR player contact

Build the separate `CLAWVRPlayerCBPCEvents` DLL and PEX with
`python -B build_player.py --baseline <retained NPC build-03> --out <new build>`.
The NPC script and its original schema remain available for NPC runs.
The new observer accepts player `0x14` in wolf form with the owned Body32
fixture and pinned sex-specific world route. It retains the actor, cell,
runtime handle, Body32 forms and identity of the attached world clone at arm.
`Seal` queues a fresh main-thread read of the same binding. Only the ready
terminal `claw-vr-cbpc-player-events/1` result with `status=sealed` and
`body32.checkedAtSeal=true` establishes continuity at the two ends. The read
exports form IDs and the runtime handle without underlying object addresses.
Player equipment or race events end an open capture with `changed_subject`.

`stage_player_contact.py` in `src/test/components/contact-profiles` prepares
one left-ear and one tail arm from the pinned isolated NPC configurations and
the dedicated equipped fit. Each has one receiver group, player/wolf-only
selection, one `LeftWandNode` sphere and a 0.3-second event threshold. The
receipt includes the fitted neutral weight-zero capsules at provider Float32
precision. These are diagnostic fixtures for the callback test. The full
adaptive collider host needs its separate multi-node profile and scope.

After game admission use one disposable process per receiver. Verify the
effective authored configs and provider identity, including the disabled
competing sources and the actual equipped Body32 route. Establish the native
observer's idle and armed receipts. Independently measure the exact left-wand
center and all four capsules in target-bone space using player-owned world
scene snapshots (`measure_frame(..., own_body=True)`). Read the same player
handle and target bone across all samples. Keep separate planned near poses
and observed signed distances. Hold a near baseline before appending the
four affected-node capsules, then measure near, far and returned-near holds.
Detach the exact indices and repeat the near hold. Seal on the same player
before changing equipment. Store raw attach/detach calls, independently
measured QPC hold intervals and original callback results. `score_player`
checks a positive near/far/near event contrast and both silence controls.
The CLAW replay in `src/test/components/contact-profiles/verify_player_contact.py`
joins those receipts from one trial. See `test_verify_player_contact.py` for the
manifest index layout. Point `association` to the run's original
`devbench-and-game-associated` Bridge observation. Use `topology` entries
`before`, `attached`, `detached` and `after` with fresh `CaptureDispatch`/`Read`
nonce pairs before the first hold, after the fourth append, after the fourth
detach and after the final hold. Capture all four within the listener window.
Pass `--manifest`, `--steps`, `--profile`, `--state`, `--backing`, `--config`
and `--body`. The manifest pins the exact `steps`, `state` and `backing` files
by SHA-256. Supply the original run state, its mapped provider evidence,
the pinned fitted profile, the staged config receipt and the static Body32 ZIP.
The Bridge batch must report the full effective CBP config inventory and the
absence of `CLAW - Physics.esp`, plus byte winners for the static trial and its
observers. FSMP must be absent from the effective files and mapped modules.
Stage the diagnostic ear and tail configuration arms separately.

The replay measures the signed union distance to the four capsules in each
world frame and credits callbacks only inside inward-rounded QPC holds. It
requires positive near controls and silent baseline, far and detached holds.
The test uses the pinned neutral capsule bank at weight zero. It leaves live
TRI neutrality, adaptive fitting, exact solver occupancy, capsule-level event
attribution and impulses outside its measured scope. Zero qualified contact
events leave self-contact unresolved.

### Detached subject and planned motion

`compose_player_contact_subject.py` merges the pinned static outfit, the Body32
topology observer, one private CBPC arm and the inherited isolated configs.
Supply the Morphbench stationary contact cue report as `--cues`. The composer
checks every written file against the replay requirements and reports the
separate CBPC DLL, its Papyrus declarations and the XP32 skeleton dependency.
Keep its two `subject/Data` directories separate. The cue file sits outside
both directories. The platform supplies the independently qualified World
Observer. The staged subject manifest does not establish an installed profile.

After admission, obtain a same-task World Observer row for the exact equipped
player, target bone, actor root, HMD and both wands. Pass that original row to
`retarget_player_contact.py` with the preceding `/8` reply from the same process,
the independently resolved fixture item/addon IDs, the pinned config and `REFERENCE-MOVEMENT.json`.
It projects the Morphbench test points through the measured target bone and
uses the measured left-wand orientation and scale to calculate tracker origins.
It leaves the head and right wand as fixed reference values and refuses points
whose calculated sphere-to-capsule clearance misses the test margin. Use the
admitted controller mapping to convert the output game units. Confirm the
result with fresh world samples before the timed hold.

The launch needs a verified starting fixture with the Body32 armor equipped,
or a qualified bounded action that equips it. The narrow replay also needs the
actual capsule append/removal and native witness receipts. A generic scene or
Havok contact observation provides separate evidence. Use the ordinary
owned-profile admission, installation and restoration process for a real run.

### Stock split-ear trial

Pass `--stock-split-ear` to `build_player.py` for the stock male route used by
the legacy NIF comparison. Load this build in place of the equipped witness.
It uses the same Papyrus declarations and returns
`claw-vr-cbpc-stock-split-ear-events/1`. At arm and seal it requires the same
attached stock `CDD86/CDD87` clone and the same unique left/right ear shape,
with its exact `EarWorldTrial.tri` link and 1,354 vertices / 2,394 triangles.
The observer validates skin partition counts when the VR shape header leaves
them empty. Independently pin the legacy NIF and TRI winners. Use
`score_player(..., stock_split_ear=True)` for the male left-ear contrast after
admitting its live geometry and measuring the wand holds.
