# Morphbench angular-limit correspondence in FSMP

Tags: CLAW, Morphbench, FSMP, radians, actual game acceptance

TEST SE run `20261118-201916-366d11` qualifies one angular stop with the same
ordinary a101 DLL, final e5a female NIF endpoints and matching 34744 TRI used by
the [linear case](physics-lower-limit-20261118.md). Actual Morphbench export
changes only left P1 `angularLowerLimit.x` from `-.01` to `0.005`. Original
linear bounds, both masses0.05, frames, damping and all other angular values
remain unchanged. There is no pulse or direct solver-state mutation.

The joint rotation is taken from
`inverse(PreBreast_world) * BreastP1_world * inverse(BreastP1_local_rest)`.
FSMP explicitly selects Bullet `RO_XYZ`; its limits use radians. For a unit
row-major joint basis R, the nonsingular extraction is:

`x = atan2(-R[7], R[8]), y = asin(R[6]), z = atan2(-R[3], R[0])`.

Positive Bullet X is therefore negative ordinary active Rx. This sign is not
guessed from a viewer convention. Official Bullet3.25 plus the pinned FSMP
overlay's exact CMake replacements reproduces the actual PDB-listed source
checksum `81678763cb0a24d53951b1f80c132bc14f4cac9cf8007413aff5831b4c949486`
under CRLF. The indexing/angle functions are unchanged by those replacements.
The external provenance record is `next-angular-review-01/bullet-derived-hash.json`
under the18November breast-attachment build directory.

The pre-frozen angular tolerance is0.0001 radians, derived from the previous
actual quiet rotations and conservative basis-association precision. Left X
must be0.005±0.0001; unchanged right X must remain0±0.0001. Both sides also retain
their other angular/linear bounds and initial-to-final settling guards. The
scorer refuses invalid bases and leaves the singular rotation regime unqualified.

The fresh owned female fixture passes model/family/module/unit-scale admission.
Four fresh injective body tokens associate both P1 bodies and kinematic parents;
the original masses give inverse masses20/20. After307 actual pre/post settling
steps, one native900-pair window with15 objects yields:

| Bullet joint X, radians | Initial pre-step | Final post-step |
| --- | ---: | ---: |
| Left, lower stop+0.005 | 0.0049673369 | 0.0049673369 |
| Right, unchanged rest | -0.0000101770 | -0.0000101770 |

Both advancing main-task observations match the same paused native pose. The
same900-pair window completes after its one known camera inverse. All31 measured
SKEE aggregates and selected family remain unchanged. The exact fixture is
disabled/unloaded; normal exit0, full collection,128 snapshot preimages and268
original subject/profile pins pass. All266 staged native VFS winners were checked.
Cumulative physical Skyrim starts are19 at this acceptance.

Independent raw replay and restoration are recorded at
`Builds/claw-breast-attachment-20261118/next-functional-physics-20261118/next-angular-review-01/runtime-proposal-01/ROOT-ACCEPTANCE.json`,
reproduced by `root-verify-result.py`. The exact optional replay bundle has
SHA256 `218264a5acacaa09c64f3dbbfd2c0ace5e2255e2614bc189005dd56e79a65dc6`.
The pure angular test scorer reuses the canonical joint pairing/frame helpers
and their sole witness validator; accepted older pair schemas stay unchanged.

Scope: one original-mass angular stop in the near-zero `RO_XYZ` regime. It is no
direct live angular-limit getter, general solver calibration, rendering/contact
test, singular-angle coverage or VR acceptance. The packet was temporary test
staging; its intentionally shifted rest stop is not a new default preset.
