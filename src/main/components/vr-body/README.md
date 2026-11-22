# CLAW VR body component

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

### Optional world-body motion trial

`world_motion.py` builds one detached FSMP overlay for each fixed-profile sex.
Use the pinned 0.10.0 core archive and the existing fixed-profile diagnostic
archive as inputs. Each output contains the selected legacy NIF and its exact
released FSMP XML. The matching namespaced TRI stays supplied by the
fixed-profile diagnostic. A staged trial uses the same sex in both layers and
the core installer setting **None**. Removing the optional layer restores the
fixed-profile static mesh.

```powershell
python -B src/main/components/vr-body/world_motion.py --fixed-profile '<fixed profile ZIP>' --core-release '<original 0.10.0 ZIP>' --skeleton '<reviewed XP32 NIF>' --pynifly '<public PyNifly add-on>' --out '<new external trial directory>'
```

The NIF adds one Scene Root hook. The native file reader checks stored driver
influence and the original TRI link. Tail and female breast influences include
visible file shapes. Ear influences belong to shapes marked hidden in this
carrier. Qualify the live world route first by checking the loaded Body32
identity, one FSMP system for the actor and normal retirement. The separate
native first-person graph needs its own qualification.

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
