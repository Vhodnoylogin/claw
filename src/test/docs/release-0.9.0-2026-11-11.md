# CLAW 0.9.0 technical verification — 2026-11-11

This record separates engine observations from visual assessment. All evidence
below was collected in Skyrim SE runtime 1.7.104.0 through DevBench and the local
executor. It does not qualify Skyrim VR runtime behavior or aesthetic quality.
The game was configured for 1920×1080.

## Retained observations

| Run | Purpose | Outcome |
| --- | --- | --- |
| `20261111-161116-c5bff9` | Shared matrix oracle, live human sources, a later material writer, transformation and save/load | Passed; environment restored. |
| `20261111-161842-ee13ea` | All ten official Randomized coats and Living Physique exact-zero cleanup | Passed; environment restored. Transparency required a stronger separate check. |
| `20261111-163417-fb99cf` | Full official Elegant addon, Model Swapper compatibility and four unavailable-coat cases | Passed; environment restored. |
| `20261111-164445-f03c8a` | Initial focused transparency launch | Aborted before SKSE/test start because MO2 added missing disabled mod inventory rows. No subject checks ran; environment restored. |
| `20261111-164720-7262ee` | Actor opacity before and after morph refresh | Confirmed a subject defect: private coat properties stayed opaque. All 36 actions completed, then requested main-menu exit returned `0xC0000005`; overall run failed and environment was restored. |
| `20261111-170041-981f0e` | Engine fade-association fix | Passed; environment restored. All 16 sampled properties followed opacity 0.4 and then 1.0, before and after refresh. |

The first three runs used game DLL SHA256
`d4c80cb15737596de9f963aa16997fe7006b40c8fd62b69cc77a966e29c5d9f0`.
The successful focused fade run used source `d96789b` and DLL SHA256
`0d4d9a5f1e14b7a1287333c9bc99af49517283f4abc5dfe07d4583e06821fbb9`.
Its result JSON SHA256 is
`72ef4cc370eb051343d4f8f3084d0026e855e14e10c119ff4ec67d3a1f82b991`.
Final combined and fallback checks must bind the exact packaged DLL; the earlier
archive is not final evidence for a later rebuild.

## Numerical and material checks

- Five actual SKEE wolf outputs matched the Morphbench WASM evaluator exactly,
  including after loading the owned save. For example, `CLAWArmBiceps` was
  `0.20873267948627472`; the retained human Living Physique contribution was
  `0.0035000001080334187` in human and wolf states and after loading.
- All ten catalog coats matched both the actual diffuse path and the currently
  bound diffuse resource on all twelve managed surfaces. The four excluded
  surfaces remained unchanged across those selections. These are scene-material
  observations, not a claim that a screenshot or renderer was inspected.
- Four separate failures—every selected DDS missing, one DDS missing, an invalid
  DDS header and a truncated DDS—rejected the whole selected coat. Twelve base
  materials remained installed, `CLAWArmBiceps` remained
  `0.43970948457717896`, and selecting a valid White coat recovered all twelve
  expected bindings.
- The full official Elegant FOMOD selection supplied 138 runtime files. Its
  cooperative ESP was disabled. Model Swapper loaded successfully; the winning
  Data-root `RandomElegantWerewolves_MS.json` was CLAW's authored empty array,
  SHA256 `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`.
  No Elegant texture is included in CLAW's runtime archive.
- Living Physique's own contribution decayed from
  `0.0035000001080334187` through `0.0014960457338020205` to exact zero. Its own
  key was removed; the foreign key and value `0.4000000059604645` survived.
- The fade fix retains the donor's existing engine fade-node association when
  cloning a shader property. In the successful focused run, all twelve managed
  surfaces reported a present, matching fade node and a healthy material lease.
  All sixteen property-alpha values were approximately `0.4000001` before and
  after refresh, then exactly `1` before and after the opaque restoration.

## Limits and reproducibility

The portable joint numeric verifier is
`src/test/python/integration/verify_joint_runtime.py`. It consumes retained result
JSON and the evaluator CLI; it contains no machine-specific paths. Coat failure
fixtures can be prepared using
`src/test/python/integration/prepare_coat_failure_fixture.py`; they use task-owned
paths and synthetic broken files without modifying the dependency's artwork.

An abnormal exit code after a requested menu quit is recorded separately from
completed subject checks; the code alone does not establish which module caused
the shutdown failure. The later focused fade run passed its complete lifecycle.
OBody was not present in these profiles, so these runs do not qualify its optional
originally-beast preset-request path. Physics and VR-body work remain outside this
release's acceptance scope.
