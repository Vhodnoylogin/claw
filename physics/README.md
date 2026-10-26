# CLAW.Physics: CBPC ear/tail candidate

## Current automatic source integration

The optional Distribution DLL now observes the provider's actual effective
`IBodyMorphInterface::GetBodyMorphs` result for the generated ordered morph list.
It never substitutes a Papyrus sum of keys or the Distribution key. Six own
scripts (including `CLAWPhysicsNative`) supply the finite host and bridge.
This source integration is built offline; it has no new game acceptance.

The schema-3 current-vector model deforms the measured support points first and
refits each capsule for that vector. Build Distribution with the exact external
generated header through `-PhysicsModelHeader`; build this host with the matching
`--fitted-capsules` JSON. Host and DLL compare complete model identity and ordered
names before observation. Schema-3 data cannot use the older affine Papyrus path.
The ledger supports 128 slots and preserves older short ledgers until resolved.

Explicit activation is `BeginSession(True, evidence)`, `RegisterActor(slot, actor)`
then `EnableAutomaticActor(slot, actor, evidence, True, True, True)`. The three
assertions qualify the actual provider/API and effective configuration, exclusive
reserved indices, and the pinned actor resources and fitted domain. They must be
established by the caller; successful compilation, DLL loading, a nonempty string
or a CBPC bool cannot establish them. Defaults remain disabled. Alternatively
call `EnableAutomaticPopulation(evidence, True, True, True)` once per session after
qualifying the actual resources for the matching population. Distribution then
offers at most 16 known loaded current beasts per scan; the host uses only empty
aliases and never evicts a remembered actor or pending cleanup. Human return or
unload releases a population alias only after reported cleanup. A changed model
blocks rediscovery until a fresh explicit qualification. This reuses Distribution's
actor registry and adds no independent world search.

Human morph family defaults are a separate explicit resource declaration in
`SKSE/Plugins/CLAW/MorphLinks.xml`. The shipped catalog has no defaults. An optional
`Defaults` declaration can name the installed male/female resource profiles; it
does not infer a family from sex or a preset name. Only fresh automatic state
adopts such a profile, after a complete current SKEE source capture. Restored,
existing empty, suppressed, quarantined and manual states retain their policy.

At most 16 explicitly registered actors are sampled on main tasks, with a
coalesced two-second fallback. On coefficient changes the observer asks SKEE to
apply current morphs synchronously on the main task, then requires two stable
sampling passes. Its immutable snapshot token binds the actor runtime identity,
world epoch, alias generation, root, model, independent weight and ordered aggregate. The host's
registered callback consumes the values and, for schema 3, per-slot fitted
capsules. Numeric fitting uses a bounded worker queue with no actor/engine objects.
The main task rechecks identity, root, sex, weight and every provider aggregate
before publication. A changed vector immediately invalidates old snapshots and
requests scoped old-capsule cleanup while fitting is pending. Delayed cleanup
receipts cannot erase a newer accepted snapshot. Every append rechecks snapshot
currency after data reads. External
same-root coefficient changes are detected by the fallback without mod events.
The public API exposes no general provider queue-completion fence; the inspected
SKEE implementation joins its workers and executes partition updates before its
main-thread call returns. Equivalent behavior of the selected runtime provider
still requires qualification.

Human return, unload and a changed root invalidate the snapshot and request
scoped cleanup. Busy or unresolved cleanup is retried at the bounded fallback;
the host renews an unchanged-resource generation only after the remembered ledger
is empty. A changed model requires fresh explicit qualification.
Provider/configuration replacement requires suspension and
fresh qualification. Save/load and new game clear native registrations and
revoke host authority; opt in again explicitly. False detach never acknowledges
a discarded provider container. Pending old ledgers need reported removals or
the existing separately verified reset acknowledgment. Foreign morph keys,
collider indices and node configurations are preserved.

The observer reads the actual same-reference NPC weight, validates 0..100, and
passes its normalized 0..1 ratio as an independent base-geometry input. A weighted
model interpolates base vertices first, then applies absolute TRI deltas. It never
multiplies effective SKEE coefficients by weight again or calls `SetWeight`.
`CLAWPhysicsNative.GetWeight` returns the cached current snapshot input;
Distribution's `GetHumanWeight`/`GetBeastWeight` return last actually observed
normalized values in each form, or -1 when unknown. Co-save v4 preserves these
observations; v1/v2/v3 remain readable. A different actor reference is never
assumed to share another actor's human weight.

The optional `--with-breast-contact` source variant is distinct from the older
zero-collision motion trial. It uses original 0.05/0.01 contact response, bounded
P1 displacement/rotation and the exact female vanilla-werewolf condition. It
requires a clear explicit provider snapshot, a matching schema-3 weighted P1
model, both pinned female body endpoints and an explicit `--breast-profile` JSON
binding its model identity, body hashes, XP32 hash and two existing P1 bone names.
Female-only slots retain global indices and are skipped on males. The profile
records an externally reviewed resource binding; no file hash or response value
alone certifies simulation/contact. The host package still excludes file-loaded
motion configs; selecting that optional source remains explicit.

The older static/manual contracts below remain supported. They describe their
original eight-capsule rest-pose candidate, rather than schema-3 surface fit.

This is an **uninstalled development candidate**, separate from the frozen
distribution companion and its quest/plugin records. It retains XP32 and uses
CBPC for both ear chains and the five-link tail. It supplies two original motion
configs, pinned rest-pose capsule data, a generator/validator, an actor-scoped
Papyrus helper and an optional finite host. An original wiring recipe builds
`CLAW - Physics.esp` with one quest, 16 actor aliases and a separate player load
relay. The dedicated offline build verifies record/VMAD wiring by binary readback
and Spriggit round-trip, and compiles six own scripts. It is an **uninstalled
development candidate**: quest startup, alias fill, Papyrus event delivery,
provider behavior and visible/contact acceptance remain unqualified.

## Inputs and own outputs

`recipe.json` declares `CLAW.Physics`, reserved positive capsule indices
**1129054208..1129054216** (`0x434C0000 + slot`), three unique `CLAW_*` aliases and
the exact condition `IsRaceFormId(Skyrim.esm|000CDD84)`. No sex condition is added.
The generator emits sequential `<`/`>` groups for EarL01/02, EarR01/02 and
TailBone01..05, leaving all CME intermediary nodes and the skeleton untouched.

The two generated files are:

- `SKSE/Plugins/CBPCMasterConfig_CLAWPhysics.txt`: `[ConfigMap]` only, nine
  race-gated node mappings. No global `[Settings]`, MalePhysics or tuning changes.
- `SKSE/Plugins/CBPConfig_CLAWPhysics.txt`: parameters only for those own aliases.
  It is unconditioned so other conditioned bounce configurations can fall back
  to the unique defaults. It changes no human/shared alias.

CBPC loads these motion mappings independently of the Papyrus host. Host opt-in
gates our actor-scoped capsule API; it cannot gate file-loaded CBPC motion. The
dedicated **host-only** ESP/PEX package therefore excludes both configs. They stay
in the separate offline source candidate for a later explicitly qualified setup.

Values are original small-displacement trial parameters, **not proven safe or
visibly effective**: force multiplier 0.1, damping 0.4, displacement clamps
±0.35 per ear link / ±0.5 per tail link, small rotation factors and bounded
collision offsets. See `recipe.json` for every value. They are not a copied
third-party settings preset. All names are checked against the inspected CBPC
parameter contract, including its exact legacy spelling/case.

`capsules.json` pins the original measurement and XP32/male/female NIF hashes.
Measurements used Morphbench's public `chain_capsules`, rest pose, percentile 90,
`body,head`, dominant weight threshold 0.5 and **node-local game units**. These are
not Havok ragdoll coordinates. Generated radius is half the measured radius,
capped at 2 game units: a cautious contact experiment, not an enclosing envelope.
Endpoints remain measured. Source data is retained for both sexes.

TailBone04 remains a motion driver but receives **no fabricated capsule**. Its
6,029 nonzero skin weights did not yield dominant ≥0.5 fit points. Eight other
nodes get capsule candidates; fur/blend layers are excluded from fitting. Morphs,
animated poses, nondefault scales and repaired geometry are not covered by these
static measurements; the host must explicitly accept the selected measurement
pose and rebuild/requalify when the input geometry changes.

## Native API ownership: what a bool establishes

`sources.json` pins the inspected MIT-licensed CBPC implementation and the
installed public PSC/DLL hashes. Source/binary equivalence remains unverified.
No provider implementation or third-party configuration was copied here.

The inspected `scan.cpp` contract matters:

- `AttachColliderCapsule(..., index, True)` **appends** to a tracked actor's
  existing mapped affected-node simulation. A repeated index is not replacement.
- `DetachCollider(actor,node,1,index,True)` removes **all** capsules matching that
  index in that actor/node/type bucket. It does not identify a calling plugin.
- False detach conflates absent capsule, missing node, unloaded reference and
  untracked actor. True attach acknowledges a container append; it does not prove
  motion, coverage, correct timing or contact. No public capsule getter exists.
- The inspected affected-node attach branch ignores `scaleWeight`; this helper
  passes 0 and makes no claim that it controls scaling.

`CLAW.Physics` is our conceptual owner name, **not a native string key**. Index
exclusivity requires coordination with every active provider/mod. The helper
removes only the exact reserved capsule indices with `isAffectedNode=True` and
never invokes global ReloadConfig, StartPhysics/StopPhysics, shared collision
configuration replacement, or a skeleton/body write. An index collision would
make cleanup unsafe; leave its explicit qualification gate false in that case.

## Helper states and lifecycle contract

`papyrus/CLAWPhysicsActor.psc` extends `ReferenceAlias`. Supply exactly one
serialized alias per actor and serialize host calls. Three properties default
false: `ProviderQualified`, `ExclusiveIndexRange`, `StaticPoseAccepted`.
`QualifyForActor` also binds the exact actor, observed model-generation counter
and a nonempty external evidence reference. Flipping those properties alone
cannot qualify attachment. A nonempty string only records an assertion; it does
not verify files, exclusive ownership, binding behavior or the measurement pose.
The helper checks **current** `Actor.GetRace()`, loaded 3D, readable NPC sex,
node availability, exact alias actor and generation before attachment. After
preclean/data reads it checks the attachment context again immediately before
the native append. An actor observed as human at that check is refused.

`Synchronize()` performs remove-before-append at own indices, remembers accepted
slots, avoids duplicate reappends, and rolls back an accepted subset after a
failure. Repeated synchronization with the same accepted ledger performs no
append. `Cleanup()` attempts only its remembered indices, including on human
return. Missing 3D/nodes or a false detach retain pending state; absence is never
guessed. Alias retargeting is blocked while the former actor's cleanup is pending.

Cleanup captures the exact tracked actor and model generation, then rechecks
that actor, generation and provider/index authority immediately before **each**
native detach. It checks again after the call before using a true result to
erase a ledger entry. A change aborts the remaining loop with unresolved entries
retained. Session revocation withdraws native authority before marking the new
generation, so a busy cleanup does not intentionally proceed on its old gate.

These checks and native calls are **not atomic in Papyrus**. A concurrent race,
alias/model or provider event can occur after the last check, including during
the native mutation. An append can therefore be accepted during invalidation,
even if the actor has just become human. The helper records that accepted append,
detects the changed context and attempts rollback; revoked authority, false
detach or missing actor/nodes retains unresolved cleanup instead. A raced
detach result is also kept unresolved. No absolute guarantee of zero appends to
a concurrently changing actor is claimed. Engine scheduling and the final
host/provider lifecycle protocol still require runtime acceptance.

| Status | Meaning |
|---:|---|
| 0 | Dormant/no remembered accepted slots |
| 1 | Provider/index/pose capability blocked |
| 2 | Current reference is not the vanilla beast |
| 3 | 3D unloaded, attachment not attempted |
| 4 | Eight native appends accepted, **no presence/contact readback** |
| 5 | Attach failed; accepted subset removal was reported |
| 6 | Cleanup or prior model/provider generation unresolved |
| 7 | Native reported matching-index removals |
| 8 | Busy; overlapping call refused |
| 9 | Host acknowledged previous provider containers discarded |

`MarkModelGenerationChanged()` increments the generation and expires static-pose
acceptance without erasing the actor or accepted ledger. The alias calls it on
`OnLoad`, `OnUnload` and `OnRaceSwitchComplete`; delivery in the final quest is
still an engine acceptance requirement. A host must also forward load/new-session
and provider rebuild signals. If previous slots remain, reattachment waits for
cleanup or `AcknowledgeProviderReset(previousActor, True)`. That method is an
**external assertion**, allowed only after separately verified reset behavior;
a false detach alone is never evidence for it. The public API cannot independently
prove a provider reset. Papyrus's saved ledger does not imply CBPC containers
survived save/load. Acknowledgment also requires renewed provider/index
qualification. Status and ledger count do not certify visible physics.

## Optional finite host contract

`papyrus/CLAWPhysicsHost.psc` extends `Quest`. The original
`host-wiring.json` recipe and `wiring.py` generate a Spriggit source tree for the
optional **ordinary ESP**, with `Skyrim.esm` and `CLAW.esp` as its only masters.
It contains only our quest `000800`, editor ID `CLAWPhysicsHostQuest`; it adds no
overrides to other plugins. The quest is **not StartGameEnabled** and has no
stages, objectives, conditions, packages or automatic actor search.

Actor alias IDs **0..15** are stable and have explicit null forced-reference
fields (`ALFR=0`), not find-matching conditions. They are Optional and carry
`CLAWPhysicsActor`. Alias **16** is forced to PlayerRef `000014:Skyrim.esm` and
carries only `CLAWPhysicsLoadRelay`. All aliases allow reuse within the quest
so one actor slot may track the player while the load relay also references the
player; the host still refuses duplicates across actor slots. Runtime alias fill
and this reuse behavior remain game acceptance checks.

The quest VMAD gives `CLAWPhysicsHost.ActorSlots` an ordered array of same-quest
alias objects 0..15, and sets `IntegrationOptIn=False`. Every actor helper's three
provider/index/pose properties are explicitly false. The binary validator checks
these fields, the optional/reuse flags, all exact alias script attachments and
the separate player reference. A text or bool alone is not runtime evidence.

The reusable source host also supports **1..16 distinct optional reference
aliases** on another explicitly configured quest. Populate `ActorSlots` explicitly.
The host copies that finite list once; changing the property later does not
replace saved aliases or their cleanup ledgers. Do not stop/reset the quest or
clear/force its aliases externally while remembered capsules remain. The source
host has no actor search, update registration, retry loop or population hookup.

The intended manually driven sequence is:

1. Call `CLAWPhysicsControl.BeginSession(True, evidence)` explicitly. Lookup uses
   `Game.GetFormFromFile(0x800, "CLAW - Physics.esp")`; lookup alone has no startup
   effect. BeginSession starts the stopped quest only when it can inspect empty
   accepted ledgers, revokes old session authority and enables the current host
   session. False opt-in, empty evidence, unavailable/wrong quest, non-ready
   startup or a stopped quest with remembered capsules refuses activation. There
   is no automatic retry. Starting the quest does not qualify a provider or append.
   A direct host consumer may use `EnableIntegration(sessionGeneration, evidence)`
   only after forwarding the session signal and confirming the quest is running.
2. `NotifySessionChanged()` on new/load session or provider replacement disables
   integration opt-in, increments its session generation and revokes provider/index/pose authority for
   every slot and retains every accepted ledger. Optional
   `CLAWPhysicsLoadRelay` on a separate **player alias of the same quest** forwards
   `OnPlayerLoadGame`; it does not attach anything. Record wiring, event order,
   new-game startup and all provider reset signals still need verification.
3. `CLAWPhysicsControl.RegisterActor(slot, actor)` / host `Assign` selects one actor. It rejects an actor assigned to or
   retained by another slot. Before changing an alias it requests cleanup and
   refuses to clear or retarget a pending ledger, including an unloaded former
   actor. Both `Clear()` and `ForceRefTo()` have observed-reference checks because
   those engine operations return no success bool. Assign never attaches.
4. Read control `GetGeneration(slot)` / host `GetSlotGeneration(slot)`, then externally establish the deployed
   provider/API/effective-config hashes, exclusive bone and reserved-index
   ownership, actual race binding and the chosen actor's static measurement
   pose. Call control `QualifyActor` / host `Qualify(slot, actor, generation, evidence, provider, indices, pose)`.
   A changed actor/generation, empty evidence or busy helper refuses qualification.
   Provider/index qualification with pose false permits pending cleanup without
   permitting append. No native version or attach/detach bool provides this proof.
5. Control `PulseActor(slot, actor)` / host `Pulse` makes one synchronization attempt; it requires that the
   expected actor still occupies that slot. It returns the helper status above.
   A lifecycle change expires qualification; repeat the external qualification
   step for the newly observed generation. A pending old ledger still needs
   actual reported cleanup or separately verified container discard.
6. Control `ReleaseActor(slot)` / host `Release` requests cleanup and clears only after the ledger is empty.
   If a qualified provider reset truly discarded the old actor's containers,
   `AcknowledgeReset(slot, previousActor, resetEvidence, True)` may explicitly
   acknowledge that fact. It records the last accepted evidence reference;
   false detach is never converted into a reset assertion.

The control API also exposes `GetStatus` and `GetLedgerCount`; these report the
helper's control ledger, not native presence. `SuspendSession()` disables the
host and revokes qualification without stopping/resetting its quest, clearing
aliases or discarding remembered capsules. Cleanup/release remains available
after suspension; native cleanup still needs separately renewed provider/index
qualification. To renew it through the host, opt in again first. No API scans
the world, chooses actors or automatically starts physics.

Host returns 0 for an accepted control operation, helper status 0..9 for Pulse,
and negative failures: -1 invalid input/topology, -2 duplicate ownership,
-3 unresolved cleanup, -4 alias operation not observed, -5 stale/missing
qualification, -6 integration opt-in missing/stale, -8 overlapping host call. Read `GetLastError()` for control
failures and the actor helper's error/status for synchronization. These are
source-level control outcomes, not certification of native collider presence.

The local base-game PSC declarations were inspected for `Alias.GetOwningQuest`,
`ReferenceAlias.Clear` (fails for non-optional aliases), `ForceRefTo` and forwarded
load/unload/race/player-load events. Compilation checks those declarations;
neither it nor source-contract regression tests establishes engine scheduling
or engine quest integration. This host intentionally leaves that acceptance open.

## Build and offline checks

From the CLAW repository:

```powershell
python physics/build.py
python -m unittest discover -s physics/tests -v
python physics/build.py --out '<new-external-staging-directory>'
```

`--measurements <node-capsule-candidates.json>` checks the exact pinned source
hash and coordinates. `--check-provider <effective-SKSE/Plugins-snapshot>` refuses
another master mapping of these bones, reuse of private aliases in master/bounce
files, and exact node references in supplied SMP XML. It preserves every matching
declaration, line and condition; it never guesses a duplicate winner or treats
apparently disjoint conditions as exclusive ownership. Unreadable configs/XML or
DTD/entity declarations leave the audit unresolved. The build records every
supplied matching config/XML/provider-DLL hash and rechecks the complete inventory
before reporting success. File addition/removal also expires the receipt.

It does not guess MO2 winners or certify archives, NIF-selected XML, generated
bindings, the actual process VFS, loaded SMP ownership or reserved native indices.
Supply the baseline before adding this candidate; all matching `.txt`/`.ini`
masters are checked, including CLAW-looking filenames. A filename alone never
establishes ownership. `python physics/audit-provider.py --snapshot '<snapshot>'
--out '<new-external-directory>'` retains the report even when conflicts block a
build. The same audit runs inside `build.py --check-provider`; its receipt is
embedded in a successful source manifest. The default build emits the two configs,
own actor/host/load-relay/control PSCs, generated `CLAWPhysicsData.psc` and a hash manifest—no NIF, shared collision file,
plugin, native DLL or release metadata. Outputs must be new external directories
or ignored `work/` descendants; live/source/archive destinations are refused.

## Explicit breast P1 motion source trial

The separate `breast-motion.json` recipe supplies original small-displacement
trial values for **only** existing `NPC L/R Breast P1`, using private
`CLAW_BreastL/R` aliases and the exact female + vanilla-werewolf condition.
It retains XP32 and writes no skeleton or body. This remains an uninstalled
source trial, with no visible motion, race rebinding, single-provider ownership
or runtime acceptance. Ordinary human Breast/3BA aliases are separate XP32
branches; their presence alone does not establish P1 motion.

Opt in only with the exact raw collar+P1 body `6792fc6c...e33d` and reviewed XP32
`b64b614d...2dd0`. The generator reads both hashes, requires a supplied baseline
provider audit and refuses known P1/pre-P1/parent mappings, private alias reuse
or matching SMP XML references. This includes the complete pinned ancestry to
Spine2, Spine1, Spine, COM and root: a configured ancestor simulation could move
P1 by inheritance. Ordinary skeletal animation is not a provider mapping. It
rechecks input bytes and the snapshot after
writing. Those static gates are prerequisites, not proof that an unseen loaded
provider cannot own P1. Actual loaded-node ownership must be qualified before
any later deployment; do not add a second writer to an already owned branch.

```powershell
python physics/build.py --out '<new-external-source-directory>' `
  --check-provider '<explicit-baseline-SKSE/Plugins-snapshot>' `
  --with-breast-motion --breast-body '<reviewed-raw-91-node-body.nif>' `
  --skeleton '<reviewed-existing-XP32-skeleton.nif>'
```

This adds `CBPCMasterConfig_CLAWBreastPhysics.txt` and
`CBPConfig_CLAWBreastPhysics.txt` to the independent source candidate. Force is
0.03, translation clamps are +/-0.15, rotation offset clamps +/-0.1 and rotation
factors 0.005. These are original trial parameters, not measured safe envelopes.
Both contact multipliers are zero: this trial adds no P1 capsule/contact model.
The optional finite host still handles only the eight ear/tail capsule slots;
host opt-in cannot gate any file-loaded motion. The host-only ESP/PEX package
continues to exclude every motion config. No production/default rig or recipe
is enabled by this option. A completed source manifest confirms only the stated
offline checks; an incomplete build retains `FAILED-unverified-do-not-install`.
The newer fur follower `d99a1180...276d` and its bounds variants remain separate
inputs. This first motion recipe deliberately refuses them; they require a new
explicit geometry pin and motion/bounds requalification, not a silent pin update.

## Compilation and host package

Compile all five emitted PSCs with Caprica `--game skyrim`, from their `Scripts/Source`
directory, importing installed SKSE, base-game sources and CBPC's public source
declarations. Put PEX output outside Git. Compilation is an offline API/type check,
not an actor/provider test. Tests cover data/isolation and source safety contracts
for pending cleanup, alias operation failures, duplicate ownership, qualification
expiry, load revocation and explicit reset acknowledgment. They inspect actual
shipped PSC guards/call order; they do not execute Papyrus, native calls or events.

To build the optional **host-only ESP + five PEX** candidate, use the separate
explicit tool entrypoint; all arguments are installed tools/imports, not downloads:

```powershell
python physics/build-host.py --out '<new-external-directory>' `
  --compiler '<Caprica.exe>' --spriggit '<spriggit.exe>' --flags '<TESV_Papyrus_Flags.flg>' `
  --import-path '<SKSE-Scripts-Source>' --import-path '<base-game-Scripts-Source>' `
  --import-path '<CBPC-public-Scripts-Source>'
```

This generates three deterministic JSON-syntax `.yaml`/metadata files, a valid
YAML subset accepted by the pinned installed Spriggit 0.41.0 package. It needs no
Python YAML dependency. Sources remain in `plugin-source/`, compiler/Spriggit logs
and tool/source hashes in `physics-host-build.json`, decoded binary wiring in
`plugin-binary-readback.json`, and the host-only candidate in `package/`. Own PSCs
are included for coordinator imports. The independent motion configs remain in
`source-package/SKSE/Plugins/`; the package validator refuses them in `package/`.
Existing outputs,
source/live mod destinations and import-directory descendants are refused.

The build independently reads the actual ESP's TES4/QUST/subrecord/VMAD bytes,
checks identity, masters, stopped quest flags, 17 alias IDs/fills/flags, same-quest
property objects, helper/relay attachments and false gates. It then serializes
with Spriggit, rebuilds that text and compares the decoded wiring. This verifies
the record and property types written by the installed tool, not their runtime
meaning or Papyrus stack/event behavior. The build preserves all intermediate
receipts. It installs, starts and tests no game/profile/actor.

## Separate integration proposal and acceptance

After goals 1/2 are accepted, a coordinator may opt into the optional
host's finite aliases, qualify effective config/DLL/API hashes and exclusive
bone/index ownership, then call synchronization for both sexes. It must verify current-race completion,
3D unload/reload, save/new/load and provider reset events; use bounded retries
only for known startup readiness, and preserve unresolved cleanup on failure.
CBPC maps conditions during binding; race rebind behavior itself needs verification.
Do not let SMP drive the same ear/tail bones. Installed collision presets can
already target werewolves; this candidate leaves their whole-actor selection intact.

Acceptance needs node-transform traces plus visible motion, negative/noncontact
controls, human return, loaded-model replacement, save/load, duplicate events,
both sexes and morph/scale extremes. CBPC's male/female player-collision mod events
can evidence its internal overlap; they do not prove HIGGS/PLANCK Havok contact,
grabbing, force response or simulation correctness. No runtime success is claimed.

Primary contracts: [CBPC scan/API](https://github.com/Acro748/CBPCSSE/blob/fabd56ce8f8ac10cde17325f0bd61ecc8cbcda20/CBPC/scan.cpp),
[simulation binding](https://github.com/Acro748/CBPCSSE/blob/fabd56ce8f8ac10cde17325f0bd61ecc8cbcda20/CBPC/SimObj.cpp),
[parameter reads](https://github.com/Acro748/CBPCSSE/blob/fabd56ce8f8ac10cde17325f0bd61ecc8cbcda20/CBPC/Thing.cpp).

## Optional morph-responsive capsule bundles for SE and VR

The public `AttachColliderCapsule`/`DetachCollider` declarations and inspected
implementation are shared by SE and VR; these calls are outside the VR-only
branches. Basic CBPC ear/tail motion and CBPC contact therefore need no headset,
HIGGS or PLANCK. This source inspection does not qualify a particular game/DLL.
SE needs its own matching provider, exact installed inputs and a separate game
acceptance run. CBPC capsules do not replace Havok movement, ragdoll or strike
collision bodies; an SE weapon hit is not proof of CBPC contact.

`fit-capsules.py` builds a separate affine node-local fit from explicit regional
geometry evidence. Schema 1 retains the eight measured capsules; schema 2 permits
**1..32 stable capsule slots**, including several capsules on one existing bone.
Each has its own reserved `indexBase + slot`. The current 32-slot bundle covers
selected dominant-skin regions and fully assigned regional triangles over its
closed morph box, using full normalized rest skinning. Unassigned boundaries,
fur, animated poses and altered bone/actor scale remain outside that proof.
Its quality report still says `surfaceFitAccepted=False`: enclosing selected
geometry is not proof of a close visible fit or acceptable contact onset.

```powershell
python physics/build.py --fitted-capsules '<explicit-fitted-capsules.json>' `
  --out '<new-external-source-directory>'
python physics/build-host.py --fitted-capsules '<explicit-fitted-capsules.json>' `
  --out '<new-external-host-directory>' --compiler '<Caprica.exe>' `
  --spriggit '<spriggit.exe>' --flags '<TESV_Papyrus_Flags.flg>' `
  --import-path '<explicit-public-source-imports>'
```

This option consumes the exact fitted endpoints/radii and their signed
coefficients. It **does not** apply the legacy half-radius or two-unit cap.
It captures and rechecks the fit file, records its hash and original geometry
source pins, and emits a generated model identity. The default static eight-slot
candidate remains a distinct build. File-loaded motion still has nine bones;
capsule slot count does not change simulation ownership or the skeleton.

The optional host exposes `CLAWPhysicsControl.GetMorphCount()` and
`GetMorphName(index)`. A coordinator must read the **effective aggregate across
all SKEE keys** for those exact TRI names, wait for the corresponding model update,
and call `PulseMorphActor(slot, actor, values, evidence)`. The inspected public
Papyrus NiOverride API has per-key reads and key enumeration but no equivalent
of native `IBodyMorphInterface::GetBodyMorphs`; blindly summing keys can disagree
with SKEE aggregation policy. The caller must provide a qualified aggregate
reader. This candidate does not yet include that observer or automatically
subscribe to Distribution changes.

The current ordered ten inputs include head/muzzle and torso fields affecting
ear/tail bases, as well as the obvious ear/tail fields. Values must be finite
and inside **[0,1]**, without silent clamping. Caller snapshots must be serialized
and immutable while copied. The helper makes a private copy, checks generation,
and uses signed affine changes, so a related value can expand or shrink both
endpoints and radius. An unchanged vector skips append; a changed vector first
removes remembered own indices, then appends the new set. Invalid domain values
request scoped cleanup and block append; unresolved cleanup is retained.

Model/load/race changes revoke morph qualification. Old saved nine-slot ledgers
remain readable; larger capacity is adopted only after all old bits are resolved.
A different model identity with remembered slots refuses native mutation rather
than interpreting old indices using a new layout. No new/read-only status call
discards a remembered slot. These source/compilation checks do not establish
native presence, race rebinding, atomic Papyrus scheduling, motion or contact.
