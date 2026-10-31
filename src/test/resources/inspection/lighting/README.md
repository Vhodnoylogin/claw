# Optional inspection lighting

This source builds `test_CLAWInspectionLighting.esp` for the CLAW test profile.
It adds one neutral light definition and three placed references around the
accepted QASmoke rows. It is test data, never a production CLAW component.

`build_lighting.py` is the retained deterministic builder used for the accepted
31 October screenshot setup. It takes explicit paths; no host paths or installed
game files are stored here. It preserves the complete winning Dragonborn QASmoke
CELL record and emits only the small localized cell-name entries needed by its
own ESP. The original master and string files come from the user's installation.

```powershell
python src/test/resources/inspection/lighting/build_lighting.py --master <Skyrim.esm> --cell-source <Dragonborn.esm> --strings <extracted-Dragonborn-STRINGS-directory> --output <fresh-external-build-directory>
python src/test/resources/inspection/lighting/verify_lighting.py <build-directory> <Spriggit.CLI.exe>
```

The second command independently parses, rebuilds and reparses with Spriggit;
it compares the resulting text trees. `source/` preserves the six text files from
that independent parse, including localized names, light properties, master
identities and placement records. It is source, not a duplicate binary fixture.

The light radius is 450 game units, RGB 220/225/230, with no shadows or flicker.
Coordinates are X -2537.944824, Y 1200/1550/1900, Z 7106.450195. A later room
override requires a new conflict review; do not carry an older vanilla CELL over
a newer winning override. Install the resulting plugin and its tiny STRINGS
files in the existing `test_CLAW - Human and Werewolf Comparison` mod only while
idle, then enable its ESP in the CLAW profile. No automatic live installation or
fresh lighting acceptance follows from preserving this source.
