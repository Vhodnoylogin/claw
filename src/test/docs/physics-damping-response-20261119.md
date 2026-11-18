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
