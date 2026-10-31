# CLAW 0.7.0.0

## Current runtime-only package

The owner-set public title is **CLAW - Customizable Lycanthrope Appearance and
Weight**. The saved file/update-group label is **CLAW - Custom Lycanthrope
Appearance and Weight**, shortened to fit Nexus's 50-character field limit.
Its version is stored separately; legacy installed identifiers remain unchanged.

The packaging-only correction is published as
[CLAW.zip on GitHub](https://github.com/Vhodnoylogin/claw/releases/download/claw/0.7.0.0/CLAW.zip).
It was uploaded to Nexus as file **829735**, replacing and archiving **829608**.
Nexus completed scanning and enabled downloads. An actual browser download of
file **829735** matches the SHA-256 and byte size below and passes ZIP CRC.
This does not imply a moderator decision about the superseded file **829608**.

| Property | Value |
|---|---|
| Archive | `CLAW.zip` |
| SHA-256 | `dec2a2a9abca26c6d597e21f415875b175d82675eb9a6c67949e1d649080feec` |
| Bytes | 14,506,411 |
| Archive members | 32; runtime/install files, required notices and brief user instructions |
| Installed combinations | HIMBO+CBBE or HIMBO+CBBE+3BA; optional OBody host; 10/12 files |

All runtime sources and destinations in the four selections and both FOMOD XML
files are byte-identical to the accepted v3 package below. The DLL remains
`e7b238c82428f76cbefb58a322d25d05580519553ab3aa307d7ce6cc080ac3d5`.
Fifteen licence texts are retained byte-for-byte. Source ZIPs, build recipes,
developer headers and verification/build material were removed; matching native
source is linked at commit `22834eb5d8a8259b17d1b29675c666ab9321753e`.
No fresh compilation, installation or new game qualification is claimed for
this packaging change. The source-only current layout is maintained on `main`.

## Original v3 package history (superseded transport)

Prepared and uploaded on 31 October 2026 as Nexus file **829608**. The upload is
quarantined by Nexus and is not yet available for download. The review request
has been sent to Nexus support with the public source and build instructions.
This record does not claim that the quarantine is resolved.

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

## Original runtime and transport verification

The 31 October core105 and born27 SE mechanisms passed on the exact universal
DLL and expressive body resources. The owner subsequently confirmed visible
differences across all six comparison presets. The screenshot run uses the same
12 selected game files, with separate test data, light and generated NeverNude
human-body output. Packaging has not modified that running session.

One CommonLib DLL serves the seven declared SE/AE/VR load boundaries. Actual game
acceptance is SE 1.7.104.0 / SKSE 2.3.1 with HIMBO/3BA and official RaceMenu.
Other runtime boundaries and the CBBE mapping have offline coverage only. See
[the runtime contract](../../docs/universal-runtime.md) and
[the game verification record](../../docs/verification-20261031.md).

Four FOMOD combinations select only the expected 10/12 game files. Dependency
gates and recommendations, pinned FOMOD5 schema validation, 10 retained packaging
tests, nested source/payload hashes, one-DLL PE metadata and source-extracted
byte-identical package reproduction passed. The 3BA/OBody selection matches the
current screenshot installation byte for byte. The final versioned FOMOD was
subsequently installed through the native MO2 Bridge, including both repeated
NIF-source copies. All 12 selected files, original profile files, priorities,
plugin states and protected test/NeverNude resources passed independent checks.
MO2's native Installed accounting and Nexus mod/file identity 194798/829608 are
verified. This installation check did not launch another game session.

The source-companion and size-reduction details below describe the historical
v3 transport only. No source archive or developer bundle remains in the current
runtime-only download.

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
