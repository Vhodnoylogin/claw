# CLAW tests and nonshipping fixtures

This source tree belongs in main alongside the corresponding released code.
Its actors, scenes and preset/configuration overrides do not ship in the working
mod. Compiled test plugins and other generated artifacts belong under ignored
target/, rather than Git.

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
- `python/integration/`: mandatory prepared-resource checks. Missing inputs fail;
  they are not silently skipped or replaced by synthetic data. This includes16
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

The wrapper runs unit, physics and VR suites. It does not run the compiled
inspection validator or claim integration readiness. Direct suite commands are:

```powershell
python -m unittest discover -s src/test/python/unit -p 'test_*.py'
python -m unittest discover -s src/test/python/physics -p 'test_*.py'
python -m unittest discover -s src/test/python/vr -p 'test_*.py'
```

Keep observed counts and optional-resource skips in the report; default source
success does not mean all resources, native libraries or game behavior were tested.

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

Once the required artifacts are ready:

```powershell
python -m unittest discover -s src/test/python/integration -p 'test_*.py'
python src/test/resources/inspection/validate.py
```

The `test-integration` wrapper action runs this prepared-resource category and
inspection validation. Neither command starts a game or writes live MO2 files.

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
