# Separate flat and VR contact profiles

This source candidate authors 52 capsule slots for the flat game and 128 for VR,
including ears and tail in both profiles. Both use the existing single owner
ledger and complete current body morph vector. The generated paired header
selects the edition inside one universal game DLL; it does not append both
profiles or require separate SE/AE/VR DLLs.

`python/build_profiles.py` consumes the explicit final-runtime input receipt and
pinned skeleton, reuses the existing fitter and emits external model/header/host
source candidates. Compile each edition's matching host data with the existing
host builder. No host is activated and no generated file belongs in source Git.

The enclosing profiles preserve sampled support coverage but are too loose to
claim accurate VR touch boundaries. One separate three-pass contact experiment
reuses the VR allocation. Its measured skin escape failed acceptance; it is
experimental and is never selected by the default builder. Improving a distance
metric alone does not establish valid contact coverage.

Tests are under `src/test/components/contact-profiles/`. Native numerical parity
and successful compilation are separate from game acceptance. HIGGS, PLANCK,
Havok hand contact, posed geometry and actual provider consumption still require
their own integration and game evidence. These profiles supply none of those
features by themselves.
