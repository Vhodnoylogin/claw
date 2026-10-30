# CLAW — Configurable Lycanthrope Anatomy and Weight

The [30 October SE core Git baseline](release/SE-Core-20261030.md) freezes the
tested Base and Distribution payloads after the owner's paired game inspection.
Human-driven linkage works; visible contrast is still modest. Stronger thin and
bulky endpoints, breast shape, fur colour and physics are the next development
work. This checkpoint does not publish another Nexus release.

A werewolf body with named morphs and distinct male/female shapes. The first release
uses each sex's low-weight (`_0`) shape at both weight endpoints. Distinct weight
endpoints are now in development; the optional Anatomy add-on remains deferred.
CLAW derives from **Elegant Werewolf Replacer** and supplies its own replacement
body meshes. The current runtime package still requires Elegant's texture files;
its original body meshes are not needed at runtime. The original donor meshes
remain pinned inputs for rebuilding CLAW. Inclusion of our changes in Elegant is
not required for CLAW to develop as a separate mod.

The first published release is **resources for modders**: meshes, named morphs and
the base plugin. OBody integration and automatic body distribution are planned for
later releases. The packaged [resource contract and NiOverride example](release/CLAW.en.md)
document the files, morph names and integration responsibilities.

See the [future plans](docs/roadmap.md) for collider alignment, ear and breast
physics, colliders that follow morphs, seam repairs, OBody or equivalent support,
a first-person VR body, and the separate adult anatomy/physics add-on.

Post-release development starts with an [offline distribution core](docs/distribution.md)
and [measured collider candidates](docs/colliders.md). Automatic population variety
is the primary goal: ordinary human presets must determine the wolf through
morph-to-morph conversion, without requiring wolf presets. Geometry repair,
ear/tail and breast physics, morph-responsive colliders and the transformation
link proceed alongside the explicitly requested distinct weight endpoints.
On 28 October the owner resumed parallel physics, first-person VR body and
morph-quality development. The prepared flat-game OBody test remains separate.
The optional [typed preset companion and authoring resources](docs/presets.md)
are development candidates; runtime acceptance is pending.
The native [human/beast morph link](docs/transformation.md) derives a beast morph
vector from actual applied human coefficients. Linked actors use ordinary human
presets; there are no separate wolf presets in this path. Real SE checks have
exercised six human actors of both sexes, transformations and returns, source
preservation, save/load and two actors created directly as wolves. Numeric
conversion is working; visible proportional quality remains under development.
Measured CBBE/3BA/HIMBO resource-family conversions are development data. The older
exact preset-pairing experiment is historical.
The nearest functional SE release now prioritizes stable linkage on the published
0.6.2.0 bodies with the official installed RaceMenu. The current development
configuration passed the later core117 checks and the owner's six-actor manual
transformations. The earlier transformation failure remains retained evidence,
not the current result. The manual inspection rejected weak visual contrast and
female breast/underarm geometry. A silent shutdown exception was also reproduced
without the Distribution DLL and integration plugin; it is not established as a
CLAW-specific fault. A separate RaceMenu repair is not a required CLAW dependency.
New body geometry, physics and VR remain separate trials.
The selected breast/axilla and male collar edits now have a [reproducible baked
authoring recipe and minimal linked-SE candidate builder](docs/core-candidate.md).
They reproduce the exact repaired-surface trial inputs; final owner visual
assessment found modest contrast, while core117 and born33 passed on the final
frozen runtime. The [next range plan](docs/morph-range-plan.md) addresses lean
minima, bulky maxima and the actual paired game measurements.
The [ear/tail physics source candidate](physics/README.md) uses existing XP32
chains, an optional finite per-actor host and explicit provider qualification.
A native observer follows actual effective morphs and NPC weight, refits capsules
on a bounded worker, and rejects stale results before publication. Actual provider
ownership, close contact and game behavior remain unqualified.
The [breast rig](docs/breast-rig.md) includes a separate layer-only fur motion
experiment. [First-person VR body resources](docs/vr-body.md) are in development.
Anatomical head/torso separation and a names-only XP32
alias compatibility candidate are implemented offline; engine integration and camera/interaction acceptance
remain pending. [Additional human-driven morphs](docs/morph-expansion.md) and
[Morphbench improvements](docs/morphbench-needs.md) are researched proposals.
The [morph-quality audit](docs/morph-expansion.md#reproducible-static-quality-audit) measures
actual serialized fields, fixed boundary pairs and finite morph combinations.
An opt-in male WaistNarrow collar repair is staged separately; rendered seams,
fur coupling and resource rebinding remain acceptance requirements.
The first-person Neck attachment candidate removes the visible torso's Head-local
coupling using existing XP32 bones, and can be composed with that collar repair.
An optional female right-ear partition trial improves measured whole-union samples
but retains regional tradeoffs; the default physics model is unchanged. Both
stages remain offline development resources with separate runtime gates.

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

| Component | Scope |
|---|---|
| `CLAW - Configurable Lycanthrope Anatomy and Weight` | bodies of both sexes with identical low/high weight endpoints per sex, a morph file **without adult sliders**, and a plugin with the weight slider and the female model |
| `CLAW - Distribution` | development candidate: human morph linkage without beast presets; optional legacy independent assignment; game acceptance pending |
| `CLAW - Anatomy` | the adult add-on: **morph files only**, five megabytes |
| `CLAW - VR` | what only makes sense in a headset: dense capsules for the hands, a beast body for the player, HIGGS, PLANCK and swinging-physics settings |

**Published 0.6.2.0 contains the base mod only.** Distribution is a separate development
candidate; `CLAW - Anatomy` and `CLAW - VR` are deferred. Version 0.6.2.0 retains both weight filenames
for compatibility, with the same `_0` shape at every weight for each sex. Named morphs
remain supported. This does not establish untested platform or physics compatibility.

Local test and legacy draft folders are outside the published package:

| Folder in MO2 | What it actually is |
|---|---|
| `test_CLAW - Companion` | a **test mod** providing a female werewolf fixture. Lives in `tests\`, never ships, removed after a run |
| `CLAW - OBody Presets` | historical draft folder; the supported new authoring contract is [typed independent CLAW presets](docs/presets.md), not OBody's human preset pool |

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

CLAW ships modified body meshes and morph files, and requires Elegant's texture
files. It does not ship Elegant textures or replace their installation. The donor
permission and its limits are recorded in [assets/donors/README.md](assets/donors/README.md).
Credit Wolflady500 and KaienHash when describing the donor work.

## Development assistance

Developed with assistance from [Codex (OpenAI)](https://github.com/codex).
