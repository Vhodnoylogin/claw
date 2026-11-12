# CLAW optional adult anatomy component

Develop the optional adult werewolf anatomy supplement, including penile
anatomy, in this directory of the CLAW repository. Keep its component-specific
code, authored resources and installation choices together. Corresponding tests
and fixtures belong under `src/test/components/adult-anatomy/`; generated files
belong in ignored `target/` or an external build directory.

Implementation follows the VR body and contact-collider releases. The component
is planned, with no implementation or release qualification implied by this
directory. It remains optional and outside the base runtime package until an
explicit component packaging choice is implemented and tested.

Reuse the shared numerical core and suitable core adapters. Keep component
resources and activation isolated, in the same repository and development
branch; do not create a separate product repository.
