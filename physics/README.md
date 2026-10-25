# CLAW.Physics: source-only CBPC ear/tail candidate

This is an **uninstalled development candidate**, separate from the frozen
distribution companion and every quest/plugin record. It retains XP32 and uses
CBPC for both ear chains and the five-link tail. It supplies two original motion
configs, pinned rest-pose capsule data, a generator/validator and a standalone
actor-scoped Papyrus helper. A host controller is deliberately a separate future
integration; there is no automatic assignment, quest patch or installer here.

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
false: `ProviderQualified`, `ExclusiveIndexRange`, `StaticPoseAccepted`. These
must be set by a separately qualified host, not inferred from a successful bool.
The helper observes **current** `Actor.GetRace()`, loaded 3D, readable NPC sex and
node availability immediately before each attach. Human actors receive no attach.

`Synchronize()` performs remove-before-append at own indices, remembers accepted
slots, avoids duplicate reappends, and rolls back an accepted subset after a
failure. Repeated synchronization with the same accepted ledger performs no
append. `Cleanup()` attempts only its remembered indices, including on human
return. Missing 3D/nodes or a false detach retain pending state; absence is never
guessed. Alias retargeting is blocked while the former actor's cleanup is pending.

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

`MarkModelGenerationChanged()` is required after race/3D changes, game load or
provider rebuild. `OnUnload` does this defensively, but the host must forward
all other lifecycle signals. If previous slots remain, reattachment waits for
cleanup or `AcknowledgeProviderReset(previousActor, True)`. That method is an
**external assertion**, allowed only after separately verified reset behavior;
a false detach alone is never evidence for it. The public API cannot independently
prove a provider reset. Papyrus's saved ledger does not imply CBPC containers
survived save/load. Status and ledger count do not certify visible physics.

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
A filename alone never establishes ownership. The build emits only the two configs, own helper PSC,
generated `CLAWPhysicsData.psc` and a hash manifest—no NIF, shared collision file,
plugin, native DLL or release metadata. Outputs must be new external directories
or ignored `work/` descendants; live/source/archive destinations are refused.

Compile both emitted PSCs with Caprica `--game skyrim`, from their `Scripts/Source`
directory, importing installed SKSE, base-game sources and CBPC's public source
declarations. Put PEX output outside Git. Compilation is an offline API/type check,
not an actor/provider test. The optional host/controller is not included.

## Separate integration proposal and acceptance

After goals 1/2 are accepted, a future host may allocate per-reference aliases,
qualify effective config/DLL/API hashes and exclusive bone/index ownership, then
call synchronization for both sexes. It must forward current-race completion,
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
