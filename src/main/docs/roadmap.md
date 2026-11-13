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

## Active development sequence — owner update, 12 November

### Current scope — owner update, 13 November

Only CLAW motion physics and the verified 0.10.0 release are active. Finish
provider binding, controlled rig motion and cleanup checks, then validate the
actual release archive, integrate released sources into main and publish the
matching GitHub and Nexus release. The broader sequence below is paused;
Living Physique, Morphbench development, VR body, contacts and anatomy are not
part of this current task.

Deferred tooling: extend MO2 API Bridge with Qt-native inspection of its own
windows, active modal text and enabled buttons, plus identity-checked actions.
Obtain the original Bridge chat's current release/candidate status before
planning implementation. No Bridge development, build or release is authorized
by this backlog entry. Existing Win32 window enumeration does not establish
that a Qt dialog has no buttons.

The original Bridge chat confirmed on 13 November: released 2.3.6; unreleased
2.3.7 on develop at e643698. Native candidate acceptance and the investigation
of inactive-profile serialization remain open. General Qt inspection is absent
from both versions and is not a committed part of that candidate's release.
Retain this as a separate deferred request, rather than a dependency of 0.10.0.

Finish shared mathematics and the first checked Living Physique RC, then the
CLAW physics/Morphbench configuration work and offline qualification. Prepare
VR body/contact and optional anatomy candidates before one ordered game batch:
SE technical checks, physics, Living Physique and anatomy; then VR test-tool
self-test, VR body and VR contacts. Build local packages and unpublished drafts
only for their verified scopes; comparison screenshots follow these checks.
This sequence supersedes waiting for a separate VR/contact release to begin
anatomy work. It does not count unrun or blocked checks as successful.

## VR body and contact colliders

Implement first-person VR body dispatch, visibility and synchronization. Then
complete morph-responsive contact colliders for both flat and VR gameplay:
coarse useful flat-game contacts with fewer colliders and detailed hand-consistent
VR contacts with mandatory ear and tail coverage.
Static Morphbench placement and numerical fitting support development but do not
replace actual engine collision and headset tests.

The VR body is a component in this same repository at
`src/main/components/vr-body/`, with tests under
`src/test/components/vr-body/`. Move the existing experimental VR sources and
their build/import/package references together when that phase starts; no new
product repository is needed.

## After the VR body and colliders: separate adult supplement

Plan a separate optional adult werewolf anatomy supplement, including penile
anatomy and its physics integration. The current owner-authorized offline slice
includes this candidate after the VR body/contact preparation. It remains a
separate optional component, with no accepted implementation or release implied.
Its component directory is `src/main/components/adult-anatomy/`, with tests under
`src/test/components/adult-anatomy/`, in this same CLAW repository. Keep it
optional and isolated from the base runtime package.

## Deferred

The independent Morphbench comparison-plugin UI/public update remains deferred.
The final visual review covers female breast refinement, musculature, lean/bulky extremes, cosmetic
self-intersection tuning and new morph authoring. Fix functional
defects such as missing textures or broken animation as they are found.

## Immediate corrections — owner update, 13 November

Complete hair-to-coat hue matching now, while motion physics remains the main
priority. Preserve RGB through the matrix and let the configurable material
adapter choose a colour group before seed variation within that group. Validate
the actual captured hair source and applied material in game; a record-colour
regression alone does not establish the rendered result. The available Elegant
palette limits the closest possible match. Do not manufacture examples with
manual coat assignments.

The current Living Physique before/after images were rejected by the owner as
visually indistinct and must not be used as release demonstrations. Their
technical evidence and originals remain retained.

For physics, distinguish provider-global stepping from target-rig movement and
visible model deformation. A read-only FSMP pre/post-step witness observed 129
completed steps in 2.16 seconds on 13 November with freezeTime and UI pause false;
this does not qualify a particular bone, collision or Morphbench correspondence.
Investigate rig motion/writeback next. Reuse the successful Body Pouches VR launch
sequence: the later failed run was interrupted by a reversed SteamVR room-setup
takeover order, rather than calibration 201 alone proving VR unavailable.

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
launch/tool defects locally for a later owner-approved handoff. The owner's
13 November exception permits one status request to the original MO2 API Bridge
chat; other testing coordination remains local. Keep FHD and the accepted
paired-scene rules.
