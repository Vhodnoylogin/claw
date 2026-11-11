# CLAW Modder Guide — 0.9.0-r3

Practical configuration and integration notes for **CLAW — Customizable
Lycanthrope Appearance and Weight**. This guide describes the released runtime
at [source commit b6f65b5](https://github.com/Vhodnoylogin/claw/tree/b6f65b5160efbd373ac35bd286810f8b3f805965),
tagged [claw/0.9.0-r3](https://github.com/Vhodnoylogin/claw/releases/tag/claw%2F0.9.0-r3).
The accompanying installation/documentation baseline is
[2a4eb5e](https://github.com/Vhodnoylogin/claw/tree/2a4eb5e37e6eaf7e5de3eebcd33de0467d66f2aa).

## How the pipeline fits together

```text
Collect named inputs -> evaluate sparse transform rules -> named outputs
                     -> morph/material adapters -> apply to the loaded model
```

Collection, arithmetic and engine application are separate responsibilities.
A matrix maps names and values; it does not discover a human body, read arbitrary
engine fields, create a TRI morph, or load an image by itself. A source provider
must supply the input, and the final adapter must support the output.

Body conversion reads effective human SKEE coefficients and supported actor
traits. It produces named wolf morph coefficients. Coat conversion reads human
hair colour and a stable actor seed, produces a named selector, then resolves
that selector through material data. Human preset names do not select paired
wolf presets.

## Files to edit

Paths below are relative to the game's `Data` directory. Keep custom changes in
a separate manager mod so their precedence and removal are clear.

| File | Responsibility |
|---|---|
| `SKSE/Plugins/CLAW/MorphLinks.xml` | Versioned body-family profiles, transform rules and selected defaults |
| `SKSE/Plugins/CLAW/CoatMatrix.xml` | Named coat inputs to named numeric outputs |
| `SKSE/Plugins/CLAW/CoatMapping.xml` | Output intervals/logical coat IDs to materials |
| `SKSE/Plugins/CLAW/CoatLibrary.xml` | External DDS paths and metadata for complete materials |

These files are loaded during game startup. Restart after changing XML.
`Refresh(actor)` does not reread configuration files.

## Body inputs and availability

| Source | Meaning |
|---|---|
| Ordinary names such as `Belly` or `Arms` | Signed, already effective SKEE body coefficients for the declared human body |
| `$actor.weight` | Current NPC weight divided once by 100, giving 0..1 |
| `$human.face.noseLength` | Captured vanilla FaceGen nose long/short value |
| `$human.face.jawWidth` | Captured jaw narrow/wide value |
| `$human.face.jawForward` | Captured jaw forward/back value |
| `$human.face.chinWidth` | Captured chin narrow/wide value |
| `$human.face.chinForward` | Captured chin underbite/overbite value |
| `$human.height` | NPC height × current human race's sex height × reference scale, each once |

`$actor.` and `$human.` are reserved, case-insensitive namespaces; only the exact
supported spellings above are accepted. They cannot be output targets. Weight
is recaptured on refresh and is not a SKEE morph. Do not multiply effective human
morphs by weight a second time. Ordinary `_0`/`_1` mesh interpolation is separate.

Face and stature are captured in an eligible human form and retained in wolf
form. A born wolf has no invented human face history. Missing face inputs use
arithmetic neutral 0; missing height uses 1, while availability remains false.
Use `HasHumanTrait(actor, source)` before interpreting `GetHumanTrait` as an
observation. Missing/invalid actor weight is an error. Stature does not measure
rendered bounds or skeleton/node overrides.

Race, sex and root-face identity are provenance, not extra numeric matrix
columns. HeadPart selections are discrete categories, not proportions: a part
index of 3 does not mean 30% of a continuous trait. A new category-based
integration should define explicit named 0/1 indicator channels and a qualified
collector, or select explicit profiles. The released runtime does not add such
a collector merely because a new XML source name is written.

## Sparse rules and named outputs

The released family file contains rules such as this 3BA weight excerpt:

```xml
<Profile id="CLAW.3BA.2.48.Geometry1" family="3BA" version="2.48"
         sex="female" calibration="anatomy-v4-response-normalized">
  <Rule source="" target="CLAWTorsoLean" gain="0.125" cap="1"
        function="constant" value="1" />
  <Rule source="$actor.weight" target="CLAWTorsoLean" gain="-0.25" cap="1" />
  <Rule source="" target="CLAWTorsoGirth" gain="-0.5" cap="0.25"
        function="constant" value="1" />
  <Rule source="$actor.weight" target="CLAWTorsoGirth" gain="1" cap="0.25" />
</Profile>
```

This is an excerpt, not a replacement for the full installed file. An empty
source is an explicit constant column. For each target, evaluate rules in order:

```text
output[target] = cap[target] * clamp(sum(gain * F(source)), 0, 1)
```

Parameters/inputs normalize to float32; functions, products and ordered sums use
binary64; the final coefficient rounds once to float32. Contributions combine
before clamping. Every rule for one target must use the same cap in `(0,1]`.
The excerpt gives neutral added lean/girth at weight 0.5, lean 0.125 at weight 0,
and girth 0.125 at weight 1.

| Function | Parameters and behavior |
|---|---|
| `linear` or omitted | `x` |
| `positive` | `max(x,0)` |
| `negative` | `max(-x,0)` |
| `smoothstep` | `t*t*(3-2*t)`, with `t=clamp(x,0,1)` |
| `power` | Integer `exponent` 1..8; repeated multiplication of clamped absolute input, preserving sign |
| `constant` | Finite `value`; requires `source=""` |

After float32 normalization, `abs(gain) <= float32(1e-6)` removes the edge.
This is a coefficient cutoff, not an input or output dead band. Other rules must
still be well formed. Duplicate active source/target pairs, inconsistent caps,
nonfinite values and case-only name aliases are rejected. An active source
cannot also be an active output name, which prevents refresh feedback.

Profiles support up to 256 structural rules and 64 active targets. Names are
printable ASCII, up to 160 bytes, with no surrounding whitespace. Named outputs
need matching installed wolf TRI geometry; adding a name does not create it.
Unmapped wolf outputs stay neutral. Use the matching NIF/TRI pair when changing
resources, and inspect combined morphs as well as individual endpoints.

## Body families and saved actors

The installer selects one male and one female family independently. Its output
contains their profiles and an explicit `<Defaults male="..." female="..." />`.
The source catalog offers:

| Body | Profile ID |
|---|---|
| HIMBO 5.8 male | `CLAW.HIMBO.5.8.Geometry1` |
| Vanilla male | `CLAW.VanillaMale.Weight1` |
| CBBE 2.0.3 | `CLAW.CBBE.2.0.3.Geometry1` |
| CBBE+3BA 2.48 | `CLAW.3BA.2.48.Geometry1` |
| BHUNP 3.34 Advanced Ver4 | `CLAW.BHUNP.3.34.AdvancedV4` |
| Classic UNP Renewal 4.6 | `CLAW.UNP.4.6.Weight1` |
| Vanilla female | `CLAW.VanillaFemale.Weight1` |

Choose the actual winning human body and its morph resources. Classic UNP and
Vanilla use weight-based body rules; they do not supply invented BodySlide
sliders. Human face/stature channels remain independently available.

An actor's saved matrix remains authoritative after an update. Reinstalling a
family or editing defaults does not replace that matrix. After installing the
new configuration and restarting, use the actual Papyrus API to rebind it.
For example, for a female actor using the installed 3BA profile:

```papyrus
Bool queued = CLAWDistributionNative.ConfigureMorphFamily(target, "CLAW.3BA.2.48.Geometry1")
```

`GetMorphFamilies(female)` enumerates loaded IDs. Check `GetStatus(target)` and
`GetLastError(target)`, then `GetMorphFamily(target)` for the actual binding.
A returned `true` means queued, not applied. Status 1 is pending, 2 means own
coefficients were read back/update requested, 3 unloaded, 4 error, 5 human with
own wolf key cleared, 6 explicitly cleared, and 7 SKEE unavailable.

`Refresh(target)` recaptures inputs and recomposes the actor's current stored
rules. `ConfigureMorphFamily` binds the new loaded rules and resumes a suppressed
actor. The older `ConfigureMorphLink` parallel-array API creates linear rules
only and has a 128-row transport limit; use file profiles for function rules.
`ClearOwn(target)` clears only `CLAW.Distribution` and suppresses automatic
reapplication until explicit configuration/assignment resumes it.

## Coat data and the material adapter

The released `CoatMatrix.xml` uses these actual rules:

```xml
<CoatMatrix schemaVersion="1">
  <Rule source="hair.red" target="coat.selector" gain="0.187088" cap="1"/>
  <Rule source="hair.green" target="coat.selector" gain="0.629376" cap="1"/>
  <Rule source="hair.blue" target="coat.selector" gain="0.063536" cap="1"/>
  <Rule source="seed.withHair" target="coat.selector" gain="0.12" cap="1"/>
  <Rule source="seed.withoutHair" target="coat.selector" gain="1" cap="1"/>
</CoatMatrix>
```

Hair channels are normalized RGB. With known human hair, `seed.withHair` supplies
a small stable variation and `seed.withoutHair` is zero. Without it, hair inputs
and `seed.withHair` are zero and `seed.withoutHair` supplies the stable selector.
These five names are the coat collector's supported inputs.

`CoatMapping.xml` names the output and maps intervals to logical IDs/materials;
for example its first range is:

```xml
<Range min="0" max="0.1" id="elegant-2k-2.1/black" material="randomized/black" />
```

Lower bounds are included; upper bounds are excluded except for the final 1.
Aliases let several logical IDs share one material. `CoatLibrary.xml` resolves
the ten materials to nine external diffuse files each, with metadata. No texture
artwork is included in CLAW. Keep Elegant's base installation for the NIF's base
material and obtain optional Randomized textures from the author's separate
download. Follow the [release installation guide](https://github.com/Vhodnoylogin/claw/blob/2a4eb5e37e6eaf7e5de3eebcd33de0467d66f2aa/src/main/resources/publication/runtime/README.md)
for the exact 0.9.0 dependency setup; this guide adds no new dependency mode.
CLAW's empty `RandomElegantWerewolves_MS.json` must win the Model Swapper conflict.

A complete coat is checked before binding. Missing/wrong-size files, invalid DDS
headers or loaded dimensions cause fallback to the installed base material;
body conversion continues. Catalog SHA values are provenance metadata: this
release does not hash the installed DDS payload at runtime. Restart after fixing
resources, or reassign the coat to invalidate its validation cache.

Use `GetCoatPatterns()` for logical IDs, `SetCoatPattern(target,id)` for a manual
override, and `ClearCoatPattern(target)` to resume automatic selection. Inspect
`GetAppliedCoatPattern` and `GetCoatPatternStatus`; requested and applied states
are separate. The shipped mapping keeps original texture colours. The separate
appearance mechanism can use captured skin/hair colour for private material tint.

## Engine ownership, optional sources and tools

CLAW writes wolf morphs under its own `CLAW.Distribution` SKEE key and clears
only that key on human return. Human provider values and other mods' keys stay
owned by their providers. Material application uses private per-actor clones,
preserves donor maps/alpha, and prepares the complete change before binding.
A later material writer wins on the same model; cleanup restores only properties
CLAW still owns. Do not build an integration that repeatedly fights another
material writer or clears every SKEE key.

The optional OBody source host asks stock OBody to supply human body coefficients
for eligible actors first encountered as wolves. It respects existing assignments,
OBody's rules and readiness. It does not create human face/colour history or pick
an independent wolf preset. Ordinary human-to-wolf conversion works without it.

The [Morphbench plugin](https://github.com/Vhodnoylogin/claw-morphbench-plugin) is
optional authoring tooling. Public version 0.3 targets older CLAW 0.7 matrices;
it is not a matching editor for every expanded 0.9 output. The updated public UI
release is deferred. Matching development tools consume an explicitly pinned
[shared C++ matrix kernel](https://github.com/Vhodnoylogin/claw/tree/b6f65b5160efbd373ac35bd286810f8b3f805965/src/main/cpp/shared),
compiled for native and WebAssembly use, rather than a second JavaScript equation.
Pixel metrics describe sampled artwork; they do not automatically build matrix
ranges or establish rendered colour/geometry quality.

When reviewing a change, check actual source availability, named output/readback,
both sexes/weights, transform/return, model refresh and save/load. Check complete
coats and fallback separately from body morphs. `RequestCoatSurfaceAudit` and
`GetCoatSurfaceAuditChunks` provide explicit short-lived read-only material
samples; concatenate every returned chunk before JSON parsing. Diagnostics and
arithmetic parity still need visual review in the target runtime.

Further reference: [matrix contract](https://github.com/Vhodnoylogin/claw/blob/b6f65b5160efbd373ac35bd286810f8b3f805965/src/main/docs/matrix-contract.md),
[native Papyrus API](https://github.com/Vhodnoylogin/claw/blob/b6f65b5160efbd373ac35bd286810f8b3f805965/src/main/papyrus/claw/CLAWDistributionNative.psc),
[coat contract](https://github.com/Vhodnoylogin/claw/blob/2a4eb5e37e6eaf7e5de3eebcd33de0467d66f2aa/src/main/docs/coat-library.md).
