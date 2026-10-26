# CLAW.Physics: source-only CBPC ear/tail candidate

This is an **uninstalled development candidate**, separate from the frozen
distribution companion and every quest/plugin record. It retains XP32 and uses
CBPC for both ear chains and the five-link tail. It supplies two original motion
configs, pinned rest-pose capsule data, a generator/validator, an actor-scoped
Papyrus helper and an optional finite source host. There is no automatic
assignment, quest/plugin record patch or installer here. Host record wiring and
engine lifecycle delivery remain unqualified; none of this is installed.

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

`papyrus/CLAWPhysicsHost.psc` extends `Quest`. A future integration must create
its own persistent quest with **1..16 distinct optional reference aliases**, each
carrying `CLAWPhysicsActor`, on that same quest. Populate `ActorSlots` explicitly.
The host copies that finite list once; changing the property later does not
replace saved aliases or their cleanup ledgers. Do not stop/reset the quest or
clear/force its aliases externally while remembered capsules remain. The source
host has no actor search, update registration, retry loop or population hookup.

The intended manually driven sequence is:

1. Call `NotifySessionChanged()` before operations in a new/load session or
   after provider replacement. This revokes provider/index/pose authority for
   every slot and retains every accepted ledger. Optional
   `CLAWPhysicsLoadRelay` on a separate **player alias of the same quest** forwards
   `OnPlayerLoadGame`; it does not attach anything. Record wiring, event order,
   new-game startup and all provider reset signals still need verification.
2. `Assign(slot, actor)` selects one actor. It rejects an actor assigned to or
   retained by another slot. Before changing an alias it requests cleanup and
   refuses to clear or retarget a pending ledger, including an unloaded former
   actor. Both `Clear()` and `ForceRefTo()` have observed-reference checks because
   those engine operations return no success bool. Assign never attaches.
3. Read `GetSlotGeneration(slot)`, then externally establish the deployed
   provider/API/effective-config hashes, exclusive bone and reserved-index
   ownership, actual race binding and the chosen actor's static measurement
   pose. Call `Qualify(slot, actor, generation, evidence, provider, indices, pose)`.
   A changed actor/generation, empty evidence or busy helper refuses qualification.
   Provider/index qualification with pose false permits pending cleanup without
   permitting append. No native version or attach/detach bool provides this proof.
4. `Pulse(slot, actor)` makes one synchronization attempt; it requires that the
   expected actor still occupies that slot. It returns the helper status above.
   A lifecycle change expires qualification; repeat the external qualification
   step for the newly observed generation. A pending old ledger still needs
   actual reported cleanup or separately verified container discard.
5. `Release(slot)` requests cleanup and clears only after the ledger is empty.
   If a qualified provider reset truly discarded the old actor's containers,
   `AcknowledgeReset(slot, previousActor, resetEvidence, True)` may explicitly
   acknowledge that fact. It records the last accepted evidence reference;
   false detach is never converted into a reset assertion.

Host returns 0 for an accepted control operation, helper status 0..9 for Pulse,
and negative failures: -1 invalid input/topology, -2 duplicate ownership,
-3 unresolved cleanup, -4 alias operation not observed, -5 stale/missing
qualification, -8 overlapping host call. Read `GetLastError()` for control
failures and the actor helper's error/status for synchronization. These are
source-level control outcomes, not certification of native collider presence.

The local base-game PSC declarations were inspected for `Alias.GetOwningQuest`,
`ReferenceAlias.Clear` (fails for non-optional aliases), `ForceRefTo` and forwarded
load/unload/race/player-load events. Compilation checks those declarations;
neither it nor source-contract regression tests establishes engine scheduling
or final quest integration. This host intentionally leaves that acceptance open.

## Build and offline checks

From the CLAW repository:

```powershell
python physics/build.py
python -m unittest discover -s physics/tests -v
python physics/build.py --out '<new-external-staging-directory>'
```

`--measurements <node-capsule-candidates.json>` checks the exact pinned source
hash and coordinates. `--check-provider <effective-SKSE/Plugins-snapshot>` refuses
another master mapping of these bones. It does not guess MO2 winners and cannot
prove loaded SMP ownership. Supply the baseline before adding this candidate;
all matching `.txt`/`.ini` masters are checked, including CLAW-looking filenames.
A filename alone never establishes ownership. The build emits only the two configs,
own actor/host/load-relay PSCs, generated `CLAWPhysicsData.psc` and a hash manifest—no NIF, shared collision file,
plugin, native DLL or release metadata. Outputs must be new external directories
or ignored `work/` descendants; live/source/archive destinations are refused.

Compile all four emitted PSCs with Caprica `--game skyrim`, from their `Scripts/Source`
directory, importing installed SKSE, base-game sources and CBPC's public source
declarations. Put PEX output outside Git. Compilation is an offline API/type check,
not an actor/provider test. Tests cover data/isolation and source safety contracts
for pending cleanup, alias operation failures, duplicate ownership, qualification
expiry, load revocation and explicit reset acknowledgment. They inspect actual
shipped PSC guards/call order; they do not execute Papyrus, native calls or events.

## Separate integration proposal and acceptance

After goals 1/2 are accepted, a future quest integration may wire the optional
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
