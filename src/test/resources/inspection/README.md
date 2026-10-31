# CLAW inspection kit

This directory is the portable, nonshipping test configuration for CLAW 0.7.0.0.
It belongs on `main` alongside the corresponding released source. It is not part
of the working mod archive. Programmatic checks live in `src/test/python`; older compatible fixtures live
in `src/test/resources/fixtures`. Generated test plugins live under ignored `target/test-assets/plugins`.

## Fixed comparison scene

`scene.json` records the owner-accepted absolute QASmoke positions and stable
`Dragonborn.esm:02A1B9` room marker. Do not anchor the scene to the current player
or camera. There are six pairs, each containing visually identical human twins;
only one twin becomes a wolf after equality of their complete keyed human morph
vectors, body weight, sex, base, face, hair, skin and scale is verified.

| Class | Male pair | Female pair |
| --- | --- | --- |
| Slim | Iney / Иней | Lada / Лада |
| Muscular | Kedr / Кедр | Mira / Мира |
| Heavy | Grom / Гром | Runa / Руна |

Names include `Human` or `Wolf` in the scene tags and spoken aliases. Pair members
stand 110 game units apart; pair pitch is 300, and the male/female rows are 320
units apart. The baseline headings are male 90 degrees and female 270 degrees.
Individual recorded floor heights must be retained.

Establish **AI Off and collision Off before creating any actor**, apply the
explicit locomotion hold, and verify two stable position samples after placement
and transformation. `tai` and `tcl` toggle their state; do not blindly replay
them. Use the existing qualified DevBench/session channel for admitted commands.
Do not expand its allowlist or install files during a manual game session.

`commands.json` defines operator intents and the relative 0/90/180/270-degree
views. It is a contract for an appropriately qualified testing adapter, not an
implemented controller or a list of directly executable console commands. Named
views derive from the immutable baseline; a relative request such as “rotate all
by 90 degrees” derives from current measured headings and executes only once.

## Groups and born-werewolf coverage

The initial group is the twelve paired characters. The six wild wolves appear
**only on an explicit `show wild` operator intent**, after the paired group is
hidden. `show pairs`, `hide pairs`, `show wild` and `hide wild` operate on the
same-run owned registry. Hiding disables references; showing reuses them without
duplicates or a fresh preset roll. These are semantic intents, not claims that
the game itself provides named commands.

Wild NPC sources and their prebuilt plugin already live under
[`../plugins/test_CLAW - Wild Preset Fixture`](<../plugins/test_CLAW - Wild Preset Fixture>)
and the ignored `target/test-assets/plugins` build directory at repository root. They are deliberately
not duplicated here. Resolve plugin/local form IDs at runtime; never reuse old
`FF` references or assume a load-order prefix. The wild group uses the six wolf
placement slots only after the paired group is hidden.

The wild test must exercise real OBody source integration on actors born as
wolves. Do not manufacture the result by assigning a wolf preset, manually
assigning human coefficients, or temporarily turning them into humans.

## Human presets, settings and dependencies

`data/CLAW-Human-Contrast.xml` contains exactly the six ordinary HIMBO/3BA human
presets used by the accepted scene, with equal small/big XML endpoints. Its bytes
match the retained `src/test/resources/fixtures/CLAW-Human-Contrast.xml`; the validation command
detects divergence. No independent wolf shape preset is introduced by this kit.
CLAW's shipped conversion preset calculates wolf morphs from actual human values.

`data/OBody_presetDistributionConfig.json` maps the six human bases and six wild
bases to these human presets and supplies sex-specific werewolf pools. This is
a test-profile override, not a general playthrough distribution policy. Existing
unrelated race blacklists are retained. `skee64.ini` and `SKSEMenuFramework.ini`
are the exact inspection overrides; review them before enabling this test mod in
a different setup.

Install every dependency as a separate mod under its own name, following
`dependencies.json` and the authors' complete requirement chains. Keep CLAW and
Morphbench in separate source profiles. The fixture's family is HIMBO/3BA; this
does not turn an offline CBBE matrix check into a CBBE game run.

For public screenshots, use the official CBBE/HIMBO NeverNude BodySlide projects
with Build Morphs enabled and a separate generated `BodySlide Output - NeverNude`
mod. The generated human output must win; The New Gentleman is disabled in the
photography profile. No third-party body, texture or skeleton is bundled here.
The optional lighting source is under `lighting/`.

## Validate and prepare a run

From the repository root:

```powershell
python src/test/resources/inspection/validate.py
```

This checks portable configuration, names, fixture identities, source data
hashes, the fixed layout, group policies and rotation views. It does not install
mods, launch the game, prove a tool's qualification or attest current game state.
Prepare the actual installed inputs and submit an ordinary Polygon order for the
current source profile and release; platform bindings, endpoints, save instances,
tokens and raw evidence remain outside Git.

During a run, retain actual human source/key maps and wolf target maps, compare
the targets with the shared native matrix kernel, and check source preservation
after return/save-load. Record current incarnations and actual poses rather than
only preset names or successful setter calls. Finish through the game menu and
complete native restoration before cleanup. The 31 October static source snapshot
is identified by `data-manifest.json`; it does not itself constitute a fresh test.
