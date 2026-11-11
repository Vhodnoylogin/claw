# Elegant PlayerOnly 2K/4K technical verification

Scope: source-archive inspection and native DDS admission. The new game DLL and
PlayerOnly route remain pending installed-game qualification. No Elegant images
are included in the CLAW package or this repository.

## Actual source archives

| Player Only FOMOD2.1 | Bytes | SHA256 |
|---|---:|---|
|2K|337370416|`0cec26f8b14a1a91aa8ffc0e14ca80989deda1f5a7d2386d11451af5cf52b0a8`|
|4K|1287728059|`23b104bd26dd219a4c974fba7865c023e1d7cfbf9f4a790a111365dd965c6755`|

The FOMOD, Coop ESP/PEX and eight female NIFs are byte-identical between these
archives. Randomized installs all ten coats at the same separate texture paths.
The managed maps are BC7_UNORM: 2K body/head2048-square and fur1024-square,
one mip; 4K body/head4096-square with13mips and fur2048-square with12mips.
All180 files contain the complete declared payload. The old installed-file-size
comparison rejected all90 valid4K files because it used2K catalog byte counts.

The corrected runtime selects by the configured path. Its actual DDS metadata
determines structural checks; catalog byte counts and digests record provenance,
not an artwork/resolution allowlist. Known BCn/DXT mip payloads are calculated
from the header. Other pixel layouts are delegated to the engine. Every diffuse
must produce an actual renderer resource view, expected dimensions and one array
element; all nine maps must pass before the coat is bound. Partial valid mip
chains and mixed resolutions are permitted. This is not pixel-quality or
arbitrary same-length corruption detection.

An independent MSVC runner using the actual production header accepted180actual
DDS files,20complete coats,10mixed2K/4Kcoats and two noncatalog/partial-mip
layouts. It rejected63missing, malformed, truncated or inconsistent cases, with
zero failures. External evidence: Builds/claw-elegant-4k-audit-20261112/,
including REPORT.md, texture-variant-mapping.json, NATIVE-VALIDATION.md and
native-validation-provenance.json. These results do not execute the engine.

## Remaining route gates

Qualify enabled-Coop player armor and the standard NPC path with the newly
built core, matching BODYTRI and optional FSMP hooks. Read back actual material
bindings for4K, fallback and after model/save-load boundaries. Do not inherit
these checks from the previous published0.9.0 runtime.

Default mesh, Timber coat and Yellow eyes provide a complete static fallback.
The upstream Khajiit choice lacks playerhead.dds and Spirit misroots its pattern
folder.32other Pattern choices and all28 Eyes choices supply expected paths.
No third-party file was changed to conceal those upstream defects.

## Deferred reference inventory

Default/Soft share one female shape; Anubis and Terror supply two further unique
shapes. Each option's _0/_1 files are identical and lack BODYTRI. Their source
hashes, bounds, textures and geometry counts are preserved externally in
female-nif-reference-inventory.json for the later aesthetic stage. No visual
retuning or redistribution follows from this inventory.
