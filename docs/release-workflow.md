# Release, test-kit and development branches

This is the owner's default CLAW release policy, confirmed on 31 October 2026.

## Repository layout and promotion

`main` records the source, recipes, build inputs and release records corresponding
to the published working mod. After content is accepted and prepared, verify the
remote is `Vhodnoylogin/claw`, preserve all existing work, and promote the release
changes to `main`. Check for an existing main worktree before switching branches;
do not reset or remove a retained checkout to bypass its ownership.

Begin subsequent backlog development on one separate branch created from the
latest released `main`. Keep unfinished work there until it is selected, built
and validated for a later release. Do not create extra release branches merely
to mark an already-main state. A release tag or GitHub Release is a publication
record, not a substitute for integrating the corresponding source into `main`.

Nonshipping actor definitions, scene configuration, test presets and inspection
instructions belong in `main/test/`. Programmatic regression tests may remain in
`tests/`; do not duplicate or rename that tree solely for the user-facing test
kit. The working installer must not select either test tree. Keep runtime
instances, machine paths, credentials, tokens, generated logs and raw captures
outside Git. Released binary reference sets follow the repository's existing
Git LFS and manifest rules in [versioning.md](versioning.md).

## Prepare all content before the Nexus update

Build one working CLAW archive with its required FOMOD alternatives and matching
source/licenses. Keep the optional `test_` archive separate. Check minimality,
actual selected file bytes, dependency choices, version labels and provenance.
Every independent dependency remains its own source-accounted mod, with its full
author-declared requirement chain. A CommonLib universal build and an offline
test do not establish game acceptance on every runtime.

Prepare the page description, file description, changelog, requirements and
approved screenshots before changing the public release. Preserve the owner's
formatting choices, keep technical details under the final technical spoiler,
and put linked author credits last. When the owner authorizes upload, apply the
prepared content as one release update and verify the resulting public page and
file identities. Do not upload rejected draft media or test assets as production
content. Record exactly what was published; pending or blocked steps remain
pending rather than being reported as complete.

## Cleanup after publication and restoration

After the release is published and the corresponding source/test configuration
is saved to `main`, inventory the task-owned temporary files. Confirm every
resolved deletion target remains within the explicitly intended CLAW staging
directories. Remove reproducible unpackings, rejected draft outputs, redundant
package reproductions and caches that are no longer used. Record the deletion
inventory and the retained release manifest before removal.

Never clean an active game session's directory, token/database, profile backups,
restoration custody or in-use outputs. Exit through the game menu, await native
restoration, verify any separately held optional components are restored, and
only then clean their no-longer-needed temporary copies. An active worker or an
unresolved restoration prevents cleanup of those files, not the preservation of
finished source and content.

Retain the final release archive and source/manifest record, current reusable
test inputs, necessary original build inputs and the evidence needed to explain
published results. Owner screenshot originals are not temporary draft files.
Do not delete unrelated mods, other chats' staging, legacy repositories or
retained worktrees under a general CLAW cleanup request. If a reusable script or
configuration still exists only in external staging, preserve its portable
source before removing the staging directory.
