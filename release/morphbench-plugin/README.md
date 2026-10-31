# CLAW - Human and Werewolf Comparison for Morphbench

Unpublished Nexus draft, created 31 October 2026:
https://www.nexusmods.com/games/skyrimspecialedition/mods/197517/edit/general

The owner requested a separate Nexus mod for this offline plugin. Do not publish
this draft without the owner's release instruction. General text, two genuine
untextured comparison screenshots and one plugin ZIP have been saved in the
unpublished page. Category: Utilities; tags: Utilities for Players and Utilities
for Modders. Credits are last; technical details are inside the final spoiler.

The retained package is the exact qualified development build 0.3.0-dev.8,
ID `claw-human-link-dev-001`, 131464 bytes, SHA256:
`418f978cf61973524b683bc557b2bb300ab7d75c54ed048464760723916b2b67`.
It is not relabelled as a stable release. Its ten runtime assets contain no
meshes, textures, host SDK, game DLL or third-party libraries. Source code and
shared kernel correspond to 02536663c527454f256279fb46122e23c8425f75.

Import the intact ZIP through Morphbench's manager, then enable it. For an update,
disable the old installation, use Update and enable again. Keep `addon.json` at
ZIP root: do not wrap this plugin in `root/Morphbench` or install it in Skyrim
Data. Morphbench 0.8.5 manages its own portable plugin directory.

## Consumer check on the packaged application

The exact 0.8.5 Application ZIP (617678 bytes, 153 files) has SHA256
`c24ab0f44431b4bff0d3ed5f708ede4a30523f724bed96c5d42e894383b10f19`.
Its public SDK matches the previously qualified bytes; all 15 detached consumer
checks passed. In a separate browser-host process using the extracted application,
the actual male pair accepted 124 human inputs and 15 wolf targets, and the
female pair accepted 154 and 16. Both reported max/RMS difference zero against
the canonical matrix. Pointer drags in either female viewport rotated both
models. Actual images and the retained female coefficient table are outside Git.

This is consumer UI/SDK/rendering acceptance. It does not replace the Morphbench
owner's separate Launcher/runtime, MO2 and Root Builder qualification. No game
or live installation was involved; the temporary host was stopped afterward.

## Release gates

- Await the Morphbench owner's final 0.8.5 release and installation qualification.
  The exact packaged application passed the separate consumer check above.
- Link accessible matching CLAW NIF/TRI resources. The default matrix needs
  CLAWArmLean, CLAWLegThighLean, CLAWLegCalfLean and CLAWTorsoLean. Historical
  Nexus CLAW 0.6.2.0 lacks them and is insufficient for the supplied defaults.
- Review intended plugin permissions with the owner. No explicit licence is
  currently present; public source readability is not a general redistribution
  grant. The independent plugin does not bundle the Morphbench SDK.
- Choose a final version and rebuild/smoke-test if runtime assets change. Preserve
  the existing plugin ID unless a deliberate migration is implemented.

The offline plugin does not require OBody or RaceMenu to execute its conversion.
Human and wolf NIF/TRI resources must be supplied separately. Applying a vector
changes preview models, not game actors or installed files. Current supplied
matrices cover body proportions; traits, fur colour and physics are future work.

External evidence and candidate package:
`D:/Skyrim VR Modding/Builds/claw-plugin-nexus-20261031/`.
No MO2 profile, game-root file or live game was changed for this draft.
