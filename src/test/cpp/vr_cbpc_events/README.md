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

Build the standalone DLL and external PEX with the pinned cross-runtime
CommonLib and Papyrus toolchain used by the VR pose witness. The portable
window tests run in the standard CTest suite.
