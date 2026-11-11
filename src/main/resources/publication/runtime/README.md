# CLAW – Customizable Lycanthrope Appearance and Weight

Version @VERSION@

Human body shape, weight and facial traits influence your werewolf form.

## Installation

1. Install [Elegant Werewolf Replacer](https://www.nexusmods.com/skyrimspecialedition/mods/93336)
   normally through your mod manager and select a base coat. Keep this mod enabled.
2. Install CLAW through its FOMOD in MO2 or Vortex and choose your actual male and
   female human bodies. Let CLAW's werewolf NIF and TRI files win conflicts with Elegant.
3. For individual coats, also install Elegant's Randomized component below.
   The base Elegant installation supplies the fallback coat and shared maps.

**Optional individual coats (MO2 or Vortex).** Download **Elegant Werewolf Player Only
FOMOD 2K**, file **798407**, separately from [Elegant's Files page](https://www.nexusmods.com/skyrimspecialedition/mods/93336?tab=files).
Install it normally through its FOMOD and select **Randomized** on its texture
page. Keep the installed mod enabled, then disable **CoopPlayerOnlyWerewolf.esp**
in your manager's Plugins list. CLAW supplies the player and NPC werewolf body.
Let CLAW win both the werewolf NIF/TRI conflicts and the Data-root
**RandomElegantWerewolves_MS.json** conflict. In MO2 place CLAW after the addon
in the left pane. In Vortex set the corresponding file-conflict rule so CLAW
loads after it, then deploy.

CLAW supplies an authored empty Model Swapper rule at that exact filename. This
prevents the addon's whole-model substitution while its original textures remain
available under `textures/DiverseElegantWerewolves/`. Check that folder contains
ten coat folders, including `Black/body.dds` and `Timber/body.dds`.

MO2 users can alternatively use its **Manual** installer, select `Randomized/Data`
as the data directory and install only its `textures` folder as a separate mod.

Human hair colour and a stable actor seed determine the coat; with no known
human hair colour the seed supplies the variation. Integrations may assign a
coat explicitly. When updating CLAW, replace its installed mod so obsolete files
are removed. Keep the separate Elegant installations enabled.

If a selected Randomized coat is missing, incomplete or has invalid DDS headers
or dimensions, CLAW retains the installed base coat. Body, head, ear, tail and
claw conversion continues. A partial coat is rejected before its materials are
bound, and the diagnostic status records the unavailable resources. Correct the
Randomized installation and restart the game to revalidate the files.

If the base Elegant textures are also missing, install Elegant first. The base
model references those files directly, so absent base files can produce missing
textures even when the optional coat fallback is working.

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
