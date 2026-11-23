# CLAW optional adult anatomy component

Develop the optional adult werewolf anatomy supplement, including penile
anatomy, in this directory of the CLAW repository. Keep its component-specific
code, authored resources and installation choices together. Corresponding tests
and fixtures belong under `src/test/components/adult-anatomy/`; generated files
belong in ignored `target/` or an external build directory.

The 12 November owner plan includes offline preparation after the VR body and
contact candidates, then SE attachment/motion tests and VR technical tests. A
previous requirement to wait for their separate releases is superseded. This
directory still implies no accepted implementation or release qualification.
The separate private candidate installer described below is optional and remains
outside the base runtime archive.

The current source candidate reuses CLAW's existing neutral procedural shape.
`python/build.py` adds bounded skin weights, the existing XP32 ancestry and an
original FSMP motion configuration to the pinned male runtime resources. It
preserves their geometry, materials and TRI fields, and refuses an existing FSMP
hook. Bone spheres enclose the serialized morph domain and declared nominal
joint limits; this is not a simulation or proof of engine culling behavior.

Keep the appearance usable with physics off by default in the eventual
installer. The pinned original resources already contain this neutral geometry
and TRI without an FSMP binding. Treat the motion rig and its XML as the
opt-in variant and verify both selections during packaging.

`src/test/components/adult-anatomy/test_neutral.py` checks the actual resources
through the native NIF reader and Morphbench facade. `visibility_probe.py` is a
separate Blender body-occlusion proxy. Neither establishes live attachment,
rendered visibility or physical movement.

`python/compose_motion.py` is a separate offline composition step for the frozen
neutral anatomy04 male resources. It retains the original nine-driver male
ear/tail XML and three-driver anatomy XML parameters in one namespaced system.
Dynamic ownership must be disjoint; duplicate drivers, incompatible anchors,
unresolved constraints, collision records and global settings are refused. Only
identical kinematic anchors can be deduplicated. The original female eleven-driver
ear/tail/P1 XML remains a separate unchanged source witness; no male P1 or female
anatomy support is inferred.

Each frozen male NIF already owns one neutral-anatomy root hook. Composition
appends the combined XML value string and redirects only that known hook's value
index. Root references, all other blocks, original strings/IDs, geometry, skin,
materials, bounds and BODYTRI remain exact. Unknown, multiple or shared hooks are
refused. The original `Tails` kinematic anchor comes from the explicitly pinned
existing XP32 skeleton; it is not grafted into the flat mesh bone graph.

For a rebuild from a later checkout, pass `--historical-source-root` with a
source tree containing the exact witnesses listed in the frozen anatomy04
receipt. The historical witnesses are hash-checked. The running checkout and
tool dependencies have separate pins in the composition report.

The output contains two male endpoints, their unchanged TRI and the combined XML.
The focused `test_compose_motion.py` suite checks invalid graphs/hooks, actual
native resources, all thirty morphs and the actual Morphbench Physics facade's
twelve configured records. Its rest-frame ranges are not physics simulation or
runtime acceptance. Live provider/config ownership and the selected VFS paths
still need a separate conflict audit before installation. No provider binary,
global configuration, installation action or game launch is included.

Reuse the shared numerical core and suitable core adapters. Keep component
resources and activation isolated, in the same repository and development
branch; do not create a separate product repository.

## Private core and add-on candidates

`python/package.py` creates two test archives. The companion core keeps the
original installer choices and hides the embedded neutral anatomy in both male
body sources. The optional add-on restores the exact visible neutral shape in
both weight endpoints and both male `bodywerewolf` / `PlayerWerewolf` routes.
The core's TRI, materials, female models, data and runtime stay byte-identical.

The add-on installer defaults to **Keep current male meshes**. This installs
only notes and credits, leaving current appearance and motion unchanged. To add
neutral anatomy, explicitly choose the motion setting from the companion core.
The next screen then defaults to anatomy motion **Off** and preserves that
selected core setting. Enabling anatomy motion selects either the separate
three-driver rig or the combined ear/tail/anatomy rig, as appropriate. Repeat
the add-on installation if the core setting changes. The original Elegant
materials and shared core TRI apply to all four explicit choices. Faster
HDT-SMP remains a separate dependency when its motion is selected.

This candidate exposes the original neutral procedural model. Adult-state
morphs, motion measurements and contacts remain separate tasks. The retained
male12 game case failed selective response. Its authored XML implements the
motion graph without collision shapes. Current verification covers the files
and serialized installer choices offline.

Build to a **new** external directory using the reviewed core and candidates:

```powershell
python src/main/components/adult-anatomy/python/package.py `
  --core-archive 'D:/Skyrim VR Modding/Builds/claw-010-physics-release-20261113/final-package-01/CLAW - Customizable Lycanthrope Appearance and Weight.zip' `
  --neutral 'D:/Skyrim VR Modding/Builds/claw-adult-anatomy-20261112/candidate-04/candidate' `
  --combined 'D:/Skyrim VR Modding/Builds/claw-fsmp-anatomy-compose-20261112/candidate-01/candidate' `
  --out 'D:/Skyrim VR Modding/Builds/claw-adult-anatomy-package-20261123-01'
```

For a current source-built core, pass its ZIP as `--core-archive` and its
`build-receipt.json` as `--core-receipt`. The packager rechecks the archive
inventory and resolves the FOMOD choices independently. The selected male
models, shared TRI and male FSMP XML still need the reviewed content pins.
The resulting companion retains the new core DLL and default appearance
without the visible optional anatomy. The two archives must be used as a pair.

The packager reopens both archives and checks 160 selections across the forty
core family/OBody/motion plans. Each plan covers the companion core alone,
the literal add-on defaults, the explicitly selected static anatomy, and the
explicitly selected anatomy motion. Default replay reads the recommended
options and step visibility from the serialized XML without supplying a core
mode; it must leave every core destination exact. Each explicit choice changes
only the four male model destinations and optionally adds one local XML. The
four variants retain the exact previous six-member NIF/XML inventory. The
external report records exact input and payload identities. The add-on archive
contains installer data, exact NIF/XML payloads, a brief guide and asset credits.
Existing Elegant and XP32 conditions apply.

### Offline FSMP collision candidate

`python/collision_candidate.py --help` lists the exact retained motion assets,
provider source and native reader needed to build a separate collision candidate.
The tool binds the existing anatomy mesh to one FSMP triangle surface per rig.
It preserves the motion graph, visible mesh, skin weights and TRI. The generated
files are for internal testing, separate from the installer.

Contact qualification requires a positive-radius skinned peer on a different
live skeleton with the reciprocal tags in the generated `peer-contract.json`.
The offline report verifies the source geometry and provider rules. A game run
with that peer is required to measure contact and confirm motion.

Run the focused pure tests with:

```text
python -m unittest discover -s src/test/components/adult-anatomy -p test_package.py -v
```

Actual archive checks require all three explicit environment inputs:
`CLAW_ANATOMY_CORE_ARCHIVE`, `CLAW_ANATOMY_NEUTRAL` and
`CLAW_ANATOMY_COMBINED`, using the paths above. Selecting none reports the
actual-input class as skipped; missing or changed selected inputs fail.
Set `CLAW_ANATOMY_CORE_RECEIPT` when selecting the current core build rather
than the reviewed original ZIP.
