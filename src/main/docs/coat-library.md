# Local Elegant pattern library

This tool prepares all 34 coat patterns from the user's existing **Elegant
Werewolf Replacer 2K**, Nexus mod 93336, file 791439, version 2.1. It does not
download, install, enable or publish a mod. The resulting DDS files are local
dependency resources; **never include them in CLAW, Git or a public archive**.
The recorded donor permission covers the two meshes and explicitly excludes
texture redistribution. Original Elegant remains required for shared normal,
specular, eye, claw and mouth resources.

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

## Local preparation

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

The local payload has 306 original diffuse DDS files, 549,498,912 bytes:

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
available. The local library supplies diffuse patterns; Elegant still supplies
the shared remaining textures. The comparison plugin's untextured preview does
not establish the game's material output.

For an observed human hair colour, the automatic selector compares the measured
fur palettes in linear RGB and resolves ties by the stable library/pattern ID.
Rendered hair takes precedence when unambiguous, with the existing record-hair
fallback. Skin continues to control the separate undercoat material tint. This
initial deterministic colour metric is not an artistic colour match or a
biological mask of skin versus hair-covered vertices.

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

An explicit choice overrides automatic selection. Clearing it resumes automatic
selection when human hair was observed. A beast without that history can receive
an explicit pattern with a neutral tint multiplier; it never gains fabricated
human hair, skin or facial values. Clearing such a choice restores its original
material. Choices belong to actor references, not their shared NPC base.

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
only explicit IDs and actor/base/sex identity. Automatic selection is recomputed
from the retained real colour source. Existing `CCLR` version-1 colour records
keep their byte layout. Invalid or unavailable patterns fall back to the original
material or existing tint, with a diagnostic; missing files are not accepted as
a successfully applied pattern.

The runtime extension has passed universal compilation and offline tests. Its
individual-material application, restoration and persistence require the next
pinned game test; preparing this library alone does not qualify those behaviors.

## Source and verification boundaries

Pure schema/path/metadata/XML functions are separate from `SevenZipArchive`, the
encapsulated external-reader adapter, and the explicit filesystem preparation.
Tests cover traversal/ADS/Windows aliases, collisions, missing/extra files,
unqualified versions/hash, truncation/order/CRC failures, source tampering,
Spirit's mapping, strict runtime XML, transparent/partial-alpha sampling and
absence of invented RGB. Full-library verification and actual DDS measurements
are separate integration evidence; synthetic unit pixels are not called Elegant
measurements. Generated libraries, reports, XML and archives stay outside Git.

## Authored source and donor rights

Copyright (c) 2026 CLAW contributors. These authored helper/test sources follow
the repository's applicable terms. No blanket licence grant is introduced here,
and no new texture redistribution permission is asserted.

Original Elegant textures remain credited to Wolflady500 and KaienHash and are
subject to their original terms. Public donor-mesh permission is not texture
redistribution permission. The local library is for the user's installation only;
no generated texture, library ZIP or texture pixel is included in source patches.
