# Human appearance to individual coat tint

Development feature, 1 November 2026; not a published or game-accepted feature.

CLAW captures human colour before transformation. The inherited face NPC's QNAM
supplies record skin RGB; HCLF supplies record hair RGB. A unique consistent
loaded HairTint material takes precedence for hair, using RaceMenu's documented
local implementation convention of twice the normalized RGB components.
Ambiguous rendered hair falls back to the record with an explicit status.
Eyebrow/beard/head-part textures and FaceGen makeup are not separately sampled.
An originally-beast actor without human observation has no invented colours.

The adapter tints `body` and `head` from skin and the ten named fur/blend shapes
from hair. This is a material grouping, not a claim that every vertex of a mesh
named `head` is a head. Eyes, mouth, claws and anatomy are excluded. The original
Elegant textures remain a dependency and are never modified or redistributed.

Tint is multiplicative: `floor + (1-floor)*humanRGB`, with floor 0.45 for the
underlying coat and 0.28 for fur. This keeps dark coats readable; it cannot turn a
baked dark diffuse into white. Selecting among all Elegant texture variants is
separate unfinished work, not established by this tint implementation. Timber is
the current comparison texture option.

On the game thread, every selected surface must have exactly one matching name
and a supported lighting material. All properties are cloned before binding any;
both property and material must differ from the donor pointers. Failure leaves
the actor unchanged and records a reason. SKEE Override v2 key7 applies transient
per-node colour to these private properties. No persistent SKEE override or NPC
base edit is registered. Model generations are retained by NiPointer, avoiding
reused raw-root-address aliases. A later property writer wins until model reload.
Restoration rebinds only properties still owned by CLAW; it never undoes a later
writer's property. Alpha properties and texture slots remain intact.

Separate bounded `CCLR` co-save records retain human colour, base/sex identity and
source availability, never engine pointers. They are accepted only alongside a
valid Distribution actor record and cleared on quarantine/deletion/revert.
`GetAppearanceStatus` exposes application or unavailability; body-morph success
does not establish colour success. Required game checks include two actors
sharing a base, both sexes, transform/return, 3D rebuild, save/load, untouched
control/excluded shapes, and actual rendered tint/alpha inspection.

Primary implementation references are the pinned public SKEE
`IPluginInterface.h` Override v2 contract, `ShaderUtilities.cpp` key7 shader
conversion and `PresetInterface.cpp` HairTint decoding, plus CommonLib TESNPC and
shader-property cloning APIs. No third-party runtime has been patched.
