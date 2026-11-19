# Read-only CPU geometry witness (nonshipping)

This standalone test component observes exactly two current third-person
BSTriShape roles and nine selected vertices for the authored female fixture.
It does not ship with CLAW, patch a provider, install itself, mutate a morph,
change physics, acquire GPU data, reconstruct skinning or accept rendered
attachment. The root production/test CMake files are not involved.

The native plugin refuses every runtime except SE1.7.104 with SKSE>=2.3.1.
Its translation unit explicitly uses the known SDK **flat** layout, including
the typed NiSkinInstance critical-section member/sizeof0x88. No VR/universal
lock offsets are inferred. The offline recipe reuses a verified source-built
multi-runtime CommonLib static library and records that distinction: successful
linking does not qualify runtime ABI or engine behavior. VR/AE refuse at load.

## Exact scope

Generated external `SealedManifest.h` pins e5a9d6b5 baseline,74a068f3 private
root578 candidate and34744d55 TRI. No NIF/TRI/generated header is stored here.
The generator records actual topology/ordered bone names and the two allowed
selected-point FP16 support variants. It admits fur_belly577–582 and
head779/1676/1677 only. Source BSTriShape counts are10810/7698 and9427/17456
vertices/triangles. Geometry names use ASCII identity, preserving observed
spelling (including actual HEAD); count, topology and support checks supplement
the name. Duplicate/missing roles refuse.

The native parser copies the **currently attached CPU pre-skin** vertex stream,
four raw FP16 weight words/uint8 bone indices, partition map/palette metadata,
typed skin binds and current local/WORLD transforms. Direct and vertexMap
triangle interpretations are checked against the sealed winding-preserving
topology fingerprint; a mismatched mapping refuses. Packed global bone indices
must reproduce the sealed per-point support with the exact ordered bone-name
map. Raw packed weights are retained, never normalized into alleged render data.
The two selected source shapes are static. Dynamic layouts explicitly refuse:
the SDK exposes only blocking BSSpinLock.Lock for that stream, so this collector
does not guess a try-lock or silently use a different position source.

One SKSE main task owns retained NiPointers to root, both geometries, skin
instances/data/partitions and bones. It takes **try-locks** in the source-observed
renderer→skin order; contention refuses without waiting. Both leases survive the
shared final identity/pose bracket. Busy reasons distinguish the renderer,
initial skin copy(role) and final skin bracket(role); the labels provide no lock
acquisition retry or ABI acceptance. No pointer escapes the task. Buffer decoding
uses bounded counts/strides/offsets and finite numeric checks; ambiguous data,
unsupported palette/layout, detached roots, changed skin or pose refuse. Root
address continuity between requests is sampled, not a retained lifetime proof:
unobserved same-address reuse remains explicitly undetectable. After the first
successful sample, a different load epoch/actor handle/root address requires a
new process, not silent rebind. Main-task equality brackets do not establish an
atomic FSMP or render phase.

The cache is one slot, one outstanding task, at most32 captures/process,
4096 traversed objects, two geometries,32 partitions,128 bones,32768 triangles
per geometry and256KiB serialized result. Full bounded topology is copied only
for fingerprint/mapping validation, not exposed as a scene dump. JSON/hashing
runs outside engine locks. Refused requests preserve old immutable evidence;
serials distinguish it. A queued request has one original five-second QPC
deadline. Expiry does not pretend the outstanding task disappeared or permit
a second task until the callback settles.
An unavailable queue outcome poisons the process-local slot: no new capture
is admitted, and even a later queued callback cannot publish a ready sample.

## Typed transport

Papyrus script `CLAWGeometryWitness` supplies:

- `String Capture(Int actorFormId, Int expectedBaseId, Int nonce)`.
- `String ReadState(Int serial)`.
- `String ReadChunk(Int serial, Int index)` (up to4096 characters/chunk).

Form IDs are signed Papyrus Int bit patterns. Capture queues **IDs only**, avoiding
any VM/listener-thread world pointer read. The main task resolves the current
actor and requires a nonplayer0xFF dynamic ref, fixed base0x0D000801, female sex,
wolf race0x000CDD84, loaded3D, runtime handle and root. This is a fixed authored
test fixture contract, not a general ownership oracle or body-family detector.
The external runner must still supply its actual fresh fixture/creation custody.
Positive increasing nonces are consumed once; busy/old nonces never requeue.
Poll the returned serial. Cache chunks are capture-time evidence, not fresh
world reads; reassembly must keep the serial and check final state/byte count.
Pre-load/failed load invalidates reads; activation uses CLAW's authoritative
encoded-success WorldStartPolicy, never a bool-pointer interpretation.

The payload sets `observedCpuPreSkin=true`, `reconstructedSkinnedWorld.status`
to `not_implemented`, `gpuPostSkinObserved=false` and
`renderedAttachmentAccepted=false`. No current tool or successful GPU upload
proves post-shader vertex positions. This first collector is not rendered
attachment acceptance or a qualification of the private root578 candidate.

## Offline build and tests

Configure this directory alone with CMake for the portable `claw-geometry-tests`
target/CTest. It covers half decoding/nonfinite values, stride/offset/byte bounds,
packed-index/support errors, winding-sensitive topology and request busy,
nonce/epoch/deadline/capacity/lease discrimination. Assertions are enabled in
Release. These controls exercise pure production helpers used by the collector;
they do not establish SDK memory layout or a running game.

Partition storage must be non-null before any element reference. The shared
pure admission check rejects missing storage and invalid bounded counts; its
negative control reaches zero element reads. The attached engine allocation/count
invariant is still required: `SimpleArray.size()` is not used as an independent
allocation-length oracle.

`make_manifest.py --baseline ... --candidate ... --tri ... --pynifly ... --out ...`
requires the exact approved hashes and creates a new external directory. The
reader DLL/Python sources and generated header are recorded in its receipt.

`build.py --previous <verified-fsmp-witness-build02> --manifest <new-manifest-dir>
--out <new-external-build-dir> --papyrus <Bethesda-PapyrusCompiler.exe>` verifies
the retained dependency closure, records exact compiler/link/PEX commands and
consumed include hashes, builds the DLL and pure executable, runs its controls,
checks exports and compiles the PSC. Each new attempt uses a new directory;
failed outputs are not overwritten. Generated DLL/PEX/PDB/JSON/logs stay outside
Git. No install or game-launch command exists here.

Actual SE attempts234057-36bd42 and235502-991f7e loaded the pinned component and
applied/read back all31 Neutral coefficients, but their sole capture refused
with lock contention; the second specifically identifies the renderer. Both
games exited normally with exact file restoration. Neither obtained CPU point data
or requested FHeavy, so CPU-buffer/ABI qualification remains open. Historical
failure receipts and build-source preimages stay outside Git.

A later same-build case retained eight renderer refusals across advancing
engine frames. The diagnostic build adds an optional `rendererBusy` object to
that specific terminal `ReadState` refusal. It records the callback and engine
main thread IDs, the two typed renderer-lock offsets, and up to twelve stack
frames. Resolved Skyrim SE and SKSE frames include module-relative addresses.
The diagnostic is tied to the original request, load epoch and deadline. It
does not consult the lock's internal fields, acquire the lock again, read
vertex buffers after refusal or identify the lock owner. SDK accessor agreement
is not independent runtime layout proof.

Actual TEST SE run `20261119-161714-927048` retained one typed refusal from
this build. Both lock offsets were `0x27F0`. The callback thread ID was
37280 and the engine's recorded main thread ID was 35192. The stack included
the installed SKSE DLL and game executable. The first game return RVA `0x65A3E1`
matches the end of SKSE's second task-pool hook call at `0x65A3DC`. This observation rules out treating
the existing callback label as proof of main-thread affinity. It does not
identify the lock owner or establish which phase would allow a safe read.
Neutral coefficients, exact fixture disposal and profile restoration were
verified. No vertex sample or FHeavy request followed. See the external
`claw-cpu-geometry-qualification-20261119/renderer-diagnostic-01` evidence.

The remaining separately admitted gate is actual CPU-buffer qualification:
neutral versus fixed FHeavy, current TRI-predicted deltas, support/unchanged-point
controls, root/epoch/refusal behavior and source/VFS/module admission. A future
test can temporarily stage two nondefault constant profiles (Neutral/FHeavy)
through existing ConfigureMorphFamily, read actual family/status/SKEE31 values
and keep production APIs unchanged. FHeavy is an authored vector, not an assumed
preset name. No profiles, game case or deployment are prepared by this component.
