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

Reuse the shared numerical core and suitable core adapters. Keep component
resources and activation isolated, in the same repository and development
branch; do not create a separate product repository.
