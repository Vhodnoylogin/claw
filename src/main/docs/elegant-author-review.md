# Elegant head/torso author-review source

The separate [author-review prerelease](https://github.com/Vhodnoylogin/claw/releases/tag/review/elegant-head-torso-20261031)
contains an offline donor-only contribution for Wolflady500. It is a developer
review product, not a CLAW working-mod update or an accepted game result. Its
historical tag remains unchanged; the complete maintained source is now on main.

## Canonical implementation and exact export

The split/container/TRI/readback algorithm is maintained in
[`head_split.py`](../python/build-tools/head_split.py). Skinning helpers come from
[`breast_rig.py`](../python/build-tools/breast_rig.py), and head-ancestry/pose
helpers from [`vr_head.py`](../python/build-tools/vr_head.py). There is no second
maintained copy of those implementations.

[`export-elegant-review.py`](../python/build-tools/export-elegant-review.py)
assembles the required definitions and the original donor-only entrypoint into
the self-contained `elegant_head_body_split.py`. Its explicit adaptations remove
the CLAW breast-field diagnostic, classify original donor weights, and exercise
the labelled synthetic verification probe in the controlled pose checks. They
do not add a runtime morph, change a donor vertex, weight or material, or hide a
shape. The original source formatting/newline encoding is preserved so the
result matches the published source file byte for byte:

```text
SHA256 702d89a6e5035bc74afe751b48209d40e5afab7dcac73255f17f08a911c9e089
```

The exporter refuses source drift instead of calling a changed implementation
the already reviewed tool. A new revision needs a new explicit review identity.
Generated source, diagnostic TRI probes, NIFs, index maps, verification reports
and ZIPs belong in ignored `target/` or an external build directory, never Git.

## Inputs and provenance

Only Elegant Werewolf Replacer 2.1's Default male and Female variants are covered.
The female archive endpoints are identical. Other variants are not qualified.
The [donor permission record](../resources/donors/README.md) defines the source
redistribution boundaries; this contribution does not grant a new licence.
No Elegant textures or replacement skeleton are included in the review output.

| Input | SHA256 |
|---|---|
| Default `malebodywerewolf_1.nif` | `22689f28006f21c58f10ca640eb3ea4741fbad00fe3edd4d0d2ed0339a3a2349` |
| Female `_0` / `_1.nif` | `ec9c70bf5ed62fdf481bbfc0aad43c7d8d2e8d0ca90833a323b9b222e437265b` |
| Read-only XP32 `skeleton.nif` | `b64b614d06eb854512ef4a9d6b08777fe0f9580f47d495d20db16dabb9fc2dd0` |

The original archive-member inventory, readback report and deliberate-corruption
results are evidence in the separate review delivery. They are not maintained
source inputs or committed generated fixtures.

## Export and read back

Use Python 3, NumPy and the public PyNifly add-on; the published check used
PyNifly 28.1.0. No Blender process or Skyrim session is needed. From repository
root, choose a new exported file and a new external review directory:

```powershell
python src/main/python/build-tools/export-elegant-review.py --out target/author-review/elegant_head_body_split.py
python target/author-review/elegant_head_body_split.py --male src/main/resources/donors/malebodywerewolf_1.nif --female src/main/resources/donors/femalebodywerewolf_1.nif --skeleton src/main/resources/donors/skeleton.nif --pynifly '<public io_scene_nifly directory>' --out '<NEW_EXTERNAL_REVIEW_DIRECTORY>'
python -m unittest discover -s src/test/python/unit -p test_elegant_review_export.py
```

The generated tool checks the exact donor hashes before output, creates the
split, reads it back through public PyNifly, and writes `verification-report.json`.
It retains all original triangles and material/UV assignments, duplicates only
the seam vertices and verifies packed skin weights, bind transforms, skeleton
hierarchy, independent shader owners and sparse TRI correspondence. Synthetic
`verification-probes/` files exercise remapping and three states under ten head
poses with raw and normalized skinning; they are not linked runtime assets and
must not be installed or included in the mesh handoff.

Published offline evidence reports zero exterior/seam differences from the input
for those finite checks. Independent mutations of one bind and one packed probe
offset were rejected. This does not establish game animation, first-person
visibility, neck coverage or artistic acceptance; retained original Head weights
still have their original influence. Existing reports remain the evidence for
that review run; exporting source alone does not claim a new native readback.
