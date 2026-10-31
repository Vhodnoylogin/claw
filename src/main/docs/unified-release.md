# CLAW - Configurable Lycanthrope Anatomy and Weight: unified installer

This is the historical **30 October packaging contract**, retained for its
recorded archive and installer checks. Read-only release references are external
or under ignored `target/`, not source payloads in Git. See the pinned
[original release record](https://github.com/Vhodnoylogin/claw/blob/53e8f3872533f193483a4ee683d3bece1fe3eafa/release/SE-Core-20261030.md).
Current source-only builds follow [rebuild.md](rebuild.md); the old archive's
acceptance does not qualify the fresh donor pipeline or a newly packaged file.

`src/main/python/build-tools/build-unified-release.py` creates one
`CLAW - Configurable Lycanthrope Anatomy and Weight - 20261030.zip` from the exact
Base, Distribution and native corresponding-source inputs retained under
`target/references/releases/se-core-20261030/`. It changes packaging and installer choices,
not runtime code, meshes, morphs, plugins, scripts or mappings. The published
file name has no edition suffix. This does not make its native DLL universal.

The FOMOD always installs the seven frozen base runtime files. Its optional
native linkage is available only for detected game version **1.7.104.0** with
active `RaceMenu.esp`. The user still needs matching official RaceMenu/SKEE,
SKSE 2.3.1 and Address Library v13. Plugin presence cannot verify those binaries
or the complete dependency chain. Linkage selects one measured human resource
declaration: HIMBO + CBBE or HIMBO + 3BA. The optional originally-beast source host
additionally requires active `OBody.esp`; omitting it installs neither its ESP nor
its PEX. Human bodies, presets and their dependencies remain separate mods.

Other SE/AE executables and VR receive base resources only; the native option is
disabled. The base's frozen light-plugin flag remains unchanged. The installer
does not establish VR light-plugin handling, dependencies or new game acceptance
for other editions. The separate historical VR DLL and experimental physics
packages are not included. Elegant textures and the appropriate XP32 skeleton
remain external requirements. No textures, skeleton, test actors, physics configs
or replacement third-party DLLs are added.

| Valid selection | Runtime files | Mapping |
| --- | ---: | --- |
| Base only | 7 | None |
| Linkage, HIMBO + CBBE | 9 | One CBBE mapping |
| Linkage, HIMBO + 3BA | 9 | One 3BA mapping |
| Linkage, HIMBO + CBBE, OBody host | 11 | One CBBE mapping |
| Linkage, HIMBO + 3BA, OBody host | 11 | One 3BA mapping |

These counts cover ESP/PEX/DLL/NIF/TRI files. Selected native notices and the
unified README are additional documentation. Original overlapping component
READMEs are retained separately under archive `Docs/Base/` and
`Docs/Distribution/`. Original Distribution installer XML and the unchanged native
corresponding-source ZIP are retained under archive `Source/`. The FOMOD never
installs that directory. The original source ZIP's historical SE-specific name
accurately identifies the frozen native source; it is nested in the one download.

## The exact runtime gate

The inspected primary FOMOD schema defines `gameDependency` as a **minimum**,
not equality, and specifies first matching dependency-type pattern. The reviewed
MO2 implementation parses four integer components, zero-fills omitted components,
and compares them lexicographically. Therefore the native selector uses:

1. Minimum `1.7.104.1`: `NotUsable`.
2. Minimum `1.7.104.0` and active RaceMenu: `Optional`.
3. Default: `NotUsable`.

Only `1.7.104.0` (including its equivalent three-part spelling) reaches the
allowing pattern. The gate does not use a nonexistent FOMOD `Not` operator or
treat a minimum dependency as equality. The single native and OBody toggles use
`SelectAny`: the inspected MO2 source turns singleton required-selection groups
into `SelectAll`, which bypasses ordinary dependency enforcement. Family selection
uses a two-option `SelectExactlyOne` group. Family and host pages read a flag
from the preceding native page, consistent with MO2's previous-visible-page rule.

[The source contract](../resources/publication/unified-installer/installer-contract.json)
records primary schema/source hashes and inspected line ranges. Third-party
installer implementation is not copied into this repository. The CLI requires
the matching local primary files, verifies their hashes and records the contract
inside the archive manifest. Other installer implementations must honor these
standard pattern semantics; manually copying every folder bypasses the choices.

## Reproduction and verification

```powershell
python src/main/python/build-tools/build-unified-release.py --out '<new-external-output-directory>' `
  --schema '<reviewed-GenericModConfig5.0.xsd>' `
  --installer-source '<reviewed-src/fomodinstallerdialog.cpp>'
python -m unittest discover -s src/test/python/unit -p test_unified_release.py -v
```

The builder requires the exact reviewed frozen input-manifest hash, checks each
listed input's size/SHA-256 and complete component inventory, and preserves its
bytes. It refuses existing, checkout and live-game/mod destinations. ZIP paths
are sorted, timestamps fixed, permissions fixed and compression fixed. Final
readback checks every ZIP entry and its CRC, then evaluates the actual shipped
XML for all five selections and unsupported-version/dependency controls. Input
bytes and inventory are rechecked before completion. A per-file archive manifest
records source provenance, hashes, installer contract and installed-file lists
for each selection; that manifest explicitly excludes its own self-hash.

Ten regression tests cover the exact owner-specified mod/archive name, all frozen
bytes, five selections, adjacent runtime
versions including `1.7.104.1`, AE/VR, missing RaceMenu/OBody, reversed pattern
order, source/unselected-script leakage, unsafe paths/collisions, corrupted inputs,
and byte-identical independent ZIP builds. The actual ModuleConfig also passed
the pinned Generic FOMOD 5.0 XSD through .NET's schema validator. These are offline
packaging checks; no manager wizard, installed mod or game was operated.

The completed external artifact is
`Builds/claw-release-20261030/unified-github-release/CLAW - Configurable Lycanthrope Anatomy and Weight - 20261030.zip`:
47,973,328 bytes, 46 archive files, SHA-256
`4d58714f83e4dea70b52d0d2d2ea2fd0aff9f54b2cd1c321c02f7a97ae038a49`.
`build-receipt.json` and `fomod-schema-validation.json` are retained beside it;
`unified-tests.log` is retained in the parent build directory. Publish the single
install ZIP as the downloadable GitHub asset. Its nested corresponding source
does not require a second release download.

Each verified outcome also has an external `selection-*.json` with every selected
destination, archive member, size and hash. `selection-3BA-OBody.json` is the
current exact-SE choice for HIMBO + 3BA with the originally-beast OBody host:
11 runtime files, one family mapping and the selected documentation/notices.
These maps say `installed: false`; generating them does not deploy or activate
anything. The earlier short-name archive and receipts remain preserved in
external `staging-history/unified-before-full-name-001/`.
