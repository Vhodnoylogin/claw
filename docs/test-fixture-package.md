# Single test-data package

`scripts/build-test-fixture-package.py` builds the deterministic
`test_CLAW - Human and Werewolf Comparison - 20261030.zip`. Install it as the single
MO2 mod `test_CLAW - Human and Werewolf Comparison`, alongside the separate working
CLAW archive and separately installed dependencies. It replaces the two source
test/configuration folders for this inspection profile; the builder never changes
MO2 or launches the game.

The archive has exactly eight files: the repository's six-NPC wild fixture ESP,
the repository's XML containing six current human HIMBO/3BA contrast presets,
the effective OBody assignments, inspection `skee64.ini` and
`SKSEMenuFramework.ini`, a sanitized reusable scene recipe, README and public
hash manifest. Repository ESP/XML bytes must exactly match the installed test
inputs. The builder independently checks the ESP contains six originally-beast
NPC definitions, three of each sex, with Skyrim.esm as its sole master and no
placed references, quests or scripts. Human pair definitions use the six existing
Skyrim NPC bases named in the effective OBody assignments; no extra human plugin
or appearance asset is necessary.

The current source profile's first enabled modlist entry wins a conflict. The
fixture's OBody configuration wins over the masked inspection configuration:
the former has twelve explicit NPC assignments and two sex-specific wild-race
pools; the latter disables distribution and is intentionally omitted. The
effective fixture assignment file is retained unchanged. It replaces global
OBody settings/blacklists in this isolated test profile, so do not treat it as a
general gameplay configuration. RaceMenu's inspection settings enable body
morphs and disable BodyGen; menu settings change controls. The external manifest
records every enabled source-profile provider, winning path and byte hash for
all five selected installed files.

The scene recipe is data, not a save or already-spawned scene. It retains the
owner-accepted absolute QASmoke coordinates and stable Dragonborn.esm:02A1B9
marker offsets, pair separation110, pair pitch300, row separation320 and all
twelve names/headings. Iney, Kedr, Grom, Lada, Mira and Runa each have Human/Wolf
members. Both members initially use the same human base, appearance, weight and
keyed OBody source vector; only the Wolf member transforms after equality checks.
The optional six originally-beast plugin bases form a separate group.

Capture actual global AI/collision Off **before creating any fixture**; TAI/TCL
are toggles, so never replay blindly. Resolve new session references, preserve
measured floor heights and verify all final poses twice after transformations.
The sanitized historical comparison records all six source vectors equal:
61 source coefficients for each male pair and52 for each female pair, with zero
aggregate/key/weight differences. This does not qualify a newly created scene.
No transient FF reference, token, private path or live command enters the ZIP.

```powershell
python scripts/build-test-fixture-package.py `
  --mods '<source MO2 mods directory>' `
  --profile '<source CLAW profile directory>' `
  --scene '<journal manual-inspection-defaults.json>' `
  --pair-readback '<accepted scene pair-readback.json>' `
  --working-archive '<final working CLAW ZIP>' `
  --out '<new external builds directory>'
python -m unittest discover -s tests -p test_test_fixture_package.py -v
```

The builder hashes and checks every selected payload of every working-ZIP
installation choice and rejects any destination collision with test data. It also
checks the frozen production manifest, including both human-family mappings.
No production body/TRI/CLAW ESP/DLL/PEX or MorphLinks override, dependency asset,
texture, manager metadata, legacy mod, save or test order is included.
`source-provenance.json` and `build-receipt.json` stay outside the archive; the
former contains machine paths for local audit only. ZIP entry order, timestamps,
permissions and compression parameters are fixed; every stored byte and CRC is
read back. Existing output directories are refused.
