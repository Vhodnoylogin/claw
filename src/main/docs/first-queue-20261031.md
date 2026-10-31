# First queue: matrix implementation and acceptance, 31 October 2026

This is development work, not another published release or new game acceptance.
The implementation is pinned at `ed0f466519a6d16c284af1a80f0adb9406523b30`.

## Delivered implementation

- Generic sparse source/target names, inclusive float32 coefficient cutoff
  `abs(gain) <= 1e-6`, default linear and explicit nonlinear/constant cells.
- One shared C++ evaluator and source-domain validator compiled into the universal
  CommonLib DLL and the independent Morphbench plugin's WebAssembly.
- Explicit `$actor.weight` in all five canonical matrices: HIMBO male, CBBE
  female, 3BA female and separate Vanilla male/female matrices. Weight is normalized
  once from NPC 0..100, not multiplied into effective SKEE coefficients again.
- Independent male/female FOMOD choices. Each of six combinations contains exactly
  two matrices, with optional OBody producing twelve installer selections.
- Co-save semantic version 6 with unchanged v5 layout. Ordinary older assignments
  retain their rules; ambiguous pre-v6 reserved names require explicit rebind.
- The plugin provides a separate actor-weight control, editable matrix,
  read-only derived outputs, linked orientation and scoped current/base vertices.
  Reserved scalar names never bind to or write human TRI controls. The production
  builder validates raw rows with shared WASM before pruning inactive edges.

The runtime candidate is version `0.7.1.0`, using the accepted v1 body resources.
Its archive SHA256 is
`b54fb8dedbdfd235dd71d72ccc867a76a6f598e83f25f2ef7c7dda1ec64ac265`.
It contains one DLL, runtime/install data and required notices; no developer source,
nested archives, test actors, body-v2 changes, physics or VR experiments.

The independent plugin candidate is `0.4.0-dev.3`, archive SHA256
`f2b63488927bbd929420b1b8ddd7fe389b80af9ecc035d515f75b9e84079b167`.
Its pinned shared dependency is the commit above, not another formula implementation.

## Evidence and remaining gates

A narrow source follow-up now guards the sex stored with a linked assignment.
Changing an actor's sex does not recapture the other body's sources, change its
saved/custom matrix or report that matrix applied. The runtime clears its own
output key and reports a binding error while retaining the original assignment
and bound sex. Restoring the original sex resumes that policy; an explicit
`ConfigureMorphFamily` or `ConfigureMorphLink` instead captures and binds the new
readable sex. The serialized layout/version stays unchanged. This follow-up is
not included in the archive hashes above and needs its own build/runtime check.

Six native CTest suites, 32 focused matrix/calibration/package tests, all twelve
serialized installer selections and 131 plugin tests passed. The latter includes
22 tests using the released Morphbench 0.8.5 SDK and scripts extracted from the
actual ZIP. Native/WASM parity covers 208 ordinary, ten sparse and 43 weight cases.
All five real matrices were additionally evaluated at weights 0, 0.25, 0.5, 0.75
and 1 by the native CLI and reject missing explicit weight.

Actual Morphbench browser observations applied the same separate scalar to male
HIMBO and female 3BA pairs; exported coefficients match the native CLI exactly.
The follow-up also opened genuine Vanilla male and female NIFs from the game's
BSA, with no TRI files, at matching weight-0/1 endpoints. All four exported
vectors match the native CLI bit-for-bit. The female full geometry export has
2,029 human and 99,023 wolf vertices: human morph names/values are empty, all
human deltas are zero and wolf deltas are nonzero. This is actual browser
rendering/readback, not a game observation. Both panels use fixed selected NIFs;
scalar edits do not interpolate human neutral geometry.

The native follow-up at `57bc951b775d33bea67b93270198cc39630acdf2` also exposes
the canonical active graph through `matrix-info` and accepts raw NPC weight
through the same native normalization used by the game. The CLAW-owned capture
analyzer requires the collector's independent actor/session/world weight witness,
never a fake SKEE field or a guessed value. It uses the native graph rather than
duplicating the cutoff or conversion arithmetic in Python. Thirty-seven actual
CLI integration tests include missing/malformed identity and scalar observations.
The sex-binding DLL follow-up passed all six native suites. It was subsequently
installed for the manual scene below, without repackaging or publication. The
earlier archive above is not this follow-up and must not be presented as its
verified runtime package.

The plugin's `0.4.0-dev.4` dependency is pinned to that same committed native
revision. The shared kernel and XML bytes are unchanged, and the recompiled WASM
is byte-identical to dev.3. Focused checks using actual Morphbench 0.8.6 SDK
assets and native/WASM weight vectors pass. Nexus page197517 was published and
is currently hidden by its owner; the owner reports the required Launcher is in
quarantine. Local verification does not make that distribution usable or publish
a new plugin version.

A separate existing-executor admission attempt started Skyrim SE and reached
QASmoke, but stopped before actor creation: the authored scenario supplied 60s
where the binding contract permits at most 30s. Four checks passed, one failed
and twelve did not run. The old installed CLAW was used, so this is not candidate
acceptance. Environment restoration was verified. Automatic menu exit was also
unconfirmed because the installed provider rejected `select-quit`; the final
process exit code was zero with an unknown termination cause. The failed
qualification reservation was subsequently settled under the owner's new direct
manual launch instruction and independent restoration/idle review. The failed
qualification remains historical evidence. No new tooling source was changed.

The current manual scene then loaded DLL SHA256
`d142ce92fc885c0df0dba5e04e792a86c552ea22b87413620d859a925f3a3ed0`
and selected HIMBO/3BA matrices. Six fresh same-base human pairs had equal complete
keyed source vectors and weights before one member of each pair became a wolf.
All six transformations completed. Thirty full captures, including 855 requested
target values, matched the current native CLI with maximum absolute error
`4.935302722053336e-10`; 60 additional passive samples also passed. Twelve before/
after comparisons preserved human sources, raw weight and observed foreign keys.
Two final position samples had zero drift and maximum placement error0.00151game
units. Captured global AI/Collision Off preceded all creation; NeverNude and the
test lighting were active. This does not attest the entire provider namespace.

The owner confirmed the new mechanism works and requested that the next game
run address queue two. They exited through the game menu. The held executor
records an expected manual game-identity end as a failed technical session;
that label does not describe a failed morph assertion or an observed crash.
Native cleanup, copied-profile archiving/removal and all optional custody/host
restoration were independently verified. Vanilla, weight endpoints, save/load
and sex-change cases were not exercised by this scene.

At identical observed human inputs, comparing the old and current matrices
changes only torso lean/girth in these six cases; Runa at weight50 is identical.
The current NPC weight100 of the slim fixtures partly offsets their lean input.
No new body geometry or large visible improvement was promised by this slice.
The owner flagged female breast transfer quality for the third queue.

Before release, test the exact candidate: generic/removed-target cleanup and
foreign-key preservation; both sexes at weights 0/50/100; mixed and Vanilla-only
inputs; human-to-beast-to-human preservation; born beasts; weight refresh;
save/load; ordinary older saves and explicit adoption/rebind. Use a qualified
launch/control/normal-menu-exit path. Do not substitute old game evidence or
offline parity for those checks. Geometry calibration, colours, physics and VR
remain in their owner-selected later queues.
