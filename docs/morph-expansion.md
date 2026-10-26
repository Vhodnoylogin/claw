# Human-driven morph expansion

Design research, 26 October 2026. These are proposed geometry targets, not new
runtime morphs or release promises. The current 24 shared / 25 female names and
the frozen SE test inputs are unchanged.

## Rule

A linked werewolf is a deterministic conversion of the actor's **actual applied
human coefficients**. Presets supply those coefficients; neither a wolf preset
nor an independent random trait is needed. Different human body families require
explicit conversion tables: equal strings or equal slider percentages do not
establish equal physical dimensions. Missing body coefficients remain zero.

The existing link reads RaceMenu/SKEE body morphs. Human head/FaceGen sliders and
node transforms use different data paths; their presence in the RaceMenu UI does
not make them readable through `IBodyMorphInterface::GetBodyMorphs`.

## Candidates backed by current human body resources

All artistic meanings and gains below need measured shape calibration. A source
name's existence does not establish current actor value or UI registration.

| Priority | Proposed wolf target | Female 3BA 2.48 sources | Male HIMBO 5.8 sources | Purpose |
|---|---|---|---|---|
| First | `CLAWArmForearmGirth` | `ForearmSize` | `ArmsFore` | Separate forearm strength from the current whole-arm girth |
| First | `CLAWTorsoGluteSize` | `BigButt`, `Butt`, `ChubbyButt` | `ButtBooty`, `BubbleButt`, `LegsGlutes` | Local hip/glute volume without enlarging the entire thigh |
| First | `CLAWTorsoAbDefinition` | `MuscleAbs`, `MuscleMoreAbs_v2` | `TorsoFlatAbs` | Abdominal surface definition; this is not a muscularity simulation |
| Next | `CLAWTorsoRibDepth` | `ChestDepth`, `SternumDepth` | `TorsoSterDepth` | Thorax/sternum depth separately from pectoral volume |
| Next | `CLAWTorsoRibWidth` | `ChestWidth`, `RibsMore_v2` | `TorsoSterWidth`, `TorsoRibsDefinition` | Thorax width; definition inputs may deserve a separate target after inspection |
| Next | paired shoulder widen/narrow targets | `ShoulderWidth` | `TorsoShoulderInc`, `TorsoShoulderDec` | Lateral width separately from shoulder mass |
| Later | `CLAWTorsoGluteRoundness` | `RoundAss`, `ButtShape2`, `ButtSaggy_v2` | `ButtRoundy`, `ButtCurve`, `ButtSaggy` | Separate roundness/sag from volume; opposing meanings require separate fields |
| After the breast rig | separate chest/breast sag fields | `BreastGravity2` | `PecsSaggy` | Soft-tissue position with stable roots and corresponding fur motion |

The present composer clamps each target to nonnegative 0..1. An opposing human
source with a negative gain can cancel widening, but cannot make a neutral wolf
narrower. Genuine narrowing therefore needs its own geometric target (or an
explicitly redesigned signed target contract), rather than an invented offset.

Do not map arbitrary muscle or belly values to ears/tail just to populate every
existing wolf slider. A human ear-size/ear-angle source could justify an ear
mapping; nose/jaw sources could justify muzzle/jaw proportions. No such source
is established in the inspected body catalogs. The inspected RaceMenu 0.5.0-b6
public plugin header offers body reads and face-preset import/export, but no
direct named FaceGen slider reader. A head adapter is separate research, with
race/sex/version handling and capture before transformation. No human `Tail`
source was identified; tail-specific controls stay outside this conversion until
an explicit human-derived rule is selected and justified.

## Required implementation before enabling a target

1. Measure the human source geometry at representative values, including negative
   input if the source family permits it. Select the wolf anatomical region and
   direction; calibrate a family-level rule independent of preset names.
2. Author neutral-preserving wolf deltas for both sexes and every following fur,
   claw or blend surface; check shared seams, weights and both weight endpoints.
3. Extend the public name catalog, native recognized-name allowlist, linked-target
   policy, authoring resources and documentation together. `CLAWArmForearmGirth`,
   for example, is currently rejected by both target recognition and link policy.
4. Stay inside the current 32-rule profile limit or explicitly review a larger
   bounded format. Each source-to-target pair consumes a row.
5. Verify actual coefficients/readback and human-return cleanup, then inspect the
   rendered shape. TRI presence and an offline morph preview are separate evidence.

## Verified source evidence

The private 26 October neutral human asset manifest pins official 3BA 2.48 and
HIMBO 5.8 resources. Main female body TRI SHA-256 is
`924762114705422af5fcf9372adc800113532afa859b42b07cc376588bf92dcf`
(154 names on its main body shape; 156 across its body/hand/foot resource union).
Male body TRI SHA-256 is
`3c4d393e70f8ee86160b5571b69e8f894d1f67f0ed2d7d1067f72b1939a5df7f`
(124 names). The proposed source names above were checked against these catalogs.
HIMBO's supplied `_RaceMenuMorphsHIMBO.psc` independently registers its menu names;
the female menu registration was not independently established here.

Current implementation contracts are [MorphLink.h](../distribution/include/claw/MorphLink.h),
[Preset.cpp](../distribution/src/Preset.cpp), [full-body.json](../recipes/full-body.json)
and [female.json](../recipes/female.json). No human third-party mesh or slider
implementation is copied into these proposals.
