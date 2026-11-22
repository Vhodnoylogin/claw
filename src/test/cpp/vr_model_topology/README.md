# Skyrim VR model topology witness

This test-only SKSE plugin examines the current wolf player's default,
explicit third-person and explicit first-person model roots. It includes
both biped roots and active/buffered part clones. Each graph receives an alias
valid only within its capture, and the inventory uses CLAW's four target
geometry roles. A second route read checks that the same player, race, base,
cell, roots and slot routes were present at both ends of the task.

Build with the same cross-runtime CommonLib flags as the CLAW DLL. The
standalone source exports the legacy Skyrim VR loader interface and admits
Skyrim VR 1.4.15 with SKSEVR 2.0.12 or newer. Compile the adjacent Papyrus
declaration as its companion. This component is outside the release build.

Capture takes an increasing positive nonce and queues one SKSE task. Read
polls that nonce without queuing work. A capture expires after three seconds
and permits up to 48 distinct roots. The witness allows 4096 objects, 128 geometries and 8192 child links per
graph, independently from the original application bounds. A capture reports
the selected model path and whether a part handle is present. The handle is
never dereferenced. A load transition invalidates cached replies.

Schema 3 also inventories the typed player VR world, room, height,
headset, wand, melee-offset, hand and clavicle roots. A capture records
the raw weapon state and checks it again at the end of the same task. Each
graph includes a bounded list of geometry names, types, local application
cull flags and available triangle-shape vertex/triangle counts. The details
are limited to 16 entries per graph and carry a completeness flag.

Schema 4 adds the local application cull flag for each observed root, then
reads up to 16 parent cull flags in nearest-first order. A known set flag
is reported even if the remaining chain is incomplete. A clear chain
requires reaching its end. Depth limits and cycles remain explicit.
The same task rechecks parent identities and flags and records the raw
live camera state ID when available. Pointer identities stay in the task.
The pure chain traversal is covered by `claw-vr-root-cull` in CTest.

The game paths are read-only. Graph membership and matching observations do
not establish rendered geometry, continuous attachment or applied physics.

The initial offline build produced the DLL and PEX. The local build receipt
is under Builds/claw-vr-model-topology-20261119/build-02, SHA-256
544932afc4afc9852e61a6c7eec6ed689998f80f3f46c55517cd9745e8444832.
The first isolated VR run reached its 15 baseline checks but SKSEVR
rejected the witness query before any transformation. The installed loader's
version carries a VR subtype nibble. The witness now uses CLAW's existing
runtime-target check and keeps the exact VR-family filter. The fixed binary
compiled with the same SDK and its own companion PEX. Its first game
qualification is recorded separately from the build.

## Post-phase torso capture

`build_torso_capture.py` builds a distinct diagnostic from the retained R06
observer using its sealed source, commands and MSVC dependencies. Supply the
R06 build directory, the pinned RaceMenu API header, the retained compiler
environment script and a new external output directory:

```text
python src/test/cpp/vr_model_topology/build_torso_capture.py --r06 <native-r06> --skee <IPluginInterface.h> --environment <capture-environment.cmd> --out <new-external-directory>
```

This preserves the original Papyrus declarations and five-bone packet. The
extension adds `torsoCaptureVersion`, `torsoBodyTri`, `torsoBones` and
`effectiveMorphs` in the same post-VRIK/HIGGS sample. `TorsoPose.h` observes
the loaded `HEAD` skin's actual palette and brackets it with readings of the
effective RaceMenu values. The R06 candidate retains its male fixture gate.
The helper's female palette is checked against its NIF/TRI separately.
Pass an independently admitted capture to the VR torso replay to reconstruct
clearance. The candidate does not acquire rendered pixels or modify the game,
and remains a separate test build.
