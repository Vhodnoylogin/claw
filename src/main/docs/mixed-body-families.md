# Per-actor body families

This development candidate adds optional explicit skin-path bindings. It is not
part of released 0.10.0, has no mixed-body gameplay qualification yet, and does
not change the installer into a multiple-choice body selector.

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

Native tests exercise default/custom selection, shared zero-capable inputs,
case/path identity, ambiguity, malformed files and preserved copied matrices.
They do not establish installed-game selection. Before offering installer mixed
mode, test simultaneous CBBE/3BA and BHUNP actors with independently verified
skin/NIF/TRI identities through human capture, transformation, model refresh,
save/load and return. Include initially-wolf, unavailable/zero morph, manual
override and body-change cases. Confirm source preservation and exactly one
applied projection for each actor.
