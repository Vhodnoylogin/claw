# CLAW — Configurable Lycanthrope Anatomy and Weight

A werewolf body with named morphs and distinct male/female shapes. The nearest release
uses each sex's low-weight (`_0`) shape at both weight endpoints; weight-dependent
geometry and the optional Anatomy add-on are deferred. An add-on to **Elegant Werewolf Replacer** — nothing here builds or works without it.

*Эта страница на русском: [README.ru.md](README.ru.md).*

Canonical repository: [Vhodnoylogin/claw](https://github.com/Vhodnoylogin/claw), branch
`main`. Sources start at the repository root. For a standalone build, configure the
ignored `build.local.json` as described in [docs/rebuild.md](docs/rebuild.md).

## The name

`CLAW` stands for **Configurable Lycanthrope Anatomy and Weight** — after the two mechanisms
everything rests on: anatomy is set by morphs, mass by weight. The trick is the same one CBBE
(Caliente's Beautiful Bodies Enhancer) and HIMBO (Highly Improved Male Body Overhaul) use:
an ordinary name whose initials spell a fitting word.

**`CLAW` is the prefix of the whole family.** Only the base mod carries the full expansion;
the others go by the short name and still read as one group and sit together in the list:

| Mod in MO2 | What it carries |
|---|---|
| `CLAW - Configurable Lycanthrope Anatomy and Weight` | bodies of both sexes with identical low/high weight endpoints per sex, a morph file **without adult sliders**, and a plugin with the weight slider and the female model |
| `CLAW - Anatomy` | the adult add-on: **morph files only**, five megabytes |
| `CLAW - VR` | what only makes sense in a headset: dense capsules for the hands, a beast body for the player, HIGGS, PLANCK and swinging-physics settings |

**The nearest release is the base mod only.** `CLAW - Anatomy` and `CLAW - VR` are
deferred and do not gate base acceptance. Version 0.6.2.0 retains both weight filenames
for compatibility, with the same `_0` shape at every weight for each sex. Named morphs
remain supported. This does not establish untested platform or physics compatibility.

Two more folders sit next to these in the setup, and neither belongs to the family:

| Folder in MO2 | What it actually is |
|---|---|
| `test_CLAW - Companion` | a **test mod**, not part of any release: it provides the only she-werewolf in the setup, the one the female body is checked on. Lives in `tests\`, never ships, removed after a run |
| `CLAW - OBody Presets` | **not a mod yet**: four slider sets kept in a folder so they don't get lost. There is no deliberate thing with a purpose, a name and boundaries here so far |

The difference is not size but responsibility: a released mod answers to the player, a test mod
only to us, and a draft answers to no one.

The split between the base and adult versions is made **by the morph file, not by geometry**:
the geometry is identical, but the base version's morph file has no crotch sliders at all, so
there is nothing to raise them with.

And that geometry sits **entirely under the skin** at rest: 27 of the 442 sheath vertices and
50 of the 444 scrotum vertices stay outside, and those are the rim seam, which has to lie on
the surface or there would be a hole in its place. So without the adult add-on the content
does not exist in game — not "hidden for now", but literally unreachable.

Why not cut it by geometry: the shape lives **inside** the body file, and a mod manager
overrides whole files. You cannot add a shape to someone else's mesh, so "adult geometry
separately" would mean a second copy of all four bodies — thirty-four megabytes for eight
hundred vertices. There is one real alternative: make the anatomy a wearable item, the way SOS
and ABC do; their mesh weighs fifty kilobytes. That is a goal, not today.

## What it is, and what it is not

Elegant provides the look: one mesh per sex, beautiful and dense. What it does not provide is
**anything adjustable** — no male weight pair, a female pair that is byte-identical, not a
single morph file, no anatomy. On top of that, the game's own werewolf armor record has the
weight slider disabled, and the female model points at the male mesh.

`CLAW` builds from the pinned Elegant donor meshes. The built package carries modified bodies
and morph files; Elegant remains required for the textures. See [assets/donors/README.md](assets/donors/README.md)
for the donor permission and its limits.

## Layout

    recipes\     sliders and builds described in JSON - what to stretch, along which bones, by how much
    plugins\     plugin SOURCES: a .yaml tree, one file per record - laid out by Spriggit
    scripts\     building and packaging for this mod specifically
    release\     what goes out: mod descriptions in both languages and the release manifest
    docs\        how it works and why
    work\        unpacked and intermediate files, outside the repository, reproducible
    assets\      donor meshes and built plugins - in the repository through Git LFS
    tests\       test material: mods and plugins that never ship
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

The author of Elegant (Wolflady500, KaienHash) permits using the models and textures in another
mod as long as it is not sold, and asks that it not make their mod redundant. Hence the design:
we ship the difference, not the mesh, and without Elegant our mod does not work. Both names are
mandatory in the description.
