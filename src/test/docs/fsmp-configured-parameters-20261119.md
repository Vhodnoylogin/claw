# Configured FSMP joint parameters — 19 November

TEST SE run `20261119-095533-974424` confirmed that the installed XML's configured
values reached the two intended breast Spring2 joints. This establishes parameter
binding, not accepted damping response. The original response check still failed
with `Unchanged right certified peak control exceeded`.

The read-only schema4 witness `444e19d4` observed15 rigid bodies and11 type12
edges. Two independent paused observations associated the target parent/driver
roles with callback-local tokens; the checker then required one enabled directed
edge per pair. All eight six-axis arrays matched the expectations derived before
the run from the XML and PDB-matched provider sources. The left linear-X damping
was0, with .4 on the right and every other damping axis. Both joints retained
linear limits±.15, angular limits±.01, stiffness1/.5, enabled springs, limit flags
and configured stopERP.2. Decimal expectations were compared as float32.

The900-pair raw capture, full31-morph post-audit and coefficient result were saved
before applying the unchanged response gate. Independent replay reconstructed
the role association, matched the configured values and reproduced that failure.
All31 outputs stayed exact. The completed raw return took16.281seconds within
the original35-second sampling cap; original whole-work/cleanup limits remained.
The retained game handle exited0; all128 snapshots,268 cold pins and266 staged
VFS entries matched, and the owned fixture/profile/anchor/camera cleanup passed.

This is the retained SE1.7.104/FSMP `5290e2a8` case with unchanged XML `28591892`,
CLAW DLL `a1012340` and matching original NIF/TRI. The independent external receipt
is `proposal03-result-review-01/ROOT-INDEPENDENT-RESULT.json`, SHA256
`f038a19edef9c08f8ec693d6103f8bfedff7bffa0ce62fe15aa82ef2bf88bcd6`.
Partial onsets from different steps must not be combined into a new trajectory.
Configured fields do not measure effective solver caps, impulses, integrated
time, waveform, rendered deformation, contacts or VR behavior. The earlier
[failed response](physics-damping-response-20261119.md) remains failed.
