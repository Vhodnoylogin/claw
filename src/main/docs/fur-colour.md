# Fur colour: frozen-resource audit and first experiment

Status on 30 October 2026: offline feasibility investigation. No recolouring code
has been installed, no human hair colour has been read from a running actor, and
no hair-to-fur link or visible colour improvement is established. The frozen SE
core remains unchanged. Elegant remains the external texture dependency; credit
Wolflady500 and KaienHash. The [donor permission](../resources/donors/README.md) does
not allow textures in this repository. This work exports metadata only.

## Reproduce the audit

`src/main/python/build-tools/audit-fur-colour.py` verifies all four frozen body NIF hashes and sizes
against `target/references/releases/se-core-20261030/claw-build.json`, then reads the actual
serialized shaders, all nine Skyrim texture slots, alpha flags/thresholds,
vertex-colour counts and per-NIF shader/texture-set sharing. Both endpoints are
read separately. The JSON includes input, parser, script and optional local
interface-source hashes. Duplicate shape names are rejected. Unknown or missing
target names are reported explicitly, so a later body revision is not silently
treated as fully covered.

```powershell
python src/main/python/build-tools/audit-fur-colour.py `
  --pynifly '<PyNifly add-on root>' `
  --texture-root '<Elegant mod root>' `
  --skee '<SKSE64Plugins checkout>' `
  --commonlib '<CommonLibSSE-NG checkout>' `
  --out '<external builds directory>/fur/audit.json'
python -m unittest discover -s src/test/python/unit -p test_fur_colour_audit.py -v
```

`--texture-root` is optional and repeatable. It reads loose DDS headers and hashes
in supplied roots; it does not resolve MO2 priorities or BSAs. A missing loose file
therefore does not establish a missing game dependency. Output must be a new JSON
outside Git, input directories and live mod/profile/Data trees. It never overwrites
an existing report. No pixels or texture files are exported or modified.

## Actual frozen bodies

The audit inspected the release at the `689e5bd` Git checkpoint. Male `_0`/`_1`
are byte-identical (`cff0f62e…`); female `_0`/`_1` are byte-identical
(`033c9828…`). These are the existing baseline endpoints, not new colour assets.

| Material group, in each sex and endpoint | Shapes | Serialized result |
|---|---|---|
| Opaque underlying coat | `body`, `head` | Default lighting shader, no alpha property |
| Main fur | `fur_arms`, `fur_back`, `fur_belly`, `fur_chest`, `fur_face`, `fur_shoulders`, `fur_tailtip` | Default lighting shader, double-sided, alpha test threshold 90 |
| Chest/face blends | `ChestBlend`, `FurfaceBlend` | Default lighting shader, double-sided, alpha blending; thresholds 80/44 stored but alpha test disabled |
| Scalp blend | `ScalpFurBlend` | Default lighting shader, double-sided, alpha blending and alpha test, threshold 80 |
| Excluded surfaces | `claws`, `eyes`, `mouth`; male also `genitals` | Deliberately outside coat experiment; eyes use Environment Map |

Each NIF has twelve coat targets, none already tint-capable, and no vertex colours.
The PyNifly buffer's white `skinTintColor`/`hairTintColor` values do not make a
Default shader use tint. Male has sixteen shapes; female has fifteen. All shapes
have distinct shader and texture-set block IDs within their respective NIFs.
This does **not** establish how the engine shares loaded shader properties or
materials between actor instances. Block IDs are local to each file.

The ten fur layers reference seven diffuse files (the blends reuse furback or
furface); `body` and `head` add two more. They all reference Elegant paths.
The supplied local Elegant installation contains all nine coat diffuse files:
body/head are 2048×2048, fur diffuse files are 1024×1024; their DDS headers report
DX10 format 98 and one mip level. Headers do not establish colour neutrality or
the rendered tint response. Across all shapes the NIFs reference 22 distinct
case-normalized textures; 21 resolve in this Elegant root. The remaining
`textures/cubemaps/catseye.dds` belongs to excluded eyes and was not resolved
through a BSA. The audit makes no missing-in-game claim about it.

Editing any shared DDS would affect every user of its path, including both sexes
and multiple actors. `body.dds` also serves the excluded male anatomy shape.
Replacing the texture globally is unsuitable for an actor-specific experiment.
Recolouring only fur cards would leave the exposed body/head coat unchanged.

## Readable human colour and local runtime interfaces

The inspected local CommonLib headers expose
`Actor::GetActorBase() -> TESNPC::headRelatedData -> hairColor -> BGSColorForm::color`
and `TESNPC::GetRootFaceNPC()` for face-template inheritance. Null head/hair data
must be handled. Capture the human source **before** beast replacement and key it
by actor reference, not just a shared NPC base. Reading a race default is not
evidence of that actor's actual hair colour. Never mutate `BGSColorForm` or the
human NPC base to drive the wolf.

This gives readable record colour, but plugins and presets can change effective
appearance. The local SKEE `PresetInterface.cpp` applies a separate HairTint
material colour with a ×2 channel scale. Consequently the first experiment must
record the human HCLF RGB and the actual loaded human HairTint material, with its
source geometry and feature. Do not assume the two values use the same scale or
that all hair replacers use HairTint. Missing, ambiguous or unsupported rendered
hair data should skip automatic mapping and retain its reason. No numeric
hair-to-fur conversion is selected until rendered comparisons exist.

The frozen package's `SKEE-IPluginInterface.h` and the inspected local source
expose `IOverrideInterface` v2 and actor/node `SetNodeProperty`. In local
`skee64/OverrideVariant.h`, `kParam_ShaderTintColor` is key 7 and accepts packed
integer RGB. `ShaderUtilities.cpp::SetShaderProperty` converts a non-tint
lighting material into `FaceGenRGBTint`, copies material values, changes shader
flags, sets the new material and initializes the shader before setting tint.
This is a plausible mechanism for Default coat shaders, not a no-op tint-field
write. It is not an automatic HairTint mechanism. The inspected checkout contains
a separate uninstalled RaceMenu repair; its source hashes do not qualify the
installed official RaceMenu B6 binary or make that repair a CLAW dependency.

## Selected minimal opt-in runtime experiment

Use the existing provider, with a transient `IOverrideInterface` v2 node-property
probe. No persistent override registration, asset rewrite, new texture or automatic
Distribution behaviour is part of the first probe. It remains to be implemented
in a separately gated diagnostic path:

1. In a fresh controlled session, select one treated actor and one same-sex
   control using the same frozen body. Repeat for the other sex. Require exactly
   one matching geometry per selected shape under the current actor root. Record
   provider/interface version, root generation and each property/material pointer,
   feature, flags, texture paths and alpha state for both actors.
2. Establish private property **and** material ownership before mutation. Distinct
   pointers to only one of them are insufficient. If a property/material is
   shared, use engine-correct clone/rebind/copy ownership or stop the probe; do not
   mutate a cached/global pointer. The offline NIF audit cannot implement this
   engine lifetime contract.
3. On the game thread, after target validation, call
   `SetNodeProperty(actor, false, shapeName, 7, 0, IntRGB, true)` for the explicit
   twelve target names. First compare neutral white and one clearly different
   fixed diagnostic tint under identical lighting. Then probe the captured human
   record/rendered hair colour with source identity recorded. Keep the control,
   eyes, claws, mouth and deferred anatomy unchanged. Check every alpha/blend
   layer and underlying coat; readback RGB alone is insufficient.
4. Inspect visible seams, alpha sorting/coverage, normals, specular response and
   fur/skin consistency in paired views. The diffuse may already contain hue and
   contrast: multiplicative tint cannot be assumed to produce the requested hue
   or a brighter pale coat. A coloured shader and larger channel values do not
   establish useful appearance.
5. Do not save during this first diagnostic session. Removing an override or
   setting white does not undo shader conversion. Restore captured private
   properties or reload baseline 3D, then verify the original features, flags,
   textures and alpha state as well as the unaffected control. Never retain raw
   material pointers across a model rebuild.

Only after this passes should the feature acquire actor-owned source storage,
race/3D generation checks, reapplication after model reload, transformation/return
handling, save/load persistence, hair-change invalidation and cooperative
ownership with other colour mods. Two actors sharing an NPC base also need an
isolation check. The current audit covers none of these runtime gates. The next
concrete implementation is the disabled diagnostic probe with ownership/readback
and restoration evidence; an automatic hair-to-fur link remains subsequent work.
