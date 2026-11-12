# Native left-P1 anchor-world mechanical feasibility test — v2

This standalone TEST source is an unqualified, prospective actuator/observer.
V2 prospectively replaces the never-deployed v1 subtree-composition proposal;
old source/receipts remain historical and cannot be mixed into v2 evidence. It
is not linked from CLAW's root/runtime CMake and has no install or packaging rule.
It must not enter a runtime release. No native test DLL has been compiled or
installed as part of the initial source review. Pure-controller tests are separate.

The fixed case accepts one explicitly identified, disposable **nonplayer female
WerewolfBeast** (race `0xCDD84`) and only `NPC L PreBreast P1`. The owning packet
must independently pin the actual NIF/XML and prove that anchor's mass-zero role.
`fixtureEvidenceSha256` records that outer-owner receipt; the plugin does not
inspect or change provider configuration, mass, gain, binding or SKEE keys. One
operation nonce is admitted per plugin process. This first case requires the
provider absent or stopped with a composition-consistent baseline; it
is not yet an actuator qualified for an actively solving body. A second case requires an owned
new process, never replay of an unresolved intent.

## Exact actuation and observation boundary

The offset is `(0.1, 0, 0)` **in the baseline anchor frame**, not an addition to
raw parent-local X. With the saved local transform, the only local write is:

```
t' = original.t + (original.R * offset) * original.scale
```

Rotation and scale are never assigned. Restore writes the exact saved translation
bits. Each translation write and each `UpdateWorldData` call has its own fresh
actor/scene guard immediately before it. The only world update invocation is:

```
RE::NiUpdateData data{};
anchor->UpdateWorldData(&data);
```

There is no downward pass, controller update, per-child update, cached-world
assignment or fallback variant. The exact external CommonLib implementation
relocates NiAVObject's virtual slot `0x30`/VR `0x31`. NiNode overrides downward
passes, not this world-data slot. V2 therefore requires an immediate **anchor**
world witness equal to composition of the current parent world and expected
anchor local. It also requires the actual moved displacement `(0.1,0,0)` in the
baseline anchor frame, then baseline zero on return. A stale anchor world fails.

All retained subtree identities, topology, finite/rigid frames and exact local
bits across each direct call remain guarded (maximum 32 objects). Descendant
world transforms are recorded verbatim; their composition and zero are **not
scored**. Descendant locals are not frozen to the prepared baseline between calls.
The first case requires an absent/stopped provider and a consistent anchor
baseline. It does not prove solver consumption or qualify later solver response.
Readback is neither a solver-phase nor render fence.

Admission and every write/update guard require the same engine actor handle,
actor pointer/FormID/base/race/sex, test world generation, exact current actor 3D
root, anchor/descendant identities and parents, current parent-child membership,
complete retained subtree topology, exact expected anchor-local float32 bits,
a nonzero generation, and stationary actor/root/control transforms. Controls are `NPC Root [Root]`,
`NPC Pelvis [Pelv]`, `NPC Spine2 [Spn2]` plus the actual model root and anchor
parent. Actor and model-root local/world scales must be unit within `1e-5`, and
model-root rotations must be orthonormal with positive determinant within `1e-5`;
nonuniform/sheared root frames are rejected. Each NiTransform scalar is finite
and positive. Every retained local/world rotation, including the parent and anchor rotations
used in composition, must remain rigid with positive determinant
at the same `1e-5` tolerance; malformed scale/shear hidden inside R is rejected. Existing stationary bounds remain actor position `.025`, angle
`1e-5`, transform position `1e-4`, rotation/scale `1e-5`, actual anchor composition/displacement
position `.003`. This MVP does not expand those gates.

## Finite operation and recovery

`prepare` captures engine witnesses on a game task. A worker then writes one
new compound `.intent.json` with `CREATE_NEW`, checks the full write and
`FlushFileBuffers`/close, and never overwrites it. The intent declares original
and moved float32 bits, ordered move/restore scope, absolute QPC deadline,
recovery restrictions and all timing limits **before the first mutation**.
Only a successful durable-intent confirmation makes `start` admissible.

The moved anchor-world witness's QPC end starts the hold. One worker waits
against producer QPC and posts at most one outstanding SKSE task. Both worker waits
acquire terminal publication in their predicate, and the loop cutoff rechecks
terminal before expiring. Because producers do not lock the wait mutex, both
waits also have a 100 ms worker-only backstop against a notification lost after
predicate evaluation. The game thread never takes that mutex. There is no
main-thread sleep or self-queuing main-task loop. The next callback restores the
saved translation and establishes the actual anchor zero witness before 25
read-only snapshots. A hold uses actual witness-end tick difference and must
remain `.12.. .6` seconds. Sampling retains `.1` nominal period, `.04.. .2` gaps,
first-read maximum `.2` and minimum span `2.1`. A late callback remains a failed
hold/cadence; no deadline rebasing, padding or timing retry is permitted.

Only known cancellation/deadline or a failed immediate anchor/local witness after
a **known normal update return** permits the predeclared guarded restore.
`failedClean` requires exact local restoration and actual anchor zero witnesses.
Root, handle, attachment, local-bit, control or epoch loss; C++ exception; unknown
call; or failed restore witness quarantines the case and prohibits further writes.
Fatal worker/queue flags invalidate every Scene observation guard and are
checked again at immediate translation/update call entry and before final
publication/retirement. Fatal is never normal cancellation or permission to
restore. A flag can change after its final atomic load: this guards consumer call
entry, not an atomic fence inside the engine. A cancelled awaiting-intent/ready
case cannot later start. Repeated start/cancel
or prepare calls with the same nonce return current status and cannot replay.
A different nonce is refused after the one case is claimed. No code loads/saves
a game or reacquires a replacement actor/model for recovery.

Operation deadline is 15 QPC seconds from its prepared observation. Worker
scheduling stops after 20 seconds from request acceptance. File/JSON work occurs
only before start or after terminal POD publication. Synchronous OS file IO and
an already-entered engine call cannot be forcibly cancelled. If a task remains
queued after the worker deadline, a late callback permits only guarded cleanup;
the intent remains unresolved and `completedClean` stays false unless the worker
has durably written the result. An AddTask exception has unknown queue outcome:
no resubmission. A known-idle worker error may post one game-thread quarantine/
retirement task; it never dereferences engine objects itself. These exceptional
cases require the sole owner to retain evidence and tear down its disposable
process, not another stimulus attempt.

## Thread and object lifetimes

The listener copies/bounds JSON arguments, owns all parsed values, and invokes
the host writer exactly once before returning. It never retains the host args,
writer or sink. `status` reads only small atomic/POD status; it does not inspect
live Case/RE data. The game callback takes no listener/worker mutex and performs
no JSON encoding, file IO or host RPC. The worker reads separate immutable
prepared/terminal POD publications, not the live controller. Retained records
contain numeric addresses as evidence, never dereferenceable worker ownership.

Actor handles, Ni smart pointers and temporary BSFixedStrings are constructed,
used and released on the game thread. Terminal game callbacks reset `Scene`
after known finish or quarantine, then publish a POD-only report. There are no
static engine-owned objects/destructors. The SDK registration context intentionally
lives for the process because API001 has no unregister operation. If an owned
callback never arrives, unresolved retained objects are intentionally not released
by the worker or an exit destructor; process teardown is the outer owner's limit.
This does not promise guards within engine implementation, third-party threads,
internal child writes, or solver phases. Native faults can terminate the process;
C++ exception handling cannot manufacture a completion receipt after a crash.

The prospective adapter diagnostics retain at most 64 immutable POD callback-entry
witnesses: callback sequence, work kind, expected first-callback and actual OS
thread IDs, producer QPC availability/tick, and observed generation. Each entry
is release-published before the affinity comparison and any controller/Scene
access; listener/worker readers acquire that individual entry. A dropped-entry
count makes the fixed capacity explicit. The first fatal origin and its POD
context are published once and never replaced by a later worker failure.
Callback contexts describe callback entry, not a claimed engine/solver phase or
the exact instant of a later exception. JSON encoding stays off the callback.
This is not an atomic snapshot of all concurrently publishing diagnostic rows.

The same first-callback OS-thread affinity guard remains mandatory; its binding
is now atomic so an unexpected delegate thread and a listener can record it
without a data race. That first ID is an observed local expectation, not proof
that SKSE guarantees a fixed OS thread or that an arbitrary callback is safe.
No epoch, ownership, call-entry or quarantine guard is relaxed. A queue-fatal
worker exit is not deadline expiration: workerExpired is set only when the
worker actually observes its deadline without an already observed fatal exit.
Existing known-idle retirement and unknown queued-outcome rules are unchanged.

SKSE pre-load/save/new/post-load, the owned actor's object-load/race-switch and
node-update events invalidate generation. Save/load during the case is forbidden
by the outer packet; these event interlocks observe transitions rather than
prevent the engine from starting one. Root/handle checks remain mandatory even
without an event. World readiness delegates to CLAW's pinned pure
`mayActivateWorld` helper: successful post-load is the scalar pointer value `1` with
`dataLen == 1`, failure is null/0, and arbitrary bool-storage pointers or malformed
lengths are rejected without dereferencing data. NewGame carries a quest pointer
and is handled by the same helper's separate new-game rule.

## Own producer and tool

Consumer DLL revision **0.0.3** registers exactly once at SKSE `kPostPostLoad`.
The prior 0.0.2 game attempt reached the saved world but stopped before subject
actions because it requested the interface during its own `kPostLoad`, before
DevBench had received that message and registered its interface listener. The
retained SKSE log records native handle 2 making the request before provider
handle 3 received PostLoad. DevBench initializes at PostLoad; PostPostLoad runs
after every plugin has completed that phase. There is no PostLoad attempt,
polling registration, retry or fallback phase. The exact host build guard,
mechanical tool name and schema remain unchanged. The historical raw tool-list
response was not retained because the outer wrapper wrote it only after its
failing admission check; a successor must retain that response before validation.
This revision has no new game qualification until a separately approved case.

Tool: `claw_test_direct_left_p1_v2`, exact DevBench build 13600 (1.36.0), API001.
A registration collision disables admission; the published SDK replaces a name
even when RegisterTool returns false, so the namespace must remain unique.
The initial test DLL load boundary is only Skyrim SE 1.7.104 / SKSE>=2.3.1.

The producer/schema is `CLAWNativeLeftP1Test` /
`claw-test-direct-left-p1-pulse/2`, with its own per-process GUID, record IDs,
raw QPC ticks/frequency, native-call brackets and numeric local/world snapshots.
`localFloat32Bits` uses rotation row-major9, translation3, scale1 order. These
are **not DevBench world_observer rows**, identities, epochs or nanosecond clocks.
`completeClean` is mechanical cleanup success only. The MVP does not score
physics, contact, all 11 drivers, three-phase correspondence,25% timing/cadence
comparability, or FSMP/CBPC binding acceptance. Any later physics experiment must
be declared prospectively with its unchanged physical gates. C3 remains failed
overall and cannot be rescored using this producer.

A prepared operator supplies the current fully resolved actor/base IDs and an
existing external local evidence directory. The eight prepare fields are:
`action`, `operation` (16..64 ASCII nonce), `actorForm`, `baseForm`, `raceForm`,
`sex` (1), `fixtureEvidenceSha256`, `outputDirectory` (UTF-8). Other requests use
only `action` (`start`, `status`, `cancel`) and the same `operation`. Poll ready
before the first start. If acknowledgement is uncertain, poll status only.

## Build boundaries and pure tests

Pure tests need no game headers or provider and do not build a DLL:

```
cmake -S src/test/cpp/fsmp_native_pulse -B <new-external>/pure -DCLAW_PULSE_BUILD_PLUGIN=OFF
cmake --build <new-external>/pure --config Release --target claw-native-left-p1-tests
ctest --test-dir <new-external>/pure -C Release --output-on-failure
```

Tests use the actual Case and RecordBuffer with a fake engine boundary/QPC,
covering scoped rotated/scaled translation, fresh guards before each call,
exact restoration, 25 read-only samples, no replay, unflushed intent, cancellation
before/after writes, root/identity/local-bit/scale loss, anchor-witness failure vs
ownership failure, failed restore, exceptions/unknown calls, early/late callbacks,
cadence, deadline, bounded record capacity, POD retirement, nonzero generations,
rigid composition inputs, both worker completion races (before wait and after
predicate evaluation), and fatal flags at actual consumer-boundary entry.

The first native build was withdrawn before live use after an encoded-message
bug was found. Its artifact/receipts remain external and must not be deployed.
The source correction reuses `claw/WorldStartPolicy.h` rather than introducing a
second payload decoder. Pure tests cover true/false scalar, malformed length,
real/fake pointer and success/failure/success messages through that actual helper.

Native compilation remains a separate root-reviewed action. Explicit opt-in
`CLAW_PULSE_BUILD_PLUGIN=ON` requires external `CLAW_PULSE_COMMONLIB_DIR`,
`CLAW_PULSE_COMMONLIB_MANIFEST`, `CLAW_PULSE_DEVBENCH_API_DIR` and the existing
external dependency prefix. CMake verifies 2662 CommonLib source files against the
exact retained manifest at commit `0c95630c29ff98f64caeea83c29ca373cf93e58b` and
pins the MIT API header/cpp/license hashes. It compiles the external glue directly;
no SDK or GPL DevBench host source is copied here. Provider SKEE headers are not
used by this direct route. External MIT and CommonLib license notices are copied
only into the chosen build output. No implicit install/game/start or runtime
packaging target exists. The native adapter, scheduling, SDK registration and
actual UpdateWorldData anchor effect still need independent review, compilation
and the separately authorized single mechanical game case.
