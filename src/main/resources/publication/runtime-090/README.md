# CLAW - Customizable Lycanthrope Appearance and Weight

Version 0.9.0

Human body shape, weight and available inherited traits carry into werewolf form.
Install with the FOMOD installer in Mod Organizer 2 or Vortex. Choose the human
body whose files actually win your mod conflicts: HIMBO or Vanilla for males;
CBBE, CBBE 3BA, BHUNP 3.34 Advanced Ver4, UNP Renewal 4.6 or Vanilla for females.
Build morphs for the selected morph-based replacement body. Classic UNP and
Vanilla use actor weight and available generic traits rather than body sliders.

Individual coats use all 34 patterns from the Elegant 2K 2.1 texture library.
Automatic selection uses 32 natural patterns; two stylized patterns are available
for manual assignment. Human hair
selects a colour group, while a stable actor seed selects the markings. Beasts
without human hair information receive a stable natural coat. Manual assignment
takes priority; CoatPolicy.xml controls the permitted patterns and tint policy.

The optional "Use OBody presets for wild werewolves" installer choice supplies
human preset inputs to eligible actors first encountered as beasts. Existing
human-to-wolf morph links do not require this extra host. Install OBody and its
dependencies separately when using preset distribution.

Install matching SKSE, RaceMenu/SKEE, Address Library, Microsoft Visual C++ x64
runtime and a compatible XP32 skeleton. Retain Elegant Werewolf Replacer as the
credited required dependency. Human replacement bodies and their dependencies
remain separate mods. Physics and a first-person VR body are not included.

Saved actors keep their existing conversion matrix. A new game uses the selected
defaults from the beginning; reinstalling a body-family choice does not replace
an actor's saved matrix.

Elegant assets by Wolflady500 and KaienHash. Additional texture credits:
LilyValley807, XilaMonstrr and CinnaMewRolle. Original asset terms:
https://www.nexusmods.com/skyrimspecialedition/mods/93336

Source and build information: https://github.com/Vhodnoylogin/claw/tree/@SOURCE_REF@
