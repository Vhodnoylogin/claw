# CBPC pulse probe: retained failure and provider qualification

The second CBPC pulse case used the unmodified official 1.7.3 master and DLL
`4996c85ee00e051a903c15746e8686a2357b70c9b27957f8ef3026dbc62d5387`.
It remains **failed**, with no eleven-driver motion acceptance. All 164 manager
preimages and the installed official DevBench DLL were restored. The owned game
exited normally with code zero after fixture disposal and real menu quit.

The separate DevBench development candidate fixed its pinned CommonLib
object-array TypeInfo decoder. Seven native descriptions, including the
previously crashing ObjectReference description, and three CBPC version getters
completed in game. This qualifies those calls in that modified candidate; it
does not establish stock DevBench or CBPC mechanics acceptance. The CBPC getters
returned stale version constants 1/6/2 despite the verified 1.7.3 DLL bytes.

## Motion findings

Exactly one of 288 read-only sample gaps exceeded the unchanged 0.200-second
maximum: 0.2009776 seconds in the stopped Tails window. The other 287 gaps and
all twelve window spans satisfied their bounds. Windows Python 3.12 uses coarse
GetTickCount64 for monotonic and QPC for perf_counter. Only the shared sample
scheduler now uses QPC. Guard deadlines and all scorer thresholds are unchanged;
the old report is not rescored or replaced.

Raw response also prevents a clock-only retry. Ears and TailBone01 showed
selective own-local variation while many sampled world transforms stayed fixed.
TailBone02–05 stayed fixed locally and globally; P1 showed only a small local
decay. None met the existing combined own-local and immediate-parent-relative
varying-response requirement. This is descriptive evidence, not a relaxed pass.

The exact DLL/PDB explain two relevant propagation mechanisms:

- The installed stock master lists TailBone01–05 in `NoJitterFixNodes`.
  `RefreshNode`, RVA 0x55b80, skips its UpdateWorldData call for listed names.
- Generic `Thing::update`, RVA 0x62cd0, stores the new local transform and
  compares its per-update change with the previous local transform. At
  0x65f7d–0x66029 it skips RefreshNode when squared translation length and every
  squared rotation-element delta are at most 2.50000028e-7 (a 0.0005 component
  scale). This optimization is present in the exact 1.7.3 image and differs from
  the retained older public source.

The fixture had AI disabled. It therefore does not yet establish whether normal
restrained-actor scene updates propagate these small local writes in ordinary
gameplay. A meaningful successor should allow ordinary scene updates while
preventing locomotion/combat, retain stock config, and keep animation/control
and inherited-only negatives. Do not force driver world matrices or tune gains
merely to satisfy this probe. Any animation contamination remains unconfirmed.

## Reusable source

`python/integration/cbpc_stock_role.py` retains the live guard used by the case:
all four special-controller targets are queried on the admitted loaded root;
an actual missing VaginaB1 or Clitoral1 establishes the exact controller's early
return. Root continuity is checked again before the callback's first control
and all later observations. Missing trees, stale samples, changed roots,
unavailable reasons and an all-present prerequisite set fail closed.

`resources/physics/cbpc-stock-role-xp32.json` records the inspected donor paths
without local machine paths. It does not replace verification of current VFS
resources or establish generic runtime ancestry. The guard's positive/negative
checks also run with Python optimization enabled; explicit checks survive -O.

Raw case evidence remains outside Git in
`Builds/claw-cbpc-pulse-live-20261111-02/`, including raw-response-review.json,
actual-cadence.json, exact stock graph admission, 33 void-control receipts,
all twelve pulses/300 samples, cleanup and restoration. Native symbol/disassembly
evidence is in `Builds/claw-cbpc-pelvis-proof-20261111/`. No dumps were uploaded.
