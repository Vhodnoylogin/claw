# Human appearance to individual coat tint

Development feature, 1 November 2026; not a published or game-accepted feature.

CLAW captures human colour before transformation. The inherited face NPC's QNAM
supplies record skin RGB; HCLF supplies record hair RGB. A unique consistent
loaded HairTint material takes precedence for hair, using RaceMenu's documented
local implementation convention of twice the normalized RGB components.
Valid rendered RGB is normalized to the same 8-bit-per-channel palette used by
CCLR v1 before ambiguity comparison, storage and first application. QNAM and
record hair colours already use that palette. A free-float third-party hair tint
is deliberately rounded once; saving/loading never introduces a second colour
policy or shifts the resulting packed coat tint.
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
the engine material factory creates a temporary FaceGenRGBTint material, or a
HairTint material for an existing HairTint donor. `CopyBaseMembers` preserves
the donor textures, UV transforms and lighting parameters, then CLAW assigns
the packed RGB directly. `SetMaterial(temporary, true)` creates a distinct
engine-owned copy on the private property. The factory temporary is destroyed
and deallocated through its captured thread scrap heap; it is never adopted
as a long-lived material. Default/FaceGen donors disable Face and enable
FaceGenRGBTint, while HairTint donors retain their feature. After binding,
the property's virtual `FinishSetupGeometry` initializes its shader through
the active runtime's vtable. No private runtime relocation or SKEE colour
mutation is used. Failure restores still-owned properties and records a reason.
No persistent SKEE override or NPC base edit is registered.
Model generations are retained by NiPointer, avoiding
reused raw-root-address aliases. A later property writer wins until model reload.
Restoration rebinds only properties still owned by CLAW; it never undoes a later
writer's property. Alpha properties and texture slots remain intact.

`appearance::Runtime` owns its surface leases, actor entries and collection
privately. Distribution uses lifecycle operations, a read-only `status(id)` and
`retainIf(predicate)` when rejecting stale loaded identities; it does not inspect
or mutate the collection. The caller retains the existing Distribution lock.
Yielding to a later material writer is private runtime state, independent of its
display message. RGB validation, palette conversion and tint composition remain
pure functions in `ColourMath.h`. This boundary changes no CCLR bytes or Papyrus
API, and introduces no engine cleanup in a destructor: reset/revert remains an
explicit lifecycle operation.

The second installed mechanism run reached the material-isolation guard for all
six wolves. The first corrective candidate subsequently crashed on its first
transformation in runs four and five. The fifth run's actual dump shows stock
SKEE key7 constructing a tint material whose GetFeature vtable entry resolves
to the non-executable SKEE module base. The engine-factory path above avoids
that constructor entirely, without replacing or patching RaceMenu. This new
candidate compiled and passed nine native suites but is not yet game accepted.
Earlier morph-vector parity does not qualify colour or this corrective path.

Each clone receives a newly allocated boolean `NO_TINT=true` extra. An inherited
extra is removed only from the clone's independent array; its object is never
mutated. This protects the separate skin/fur colours from SKEE's ordinary
`UpdateModelColor_Recursive` skin/hair refresh. CLAW's direct private-material
write does not use that recursive guard. Application verifies the actual material
tint at the stored 8-bit palette precision, the guard and private ownership.
The unchanged-model fast path checks those invariants too: a later writer that
changes the property, removes the guard or changes its tint wins until reload;
CLAW does not repeatedly fight it. These source-level protections still require
the runtime checks below, rather than proving colour persistence by compilation.

After private shader initialization, each surface retains the exact material, private
guard and texture-set identities. Material uses its `BSIntrusiveRefCounted`
smart-pointer policy; the guard and texture set use `NiPointer`. Fast-path and
restoration checks reject identity changes before inspecting the live tint.
Consequently SKEE's supported texture write, which replaces a texture set inside
the same material while preserving RGB and `NO_TINT`, also wins. The retained
witnesses prevent pointer reuse from making a replacement look unchanged. This
bounded lease does not claim to detect arbitrary edits to every shader field or
in-place changes of texture paths inside an unchanged texture-set object.

Separate bounded `CCLR` co-save records retain human colour, base/sex identity and
source availability, never engine pointers. They are accepted only alongside a
valid Distribution actor record and cleared on quarantine/deletion/revert.
`GetAppearanceStatus` exposes application or unavailability; body-morph success
does not establish colour success. Required game checks include two actors
sharing a base, both sexes, transform/return, 3D rebuild, save/load, untouched
control/excluded shapes, and actual rendered tint/alpha inspection.
Also refresh the wolf's ordinary skin/hair colour while it retains the same
model, then verify independent expected skin/fur RGB, all private guards and an
untouched human/control actor. After returning to human, no CLAW clone or guard
must remain attached to the human model. On a new wolf model the clones and
guards must be newly owned; restored co-save source colours must produce the
same packed tints.
Test a supported SKEE texture write and a material/guard replacement preserving
the same RGB: CLAW must yield and restore/reset must retain the later property,
material and texture choice rather than rebinding its donor over that writer.

Primary implementation references are the pinned public SKEE
`IPluginInterface.h` Override v2 contract, `ShaderUtilities.cpp` key7 shader
conversion and `PresetInterface.cpp` HairTint decoding, plus CommonLib TESNPC and
shader-property cloning APIs. No third-party runtime has been patched.
