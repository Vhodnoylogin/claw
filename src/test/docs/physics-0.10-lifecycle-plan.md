# Motion physics 0.10: remaining acceptance gates

This is a proposed technical acceptance plan, not new runtime acceptance. Scope:
ear/tail motion for both sexes and existing female P1 motion, with one provider
per case. Contact colliders, VR, new breast geometry and aesthetics remain deferred.
The motion-only adapters do not enable the separate finite collider host; its
snapshot/ledger guards do not establish a motion provider's binding or cleanup.

## Retained baseline

- FSMP case08, `20261111-203138-d854f8`, source
  `5c77c87879caea8107beafd9e7a2bfd9756f7c0c`, passed and restored. All eleven
  female drivers passed the fresh previous-state gate and protocol/2 returned-
  anchor on/off/on contrast. Its 300 read-only samples had 0.0507–0.1828-second
  gaps; all anchor components were removed and original local transforms read
  back. Menu exit was `0`, 154 profile preimages matched, and inputs were unchanged.
  Evidence: external `Builds/claw-fsmp-live-20261111-08/actual-case-summary.json`
  and `runtime/runs/20261111-203138-d854f8/result.json` beneath that directory.
- This proves sampled nominal response, not render/solver-phase synchronization,
  lifecycle rebinding, every morph/scale combination or resource-envelope safety.
  Earlier male evidence remains separately scoped; female eleven-node success
  does not substitute for a matching male nine-node lifecycle case.
- CBPC case01, `20261111-204915-97db89`, failed **before the subject**: no fixture
  enable and zero CBPC control calls. The retained dump supports the ongoing
  DevBench/CommonLib object-array decoding investigation; it is not a CBPC
  motion failure. Evidence: external
  `Builds/claw-cbpc-pulse-live-20261111-01/actual-case-summary.json`.
  Nominal CBPC response still awaits the repaired-provider case. Its isolated
  master also omitted a bare `Pelvis` row; standard-master compatibility is a
  separate unresolved gate, not covered by isolated success.

## Smallest scenario after nominal response

Reuse the owned Session, `owned_anchors.py`, and the existing provider-specific
callbacks/scorers under `src/test/python/integration/`. Add lifecycle orchestration
around completed pulse segments; do not weaken a segment's root/epoch continuity
checks to span a transformation or load. Start with one human-origin female NPC
and one male NPC, sequentially, in the dedicated FHD test profile. Reuse the
authored `CLAWBeastFormEffect` fixture for its configured Nord return; prepare an
explicit equivalent male record rather than changing a born-beast actor's label.
Keep a separate born-beast control for admission-origin differences.

| Boundary | Required observation and failure condition |
| --- | --- |
| Human admission → first wolf | Capture actual human race/base/sex, source keys and loaded graph first. Transform by the fixture's declared mechanism; observe actual wolf race, body/TRI/XML or ConfigMap winners and new graph. Require fresh nominal response without a global provider reload. Human-origin base race remains human: use a separate lifecycle admission rule, not the born-beast callback's base-race assertion. |
| Same-model CLAW refresh | Record graph identities and coefficients; call `CLAWDistributionNative.Refresh` once and wait for actual status/coefficient readback. A queued `true` is insufficient. If the graph stays unchanged, require continuing contrast without a new provider system or lost morph/coat ownership. If parts/root change, classify and requalify that boundary explicitly. |
| Wolf → human → wolf | Finish pulse cleanup before each transition. On human return, no wolf-only aliases/system or stale probe key may affect the human graph; independent human physics remains unchanged. Second wolf form needs fresh graph admission, binding evidence and full response, never reuse old Toggle receipts or captured transforms. |
| Actual model recreation | Use one installed, inspected public model-update mechanism and record real root/current-part replacement; a refresh receipt alone does not prove recreation. Reject old graph observations and prohibit old-anchor cleanup against the new graph. Fresh response must follow automatic provider rebinding. |
| Save/load in wolf form | Remove all test-owned components and verify originals before saving. Use an owned save and exact hashes. Observe genuine load/world-epoch change, reacquire by plugin/local ID, verify source keys/coefficient/coat persistence and run fresh binding/response checks. No prior token, root, sample ID or Toggle return remains authority. |
| Unload/reload | Exercise one declared cell/3D unload and return, with probe keys already removed. Observe actual unloaded then new loaded graph, no stale writes, and fresh response. A disabled fixture is not by itself proof of a cell-unload path. |

One provider/sex segment first establishes these boundaries. A separate finite
segment covers the other sex; combine cases only when the declared deadline and
cleanup allowance remain adequate. Retain each boundary's raw before/after
identity, command receipt, graph generation, native state, pulse samples and
cleanup outcome. Never infer a new graph merely from a changed logical position.

## Provider-specific assertions

- **FSMP:** verify all four installed mesh hooks and selected XML; males request
  nine dynamic bodies, females eleven. Each new graph requires the existing
  exact previous-state bool-array sequence before excitation. A missing/uncertain
  return stops the case; restore only states known from completed receipts on
  the same graph. Check that root/part replacement does not accumulate duplicate
  systems. Toggle success alone cannot count or retire old systems: qualify an
  installed diagnostic/readback for that check or retain it as unknown.
- **CBPC:** after nominal admission, test human-origin rebinding with the stock
  master restored. `StartPhysics`/`StopPhysics` have completed void receipts, no
  previous-state or bound-node inventory. Retain own-local **and** actual-parent-
  relative selective response for every driver; inherited parent motion fails.
  Add a passive pulse segment before the first Start call to test automatic
  gameplay activation. A one-off `ReloadConfig` may diagnose a failed rebind in
  a separately declared case; it must not silently turn a failed normal path
  into acceptance or become an unproved production workaround.

## Eligibility, interference and cleanup

1. Pin effective provider binaries/configs, released body endpoints/TRIs, skeleton,
   hooks, source and fixture bytes. Repeat static driver/ancestor/private-alias
   audit against the **standard** effective configuration. Two writers or an
   unresolved ancestor writer block deployment; do not delete stock rows merely
   to manufacture release compatibility. A conflict negative can remain offline.
2. Verify human, male-P1 and unrelated-race exclusions against actual effective
   conditions; retain human source/morph keys and independent control nodes.
   Exercise supported finite weight/morph endpoints and actual actor/node scale
   as technical stability cases, without aesthetic scoring. Audit each FSMP
   joint relative to its declared constraint body, not accumulated Head/Tails
   motion; the unit-scale authored envelope cannot be assumed at scale 1.13.
3. Keep the predeclared returned-anchor pulse/cadence and quiet independent
   controls. FSMP world-only writes and CBPC local writes retain different
   scorers. No direct dynamic-driver stimulus or continuing-anchor P1 shortcut.
4. Remove only the current run's position components, attempt every captured
   anchor cleanup independently, and read back originals. Never restore stale
   transforms after graph loss or guess a compensating CBPC state. Preserve the
   first failure alongside cleanup failures; unknown completion forbids replay.
5. Dispose only the identity-guarded fixture, observe disabled state and null
   crosshair, then ordinary menu exit. Retain the process observer through exit;
   require restored profile/INI/source preimages and no owned processes left.

## Release decision

Current open gates: CBPC nominal and stock-master compatibility; both providers'
human-origin/recreated-graph lifecycle; refresh, unload and saved-world rebind;
single-writer exclusions and cleanup; finite resource-envelope checks. A provider
passes only its actual tested runtime/resources and all requested drivers. AE/VR,
contacts, solver-phase synchronization and visual quality receive no acceptance
from SE samples. If public APIs cannot prove old-system retirement, keep that
specific unknown explicit rather than inventing qualification flags or a getter.
