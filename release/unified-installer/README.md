# CLAW - Configurable Lycanthrope Anatomy and Weight

This installer combines the retained 30 October SE core payloads into one archive.
It always installs the CLAW base. Human morph linkage and its optional OBody
source host are separate choices within the same installer. Packaging does not
extend the retained game qualification to other executable versions.

The base requires Elegant Werewolf Replacer for its textures and the compatible
XP32 skeleton to which the bodies are rigged. Keep CLAW after Elegant in the mod
manager so CLAW's meshes win. CLAW supplies no Elegant textures or skeleton.
Named morph application requires the official RaceMenu/SKEE build and SKSE
matching the chosen game. Install each dependency and its author-declared
requirements separately.

Enable **Human morph linkage (Skyrim 1.7.104.0 only)** only with the exact Skyrim
SE 1.7.104.0 runtime, SKSE 2.3.1, matching Address Library v13 and official
compatible RaceMenu/SKEE. The installer gates the option using the manager's
detected game version and active `RaceMenu.esp`; it cannot establish matching
SKSE, DLL/API versions or the complete dependency chain. Other SE/AE runtimes
and Skyrim VR receive the base resources alone. This is no new claim that those
base resources or their dependency combinations have passed game qualification.
The retained base plugin is flagged light; its VR loading requirements have not
been qualified for this frozen bundle.

When linkage is selected, declare the human geometry actually installed:
HIMBO 5.8 with either CBBE 2.0.3 or 3BA 2.48. These choices install a conversion
mapping, not human bodies or presets. OBody retains ownership of ordinary human
preset assignment. CLAW reads effective human morphs and contributes linked wolf
morphs; it does not introduce a separate wolf preset pool.

The optional **Originally-beast OBody source integration** requires active
`OBody.esp` and its complete dependency chain. It asks OBody for human source
values for eligible actors first encountered as wolves. Leave it unchecked to
omit that host and its scripts. The base and ordinary linkage remain available
without the host.

The five payload selections are:

| Selection | Installed payload |
|---|---|
| Linkage unchecked | Base |
| HIMBO + CBBE, source host unchecked | Base + native linkage + CBBE mapping |
| HIMBO + CBBE, source host checked | Base + native linkage + CBBE mapping + source host |
| HIMBO + 3BA, source host unchecked | Base + native linkage + 3BA mapping |
| HIMBO + 3BA, source host checked | Base + native linkage + 3BA mapping + source host |

The native corresponding-source ZIP is retained under the archive's `Source/`
directory. The installer selects no files from that directory; it is not copied
into the game. Keep it with the distributed archive.

The frozen linkage passed the documented SE mechanism and numeric regressions.
The owner still finds the visible thin/bulky contrast too weak, and breast shape
needs further work. Physics, stronger body endpoints, fur colour, VR body work
and other native runtimes remain separate trials. This installer supplies no
physics configuration, test actors, third-party DLL replacement or alternate
skeleton. The unchanged native binary contains dormant development paths;
their presence does not establish physics support.

Use a FOMOD-capable manager that honors the runtime and dependency gates. The
installer was checked offline against the documented FOMOD format and MO2's
installer source; a new manager wizard or game session was not run for this
repackaging. Manually copying every archive folder would bypass its choices.
