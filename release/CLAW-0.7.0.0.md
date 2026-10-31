# CLAW 0.7.0.0

Prepared on 31 October 2026. Publication is a separate operation; this record
identifies the checked archive rather than asserting a Nexus upload.

| Property | Value |
|---|---|
| Archive | `CLAW - Configurable Lycanthrope Anatomy and Weight - 0.7.0.0.zip` |
| Installed mod name | `CLAW - Configurable Lycanthrope Anatomy and Weight` |
| SHA-256 | `b5f4a6f029b8db109542ed83d6b2ba874499d0977ecee87b4d6e05dd6d9b0cd2` |
| Bytes | 22,027,929 |
| Installer choices | HIMBO+CBBE or HIMBO+CBBE+3BA; optional OBody source host |
| Selected game files | 10 without the optional host; 12 with it |
| Archive members | 43, including one corresponding-source ZIP and retained licenses |

This is one working mod archive. The separate `test_CLAW` fixture and its human
comparison presets are not runtime dependencies and are not included here.
The package contains no textures, human bodies, skeleton, physics configuration
or first-person VR body.

## Behavior and requirements

Human morph values drive the actor's own werewolf body through the selected
family's coefficient/function matrix. Ordinary human presets provide the source;
a separate wolf-shape preset pack is not required. Lean fields and stronger
growth fields distinguish thin, muscular and heavy forms. The optional OBody
source host handles eligible new actors first encountered as werewolves while
retaining stock assignment and blacklist rules.

The release requires HIMBO male and CBBE female bodies. 3BA is an optional female
extension that also requires CBBE. Keep all human bodies and their author-declared
dependencies as separate mods. Vanilla human bodies remain deferred.

Elegant Werewolf Replacer supplies required textures; CLAW supplies its own wolf
meshes and lets those meshes win. A compatible XP32 skeleton, the runtime's SKSE,
RaceMenu/SKEE, Address Library and Microsoft Visual C++ x64 runtime are separate
dependencies. OBody and its complete dependency chain are required only when its
optional source integration is used or its human distribution is desired.

The FOMOD requires active RaceMenu/HIMBO/CBBE plugin markers. An active `3BBB.esp`
recommends and enables 3BA; CBBE remains selectable. These markers do not prove
the effective mesh winners, compatible DLL versions or recursive dependencies.

## Verification scope

The 31 October core105 and born27 SE mechanisms passed on the exact universal
DLL and expressive body resources. The owner subsequently confirmed visible
differences across all six comparison presets. The screenshot run uses the same
12 selected game files, with separate test data, light and generated NeverNude
human-body output. Packaging has not modified that running session.

One CommonLib DLL serves the seven declared SE/AE/VR load boundaries. Actual game
acceptance is SE 1.7.104.0 / SKSE 2.3.1 with HIMBO/3BA and official RaceMenu.
Other runtime boundaries and the CBBE mapping have offline coverage only. See
[the runtime contract](../docs/universal-runtime.md) and
[the game verification record](../docs/verification-20261031.md).

Four FOMOD combinations select only the expected 10/12 game files. Dependency
gates and recommendations, pinned FOMOD5 schema validation, 10 retained packaging
tests, nested source/payload hashes, one-DLL PE metadata and source-extracted
byte-identical package reproduction passed. The 3BA/OBody selection matches the
current screenshot installation byte for byte. The final versioned FOMOD itself
has not yet been installed or associated with an MO2 download record.

The minimal transport stores one NIF source per sex and maps it explicitly to
both runtime weight-endpoint paths. This removes duplicate compressed data while
preserving all four installed NIF files and every selected runtime hash.
Unused vendor documentation, tests and examples are removed under a hashed
per-file source-pruning manifest; the complete CommonLib source ZIP and all 28
source-license files remain byte-identical. All ten shipped dependency projects
configured, built and installed into a fresh external prefix. The full CommonLib
SE/AE/VR static library and CLAW's CLI/test targets then built against that prefix;
all six CTest groups passed. The shipped DLL was neither rebuilt nor replaced.
This reduced the archive from 43,008,854 to 22,027,929 bytes (48.79%).

The rejected v2 transport had removed duplicate NIF sources without serializing
the matching FOMOD file directives. Its in-memory verifier had incorrectly
constructed those directives during verification. That earlier signoff was
retracted. The final v3 archive serializes all seven required base file mappings
before validation. A separate ZIP-only regression rejects v2 and confirms the
literal v3 XML's four outcomes, without using release manifests or synthetic
destinations. Independent review and the origin's second literal-XML inspection
confirmed all four 10/12-file selections, both high-weight destinations and every
runtime hash in this exact v3 archive.

## Reproduction and version identity

`scripts/build-working-release.py` takes the hash-pinned candidate03 working ZIP
and writes this package into a new external directory. Its source companion
contains that packager, body authoring inputs and the exact native source with
required upstream sources/licenses. Packaging neither compiles nor publishes.

0.7.0.0 is the complete product/package version. Runtime artifacts retain their
original build identifiers and hashes. No tested DLL, NIF, TRI, PEX, ESP or matrix
was relabelled or recompiled merely to change the package number. Saved native
matrices remain authoritative until explicit rebinding; installing updated XML
does not silently replace existing experimental native co-save profiles.
