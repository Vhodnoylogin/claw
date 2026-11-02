# Elegant texture library and runtime contract

The 0.8.5 source candidate packages all 355 original DDS members from **Elegant
Werewolf Replacer 2K**, Nexus mod 93336, file 791439, version 2.1, plus the runtime
catalog and policy. The original diffuse-only preparation helper remains useful
for development measurements; it is not an end-user installation requirement.
Neither helper downloads, installs, enables or publishes a mod. Generated DDS
files remain outside Git.

Elegant remains a declared Nexus requirement at the owner's request, with
Wolflady500, KaienHash and the donor's asset contributors credited, and the reuse terms retained. The
private repository permission excludes textures from that repository; it does
not replace the separate runtime terms or grant unrestricted donor replacement.
The bundle is not a new texture licence, and attribution/non-obsolescence
conditions still apply.

Only this exact source archive is qualified:

```text
248252479 bytes
SHA256 622c7be3d10d4158e84e41ce0eb41941469879800e9a5effbe186aaddb305fcc
```

Its Nexus metadata identifies 2.1; embedded `fomod/info.xml` still says 2.0.
The pinned inventory records actual archive members, not a guessed version or
blind FOMOD replay. In particular, Spirit's FOMOD source ends in `Data/Textures`
with an empty destination. The tool correctly retains its actual source path
and writes the same namespaced `textures/...` layout as every other pattern.

## Complete 0.8.5 bundle

`coat_bundle.py` includes 306 pattern diffuse files, 11 shared resources, 28 eye
variants and 10 Lobo patch textures. All 34 nine-map patterns remain intact. Shared
textures retain their expected Elegant paths; pattern maps, alternate eyes and
Lobo files use CLAW namespaces. The alternate eyes and Lobo files are bundled but
are not automatically applied or used to override an installed eye/companion
choice. The per-actor adapter still changes only its named body/head/fur diffuse
slots.

```powershell
python -B src/main/python/build-tools/coat_bundle.py prepare `
  --archive '<existing Elegant 2K 2.1 archive.7z>' `
  --executable 'C:/Program Files/7-Zip/7z.exe' `
  --metrics '<reviewed palette-metrics.json>' --output '<NEW_BUNDLE_DIRECTORY>'

python -B src/main/python/build-tools/coat_bundle.py verify `
  --folder '<BUNDLE_DIRECTORY>'
```

This build interface consumes the pinned complete inventory, archive identity
and approved real-pixel metrics SHA256. It verifies all 355 members and exactly
reconstructs `CoatLibrary.xml` from those measured palettes. The bundle has 357
runtime resources: DDS files plus `CoatLibrary.xml` and `CoatPolicy.xml`.
`bundle-receipt.json` and `palette-metrics.json` are external provenance, not
runtime payloads. `package-source-build.py --coat-bundle` checks captured payload
size/SHA256 and maps those resources into every body-family selection. Users
install the resulting normal archive, without extracting the donor archive.

These are offline preparation and packaging checks. The new policy, fallback
and persistence mechanism still require actual game acceptance.

## Diffuse-only development preparation

Python 3 and an explicitly supplied trusted 7-Zip executable are required.
Choose a **new directory outside the game, MO2, repositories and release staging**.
Preparation refuses an existing target and rejects reparse/symlink ancestors.
The same reusable output guard applies to metrics and runtime XML: no `.git`
ancestor (including worktree `.git` files); no exact `Data`, `mods`, `profiles`,
`overwrite` or `downloads` path component; and no ancestor containing
`ModOrganizer.ini`, `ModOrganizer.exe`, `SkyrimSE.exe`, `SkyrimVR.exe` or `TESV.exe`.
Preparation also excludes the archive, 7-Zip and helper input/tool directories.
These are exact components and filesystem markers, not broad name substrings:
an isolated `Builds/modelling-data-downloads-review/` destination is permitted.
The guard validates paths without creating them and is repeated before publishing
the completed library. Metrics/XML file creation additionally uses exclusive mode.
From repository root after source integration:

```powershell
python -B src/main/python/build-tools/coat_library.py prepare `
  --archive '<existing Elegant 2K 2.1 archive.7z>' `
  --seven-zip 'C:/Program Files/7-Zip/7z.exe' `
  --inventory src/main/resources/appearance/elegant-2k-2.1.inventory.json `
  --output '<NEW_LOCAL_LIBRARY_DIRECTORY>'

python -B src/main/python/build-tools/coat_library.py verify `
  --inventory src/main/resources/appearance/elegant-2k-2.1.inventory.json `
  --library '<LOCAL_LIBRARY_DIRECTORY>'
```

The tool checks the whole archive size/SHA256, selected-member sizes/CRCs,
normal-file attributes, complete palette coverage and decoded DDS headers.
7-Zip emits only a byte stream on stdout. Python writes only validated namespace
paths, so an archive member never controls an extraction destination. Per-member
CRC checks also validate the stream's order. Failed preparation is not published
as a completed output. Temporary files remain under the explicitly chosen parent.
The current publication rename contract is qualified on Windows: it refuses an
already existing target directory and never uses overwrite/merge/replace.

This older diffuse-only helper payload has 306 original DDS files, 549,498,912 bytes:

```text
textures/actors/character/werewolf/claw/elegant-2k-2.1/<pattern-id>/<name>.dds
SKSE/Plugins/CLAW/CoatLibraries/elegant-2k-2.1.json
```

Every pattern has `body`, `head`, `furarms`, `furback`, `furbelly`, `furchest`,
`furface`, `furshoulders` and `furtail` diffuse textures. No normal/specular map,
eye, skeleton, mesh or anatomy texture is copied. The JSON manifest includes the
original archive/member paths, CRCs, SHA256, DDS dimensions/format and source
inventory identity. `verify` rechecks size, SHA256, the qualified source CRC and
DDS metadata, and rejects path changes or missing files.

## Measured palette metadata and runtime XML

Pillow and NumPy are optional offline analysis prerequisites, not game
requirements. To measure actual pixels and emit the small native sidecar:

```powershell
python -B src/main/python/build-tools/coat_palette_metrics.py `
  --library '<LOCAL_LIBRARY_DIRECTORY>' `
  --inventory src/main/resources/appearance/elegant-2k-2.1.inventory.json `
  --output '<NEW_LOCAL_METRICS_REPORT.json>' `
  --runtime-xml '<LOCAL_LIBRARY_DIRECTORY>/SKSE/Plugins/CLAW/CoatLibrary.xml'
```

These outputs must also be new files. Decoding failure is explicit; no colour is
invented. A deterministic grid samples at most 65,536 actual texels per texture.
Fully transparent texels contribute nothing. Remaining texels are weighted by
their actual alpha, and RGB bytes are interpreted as sRGB then averaged in
linear RGB. The report retains sample counts/stride, alpha coverage and weighted
luminance quantiles. Alpha >= 90 coverage is diagnostic and does not replace a
mesh's actual alpha-blend/test state.

The representative fur colour equally weights the seven per-texture linear RGB
means, then converts that result back to normalized sRGB. This is not UV-area
weighting or a prediction of game lighting. The two `body`/`head` undercoat images
are measured separately: they also paint coat, and are not a biological skin
mask. No automatic selector or aesthetic calibration is implemented in Python.

The deterministic runtime XML uses the existing native pugixml boundary:

```xml
<CoatLibrary schemaVersion="1" id="elegant-2k-2.1" sourceArchiveSha256="...">
  <Surfaces>
    <Surface name="body" texture="body.dds" group="undercoat" />
    <!-- exactly 12 named body/head/fur/blend surfaces -->
  </Surfaces>
  <Patterns>
    <Pattern id="amber" label="Amber" furR="..." furG="..." furB="...">
      <Texture name="body.dds" path="textures/.../amber/body.dds"
               bytes="4194452" sha256="..." />
      <!-- exactly nine diffuse files -->
    </Pattern>
  </Patterns>
</CoatLibrary>
```

`furR/G/B` are all present or all absent. They are emitted only when all seven
fur textures have real alpha-visible measurements whose source hashes match the
validated manifest. The JSON remains the detailed provenance record. This XML
contains 34 palettes and 12 explicit material-group surface mappings; both sexes
share the same texture palette. The game adapter must still validate the actual
loaded shapes, privately own the texture/material objects, load/bind textures on
the game thread and handle actor/root lifecycle and later writers. Preparing
files establishes none of those runtime or visual acceptance claims.

## Game adapter

The development DLL reads `Data/SKSE/Plugins/CLAW/CoatLibrary.xml` once during
startup. Without this optional catalog, the existing human skin/hair tint remains
available when no policy changes that behavior. It separately reads
`CoatPolicy.xml`; the bundled policy defaults to original texture colours, with
skin/hair tint opt-in via `tintMode="linked"`. The comparison plugin's untextured
preview does not establish the game's material output.

The policy has six hair pools (`dark`, `dark-brown`, `brown`, `red-gold`, `grey`,
`light`). Real hair chooses the pool containing the nearest eligible measured fur
colour in linear RGB; a stable saved-reference selector chooses a marking within
that pool. Rendered hair takes precedence when unambiguous, with record-hair
fallback. The 32-pattern `natural` fallback covers absent/unreadable human hair.
Hyena Spotted and Khajiit remain manual-only; all 34 patterns are explicitly
selectable. Known skin remains independent for opt-in linked tint. Neither
material groups nor this technical colour metric establish biological pixel
masks or artistic colour matching.

The native `CLAWDistributionNative` Papyrus interface provides:

```text
String[] GetCoatPatterns()
Bool SetCoatPattern(Actor target, String patternId)
Bool ClearCoatPattern(Actor target)
String GetCoatPattern(Actor target)
String GetAppliedCoatPattern(Actor target)
String GetCoatPatternStatus(Actor target)
```

Use a fully qualified ID returned by the catalog, for example
`elegant-2k-2.1/timber`. Setting or clearing returns admission to the actor-pinned
game-thread queue; `true` does not mean the material has been applied. The first
getter returns the requested override, while `GetAppliedCoatPattern` returns the
last successfully bound pattern ID, or empty. Status explains pending, unavailable,
fallback or yielded application. These reads are cached diagnostics from CLAW,
not independent renderer measurements.

An explicit choice overrides automatic selection. Clearing it returns to the
configured hair or fallback policy, preserving its automatic caches. A source-less
beast uses neutral material multipliers and never gains fabricated human hair,
skin or facial values. The seed uses the Distribution save namespace and persistent
actor identity, not its runtime FormID or shared NPC base. Source arrival/removal
selects the appropriate saved hair/fallback choice. An absent policy retains the
older nearest-hair/linked-tint behavior; invalid policy disables automatic
selection rather than broadening its pools.

Before first use, the adapter checks all nine loose DDS files through the current
Data view for expected byte size and valid dimensions/header. The preparation
tool verifies the hashes; the game does not rehash all textures every scan.
The engine-loaded resource must also report the expected dimensions. Private
texture sets copy all nine original slots and replace diffuse only. Normal and
specular resources, alpha properties, eyes, mouth and claws retain their existing
resources. All selected surfaces are prepared before the live binding transaction.

The surface lease retains material, guard, texture-set and diffuse-resource
identities plus all texture paths. A later material writer wins; clear/return
does not restore over its changes. Separate bounded `CCPT` version-1 records keep
only explicit IDs and actor/base/sex identity. Additive bounded `CCAS` version-1
records store the seed, Distribution identity and separate automatic hair/fallback
choices. Actor/base FormIDs are remapped on load and the seed/identity must match
the owning Distribution state. Existing `CCLR` colour and `CCPT` choice layouts
remain unchanged. Invalid or unavailable patterns preserve original material or
eligible tint with a diagnostic; missing files are not accepted as applied.

The earlier runtime extension passed universal compilation and offline tests.
The 1 November game11 checked automatic Valley Brown, explicit
Black/Timber on both sexes, same-base per-reference isolation, invalid choices,
clear, model refresh, six-reference save/load and the control's human return.
Independent saved-byte checks verified the real source palette and explicit
pattern records; owner Steam images show simultaneous different coats. After
functional completion the process exited abnormally before the operator's finish
request. Environment restoration completed, but the overall run is not marked
passed and the termination cause is unknown. These checks cover the installed
SE candidate, not all runtimes, all patterns, every visible surface or artistic
colour matching. Preparing the library alone establishes none of this runtime
coverage. See the [remaining variation and release plan](coat-variation-plan.md).
The 0.8.5 pools, original-colour default, automatic fallback and CCAS record are
new source mechanisms and are not qualified by that earlier game run.

## Source and verification boundaries

Pure schema/path/metadata/XML functions are separate from `SevenZipArchive`, the
encapsulated external-reader adapter, and the explicit filesystem preparation.
Tests cover traversal/ADS/Windows aliases, collisions, missing/extra files,
unqualified versions/hash, truncation/order/CRC failures, source tampering,
Spirit's mapping, strict runtime XML, transparent/partial-alpha sampling and
absence of invented RGB. Full-library verification and actual DDS measurements
are separate integration evidence; synthetic unit pixels are not called Elegant
measurements. Generated libraries, reports, catalog XML and archives stay outside
Git; authored policy and inventory source remain tracked separately.

## Authored source and donor rights

Copyright (c) 2026 CLAW contributors. These authored helper/test sources follow
the repository's applicable terms. No blanket licence grant is introduced here,
and no new texture redistribution permission is asserted.

Original Elegant textures remain credited to Wolflady500 and KaienHash and are
subject to their original terms. A repository-only mesh permission does not
replace the separate runtime reuse terms. Current source patches contain no
generated texture, library ZIP or texture pixel. The 0.8.5 runtime packaging candidate
uses the complete texture bundle and a normal archive installation while keeping
Elegant's Nexus requirement and credits. This documents the owner's packaging
decision; it does not waive the donor's original reuse conditions or claim a new
permission grant.
