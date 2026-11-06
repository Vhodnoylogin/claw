# 6 November: mixed-origin coat lifecycle

The alpha repair uses the universal minimal game DLL SHA256
`6e2998f2b5049ef804895810f2904f463433f65cd24cb6803ec43674288291fc`.
Its compiled source is the isolated `86d76a3` tree, including the captured-stature
correction from `c209d006`. The matching code was transferred to the existing
development branch as `60e2679` and `65aefd6`; released `main` is unchanged.
No fitted-physics model or altered RaceMenu library is included.

## Reproduced defect and correction

Q10, run `20261106-164049-08f525`, reproduced loss of a born-female coat. The first
failed predicate observed BODY property alpha changing from `0.92416644`
(`0x3f6c962c`) to `1` (`0x3f800000`). The observation does not identify its writer.
The old complete-state comparison treated this opacity change as lost ownership;
rollback consequently left the changed BODY private material while restoring other
surfaces. Q10's operator baseline failed; its successful tooling bootstrap is not
coat acceptance.

Coat ownership now separates finite live property alpha from coat content.
Material alpha, flags, material/property/guard identities, tint and texture checks
remain strict. Rollback carries current opacity on a private donor-property and
material copy where necessary, without changing the retained shared donor.
The engine setup callback is followed by property/material identity checks before
the opacity write; a later replacement is preserved on either callback outcome.

Eight native CTests passed, including the actual alpha pair and failure/foreign
replacement cases. An actual-header probe rejects that pair with the old lease
comparison and accepts it with the new comparison. These checks use fake engine
objects; real shader behavior is covered only by the following game trial.

## Q11 game evidence

Run `20261106-172028-514f48` used Skyrim SE, the dedicated CLAW profile at
1920×1080, HIMBO/classic UNP, 20 enabled mods and 21 plugins. Physics remained
disabled. Its born female and human-origin male were independently created and
frozen; only the male received the human refresh and race-change sequence.

All 13 prelude commands and eight operator phases passed, with 124 unique
commands/events within the declared limit of 152:

- Automatic choices: born female Valley Black, transformed male Himalayan.
- Independent manual overrides: male Black; female Black, then Timber.
- Model refresh preserved both requested and applied choices.
- One owned ESS/SKSE pair was saved and loaded; both current actor remaps and
  new world/model generations were verified.
- Clearing the female override restored exactly Valley Black while the male
  retained its explicit Black choice.

Fourteen fresh, chunked material audits were independently decoded and checked.
Every audit covered all 12 managed surfaces, actual diffuse paths **and bound
resources**, private ownership/guards, neutral tint and finite alpha. Maximum
sample age was 1217 ms within the unchanged 2-second limit. Actual excluded
surface multisets contained 3 or 8 entries; preservation was compared only within
the same observed root and world. Refresh retained the same roots; loading
created the separately witnessed new generations. No first-yield event occurred.
The trial did not directly record a new numerical fade pair.

The game ended through normal menu shutdown. Independent review verified 121
restored targets and backups, all 5874 registered pin rows, packet/archive files,
owned process termination, original profile/INI/FHD and RootBuilder restoration.
The exact reservation was then released. The formal packet projects one tooling
bootstrap; the operator checks above have separate raw evidence and review.

Technical review SHA256:
`19bf2d7c4ecf33d56b088a638f0d5503caa0dca4e106f89da18a8553e12a8292`.
Restoration review SHA256:
`056999471e93afc84a06e956c849f7953d12ff26f83030707d5bc7dc9cb159ac`.

## Saved source and deterministic choices

A separate bounded parser checked the actual owned ESS/SKSE hashes, actor/base/VM
identities and saved colour/automatic records. The born female had no CCLR record
or hair choice and retained `natural / valley-black`; the male retained human hair
RGB `[48,35,33]` and `dark-brown / himalayan`. Both saved namespace/identity seeds
agreed with the retained independent Python selector. Manual CCPT overrides
coexisted with those cached automatic choices in the save.

The actual compiled serialization sections were compared with the retained
decoder's layout before analysis. Twenty-three retained parser tests and six Q11
negative cases passed. This is independent Python arithmetic, not execution of
the native codec/selector. Saved desired choices alone do not prove a shader or
absence of earlier human history; the creation/prelude/audit evidence supplies
the separate live association.

Source analysis SHA256:
`1b9618d4b1b39e27ef7aab3a1c2ef86292450bf27d687593b6bd63d8db6086fc`.

This qualifies the bounded SE composition and observed patterns. It does not
establish all 34 patterns in-game, AE/VR behavior, visual quality, physics or
collision fit. Human stature's new reference-scale calculation still needs its
own explicit scale-contrast game check.
