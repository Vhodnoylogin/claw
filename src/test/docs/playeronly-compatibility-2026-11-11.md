# PlayerOnly resource compatibility candidate

This is unfinished development work, not acceptance of a new release. The
published 0.9.0 archive and its dated game evidence remain unchanged.

## Problem and narrow repair

The ordinary Elegant Player Only quest equips an independent slot-32 armor on
the player. Its ARMA loads `MalePlayerWerewolf_1.nif` or
`FemalePlayerWerewolf_1.nif`, with both weight sliders enabled. CLAW previously
installed only the standard `bodywerewolf` model paths. The author's original
PlayerOnly models do not contain the matching CLAW BODYTRI resources.

PlayerOnly also installs player-prefixed body/head/fur/eye diffuse names. Those
files differ from the Main Replacer's unprefixed names. Shared normal maps,
claws and teeth keep their existing paths.

The packager now adapts generated NIF diffuse paths in a pure final resource
stage. It preserves every unrelated block and non-diffuse texture slot, leaves
donors and TRI bytes untouched, and records pre/post hashes and changed blocks.
The serialized FOMOD maps each sex/weight source to both standard and PlayerOnly
destinations. Identical endpoints share an archive member; distinct endpoints
remain distinct. No Elegant artwork is included or copied from an installation.

## Offline evidence

Pinned inputs:

- Published CLAW 0.9.0 ZIP SHA256:
  `f7ae8b52877680eafd3ef9c5c1f3bf1cdf94605e9a69d6d3acabaf2093adcbf8`.
- Elegant Player Only FOMOD 2K 2.1, file 798407, ZIP/7z SHA256:
  `0cec26f8b14a1a91aa8ffc0e14ca80989deda1f5a7d2386d11451af5cf52b0a8`.

The focused package suite passes 23 tests. Four real-artifact integration tests
independently read all eight installed model endpoints through PyNifly, checking
geometry, UVs, skinning, partitions, texture slots and BODYTRI. Existing male
30-morph and female 31-morph TRI data remain unchanged. All 20 family/host
combinations retain exact standard/PlayerOnly endpoint mapping and contain no
DDS. Ordinary Default/Timber/Yellow selection is checked with and without the
Randomized option. This evidence is not game execution or a full source rebuild.

Actual integration inputs are explicit environment variables documented in
`src/test/python/integration/test_player_only_resources.py`; absent resources
fail rather than silently substituting synthetic meshes.

## Remaining gates and dependency exceptions

- Inspect the completed 4K archive independently. The current coat catalog
  records exact 2K randomized DDS byte counts. Different 4K counts would be
  rejected by runtime validation; matching names alone do not prove support.
- The inspected 2K FOMOD has two independent Pattern defects: Khajiit lacks
  `playerhead.dds`, while Spirit installs its nine diffuse files below
  Data-root `Actors/` instead of `Textures/Actors/`. The other 32 Patterns and
  all 28 Eyes choices provide the expected paths. Do not claim every ordinary
  Pattern is supported from the positive Timber test or repair third-party
  installation files silently.
- A Main-only upgrade needs an ordinary PlayerOnly installation before these
  player-prefixed defaults can be used. Final user instructions, dependencies
  and archive README remain a release gate; they are not updated by this draft.
- Freeze a real candidate and test both player sexes with Coop enabled:
  transform, equipped skin/morphs/materials, model refresh, save/load already in
  beast form, human return and second transform. Check ordinary NPC paths,
  weight endpoints/intermediate weight, single-coat mode, all ten randomized
  coats and missing/damaged-coat fallback. Verify the empty authored Model
  Swapper rule wins and only one intended body is visible/equipped.
- First-person models, VR body and physics have separate acceptance. None is
  established by these third-person aliases or the old 0.9.0 runs.

Local audit and derived probe evidence remain outside Git under
`Builds/claw-elegant-playeronly-audit-20261111/`; the independent critique is in
`Builds/claw-playeronly-critic-20261111/`. The derived probe is explicitly an
offline audit artifact, not a release archive or an installed test subject.
