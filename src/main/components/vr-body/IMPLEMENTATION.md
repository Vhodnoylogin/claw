# Current0.10 first-person resource candidate

`build.py` is an offline, component-local composition entry point. It uses the
existing CLAW split/skin/bounds adapters; it does not install files, create an
ESP, change the world body or call the engine. The pinned inputs in
`current-010.json` are the FINAL archive/FOMOD runtime files, including their
material and BODYTRI aliases. The earlier raw authoring NIFs are not substitutes.
Both current runtime endpoints intentionally come from the same sex `_0` file.

The build losslessly splits current head/torso triangles and remaps ALL current
serialized TRI records:30 male and31 female morphs, not the retained24/25-morph
prototype. The original ownership threshold remains0.5. Every vertex with any
nonzero serialized value under the actual declared breast targets stays visible;
affected connected fur/Blend cards stay whole. The current female target catalog
is `CLAWTorsoBreastSize`; the male has none. The build rejects a changed catalog.
This deliberately keeps additional female head-side triangles visible. It does
not remove those deltas or hide their support to pass a test. Exact triangle,
UV/material, packed-weight, bind, shader-owner and TRI checks use the existing
independent native readback verifier.

The existing Neck graft removes visible Head/Jaw/ear-descendant skin influence
using the original rest product and existing XP32 Neck. Foreign/P1/hand weights,
old binds, geometry, materials and unrelated blocks stay exact. The candidate's
actual serialized weights/binds are checked against the intended Neck reference
over every current TRI coefficient independently0..1 at all160 retained finite
poses. The original normalized/raw error limits .005/.075, packed-sum limit
.0005 and P1-change limit .005 remain. The affine error boxes include a declared
binary64 pad1e-8; these finite numerical poses are not HMD traces or game phases.
Only new-Neck sphere radii are enlarged and rounded outward to float32 against
the complete current TRI cube. Original bone spheres are preserved and are not
requalified by this step.

The output has six namespaced resources under
`Meshes/Actors/WerewolfBeast/CLAW/FirstPerson/{female,male}/`. Each NIF points to
its same-sex namespaced `Body.tri`. The BODYTRI patch changes only its shared
string-table value; all blocks and IDs remain exact. A remapped first-person TRI
therefore cannot replace the world body's original TRI. No external textures,
skeleton, third-party mesh or animation are copied into this payload.

```text
python src/main/components/vr-body/build.py --body-root <final-runtime-bodies>
  --runtime-receipt <pinned-runtime-inputs.json> --skeleton <pinned-XP32-nif>
  --pynifly <explicit-addon-root> --morphbench <explicit-frozen-tool-root>
  --reference-mod <installed-Werewolf-Body-for-VR-source> --out <new-external-dir>
```

The actual installed reference's NIF and saved author metadata are hash-pinned
as source proof for `1stperson_werewolf_hands.nif`. None of that mesh is reused.
`install-manifest.json` lists only the namespaced six files and declares four
disabled, fixed-sex/endpoint mappings to that reference path for a later probe.
It does not emit the alias, enable an install choice or claim native dispatch.
The actual VR sex/weight/path branch remains unresolved. First-person coat
leases, model reload/morph coherence, VRIK arm resolution, camera/Neck clearance,
headset hand/contact behavior and save/load remain explicit runtime gates.

Tests are in `src/test/components/vr-body/test_component.py`. Run dependency-free
checks through unittest discovery. Set `CLAW_VR_COMPONENT_ROOT` to a completed
candidate plus `CLAW_VR_COMPONENT_PYNIFLY` and `CLAW_VR_COMPONENT_MORPHBENCH` to
include actual NIF/TRI checks. They verify all four endpoints, all current morphs,
the protected support, namespace and exact source split, and reject hiding a
retained torso. No test starts a manager or game.

The retained October builders/resources remain historical references. This
bounded step reuses their functions directly rather than copying shared math,
rewriting their strict old profiles or silently applying their resource hashes
to a newer body family. It introduces no gameplay hook or second morph cache.
