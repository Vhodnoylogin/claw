# CLAW 0.8.0 publication content

Prepared release content. Publication and installed-game acceptance are recorded
separately; this file alone does not establish either.

Technical mechanism checks are complete for Vanilla and BHUNP/HIMBO. The Vanilla
run ended normally; the BHUNP/HIMBO run passed its mechanical phases and real
source proof but failed during teardown. Keep that distinction in the public
notes; do not describe both runs as clean passes. Acceptance of the independent
Morphbench plugin is deferred and does not block the game-mod release. Keep a
short source/legacy plugin notice; do not advertise development as released.

Exact runtime identities, coverage, restoration and the abnormal-end limit are
recorded in [the 2 November verification record](../../docs/verification-20261102.md).

## Short description

Human presets and inherited traits give each werewolf a shape of its own.

## File description

Human body shape, weight and inherited traits carried into werewolf form.

## Changelog

- Added human-driven head, muzzle, ear, tail and claw proportions using available
  FaceGen traits, stature and body inputs.
- Added explicit actor-weight input to every conversion matrix and male/female
  Vanilla options.
- Added a female BHUNP 3.34 Advanced Ver4 matrix for bodies built with morphs.
- Expanded sparse matrices to arbitrary supported morph names with a shared
  small-coefficient cutoff in the game and preview evaluator.
- Added individual human-derived skin/fur tint and appearance state preservation
  across transformation, model refresh and save/load.
- Made male/female body choices independent and freely selectable in FOMOD.
  Installed plugin markers recommend a default without blocking other choices.
- Fixed the Vortex FOMOD XML encoding failure, also delivered in 0.7.1.

## Description additions

Your character's build carries into beast form. Male and female werewolves can
inherit body proportions, weight and available head/face traits from the person
beneath the fur. Ear, tail and claw proportions participate in the same conversion.
Human skin and hair colours can tint the werewolf's existing materials.

Choose the actual male and female bodies independently during installation.
Supported male choices are HIMBO and Vanilla; female choices are CBBE, CBBE 3BA,
BHUNP 3.34 Advanced Ver4 and Vanilla. Build morphs for the chosen replacement body.
The installer suggests a choice from active plugin markers. If several body mods
are present, select the body whose files actually win your mod conflicts.

Vanilla body deformation uses actor weight. OBody can continue to supply human
body-preset inputs for the morph-based body families, including eligible actors
first encountered as werewolves. It does not create missing human facial or
colour history for an originally-beast actor.

Different automatically distributed coat patterns are planned for 0.8.5. Physics,
fitted contact and a first-person VR body remain separate development work.

### Updating an existing save

Existing characters keep the conversion matrix already stored in the save.
Installing 0.8.0 does not automatically replace those assignments. Start a new
game to use all new defaults from the beginning. Reinstalling a body-family
option alone does not reset a saved actor's matrix.

There is no verified ordinary-console reset command in this release. Do not
recommend recycleactor, disable/enable or resetai as a matrix reset. The developer
Papyrus API ConfigureMorphFamily can explicitly rebind an actor, but is not a
stock console command. An optional console-triggered reapply helper remains
outside the runtime package until its game test is complete.

## Requirements update

Keep the current runtime-matched SKSE, RaceMenu/SKEE, Address Library, compatible
XP32 skeleton and Elegant texture requirements. HIMBO/CBBE/3BA/BHUNP are choices
for their matching matrices, not unconditional requirements for Vanilla users.
OBody and its own dependencies apply to its optional distribution/integration.
The developer-only Morphbench plugin has separate file-specific tool requirements.
Do not make Morphbench a gameplay dependency.

Add the following conditional Nexus requirement, rather than a requirement for
every user:

- **BHUNP (Nexus 31126):** required only when selecting the female BHUNP matrix.
  Use BHUNP 3.34 Advanced Ver4 and build its body with BodySlide's Build Morphs.
  Install BHUNP's own required dependencies and a compatible UNP skin separately.
  This does not add classic UNP Renewal as a supported CLAW matrix family.

Keep HIMBO, CBBE and 3BA requirements conditional on their corresponding installer
choices too. The optional CLAW OBody host is for actors first encountered as
beasts; existing human-to-wolf links do not require that host. OBody itself may
still be used to distribute human presets without installing the beast host.

The ready-to-paste version changelog is
`nexus/0.8.0/changelog-0.8.0.txt`. Keep unfinished physics, automatic matrix
migration and future coat-pattern distribution out of that changelog.

For Nexus 0.8, preserve the existing file-to-file requirements method and its
seven original groups. Add BHUNP 3.34 only as an OR alternative in the female
CBBE group (group 6). Keep the original CBBE row, the other six groups and their
recorded file/version constraints unchanged.

## Technical guide placement

Put the detailed matrix contract, source traits, appearance API, runtime coverage
and developer links in the final technical spoiler. Keep ordinary usage above it.
The conversion uses the same C++ kernel compiled for the game and preview; there
is no independent JavaScript math implementation. Keep source/build bundles out
of the runtime ZIP. Credits remain after the technical guide.

## Credits

Elegant Werewolf Replacer by [Wolflady500](https://www.nexusmods.com/profile/Wolflady500)
and [KaienHash](https://www.nexusmods.com/profile/KaienHash).
XP32 Maximum Skeleton Special Extended by
[Groovtama](https://www.nexusmods.com/profile/Groovtama).
RaceMenu by [expired6978](https://www.nexusmods.com/profile/expired6978).
Preserve the existing additional credits and links when applying page changes.
