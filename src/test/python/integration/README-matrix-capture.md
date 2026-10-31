# Independent captured-matrix analysis

`analyze_matrix_capture.py` reads retained game captures. It never connects to
Skyrim, changes a profile or loads the game DLL. The explicitly pinned
`claw-preset-tool matrix` command executes the same C++ kernel as the runtime and
Morphbench WASM. Python does not reimplement coefficients, functions, ordered
summation, float32 normalization or gain omission.

Supply the exact XML installed for the captured run and verified CLI/XML SHA256
pins. A new executable is not evidence that an older game run used that DLL.
Verify the collector's packet and qualification separately before analysis.

```powershell
python src/test/python/integration/analyze_matrix_capture.py `
  --xml '<archived selected MorphLinks.xml>' --xml-sha256 '<verified XML SHA256>' `
  --cli '<built claw-preset-tool.exe>' --cli-sha256 '<verified build SHA256>' `
  --capture '<retained step JSON or raw snapshot JSON>' `
  --before '<optional same-reference baseline snapshot>' `
  --output '<new external report.json>'
```

Alternatively use `--order '<frozen schema2 order.json>' --run '<collected run>'`
instead of `--capture/--before`. Run mode supports both the retained
`actor-morph-link-evaluation` and additive `actor-morph-capture` domains. It checks
the installed XML pin, checkpoint names, requested profile/stage/fixture labels,
name/key coverage and passive intervals when present. It retains the original
game result/restoration fields; its numerical result does not certify all game
checks or restoration. Explicit `compareSnapshot` links compare retained
predecessors. Without such a link or `--before`, preservation is unavailable.
Cross-reference/save-remap identity needs independent tooling evidence; this
analyzer does not substitute a matching fixture label for a changed reference.

Exit status is 0 for passing observed checks, 1 for a completed mismatch report,
and 2 for invalid/unavailable inputs. Invalid argument combinations and an existing
output are refused. Reports retain input hashes and do not overwrite old evidence.

## Storage and presence contract

- Names retain their spelling; provider identity folds ASCII letters only. Morphs
  are printable ASCII up to 160 characters, provider keys up to 128. Ambiguous
  case aliases, unavailable/nonfinite records and duplicate JSON keys are refused.
  Supplied direct/nested actor references also require nonempty bounded printable
  identifiers and must agree; two empty strings cannot establish actor identity.
- Source aggregates are independently observed inputs. Their values are not
  reconstructed by summing provider keys. Complete source key lists and target
  key lists must agree with their captured availability/presence/scalars.
  `HasBodyMorphName=true` with no keys is valid: SKEE's `ClearMorph` removes the
  final key while retaining its name bucket. This remains distinct from an
  absent name; an absent name with stored keys is refused.
- Every nonzero expected output requires an actual nonzero own-key entry. A
  numeric tolerance (at most 1e-4) applies to its coefficient only. Human,
  suppressed and zero-output states require structural key absence, including
  the absence of stored zero or tiny entries. Extra observed custom own targets
  are checked too. Another mod's zero-valued key remains a present foreign key.
- Before/after comparisons preserve exact foreign values and presence within
  the observed lists. Passive intervals also require unchanged own storage.
- `claw-preset-tool matrix-info <XML> <profile>` reports the canonical **active**
  graph after the native parser's gain omission/validation. Sources carry kind
  `skee-morph` or `actor-weight`, and targets are actual active names. Coverage
  requires the active SKEE reads/targets only. Constant/zero/tiny rows do not
  create invented human reads; Python does not copy the cutoff or parse rules
  into a second evaluator.

## Independent actor weight

`$actor.weight` is an actor scalar, never a SKEE name or provider-key assignment.
The current collector already retains World Observer's sampled actor weight in
`raw.identity.actor.weight`, within its actor/world/provider identity bracket:

```json
{
  "identity": {
    "sessionId": "ACTUAL-OBSERVER-SESSION", "loadGeneration": 1,
    "identity": {"form": "0xACTUALREF"},
    "actor": {"weight": {"status": "available", "rawNPCWeight": 25,
                         "normalizedNPCWeight": 0.25}}
  },
  "weightRaw": 25, "weightNormalized": 0.25
}
```

This is a shape example, not a game witness. The observer source emits the actual
`TESNPC::weight` property; the collector copies it after checking the surrounding
identity. The analyzer requires available weight plus the observed reference,
session and world generation when the native graph includes the scalar. Flat
`weightRaw` alone or a fake `$actor.weight` SKEE record is insufficient. Missing
weight is unavailable; no cached human history or guessed zero is substituted.
Convenience fields, when present, must equal their independently retained sample.

The analyzer passes raw NPC weight through native CLI option
`matrix <XML> <profile> --actor-weight-raw <NPC0..100>`. That uses the runtime's
`captureActor`/`normalizedActorWeight` path for validation, float32 and division by
100. Python supplies no normalization formula. The collector's normalized value
is retained as producer evidence, not substituted for native calculation. The
original normalized `$actor.weight<TAB>value` CLI input remains supported for
offline vectors; combining it with the raw option is rejected.

Scalar-free historical XML/captures retain their old requirements. Constant-only,
empty and inactive-scalar graphs need no weight. Before/after comparisons report
raw actor-weight preservation separately from SKEE aggregates/foreign keys; two
independent weight witnesses are required for that claim. None of these checks
qualifies the producer or retrospectively creates a missing game measurement.

## Optional complete provider namespace

Requested target lists alone cannot prove that an arbitrary old name was
removed. Reports mark global cleanup/foreign preservation unavailable unless
`raw.namespace` meets the producer's complete `VisitMorphValues` wire contract:

- `method=VisitMorphValues`, `scope=stored_morph_key_values`, `status=available`;
- `complete`, `providerTraversalCompleted`, `contextGuardProvided` and
  `contextCurrent` are explicitly true;
- `truncated`, `invalidMorph`, `invalidKey`, `invalidActor`, `nonFinite`,
  `captureFailure`, `aliasAmbiguous`, `duplicatePair` and `identityUnsupported`
  are explicitly false; a missing flag also refuses global completeness;
- `callbackCount=retainedCount=len(entries)`, at most 4096 stored tuples and
  512 distinct morphs; ordered nonnegative integer monotonic start/finish;
- each tuple contains an available finite `morph/key/value`, preserving spelling
  and zero entries, with no folded duplicate/alias identities.

The inventory must agree exactly with requested key reads. Complete captures
check the entire own-key set against native nonzero output and detect stale own
names outside the requested list. Two complete inventories additionally compare
every foreign stored tuple. Extra timing/context/producer metadata is retained by
the original capture and need not be removed. These flags are evidence from a
separately qualified producer; this consumer does not qualify the producer itself.

## Focused native integration checks

```powershell
$env:CLAW_MATRIX_CAPTURE_CLI = '<built shared-kernel CLI>'
$env:CLAW_MATRIX_CAPTURE_CLI_SHA256 = '<verified build SHA256>'
python -m unittest discover -s src/test/python/integration -p test_matrix_capture.py -v
```

The CLI is mandatory; a missing integration input fails rather than silently
skipping coverage. Synthetic cases exercise native nonlinear/constant/empty and
epsilon boundaries, structural zero-key rejection, case identity, foreign-key
preservation, active sparse graph coverage, scalar-only/mixed raw weight,
missing/invalid weight, complete-namespace failure flags and run-parser provenance. They
do not claim a game run or visual acceptance.
