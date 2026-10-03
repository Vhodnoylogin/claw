# CLAW — Configurable Lycanthrope Anatomy and Weight

A werewolf body you can actually shape: a real weight pair, named morphs for every region,
and sexual dimorphism.

CLAW is an **add-on to [Elegant Werewolf Replacer](https://www.nexusmods.com/skyrimspecialedition/mods/93336)**,
not a replacement for it. Elegant gives the look; CLAW adds everything Elegant leaves out.

## What it adds

| | Elegant alone | with CLAW |
|---|---|---|
| male weight pair | one mesh, weight ignored | `_0` and `_1`, slider works |
| female weight pair | both files byte-identical | two genuinely different bodies |
| morph files | none | 24 male / 25 female named sliders |
| female model record | points at the male mesh | points at the female mesh |
| weight slider on the beast armor | disabled in the game record | enabled |

Morph names follow one pattern — `CLAW` + body area + what it does — so the list reads like
a body, not like a glossary: `CLAWHeadEarSize`, `CLAWTorsoShoulderGirth`, `CLAWLegDigitigrade`,
`CLAWTailFluff`, and so on, covering head, torso, arms, legs and tail.

## Requirements

| mod | why |
|---|---|
| [Elegant Werewolf Replacer](https://www.nexusmods.com/skyrimspecialedition/mods/93336) | donor geometry and **all** textures — CLAW ships none |
| [XP32 Maximum Skeleton Special Extended](https://www.nexusmods.com/skyrimspecialedition/mods/1988) | the skeleton the bodies are rigged to, anatomy bones included |
| [RaceMenu](https://www.nexusmods.com/skyrimspecialedition/mods/19080) | NiOverride BodyMorph — the mechanism that applies named morphs |

**Load order matters:** CLAW replaces Elegant's body meshes, so it must sit **below Elegant**
in your mod manager. CLAW ships no skeleton and does not conflict with XP32.

## How to use the sliders

The morphs are applied through NiOverride's BodyMorph, the same way body mods drive CBBE or
HIMBO sliders — by another mod, a menu, or a script. CLAW itself ships no MCM: it provides
the body and the names, not a user interface.

## Adult content

Nothing explicit is visible in this mod. The anatomy is sculpted into the mesh but sits
**entirely under the skin** at rest — only the rim seam stays on the surface, because a seam
must, or there would be a hole in its place — and the morph file here contains no crotch
sliders at all. There is simply nothing to raise it with.

The separate add-on **CLAW - Anatomy** adds those five sliders and nothing else.

## Credits and permissions

Elegant Werewolf Replacer by **Wolflady500** and **KaienHash**. The meshes are used with the
authors' permission, on their condition: no textures are redistributed, and CLAW does not work
without Elegant installed. Please endorse their mod — this one exists because theirs does.

The anatomy bones come from XP32 Maximum Skeleton Special Extended by **Groovtama**, used under
the terms of its page.

## Under the hood

CLAW is not a folder of meshes someone edited once. It is built by a journal of operations —
thirteen steps that turn the donor meshes into these bodies — so every slider in it can be
traced to the line that made it, and the whole mod can be rebuilt from the sources.
