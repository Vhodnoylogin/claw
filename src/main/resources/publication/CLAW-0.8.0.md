# CLAW 0.8.0 publication content

Prepared release content. Publication and installed-game acceptance are recorded
separately; this file alone does not establish either.

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
- Fixed the Vortex FOMOD XML encoding failure, also delivered separately for 0.7.0.

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

## Requirements update

Keep the current runtime-matched SKSE, RaceMenu/SKEE, Address Library, compatible
XP32 skeleton and Elegant texture requirements. HIMBO/CBBE/3BA/BHUNP are choices
for their matching matrices, not unconditional requirements for Vanilla users.
OBody and its own dependencies apply to its optional distribution/integration.
The developer-only Morphbench plugin has separate file-specific tool requirements.
Do not make Morphbench a gameplay dependency.

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
