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

## Separate private candidate archive

`python/package.py` packages the exact retained neutral resources with a small
FOMOD. It does not rebuild geometry, alter the core installer, install anything
or launch a game. The default **Keep current CLAW motion** installs only a
uniquely named user guide and asset-credit notice. It installs no NIF or XML,
so choosing anatomy physics off preserves an existing core male ear/tail FSMP
binding. Overwriting it with the unhooked static core would disable that motion.

The other two choices are explicit: anatomy motion only for core **None**, or
the combined ear/tail/anatomy system for core **FSMP**. The installer cannot
detect the prior core selection; the user must match it and reinstall the
overlay when that selection changes. Each option maps both endpoints to both
male `bodywerewolf` and `PlayerWerewolf` armor paths. The original PlayerOnly
materials remain exact, and the unchanged male TRI is inherited from required
core. No female resource, matrix, DLL, script, plugin, provider binary, texture,
skeleton or global configuration is bundled or overridden.

The static core already contains the neutral procedural shape. This archive
does not add adult-state morphs, a state controller or a completed independent
appearance. Its anatomy motion remains unqualified: the retained male12 game
case failed selective response. The authored XML has no collision shapes.
Private file/installer checks do not turn those gates into passes.

Build to a **new** external directory using the reviewed core and candidates:

```powershell
python src/main/components/adult-anatomy/python/package.py `
  --core-archive 'D:/Skyrim VR Modding/Builds/claw-010-physics-release-20261113/final-package-01/CLAW - Customizable Lycanthrope Appearance and Weight.zip' `
  --neutral 'D:/Skyrim VR Modding/Builds/claw-adult-anatomy-20261112/candidate-04/candidate' `
  --combined 'D:/Skyrim VR Modding/Builds/claw-fsmp-anatomy-compose-20261112/candidate-01/candidate' `
  --out 'D:/Skyrim VR Modding/Builds/claw-adult-anatomy-package-20261122-01'
```

Input pins are explicit in the packager. It reopens the written ZIP, checks its
eight-member inventory and verifies eighty compatible overlays across all forty
core family/OBody/motion plans. Default overlays retain every selected core
byte; enabled overlays change only the four male model destinations and add
one local XML. The required source/asset records and all consumed input hashes
stay in the external build report. The runtime archive contains only installer
data, exact NIF/XML payloads, a brief guide and asset credits. Existing Elegant
and XP32 conditions remain in force; private donor correspondence and developer
sources are not copied into the archive.

Run the focused pure tests with:

```text
python -m unittest discover -s src/test/components/adult-anatomy -p test_package.py -v
```

Actual archive checks require all three explicit environment inputs:
`CLAW_ANATOMY_CORE_ARCHIVE`, `CLAW_ANATOMY_NEUTRAL` and
`CLAW_ANATOMY_COMBINED`, using the paths above. Selecting none reports the
actual-input class as skipped; missing or changed selected inputs fail.
