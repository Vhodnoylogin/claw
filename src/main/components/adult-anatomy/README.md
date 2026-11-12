# CLAW optional adult anatomy component

Develop the optional adult werewolf anatomy supplement, including penile
anatomy, in this directory of the CLAW repository. Keep its component-specific
code, authored resources and installation choices together. Corresponding tests
and fixtures belong under `src/test/components/adult-anatomy/`; generated files
belong in ignored `target/` or an external build directory.

The 12 November owner plan includes offline preparation after the VR body and
contact candidates, then SE attachment/motion tests and VR technical tests. A
previous requirement to wait for their separate releases is superseded. This
directory still implies no accepted implementation or release qualification. It remains optional and outside the base runtime package until an
explicit component packaging choice is implemented and tested.

The current source candidate reuses CLAW's existing neutral procedural shape.
`python/build.py` adds bounded skin weights, the existing XP32 ancestry and an
original FSMP motion configuration to the pinned male runtime resources. It
preserves their geometry, materials and TRI fields, and refuses an existing FSMP
hook. Bone spheres enclose the serialized morph domain and declared nominal
joint limits; this is not a simulation or proof of engine culling behavior.

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
