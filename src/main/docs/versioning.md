# Source, resources and generated artifacts

CLAW follows the owner's source-only rule. File role determines what is maintained:
an original binary resource can be source; a generated text report or source ZIP
is still output.

| Content | Location | Version control |
| --- | --- | --- |
| C++, Python, Papyrus and maintained documentation | `src/main/` | Source |
| Recipes, matrices, Spriggit YAML, presets and publication source | `src/main/resources/` | Source |
| Authoritative donor meshes and other authored binary inputs | `src/main/resources/` | Source, with origin/hash/licence; LFS where configured |
| Unit/integration tests, fixture source, test actors/scenes and inspection configuration | `src/test/` | Source, included on `main` |
| Generated NIF/TRI variants, DLL/PEX/ESP, archives, dependency/build trees and reports | ignored `target/` or configured external directory | Output, never Git or LFS |
| Machine paths, credentials, live saves/session bindings and raw captures | Local/external storage | Never Git |

## Binary inputs

An authored binary resource is an input only when maintained sources cannot
regenerate it. Keep it inside the resource hierarchy and identify its author,
origin/version or hash, permission and purpose. The original Elegant meshes and
XP32 skeleton have their [provenance record](../resources/donors/README.md).

Do not classify a generated body as an original input merely to retain a tested
copy. A recipe-produced NIF/TRI belongs in output; maintain its donor, recipe and
producer instructions. Do not commit DLL, PEX, compiled ESP or ZIP through LFS.
LFS stores permitted source resources; it does not change this boundary.

## Text plugins and tests

Runtime plugin YAML lives in `src/main/resources/plugins/`; fixture plugin YAML
lives in `src/test/resources/plugins/`. Spriggit compiles them into ignored output.
Its record roundtrip compares content, separately from header serialization.
Papyrus source is PSC, with PEX generated during the build.

There is one `src/test/` hierarchy for C++/Python tests, Papyrus fixture source and
reusable inspection assets. The working installer must not depend on those
fixtures. An optional `test_` archive is generated separately.

## Releases and branches

Release source, recipes, maintained publication records and reusable test source
reach `main`. One active development branch starts from latest released `main`;
obsolete task branches are retired after fresh remote, unique-commit and worktree
checks. Preserve historical tags and release assets.

An immutable release record identifies source commit, tool/dependency pins,
archive/member hashes and actual validation. Generated archives are published
as release assets or distribution-site files. Source reorganization does not
reproduce or requalify an existing archive. The fresh donor pipeline now reproduces
all six body destinations of 0.7 bytewise with Steam Blender 5.2.3; this is a
body-build result, separate from archive/native/game acceptance. See
[rebuild.md](rebuild.md).

Earlier releases kept generated reference sets in Git/LFS. That policy is
superseded for the current tree; its description remains in the pinned
[historical versioning record](https://github.com/Vhodnoylogin/claw/blob/53e8f3872533f193483a4ee683d3bece1fe3eafa/docs/versioning.md).
Removing generated products from the current tree does not require deleting
tags or rewriting history.

Use [release-workflow.md](release-workflow.md) for archive review, Nexus metadata,
publication state and bounded cleanup after restoration.
