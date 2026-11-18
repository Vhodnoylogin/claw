# Uniform actor scale and FSMP correspondence

Tags: CLAW, FSMP, scale, mass, joint limits, actual game acceptance

TEST SE run `20261118-211810-d86de9` qualifies one uniform scale change using
the ordinary a101 DLL, e5a female NIF endpoints, 34744 TRI and the accepted
[left linear stop+0.05](physics-lower-limit-20261118.md). The XML and its original
bilateral masses0.05 are unchanged. One fresh owned Khajiit-female fixture first
reaches a unit-scale wolf, then receives one typed `SetScale(1.1)` call.

A completed command is not the measurement. The retained unit observation stays
immutable. Only its known acknowledgement permits the declared scale/root setup
transition, with the same actor creation, process, base/race and world. Two fresh
stable observations establish a separate measurement lease. Actual GetScale,
reference scale, root WORLD scale and both PreBreast/P1 WORLD scales agree at
`1.100000023841858`; local rest scales remain1. Unknown completion cannot rebind
the lease or trigger a replay or guessed inverse.

The exact-PDB-matched FSMP source gives inverse mass `20/s^3` for these original
P1 masses. Native WORLD rotations/translations still associate directly with
NiWORLD: scale is stored separately. With frozen local rest rotationR0 and
translationt0, the joint calculation uses the scaled pivot:

`RJ = transpose(RA) * RB * transpose(R0)`

`qWorld = transpose(RA) * (pB-pA) - RJ * (s*t0)`

`qNominal = qWorld/s`.

The pure adapter is separate from the accepted unit-scale checker; it never
rewrites observed scale to1. Linear limits scale withs; angular limits remain
radians. The prospective tolerances are2e-5 for inverse mass and0.0015 for WORLD
joint position. The old0.005 tolerance would not discriminate0.050 from0.055.

After312 actual pre/post settling steps, one900-pair/15-object window yields:

| Final measurement | Left P1 | Right P1, unchanged stop |
| --- | ---: | ---: |
| Inverse mass, expected15.02629504 | 15.02629375 | 15.02629375 |
| Joint WORLD X, expected0.055/0 | 0.05525806 | -0.00053159 |
| Nominal joint X, expected0.05/0 | 0.05023460 | -0.00048326 |

Both paused observations and the completed window retain bilateral settling,
untouched bounds and fresh injective four-role associations. All31 SKEE values
and the selected family remain stable after setup. One known camera inverse
restores normal clock/camera state; the exact fixture is disabled/unloaded.
Normal exit0, full collection,128 restored snapshot preimages,268 original cold
subject/profile pins and266 native staged VFS winners pass. This is physical
Skyrim start20 on18November; the separate earlier SKEE-INI VFS refusal did not
dispatch SKSE and adds no game start.

Independent raw replay and restoration are in
`Builds/claw-fsmp-actor-scale-assessment-20261118/runtime-proposal-01/ROOT-ACCEPTANCE.json`,
reproduced by its `root-verify-result.py`. The explicit optional replay bundle
has SHA256 `81fd284e7e1fe54bf030c80831061f10f5852f63effaa8c15ea345c977818fb8`.
Raw captures remain outside Git and release files.

Scope: one finite uniform1.1-scale mass/linear-stop result. Nonuniform skeletons,
inertia getters, general damping/time response, rendered-card attachment,
contacts and VR remain unqualified. The shifted stop is temporary test staging,
not a default physics-preset change or a new public release.
