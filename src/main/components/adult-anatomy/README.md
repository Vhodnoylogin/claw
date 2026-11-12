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
rendered visibility or physical movement. Composition with the ear/tail/P1
configuration remains a separate integration step before combined installation.

Reuse the shared numerical core and suitable core adapters. Keep component
resources and activation isolated, in the same repository and development
branch; do not create a separate product repository.
