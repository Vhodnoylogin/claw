# Owned FSMP binding and excitation probe

## Preferred male trial: direct mass-zero anchors

`fsmp_owned_case.run(session, reference, "male", stimulus="xml-anchors")`
is a provider-specific callback within the existing owned Session lifecycle.
Machine paths, profile selection and launch remain in an external harness. It
does not create a testing host or change the maintained executor/provider.

The first real November 11 trial established all nine dynamic bodies and exact
four previous-state transitions, but actor AI-off left model/anchor transforms
stationary while SetPosition changed only the logical reference. That stimulus
was rejected; its failed report remains unchanged. The callback now rejects
that mismatch at the first observed point rather than after three windows.

The successor keeps AI off and writes **only** the two XML mass-zero anchors,
`NPC Head [Head]` and `Tails`, through public NiOverride position transforms. It
requires initially empty transform keys and uses `CLAW.FSMPProbe.<owned-run-id>`.
GetNodeTransformPosition proves storage; same-task World Observer readback
separately proves actual world movement. Dynamic driver transforms are never
written. Native function signatures are inspected before use.

SKEE UpdateNodeTransform recomposes a cached rest transform, including rotation
and scale. Therefore the callback captures the original full local/world
transforms before priming a zero key, then records a separate stimulus baseline.
Before any motion window it checks an actual +0.25 offset and return to zero.
Only if that calibration succeeds do identical ±0.5-key-offset on/off/on windows
begin. Expected movement is measured by inverse primed anchor world transform
times current anchor world transform, so rotation and scale are accounted for.
The actor/root must remain stationary; anchors may translate by exactly the
declared stimulus. All other local/CME and torso/root controls remain quiet.

Cleanup removes only the owned position component, verifies it absent, restores
the captured full local anchor transforms through the public NetImmerse position,
rotation-matrix and scale setters, and reads those originals back. Foreign keys
are never removed or recomposed. The public component-removal API may retain an
empty key container; no transform data or saved-game change is claimed to remain.
Unknown native physics completion still forbids a guessed all-on restoration.

For direct-anchor score input, set `stimulus: "xml-anchors"` and retain raw
`stimulusBaseline` plus `anchorCalibration.moved` and `.reset` snapshots between
reenable receipt and first active sample. The scorer preserves the same strict
receipt order, world/actor/root continuity, cadence and selective-response limits.
Female P1 direct excitation remains outside this male-only trial.

## Retained reference-trajectory protocol

`fsmp_probe.py` is a transport-free test source, not an installer, runner or
provider. It prepares ordinary DevBench tool packets and scores retained actual
World Observer snapshots. It never launches a game, calls a tool, edits MO2,
changes a runtime DLL, retries a mutation or invents state evidence.

## Why world-relative observation

The inspected FSMP source writes `SkyrimBone::m_node->world` in
[writeTransform](https://github.com/DaymareOn/hdtSMP64/blob/e52ad960048c14e637d14fcbd65314ca017fc3b8/src/hdtSkyrimBone.cpp#L92).
The conversion back to `local` is commented out. The earlier stationary case
scored only local transforms, which cannot exclude valid world-only physics.
This is source evidence, not proof of equivalence to the installed FSMP binary.

The existing World Observer returns local and world NiTransforms in one main
thread task. The new probe requests all nine male/eleven female dynamic names
plus the actual mass-zero anchors from `fsmp_motion.render_xml`:

- Ear chains: `NPC Head [Head]`.
- Tail chain: `Tails` (unchanged intermediary CME nodes remain in the skeleton).
- Female P1: `NPC L PreBreast P1` and `NPC R PreBreast P1`.

The actual `CME TailBone01` through `CME TailBone04` intermediaries are also
sampled as local animation controls. Their inherited world motion is allowed;
their local transforms must remain quiet so wrapper animation cannot masquerade
as a selective solver response.

For each dynamic node, the scorer applies **inverse sampled anchor world
transform × sampled dynamic world transform**, including inverse rotation and
scale. It retains local channels as animation controls. Subtracting actor/world
positions alone is insufficient. Missing anchors, a partial snapshot, changed
root/incarnation, replayed timestamps or scale changes fail the check.

## Fresh admission and order

The caller must use the current owned run's actual reference, sex, base,
incarnation, root and origin. Historical FF references and the November 8 gate
are not reusable authority. Verify provider DLL, four current mesh hooks, XML,
skeleton and TRI winners and the absence of a competing CBPC motion owner.
Read the live function descriptions before mutation:

```text
DynamicHDT.TogglePhysics(actor, string[], bool) -> bool[]  (global)
ObjectReference.SetPosition(float, float, float) -> None (member)
```

The [native TogglePhysics implementation](https://github.com/DaymareOn/hdtSMP64/blob/e52ad960048c14e637d14fcbd65314ca017fc3b8/src/dhdtPapyrusFunctions.cpp#L62)
returns **previous** dynamic state. The first all-off request must return nine or
eleven literal `true` values before excitation. Any `false` remains ambiguous
between missing and already kinematic; stop that case. On a completed partial
first-off gate, restore only indices whose previous state was true. A missing or
uncertain native result never authorizes a replay or guessed all-on cleanup.
Reuse the owned runner's existing journal/actor/root fences for every dispatch.

Order: baseline → first-off gate → reenable → settle → active window → second-off
→ settle → stopped window → restore → settle → restarted window. The three
windows use the same 25-point, two-cycle, ±0.5-engine-unit horizontal trajectory
and explicit float JSON arguments. Each SetPosition is followed by 200 ms and a
single coherent observation. The scorer verifies actual reference and model-root
displacement and comparable producer-clock cadence. Each window returns to the
captured origin. Restore that original position on failure only while the same
owned actor/root remains current. Do not continue across a world load/rebind.

The controlled NPC translation is a small explicit stimulus, not a promise of
provider response. The inspected `prepareForRead` resets on root change; it does
not provide an NPC translation-distance reset threshold. No guessed threshold
or solver phase is recorded. Existing finite owner cleanup still ends the case.

```powershell
python src/test/python/integration/fsmp_probe.py prepare `
  --reference '<current-owned-NPC-ref>' --sex female --origin <x> <y> <z> `
  --output '<new-external-plan.json>'

python src/test/python/integration/fsmp_probe.py score `
  '<retained-actual-observations.json>' --output '<new-external-result.json>'
```

The plan deliberately does not flatten the first native gate into an unattended
scenario. The caller must evaluate the real all-true return **before** dispatching
reenable/excitation. Persist all original responses, native receipts, timings,
command results, source/provider pins and cleanup outcomes alongside the report.
Bracket every native call with fresh full baseline-query observations and store
them as that receipt's `before` and `after`. The scorer requires the same session,
incarnation and root and strictly advancing observation order around all windows.

## Scorer input and limits

Input fields are `reference`, `sex`, one raw `baseline` snapshot, `receipts`
with four records `{previous: <exact bool[]>, before: <raw snapshot>, after:
<raw snapshot>}`, and `windows` containing the 25 raw
snapshots for each `active`, `stopped`, `restarted` phase. No normalized or
synthetic observations may be relabelled as runtime evidence. Expected positions
are derived from the captured baseline, not copied from reported commands.

Selective contrast requires both on windows above four diagnostic noise floors
and off response below one quarter of the smaller on response (or the floor).
Every sampled local transform and anchor/root-relative control must remain quiet;
otherwise the result is unconfirmed. If the idle animation changes those controls,
report that limitation instead of weakening thresholds to obtain a pass. A
neutral-pose fixture may need separate preparation, without freezing physics.

The synthetic tests exercise inverse transforms, world-only motion, animation,
inherited movement, cadence, missing bindings/anchors and lifecycle negatives.
They establish scorer discrimination only. Positive runtime output is named
`sampled-selective-contrast-observed`; `solverQualified`, `contactQualified` and
`physicsPhaseObserved` remain false. This does not qualify contact, appearance,
transformation/reload coverage or released physics support.
