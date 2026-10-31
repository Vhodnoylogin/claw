# CLAW — Configurable Lycanthrope Anatomy and Weight

**CLAW 0.7.0.0** connects ordinary human body morphs to male and female werewolf
bodies. A lean, athletic or heavy human drives a corresponding beast through the
included coefficient/function conversion preset. Its body-family matrices cover
**HIMBO**, **CBBE** and **CBBE+3BA**. Optional OBody integration supplies ordinary
human preset inputs to eligible actors first encountered as wolves.

The working mod is one FOMOD archive, installed as
**CLAW - Configurable Lycanthrope Anatomy and Weight**. It includes the bodies,
28 male/29 female named morphs, one CommonLib runtime DLL, conversion data and the
optional OBody source host. It does not install human bodies, textures, skeletons,
test actors, physics configuration or a first-person VR body.

See [release contents and verification](release/CLAW-0.7.0.0.md),
[installation notes](release/working-installer/README.md) and the
[nonshipping test configuration](test/README.md).

## Requirements and installation

Install each dependency as its own mod: HIMBO male bodies and CBBE female bodies
are required; 3BA is an optional CBBE extension. Build human bodies with working
morph data according to the selected body's and OBody's instructions. Vanilla
human bodies remain in the backlog.

CLAW is derived from Elegant Werewolf Replacer and supplies its own modified
meshes. **Elegant remains required for textures**; its original body meshes do
not need to win. Keep a compatible XP32 skeleton, runtime-matched SKSE,
RaceMenu/SKEE, Address Library and Microsoft Visual C++ x64 runtime installed.
OBody and its complete dependency chain are required for automatic human preset
distribution and the optional originally-beast source host.

Choose HIMBO+CBBE or HIMBO+CBBE+3BA in the installer. Active body plugin markers
provide recommendations, not proof of the effective body meshes. Reinstall the
matching conversion after a body-family change. Existing saved actor matrices
remain authoritative until explicitly rebound; updates do not overwrite custom
co-save profiles silently.

## What has been checked

The exact universal DLL and body resources passed the
[31 October SE mechanism checks](docs/verification-20261031.md): both sexes,
six human presets, transformation and return, source preservation, save/load and
actors created directly as wolves. The owner subsequently confirmed visible
variation across all six presets in the textured game scene.

One CommonLib DLL targets the declared SE, AE and VR boundaries. Actual current
game acceptance is **Skyrim SE 1.7.104.0 / SKSE 2.3.1 with HIMBO/3BA** and official
RaceMenu. Other runtime boundaries and CBBE retain offline rather than equivalent
engine coverage. Read [the runtime contract](docs/universal-runtime.md).

Each sex still uses identical neutral `_0`/`_1` geometry. Leaner and larger forms
come from the authored morph fields. Female breast naturalness, further shape
quality, head/ear/tail/claw relationships and fur colour remain future work;
physics, fitted colliders and a first-person VR body are not shipped here.
The [roadmap](docs/roadmap.md) records those priorities.

## Authoring and repository

The [matrix contract](docs/matrix-contract.md) defines coefficient/function wolf
presets. The game and the [paired Morphbench plugin](tools/morphbench-addon/README.md)
use one C++ evaluator; an all-constant custom matrix defines an independent wolf.
The separate Morphbench plugin is an authoring tool, not a game dependency or a
second artistic preset pack. See [body authoring](docs/expressive-body.md),
[human/beast linkage](docs/transformation.md) and [rebuilding](docs/rebuild.md).

Canonical repository: [Vhodnoylogin/claw](https://github.com/Vhodnoylogin/claw).
Released work and the portable `test/` kit belong on `main`; subsequent unfinished
work belongs on a development branch. Follow [the default release workflow](docs/release-workflow.md).
Sources begin at the root. Configure ignored `build.local.json` for local builds.

CLAW stands for **Configurable Lycanthrope Anatomy and Weight**. Donor credits
and permissions are recorded in [assets/donors/README.md](assets/donors/README.md).
The historical Nexus 0.6.2.0 base-only and 30 October technical Git release remain
separate historical artifacts; their old limits do not describe 0.7.0.0.

*Эта страница на русском: [README.ru.md](README.ru.md).*

## Layout

    recipes\     sliders and builds described in JSON - what to stretch, along which bones, by how much
    plugins\     plugin SOURCES: a .yaml tree, one file per record - laid out by Spriggit
    scripts\     building and packaging for this mod specifically
    release\     what goes out: mod descriptions in both languages and the release manifest
    docs\        how it works and why
    work\        unpacked and intermediate files, outside the repository, reproducible
    assets\      donor meshes and built plugins - in the repository through Git LFS
    tests\       test fixtures and authoring inputs; the separate test_CLAW archive uses selected data
    dist\        release archives, outside the repository

**Binary files are versioned through Git LFS regardless of weight.** Git stores a full copy of
a binary file on every change and shows no diff, so an eight-hundred-byte plugin harms the
history the same way a two-megabyte mesh does — just more slowly. Size is beside the point.
The rule and the extension list live in `.gitattributes` at the repository root; what is stored
when, and why the release set goes in on release rather than on every build, is in
[docs/versioning.md](docs/versioning.md).

**A plugin has two representations, and they are not interchangeable.** The source is **text**
in `plugins\<name>\`: a `.yaml` tree, one file per record. It is edited by hand, read in diffs
and merged. The product is the `.esp` in `assets\plugins\`, kept in LFS so the mod builds on a
machine without Spriggit. One is made from the other:

    python scripts/plugin.py build     text -> .esp
    python scripts/plugin.py dump      .esp -> text
    python scripts/plugin.py check     build into a temp folder and compare text to text

`check` compares **text, not bytes**. Spriggit rewrites the plugin header its own way on the
way back — record count, next free id — so a byte-for-byte match never happens and is not
needed: what matters is the content of the records.

## How it is built

The bodies and morphs are built from `recipes/build.json` and the recipes its steps refer to.
Pinned donor meshes and plugins are kept in `assets/` through Git LFS; intermediate builds
stay outside version control.

Everything builds with one command from the module folder:

    python scripts/build-all.py

It walks the journal step by step, builds into a separate folder, **compares the result against
what is in the mod** — by content, not by checksum — and writes a manifest next to it: which
sources and which recipe commit it was built from.

**To rebuild the mod, read [docs/rebuild.md](docs/rebuild.md):** which sources to start from
(two third-party mods, three files pinned by checksums), what must be installed, how to run the
journal, what the comparison's answer means, and how to add your own step.

The history of journal edits is the git history: `git log -p recipes/build.json`.

## How it is released

The current working installer is produced by `scripts/build-working-release.py`.
It requires HIMBO plus CBBE or CBBE+3BA and installs the same tested native/body
payload for every applicable selection. The optional originally-beast OBody
source host is part of this one working archive. The portable nonshipping
[test kit](test/README.md) belongs to `main/test/` and remains separate.

Use [the release workflow](docs/release-workflow.md): released source and reference
payloads belong on `main`, new backlog development starts on a separate branch,
and task-owned temporary outputs are cleaned after publication and restoration.
The [0.7.0.0 release record](release/CLAW-0.7.0.0.md) identifies the final archive.
Packaging itself neither installs nor publishes a release.

The historical family-version packaging workflow remains:

    python scripts/release.py [--list]

The script checks that what is built is fit to ship — family version against every mod's
`meta.ini`, the manifest present and of the same version, every comparison matched, the recipe
tree clean and at the branch's current commit — and only then packs the archives, putting the
descriptions from `release\` inside each one. The script itself never ends up in the archive.

Shared tooling lives in the project's `tools\` branch and owns no mod: NIF parsing, morph
building through Blender and PyNifly, measurements, rendering. Here there are only descriptions
of what to build.

A hard requirement for any work with PyNifly: **Blender's interface must be in English.**
PyNifly looks up the material node by the name `"Material Output"`, and with a Russian interface
it silently loses both the shader and every transparency block.

## Rights

CLAW ships modified body meshes and morph files, and requires Elegant's texture
files. It does not ship Elegant textures or replace their installation. The donor
permission and its limits are recorded in [assets/donors/README.md](assets/donors/README.md).
Credit Wolflady500 and KaienHash when describing the donor work.

## Development assistance

Developed with assistance from [Codex (OpenAI)](https://github.com/codex).
