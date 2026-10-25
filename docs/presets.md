# Independent CLAW presets and OBody coexistence

Development contract, 25 October 2026. The 0.6.2.0 release contains body resources;
the distribution companion and authoring support are being developed separately.
No game compatibility or preset range qualification is implied by format validity.

## Why an optional companion

Inspected stock OBody NG 4.4.3 and upstream1351360 (24 October 2026) lack typed
body-family filtering. Both classify male presets through human body-family
substrings, and use the actor's base race for race distribution. The vanilla
WerewolfBeastRace lacks ActorTypeNPC, which gates OBody's automatic event handler.
Its public API cannot register another body family or filter the stock menu by it.

The companion therefore owns beast selection and assignment. OBody continues to
own human assignment. No fake HIMBO tags, global preset database replacement,
race keyword edits or human preset reassignment are required. A separate companion
is the intended implementation; an OBody fork is not required for coexistence.
This does not add werewolf presets to OBody's own internal menu.

## Package contract for preset authors

An independent preset mod can contain just:

```text
CalienteTools/BodySlide/SliderPresets/CLAW/YourAuthorName.xml
```

Use a unique file name and globally unique preset names. The XML is ordinary
BodySlide format, with exact `set="CLAW Male"` or `set="CLAW Female"` and CLAW
groups. OBody's inspected loader scans only the parent directory; it does not
read this nested subtree. BodySlide scans recursively. The companion reads the
CLAW subtree, keeping beast presets outside the human random-selection pool.
The directory name and loader behavior are part of the compatibility contract;
recheck if a future OBody version changes its scanner to recursive traversal.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<SliderPresets>
  <Preset name="YourName - Long Ears Male" set="CLAW Male">
    <Group name="CLAW"/>
    <Group name="CLAW Male"/>
    <SetSlider name="CLAWHeadEarSize" size="small" value="15"/>
    <SetSlider name="CLAWHeadEarSize" size="big" value="30"/>
  </Preset>
</SliderPresets>
```

XML values use percentages:15means morph0.15. `small`/`big` endpoints interpolate
at actor weight0..100 even though the base release uses identical neutral weight
meshes. An omitted endpoint is zero, as in ordinary BodySlide presets. This affects
named morph values and does not restore weight-dependent base geometry.

Initial supported range is0..100 in XML, known base CLAW names only. Male presets
cannot contain the female-only breast morph. Adult morphs, malformed XML,
nonfinite/extrapolated values, duplicate endpoints and duplicate preset names are
rejected. These are format/ownership constraints, not guarantees that all combined
morph values look correct. Avoid enlarging the female breasts in distributed
examples until shape/rig repair is accepted.

Names are limited to160UTF-8bytes, without surrounding ASCII whitespace or control
characters. A typed preset with no sliders represents the neutral body: all of
the companion's contributions are zero. It is not a request to clear other keys.

## Authoring and validation

`scripts/presets.py` validates XML files/folders and converts the documented
`presets/examples.json` authoring schema (coefficients0..1) to XML. It never
overwrites an existing output. The four examples intentionally focus on ears/tail
and remain development examples pending game validation.

```powershell
python scripts/presets.py export presets/examples.json --out 'D:/staging/YourName.xml'
python scripts/presets.py validate 'D:/staging/YourName.xml' --weight 50
```

The validator reports weight-interpolated values,
sex, source paths and hashes. Installing a preset does not require rebuilding the
body. A separate BodySlide project is needed to expose the sliders for authoring
in its preview; its generation belongs to the authoring resource build.

`scripts/build-authoring.py` generates the two typed projects using official
Outfit Studio automation in an isolated tool/config copy. It imports the actual
NIF and TRI, checks every shape/morph and retains unchanged reference geometry.
The output contains OSP, OSD, reference NIF and sex-specific groups, without the
third-party executable. Save a preset in BodySlide, then put its XML under the
CLAW subtree before packaging or starting the game. Keep the installed body
neutral for distribution: saving a preset does not require building that preset
into the game's body meshes.

`scripts/check-authoring.py` runs official BodySlide batch builds for neutral,
ear-at100percent and mixed presets for both sexes and both weight endpoints.
It compares the result to source NIF plus decoded TRI offsets; it does not use a
second hand-written BSD/OSD codec. The first resource build passed all six builds
and twelve endpoint comparisons outside the game.

`scripts/build-distribution-data.py` separately compiles the menu/native script
and builds the selector quest in new external staging. After a native build,
`scripts/package-distribution.py` verifies source/artifact receipts and assembles
two development ZIPs: the companion and an independent example-preset mod. It
requires all five dependency license texts. Unexpected compiled files, stale
source receipts and changed artifact bytes are refused; no live installation or
release promotion follows. A unified native build freeze can be supplied with
`--native-receipt`; it must contain the matching source and artifact hashes and
successful offline test results. This does not certify the game ABI or behavior.
The CLI/test sources and their compiled bytes are verified too; those executables
remain outside the installable companion archive.
Keep the authoring OSP/OSD resources separate from
the runtime mod. The companion package contains no test actors, body repair,
physics, external executables or body meshes.

## Runtime ownership and settings

The companion uses only `CLAW.Distribution`, persists an independent beast preset,
checks current race and loaded 3D, and reports pending/applied/error separately.
Human-to-beast coefficient transfer is a later feature, not required for independent
beast presets. UI selection and automatic assignment must be tested on both sexes,
including save/load, delayed model loading and coexistence with other morph keys.

For OBody4.4.3, enable its respectful morph application setting: that version
otherwise clears all actor morph contributions. Current upstream clears only
its own keys. Do not infer compatibility with an untested deployed version from
these source observations. Automatic recovery after OBody notifications still
requires actual runtime qualification.

Primary sources: official [OBody4.4.3 preset loader](https://github.com/Aietos/OBody-NG/blob/e33bbc151c38fbe6feae9f5b04558cd6c7528384/src/PresetManager/PresetManager.cpp),
[event eligibility](https://github.com/Aietos/OBody-NG/blob/e33bbc151c38fbe6feae9f5b04558cd6c7528384/src/Body/Event.cpp),
[preset application](https://github.com/Aietos/OBody-NG/blob/e33bbc151c38fbe6feae9f5b04558cd6c7528384/src/Body/Body.cpp),
and [BodySlide recursive preset discovery](https://github.com/ousnius/BodySlide-and-Outfit-Studio/blob/7ccf6a21eb72a583a9e593abf0a186f4361846af/src/components/SliderPresets.cpp).
