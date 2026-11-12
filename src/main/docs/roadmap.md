# CLAW development roadmap

## 0.9.0: core mechanics and external artwork

Read the ten optional coat sets from Elegant Randomized through the game data
view. Keep the installed material if the required set is unavailable. The
CLAW archive contains configurations referencing those external files.
Check both installations, selections, game materials and save/load.

## 0.10.0: motion physics

Complete actual CBPC and FSMP provider binding, actor-scoped activation,
refresh/rebinding, cleanup and motion. Prefer provider-specific adapters and the
existing XP32 skeleton. Compilation, a void callback and animation-driven node
changes do not prove physics simulation. Establish actual provider state and
controlled motion in the game; do not mask uncertainty with qualification flags.

## After motion physics: female breast, then VR body and contact colliders

Improve the female breast geometry and its response to human inputs.
Follow with the VR body and morph-responsive contacts.

Implement first-person VR body dispatch, visibility and synchronization. Then
complete morph-responsive contact colliders for both flat and VR gameplay:
coarse useful flat-game contacts and detailed hand-consistent VR contacts.
Static Morphbench placement and numerical fitting support development but do not
replace actual engine collision and headset tests.

The VR body is a component in this same repository at
`src/main/components/vr-body/`, with tests under
`src/test/components/vr-body/`. Move the existing experimental VR sources and
their build/import/package references together when that phase starts; no new
product repository is needed.

## After the VR body and colliders: separate adult supplement

Plan a separate optional adult werewolf anatomy supplement, including penile
anatomy and its integration. It follows working VR body and contact mechanics;
it is not part of 0.9.0 or 0.10.0 and is not being implemented in this slice.
Its component directory is `src/main/components/adult-anatomy/`, with tests under
`src/test/components/adult-anatomy/`, in this same CLAW repository. Keep it
optional and isolated from the base runtime package.

## Deferred

The independent Morphbench comparison-plugin UI/public update remains deferred.
The final visual review covers musculature, lean/bulky extremes, cosmetic
self-intersection tuning and new morph authoring. Fix functional
defects such as missing textures or broken animation as they are found.

### Visual reference library

Use the different female werewolf body shapes supplied in the Elegant archives
as references when assessing the appearance of CLAW's results. Include the
other werewolf/body/coat mods previously supplied by the owner, rather than
limiting comparisons to Elegant. Recover the existing archive inventory and
technical audits when this stage starts; Werewolf Colour Sync and its Fluffworks
variants are among the previously supplied references. Record each source and
compare equivalent poses and morph states. This is deferred aesthetic work,
not authorization to redistribute reference artwork or begin visual retuning now.

No separate neutral _0/_1 authoring task or synthetic age input is implied.
Every matrix retains actor weight as an explicit input. Human presets remain
OBody's responsibility; CLAW does not randomly distribute conversion matrices.

Testing is performed in the CLAW chat in its dedicated test environment. Retain
launch/tool defects locally for a later owner-approved handoff; send no messages
to other chats during this work. Keep FHD and the accepted paired-scene rules.
