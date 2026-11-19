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

A later single-slot study shortened the capsule for part of `TailBone02`.
Its static and sampled union distances improved for both sexes. In the
withheld compound tail bend, however, the assigned skin exceeded the
capsule by .201 female and .193 male, up from .028 and .027 respectively.
A pose-envelope fit trained on rest and two separate transverse bends still
exceeded the capsule by .129 and .119 on that holdout. The source profile
therefore retains its original fit and slot allocation.

These comparisons reconstruct skin from the exact NIF binds, packed weights
and TRI deltas. Their poses are synthetic. A rigid capsule can cover a measured
pose envelope at the same slot count by occupying more space. A tighter
pose-dependent result needs evaluated bone transforms, the current TRI vector
and observations of contact in the same provider frame.

The enclosing fit reserves its two temporary projection arrays for the
known support size. A paired offline benchmark measured 6–12% less CPU
time for the complete fit on the tested machine. All 45,360 capsules
across 504 inputs stayed bit-for-bit identical. The benchmark covers the
worker calculation in the experimental host. Engine contact work and
frame time have yet to be measured.

Tests are under `src/test/components/contact-profiles/`. Native numerical parity
and successful compilation are separate from game acceptance. HIGGS, PLANCK,
Havok hand contact, posed geometry and actual provider consumption still require
their own integration and game evidence. These profiles supply none of those
features by themselves.
