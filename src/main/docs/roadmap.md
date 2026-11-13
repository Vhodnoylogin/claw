# CLAW development roadmap

## Current owner scope — 13 November 2026

Only CLAW motion physics and the verified 0.10.0 release are active. Complete
provider behavior/lifecycle checks, validate the final installer, integrate its
source into main and publish matching GitHub/Nexus releases. The remaining
roadmap items are deferred; this slice does not resume them automatically.

MO2 API Bridge follow-up is planned separately: Qt-native inspection of MO2's
windows, modal text and enabled buttons, with identity-checked actions. The
original chat reports released 2.3.6 and unreleased 2.3.7/develop e643698. Native
candidate acceptance and inactive-profile serialization remain unresolved.
General Qt inspection is absent from both and is not a committed candidate
feature. No Bridge implementation, build or release is part of this task.

## 0.9.0: core mechanics and external artwork

Read the ten optional coat sets from Elegant Randomized through the game data
view. Keep the installed material if the required set is unavailable. The
CLAW archive contains configurations referencing those external files.
Check both installations, selections, game materials and save/load.

## 0.10.0: motion physics

Ship the checked Faster HDT-SMP motion adapter, lifecycle and cleanup using the
existing XP32 skeleton. Keep CBPC out of the installer until its original-human
rebind problem has a provider-supported solution. Compilation, a void callback and animation-driven node
changes do not prove physics simulation. Establish actual provider state and
controlled motion in the game; do not mask uncertainty with qualification flags.

## Deferred CBPC actor rebinding

Actual 13 November case142827-3a903c transformed a human NPC successfully, but
CBPC1.7.3 kept updating human Things and created none of the eleven requested
wolf drivers. Its installed public interface provides parameter refresh, not a
proven per-actor rebind. Retain the exact failed test/API evidence and pursue a
provider-supported invalidation contract separately. Do not ship guessed refresh
calls, a global reset workaround or an unverified CBPC option. The independent
FSMP mode passed the full both-sex human-origin lifecycle and remains0.10 scope.

## After motion physics: female breast, then VR body and contact colliders

Improve the female breast geometry and its response to human inputs.
Follow with the VR body and morph-responsive contacts.

Implement first-person VR body dispatch, visibility and synchronization. Then
complete morph-responsive contact colliders for both flat and VR gameplay:
coarse useful flat-game contacts and detailed hand-consistent VR contacts.
Static Morphbench placement and numerical fitting support development but do not
replace actual engine collision and headset tests.

## After the VR body and colliders: separate adult supplement

Plan a separate optional adult werewolf anatomy supplement, including penile
anatomy and its integration. It follows working VR body and contact mechanics;
it is not part of 0.9.0 or 0.10.0 and is not being implemented in this slice.

## Deferred

The independent Morphbench comparison-plugin UI/public update remains deferred.
The final visual review covers musculature, lean/bulky extremes, cosmetic
self-intersection tuning and new morph authoring. Fix functional
defects such as missing textures or broken animation as they are found.

No separate neutral _0/_1 authoring task or synthetic age input is implied.
Every matrix retains actor weight as an explicit input. Human presets remain
OBody's responsibility; CLAW does not randomly distribute conversion matrices.

Testing is performed in the CLAW chat in its dedicated test environment. Retain
launch/tool defects locally for a later owner-approved handoff; send no messages
to other chats during this work. Keep FHD and the accepted paired-scene rules.
