# Development mechanism verification — 1 November 2026

This record applies to CLAW source `c84d6eb71cc40cf6e77e85e794fecfe187baab0c`
and installed universal DLL SHA-256
`dd8f075543977531254c1dbb58ed3c3dc1441a06a880209518470da6fa5d6113`.
It is development evidence, not a new public release or acceptance of later
source changes. The actual game is Skyrim SE 1.7.104 with SKSE 2.3.1, official
RaceMenu, OBody and the pinned HIMBO/3BA profile. Nine native suites passed.

## Transformed actors

Run `20261101-142745-a05f1e` (game06) completed six human-to-werewolf
transformations and six returns. The first transformation previously crashing
in the tint adapter now completed with advancing frames. Each wolf checkpoint,
including model refresh and save/load, matched all 183 CLAW target values
bit-for-bit with the shared native evaluator. The checks preserved 339 human
source values/key sets and 36 available human face/stature inputs at each phase.
Returned human models had all 183 own morph keys structurally absent while their
original sources remained present.

All six own private skin/fur material-health statuses remained applied through
refresh and load. This is a live diagnostic from CLAW, not an independent shader
RGB, texture-path or image-quality measurement. The test did not exercise a
deliberate competing material writer or every donor material variant.

## Actors first encountered as werewolves

Run `20261101-154509-5bf234` (game08) created five beasts directly, without tester
race, preset or human-morph writes, alongside one human readiness control. Actual
OBody generation events and assigned human preset values were observed for each
beast. Only the readiness control was transformed. All six references survived
native save/load, including three male and two female beasts sharing repeated
bases. At each relevant checkpoint, 182 CLAW targets matched the evaluator
bit-for-bit and 348 source values/key sets plus 36 typed availability/value checks
were preserved.

The repeated male bases deliberately received the same Male Heavy preset and the
female bases the same Female Heavy preset. This verifies reference independence
and persistence, not five distinct assigned shapes. The source witnesses do not
isolate whether CLAW's optional source-bootstrap branch itself executed.

Human head, height and colour history stayed explicitly unavailable for all five
beasts. Neutral missing-input evaluation is not a measured human trait. The
transformed control retained its actual human inputs and private tint status.

The preceding game07 ended normally but created no beast: an obsolete fixture
light-plugin index was rejected by the allowlist. Its born coverage remains
`not_run`; the fresh game08 corrected only the six fixture ID bindings.

## Termination and practical limits

Both accepted runs exited through the normal game menu with process exit code
zero. The native profile, optional file custody and original host were restored,
the pipeline was clear, and all nine staged product files still matched their
installed hashes. Eight physical starts occurred in this development session,
including the earlier failed candidates; successful runs do not erase failures.

These checks establish the recorded SE mechanism lifecycle. They do not establish
new AE/VR execution, CBBE or Vanilla installed-game acceptance, physical motion,
contact, individual texture-pattern selection, artistic quality, independent
rendered tint/alpha correctness or arbitrary dynamic load-order compatibility.

Raw reports are retained outside Git under
`Builds/claw-mechanics-20261101/game-06/result-evidence/result-summary.json`
(SHA-256 `02180c6cb9aa320dea18c88f649961022b4c1aee831903e9b2e68d0d0b9b97e3`)
and the corresponding `game-08` directory. Generated logs, saves and binaries are
excluded from this source repository.
