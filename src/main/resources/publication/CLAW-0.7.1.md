# CLAW 0.7.1

Installer-only update of 0.7.0. Game files, conversion matrices and gameplay
are unchanged.

## File description

Human presets shape male and female werewolves.

## Changelog

- Fixed the XML encoding error during FOMOD installation with Vortex.
- Separated male and female body selection into individual installer screens.
- Kept both supported female body choices available; installed markers recommend
  a default without blocking manual selection.

## Supported choices

Male: HIMBO. Female: CBBE or CBBE + 3BA. These are the existing 0.7 game inputs;
Vanilla, BHUNP and the new mechanisms belong to 0.8.0.

## Reproduction and verification

`src/main/python/build-tools/build-fomod-update.py` accepts only the pinned
runtime-only 0.7 archive or its encoding-only hotfix and changes the two FOMOD
XML members. All other member contents remain byte-identical. Generated archives
and verification reports stay outside Git. The installer is checked through
Vortex's XML preprocessing, its primary schema and all four original runtime
payload selections across the seven declared installer runtime boundaries.
This installer update adds no gameplay-test claim.
