# CLAW VR body component

This component requires the published CLAW 0.11.0 core and VRIK. The VR plugin
declares `CLAW.esp` as a master. The fixed-profile installer checks that both
`CLAW.esp` and `vrik.esp` are active. The archive supplies the VR armor override
and its VR meshes and morph data. CLAW's morph engine, conversion matrices,
ordinary werewolf models and coat dependencies come from the original install.
Install CBPC for the optional werewolf hand-contact colliders. Its Skyrim VR
configuration uses the stock left and right controller nodes. HIGGS is an
optional companion for its own VR interaction features.

Develop the optional VR body in this directory of the CLAW repository. Keep its
component-specific C++, authoring tools and resources here; put corresponding
tests and fixtures under `src/test/components/vr-body/`. Build outputs stay in
ignored `target/` or the external workspace build directory.

The 12 November owner plan includes this candidate after offline qualification
of shared mathematics and motion-physics/tool changes. Female breast aesthetics
remain deferred. Existing
prototypes still live in the earlier C++/Python/resource locations; migrate them
with their imports, build/package paths and tests when this phase begins. This
directory does not establish a working or released VR body.

The VR add-on release design uses optional FSMP motion for the tail only.
Preserve contact colliders for ears, tail and chest and verify them separately
against the morphed shapes. The sections below retain earlier diagnostic
overlays and their test history, including the older ear and chest motion trials.

The current [resource candidate](IMPLEMENTATION.md) rebuilds the complete current
male/female body and TRI family in an independent first-person namespace. It
reuses the lossless split, Neck skin graft and bound tools and retains actual
breast support. Its authored install manifest leaves every native dispatch probe
disabled. Offline file, skin and finite-pose checks do not qualify camera, IK,
sex/weight selection or live first-person behavior.

`vr_dispatch.py` builds a diagnostic-only companion ESP from the same authored
werewolf armor addon as CLAW. Give it an explicit male, female, or both-sex
model-range setting. The ESP keeps the world meshes and uses the namespaced
resources for the first-person record paths. Its binary readback checks the
paths, race, slot, range bytes and declared CLAW master.

```text
python src/main/components/vr-body/vr_dispatch.py --disable-range male --out <new-external-dir>
```

Add `--keep-stock-first-person` to generate just the weight-range override
for a stock world-body check. This loose ESP keeps both original first-person
paths and needs no component meshes. Load it after CLAW and any other
override of the werewolf armor addon. It applies only to the Skyrim VR test.

Pass `--resources <body-candidate-dir>` to make a separate MO2 test archive.
The command reopens the archive and checks the companion ESP and six
namespaced NIF/TRI assets against their exact source hashes. Before assembling
either archive, it reads each shape's `BODYTRI` reference and requires exactly
one link to the packaged `Body.tri` for that sex. This also applies to the
selected mesh copied to the legacy filename by the fixed-profile installer.
The VR body archive supplies static meshes and morph data. Its builder and
archive step reject FSMP bindings and embedded collision blocks. Pair it with
`None` in the core CLAW installer for a setup with CLAW motion disabled.

For a private comparison in a disposable MO2 profile, explicitly opt in to
the fixed-profile FOMOD and disable both model ranges.

```text
python src/main/components/vr-body/vr_dispatch.py --disable-range male --disable-range female --resources <body-candidate-dir> --fixed-profile-fomod --out <new-external-dir>
```

With Skyrim VR closed, choose exactly one player mesh for that profile. The
installer maps the selected authored `Body_1.nif` to the legacy mesh path and
installs the same seven common files for either choice. Switching the
profile's mesh requires reinstalling the variant and restarting Skyrim VR.
The default archive keeps its seven original members. This opt-in archive is
for diagnostics. The two installed layouts have matching game evidence from
direct profile staging. The interactive installer, automatic runtime sex
selection and hardware/view behavior remain unverified.

Separate one-byte controls showed world-body attachment for each sex with
its range disabled at the tested source weight. The combined override
compiles and passes binary readback. The fixed-profile tests observed the
matching male and female world-body resources and eleven expected
weight-100 outputs. A virtual controller pulse reached the wolf's named
world hand with the installed VRIK profile and in the exact stock
counterfactual. The headset renderer and dynamic selection of the
first-person model remain open. See the [VR evidence](../../../test/docs/vr-readiness-20261119.md).

CLAW supplies the werewolf mesh, its skin weights and the morph data. VRIK
and HIGGS continue to use their normal game interfaces. The scoped VR check
verified that transforming the player attaches the intended CLAW mesh and
that the same mesh remains attached across a tracked head pose and return.
The HIGGS callback supplied the observation point. Detailed ear and tail
contacts are separate checks of CLAW's authored colliders. A change to those
colliders does not require repeating the general tracking check.

### Scoped player outfit trial

The fixed-profile alias occupies one global path. A separate diagnostic
tests an ordinary equipped Body32 route using a new ARMO and ARMA. It declares
different male and female models in both views, keeps both TRI families in the
same archive, and leaves race, skin and NPC records as shipped by core CLAW.
The weight-range flags stay clear in this trial. Both endpoints of each current
sex have identical geometry, and CLAW's ordinary matrix supplies the weight
input. Each trial model has one empty provenance node for its sex. The original
TRI, skin, material and geometry blocks remain byte-identical.

```text
python -B src/test/components/vr-body/stage_player_armor.py --resources <body-candidate-dir> --out <new-external-dir>
```

In a separately admitted game run, select the subject by the admitted player
handle and give/equip only the fixture armor after the normal transformation.
Use a same-run stock Body32 observation before equip and after removal. Match
the active clone and both VFS model identities, report which view actually
attaches the model, and compare the named CLAW outputs with the matrix for
both sexes. Repeat the stock observation on a control NPC. Record item removal
and the return to human. The [schema 7 topology witness](../../../test/cpp/vr_model_topology/README.md)
inspects the exact test armor on the active player graph. Its verifier needs
independently observed fixture FormIDs. The archive does not give, equip or
serialize the outfit on its own.

The [split-view probe](../../../test/components/vr-body/probe_player_dispatch.py)
runs inside a verified disposable VR session. It waits for natural quest
initialization, casts the vanilla transformation, observes the stock body,
equips one test outfit, and captures both views. It records a missing stock
model separately, removes the outfit and checks that the original slot state
returns. The caller pins the exact VFS
winners and mapped DLLs before invoking the probe. The probe does not save
the game. The reported route and application cull describe the scene graph.
Headset rendering needs a separate observation.

Pass `--visible-ears <verified-control-directory> --fixed-profile <fixed-profile-ZIP>`
to the same builder for the optional motion trial. The armor uses separate
world and first-person records for both sexes. The base test archive installs
static models and the TRI. The separate World FSMP overlay replaces only the
two world NIFs and adds their two XML configs. Use the core setting **None** and
keep the legacy motion overlays disabled. Disable World FSMP to return to the
static trial.

Use CaptureDispatch schema 8 to identify the world model by `W_M` or `W_F`
and the first-person model by `P_M` or `P_F`. Verify the winning files in MO2
and the live FSMP registration independently. This fixture covers equipped body
dispatch and is intended for an isolated motion check. The stock-body coat
and posed contact gates still require their own in-game fixtures.

### Optional world-body motion trial

`world_motion.py` builds one detached FSMP overlay for each fixed-profile sex.
For a current core candidate, use its ZIP as `--core-release` and its
`build-receipt.json` as `--core-receipt`. With a freshly built fixed-profile
archive, pass its `dispatch-build.json` as `--fixed-profile-receipt`. The
builder rechecks the serialized choices, confirms the static body routes and
uses the same tail-only FSMP XML selected by the core installer.
The historical command below uses the pinned 0.10.0 core archive. Both paths
use the existing fixed-profile diagnostic archive. Each output contains the selected legacy NIF and its exact
released FSMP XML. The matching namespaced TRI stays supplied by the
fixed-profile diagnostic. A staged trial uses the same sex in both layers and
the core installer setting **None**. To disable CLAW motion in this setup,
keep the core on **None** and disable the separate VR motion mod in MO2.
This restores the fixed-profile static mesh.

```powershell
python -B src/main/components/vr-body/world_motion.py --fixed-profile '<fixed profile ZIP>' --core-release '<original 0.10.0 ZIP>' --skeleton '<reviewed XP32 NIF>' --pynifly '<public PyNifly add-on>' --out '<new external trial directory>'
```

The NIF adds one Scene Root hook. The native file reader checks each driven
bone's influence on visible geometry and the original TRI link. The pinned
historical 0.10.0 trial retains its original full rig and its ear and breast
driver checks. Qualify the live world route by checking the loaded Body32
identity, one FSMP system for the actor and normal retirement. The separate
native first-person graph needs its own qualification.

The detached `src/test/components/vr-body/stage_visible_ears.py` trial gives
both sexes visible ear skin on the legacy world carrier. It splits both ears
from the already hidden `head_CLAWHead`, retains the original skin and sparse
TRI records, and clears the hidden flag only on the added shape. Its isolated
TRI destination protects the original first-person resources. The static and
FSMP controls use identical ear geometry. Select only one arm in a disposable
profile, with core physics set to None. These archives are test fixtures.

The numerical readback covers skin influence on all four ear bones and the
authored [0,1] TRI box in the inherited sphere. Before making it a player
option, confirm the active body and its FSMP registration, measure movement
using the actual skinned ear surfaces, and check both eye frusta with the
matched bone and TRI sample. The appearance adapter can reuse the head coat
for the separate ear skin on the player's owned active Body32 with the matching
trial TRI. The installed base coat remains its fallback. Live coat attachment,
replacement and retirement have their own checks.

For the next headset probe, `src/test/components/vr-body/avatar_torso.py`
reads the pinned active NIF and TRI and lists the exact influential torso
bones and morph channels to capture. Run it with a JSON file containing `nif`
and `tri` entries (`path`, `sha256`, `bytes`, plus the TRI's `virtualPath`) and
`--pynifly <path>`. The NIF's typed `BODYTRI` links must use that path. With
`--observation <file>`, it also uses one admitted post-VRIK/HIGGS envelope
from the [torso capture extension](../../../test/cpp/vr_model_topology/README.md).
The captured `torsoBodyTri` must match the pinned route. The `effectiveMorphs`
and `torsoBones` fields reconstruct the visible torso. The tool measures the
signed distance from its triangles to a
camera-centred ball with the engine's left near distance as radius. The
archived player trial lacks eleven influential bones and the co-sampled
effective TRI values. Its bounding spheres alone cannot supply that result.
Headset visibility and clearance against the full stereo frusta need their
own observations.

Start from the retained [VR body design](../../docs/vr-body.md),
[head policy](../../docs/vr-head-policy.md) and
[loaded-graph notes](../../docs/vr-loaded-graphs.md). Shared matrix mathematics
and the core game adapter remain shared source. Do not create a separate product
repository or a second copy of that code for this component.
