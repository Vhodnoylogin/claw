# Coat variation: 0.8.5 source candidate

Owner-directed implementation status, 3 November 2026. The source implements
discrete coat distribution and complete texture packaging. This is not a release
announcement or complete game acceptance. The retained six-reference probe has
diagnostic lifecycle and independent co-save evidence for stable choices in one
hair pool and the natural fallback. Independent material ownership and broader
source/pool transitions still need proof. Physics follows working mechanisms;
VR-body work and visual polish are currently deferred by the owner.

## Complete texture bundle

The 0.8.5 packaging path includes all **355 original DDS members** from the pinned
Elegant Werewolf Replacer 2K 2.1 archive: 306 pattern diffuses, 11 shared textures,
28 alternate eyes and 10 Lobo patch textures. The runtime payload also contains
`SKSE/Plugins/CLAW/CoatLibrary.xml` and `CoatPolicy.xml`: 357 resources in total.
The detailed bundle receipt and measured-palette report remain external build
evidence, not game files. Donor archives, developer source and build tools are not
placed inside the runtime ZIP. Generated DDS files remain outside Git.

Each of the 34 patterns is a complete nine-diffuse set: body, head, arms, back,
belly, chest, face, shoulders and tail. Select that set as a unit for an actor.
The 306 named diffuse files contain 124 unique byte payloads, but shared bytes do
not make distinct markings interchangeable: Black ALT changes all seven fur maps
while retaining Black's body/head, and Silver ALT differs in five map roles.
Mixed-pattern heads, torsos or fur layers are outside this implementation.

`coat_bundle.py` streams pinned archive members, validates complete coverage,
sizes, CRCs and DDS headers, and writes controlled destinations. It binds the
real measured-palette report and reconstructs the runtime catalog exactly during
verification. The package builder consumes only the 357 runtime resources,
checks captured size/SHA256 against the receipt and installs them for every
body-family selection. End users install the normal CLAW archive; they are not
asked to extract another archive with a development helper.

Pattern maps and alternate eyes/Lobo textures use separate CLAW paths. The 11
shared resources retain their expected Elegant paths. Bundled alternate eyes and
Lobo textures are **not automatically assigned**, and do not replace an existing
eye or companion choice merely by being present. The pattern adapter changes
diffuse slots on its named body/head/fur surfaces; eyes, mouth and claws remain
outside that per-actor operation.

Elegant's Nexus requirement and credits to Wolflady500 and KaienHash remain at
the owner's request and under the donor's reuse terms. Bundling textures does
not grant a new licence or remove attribution/non-obsolescence conditions. The
earlier permission excluding textures from Git concerns repository storage;
it is not a universal ban on runtime texture use or an unrestricted grant to
replace the donor mod. Keep those scopes separate in publication and credits.

## Selection and tint are separate policies

`CoatPolicy.xml` defaults to `tintMode="original"`. Neutral material multipliers
retain the selected texture set's authored colours. Human skin/hair tint is an
explicit opt-in with `tintMode="linked"`; it keeps the existing separate undercoat
and fur material groups. Multiplicative tint cannot turn a black diffuse white
or guarantee an exact requested RGB.

The default policy has six authored hair pools:

| Pool | Patterns |
| --- | ---: |
| `dark` | 6 |
| `dark-brown` | 7 |
| `brown` | 6 |
| `red-gold` | 4 |
| `grey` | 6 |
| `light` | 3 |

Real readable human hair selects the pool containing the nearest eligible
measured fur colour, compared in linear RGB. A stable saved-reference selector
then chooses a marking within that pool. Membership is explicit appearance data,
not filename inference, another conversion matrix or an OBody preset. This
technical initial policy makes no aesthetic matching claim.

The selection order is manual override, usable human hair, then the enabled
`natural` fallback pool. Its 32 patterns exclude Hyena Spotted and Khajiit from
automatic distribution; all 34 remain available for explicit manual selection.
The fallback covers born werewolves and observed humans whose hair is unreadable.
Skin alone never becomes hair. Genuine skin remains independently available for
linked tint, and no human skin/hair/face source is fabricated for a born beast.
Body/head images already contain painted coat: the undercoat/fur material split
is not a biological pixel mask. Beard/brow inputs, arbitrary recolouring and
artistic tuning remain outside this slice.

## Saved reference identity and lifecycle

Selection uses the Distribution save namespace and persistent actor identity,
not NPC base, runtime FormID, pointer, time or a global RNG. An additive, bounded
`CCAS` version-1 record retains that seed and separate hair/fallback choices.
Existing `CCLR` and explicit-choice `CCPT` version-1 layouts remain unchanged.
Actor/base FormIDs are remapped on load, and CCAS identity/seed must agree with
the owning Distribution state; conflicting records cannot acquire a fresh lease.

A saved choice remains while it belongs to the currently eligible pool. Source
arrival/removal selects the appropriate hair or fallback cache. Clearing a manual
override returns to that policy without erasing saved automatic choices. An
absent policy preserves prior nearest-hair/linked-tint behavior; an invalid
policy disables automatic selection rather than broadening its allowed pools.
Manual catalog choices remain separate from automatic pool restrictions.

`GetCoatPattern` reports the requested manual override; `GetAppliedCoatPattern`
reports the successfully bound pattern. Status identifies its origin and tint
mode. Queue admission does not establish application. Private material/texture
leases still yield to a later writer and restore only their own surviving work.

## Remaining acceptance

An offline ownership correction additionally captures readable initialized
material state after engine setup. Later in-place changes to normal/rim/specular
textures, UV coordinates, specular/alpha parameters, shader flags or the effect
data identity now yield the property instead of restoring a stale whole-property
copy over that writer. Compared object identities retain their references.
This checks named public fields, not opaque renderer state or arbitrary writes;
an engine change to a watched field can conservatively cause yielding. Actual
engine material ownership and animated/fading behavior still need acceptance.

Probe 18 retained six actor identities/seeds and choices in actual `CCAS` co-save
records, alongside manual selection/clear, neighbor isolation, model refresh,
save/load, return and retransform diagnostics. Two controls used `dark-brown`;
four born references used `natural`. This covers saved data and reported state,
without independently establishing the rendered hair source or material leases.
The [verification record](verification-20261102.md#development-085-coats-and-classic-unp)
preserves the run's termination and later restoration limits. Do not repeat these
already observed facts as wholly missing or promote them to formal acceptance.

Remaining witnesses include manual clear **after** actual load/remap, genuine
hair arrival/removal and migration between pools, additional hair pools,
independent per-surface material/texture ownership, excluded shapes, controlled
unload, and invalid/missing-policy/library controls. Separate requested/applied
choices and captured source availability from independent engine readback.
The bounded read-only surface audit described in [the runtime contract](coat-library.md)
now supplies actual texture-set paths, bound diffuse resources and exposed material
fields. Its source checks are complete; actual main-task sampling remains a game
check. The portable coat fixture now requires fresh samples around manual changes
and after post-load clear, with duplicate-name and generation limits explicit.
Offline parser, record-codec, bundle and installer checks do not prove rendering;
body-morph success and universal compilation do not establish coat, AE or VR
acceptance. The unsuccessful 3 November tool attempt collected no actor or coat
snapshots and adds no coverage here. The owner has since authorized game tests;
the next attempt waits for Skyrim-Foundation to release its MO2 migration and a
verified test-SE environment. This is shared-environment custody, not an owner
ban on launches or missing coat implementation.

Keep mechanical coverage separate from process termination and restored-state
evidence. Diagnose any new failure from actual evidence without speculative
third-party patches. Publish only accepted runtime and accurate documentation;
released source/test fixtures belong on main and unfinished work remains on the
development branch. Visual calibration, mixed-pattern seams and new artwork are
not completion criteria for this technical slice.

See [texture preparation and runtime contract](coat-library.md),
[matrix contract](matrix-contract.md) and [owner roadmap](roadmap.md).
