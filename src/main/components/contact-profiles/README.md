# Separate flat and VR contact profiles

This source candidate authors 52 capsule slots for the flat game and 128 for VR,
including ears and tail in both profiles. Both use the existing single owner
ledger and complete current body morph vector. The generated paired header
selects the edition inside one universal game DLL; it does not append both
profiles or require separate SE/AE/VR DLLs.

Both recipes must keep both-sex contact on the two bones of each ear and on
TailBone01, TailBone02, TailBone03 and TailBone05. The builder checks those
attachments before fitting, even when reallocating their capsules would keep
the overall budget unchanged.

`python/build_profiles.py` consumes the explicit final-runtime input receipt and
pinned skeleton, reuses the existing fitter and emits external model/header/host
source candidates. Compile each edition's matching host data with the existing
host builder. No host is activated and no generated file belongs in source Git.

`python/posed_support.py` uses that fitted VR model and the same six pinned
runtime assets to emit `posed-vr-support.h` in a new external directory:

```text
python src/main/components/contact-profiles/python/posed_support.py --vr-model <vr/fitted-capsules.json> --runtime-inputs <runtime-inputs.json> --out <new-external-directory>
```

`CompiledVRPoseSupport` exposes both sexes with their required bones, the
existing morph order, and the original indices of the 42 head, ear and tail
slots. Head support includes the jaw and other actual skin influences, so
the capsules can follow deformation when the Head bone itself is stationary.
Use `--ear-tail-only` to reproduce the archived 32-slot tables.
The exporter checks the actual oriented triangles and requires the same
normalized weights and bind mappings across actor-weight endpoints. It emits
the vertex endpoint differences and sparse TRI fields in shape space, for
application before skinning. The earlier ear/tail native calculation used the
archived VR67 pose at both the observed ear-size value and its zero control.
All sixteen ear slots changed and the sixteen tail slots matched. The female
model was checked against the independent solver at rest with two effective
input vectors.

Pass `--paired-build <paired-profile-output>` to also emit the combined
`physics-fit-model.h` for `-PhysicsModelHeader`. The exporter verifies the
paired build receipt and enables the posed fit in that header. For new head
support it requires the current fitter's static backing for numeric tables.
Archival initializers can exceed the game thread's stack. For VR, the worker uses the captured
actor pose to fit those original slots on first attachment and when the
existing refresh detects a model, weight or morph update. The other slots
use the regular fitter. Scene reads use the third-person Body32 and the actual
skin palettes. The candidate checks the authored geometry extents, BODYTRI and
the provider's attachment lookup. A replaced graph or superseded observation
cannot publish the queued pose. The candidate still requires the exact
installed asset pins. A shape with the same extents is not a file hash.

After the provider host acknowledges a complete snapshot, a VR-only 250 ms
task samples one eligible actor in rotation. An independent rotation retries
one unacknowledged pose event per tick through the ordinary observation guards.
The two-second scan still handles morph updates and retries ordinary events.
Pose captures older than 500 ms are discarded for both full refits and pose
updates. The worker compares each updated capsule with the last accepted capsule
in the attachment bone's local coordinates. The initial movement threshold
is 0.05 game units. Exchanging the ends of a capsule leaves its identity
unchanged for the comparison.

A pose event carries the new snapshot token. The host gets changed slots
only against its own fully accepted previous token and uses the existing
ledger to replace those slots. An incomplete or mismatched ledger uses the
scoped full synchronization path. The native lane holds at most one
unacknowledged update per actor, so a busy host can receive the same event again.
Live coordinates, update timing and contacts need a qualified VR run.

For an isolated VR test, configure a fresh CMake tree with
`-DCLAW_TRACE_VR_POSE_ACK=ON` and the posed model header. Use the matching host
PEX. The default build leaves the trace disabled. At the first valid host
acknowledgment, Distribution writes one `CLAW posed VR ACK` JSON record. It
includes the exact matrices consumed by the fitter (row-major 3×4, relative
to the actor root), weight and effective morphs, the published snapshot and
predecessor, and capture, compute, publish and acknowledgment times. These
times use one monotonic microsecond clock within the process.

```text
python src/test/components/contact-profiles/verify_pose_ack.py <CLAWDistribution.log> --actor <FormID> --generation <generation> --profile <vr/fitted-capsules.json> --require-delta
```

Retain the log from the start of the actor registration so the verifier has
the initial full snapshot as a baseline. Pin the fitted profile to the build.
`changedSlots` records the native fit decision. `application` records whether
the host accepted a slot delta or synchronized the full set. `capsules` lists
the Float32 requests for that path. A full synchronization can replace more
slots than the native fit marked as changed. This receipt establishes what
the pinned host acknowledged. CBPC solver state and hand contact still
require independent observations.

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

The fitted male VR tail slot 106 passed the same controlled experiment with
one actual capsule. CBPC emitted 3, 0, 1 and 0 callbacks during the active
near, far, return and detached intervals. The unattached near control emitted
zero. The engine then faulted during process shutdown. The test verified the
scoped capsule on one born werewolf. Full profile activation and human-to-wolf
provider binding remain separate work.
