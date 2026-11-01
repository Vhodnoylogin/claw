# CLAW — future plans

Owner-defined priorities, revised 1 November 2026. No release dates are promised.

## Active owner queue (latest instruction)

This list supersedes every older release sequence below.

The [current execution and discrete-coat plan](coat-variation-plan.md) records
the verified game11 mechanisms, remaining installation/appearance policy work,
and the order of practical acceptance before physics and VR. Its passed
mechanical coverage is separate from the abnormal process exit after checks.

The current release sequence is the 0.7.0 FOMOD compatibility update, then 0.8.0
for completed mechanisms/body-family choices, followed by demonstrated coat
variation as 0.8.5. The owner clarified UNP/BHUNP as a female family: 0.8's new
matrix targets BHUNP 3.34 Advanced Ver4 with Build Morphs, not classic UNP or a
male UNP body. Installer markers recommend a choice but never block alternatives.

1. **Technical mechanisms:** generic sparse coefficient/function matrices;
   shared game/Morphbench evaluator and independent comparison plugin;
   human-to-wolf body/head/face links, including ears, tail and claws;
   individual skin/fur appearance links; source preservation, transformation,
   model refresh and save/load. Include HIMBO, CBBE, 3BA and both Vanilla sexes.
   Every matrix explicitly supports `$actor.weight`; Vanilla body deformation
   uses weight rather than invented body morphs. Validate exact installation
   choices and actual game behavior. General testing-tool development is outside
   this product queue.
2. **Physics and VR body:** ear/tail/breast motion providers; coarse fitted SE
   collisions, detailed VR contact, morph-responsive collider bounds;
   first-person body dispatch, visibility, morph synchronization and interaction.
   Prefer existing XP32 bones and separate provider-specific adapters. A built
   configuration is not evidence of actual provider motion or collision.
3. **Visual quality and morph authoring:** improve existing morphs and their
   transfer calibration, natural breast shape, lean/growth endpoints and local
   musculature; fix self-intersections and remaining surface defects; develop
   additional or replacement morphs. This work is deferred while mechanisms
   take priority. Do not continue aesthetic iteration merely to call an extreme
   shape attractive.

The previously separate adult-anatomy/physics idea remains deferred and is not
silently added to any of these three current queues. This ordering supersedes
all numbered queue/release lists retained below as historical planning.

### Additional body-family compatibility investigation

The owner proposed UNP-family support on 1 November and supplied the UNP Renewal
(Nexus1699) and BHUNP (Nexus31126) archives for local inspection. After inspection,
the owner explicitly excluded classic UNP Renewal1699 from support. Do not add
a classic UNP matrix or installer option. Keep its archive findings as reference.
Only BHUNP31126 remains planned compatibility work; it is not an implemented or
tested body-family declaration.
BHUNP advertises BodySlide/RaceMenu morph support; UNP Renewal primarily supplies
ready meshes/textures and directs shape editing to Legacy UUNP or BHUNP.
Inspect the actual chosen archive's OSP/OSD/TRI morph names and effective ranges
before authoring a separate female matrix and installer choice. Do not substitute
CBBE coefficients merely because some slider names look similar. The UNP texture
layout alone does not establish support for UUNP/BHUNP morphs.
No replacement body or physics dependencies are installed as part of this research.

### Mechanical scope after the combined queue-two/three scene

The owner requested maximum functional implementation first and moved visual
attractiveness to queue three. Retain appearance observations as deferred
feedback, rather than spending this slice on breast naturalness, attractive
proportions or repeated endpoint calibration. Functional channels, human-source
links, per-actor colour, native/preview parity, persistence and actual provider
motion remain active. Separate muscle and soft-mass channels address a missing
control mechanism; their final artistic tuning remains deferred. Abdomen/thigh
self-intersection is a known mesh defect in queue three, not a completed repair
or a reason to declare unrelated mechanisms nonfunctional. Its bounded partial
repair and captured-pose evidence are retained without further tuning now.

Do not invent an age slider or synthetic age input. An age-related conversion
requires a verified existing readable source; investigate actual game markers
before proposing any implementation.

### First-queue inspection record

The owner confirmed that the new mechanism works after inspecting the current
HIMBO/3BA pairs. The next game run is explicitly for queue two. The inspected
scene verifies that installation and these six transformations, not unperformed
Vanilla, save/load or sex-rebinding cases. No new public release is implied.

The first technical queue implements head/face links, ears/tail/claws and individual colour.
Inventory actual available human and wolf inputs first; route supported traits
through the shared native/WASM matrix kernel and expose the same controls in
the independent Morphbench plugin. Separate muzzle/jaw/head proportions from
ear/tail/claw length and thickness. Missing readable traits need an explicit
fallback. Treat skin and fur as separate materials; investigate per-actor Elegant
texture selection and tint from actual human hair/skin data. A global Timber
installation is a photography setting, not per-actor colour implementation.

The deferred queue-three appearance work improves body shape and calibration: more expressive lean/bulky
endpoints, arm/thigh/abdomen silhouette, natural breast growth and motion physics.
The owner observed that Runa and Mira have similar human breast size but Runa's
wolf breasts are visible while Mira's are almost absent; Lada's human breasts
are only moderately smaller but likewise disappear on her wolf. Preserve this
as a transfer-quality regression case, alongside downward/broad static growth,
axilla continuity and coordinated fur deformation. Do not mistake different
slider names or equal raw coefficients for equal visible breast volume.

The next comparison fixture needs a simple dedicated photo room for all twelve
actors, light neutral backdrops and uniform illumination for both sexes. Retain
the accepted compact pair separation, NeverNude human meshes, AI/collision Off
and numeric placement checks. This room is planned, not built or game-qualified.
The original accepted QASmoke layout remains retained for reproducibility.

There is no separate active `_0`/`_1` body-authoring task. The owner rejected that
item as a misunderstanding. Matrix weight input is first-queue work; creating
different neutral meshes is not implied by it. The body-v2 geometry candidate and
its integration patch are preserved separately, without selecting it for this
first-queue build. No further geometry/calibration work precedes the first queue.

The 0.7.0.0 matrix and visible-contrast slice has recorded SE acceptance; see
[its verification record](verification-20261031.md). The later sections retain
the earlier planning/baseline history and do not override that result. Repository
layout migration is source maintenance; the fresh donor pipeline now reproduces
all six 0.7 body destinations bytewise, without a new installation or game run.
The comparison plugin is now an [independent product](https://github.com/Vhodnoylogin/claw-morphbench-plugin)
with a pinned shared-kernel dependency, rather than a component stored here.

## Historical release sequence (superseded by the active three queues)

The 31 October owner instruction supersedes the earlier six-release estimate.

1. **Current release — authorable conversion and visible body contrast.** A wolf
   preset is an ordered sparse coefficient matrix plus a matching function matrix:
   each human source can affect multiple wolf targets and vice versa. Linear,
   nonlinear and constant cells share one validated C++/preview evaluator contract.
   An all-constant matrix is a standalone wolf preset. Deliver the Morphbench
   **plugin** with two independently rendered human/wolf panels, linked rotation,
   editable human controls, read-only wolf controls, editable/importable/exportable
   matrix, per-cell contributions and current/base vertex measurements. Author
   leaner minima and larger fat/muscular maxima, prioritizing arms, thighs/legs
   and abdomen, including the visible fur silhouette. Compare in Morphbench first,
   then verify the exact installed resources and conversion in Skyrim SE. Tests
   must cover OBody, both sexes, transform/return, born beasts and persistence.
2. **Next release — individual traits and breast shape.** Human-driven head/face,
   ear, tail and claw conversion participates in the same matrix concept; qualify
   actual human sources rather than inventing anatomical equivalence. Investigate
   per-actor fur colour from hair, skin, eyebrow and beard parameters. Improve the
   static female breast shape, downward growth and skin/fur/axilla continuity.
3. **Third release — physics and VR.** Finish FSMP/CBPC motion, coarse fitted SE
   collision, detailed VR hand-contact coverage, morph-responsive collider bounds
   and the first-person VR body. Prefer existing XP32 bones. Measure actual engine
   behavior; an offline capsule fit is not contact acceptance.
4. **Maintenance — morph expansion.** Evaluate additional or replacement wolf
   fields using the same human-source, geometry-quality and appearance checks.

Implementation and acceptance are separate. A passing evaluator or increased
coefficient does not establish a visible or attractive deformation. New game
tests use the accepted compact paired scene, disabled AI/collisions and DevBench
engine commands; temporary output and tests stay outside the mod archive.

The remaining sections retain the 30 October baseline and backlog history; their
older priority statements do not override the sequence above.

The nearest release is the SE core: repaired male/female bodies plus human-driven
Distribution using ordinary OBody presets. Effective human morphs determine beast
morphs through deterministic resource-family rules; no separate wolf presets are
required. The selected breast/axilla and male collar repairs are reproducible and
included in the minimal candidate archives. Later SE checks observed six actual
transformations with advancing frames and preserved human coefficients; the
earlier render hang remains historical failure evidence, not the latest result.
Official RaceMenu remains the dependency; a replacement RaceMenu is not required.

The owner subsequently inspected paired actors in the game and accepted the
technical projection as a GitHub release, while rejecting its weak visible
contrast for product use. The frozen runtime cut is `claw/se-core-20261030`.
The [range and release plan](morph-range-plan.md) records the actual twelve-actor
measurements, proposed lean/bulky fields, control terminology and six small
post-baseline releases. New feature development starts from the latest `main`
on a separate branch; this does not publish another Nexus version.

## Post-release backlog

**Vanilla human bodies (deferred by the owner on31October2026):** add explicit
male/female vanilla conversion profiles using actually available vanilla inputs,
primarily actor weight. Do not invent HIMBO/CBBE body morphs for a vanilla mesh.
Qualify neutral and weight-extreme results in game before exposing these choices.
The nearest release requires HIMBO for males and CBBE or3BA for females; its
installer checks enabled plugin markers and recommends a family, which is not
runtime detection of the winning NIF/TRI. Changing the installed body family
requires reinstalling the matching conversion data and explicit adoption for
existing actor states; saved/custom matrices must not be silently overwritten.

1. **Abdomen:** transfer the roundness of the human belly more faithfully to the
   wolf. Improve the abdomen field and conversion together, judging contour and
   silhouette rather than only a larger numeric coefficient.
2. **Breasts:** make the female shape more natural and preserve human breast
   differences more clearly. Size should broaden mainly along the torso, grow
   less strongly outward and settle downward. Keep axilla, skin and fur joins
   continuous; this is a shape task before dynamic breast physics.
3. **Musculature:** make athletic human bodies produce visibly more athletic
   wolves, including shoulders, chest, back and limbs. Calibrate related inputs
   together while avoiding excessive bulk or saturated output morphs.
4. **Physics and collisions:** finish ear/tail motion and contact, breast rig and
   physics, close body collision fitting and morph-responsive collider resizing.
   Prefer existing XP32 bones; actual provider ownership and game behavior remain
   unaccepted. The older separate `_0`/`_1` authoring item was withdrawn by the
   latest owner queue above; explicit matrix weight is a separate input contract.
5. **First-person VR body:** finish model dispatch, selective head visibility,
   morph synchronization, camera clearance, IK and interaction acceptance.
6. **Ear, tail, head and claw selection:** design how an actor's ear size, tail
   size, head proportions and claw size are chosen and adjusted. Existing public
   morphs do not yet participate in the current body-only human conversion.
   Investigate meaningful readable human body/head parameters and deterministic
   many-to-many links; keep the choice of controls and handling of traits without
   an established human counterpart open. Do not require separate wolf presets
   or invent unrelated body-to-ear mappings. Preserve each actor's choices across
   transformations and save/load.
7. **Fur colour feasibility:** investigate whether male and female werewolf fur
   can be recoloured per actor, then whether that colour can follow the human
   actor's actual hair colour. Establish readable hair-colour data and feasible
   material, tint or texture mechanisms for skin and fur layers; check consistency
   across transformations, model reload and save/load. Keep this an investigation:
   no working recolour mechanism or automatic hair-to-fur link is claimed yet.

All seven are outside the nearest release gate. Existing partial implementations
are retained; this deferral does not declare physics or VR complete. The optional
adult Anatomy/physics add-on remains a separate later task.

## Existing development work and constraints

The 25 October order supersedes the 11 October sequence that placed VR second.
The 26 October manual-session request refines preset interoperability: ordinary
human presets must determine the wolf through morph-to-morph conversion, without
an additional beast preset. Resource-specific mapping is therefore part of this
session's preparation. The earlier independent beast route remains optional.
Prefer keeping XP32 and its existing bones. Replace the skeleton only if a
demonstrated requirement cannot be met otherwise.

- [Distribution reference core](distribution.md): implemented mapping and native
  human-driven controller with SE evidence; final packaged regression pending.
- [Independent presets](presets.md): typed XML, optional VR native distributor,
  selector and authoring resources built; runtime acceptance pending.
- [Human/beast morph linkage](transformation.md): native signed coefficient
  conversion is implemented as a development candidate. Linked actors start
  from neutral owned coefficients and bypass beast catalogs, saved choices and
  actor-weight interpolation. Measured typed CBBE2.0.3/3BA2.48/HIMBO5.8 conversions
  support many-to-many signed rules, explicit setup defaults and female breast
  fields; runtime transformation/persistence and appearance acceptance remain.
- [Surface attachment repair](geometry-repair.md): opt-in female candidate built
  with topology/UV data retained. A separate post-export stage repairs the narrow
  head/body skin-weight collar; controlled pose errors improve, while actual
  seams, fur coverage and animation still need qualification.
- [Ear/tail physics source candidate](../python/physics/README.md): native effective
  SKEE aggregation, stable observation, bounded worker fitting and host lifecycle
  integration are implemented. Current normalized NPC weight is a separate fit
  input. Explicit provider qualification and actual motion/contact tests remain.
- [Collider candidates](colliders.md): reproducible offline fitting and measured
  male/female candidates; installation and runtime physics qualification pending.
- [Breast shape and rig](breast-rig.md): verified existing bones, missing mesh
  weights and a separate-part alternative. A moderate shape-only BreastSize profile
  and a separate opt-in P1 skinning stage are implemented. The latter reuses six
  existing XP32 nodes, retains the four-weight budget and verifies serialized
  weights/binds against controlled poses. It does not replace the skeleton.
  Current composition retains the repaired collar, breast support and constrained
  fur-root continuation. Actual provider ownership, remaining attachment residuals
  and visual/game acceptance remain separate gates.
- [Human-driven morph expansion](morph-expansion.md): proposed localized forearm,
  glute, abdomen and thorax targets have real 3BA/HIMBO sources. Additional head/
  ear conversion needs a separate readable human head-data contract.
- [Morphbench needs](morphbench-needs.md): pose-aware binds, frozen skin/fur joins,
  seam/intersection reports and perspective camera clearance are proposed tool
  improvements, rather than claimed existing measurements.

The owner added first-person VR body work to parallel development on 26 October,
paused that work on 27 October to prioritize SE and resumed it on 28 October. The
[VR body prototype](vr-body.md) records its
resource and runtime-integration boundaries. No manual game or microphone launch
is implied; that still waits for the owner's direct command.
The [head-bone audit](vr-head-policy.md) additionally finds Head-weighted breast
and fur vertices: preserving the mixed shape alone does not qualify head hiding.

These development results do not change or requalify the published0.6.2.0 package.

## Accepted technical baseline and product work

Completed: the six repaired surface files replay exactly; minimal archives,
four FOMOD selections, actual native MO2 installation/accounting, dependencies
and winning runtime files are verified. Contrast6 passed 278 source tests with
10 skips and 59 clean-package consistency checks. The exact runtime set then
passed two actual SE scenarios: core117 and born33, with both-sex roundtrips,
preserved human/foreign keys, save/load and two originally-beast actors. Both
processes exited normally and the environment was restored. The two scenarios
remain separate because the current fixture supports six persistence participants
and requires a fresh world for born actors. See the
[verification summary](verification-20261030.md) and
[candidate build contract](core-candidate.md).

The owner has accepted a technical Git release with modest contrast. Improve the
actual geometry range and obtain a new in-game visual assessment before claiming
the stronger product outcome. Packaging is consolidated into one working-mod
archive and one `test_` archive; the native corresponding source is nested in
the working download and is not installed. The native binary still targets
SE1.7.104 only; CommonLib configuration alone does not qualify AE/VR. See
[unified-release.md](unified-release.md) and
[test-fixture-package.md](test-fixture-package.md).

The separate CLAW Morphbench plugin had a first API v1 development package; it is
not part of the game archives or a prerequisite for this release. Natural shape,
physics and VR work remains in the backlog. A minor diagnostic cleanup is also
queued: an absent legacy wolf-preset directory should be logged as an empty
optional catalog, rather than an error. Linked human-driven operation does not
need that directory and passed with it absent.

Future inspection scenes use the owner's accepted absolute QASmoke placement,
pair distance110, pair pitch300 and row separation320. Capture AI/collision Off
before the first fixture. Recheck shared ownership; no old order, actor reference
or toggle batch is reusable. Publication remains separate from testing.
