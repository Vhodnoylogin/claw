# CLAW – Customizable Lycanthrope Appearance and Weight

Version @VERSION@

Human body shape, weight and facial traits influence your werewolf form.
Install [Elegant Werewolf Replacer](https://www.nexusmods.com/skyrimspecialedition/mods/93336)
and choose your usual skin. Give CLAW's body meshes priority. CLAW uses that
skin when the optional coat textures are unavailable.

**Optional individual coats (MO2).** Download **Elegant Werewolf Player Only
FOMOD 2K**, file **798407**, separately from [Elegant's Files page](https://www.nexusmods.com/skyrimspecialedition/mods/93336?tab=files).
Start its manual installer in MO2. Expand `Randomized`, set its `Data` folder
as the data directory and select only `textures`. Install this as a separate
mod and keep it enabled. This provides ten coats under
`textures/DiverseElegantWerewolves/`. CLAW reads the installed files. The
optional addon's ESP and Model Swapper rules can select different meshes and
are unnecessary for this texture-only installation.

Human hair colour and a stable actor seed determine the coat; with no known
human hair colour the seed supplies the variation. Integrations may assign a
coat explicitly. If upgrading from the withdrawn 0.9.0 archive, remove its
installed copy first and keep the separate Elegant installation enabled.

Use the FOMOD installer in MO2 or Vortex. Choose the human meshes that win your
mod conflicts. Male options are HIMBO and Vanilla. Female options are CBBE,
CBBE 3BA, BHUNP 3.34 Advanced Ver4, UNP Renewal 4.6 and Vanilla. Generate body
morphs for the selected morph-based body. Classic UNP and Vanilla use NPC weight.

Requires SKSE, RaceMenu/SKEE, Address Library, a compatible XP32 skeleton and
the Microsoft Visual C++ x64 runtime. Use versions matching your game.
The optional OBody choice requests a human preset for eligible actors first
encountered as werewolves. Leaving it unchecked keeps ordinary human-to-wolf
conversion and uses the inputs already available for wild werewolves.

Existing actors keep their saved body matrices. A new game starts with the
selected defaults.

Elegant Werewolf Replacer by Wolflady500, based on work by KaienHash. Valley
coat textures by LilyValley807; texture processing by XilaMonstrr. Obtain the artwork
from Wolflady500's Elegant download linked above.

[Source and build instructions](@SOURCE_URL@)
