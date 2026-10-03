# CLAW - Anatomy

The adult add-on for [CLAW — Configurable Lycanthrope Anatomy and Weight](https://www.nexusmods.com/skyrimspecialedition/mods/).
Two morph files, five megabytes, nothing else: no meshes, no plugin, no scripts.

## What it does

The base mod's bodies already contain the anatomy — it is sculpted into the mesh and sits
entirely under the skin. What the base mod does not contain is any way to bring it out: its
morph file has no crotch sliders. This add-on supplies exactly those.

| | male | female |
|---|---|---|
| base mod alone | 24 sliders | 25 |
| with this add-on | **28** | **26** |

Added: `CLAWCrotchSheathState`, `CLAWCrotchSheathLong`, `CLAWCrotchSheathKnot`,
`CLAWCrotchBallsSize` for the male, `CLAWCrotchVulva` for the female.

Nothing appears on its own. At zero the body looks exactly as it does without this add-on —
the sliders are the only way anything shows, and they start at zero.

## Requirements and load order

Requires the base mod **CLAW — Configurable Lycanthrope Anatomy and Weight** and everything it
requires. This add-on must sit **below the base mod**: it replaces the base morph files.

The geometry is untouched — it is the same body in both versions, and the build verifies that
by comparing the meshes of the two sets against each other.

## Why it is a separate mod

Splitting by morph file rather than by geometry keeps the download honest. The geometry is one
and the same; a separate "adult geometry" would mean a second copy of all four bodies —
thirty-four megabytes for eight hundred vertices — and a mod manager overrides whole files, so
the form cannot be added to someone else's mesh anyway.
