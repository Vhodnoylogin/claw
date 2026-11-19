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
and permits up to 48 distinct roots. Individual graphs retain CLAW's object,
geometry and child-link bounds. A load transition invalidates cached replies.
The game paths are read-only. Graph membership and matching observations do
not establish rendered geometry, continuous attachment or applied physics.

The initial offline build produced the DLL and PEX. The local build receipt
is under Builds/claw-vr-model-topology-20261119/build-02, SHA-256
544932afc4afc9852e61a6c7eec6ed689998f80f3f46c55517cd9745e8444832.
The witness has not yet been staged or run in Skyrim VR.
