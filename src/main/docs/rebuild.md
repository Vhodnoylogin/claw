# Building CLAW from source

The current source layout separates maintained inputs from generated output.
Production sources live in `src/main/`, every test and reusable fixture in
`src/test/`, and generated files in ignored `target/` or an explicit external
build directory. Run commands below from the repository root.

The released 0.7.0.0 runtime has its own [recorded game evidence](verification-20261031.md).
The reorganized donor pipeline has now passed a fresh Steam Blender 5.2.3 LTS
build from all three original donors: six exact legacy files, six strict repaired
files and six expressive destinations matching the 0.7.0.0 installer bytewise.
The historical archive was comparison evidence, never an input to generation.
This is body-resource reproduction, not a new installation or game result.

## Inputs and tools

- Python 3.12 and the dependencies required by the selected stage, including NumPy.
- Blender and PyNifly for the donor pipeline. Keep Blender's interface in English:
  PyNifly's material-node lookup expects `Material Output`.
- The pinned original Elegant male/female meshes and XP32 skeleton in
  [donors](../resources/donors/README.md), with their original permissions and hashes.
- CommonLib and the dependency versions recorded in
  [the native build inputs](../cpp/dependencies.json), plus the required C++ tools.
- Spriggit for compiling maintained YAML; the Papyrus compiler and declared
  imports for scripts. Compiled products are not stored in Git.

Configure machine paths in ignored `build.local.json` at the repository root:

```json
{
  "mods": "D:/MO2/Skyrim SE/mods",
  "blender": "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe",
  "pynifly": "C:/Blender/addons/io_scene_nifly",
  "sevenZip": "C:/Program Files/7-Zip/7z.exe",
  "morphbench": "../morphbench/src/main/mb.py"
}
```

Use actual installed paths and verify producer versions. The historical donor
export used Blender 5.2.2 LTS; differences must be diagnosed rather than accepted
by disabling the pinned input checks.
The legacy path adapter still requires a configured `mods` key for external tool
locations. The body pipeline does not substitute installed meshes for the donors.

## Fresh bodies

```powershell
python src/main/python/build-tools/fresh-body-pipeline.py --out target/bodies/review-1
```

Choose a new directory. This reads original donors and
`src/main/resources/recipes/build.json`, records source/tool hashes and builds
legacy stages before applying `surface-repair-v1.json`. It does not read installed
MO2 bodies as substitutes or use a historical release as a build input. An optional
historical reference under `target/references/` is comparison evidence only.
A missing reference is not permission to skip before-repair hashes. Read
`fresh-body-report.json` in the output directory and retain mismatch diagnoses.
The expressive fields are described in [expressive-body.md](expressive-body.md).

The older `build-surface-repair.py` consumes a supplied baseline body directory.
Replaying repair against a downloaded baseline is a different check from rebuilding
that baseline from original donors.

The completed source-build report is `fresh-body-report.json`, status
`fresh-source-through-070-built`; it records the producer and every input/output
hash. The female legacy slimming path preserves the original local-space float32
vertex additions. Routing that path through the world-space helper introduced an
extra inverse-matrix multiplication and changed packed output. The correction is
in CLAW's own `build-female.py`; no third-party exporter was patched.

## Native code, plugins and scripts

Native source and CommonLib builds are in [src/main/cpp](../cpp/README.md):

```powershell
pwsh -File src/main/cpp/build.ps1 `
  -BuildDir target/native/review-1 `
  -CommonLibDir '<pinned-CommonLib-source>' `
  -SkeeHeader '<official-SKEE>/IPluginInterface.h' -BuildTests
```

The one portable matrix implementation remains
`src/main/cpp/shared/MatrixKernel.cpp`. The independently maintained
[Morphbench comparison plugin](https://github.com/Vhodnoylogin/claw-morphbench-plugin)
consumes a pinned version of that source; it is not a copied subtree here.

Runtime plugin source is text in `src/main/resources/plugins/`; test plugin source
is in `src/test/resources/plugins/`. Compile the YAML through Spriggit:

```powershell
python src/main/python/build-tools/plugin.py build
python src/main/python/build-tools/plugin.py check
```

Generated ESP files go under `target/plugins/` and `target/test-assets/`.
The legacy full `build-all.py` package stage expects the separately generated
`target/plugins/released/CLAW.esp`; compile its YAML first rather than restoring
an old compiled plugin from Git or a historical archive.
`check` compares reconstructed records; plugin-header serialization and source
record equality are separate checks. Papyrus source is in `src/main/papyrus/claw/`
and `src/main/papyrus/obody/`; integration examples have their own source directory.
Read each compiler entrypoint's options before supplying game imports. PEX, ESP
and DLL outputs never become source through LFS.

## Checks and packaging

The root build entrypoint exposes `test`, `test-integration`, `bodies`, `native`,
`plugins` and `package` actions. `python build.py test` runs the source-level unit,
physics and VR Python suites; it does not run the compiled inspection validator.
Native CTest checks are part of the native build contract. All test code and
fixtures are under [src/test](../../test/README.md).

`python build.py test-integration` runs the prepared-resource tests and inspection
validator. Compile the wild fixture from
`src/test/resources/plugins/` before its record tests and inspection validator.
Real-body regression cases also require their declared generated inputs, while
the older unified-installer regression deliberately checks an exact historical
manifest and components. These are explicit integration/reference preconditions;
copying a warm `target/` into a snapshot does not prove a clean-source test pass.
Keep missing-input failures and optional-integration skips visible.

Packaging requires completed body/native/plugin/script stages, exact source and
dependency identities, actual FOMOD selection checks and a minimality audit. Keep
the working archive and optional `test_` archive under `target/` or a declared
external release directory. Follow [release-workflow.md](release-workflow.md).
An archived binary set is not proof of a fresh build.

## Historical build documentation

The original [0.7 source/build record](https://github.com/Vhodnoylogin/claw/blob/53e8f3872533f193483a4ee683d3bece1fe3eafa/release/working-installer/SOURCE.md)
and [earlier donor/build narrative](https://github.com/Vhodnoylogin/claw/blob/53e8f3872533f193483a4ee683d3bece1fe3eafa/docs/rebuild.md)
are pinned to the original tree. Their paths describe those historical commits.
Current layout and fresh-build acceptance follow this document and current reports.
