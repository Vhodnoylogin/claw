# Optional private Bijin skin compatibility test

This local builder targets only original **Bijin NPCs SE1.2.1 AIO**, identified
by `pin.json`. It is a controlled follow-up to the actual Adrianne/Lisette test,
not a production compatibility promise or a new body-family detector.

```powershell
python src/test/resources/compatibility/bijin/build_patch.py --source "<original Bijin NPCs.esp>" --output "<fresh external build folder>" --spriggit "<Spriggit0.41 CLI>"
```

The patch has three masters in this exact order: Skyrim.esm, Update.esm,
Bijin NPCs.esp. Original self-index2 FormIDs/references therefore stay unchanged
when copied as Bijin master overrides. Each of the14 existing skin ARMO records
gets exactly one extra MODL reference to Skyrim.esm:0CDD87, immediately after
its last existing armature entry. All original subrecord bytes and record-header
fields except the necessarily changed payload size are preserved. The inverse
removal must recover the original payload exactly.

Only an own TES4 header and one ARMO group are emitted:14 overrides, no NPC,
ARMA, body, texture, script or DLL payload. Spriggit0.41 parses, rebuilds and
reparses the patch; the text trees and record counts are checked. Generated ESP,
ZIP, vendor-derived YAML and receipts stay outside Git. No third-party record
payload or artwork is tracked here, and no installation is performed.

The small ZIP can be installed normally in the **owned test MO2 profile only**,
after Bijin and with CLAW's werewolf ARMA/model resources winning. Keep the
original Bijin files untouched. Re-run the same actual owned NPC case and
observe geometry/materials, human return, save/load and restoration separately.
Fourteen structurally changed skins do not establish fourteen runtime successes.
