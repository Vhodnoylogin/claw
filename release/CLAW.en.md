# CLAW — Configurable Lycanthrope Anatomy and Weight

A werewolf body you can shape with named morphs for every region and distinct male/female bodies.
This first release is **resources for modders**. It provides meshes, named TRI morphs
and the base plugin; your integration supplies the controls and decides which actors
receive morphs. OBody, automatic distribution, presets and an MCM are not included.
Version 0.6.2.0 uses each sex's low-weight (`_0`) shape at every actor weight.
Weight-dependent geometry is deferred; named morphs remain available.

CLAW is an **add-on to [Elegant Werewolf Replacer](https://www.nexusmods.com/skyrimspecialedition/mods/93336)**,
not a replacement for it. Elegant gives the look; CLAW adds everything Elegant leaves out.

## What it adds

| | Elegant alone | with CLAW |
|---|---|---|
| male/female weight endpoints | no body-shape variation by weight | matching `_0` and `_1` files per sex; weight does not change the body |
| morph files | none | 24 male / 25 female named sliders |
| female model record | points at the male mesh | points at the female mesh |
| weight slider on the beast armor | disabled in the game record | enabled for compatibility; fixed geometry in this release |

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

## Resource contract

All mesh and TRI files are under `Meshes/Actors/WerewolfBeast/Character Assets/`:

| Files | Purpose |
|---|---|
| `malebodywerewolf_0.nif`, `malebodywerewolf_1.nif` | identical male low-weight geometry at both endpoints |
| `femalebodywerewolf_0.nif`, `femalebodywerewolf_1.nif` | identical female low-weight geometry at both endpoints |
| `malebodywerewolf.tri`, `femalebodywerewolf.tri` | sex-specific named body morph data referenced by the NIF BODYTRI metadata |
| `CLAW.esp` (archive root) | override of Skyrim's `NakedTorsoWerewolfBeast` ArmorAddon: enables both weight sliders and selects the female world model |
| `claw-build.json` (archive root) | original build provenance and artifact hashes |

`CLAW.esp` is an override of a vanilla record; it does not create female actors,
distribute bodies or apply morph coefficients. The test companion is not shipped.
The base plugin does not supply a player first-person beast body or VR physics settings.
An integration using these vanilla paths needs the plugin's female model mapping;
an integration using custom ArmorAddons must supply its own correct sex/model mapping.

Install through the mod manager with CLAW winning the body NIF/TRI conflicts over
Elegant. Enable `CLAW.esp`; another plugin overriding the same ArmorAddon must preserve
the intended sex/model paths. Texture and skeleton providers must remain enabled.
For Skyrim VR the working environment uses the compatible RaceMenu VR/SKEE runtime
in addition to its required RaceMenu resources. This does not claim qualification
on other game/runtime versions.

### Named morph inventory

| Morph | Availability |
|---|---|
| `CLAWArmClawLong` | Both sexes |
| `CLAWArmGirth` | Both sexes |
| `CLAWArmPawSize` | Both sexes |
| `CLAWHeadEarSize` | Both sexes |
| `CLAWHeadEarTilt` | Both sexes |
| `CLAWHeadMuzzleLong` | Both sexes |
| `CLAWHeadMuzzleWide` | Both sexes |
| `CLAWHeadSize` | Both sexes |
| `CLAWLegCalfGirth` | Both sexes |
| `CLAWLegClawLong` | Both sexes |
| `CLAWLegDigitigrade` | Both sexes |
| `CLAWLegPawSize` | Both sexes |
| `CLAWLegThighGirth` | Both sexes |
| `CLAWTailFluff` | Both sexes |
| `CLAWTailLength` | Both sexes |
| `CLAWTailLift` | Both sexes |
| `CLAWTorsoBackWide` | Both sexes |
| `CLAWTorsoBellyRound` | Both sexes |
| `CLAWTorsoBreastSize` | Female only |
| `CLAWTorsoChestSize` | Both sexes |
| `CLAWTorsoFlankWidth` | Both sexes |
| `CLAWTorsoGirth` | Both sexes |
| `CLAWTorsoNeckGirth` | Both sexes |
| `CLAWTorsoShoulderGirth` | Both sexes |
| `CLAWTorsoWaistNarrow` | Both sexes |

### Coefficients and ownership

`0` contributes no delta for your key; `1` applies the stored recipe delta. Intermediate
coefficients interpolate the delta. Start integration previews in `0..1`. That is a
reference interval, not a guarantee that every combined or extrapolated shape is safe.
Negative values, values above one and arbitrary simultaneous combinations have not
been qualified as a release-wide visual range. Other mods can contribute additional
keys, so your key's value alone does not describe the final visible body.

Use your own stable key, apply to the intended loaded Actor reference, and request a
model update after changes. Restore your own contribution to zero when your integration
stops controlling it. Do not clear all actor morphs or another mod's keys. Handle actor
3D reloads and race changes in your integration; this resource package has no controller
script or persistence policy.

### Minimal Papyrus integration

These functions can be added to your integration script. Compile against the compatible
RaceMenu/SKSE Papyrus declarations. Choose a stable key belonging to your mod:

```papyrus
Function SetClawHeadSize(Actor target, Float coefficient) Global
    If target == None || !target.Is3DLoaded()
        Return
    EndIf
    NiOverride.SetBodyMorph(target, "CLAWHeadSize", "MyMod.CLAW", coefficient)
    NiOverride.UpdateModelWeight(target)
EndFunction

Float Function ReadClawHeadSize(Actor target) Global
    If target == None
        Return 0.0
    EndIf
    Return NiOverride.GetBodyMorph(target, "CLAWHeadSize", "MyMod.CLAW")
EndFunction

Function ResetClawHeadSize(Actor target) Global
    SetClawHeadSize(target, 0.0)
EndFunction
```

The reset leaves this key at zero; it does not delete other contributions. A storage
readback confirms the coefficient, while the visible geometry is a separate observation.
The runtime test exercised this set/update/read/reset sequence at `0 -> 1 -> 0` on both
sexes for six common morphs and the additional female breast morph, with `1e-6` readback
tolerance. This is evidence for that native API sequence, not a claim that this example
has been built and tested as a separate published mod.

## Adult content

Nothing explicit is visible in this mod. The anatomy is sculpted into the mesh but sits
**entirely under the skin** at rest — only the rim seam stays on the surface, because a seam
must, or there would be a hole in its place — and the morph file here contains no crotch
sliders at all. There is simply nothing to raise it with.

The separate **CLAW - Anatomy** add-on is deferred and is not included in this release.

## Credits and permissions

Elegant Werewolf Replacer by **Wolflady500** and **KaienHash**. The meshes are used with the
authors' permission, on their condition: no textures are redistributed, and CLAW does not work
without Elegant installed. Please endorse their mod — this one exists because theirs does.

The anatomy bones come from XP32 Maximum Skeleton Special Extended by **Groovtama**, used under
the terms of its page.

## Under the hood

CLAW is not a folder of meshes someone edited once. It is built by a journal of operations —
a reproducible sequence that turns the donor meshes into these bodies — so every slider in it can be
traced to the line that made it, and the whole mod can be rebuilt from the sources.
