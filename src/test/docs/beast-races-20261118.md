# Khajiit and Argonian source regression — 18 November 2026

This is an offline policy and static-record study. No game was launched and no
Khajiit/Argonian transformation, rendered face/coat/tail, engine FormID remapping,
installed resource winner or SE/AE/VR gameplay acceptance is established here.
The tests add no race-specific face gains, colour policy or direct tail inputs.

## Static master-record evidence

The installed SE `Data/Skyrim.esm` was read without modification using
[`record_reader.py`](../../main/python/vr/record_reader.py), with its process-local
index also including KYWD and CLFM records. File size: 249752131 bytes. SHA-256:
`e198c3b85e5e48e0c92a6580d8f66e644256b68d812ee32b61735cf9b753df73`.
These are master records, not the winning records of a declared MO2 load order.

| Race FormID | Editor ID | Record byte offset |
| --- | --- | ---: |
| 013745 | KhajiitRace | 1529152 |
| 088845 | KhajiitRaceVampire | 1036998 |
| 013740 | ArgonianRace | 1709451 |
| 08883A | ArgonianRaceVampire | 1211192 |

All four carry 013794 `ActorTypeNPC` and 0D61D1 `IsBeastRace`. The existing
[`humanSourceEligible`](../../main/cpp/include/claw/SourceBootstrapPolicy.h)
checks the first keyword and excludes only the resolved WerewolfBeastRace
0CDD84. It therefore accepts these source forms. `IsBeastRace` is not the
werewolf race identity.

The normal race records reference ARMO 069CE3 `SkinNakedBeast`. Its relevant
torso ARMA records 04E76E `NakedTorsoArgonian` and 081BA5 `NakedTorsoKhajiit`
use the ordinary `MaleBody_1.NIF` and `FemaleBody_1.nif` paths. Their separate
tail ARMA records 069CE2 and 0B79B9 use the male/female Argonian and Khajiit tail
NIFs. Shared body paths support using the selected installed body family's
coefficients; they do not establish rendered geometry or direct tail capture.

The following five raw NAM9 values are in CLAW's capture order: slots
0, 3, 4, 14, 16 (nose length, jaw width/forward, chin width/forward).

| NPC FormID / editor ID | Five captured values |
| --- | --- |
| 10D3CE / KhajiitMalePreset09 | 0, 0, 0, -0.6, 0 |
| 10D3C4 / ArgonianMalePreset09 | 0.4, 0.6, 0, 0, 0.8 |

Actual values are binary32. The tests author these literals as regression
inputs; female and vampire cases deliberately reuse them to test policy and
are not extracted female/vampire appearance fixtures.

KhajiitMalePreset10 (10D3CF) and KhajiitMalePreset08 (10D3CD) both have zeros in
all five captured slots, but different categorical NAMA parts. Those parts,
other face channels, HeadParts, sculpt and race-specific baseline geometry are
not represented by the five scalars. No categorical index should be inferred
to be a measured continuous shape.

Colour channels also have distinct meanings: ArgonianMalePreset10 (10D3C5)
references HCLF 0829D0, the CLFM `FeatherColorRed02`. Existing
[`Appearance.h`](../../main/cpp/include/claw/Appearance.h) captures HCLF as hair,
while [`CoatMatrix.h`](../../main/cpp/include/claw/CoatMatrix.h) supplies hair RGB
and seed to coat selection. Neither pelt/scale colour semantics nor a revised
colour policy is qualified by these tests. Existing wolf tail rules are
stature/body analogies, not measurements of the source race's tail; see
[`human-head-traits.md`](../../main/docs/human-head-traits.md).

## Regression coverage

[`SourceBootstrapTests.cpp`](../cpp/SourceBootstrapTests.cpp) names all four
races explicitly and checks eligibility, missing keyword/race-lookup rejection,
human-history/bootstrap revocation and retention after wolf/creature observations.

[`HumanTraitsTests.cpp`](../cpp/HumanTraitsTests.cpp) checks all four source
races for both sexes: supported signed/zero FaceGen values, stature, no invented
born-wolf source, retained source during wolf/creature/unresolved forms, opaque
FormID and availability serialization, sex isolation and atomic race/face
recapture through unavailable channels back to supported zeros. Engine
`ResolveFormID` belongs to the game adapter and is not simulated by these tests.
