# Human-origin lifecycle fixture (not shipping)

This prospective alternative reuses `test_CLAW - Physics Probe.esp`, with only
`Skyrim.esm` as master. It replaces that test plugin for the declared case;
the old born-beast fixture/consumed evidence remain separate and unchanged.
It defines two persistent initially-disabled ACHR records, no NPC records,
scripts, quests, races, body/face assets or runtime-created FF references.

| Local reference | Original base | Scene alias | Actual original EditorID | Sex / race | Base weight |
| --- | --- | --- | --- | --- | --- |
| 000900 | Skyrim.esm:0A2C91 | Runa | HousecarlRiften | female / Nord013746 | 50 |
| 000901 | Skyrim.esm:0A2C90 | Grom | HousecarlWindhelm | male / Nord013746 | 29.999998092651367 |

Aliases come from the tracked comparison `inspection/scene.json`. The comparison
is a mod folder, not a plugin/master named "Human and Werewolf Comparison.esp".
Its human actors use these original Skyrim NPC bases. `fixture.json` retains
original-record offsets/hashes and float32 weight bits from the source readback.
The producer reopens and verifies those exact records, including sex, Nord race,
height, weight and absence of a template. It does not copy or modify their data.
These source facts do not establish the active profile's winning overrides.

The complete CELL fields and storage positions retain the previous authored
probe source. Storage coordinates are not a qualified standing-floor claim.
The future case must place each still-disabled owned reference at its explicitly
declared scene position and verify it before enabling/measurement. It must also
refuse stale saved changeforms whose base/disabled state differs from the new
fixture; filename/local-ID reuse does not prove fresh reference identity.

## Offline build

Run `build_fixture.py` with explicit `--master`, `--spriggit`,
`--spriggit-assembly`, `--translation-cache` and a fresh external `--out`.
The existing installed Spriggit0.41.0 tool and cached Skyrim YAML translator are
required; missing inputs fail. No compiler/provider acquisition or installation
is part of this producer. It records commands/tool/source pins, official
serialization/rebuild, byte-identical roundtrip and independent binary guards.
Generated ESPs/readbacks stay outside Git. Build success is not game acceptance.

## Prospective one-process lifecycle (not an executable order)

1. Reacquire900/901 with actual `GetFormFromFile`; admit exact base, reference,
   plugin, sex, original-human Nord base race, current human race, disabled state
   and fresh loaded incarnation/root as appropriate. Never hard-code a0D prefix.
2. Enable only the declared subject with known ownership; capture human keyed
   morph/source state, appearance and unchanged original base weight.
3. Human → wolf via the declared SetRace; observe actual race/root and retained
   source/selection. Queue one CLAW Refresh and require applied readback.
4. Return to the original human race, then transform again; reject old graph
   authority. Queue one NiNode update, observe actual completion/root outcome.
5. Use an owned save/load only after mutation completion is known. Reacquire the
   authored reference by plugin/localID and a fresh epoch/root; no old pointer,
   handle, graph or completion authorizes later writes.
6. Only then arm the existing provider pose/first-witness measurement once in
   that process. Use the exact current0.10 DLL/resources/provider contract; no
   physics window is inferred at the preceding lifecycle boundaries.
7. Known ownership permits guarded Disable and unloaded/null-root verification.
   Unknown transport, identity, epoch or root quarantines custom writes; ordinary
   owned Session exit/restoration remains mandatory.

Initial human Nord ancestry is captured explicitly. Actual typed SetRace in the
13November engine test changed both observed currentRace and baseRace to its
target, while baseForm, sex and weight stayed unchanged. Subsequent guards must
require both actual race fields to match that declared transition target; a
permanently-Nord baseRace assertion is incorrect. Human return requires both
fields Nord again. Retain the initial-human witness and exact original baseForm
throughout; never rewrite rows or waive identity checks. Morph vectors/coat
retention still need actual observations.

Base weights stay at their authored Skyrim values. No SetWeight is scheduled:
an actor API that changes its shared NPC base would modify foreign state. Any
later0/100 phase needs a proven reference-only mechanism or separate authored
NPC sources and a new reviewed scope. This fixture provides no such mechanism.
