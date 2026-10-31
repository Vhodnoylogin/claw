# Matching source for CLAW 0.7.0.0

This source companion belongs to the exact universal DLL identified by
`source-manifest.json`: one binary for the seven declared SE/AE/VR load
boundaries. It is a source archive, not an installable Skyrim mod.
The product/package version is 0.7.0.0. Native and body input build identifiers
are preserved because this release repackages tested artifacts without recompiling
or modifying any selected game file.

`claw/distribution/` retains the exact native source bytes from candidate03,
including the shared matrix kernel, runtime policy, CMake build and Papyrus
declarations. Packaging verifies these against the checkout before accepting
the candidate. Line-ending differences in text are allowed; code differences
are refused. The source manifest hashes every retained file individually.
`claw/scripts/` and `claw/recipes/` additionally contain the current expressive
body builder and its Python import closure, exact recipe and six-vector fixture.
The snapshot manifest distinguishes these authoring/packaging additions from
the native source frozen with the tested binary.

Native requirements: x64 MSVC with C++23, CMake 3.25+, an external dependency
prefix, and the included exact CommonLib SDK source. Extract
`upstream/CommonLibSSE-NG-0c95630.zip` and place `upstream/openvr/` under the
SDK's `extern/openvr/`. This pins SDK revision
`0c95630c29ff98f64caeea83c29ca373cf93e58b` and OpenVR gitlink
`60eb187801956ad277f1cae6680e3a410ee0873b`. The other `upstream/` trees retain
the library sources and build inputs used by the external SDK dependency prefix.
Unused vendor documentation, tests, examples and developer-only tools are omitted
under the exact per-file policy in `provenance/source-pruning.json`. Every native
source/header, dependency license and the complete CommonLib source ZIP is retained.
Build/install the shipped dependency closure into an external prefix with:

```powershell
./claw/release/working-installer/build-source-dependencies.ps1 `
  -WorkDir '<fresh-external-dependency-build>' -SourceRoot '<source-root>'
```

The helper explicitly disables optional documentation/test/example targets and
records configure/build logs for every library. It does not install into Skyrim.
Use its `prefix/` with the native build below, or provide an equivalent toolchain; the
original dependency versions are retained in `provenance/vcpkg-status.txt`.
Do not copy proprietary game scripts, compilers or live mod folders into source.

From this source archive's root, use fresh external directories and run:

```powershell
./claw/distribution/build.ps1 -BuildDir '<external-native-build>' `
  -CommonLibDir '<extracted-commonlib-sdk>' `
  -SkeeHeader '<source-root>/api/IPluginInterface.h' `
  -OBodyHeader '<source-root>/api/API.h' `
  -DependencyPrefix '<external-dependency-prefix>' `
  -FetchSources @{ PUGIXML = '<source-root>/upstream/pugixml-1.15' } `
  -Runtime UNIVERSAL -BuildTests
ctest --test-dir '<external-native-build>' -C Release --output-on-failure
```

The tested universal build had the optional OBody public header enabled and no
generated physics model/fixture header. The obsolete exact-SE cache, generated
physics data and historical host build receipts are intentionally omitted.
No physics host or configuration ships in the working installer. The helper
never installs or starts the game; tests run only through the explicit CTest
command. `claw/distribution/dependencies.json` and the runtime contract document
pins, build requirements and the distinction between loading and game coverage.
The packaged DLL also needs the Microsoft Visual C++ x64 runtime corresponding
to its imported MSVC runtime libraries.

To rebuild the expressive resources, obtain the exact frozen body inputs from
the canonical CLAW repository's `assets/release/se-core-20261030/base/` through
Git LFS, preserving their relative paths below `claw/`. Their six SHA-256 pins
are enforced by `claw/recipes/expressive-body-v1.json`. Install NumPy, SciPy and
the PyNifly tooling described in `claw/docs/rebuild.md`; configure a local
`claw/build.local.json` or pass `--pynifly` explicitly. Then run:

```powershell
python claw/scripts/expressive_body.py --out '<external-body-build>' `
  --pynifly '<external-PyNifly>' `
  --vectors claw/recipes/expressive-fixture-vectors-v1.json
```

The six generated resources were previously rebuilt twice byte-identically.
This packaging step preserves the accepted candidate's bytes and does not
claim a fresh native rebuild or a new bit-for-bit MSVC DLL reproduction.
The native binary's exact artifact digest is retained separately from its source
digests. Papyrus and ESP rebuilds require external Caprica/game imports and
Spriggit as described by their included declaration/build sources. The tested
PEX/ESP payloads are retained without recompilation.

The deterministic working installer is reproduced from the hash-pinned
candidate03 working archive plus this source snapshot:

```powershell
python claw/scripts/build-working-release.py --candidate '<candidate03.zip>' `
  --out '<new-external-output-directory>'
```

`release/working-installer/` holds the shipped release instructions; packaging
does not modify game, mod-manager, published-release or Git state. All four
installer selections are checked against the candidate's actual runtime files.
This packaging revision makes the native linkage and HIMBO/CBBE body declaration
mandatory. The female choice is CBBE or CBBE plus 3BA; Vanilla body support is
deferred. Only installer policy and documentation change. The three existing
calculation profiles, their arithmetic and all selected game files are retained.
The outer ZIP stores each sex's identical weight-endpoint NIF only once. Explicit
FOMOD file mappings install that source under both `_0.nif` and `_1.nif` paths;
runtime file names, counts and hashes remain unchanged.
Active HIMBO/CBBE/RaceMenu plugin markers gate the module. Active `3BBB.esp`
recommends the 3BA mapping and enables that choice; otherwise CBBE is recommended.
CBBE remains an editable alternative. This detects enabled plugin markers only.
The offline resolver accepts additional active markers as an optional argument;
its frozen 30 October behavior is unchanged when that argument is omitted.
