# CLAW tests and nonshipping fixtures

This source tree belongs in main alongside the corresponding released code.
Its actors, scenes and preset/configuration overrides do not ship in the working
mod. Compiled test plugins and other generated artifacts belong under ignored
target/, rather than Git.

## Reusable game scenes

| Scene | Reusable source | What it checks |
| --- | --- | --- |
| Human to wolf morphs | [Six-pair placement and operator guide](resources/inspection/README.md), [scene data](resources/inspection/scene.json), [matrix scorer](python/integration/analyze_matrix_capture.py) | Matched human and wolf poses and recorded output against the shared evaluator. The operator guide uses an admitted session. |
| Coat appearance | [Four matched pairs, five skin tones and seeded combinations](resources/inspection/regional-coats/README.md), [SE runner](python/integration/coat_regional_scene.py) | Compare the automatic coats, common Valley Grey control and harmonized previews. Isolate skin with identical hair inputs, then sample natural skin and hair combinations under the same lighting. Every run retains per-wolf material observations. |
| SE publication photos | [Coat and light-coat morph scenes](resources/inspection/publicity-se/README.md), [SE runner](python/integration/publicity_se_scene.py) | Photograph the automatic colour controls and the HIMBO and CBBE morph cases in the same lit QASmoke bay. Check the actual materials and RaceMenu coefficients. |
| SE coat gallery | [Gallery setup](resources/inspection/publicity-se/README.md), [catalog runner](python/integration/publicity_coat_catalog.py) | Photograph all 34 original Elegant Replacer patterns or the ten Randomized patterns on one wolf with a fixed camera and neutral fill. Verify the actual texture assignments for every frame. |
| SE human colour references | [Portrait setup](resources/inspection/publicity-se/README.md), [portrait runner](python/integration/publicity_human_palette.py) | Photograph nine stock NPCs in matched skin and hair groups. Verify the live material colours and fixed capture conditions. |
| SE Elegant palette review | [Selected donors and return trials](resources/inspection/publicity-se/elegant-review.json), [review runner](python/integration/publicity_elegant_review.py) | Photograph original Elegant body, head and fur combinations with the same lighting. Verify each bound texture on a fresh werewolf model. |
| SE dark skin and red hair | [Anwen's red hair scene](python/integration/publicity_red_hair_review.py), [setup](resources/inspection/publicity-se/README.md#selected-elegant-combinations) | Verify the actual human colours and automatic regional coat on two transformations of the same actor. |
| Physics and motion | [SE physics probes](docs/physics-probe-fixture.md), [owned FSMP motion case](python/integration/fsmp_owned_case.py), [human-origin lifecycle runner](python/integration/fsmp_human_lifecycle.py) | Compare enabled and disabled motion and verify the target bones and configuration. Each case needs the provider and topology it declares. The earlier whole-body probes do not qualify the tail-only candidate. |
| VR colliders | [Posed contact case](components/contact-profiles/posed-contact.md), [tail refit scene](components/contact-profiles/tail-refit-preparation.md), [owned tail refit runner](components/contact-profiles/owned_tail_refit_case.py) | Check the bound geometry, controller/contact timing and collider refit at different morph states. The calibrated VR session, controller provider and current fitted model are external inputs. |
| VR add-on 0.5.0 inspection | [Operator run sheet](resources/inspection/vr-addon/README.md), [scene inputs](resources/inspection/vr-addon/scene.json) | Follow one human through Beast Form and return, inspect body and morphs in the headset, then verify contact and optional tail motion with the selected provider setup. |
| VR stationary collider showcase | [Build and prepare](resources/inspection/vr-addon/collider-showcase/README.md) | A stationary wolf wears colour-coded wire cages drawn from the exact fixed CBPC bank. Use either tracked hand to compare the drawn boundary with live contacts. |
| VR body mirrors | [HIMBO and 3BA scene](resources/inspection/vr-addon/player-mirror/README.md) | The same large human morphs are applied to the player and two matching fixtures. Compare the first-person Beast Form with a human and a wolf seen from outside. |

Preserve new or revised placements, fixture sources and observations required
by a scenario here. Keep local configuration, saves, screenshots, generated
artifacts and MO2, Morphbench and Autotest logs outside the repository.

## Test categories

- `python/unit/`: synthetic/pure contracts, source configuration and packaging
  guards. These do not require a pre-existing release archive, built body or
  compiled NPC fixture. Tests may create their own temporary synthetic artifacts
  under target/ and remove them afterward.
- `python/physics/`: provider, source/lifecycle and capsule-calculation contracts.
  A passing offline contract does not establish engine physics acceptance.
- `python/vr/`: offline geometry/visibility and resource lookup contracts. Existing
  explicitly optional external-resource cases report their skips when their
  declared inputs are absent.
- `python/photo_comparison/`: nonshipping pose, frame-registration and screenshot
  custody checks retained from the 13F comparison. Run this separate suite with
  Pillow, NumPy and OpenCV; four same-opened-file custody tests require Windows.
  See [scope and provenance](docs/photo-comparison-13F.md). These helpers do not
  launch a game and are not included in the default source suites.
- `python/integration/`: prepared-resource checks. Missing mandatory inputs fail;
  they are not silently replaced by synthetic data. Explicitly opt-in archived
  evidence checks identify their skips separately. This includes16
  checks moved out of the default unit suite without changing their assertions:
  ten historical FOMOD checks, three actual surface-repair checks, one six-resource
  hash inventory and two compiled wild-NPC fixture checks.
- `cpp/`: native CTest source, built through the root CMake project.
- `resources/`: human preset XML, Spriggit NPC sources and the portable inspection
  kit. `papyrus/` contains scripts used only by test plugins.

From repository root, default source checks are:

```powershell
python build.py test
```

The wrapper runs unit, physics, VR and contact-profile suites. Run the
prepared-resource integration and inspection separately. Direct suite commands are:

```powershell
python -m unittest discover -s src/test/python/unit -p 'test_*.py'
python -m unittest discover -s src/test/python/physics -p 'test_*.py'
python -m unittest discover -s src/test/python/vr -p 'test_*.py'
```

Keep observed counts and optional-resource skips in the report; default source
success does not mean all resources, native libraries or game behavior were tested.

The transport-free [FSMP binding/excitation probe](python/integration/fsmp_probe.md)
prepares owned-run packets and scores retained anchor-relative world transforms.
Its synthetic discrimination tests do not establish working in-game physics.
The [12 November qualification record](docs/physics-qualification-20261112.md)
keeps accepted female/male root-recreation cases separate from failed timing
cases and passive CBPC binding diagnostics. The [authored probe fixtures](docs/physics-probe-fixture.md)
include separate born-female and born-male actors; compiled plugins stay outside Git.

## Prepare resource integration

The actual body tests use generated `legacy/` and `repaired/` stages, each with
`Meshes/Actors/WerewolfBeast/Character Assets/` beneath it. The default input root
is target/bodies/fresh. Build from pinned original donors with the declared
Blender producer before running integration; released body files are not build
inputs. For another explicit fresh build directory:

```powershell
$env:CLAW_INTEGRATION_BODY_ROOT = '<fresh-body-build-directory>'
```

The body tests retain their six exact hashes and corruption/refusal assertions.
A newer geometry baseline needs its own reviewed contract change, not an altered
expectation merely to make a failing test pass.

The compiled wild fixture must exist at
`target/test-assets/plugins/test_CLAW - Wild Preset Fixture.esp`. Build its
Spriggit YAML from resources/plugins using the configured external Spriggit tool:

```powershell
python build.py plugins 'test_CLAW - Wild Preset Fixture'
```

The historical FOMOD class additionally requires the exact retained
`target/references/releases/se-core-20261030/` tree. Its manifest SHA256 remains
`d915156d9620770153e26d5bbbe1577da828c69f572daac402e2e93756e20ed9`.
This is a historical golden-release test: a newly compiled universal DLL cannot
be relabelled as that old payload. Reference acquisition and its verification
are separate prerequisites; no compiled reference is tracked in current main.

The prepared integration also needs these explicit inputs:

- `CLAW_AUTOTEST_SOURCE` points to the selected source checkout containing
  the `skyrim_autotest` package for the transport fixtures.
- `CLAW_MATRIX_CAPTURE_CLI` points to the matching native `claw-preset-tool`.
  Set `CLAW_MATRIX_CAPTURE_CLI_SHA256` to check a reviewed binary pin.
- The PlayerOnly tests require `CLAW_PLAYERONLY_PACKAGE`,
  `CLAW_PLAYERONLY_BASELINE`, `CLAW_PLAYERONLY_ELEGANT_ARCHIVE`,
  `CLAW_PLAYERONLY_PYNIFLY` and `CLAW_PLAYERONLY_NATIVE_DLL`. Use the archived
  actual packages and external installed dependency inputs listed by the test.

Once the required artifacts are ready:

```powershell
python -m unittest discover -s src/test/python/integration -p 'test_*.py'
python src/test/resources/inspection/validate.py
```

The `test-integration` wrapper action runs this prepared-resource category and
inspection validation. Neither command starts a game or writes live MO2 files.

## Replay the actual physics mass observation

`python/integration/fsmp_mass_readback.py` is the pure, nonshipping checker for
two paused solver/WORLD observations. It reuses the one existing native witness
validator. The [18 November record](docs/development-20261118.md) identifies the
actual one-parameter Morphbench/FSMP check and its limits.

Select the immutable archived `paused-mass-writeback.json` explicitly:

```powershell
$env:CLAW_FSMP_MASS_READBACK_EVIDENCE = '<archived-paused-mass-writeback.json>'
$env:CLAW_FSMP_MASS_READBACK_REQUIRED = '1'
python -m unittest discover -s src/test/python/integration -p 'test_fsmp_mass_readback.py' -v
```

These eight checks replay the actual positive observation and reject corrupted
mass, body association, scale, identity, cache and clock data. With no selection
the optional class reports a visible skip; `REQUIRED=1`, a missing selected file
or a changed selected digest fails. No game, manager or synthetic positive
observation is created. Raw archived captures stay outside Git and release files.

## Replay the actual joint lower-limit observation

`python/integration/fsmp_joint_limit_readback.py` ports the frozen pure checker
used by the18November functional lower-limit case. It shares the sole native
witness validator. Portable symbolic fixtures check pivot/frame math, original
mass and kinematic-parent association, positive/zero/wrong-sign discrimination,
right-side controls and both-side completed-window drift. Symbolic passes are
scorer checks, not game evidence.

Select the immutable archived `ACTUAL-REPLAY-BUNDLE.json` explicitly to replay
run`20261118-195300-705a97`:

```powershell
$env:CLAW_FSMP_JOINT_LIMIT_READBACK_EVIDENCE = '<archived-ACTUAL-REPLAY-BUNDLE.json>'
$env:CLAW_FSMP_JOINT_LIMIT_READBACK_REQUIRED = '1'
python -m unittest discover -s src/test/python/integration -p 'test_fsmp_joint_limit*.py' -v
```

Without selection the actual class reports a visible skip; `REQUIRED=1`, an
explicitly missing input or changed selected digest fails. The six actual-data
checks replay both paused associations and the completed900pair window, then
reject corrupted mass, parent association, identity/scale/clock and right-side
drift. Raw captures stay outside Git. These functions do not call the historical
cached module-admission dictionary or perform current binary admission.
The scope is one edited lower-limit's unit-scale solver/WORLD effect; no broad
damping, contact, rendering, root578 or VR qualification follows.

## Replay the actual angular lower-limit observation

`python/integration/fsmp_angular_limit_readback.py` reuses the canonical joint
pairing/frame helpers and their sole witness validator. It checks one left P1
angular lower limit+.005radians with1e-4rad tolerance, unchanged right control
and bilateral settling. Bullet RO_XYZ uses column-indexed matrix elements:
positive Bullet x has the opposite sign to ordinary active Rx. Portable tests
cover this sign, rotated frames/pivots, invalid bases/regimes and drift, using
the existing symbolic fixture helper. Symbolic positives are not game evidence.

Select the immutable bundle from run`20261118-201916-366d11` explicitly:

```powershell
$env:CLAW_FSMP_ANGULAR_LIMIT_READBACK_EVIDENCE = '<archived-ACTUAL-REPLAY-BUNDLE.json>'
$env:CLAW_FSMP_ANGULAR_LIMIT_READBACK_REQUIRED = '1'
python -m unittest discover -s src/test/python/integration -p 'test_fsmp_angular_limit*.py' -v
```

The eight portable checks require no external assets. Four selected actual-data
checks replay the paused and completed900pair window and reject sign/zero,
right-drift, mass and stale-observation corruptions; two additional checks cover
explicit input selection. Without selection the actual class skips visibly;
`REQUIRED=1`, a missing selected file or a changed digest fails. Raw captures
remain outside Git. This is one angular stop's solver/WORLD effect, without
general damping, amplitude, contact, rendering or VR qualification.

## Replay the actual uniform-scale observation

`python/integration/fsmp_uniform_scale_readback.py` reuses the canonical joint
and angular helpers for one observed uniform1.1-scale case. It retains the unit
setup separately from the acknowledged measurement lease and uses actual WORLD
scale for inverse mass20/s^3 and the scaled rest pivot. The accepted unit-scale
pair contract is unchanged. See the
[18 November scale record](docs/physics-uniform-scale-20261118.md).

```powershell
$env:CLAW_FSMP_UNIFORM_SCALE_READBACK_EVIDENCE = '<archived-ACTUAL-REPLAY-BUNDLE.json>'
$env:CLAW_FSMP_UNIFORM_SCALE_READBACK_REQUIRED = '1'
python -m unittest discover -s src/test/python/integration -p 'test_fsmp_uniform_scale*.py' -v
```

Fourteen portable checks cover scale, mass, pivot and identity discrimination.
Six selected actual-data checks replay the retained setup and900-pair window,
including unscaled mass/limit, right-side drift and stale-data refusals; two
additional checks cover explicit evidence selection. Unset evidence skips the
actual class visibly; required, missing or changed selections fail. Raw captures
remain external. This finite case does not establish general damping, nonuniform
scales, rendered attachment, contacts or VR behavior.

## Replay the actual nonzero mixed-source lifecycle

The [18 November record](docs/nonzero-mixed-20261118.md) describes the accepted
CBBE/BHUNP source-update/deletion/save-load/return case. Its portable replay uses
recorded native predictions and independently parsed Observer storage packets;
it neither reruns the native evaluator nor checks current installed files.

```powershell
$env:CLAW_MIXED_SOURCE_READBACK_EVIDENCE = '<archived-ACTUAL-MIXED-SOURCE-REPLAY.json>'
$env:CLAW_MIXED_SOURCE_READBACK_REQUIRED = '1'
python -B -m unittest discover -s src/test/python/integration -p 'test_mixed_source*.py' -v
```

The selected suite passes23 checks. Without selection the actual class skips
visibly; explicit missing, changed or required-unset evidence fails. Four fast
markers remain provisional: mandatory full source/target audits cannot be
replaced by retained-input predictions. This is numerical/storage evidence,
not rendered body deformation or a universal body-family classifier.

The [configured-parameter check](docs/fsmp-configured-parameters-20261119.md)
records a separate schema4 FSMP result: the intended two joints received the
source-derived coefficients, while the original damping-response gate still
failed. Configured values and observed motion are separate acceptance claims.

## Private CPU geometry observation

The standalone [geometry witness](cpp/geometry_witness/README.md) is a
nonshipping SE-only test component. It reads nine bounded points from the
currently attached CPU pre-skin stream. Portable controls and a successful DLL
build do not qualify the engine ABI, actual GPU positions or visual attachment.
It has no production CMake, install or game-launch integration.

## Test actors and manual scene

Every actual test actor/scene mod uses the prefix test_. Ordinary dependencies
keep their original mod names and separate source-accounted installations.

`test_CLAW - Companion` retains the older Ulva human/female-beast records and
its explicit race-switch test spell. `test_CLAW - Wild Preset Fixture` contains
six initially-beast, unplaced NPC bases: Sever, Klyk, Buryi, Luna, Vyuga and Tucha.
The first three are male, the last three female; the plugin creates no scene.

`resources/fixtures/CLAW-Human-Contrast.xml` supplies six ordinary HIMBO/3BA human
presets with equal small/big coefficients. The same source coefficients drive
human-to-beast linkage and originally-beast OBody bootstrap. The test must not
substitute an independently assigned wolf preset, manual GenActor call or a
temporary human transformation for actual born-wolf distribution.

The [portable inspection kit](resources/inspection/README.md) records the accepted
paired placement, clear actor identities, underwear, lighting, AI/collision holds
and group commands. Wild actors appear only on an explicit group command after
the paired group is hidden. Group removal hides same-run owned references;
showing a group reuses them without duplication or a new preset roll. No saved
FF reference or assumed load-order prefix is reusable across sessions.
