# Nonshipping mixed-source replay — 18 November 2026

The accepted SE run `20261118-225457-40b531` used two owned CBBE/BHUNP fixture
actors, the unchanged `a1012340…` CLAW DLL and the original native evaluator.
It covered human → wolf → owned save/load → human, a source update while already
a wolf, deletion of both test keys and cleanup. This is a declared skin/body
route test, not an automatic classifier for arbitrary installed body mods.

`python/integration/mixed_source_readback.py` retains the frozen case's pure
storage/input/scoring functions. Python does not evaluate matrix coefficients.
The replay compares actual independent SKEE reads against **recorded native CLI
predictions**. The original root verification separately re-executed that CLI;
the portable replay does not re-execute it or admit today's binaries.

The reviewed external `ACTUAL-MIXED-SOURCE-REPLAY.json` has SHA-256
`cbcb031572849c27f6b6de6b29e8ef3f829e1957854f52520df01962b61b5c74`.
It contains selected exact JSON fields from the archived run, their original
file hashes and unchanged selected Observer packet objects. It contains no
licensed assets, absolute machine paths or native executable commands. The
selection is a projection, **not** a claim that the whole archived files or
baselines are byte-identical to their redacted representations. The original
whole-baseline digest is retained as a reference; only its numerical/source
inputs are independently rebuilt here. Native prediction path provenance is
omitted. Extraction and one-off function-AST equivalence receipts stay external.

Select that immutable bundle explicitly:

```powershell
$env:CLAW_MIXED_SOURCE_READBACK_EVIDENCE = '<archived-ACTUAL-MIXED-SOURCE-REPLAY.json>'
$env:CLAW_MIXED_SOURCE_READBACK_REQUIRED = '1'
python -B -m unittest discover -s src/test/python/integration -p 'test_mixed_source*.py' -v
```

The focused suite has 14 portable symbolic tests, seven actual-data tests and
two explicit-selection tests: **23 pass, zero skips** with the selected bundle.
With no selection the actual class visibly skips; `REQUIRED=1`, an explicitly
missing input or altered digest fails. Symbolic inputs qualify the checker only.

The replay checks:

- All 14 full captures and every one of 31 target float32 values; zero expected
  values require absence of CLAW's key. A present empty SKEE name bucket remains
  valid after the last key is cleared.
- The independently observed aggregate and both run-owned keys on `Breasts`,
  the `.0625` intermediate value after the first clear, all other configured
  source values and all unrelated provider keys. The source catalog has 91
  names; its union with the 31 targets contains 118 distinct names.
- Four one-packet response markers, explicitly `PROVISIONAL` with
  `fullSourceVectorFresh=False`: only `Breasts` is fresh; other human source
  rows and traits/weight are retained. These markers cannot replace the four
  subsequent full actor barriers with fresh complete source and target reads.
- Nine source operations, one owned save/load, load-generation progression,
  both observed families, return races and original actor weights. The full
  unchanged-target and foreign-key checks remain mandatory after each response.

Corruption controls cover altered/zero-owned targets, unrelated source/key
changes, case aliases, nonfinite/unavailable data, stale actor/world identity,
truncated key traversal, false full-proof marker labels, missing full audits,
extended reaction-budget metadata, incomplete operations and unknown mutation.

The historical root verification also confirmed normal exit0, exact restoration
of 122 snapshot preimages, 268 cold profile/payload pins and 266 VFS winners.
Those live-file/process facts are **not reverified** by this portable bundle.
Human traits remain explicitly subject-cached inputs; SKEE storage/status and
numerical correspondence do not establish rendered human vertex deformation,
CPU skinning, GPU positions, visual attachment, physics or VR behavior.

No launcher, manager API, game connection or storage mutation is imported by
these tests. The bundle and compiled test fixtures stay outside Git and release
packages. The original failed attempts and native CLI verification are retained
separately; this passing replay does not rescore their failures.
