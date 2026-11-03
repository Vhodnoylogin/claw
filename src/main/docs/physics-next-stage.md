# Physics next stage: compile and qualify current-body contact

The existing automatic pipeline observes effective native SKEE morphs, samples
independent NPC weight, fits schema-3 capsules on a bounded worker and rejects
stale snapshots before the finite Papyrus host appends. Its defaults remain
disabled. The 30 October record below retains an earlier resource mismatch;
it is not the status of the current v4 model.

On 2 November the current v4 body endpoints/TRIs and XP32 inputs were checked
against the retained model
`CLAW.Physics.CurrentVector.a24397e77b1c9af1fde18e3f984b253e13db71415b70c61d3a4df4b4a3491b73`.
Its 22 regional morph dependencies cover every field affecting selected support;
nine other global TRI targets have no records on that support. The 128 slots
have 96 active male and 128 active female capsules. Generated native header,
host data and explicit offline preflight agree with the measured inputs.
Thirty-six independently evaluated sex/vector cases reproduced the retained
support metrics exactly. This validates retained inputs and calculations;
no numeric optimization or provider/game acceptance is implied.

The matching universal native DLL has now been compiled offline, SHA-256
`4f85b88b8ec8ab5e0be230978f9579e514537cfc34cd3210b2a5a9a4a4613e54`.
Its compiled model header matches the validated generated header. A fresh native
run passed 198 fixtures and 25,344 slot outputs with maximum coordinate/radius
error `1.28786e-13`; the test assertions were enabled. PE inspection confirms
the expected SE/AE/VR metadata and no unconditional SKEE/OpenVR imports. These
checks do not load the DLL into a game or qualify an engine boundary.

A separate finite host ESP and six PEX were compiled for the same model. Binary
VMAD and a Spriggit round-trip preserve 16 actor aliases, a separate player relay,
stopped/default-disabled integration and unqualified provider gates. The host
contains no motion configurations. Its original build was interrupted during
Spriggit's translator restore; the explicit continuation uses the same installed
managed tool and a pinned existing translator cache. Both attempts and all input
hashes remain outside Git under
`Builds/claw-backlog-20261102/physics-host-current-v4-01*`.

The next mechanical gate is actual provider ownership, effective resources and
lifecycle checks. Contact and motion node inventories are intentionally different: this
contact model omits TailBone04, while the separate motion adapter drives nine
ear/tail nodes plus the two female P1 nodes. Do not substitute the source
builder's legacy nine-node motion configuration for that 11-node P1 adapter.
The measured contact fit still has undercoverage; close fitting, animated
surface quality and VR hand contact remain unaccepted.

Automatic runtime activation is also unfinished. `CLAWPhysicsControl` exposes
explicit session, actor and population activation, but no gameplay coordinator
currently calls it. The stopped host is not enabled by installation. The player
load relay revokes the old session; it does not silently requalify the new one.
Existing native population discovery already includes the player and loaded
known werewolves, so a second actor scanner is unnecessary.

The 3 November source now rejects empty or nonfinite effective-morph vectors
before this physics adapter calls `ApplyBodyMorphs`. It expires the current
snapshot and uses the existing domain-cleanup signal. Signed, zero and finite
values above one remain unchanged; fitted-model limits are a separate check.
Focused observer tests and universal compilation with the fitted model passed.
This protects this adapter's sampled update, without a global or atomic guarantee
against other writers. It adds no provider activation or cleanup acknowledgment.

The subsequent offline authority correction separates fresh external qualification
from ordinary lifecycle renewal. Previously, a delayed ready/stale-snapshot receipt
could reuse cached Host assertions and replace a binding after a missed rejection
callback; lifecycle condition updates could also overwrite some rejection classes.
Transient per-runtime authority now preserves rejection across those paths and
unregister. Identity/provider cleanup revocation is separate from attach permission.
Queued registration binds a fixed process/issued-world/session token and revision;
an intervening rejection, context change or suspension invalidates it. Only explicit
Host enable selects a fresh grant, after the exact old accepted ledger is empty.
Population initial admission cannot revive consumed history. Released actors need
fresh explicit qualification until a verified rebind adapter exists. Two pure CTests,
27 actual-source contract checks, both universal translation-unit variants and six
matching Papyrus compilations passed. These remain offline checks, without a
reproduced game failure or provider acceptance. The final snapshot check and
third-party append remain non-atomic. See the
[3 November verification](verification-20261103.md#offline-physics-registration-authority).

Before adding automatic activation, qualify the actual CBPC build, its handling
of an NPC changing race/model, reserved capsule indices and matching body/model
resources. Reuse those observations in a session coordinator with persisted
user opt-in and fresh runtime validation. Do not turn evidence/provider/index
booleans into unconditional `True`, acknowledge uncertain cleanup, or invoke a
global configuration reload to mask missing NPC container rebinding. The
separate motion-only adapter has zero contact response and cannot substitute
for a qualified contact configuration. FSMP motion is a separate provider path;
it does not implement CBPC's actor capsule API.

The inspected CBPC reference source `fabd56ce8f8ac10cde17325f0bd61ecc8cbcda20`
binds an NPC's configured nodes once and subsequently updates cached objects;
resolving an old node name on a new root does not rerun race-dependent binding.
Its public detach path also requires the named node to be loaded. Therefore a
false detach cannot acknowledge cleanup after human return or unload. These are
reference-source findings, not proven equivalence to the installed 1.7.3 DLL.
The needed runtime evidence is the actor's provider binding/container generation
across race changes, root replacement and unload, rather than just an available
node or an attach boolean.

The current motion slice is separate from that retained contact-model work.
Released v4 bodies have 30 male / 31 female morphs; their fresh pipeline already
includes current-TRI P1 skinning and nominal motion bounds. Build the existing
[CBPC and FSMP motion adapters](../python/physics/motion-adapters.md) against the
exact selected v4 endpoints and qualify each provider independently, including
human-to-beast NPC rebinding and disabled/neutral controls. Their motion-only
packages neither activate the finite collider host nor qualify the older
19-morph contact model for these bodies. Full FSMP builder/readback and late
input-mutation tests provide offline failure coverage only. Actual provider
motion, loaded-resource ownership and lifecycle acceptance remain pending.

`src/main/python/physics/preflight.py` now checks that gap without running or installing anything.
It requires a current-vector independent-weight model, validates its identity,
and compares seven explicitly bound files to the model's declared source pins.
It regenerates and compares the **whole** native model header and
`CLAWPhysicsData.psc`, including numeric support, ordered morphs, reserved indices,
slot order and female-only P1 gates. It also audits an explicitly supplied
baseline provider snapshot and requires a nonempty `cbp.dll` in that snapshot.
That presence check establishes no DLL version, behavior or source equivalence.

Resource roles are explicit because the fitter accepts arbitrary filenames.
There is no basename/hash inference or first-match selection. The external
bindings JSON has `schemaVersion: 1` and a `resources` object with exactly these
keys: `maleNif`, `maleWeight1Nif`, `maleTri`, `femaleNif`, `femaleWeight1Nif`,
`femaleTri`, `skeleton`. Each value contains exactly `modelSourcePath` (the exact
string from one model `sourceInputs` entry) and `actualPath` (the supplied file,
absolute or relative to the bindings JSON). Each role needs its own source and
actual path, even when both endpoint files contain identical bytes. Duplicate
pins, missing roles and unrecorded source paths fail. Role assignment is the
caller's declaration, not an independent NIF or armor-binding reconstruction.

```powershell
python src/main/python/physics/preflight.py --fitted-capsules '<fitted-capsules.json>' `
  --resources '<external-resource-bindings.json>' `
  --native-header '<selected-physics-fit-model.h>' `
  --host-data '<selected-CLAWPhysicsData.psc>' `
  --provider-snapshot '<baseline-SKSE/Plugins-snapshot>' `
  --out '<new-external-evidence-directory>'
```

The provider input is the baseline before adding CLAW's intended motion configs;
including those configs correctly reports existing private-alias ownership.
This uses the existing scanner and preserves its limits for XML selection,
archives and effective runtime bindings. Omitted resource/source/provider inputs
remain explicit blocking findings. The report records every consumed file's
size/hash and the provider inventory; final rereads catch changes or added files.
Existing, source and live game/mod destinations are refused. Nothing is copied
into a game or mod manager.

Exit `0` means `offline-inputs-matched-runtime-pending`; exit `2` means missing,
invalid or mismatched offline inputs. The output includes `physics-preflight.json`
and regenerated expected sources. Failure retains
`FAILED-unverified-do-not-install`. Every result keeps `runtimeQualified`,
`gameValidated` and `releaseReady` false. Schema-3 identity deliberately excludes
`sourceInputs` so a proven input-only rebase can preserve the numeric model;
editing those pins alone does not prove that new geometry has the same support.
This preflight compares declared pins and sources, without independently
reconstructing or approving their geometric derivation.

The 30 October offline evidence is retained outside Git under
`Builds/claw-postrelease-20261030/physics/`:

| Run | Result |
| --- | --- |
| `original-final020-preflight/physics-preflight.json` | Original seven resources, whole header, whole host data and retained provider baseline agree; runtime remains pending. |
| `frozen-core-preflight/physics-preflight.json` | All six frozen-core body NIF/TRI files differ from the model's pins. Existing XP32 bytes match. Header/host/provider agreement does not resolve the geometry mismatch. |
| `preflight-runs.json` | Exact external bindings, invocation arguments and exit codes for both runs. |
| `physics-tests.log` | All 106 offline physics tests passed, including eight preflight regressions and their mutation/missing-input cases. |

The source model is `final-020-stable-weight-P1-contact`: 128 slots and 19 ordered
morphs, identity
`CLAW.Physics.CurrentVector.e1ea23b3f3203a242379fdb4c7c64c78f7c2a1c646297fa809726cdc24cf016e`.
The frozen-core comparison reads the retained repository release resources,
not the live installation. The provider snapshot is retained historical evidence,
not a newly observed process configuration.

For any later body revision, reconstruct support from the exact body/weight/TRI
files and XP32 skeleton. A changed physical surface needs a new fit and
measurements; use `rebase-contact-inputs.py` only when its full oriented
triangle/base/weight/TRI comparison proves the physical support unchanged.
Generate matching native and host artifacts and rerun preflight before a game
trial. The current mechanics work does not wait for aesthetic calibration.

Game acceptance still needs actual armor/race/VFS bindings; loaded provider/API,
single-writer and reserved-index qualification; compiled DLL/PEX provenance;
effective-morph/model-update ordering; lifecycle cleanup/reset checks; and node
traces plus visible ear/tail/P1 motion/contact with negative controls, both sexes,
weight/morph extremes and return to neutral. Fur following, animated poses,
scale, HIGGS/PLANCK and close-contact quality receive no new acceptance here.
