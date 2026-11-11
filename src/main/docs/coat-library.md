# Coat selection and materials

The 0.9.0 FOMOD installs three XML files under `SKSE/Plugins/CLAW/`.
`CoatMatrix.xml` produces a named, normalized value from actor inputs.
`CoatMapping.xml` maps that value to a logical coat ID and then a material.
Each interval includes its lower bound, and the final interval includes 1.
Manual assignments take precedence. Several logical IDs can share a material.
`CoatLibrary.xml` describes ten externally installed material sets and their
texture paths, so integrations can retain prior logical identifiers.

The optional artwork is installed from Elegant's own Randomized component.
The adapter keeps the installed model material when the selected resources
are unavailable. No texture image is included in CLAW. The [installer guide](../resources/publication/runtime/README.md)
covers an MO2 texture-only installation that preserves CLAW's meshes.

Earlier catalog and palette tools document the withdrawn release. See its
[historical contract](https://github.com/Vhodnoylogin/claw/blob/a7076f51333372a349239a4fe68285f50d089572/src/main/docs/coat-library.md)
for its original tool usage and observations. Install artwork through the
original author's normal mod-manager distribution.

## Papyrus interface

The native `CLAWDistributionNative` Papyrus interface provides:

```text
String[] GetCoatPatterns()
Bool SetCoatPattern(Actor target, String patternId)
Bool ClearCoatPattern(Actor target)
String GetCoatPattern(Actor target)
String GetAppliedCoatPattern(Actor target)
String GetCoatPatternStatus(Actor target)
Bool RequestCoatSurfaceAudit(Actor target)
String GetCoatSurfaceAudit(Actor target)
String[] GetCoatSurfaceAuditChunks(Actor target)
```

Use a fully qualified ID returned by `GetCoatPatterns`, for example
`elegant-2k-2.1/timber`. Setting or clearing returns admission to the actor-pinned
game-thread queue; `true` does not mean the material has been applied. The first
getter returns the requested override, while `GetAppliedCoatPattern` returns the
last successfully bound pattern ID, or empty. Status explains pending, unavailable,
fallback or yielded application. These reads are cached diagnostics from CLAW,
not independent renderer measurements.

### Explicit current-surface observations

`RequestCoatSurfaceAudit(actor)` requests a separate read-only main-task sample
of an already bound actor's loaded werewolf model. It never refreshes or applies
materials. `true` means queued; an already pending request or unavailable bound
appearance entry returns `false`. Poll `GetCoatSurfaceAudit(actor)` promptly after
admission. It returns empty while pending, invalidated, unavailable or more than
2,000 milliseconds old. A new request immediately hides the previous sample.
An accepted body/coat request, a model/race/load notification, material unbind,
unload, deletion or world reset invalidates the sample. The VM getter reads only
plain retained data and a monotonic clock; scene/material access stays in the
queued task with the actor, Distribution runtime and world checked again.

The result is JSON schema 1. Its `sample` and `modelGeneration` are process-local
decimal-string tokens, not saved reference IDs or pointer addresses. The model
token refers to a retained, observed third-person root; a different observed root
or an unload starts a new token. `ageMs` reports elapsed time since the main-task
sample. This is a timestamped observation, not a guarantee that an unreported
external write cannot occur between sampling and reading. Request a fresh sample
after every test action and retain each result outside the game for comparison.

For consumers with a short-string transport, use `GetCoatSurfaceAuditChunks`.
It reads the same cache once and returns the JSON as at most 64 ordered ASCII
strings, each at most 1,024 bytes. Join all elements with no separator **before**
parsing JSON; an escape sequence may cross a chunk boundary. One array contains
one complete observation and one age value. An empty array means unavailable,
with the same pending/invalidation/two-second freshness rules as the full-string
getter. It neither starts a sample nor relaxes the audit's inventory limits.

`surfaces` contains every geometry encountered beneath that root, including
unnamed and duplicate-name geometries. `managed` is membership in CLAW's twelve
explicit material names, with the engine's name comparison; all other rows are
excluded by that application rule. The sampler fails closed rather than
publishing a partial inventory when it exceeds 512 scene objects, 64 geometries,
128 name bytes, 512 bytes per texture string or its 64-KiB JSON budget.

Each row reports these observations independently of catalog selection:

- `name`, actual material `materialType` and `feature` numeric engine enums.
- `diffusePath` from the current lighting material's texture set and
  `diffuseResource` from its currently bound diffuse texture's resource name.
  They are separate fields and can disagree; neither comes from the desired
  catalog path. Missing or unsupported fields are JSON `null`.
- The current `tint` RGB for FaceGenRGBTint/HairTint features, without palette
  rounding, clamping or substitution; other features report `null`. Nonfinite
  channels report `null`. `materialAlpha`, `propertyAlpha` and decimal-string
  `shaderFlags` are likewise sampled actual fields.
- `noTint`: -1 unavailable, 0 absent, 1 false boolean, 2 true boolean, 3 other
  extra-data type. `tracked` identifies a surviving CLAW surface lease.
  `ownProperty`, `ownMaterial`, `ownGuard`, `ownTextureSet` and `ownDiffuse`
  compare current identities with retained lease witnesses. `healthyLease`
  additionally checks the existing full lease/tint contract. These are
  comparisons, not claims to discover arbitrary external owners.

`leaseRootCurrent` compares the sampled root with CLAW's applied lease root.
Strings preserve source bytes: ordinary ASCII uses normal JSON escaping;
non-ASCII bytes use `\u00xx` escapes (`stringEncoding="bytes-u00xx"`). This avoids
inventing a Unicode decoding for engine paths. Compare names/paths as source
bytes when non-ASCII is present.

For excluded-shape checks, compare the observed name/path/resource/feature/tint/
alpha/flag fields in complete samples around a bounded action, accounting for
model-token changes and duplicate names. This instrumentation does not itself
declare an excluded shape unchanged. It does not inspect pixels, opaque renderer
state, every texture slot, first-person VR graphs or unknown animation state.
Source/native tests establish transport, bounds and freshness; actual sampler
execution, lease readback and rendered output still require game evidence.
