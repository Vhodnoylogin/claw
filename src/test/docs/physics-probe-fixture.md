# Female born-werewolf physics probe

`src/test/resources/plugins/test_CLAW - Physics Probe/` contains authored
Spriggit YAML for a disposable physics test plugin. Generated ESP files belong
in ignored `target/` or an external Builds directory, never in Git or the
released mod archive. Preparing or building these records does not install them
or authorize a game launch.

## Records

The plugin is a regular ESP with only `Skyrim.esm` as a master. It contains two
female NPC bases, two persistent initially-disabled references and the seed
QASmoke cell override. There is no script, quest, new race, body asset or model
override in this fixture.

| Role | Editor ID | Local ID | Base | Initial position |
| --- | --- | --- | --- | --- |
| Probe A base | CLAWPhysicsProbeA | `000800` | — | — |
| Probe B base | CLAWPhysicsProbeB | `000801` | — | — |
| Probe A reference | CLAWPhysicsProbeARef | `000900` | `000800` | `-554, 1893, 6650` |
| Probe B reference | CLAWPhysicsProbeBRef | `000901` | `000801` | `-224, 1893, 6650` |

Both bases have Female, Essential and AutoCalcStats flags, race
`0CDD84:Skyrim.esm` (WerewolfBeast), height 1 and weight 100. Their born-beast
fields derive from the authored `CLAWTestWildLuna` record in the Wild Preset
Fixture. Human head parts, hair colour, head texture, face morphs, face parts,
tint layers and a human worn-skin override are absent. Neutral TextureLighting
and creature sound fields retain that existing born-beast template.

Both ACHR records have header flags `0xC00`: Persistent (`0x400`) and
InitiallyDisabled (`0x800`). Their bases, placements and the complete room
override derive from the existing external-coat actor seed; other room fields
are unchanged. The coordinates are retained storage coordinates, not proof of a
valid standing floor or physics measurement location.

## Build and verification

Use the installed Spriggit CLI 0.41.0 with the Skyrim YAML package 0.41.0:

```text
spriggit deserialize --InputPath "src/test/resources/plugins/test_CLAW - Physics Probe" --OutputPath "<external-build>/test_CLAW - Physics Probe.esp"
spriggit serialize --InputPath "<external-build>/test_CLAW - Physics Probe.esp" --OutputPath "<external-build>/readback" --GameRelease SkyrimSE --PackageName Spriggit.Yaml --PackageVersion 0.41.0
spriggit deserialize --InputPath "<external-build>/readback" --OutputPath "<external-build>/roundtrip/test_CLAW - Physics Probe.esp"
```

The 2026-11-11 preparation under external directory
`Builds/claw-fsmp-female-fixture-20261111` records source/tool hashes, original
seed and Luna provenance, commands, official typed readback and an independent
binary record check. The generated ESP is 1,351 bytes with SHA256
`e0225fa32d6e36df519719e9d7a7a952d2e2ec178537e3f64e7aaef6cad61ebe`.
The second build is byte-identical. Raw ACBS/RNAM, ACHR flags/NAME/DATA, cell
ancestry, master list and absence of human head/face/tint subrecords were checked
independently of the YAML serializer.

## Runtime boundary

This fixture has not been installed or tested in game. Resolve local IDs through
`test_CLAW - Physics Probe.esp` at the actual load order; do not hard-code a
runtime load-order prefix. Before enabling either reference, inspect its exact
reference/base/plugin identity and initially-disabled state. Use the native
world observer for this check: the general actor domain requires an enabled
incarnation. Place the actors at explicit qualified scene coordinates, then
enable and verify loaded female werewolf models before physics measurements.

The operator must select the actual CLAW female body and physics resources in
the separate task profile, capture their exact hashes and distinguish solver
motion from imposed skeleton motion. YAML/readback success establishes record
wiring, not FSMP motion, collision, body rendering or game acceptance.
