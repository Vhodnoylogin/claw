# Read-only FSMP step witness (nonshipping test component)

This standalone test DLL does not hook, patch or modify a provider, actor, rig,
camera, clock, configuration, render state or Bullet object. It observes the
existing FSMP public pre/post-step events. It is not part of runtime CMake or
any end-user package, and does not qualify physics motion or a target actor.

The consumer listens for `hdtSMP64` during SKSE PostLoad. The public startup
message is type0/dataLen0 with data equal to the interface pointer itself.
Before attaching process-lifetime sinks it requires exactly interface2.0.0 and
declared Bullet3.24.0. Invalid runtime,
message, duplicate startup or version refuses without a registration retry.
The cached public header is an external pinned build input, not copied here.

`CLAWFSMPWitness.ReadState(Int serial=0)` queues metadata snapshots. Zero
queues one SKSE task and returns pending/requestSerial. Poll that positive
serial for pending or ready/sample; polling never queues or waits. A new zero
after completion starts the next snapshot and retires the previous serial.
The bounded single-slot sample stays immutable until that new request. Refused
responses are not physical observations and must stop the diagnostic.

Main/UI/timer/world-root-presence reads run only in the queued SKSE task.
Raw thread IDs are evidence, not an assertion about Main.threadID semantics.
The sample records freezeTime separately from engineMultiplier; neither one
substitutes for the other. v2 callbacks publish atomic counters plus the bounded
read-only object window below. Contention never blocks the provider; dropped/invalid/coherence
fields expose incomplete evidence. Pre/post are separate observations, not one
atomic solver-frame transaction. `physicsPhase:not_synchronized` describes the
main-thread snapshot, while each event timestamp comes from the provider event.

The exact native build recipe and source/dependency/output manifests are in
`Builds/claw-fsmp-step-witness-20261113/build-02` (v1 remains immutable in build-01).
It reuses the independently
source-built C5dd CommonLib library and verifies its2662 SDK files plus293
dependency-prefix inputs. SE1.7.104/SKSE>=2.3.1 only; AE/VR refuse. This component
uses SDK structures and does not claim NoStructUse. Three SKSE exports only.
The native-only PSC compiles separately with Bethesda's compiler; no flags-file
or imports are needed. Deploying DLL/PEX or running any game needs root authority.

Run the standalone CMake/CTest collector test or the recorded direct compiler
recipe. `python -B -m unittest -v test_validate_snapshot` tests the pure reader.
Zero counts are valid diagnostic data, never a simulation PASS. A positive
post-step delta proves provider-global completed events, not target body motion,
correct reset behavior, writeback visibility, contacts or parameter correspondence.

## v3 observer-only dynamics extension

The current test source emits `claw-fsmp-step-witness/3`, window
`schemaVersion:3` and plugin version0.0.3. It adds observations without changing
ReadState/BeginWindow signatures or adding a hook, simulation write or actuator.
The historical build-02 DLL, PEX and schema2 actual captures remain immutable.
The pure reader explicitly accepts archived schema2, with its exact old pose
shape, and schema3, with its required new fields. Direct validate_window calls
use the explicit window version; absent version means historical2 only. New
vectors or statistics cannot implicitly promote an old record to version3.
Mixed-version compare refuses. Old readers intentionally refuse new schema3.

Each initialPre, lastPre, lastPost and retained firstNonzeroPair pose now also
contains `linearVelocity`, `angularVelocity` and `inverseLocalInertia`. Public
const SDK getters copy xyz in the same provider callback as WORLD/mass/flags.
Rigid-body zero vectors and zero inverse-inertia axes are valid observations.
Non-rigid objects publish null for all three unavailable vectors. Linear values
are raw Bullet world-distance units per second, angular values radians per
second, and inertia remains in the provider's local mass/distance convention;
there is no hidden unit conversion or claim of metres. Local inertia can change
between recorded poses; it is observed rather than assumed constant. No object
pointer escapes its callback or becomes an external identity.

FirstNonzeroPair selection remains based ONLY on WORLD pre/post difference,
preserving v2 semantics. Its added vectors can expose actual onset velocity
when WORLD first moves, but a velocity-only change does not create a new
firstNonzeroPair. This is bounded existing storage, not a growing trajectory.

`minimumPairedHostTimeStep` and double-precision `summedPairedHostTimeStep`
count each successfully completed provider pre/post callback pair once. The
minimum is null and sum0 before the first completed pair. An in-flight pre does
not contribute; nonce polling and copying do not rebase or add to either value.
`timeStepStatisticsScope` explicitly says these are completed host callback
intervals, **not Bullet substeps or integrated simulated time**. FSMP can split
an interval or discard a small remainder internally. All pose/statistic fields
are published together by the existing fixed-memory copy gate. Contention still
invalidates evidence rather than blocking a provider callback.

Before these edits, the actual provider's retained PDB type records and fresh
MSVC public-getter assembly/layout proof confirmed rigid-body offsets432
(linear velocity),448 (angular velocity),528 (inverse local inertia), size784,
float32/SSE API, and the same13 PDB-exact official3.25 headers. The pre-edit proof
and separate candidate build live under
`Builds/claw-physics-next-response-20261119/observer-extension-03/`.
No private offset read, Bullet link library or provider change is introduced.

Portable collector/reader tests exercise co-temporal initial/latest/onset fields,
legitimate zero values, non-rigid nulls, malformed vectors, completed-pair dt
accounting, pending-pre behavior, strict version selection and historical v2.
They qualify source behavior only. This extension is not installed, admitted or
game-qualified, and cannot retroactively supply missing data to the failed
004012 damping run. Velocities/inertia help diagnose its unexplained input kick;
they do not directly expose a constraint's damping coefficient or solver impulse.

## v2 bounded Bullet observation

`String BeginWindow(Int nonce)` queues one consumer-only arm task. Positive nonce
required. Repeat the SAME nonce to poll pending/ready; it cannot rearm or reset.
A different nonce, epoch change or failed queue refuses. There is one window per
process, starting at the next PreStep, capped at128 objects and900 paired steps.
No physics or engine state is changed. This is a diagnostic, not a solver actuator.

Both callbacks copy only public `btCollisionObject`/`btRigidBody` getters: world
3x3 basis plus xyz origin, collision flags, rigid-body status and inverse mass.
The adapter sorts callback-local numeric identities, never casts userPointer,
and never dereferences a pointer after its callback. External tokens are1..N,
never addresses. Object-set/metadata/epoch/pair/thread/timing changes, nonfinite
input, overflow or callback contention refuse; nothing is silently truncated.
There is no callback allocation or wait. A main-task POD copy uses a try-gate;
if it blocks a provider callback that drop invalidates the window explicitly.
Publication retains initial PreStep poses, latest paired poses, post-step
world extrema and each object's first nonzero pre/post pair (exact nonzero is
evidence, not a physical acceptance threshold). No history grows with runtime.

The API's declared3.24 is hardcoded. The actual DLL/PDB GUID
`FA13003A-6397-4D63-833B-71BE3CFFE2C2`, age1, establishes official3.25 headers:
all13 transitive headers match PDB SHA-256 exactly; its world compile record
sets `BT_USE_SSE_IN_API`, float32. Compile assertions require vector16,
transform64, collisionObject384, rigidBody784 and pointer-array32 bytes.
Evidence/official-source URLs are retained under sibling `bullet-abi-review-01`.
The nine relevant FSMP source files also match PDB checksums after CRLF-only
normalization. These facts qualify this exact provider binary, not arbitrary
providers reporting the same hardcoded version. Root must retain exact runtime
module/VFS admission. No Bullet library is linked into this read-only consumer.

PDB-bound provider source emits PostStep after simulation and restoring its
temporary origin shift, before FrameSync engine writeback. Position conversion
is direct xyz. Bone-to-rigid COM transforms still require fixture proof before
spatial association; the public API does not expose actor/bone names. Anonymous
objects that cannot be uniquely associated stay unqualified. Bullet motion plus
zero engine-observer motion isolates a downstream binding/writeback/visibility
boundary; it does not by itself prove engine overwrite. Nonzero local engine
transforms are not required by the provider, which writes WORLD fields only.
