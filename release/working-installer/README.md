# CLAW - Configurable Lycanthrope Anatomy and Weight

Release 0.7.0.0 (31 October 2026): expressive male/female body morphs and
human-to-werewolf conversion matrices. This installer preserves the exact body,
native DLL, scripts, plugins and mappings exercised in the 31 October SE tests.
The owner subsequently confirmed visible differences across all six comparison
presets. This confirms contrast; final proportions, breast shape, fur colour and
other appearance refinements remain development work.

**HIMBO male bodies and CBBE female bodies are required for this release.**
The female choice is CBBE, or CBBE with its 3BA extension; 3BA also requires
CBBE. Install these bodies and their complete author-declared dependencies as
separate mods. Vanilla human bodies are deferred to the backlog and are not
supported by this release.

Install with a FOMOD-capable mod manager. The wolf resources and human morph
linkage are required components; there is no base-only installation choice.
Declare exactly one installed body combination: **HIMBO + CBBE** or
**HIMBO + CBBE + 3BA**. These choices install conversion mappings; they do not
install human bodies or human presets.
The installer recommends 3BA when `3BBB.esp` is active and CBBE otherwise.
Without that active marker the 3BA choice is unavailable. The choice remains
visible and editable: CBBE is still available when the 3BA marker is active,
because the effective body meshes may differ. Reinstall CLAW after changing
body families, and explicitly rebind existing actors' saved profiles if needed.
The optional **Originally-beast OBody source integration** obtains ordinary
human source values for actors first encountered as wolves.

Keep Elegant Werewolf Replacer installed for its textures and a compatible XP32
skeleton as separate mods; let CLAW's body meshes win. Named morph application
and native linkage need the matching SKSE, RaceMenu/SKEE and Address Library for
the actual game, plus the Microsoft Visual C++ x64 runtime. OBody and its complete dependency chain are needed for the
optional source host. The installer requires active `HIMBO.esp`, `CBBE.esp` and
`RaceMenu.esp` markers and checks active `OBody.esp` for its optional host. These
are checks of enabled plugin markers, not proof of effective body meshes,
compatible DLL versions or the complete dependency chain. The visible body
choice declares the actual geometry conversion to use; the installer does not
identify bodies from common mesh paths or detect game-runtime compatibility.

One CommonLib `CLAWDistribution.dll` serves all declared SE, AE and VR candidate
load boundaries; there are no separate runtime DLL variants. Actual game
mechanism acceptance is **Skyrim SE 1.7.104.0 / SKSE 2.3.1** with official
RaceMenu and HIMBO/3BA. Other SE/AE versions, VR and the CBBE selection retain
offline coverage only. The retained base plugin is light flagged; its VR
loading/dependency combination has not been qualified. Read
[the runtime contract](Docs/universal-runtime.md) before using another runtime.
SE core105 and born27 mechanism checks passed on these exact bytes; the original
failed bounded attempt and incomplete canonical collection coverage remain in
[the verification record](Docs/verification-20261031.md).

The existing HIMBO, CBBE and 3BA XML calculation profiles remain separate;
this installer does not implement one unified matrix or change their arithmetic.
Wolf presets are conversion matrices. An all-constant matrix defines an
independent wolf. Existing saved matrices remain authoritative until explicitly
rebound. The four new lean fields and repaired growth fields use bounded 0..1
coefficients; each sex still has equal neutral low/high weight endpoints.
See [the matrix contract](Docs/matrix-contract.md) and
[the body recipe](Docs/expressive-body.md).

This working archive contains no test actors, human body meshes, textures,
skeleton, physics configuration or first-person VR body. `test_CLAW` is a
separate optional testing archive. Screenshot underwear and room lighting belong
to that test setup and its human-body dependencies. Donor credits: Wolflady500
and KaienHash (Elegant Werewolf Replacer).

`Source/` contains matching native source, current body-authoring resources,
pinned dependency sources and rebuild instructions. `NOTICES/` retains licenses
and source attribution. Neither directory is selected into the game by the
installer. Do not copy all archive folders into Data manually.

## Changes from Nexus 0.6.2.0

* Human morphs now drive each actor's own werewolf form, with body-family
  conversion matrices for HIMBO, CBBE and 3BA. Ordinary human presets remain
  the source; no separate wolf-shape preset pack is required.
* Lean fields and stronger growth fields make thin, muscular and heavy shapes
  more distinct. Male collar and female breast/axilla surface repairs are included.
* The optional OBody source host covers newly encountered, originally-beast
  actors while retaining OBody's assignment and blacklist rules.
* One universal CommonLib DLL and one body-selecting FOMOD replace separate
  working components. Physics and first-person VR body resources remain deferred.

Upgrade by replacing the previous CLAW installation with this archive through
the mod manager and selecting the actual human body combination. Keep third-party
dependencies installed separately. Existing experimental native CLAW co-saves
retain their saved matrices; reinstalling XML alone does not rebind those actors.
The package version identifies this complete release. Preserved internal native
and body build identifiers describe the tested input artifacts; they were not
changed by recompiling or relabelling game files for packaging.
