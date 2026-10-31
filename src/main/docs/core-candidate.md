# Reproducible linked SE core candidate

This records the **30 October technical baseline**, before the universal 0.7
package. Its original [source snapshot](https://github.com/Vhodnoylogin/claw/tree/53e8f3872533f193483a4ee683d3bece1fe3eafa)
and game receipts remain historical. Commands below name relocated replay helpers
and require separately supplied reference inputs under ignored `target/`; those
inputs are not maintained release binaries in Git. The current clean-source donor
pipeline separately reproduced the six 0.7 body destinations; use
[rebuild.md](rebuild.md) for that result and its boundary from this older archive.

The frozen surface source is `src/main/resources/recipes/surface-repair-v1.json`. It is **baked
authoring data**: explicit sculpted vertex coordinates, packed frames, skin weights,
spheres and named TRIP fields relative to the permanent published0.6.2.0 inputs.
It does not claim to procedurally reconstruct every historical sculpt experiment.
The source contains no game paths and needs neither Blender nor temporary build
folders. `surface_edits.py` permits only the declared data categories; topology,
UVs, bind transforms, node inventory and shader/material blocks remain protected.
Both input and exact output identities are checked before a result is accepted.
The male NIFs remain byte-identical. The female source includes the earlier collar
weight repairs as well as breast006; it is not merely a new breast TRI.

Build six surface resources into a **new external** directory:

```text
python src/main/python/build-tools/build-surface-repair.py --out <new-external-surface-folder>
```

This needs Python and numpy; the strict packed adapters are existing repository
code. Real-asset replay tests reproduce all six game-tested hashes. Per-sex `_0`
and `_1` remain equal. One existing female `fur_chest/WaistNarrow` record is
explicitly removed by the inherited authored repair; the complete public morph
inventory remains unchanged. The recipe makes this visible rather than claiming
every per-shape field is preserved from the published base.

Build separate minimal base and Distribution archives:

```text
python src/main/python/build-tools/build-core-candidate.py --external-inputs <local-inputs.json> --out <new-external-package-folder>
```

`src/main/resources/publication/core-input-hashes.json` fixes the reviewed native build, exact native
corresponding-source archive, own compiled declarations/source-host files and
license notices. The local inputs document supplies paths with `path`, `bytes`
and `sha256`; it stays outside Git. Native code is unchanged from078510a and the
DLL is16543ae9ef459599bb02fd912d6ab70fe8af4155fa821a6b1a56e440bfbf6e92.
The corresponding-source archive remains a separate source download, not an
installed runtime component. The current repository supplies the surface recipe,
mapping and packaging source. This exact DLL targets SE1.7.104 only.

The base has seven runtime files plus two short language guides. Distribution
has one own DLL and its native declaration, two selectable mapping variants and
an optional OBody source-host plugin/script. The FOMOD selects HIMBO with CBBE or
3BA; each variant retains all measured rules and declares exactly one male and
female default. The host is offered only with active OBody.esp. No wolf presets,
UIExtensions menu plugin/script, human bodies/presets, skeleton, textures, physics
configuration, VR body, test actors or debugging executables are shipped.
Dependency notices are retained even though they do not affect game behavior.

The builder checks exact archive/member bytes and inventory. It writes a separate
build manifest outside the installable archives. It never installs or publishes.
Candidate packaging is not owner visual acceptance. Current quality limits
include residual fur/skin continuity and weak slimming response. The current
runtime set passed core117 and born33 in actual SE, both with normal exit 0 and
verified restoration. Earlier shutdown failures remain historical evidence; these
two results do not establish universal exit reliability. See
[verification scope](verification-20261030.md). Documentation-only repackaging
must preserve every verified runtime hash and does not create a new gameplay test.
