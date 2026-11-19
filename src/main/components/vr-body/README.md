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
namespaced NIF/TRI assets against their exact source hashes.

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
compiles and passes binary readback. Native selection of the first-person
record paths and additional source weights still require game evidence.

Start from the retained [VR body design](../../docs/vr-body.md),
[head policy](../../docs/vr-head-policy.md) and
[loaded-graph notes](../../docs/vr-loaded-graphs.md). Shared matrix mathematics
and the core game adapter remain shared source. Do not create a separate product
repository or a second copy of that code for this component.
