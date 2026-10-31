# CLAW - Human and Werewolf Comparison for Morphbench

Release target: **0.3.0**. Nexus page:
https://www.nexusmods.com/skyrimspecialedition/mods/197517

The owner explicitly requested publication on31October2026. This file records
prepared artifacts and checks; it does not assert that the Nexus Publish action
or public download verification has already completed. The root publication
record owns the final website status and receipt.

## Final package

- ID: `claw-human-link-dev-001` (preserved for existing installations).
- Version: `0.3.0`.
- Size: 131458 bytes.
- SHA256: `7afa4a3f0fe48fae8df3dfb0cb8da86f5fad28a48f7635d212cbae8041f8e835`.
- External archive: `D:/Skyrim VR Modding/Builds/claw-plugin-release-20261031/package/claw-human-link-dev-001.zip`.

The ZIP contains exactly ten runtime assets. Its nine executable/data assets,
including the embedded shared-kernel WASM and canonical matrix catalogue, are
byte-identical to the qualified0.3.0-dev.8 package
`418f978cf61973524b683bc557b2bb300ab7d75c54ed048464760723916b2b67`.
Only the manifest version changed. Corresponding executable source is unchanged
from02536663c527454f256279fb46122e23c8425f75; the release commit records the updated
manifest and documentation.

No human/wolf meshes, textures, host SDK, game DLL, compiler or third-party
libraries are bundled. No new open-source redistribution grant is implied by
publication; retain the existing source and Nexus permissions. The independent
plugin loads the host's public SDK rather than distributing a copy.

## Dependencies and installation

Use [Morphbench Application0.8.5 and Launcher v1](https://github.com/Vhodnoylogin/morphbench/releases/tag/v0.8.5).
Application ZIP SHA256:
`c24ab0f44431b4bff0d3ed5f708ede4a30523f724bed96c5d42e894383b10f19`.
Root Builder is optional for MO2-managed host deployment. Separate Python,
Blender, OBody and RaceMenu are unnecessary for offline conversion.

Supply the applicable human NIF/TRI family: HIMBO5.8 male, CBBE2.0.3 female or
3BA2.48 female. Compatible werewolf resources are available in the
[CLAW0.7.0.0 release](https://github.com/Vhodnoylogin/claw/releases/tag/claw/0.7.0.0).
The defaults require CLAWArmLean, CLAWLegThighLean, CLAWLegCalfLean and CLAWTorsoLean;
historical CLAW0.6.2.0 lacks these targets. Body resources are read separately,
not redistributed in this plugin ZIP.

Import the intact ZIP through Morphbench's manager and explicitly enable it.
For an update, disable the old installation, use Update and enable it again.
Keep `addon.json` at ZIP root; do not wrap the ZIP in `root/Morphbench` or install
it in Skyrim Data. Morphbench0.8.5 manages its own portable plugin directory.

## Verification

The final release package passed7Python and89Node checks, including all15
consumer checks against the exact0.8.5 public SDK and native/WASM arithmetic
parity. All six human fixture vectors passed against current0.7 body targets and
native-generated expectations. An initial historical fixture audit correctly
failed because it lacked the four later Lean targets; the original failure was
retained. Actual current NIF/TRI names/hashes were re-read through Morphbench's
public facade and expected values recalculated by the independent native CLI.
Original human observations/reconstructions and original fixture files were not
changed. Recalculated expectations are not new game observations.

The exact0.8.5 Application previously passed actual male/female paired renderer
checks with the byte-identical executable assets:124male human inputs/15wolf
outputs and154female inputs/16outputs, max/RMS canonical differences zero,
and linked pointer rotation in both directions. Host0.8.5 itself is now published
and independently qualified for MO2/Root Builder installation and restoration.
Final0.3.0 manifest installation/enabling passed in a separate isolated host.
Any new final-package browser smoke is recorded separately; none of these
consumer checks asserts game, animation or physics acceptance.

External final build/checks/install evidence:
`D:/Skyrim VR Modding/Builds/claw-plugin-release-20261031/`.
Earlier actual renderer evidence:
`D:/Skyrim VR Modding/Builds/claw-plugin-nexus-20261031/host085/`.

## Publication checklist

- Finish the final-package isolated browser smoke and close its temporary host.
- Save the approved cover, description and exact-file dependency choices on Nexus.
- Publish the page and verify the public download/hash/status; record any quarantine
  honestly rather than asserting availability.
- Save the released source/content on main and retain reusable nonshipping tests
  under test; keep later backlog development separate.

The supplied matrices cover body proportions. Head/ears/tail/claws, fur colour,
physics and neutral low/high geometry interpolation remain separate work.
Applying values updates the previews; it does not edit game actors or install
exported mapping files automatically.
