# Bijin NPCs 1.2.1: local compatibility analysis

The owner's downloaded `Bijin NPCs SE 1.2.1-11287-1-2-1.7z` has SHA256
`c862bee6f49dd064d62f8606df074e9125e2e7cf6e84127b7cb3ced7442c83df`
and size 159,295,466 bytes. Initial extraction and analysis were external and
changed no installed mod, profile or original archive. The subsequent owned SE
installation and game checks are recorded below. Private extracted artwork/record dumps are
not CLAW source or distributable payload.

## Actual archive and record chain

The FOMOD offers UNP Body and CBBE Body. Main supplies UNP; choosing CBBE installs
`03 CBBE` over the same destinations. Both bodies, hands and feet use the private
`meshes/actors/character/Bijin NPCs/` folder. The plugin does not select a second
path or expose a body-family identifier for the CBBE option.

The AIO plugin contains sixteen NPC overrides for fourteen named characters
(three Rikke records), fourteen skin ARMO and forty-two ARMA. Official Spriggit
readback and an independent binary decoder agree. All fourteen separate plugin
alternatives were also decoded: each uses the same skin→human-addon mechanism
and the same female torso path. They do not implement a distinct algorithm for
every NPC. Individual skin texture sets differ; the body mesh is shared within
Bijin rather than uniquely named per NPC.

NPC WNAM is rendered as `WornArmor` in this Spriggit schema. It is the NPC skin
field read by parameterless `Actor::GetSkin()`, not proof of equipped clothing.
For example, Ingun routes through her own ARMO to a female torso ARMA referencing
`actors/character/Bijin NPCs/femalebody_1.nif`. This is the same class of routing
as the authored CLAW custom-skin fixture, not evidence that the fixture already
qualifies Bijin.

All these skin armatures contain only three human addons. None declares the
wolf torso `Skyrim.esm:0CDD87` or WerewolfBeastRace compatibility. A possible wolf
model availability problem is separate from correct matrix selection and needs
actual transformation evidence or a reviewed compatibility patch. Do not claim
an observed invisible-body failure from static records alone.

## Morph capability is distinct from body-family names

The 257 actual files include 98 NIFs, 125 DDS, 15 ESPs, 18 JPGs and one FOMOD XML. There is
no TRI, BodySlide project, DLL or packaged script. Public PyNifly independently
loads all twelve supplied body/hands/feet endpoints. They have no attached root/
shape string extra data and no BODYTRI, `.tri` or NiGeomMorpherController marker.
The body headers use BS83; rejection by CLAW's intentionally narrow BS100 editing
helper is unsupported format, not corruption. No helper restriction was relaxed.

UNP torso has 6,622 vertices; CBBE has 3,471. Every torso vertex differs between
its 0/1 endpoints, and the ARMA enables weight interpolation. This is source evidence
for ordinary weight variation, not RaceMenu BodySlide morphs or actual game
interpolation acceptance. Additional user-generated patches can change that
capability; this analysis applies only to the exact downloaded archive.

## Architectural consequence

An explicit path binding is configuration, not automatic content classification.
Bijin demonstrates two different families at exactly the same path. Neither an
active ESP nor a stored RaceMenu value proves that a particular loaded body can
deform by that morph. Do not add a guessed permanent Bijin→CBBE binding.

Keep the mathematical evaluator independent of these decisions. A future source
adapter can distinguish declared family/resource identity, actual morph
capability and input availability; a separate model adapter owns the wolf skin
route. Inspect the naked skin's referenced resources rather than identifying the
family from an equipped outfit's embedded body. Changing clothes must not select
another conversion matrix. For a confirmed static body, weight and available actor traits remain
useful without inventing BodySlide inputs. Unknown bodies remain unsupported
unless their configuration is explicitly verified. A universal classifier is
not part of this analysis or the owner's current compatibility scope.

External evidence: `Builds/claw-bijin-analysis-20261118/analysis.json`,
`binary-plugin-proof.json`, `weight-endpoint-proof.json`, official AIO readback
and the original archive/extraction logs. No third-party asset is copied here.

## Actual SE lifecycle and optional skin patch

The owner then requested installation in TEST SE. Native MO2 installation selected
AIO/CBBE and original appearance options from the original archive. All200 selected
payload files, source IDs11287/30612, provenance and native Installed accounting
were verified. Only the CLAW source profile's three lists changed; other profiles
and gaming libraries were preserved. Tests used FHD, owned dynamic references in
a disposable NEW world and the same qualified native/observer composition.

Adrianne (Skyrim.esm:013BB9, Imperial, weight80) and Lisette
(Skyrim.esm:013297, Breton, weight50) completed human→wolf→owned save/load→human.
All31 target values matched the external native evaluator at eight observations;
source values, available traits, weight and selected CBBE matrix persisted.
Missing face inputs remained unavailable: this is partial facial-source coverage,
not full facial equivalence or nonzero human BodySlide deformation acceptance.

The unpatched run exposed the skin-route gap: actual human geometry/material
inventories were available, but wolf inventories were unavailable. An independent
[private patch builder](../resources/compatibility/bijin/README.md) adds only
Skyrim.esm:0CDD87 to the14 original skin armature lists. All original payload
bytes are recovered by removing that one field; official Spriggit roundtrip
checks the14 overrides. No original Bijin file, NPC, DLL, matrix, mesh or texture
is edited. Generated vendor-derived records remain outside Git and releases.

With that sole patch, run20261118-180157-d6f279 passes the unchanged24-step case:
all four wolf inventories contain15 actual geometries, including BODY, HEAD,
claws and tail fur; twelve coat geometries are managed. All four human inventories
contain the original ten Bijin geometries/materials, including both returned
characters. Independent actor/base race reads confirm Imperial/Breton restoration
and weights80/50. Exit0, full restoration/collection and268 cold pins pass.

Do not infer invisible bodies from source-name lookup alone: the engine renames
weighted human geometry with ARMA/skin IDs and weight, while wolf BODY/HEAD names
are capitalized. The actual bounded geometry/material traversal supplies the
positive evidence, with independent actor/root/race bracketing. This is engine
model availability, not rendered pixels, artistic quality or physics acceptance.

The first attempt stopped on an omitted reference-name preparation before subject
capture; the next two retained numerical success and unresolved model evidence.
All four starts/restorations remain accounted; cumulative18 November starts are15.
`Builds/claw-bijin-game-20261118/BIJIN-ACCEPTANCE.json` records exact scope.
Only these two AIO/CBBE NPCs are game-qualified with this optional private patch;
fourteen structural overrides do not qualify every character or UNP installation.
