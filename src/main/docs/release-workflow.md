# Release, source layout and development branches

This is the owner's default CLAW workflow. The shared repository standard is
[published separately](https://github.com/Vhodnoylogin/ai-project-meta/blob/55e5087852e6ac9c5037b3aeccb3812fa617e7eb/infrastructure/admin/knowledge/release-branches.md).

## Source and ownership

Maintain production source and authored resources in `src/main/`; maintain all
unit/integration tests, actor/scene source, presets and inspection configuration
in `src/test/`. Include both trees on `main`. This replaces the former root
`test/` and `tests/` split. Keep generated files in ignored `target/` or an
explicit external build directory. DLL, PEX, compiled ESP, reproducible NIF/TRI,
ZIPs and build reports are output, not source; LFS does not change that boundary.
Binary source resources need origin/hash/licence records within the hierarchy.
See [versioning.md](versioning.md).

The independent [Morphbench comparison plugin](https://github.com/Vhodnoylogin/claw-morphbench-plugin)
has its own repository and release. CLAW owns the shared C++ matrix kernel;
consumers use an explicit pinned dependency rather than a copied implementation.
Do not put another product's source back into this tree for convenience.

## Build and release correspondence

Build from a known source commit with pinned donors, tools and dependencies.
Keep the build recipe, compile/packaging code and reusable tests in source.
Record selected input identities and generated member/archive hashes outside the
installable runtime payload, with maintained publication facts linked to the
matching source commit. Do not label an archived reference set as a fresh build.
The reorganized donor pipeline passed its strict Blender/body checks and
reproduced all six 0.7 body destinations; [rebuild.md](rebuild.md) records that
scope. Native/archive acceptance remains a separate check. Old gameplay
acceptance applies to its exact original runtime set.

Prepare one complete working CLAW archive and, when useful, a separate optional
`test_` archive. The working archive contains ready runtime/install files,
required copyright/licence notices and brief user instructions only. Keep
developer source bundles, build instructions/toolchains and test fixtures out
of it. Publish matching source and rebuild instructions on GitHub, with an exact
source reference and any required source-availability notices; necessary
interpreted runtime code remains runtime content.

Keep dependencies installed as separate mods with the full
transitive requirement chain. Validate the actual ZIP and serialized FOMOD for
every supported choice: required destinations, duplicate-source copies, licences,
matching source delivery where required and minimality. Exclude test actors,
physics/VR experiments, tools, backups and unrelated donor material from the
working installer. Verify the selected files and manager accounting when
installation is in scope. Packaging alone does not install or test the mod.

Publish generated archives as GitHub Release assets or distribution-site files,
not inside Git/LFS. Preserve historical release assets and tags. A new source
layout does not retroactively alter or requalify those archives.

## Main and one development branch

Before integration verify the remote is `Vhodnoylogin/claw`, preserve all work
and check existing worktree ownership. Release source, resources, documentation
and reusable `src/test/` content reach `main`, directly or through a reviewed PR.
A tag or uploaded archive alone is not source integration.

Use one active development branch based on latest released `main` for unfinished
backlog work. Remove obsolete task branches only after fresh remote, unique-commit
and worktree checks establish preservation. Do not create another release branch
for an already-main state. Keep protected/upstream/service branches when required;
never reset or remove another checkout merely to simplify the branch list.

## Page and file publication

Prepare description, file text, changelog, requirements and approved screenshots
before uploading. Keep technical details in the final spoiler and linked author
credits last. Respect the owner's gallery and formatting decisions. On Nexus use
a descriptive version-free public file display name and its separate version
field. Local archive filenames may retain a version for immutable provenance.

Apply the prepared content only within the owner's publication authority, then
verify public file/page identities and actual download availability. Uploaded,
quarantined, reviewed and downloadable are different states. Preserve the source
commit and archive hash, actual runtime coverage and remaining limitations.
A universal CommonLib build does not itself prove equivalent SE/AE/VR engine
acceptance. Never bypass scanner review by repeatedly reuploading the same file.

## Cleanup

After preserving source and reusable tests and completing the relevant work or
publication, inventory exact task-owned temporary files. Resolve every deletion
target inside the intended staging directory. Retain the final archive, necessary
input/rollback material, provenance and evidence. Owner screenshot originals and
unrelated mods or checkouts are not temporary files.

For game tests, exit through the game menu and verify native plus separately held
optional restoration before cleaning their session files. Active workers, live
profiles, saves, command databases and custody remain protected. An unresolved
restoration or publication issue delays affected cleanup. Record what was removed;
never fabricate completion or bypass a hold to make an inventory executable.
