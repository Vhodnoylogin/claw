# Per-actor body families

**Support policy:** arbitrary standalone NPC/follower bodies are unsupported by
default. CLAW cannot reliably infer CBBE, BHUNP or UNP from a path or stored
RaceMenu values. Such bodies require an explicitly declared and tested
compatibility setup, including their human morph resources and werewolf skin
routing. Passing the Bijin case below does not extend support to other Bijin
installer variants or other standalone-body mods. The ordinary installer keeps
one default body family per sex; it does not automatically combine families.

This development candidate adds optional explicit skin-path bindings. It is not
part of released 0.10.0 and does not change the installer into a multiple-choice
body selector. A declared CBBE/BHUNP two-actor numerical lifecycle passed in SE;
its exact scope and remaining limits are in the
[18 November verification](../../test/docs/development-20261118.md).

## Why different bodies can coexist

Ordinary CBBE/3BA and BHUNP BodySlide builds write the same
`meshes/actors/character/character assets/femalebody_0.nif`, `_1.nif` and TRI paths.
One winning resource set is used there. Installing both mods does not give that
path two meanings at once. The existing single default per sex fits this setup.

A follower or NPC can instead use its own skin ARMO, body ARMA and mesh/TRI paths,
with matching hands, feet, UV-compatible textures and outfit morphs. Thus a BHUNP
follower and a CBBE population can coexist. BodySlide project presence or an active
ESP alone does not establish which family an actor actually uses. SKEE values
are actor contributions, not a reliable body-family identifier: a zero slider is
still a valid input and some families share names with different meanings.

Standalone bodies are a real compatibility case: the
[Bijin AIO De-Standalone author's description](https://www.nexusmods.com/skyrimspecialedition/mods/72957)
explains replacing Bijin's individual bodies/textures with the shared defaults.
The authored CLAW fixture reproduces the separate-skin mechanism; it is not a
tested compatibility patch for Bijin or a claim that every follower uses it.

There is no universal body-family identifier supplied by this adapter. A common
reader handles NPC/race skins, while data declares their known model paths.
Mods that replace a loaded scene graph without updating those records need a
different observed-resource adapter. Even a known path can contain a different
user-generated NIF/TRI; bindings therefore declare compatibility rather than
proving file contents. Actual TRI morph inventory could support a future family
classifier, but stored RaceMenu values, shared morph names and filename guesses
do not establish one. Do not promise universal detection or require a separate
hardcoded implementation for every ordinary custom-skin follower.

An explicit NPC skin also needs a compatible werewolf ARMA in its armature if
that skin remains selected after transformation. Human-only Nord addons cannot
supply a wolf torso. A compatibility patch can retain its custom human body,
hands and feet while adding `NakedTorsoWerewolfBeast` (`Skyrim.esm:0CDD87`), whose
winning CLAW override supplies the matching wolf model. Race filtering keeps the
human and wolf routes separate. Verify the actual selected skin and loaded model
in game: body-family selection alone does not repair an incompatible custom
skin, and CLAW does not rewrite another mod's skin records automatically.

## Explicit source adapter

CLAW optionally reads `Data/SKSE/Plugins/CLAW/BodyFamilyBindings.xml` at data load.
The [example](../resources/profiles/examples/BodyFamilyBindings.xml) is not loaded
automatically. Replace its fictional follower path with the actual naked body
model path from the NPC's skin ARMA. Both endpoint paths can be declared.

Every referenced profile must exist in the installed `MorphLinks.xml` with the
correct sex. A compatibility installation must provide the required profiles
alongside its bindings. The current ordinary FOMOD installs its selected family
pair; adding a binding alone cannot supply an absent BHUNP matrix.

On **first automatic adoption** in an eligible source form, the main-thread
adapter reads parameterless `Actor::GetSkin()` (NPC skin, otherwise race skin),
filters its body-slot ARMA by the current race and reads their sex-specific
third-person model paths. It does not identify the body from worn clothes,
textures, a nonzero morph, a filename substring, or a wolf mesh. A pure policy
normalizes ASCII path case/slashes and optional `meshes/`, then selects exactly
one explicitly bound profile. Matching several paths for the same profile is
allowed; matching different profiles withholds automatic adoption and logs a
bounded diagnostic. No matrix addition occurs.

Unmapped bodies and actors first observed as wolves retain the installer default.
An unavailable source form cannot establish a former custom body. Malformed,
ambiguous or wrong-sex compatibility data never silently selects a different
custom family. A malformed present document blocks new automatic adoption until
corrected and reloaded; absent optional data preserves ordinary behavior.

The selected link is copied into the actor's existing saved state. Changing XML,
changing clothes, refreshing the model, or later returning from a first-seen wolf
does not replace an already stored/manual matrix. Use the existing asynchronous
`CLAWDistributionNative.ConfigureMorphFamily(actor, profileId)` for an explicit
rebind and inspect `GetMorphFamily`, `GetStatus` and `GetLastError`. Existing
co-save serialization remains unchanged; this is an application adapter, not a
change to shared numerical mathematics.

## Limits and acceptance

This supports explicit compatibility for known separate skin paths. It does not
classify arbitrary TRI files or discover every runtime body-swap implementation.
A dynamically replaced naked mesh that disagrees with the skin records needs
its own observed-resource integration or an explicit assignment.

The [actual Bijin archive analysis](../../test/docs/bijin-npcs-20261118.md) shows
why path bindings are declarations: its UNP/CBBE installer alternatives use the
same private path, and its supplied static bodies have no BODYTRI. Individual
skin routing, family semantics, available morph inputs and wolf-model routing
must not be treated as one inferred property.

The subsequent Bijin AIO/CBBE SE check qualifies two original NPCs through an
owned lifecycle with a separate skin-armature patch. The mathematical core,
family selection, source meshes and original Bijin payload remain unchanged;
adding the missing wolf addon makes the actual wolf geometry available. Treat
this as a model-application adapter boundary, not a reason to add a guessed
body classifier or promise all custom-skin mods. Static human bodies still have
only weight/available-trait coverage. The dated record distinguishes the initial
unpatched observations, private patch, two tested NPCs and untested configurations.

## Check a compatibility installation offline

The development `claw-preset-tool` uses the same catalog and binding policy as
the DLL. Supply the actual installed XML files and naked-skin body model paths
from the source actor's ARMA, one path per input line:

```powershell
'actors/MyFollower/femalebody_1.nif' | & $tool body-family $catalog $bindings female
```

The JSON result names the chosen profile and whether it came from a skin binding
or the default. Ambiguous paths, invalid data and an absent usable default return
exit code 2. A missing optional bindings file retains the ordinary default.
`--source-unobserved` with empty input checks the initially-wolf fallback.
This command reads supplied records' paths; it does not inspect a running game,
prove which resources win in a manager, or change an actor's stored assignment.

Native tests exercise default/custom selection, shared zero-capable inputs,
case/path identity, ambiguity, malformed files and preserved copied matrices.
Source tests alone do not establish installed-game selection. The declared SE
case verifies automatic CBBE/BHUNP selection, human/trait/weight retention and
native parity through transformation, save/load and return. It does not promise
compatibility with arbitrary individual-body mods. Before offering installer
mixed mode, also test CBBE/3BA and BHUNP actors with independently verified
skin/NIF/TRI identities through human capture, transformation, model refresh,
save/load and return, including nonzero human morph bases. Include initially-wolf,
unavailable/zero morph, manual
override and body-change cases. Confirm source preservation and exactly one
applied projection for each actor.
