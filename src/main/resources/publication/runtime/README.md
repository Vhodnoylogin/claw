# CLAW – Customizable Lycanthrope Appearance and Weight

Version @VERSION@

Human body shape, weight and facial traits influence your werewolf form.

## Installation

1. Install SKSE, RaceMenu, Address Library and a compatible XP32 skeleton for
   your game, together with the Microsoft Visual C++ x64 runtime.
2. From [Elegant's Files page](https://www.nexusmods.com/skyrimspecialedition/mods/93336?tab=files),
   install **Elegant Werewolf Player Only FOMOD 4K** or
   **Elegant Werewolf Player Only FOMOD 2K** through your mod manager.
   Choose **Randomized** for individual coats. Other choices provide one coat.
   Keep Elegant enabled.
3. Install CLAW through its FOMOD in MO2 or Vortex. Choose your actual male and
   female human bodies and let CLAW win conflicts with Elegant. When updating,
   replace the previous CLAW installation so obsolete files are removed.

Male bodies: HIMBO or Vanilla. Female bodies: CBBE, CBBE 3BA, BHUNP 3.34 Advanced
Ver4, UNP Renewal 4.6 or Vanilla. For a morph-based body, build that body in
BodySlide with **Build Morphs** enabled. Vanilla and classic UNP use actor weight.

## Individual coats

Human hair colour and a stable actor seed determine the coat; with no known
human hair colour the seed supplies the variation. Integrations may assign a
coat explicitly. Keep the separate Elegant installation enabled.

If a selected Randomized coat is missing, incomplete or has invalid DDS headers
or dimensions, CLAW retains the installed base coat. Body, head, ear, tail and
claw conversion continues. A partial coat is rejected before its materials are
bound, and the diagnostic status records the unavailable resources. Correct the
Randomized installation and restart the game to revalidate the files.

If the base Elegant textures are also missing, install Elegant first. The base
model references those files directly, so absent base files can produce missing
textures even when the optional coat fallback is working.

## Werewolf motion

@MOTION_INSTRUCTIONS@

## Optional OBody presets

The installer option **Use OBody presets for wild werewolves** requests human
presets for eligible actors that originally spawned as werewolves. Leaving it
unchecked uses their already available parameters. Ordinary human-to-wolf
conversion works with either choice. OBody and its dependencies are required
only when using that optional source assignment.

Existing actors keep their saved body matrices. A new game starts with the
selected defaults.

Elegant Werewolf Replacer by Wolflady500, based on work by KaienHash. Valley
coat textures by LilyValley807; texture processing by XilaMonstrr. Obtain the artwork
from Wolflady500's Elegant download linked above.

[Source and build instructions](@SOURCE_URL@)
