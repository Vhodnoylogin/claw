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

The male VR replay now uses 15 observed bone transforms and the co-sampled
effective RaceMenu vector. It covers all 32 ear/tail slots. One tail-root
partition exceeded its rest-fit capsule by .518 owner-local units at both
sampled poses. Moving that capsule to the pelvis increased the gap. A
same-pose refit encloses the sampled support. The native feasibility replay
fits those 32 regions using the same C++ enclosing function, with deduplicated
skinned points and no engine dependencies. See the
[replay notes](../../../test/components/contact-profiles/posed-contact.md).

The enclosing fit reserves its two temporary projection arrays for the
known support size. A paired offline benchmark measured 6–12% less CPU
time for the complete fit on the tested machine. All 45,360 capsules
across 504 inputs stayed bit-for-bit identical. The benchmark covers the
worker calculation in the experimental host. Engine contact work and
frame time have yet to be measured.


A follow-up tried fixed-size field bookkeeping, one array of paired
projections and symmetric covariance accumulation. The first two together
changed the measured worker median by 0.4–1.3%. Symmetric covariance ran
2–10% slower on the same bank. Every variant agreed bitwise across all
504 inputs. The source retains the measured reservation and original
arithmetic.

A separate audit traced 31 morph channels and direct weight interpolation to
the support vertices of each slot. Across 256 single-channel contrasts in the
compiled rest-space fitter, every changed capsule belonged to the predicted
partition set. A size change to the ears affected 6 capsules in the flat
profile and 22 in VR for either sex. A tail-length change affected 6 in the
flat profile and 17 male or 18 female capsules in VR. This identifies which
slots a changed-capsule refresh could preserve. Such a refresh still requires
provider ownership, verified cleanup, and live timing and contact checks.

Tests are under `src/test/components/contact-profiles/`. The stock CBPC probe
registered 5, 0, 5 and 0 scoped callback events during nearby, far, nearby
and detached intervals on one male wolf's tail. The exact near geometry and
native event window were independently replayed. Game shutdown returned
0xC0000005 after the case, and the isolated installation was restored.
The release profile is still open for live provider consumption, rebinding
and contact tests on its actual fitted regions. HIGGS and PLANCK use separate
contact paths. See the [VR evidence](../../../test/docs/vr-readiness-20261119.md).
