# Bijin NPCs 1.2.1: local compatibility analysis

The owner's downloaded `Bijin NPCs SE 1.2.1-11287-1-2-1.7z` has SHA256
`c862bee6f49dd064d62f8606df074e9125e2e7cf6e84127b7cb3ced7442c83df`
and size159,295,466bytes. Extraction and analysis are external; no installed mod,
profile or original archive was changed. No Bijin game test or compatibility
promise follows from this record. Private extracted artwork/record dumps are
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

The257actual files include98NIFs,125DDS,15ESPs,18JPGs and one FOMOD XML. There is
no TRI, BodySlide project, DLL or packaged script. Public PyNifly independently
loads all twelve supplied body/hands/feet endpoints. They have no attached root/
shape string extra data and no BODYTRI, `.tri` or NiGeomMorpherController marker.
The body headers use BS83; rejection by CLAW's intentionally narrow BS100 editing
helper is unsupported format, not corruption. No helper restriction was relaxed.

UNP torso has6,622vertices; CBBE has3,471. Every torso vertex differs between
its0/1endpoints, and the ARMA enables weight interpolation. This is source evidence
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
route. For a confirmed static body, weight and available actor traits remain
useful without inventing BodySlide inputs. Unknown bodies remain unsupported
unless their configuration is explicitly verified. A universal classifier is
not part of this analysis or the owner's current compatibility scope.

External evidence: `Builds/claw-bijin-analysis-20261118/analysis.json`,
`binary-plugin-proof.json`, `weight-endpoint-proof.json`, official AIO readback
and the original archive/extraction logs. No third-party asset is copied here.
