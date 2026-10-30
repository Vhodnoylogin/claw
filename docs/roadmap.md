# CLAW — future plans

Owner-defined priorities, revised 30 October 2026. No release dates are promised.

The nearest release is the SE core: repaired male/female bodies plus human-driven
Distribution using ordinary OBody presets. Effective human morphs determine beast
morphs through deterministic resource-family rules; no separate wolf presets are
required. The selected breast/axilla and male collar repairs are reproducible and
included in the minimal candidate archives. Later SE checks observed six actual
transformations with advancing frames and preserved human coefficients; the
earlier render hang remains historical failure evidence, not the latest result.
Official RaceMenu remains the dependency; a replacement RaceMenu is not required.

After reviewing six paired Morphbench comparisons on 30 October, the owner called
the result a good start and explicitly deferred the following improvements until
after this release. That is preliminary offline feedback, not final game visual
acceptance or permission to publish.

## Post-release backlog

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
   unaccepted. Distinct male/female `_0`/`_1` shapes remain queued alongside this
   stage, linked to human actor weight without weighting effective morphs twice.
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
- [Ear/tail physics source candidate](../physics/README.md): native effective
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

## Remaining acceptance for the next functional release

Completed offline: all six selected surface files replay exactly from source;
minimal base/Distribution archives rebuild identically; 23 focused tests and
136 archive checks pass, including all four installation selections. Six actual
human source vectors have paired human/wolf Morphbench images. See the
[candidate build contract](core-candidate.md) for exact scope and limitations.

- Install the actual minimal archives through MO2, verify selected FOMOD files,
  recursive dependencies, active plugins and winning runtime bytes. Check fresh
  installation and the upgrade path; offline selection simulation alone is not
  manager installation evidence.
- Run the final combined SE scenario on that exact composition: multiple actors
  of both sexes, real OBody input, human/wolf/human transitions, source and foreign
  key preservation, born-wolf distribution and save/load without unintended
  reassignment. Retain earlier positive checks separately; they do not substitute
  for the final packaged run. Use actual game-menu exit and verify restoration.
- Obtain the owner's in-game visual acceptance of the selected repaired bodies,
  especially textures, fur and axilla/neck joins. Offline comparisons do not
  establish textured or animated appearance. The post-release shape improvements
  above are not additional acceptance requirements for this release.
- Finalize version labels, changelog and dependency/platform claims against the
  accepted archive hashes, including the separate native corresponding source.
  The current Distribution binary targets SE1.7.104 only; do not claim untested
  AE/VR compatibility. Publication remains a separate owner decision.

The final automatic and manual orders are prepared; preparation alone does not
mean the final regression ran or passed. Recheck current shared test ownership
before live work and do not clear another qualification's hold. No source build
starts a game, microphone session or old held order, or changes the public release.
