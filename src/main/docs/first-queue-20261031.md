# First-queue matrix candidate, 31 October 2026

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

Six native CTest suites, 32 focused matrix/calibration/package tests, all twelve
serialized installer selections and 131 plugin tests passed. The latter includes
22 tests using the released Morphbench 0.8.5 SDK and scripts extracted from the
actual ZIP. Native/WASM parity covers 208 ordinary, ten sparse and 43 weight cases.
All five real matrices were additionally evaluated at weights 0, 0.25, 0.5, 0.75
and 1 by the native CLI and reject missing explicit weight.

Actual Morphbench browser observations applied the same separate scalar to male
HIMBO and female 3BA pairs; exported coefficients match the native CLI exactly.
Both model panels use fixed selected NIFs. Scalar edits do not interpolate human
neutral geometry; Vanilla zero-TRI control-domain checks are SDK coverage, not
actual Vanilla body rendering or game acceptance.

A separate existing-executor admission attempt started Skyrim SE and reached
QASmoke, but stopped before actor creation: the authored scenario supplied 60s
where the binding contract permits at most 30s. Four checks passed, one failed
and twelve did not run. The old installed CLAW was used, so this is not candidate
acceptance. Environment restoration was verified. Automatic menu exit was also
unconfirmed because the installed provider rejected `select-quit`; the final
process exit code was zero with an unknown termination cause. The failed
qualification reservation remains held. No new tooling source was changed here.

Before release, test the exact candidate: generic/removed-target cleanup and
foreign-key preservation; both sexes at weights 0/50/100; mixed and Vanilla-only
inputs; human-to-beast-to-human preservation; born beasts; weight refresh;
save/load; ordinary older saves and explicit adoption/rebind. Use a qualified
launch/control/normal-menu-exit path. Do not substitute old game evidence or
offline parity for those checks. Geometry calibration, colours, physics and VR
remain in their owner-selected later queues.
