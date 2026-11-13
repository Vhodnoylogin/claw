# Human-origin FSMP lifecycle and cached WORLD test source

This nonshipping source preserves the qualified13 November case without copying
its machine-specific launcher, credentials, runtime binaries or result data into
Git. It does not extend the general Skyrim executor or add an engine actuator.

`python/integration/fsmp_human_lifecycle.py` contains the finite case.
`python/integration/fsmp_cached_world.py` contains only its shared receipt,
camera and cached-WORLD comparison guards. The existing `fsmp_probe.py` is reused
unchanged. Nine files in `cpp/fsmp_step_witness/` are byte-identical to the
qualified witness v2 source: native C++/PSC, standalone pure CMake test, parser,
parser tests and README. No DLL, PDB, PEX, ESP, NIF, dump or generated output is
part of this source port.

The caller supplies an already admitted, bounded disposable SE Session and the
validated external configuration explicitly:

```python
from fsmp_human_lifecycle import run

run(session, scenario, original_execute, configuration=configuration)
```

The caller's import path must include this integration directory and the exact
separately pinned `skyrim_autotest` executor. There is no fallback executor,
launcher, profile preparation, machine admission, input acquisition or live GO
in this module. Those remain external owner-controlled operations. The existing
Session owns menu exit, debugger/watchers and exact profile/file restoration.
Native witness building requires the external pinned CommonLib/FSMP/Bullet API
inputs and compiler described by its README and original build receipt; copying
source does not acquire them or qualify a different provider binary.

The case's original profile fixture IDs, compiled module hashes,300-second
subject/250-second work/50-second cleanup, source families and numerical gates
remain explicit. Initial disabled human metadata proves ancestry. Later typed
SetRace commits require actual currentRace and baseRace together; baseForm,
identity, sex and original weight remain strict. Known root transitions are
recorded, not relabelled as forced recreation. Owned save/load must advance both
observer and native witness epochs before the process's first window is armed.
The final pair of combined main-thread samples must uniquely match11 female and9
male positive-mass cached WORLD matrices at the original.002 translation and
1e-5 rotation limits. Fixed anchors are recorded separately.

## Retained game evidence versus this source port

Actual frozen operator03, run `20261113-132921-ea509a`, passed:

- initial human, first wolf, Refresh, human return, second wolf, Disable/Enable
  and owned save/load boundaries;
- six confirmed current/base-race transitions;
-20 mutually distinct dynamic roles, twice, with exactly zero matrix error;
-900 coherent pairs and48 objects;
- camera restoration, both fixtures disabled, own normal exit0, debugger stopped,
  and independent exact333-file/32-profile restoration.

Those observations qualify the retained operator and its exact inputs. Physics
was measured only at the final paused writeback boundary. They do not establish
normal render-phase visibility, contact/parameter acceptance, other runtimes or
physics at every preceding lifecycle boundary. Full release acceptance was
separate, with current CBPC lifecycle work still pending.

The repository port has **not** been game-launched. Its offline replay consumes
all435 retained case tool receipts in exact request order for both the frozen
original and port. It requires equal semantic state to each other and to the
retained actual result, excluding only local output paths and host-only final
timing. It leaves the original operator/results unchanged. OS/module lookups use
the retained actual path/hash proof; no current installed module, manager, API
or game is accessed. Startup world-ready has separate actual passed evidence;
no mutating scenario prefix is omitted.

Example with explicit external inputs and a fresh external output:

```text
python src/test/python/integration/replay_fsmp_human_lifecycle.py \
  --executor <pinned-executor> --original-case <frozen-run-03-packet> \
  --run <completed-run-20261113-132921-ea509a> --output <new-receipt.json>
```

Minimal pure checks:

```text
python -m unittest discover -s src/test/python/physics -p test_fsmp_cached_world.py
python -m unittest discover -s src/test/cpp/fsmp_step_witness -p test_validate_snapshot.py
```

The retained source-port receipt is external under
`Builds/claw-fsmp-qualified-source-port-20261113/`. It records source hashes,
unchanged nine-file closure,10 pure checks and the435-receipt equivalence result.
No new native build or live operation was performed for this port.
