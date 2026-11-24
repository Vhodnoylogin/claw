# CLAW development roadmap

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

Keep each CLAW body and appearance component installable with physics turned
off. Default to the static model and make optional motion or contact support
an explicit choice for players.

For the 0.11.0 main mod and the future VR add-on, retain FSMP tail motion
as an option. VR contact colliders remain required for ears, tail and chest.

## Deferred CBPC actor rebinding

Actual 13 November case142827-3a903c transformed a human NPC successfully, but
CBPC1.7.3 kept updating human Things and created none of the eleven requested
wolf drivers. Its installed public interface provides parameter refresh, not a
proven per-actor rebind. Retain the exact failed test/API evidence and pursue a
provider-supported invalidation contract separately. Do not ship guessed refresh
calls, a global reset workaround or an unverified CBPC option. The independent
FSMP mode passed the full both-sex human-origin lifecycle and remains0.10 scope.


## Active development sequence — owner update, 12 November

### Resumed CLAW scope — owner update, 18 November

Product ownership of Living Physique, Morphbench and MO2 API Bridge returns to
their original chats with the rechecked 17/18 November handoff packets. Shared
numerical source stays CLAW-owned and is consumed through immutable pins. An
ordinary RaceMenu interoperability check does not create a private LP dependency.
Morphbench still owns its open tool-to-game physics correspondence gate.

Investigate Khajiit/Argonian sources and individual BHUNP bodies before deciding
mixed-family installer behavior. The new optional explicit naked-skin binding
adapter is described in [mixed-body-families.md](mixed-body-families.md). Preserve
one matrix per actor, saved/manual ownership and born-wolf fallback; do not infer
families from installed plugins or outfit meshes. Offline selection tests do not
qualify simultaneous mixed bodies in game. Keep the current installer until that
acceptance is completed.

Khajiit/Argonian static records and regression coverage are recorded under
src/test/docs/beast-races-20261118.md. Follow up partial FaceGen semantics,
hair/feather versus pelt/scale colour provenance and direct source-tail inputs;
do not claim those inputs are already represented. Broader implementation order
remains motion-physics follow-up, female breast work, VR body/contacts, optional
anatomy and final artistic review. Nexus removal/restoration is separate from
local development; no new public release is authorized by this resume.

The next 18 November development slice adds a reproducible six-base test fixture,
explicit custom-skin wolf routing, the native `body-family` setup diagnostic and
standard BodySlide empty-UV-section compatibility in the strict TRI helper.
Source/record checks and private unique-path BHUNP preparation are complete;
three two-actor lifecycle plans were prepared. Subsequent direct SE checks passed
both sexes of Khajiit/Argonian and a declared simultaneous CBBE/BHUNP skin setup:
twenty steps and eight complete matrix observations per case. The retained first
mixed attempt failed on unavailable FaceData in the all-zero Nord fixture;
correcting the authored fixture preserved the assertions and passed the next
case. See src/test/docs/development-20261118.md for exact pins, failed preparation
attempts and limits. Nonzero human-morph bases, actual rendered resources and
arbitrary body swaps remain distinct from this numerical lifecycle evidence.

Later on18 November the owner explicitly made this chat the sole game operator
and stopped further Polygon contact. Complete the existing preparation barrier
with independent settlement, then run the bounded tests here with the same
native custody, startup, snapshot/restoration and evidence requirements. Prepared
plans and an installed DLL still do not count as actual game acceptance.

The owner clarified that prohibiting unsupported individual-body mods means
withholding a compatibility promise, not actively disabling them. Do not turn
this limited compatibility work into universal body classification. Preserve
the single default per sex and use explicit data bindings only for known paths;
an authored fixture does not qualify a third-party follower.

On19 November the owner confirmed this support boundary: arbitrary standalone
NPC/follower bodies remain unsupported by default. Known configurations require
explicit tested compatibility; shared filenames or RaceMenu morph values cannot
establish a universal family identifier. Do not continue classifier or installer
multiselect work on this basis. The Bijin result keeps its exact tested scope.

The current-v4 [breast attachment audit](breast-attachment-audit.md) now measures
collar and coat-root offsets across combined morphs and controlled poses. A
limited-training weight fit regressed other states and was rejected. An expanded
private fit improved one six-vertex card without measured protected-state
regressions, but its whole-belly benefit is small and the candidate is not shipped.
Continue full-state attachment work and game correspondence; static offset,
fade-policy, posed drift and actual rendered separation are different findings.

### Completed release scope — owner update, 13 November

The 13 November scope was CLAW motion physics and the verified 0.10.0 release.
Provider binding, controlled rig motion, cleanup and final archive checks were
completed before matching GitHub/Nexus publication. The 18 November resume above
supersedes that completed task's stop; it does not reopen another product's
ownership. Historical publication is not a present Nexus-availability claim.

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

## Aesthetic work split

Start this phase after the core appearance and body-family checks, flat-game
physics, VR body and collision checks, and the optional anatomy component have
completed technical verification. The 23 November owner update permits item 2's
colour-mechanism analysis and offline prototyping before this gate. Items 1 and
3 and aesthetic tuning remain behind the gate. Restore ordinary technical
function, such as a missing coat texture, during the earlier work.

1. Audit self-intersections on the actual wolf meshes. Compare neutral states
   with individual morph extremes and targeted combined extremes. Prioritize
   reproducible new penetrations and preserve existing shapes while fixing them.
2. Improve hair-to-coat colour matching from measured available textures. Verify
   which selection is controlled by hair and skin, and document the difference
   between selecting authored textures and applying a continuous shader tint.
3. Review human-to-wolf shape mapping, proportions, limits and new morphs jointly
   with the owner. Start this review together after the two independent checks.

The independent Morphbench comparison-plugin UI/public update remains deferred.
Fix functional defects such as missing textures or broken animation as they are found.

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

For every CLAW game run, retain the Autotest `run-review.json` with the original
steps and terminal evidence. For a frozen executor without this report, read its
retained directory with `python -m skyrim_autotest.run_review`. Use the observed
startup, tool, shutdown and restoration behavior to propose improvements to the
general executor. Keep the CLAW feature result and Autotest findings distinct.
Develop the tool from these observations alongside the feature work.
