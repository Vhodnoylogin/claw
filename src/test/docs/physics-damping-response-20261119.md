# Exploratory damping response — 19 November

Actual TEST SE run `20261119-004012-848f3a` **failed** its frozen response
criteria. It is not accepted Morphbench-to-game damping correspondence.

The unchanged Morphbench numeric editor and Python exporter produced identical
XML bytes for one left PreBreast→Breast P1 joint `linearDamping.x` change,
`.4` to `0`. The right joint, rigid-body damping, masses, stiffness, limits,
frames, NIF and TRI remained unchanged. Four acknowledged sequential NiOverride
calls applied independently observed bilateral anchor steps; this was not an
atomic input. Actual displacements were `0.10009765625` on each side. The native
900-pair window retained 790 pairs after the second known update.

The conservative maximum-projection enclosures were:

| Side | Lower | Upper | Bounds divided by actual step |
|---|---:|---:|---|
| Left, edited | 0.1369504954 | 0.1672458290 | 1.36817…1.67083 |
| Right, unchanged | 0.1309269081 | 0.1582975619 | 1.30799…1.58143 |

Even the right **lower** exceeds the frozen upper gate, `0.4 × step`.
Independent WORLD readback during the held-input checkpoint also observes the
large right response. Interval slack alone cannot explain the failure. These
enclosures are not exact peak values, co-temporal poses, recovered trajectories
or integrated simulation time. The original failed result remains immutable.

The isolated one-dimensional oscillator screening was insufficient for the
actual off-centre, six-axis rigid-body system and finite anchor displacement.
The selected XML has one breast rigid body per side, not a P1/P2/P3 chain.
Do not infer a runtime damping coefficient from that screening, broaden the
failed gates retrospectively, or launch blind stronger-damper retries.

The callback saved its final witness only after scoring, so a thrown assertion
omitted it from the compact case state. The exact completed packet was recovered
from the retained raw transport log. Future packets must persist observations
before evaluating assertions; absent compact data must never be invented.

Root independently verified normal exit code 0, exact owned fixture disposal,
128 restored snapshot preimages, 268 cold profile/payload pins and 266 actual
staged VFS winners. This restoration is separate from subject acceptance.

`python/integration/fsmp_damping_response_readback.py` retains the pure,
transport-free exploratory scorer. Its asset-free symbolic tests discriminate
rotated axes, pivot lever arms, non-co-temporal extrema, float32 input values,
unchanged controls and invalid observation contexts. Their synthetic positives
establish scorer behaviour only. No shipping DLL or physics setting changed.

Raw observations, original failed reports and root restoration receipts remain
in the external `claw-physics-next-response-20261119/proposal01` build directory.
The next diagnostic must explain the observed response and preserve all failed
evidence before requesting another finite game case.

The optional `test_fsmp_damping_response_actual.py` replays the hash-bound,
asset-free failed capture. Select its external JSON explicitly:

```powershell
$env:CLAW_FSMP_DAMPING_RESPONSE_EVIDENCE = '<absolute path to reviewed failed replay JSON>'
$env:CLAW_FSMP_DAMPING_RESPONSE_REQUIRED = '1'
python -B -m unittest discover -s src/test/python/integration -p 'test_fsmp_damping_response_actual.py' -v
```

Success means the original right-control refusal was reproduced unchanged.
It grants no physics acceptance. Unset evidence visibly skips; required,
explicitly missing or altered evidence fails. Raw opening/held/final observations,
rest frames, input hashes and final-packet extraction line/offset stay in the
external bundle; game assets and machine-specific source paths are excluded.

## Later single-left input diagnostic

TEST SE run `20261119-160523-4877f8` retained all 900 provider pairs,
verified the original configured joint parameters and returned normally.
The final quiet sample and first post-update sample were pairs 93 and 126.
The 33-pair gap improved on the earlier 39 but still exceeded the unchanged
30-pair limit. The runtime measurement remained inconclusive. Independent
arithmetic on the retained poses shows the relocated actor brought all
off-axis float32 bounds inside ±0.0005. This did not rescore the rejected input.
Raw timing, exact transforms and restoration evidence remain in
`Builds/claw-damping-resume-20261119/`.

`src/test/papyrus/CLAWTestFsmpPulse.psc` is a separate, nonshipping test
actuator for a future prospective diagnostic. It makes one ordered Papyrus
call for the original single-left .01 input, stored-value verification, and
scoped Update. The script admits only a loaded disposable female fixture in
QASmoke and refuses a pre-existing position at the reserved test key. It checks
the actor again before the getter and before Update. It does not remove keys
or use a right-hand actuator.

The host must validate the exact owned actor and scene root, inspect the
reserved `CLAW.Test.FSMP.Damping.Step` key, persist a single intent before dispatch, and verify independent
post-call world and solver readbacks. A typed 0 means no Add, 1 means Add
returned but Update was withheld, and 2 means Update returned. A returned 2
does not prove physical movement or an atomic input. A partial or unknown
result must quarantine the owned fixture. Never mark it applied or issue a
compensating Update. Known-success cleanup removes only the reserved test key.
No production DLL, runtime assets, or test witness API depend on the script.
The local build passed the Papyrus compiler against the installed SE imports
and the four declared SKEE signatures. TEST SE run `20261119-162944-d16c69`
returned typed 2. Its quiet pairs were 60, 79 and 94, with the first post-call
native read at pair 144. The 50-pair gap (.8313188 seconds) exceeded the same
30-pair limit. Host observation saw .66246 seconds before the typed return and
.18593 seconds from that return to the ready native read. These host intervals
do not measure time spent inside individual Papyrus operations. The compound
call did not reduce the observed gap. The result remains inconclusive.
The reserved key was removed during known cleanup, all 31 outputs stayed exact,
and the same 900-pair window, normal game exit and custody were verified.
The raw timing and restoration receipts are under
`Builds/claw-damping-resume-20261119/a1-compound-01/` and alongside it.

A separate [paired pose trace](../cpp/fsmp_step_witness/README.md) can preserve
whole pre/post poses across polling gaps. A prospective experiment still needs
an independently recorded acknowledgement boundary, an exact owned actor and
catalog, and the original physical input and timing gates. Neither retained
case can be retroactively qualified with this instrumentation.

## Actual paired trace and input transition

TEST SE run `20261119-171846-a91eaf` retained 53 trace pages spanning
836 paired steps (65 through 900), all 31 output checks and the unchanged
configured joint values. The last quiet pair was 102. The raw post-Update
acknowledgement marker followed its post event by .4500752 seconds.

The first whole pair after the marker was 130. Its left parent starts at the
unchanged position and ends at projected displacement .010009765625. Pair
131 has that displacement throughout. The right parent remains unchanged in
these pairs. These are observations of a transition followed by a held pair,
within the original 30-pair range. The separately polled ready readout arrived
at pair 137, a gap of 35.

The frozen paired timing check required both poses at pair 130 to be held and
returned `pose_refused`. The subsequent poses explain that refusal without
qualifying this run or accepting damping. A separate prospective check may
admit an explicitly recognized neutral-to-held transition followed by the next
complete held pair. The same clock, gap, unchanged-axis and independent world
pose requirements still apply.

The retained game exited normally and 128 snapshots, 268 cold pins, 261 cold
VFS winners and all 266 staged winners were verified with the original profile
restored. Evidence is under `Builds/claw-fsmp-paired-trace-20261119/`, including
`se-direct-trace-01-phase-analysis.json` and `se-direct-trace-01-restoration.json`.

## Prospectively qualified A1 baseline

Run `20261119-175222-fe1399` used the separately pinned transition-aware
protocol and the original configuration with both joints at linear-X damping
.4. The last quiet pair was 100. The left displacement arrived during pair
122 and held throughout pair 123, a 23-pair gap. Genuine normal-clock
ReadStates at pairs 100 and 128 bracketed both callbacks of the held pair.
The independent WORLD readback and all original pose checks passed.

The measured bins use real ReadState pairs [169,188,207], [227,246,264] and
[282,301,319]. The maximum scored gap including bin boundaries is 20.
The equal-bin RMS is .000454076696 and the engineering uncertainty bound
is .000488287031, below the unchanged .0005 cap. The engineering interval
reaches zero. The 837-row trace verifies the held-pair geometry and clock
anchor. Its rows do not enter the measured bins.

The timing-only runtime retained its original classification. A separate
prospectively pinned evaluator validated the raw captures after normal exit
and restoration and qualified the sampled A1 baseline. The A/B/A comparison
and damping effect remain unqualified. Evidence:
`Builds/claw-fsmp-paired-trace-20261119/se-a1-measurement-01-evaluation.json`,
SHA256 `5d08fa115a3cb34d906c6ae7956fdebef3187b114a051c37d9b18589a8f4e96c`.

## Single-setting B trial: rotation bound refused

TEST SE run `20261119-181503-de24fa` changed only the left joint's linear-X
damping from .4 to 0. The controller retained the full 900-pair window,
79 ready ReadStates and all 31 post-response values. The older polled input
gap was 34 pairs from quiet 103 to readout 137. The prospective independent
trace analysis identified the transition at 132 and the complete held pair
at 133, at the unchanged limit of 30 pairs.

The frozen offline evaluator then refused the trial at its .004 whole-window
relative-rotation enclosure. This leaves the sampled B measurement, the
A/B/A contrast and damping effect unqualified. A2 remains conditional on
a qualified B. The refusal itself does not identify whether true rotation
or uncertainty in its representation exceeded the range.

The retained game exited normally. All 128 snapshots, 268 cold pins, 261 cold
VFS winners and 266 staged winners were independently verified. The temporary
profile was archived and removed. Evidence in
`Builds/claw-fsmp-paired-trace-20261119/`:
`se-b-measurement-01-restoration.json` (SHA256
`028d4c5bb7f9446983cc20aec595caef2bbcfcb19ff5414e322f99c6496a52c3`)
and `se-b-measurement-01-evaluation.json` (SHA256
`8a5bdc703fcfec7cd6db3e18871c24da4dcc475381a6b4907a247301675a7bd5`).

### Whole-window rotation diagnosis

The trial's original enclosure for the left driver was .004087797480 radians.
The maximum actual pose in the paired trace was .003501208875 radians, but
the trace starts at pair 66. The parent basis was constant in the complete
900-pair extrema. Pair-by-pair angles alone cannot cover the omitted prefix.

The test-only fixed-parent bound operates on all 900 retained post-step
extrema. It bounds the rotation in the world basis before converting to an
angle and includes the measured orthogonality defect of the parent and
rest matrices. Its outward bounds are .003501306547 for the left driver
and .000010442852 for the right. The exact test against .004 uses a lower
bound on the sine threshold. Reversed or nonfinite extrema and a varying
parent are refused by this method. The diagnostic improves the enclosure
without changing the angular limit. It neither reclassifies the retained B
failure nor scores any B, A2 or physics contrast. A future measurement
must name and pin the method before running with the same physical limits.

The reproducible read-only replay is
`Builds/claw-fsmp-paired-trace-20261119/se-b-fixed-parent-rotation-diagnostic.json`,
SHA256 `ec858de973e0c2c98168b89a642e82dead28ccc745ade8c9f8c539a3858404e4`.


## Checkpoint for a prospective repeat

The revised 0.004-radian screen prefers the original bound and accepts the
exact world-space Frobenius bound only for an exactly fixed parent. Six local
controls cover equality of the earlier A1 result, failures when the parent
changes or the exact limit is exceeded, and preservation of the position
limits. The original B result remains refused. Replaying its retained data
with the new screen produced a diagnostic RMS of 0.004098943502223942 and
representation bound of 0.0004882902943502341, with all remaining original
gates holding. This retrospective calculation is diagnostic only. A new B
sample must qualify prospectively under the pinned proof, then be
independently restored before considering A2.

Local proof closure SHA-256 is
0a9bf6169019c5b1def3c1ff47074857739098185cc8509785dac072755c9f1a.
The original B evidence and classification remain unchanged.
