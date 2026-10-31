# CLAW human/wolf comparison — Morphbench plugin

This independent CLAW tool opens a human body and a wolf body in two host-rendered
preview panels. One full human morph vector controls the human preview and the
editable many-to-many CLAW conversion. Wolf coefficients are derived and read-only;
there is no inverse conversion. Rotating either panel follows the other through
the host's native orientation link. Zoom, pan and framing remain independent.

This plugin requires [Morphbench Application 0.8.5 and Launcher v1](https://github.com/Vhodnoylogin/morphbench/releases/tag/v0.8.5).
The exact qualified Application ZIP has SHA256
`c24ab0f44431b4bff0d3ed5f708ede4a30523f724bed96c5d42e894383b10f19`.
See its pinned [API contract](https://github.com/Vhodnoylogin/morphbench/blob/v0.8.5/docs/addons.md)
and [WASM contract](https://github.com/Vhodnoylogin/morphbench/blob/v0.8.5/docs/addon-wasm.md).
Independent previews and packaged WebAssembly are required; scoped geometry and
parent-window downloads are optional capabilities. Stable Application 0.8.0 is
insufficient. There is no separate JavaScript formula fallback: every calculated
coefficient uses the shared compiled kernel. Root Builder is optional for the
host's MO2-managed root deployment; separate Python and Blender are not needed.

Actual CLAW browser checks on31October opened male/female pairs, applied real
thin/muscular vectors, rotated both directions, downloaded an18837-byte matrix,
and read/exported every current/rest/delta position (14597 human and99909 wolf
vertices in the male check). These are untextured fixed-NIF observations, not
game or artistic acceptance. The earlier filechooser timeout remains a browser
automation limitation; a text-paste import is provided without a native picker.
Further actual browser checks imported a constant matrix, edited a gain from
1 to 0.8, and downloaded the edited JSON and full game XML. The native CLI
accepted that XML and matched all 28 male preview targets with no human input.
Changing the human from thin to muscular preserved the wolf's entire 99,909-vertex
model exactly, including current/base/delta arrays and actual coefficients.
Both complete approximately 16.2 MB geometry snapshots were downloaded through
the parent service while the plugin displayed only a 32 KiB text page.

This tool installs or edits no game, MO2 profile, Distribution DLL, human preset,
texture or skeleton. It imports no Morphbench backend, private renderer or DOM.
It is a separate plugin ZIP, not part of either CLAW game package. The host SDK,
manifest filename `addon.json` and its keys keep Morphbench's public names.

## Use

1. Install the plugin ZIP through Morphbench's manager, explicitly enable it
   and open its inspector. Updating the same ID requires disabling it, using the
   manager's update operation, and enabling it again. The shared-kernel plugin
   retains the existing ID `claw-human-link-dev-001` and uses version `0.3.0`.
2. Declare the actual human resources: **HIMBO 5.8 male**, **CBBE 2.0.3 female** or
   **3BA 2.48 female**. Select the exact human and wolf catalog entries and click
   **Open comparison pair**. The plugin opens no models automatically.
3. Import a full human coefficient JSON, a retained evidence-fixture JSON with
   `humanValues` and optional per-name provenance, or a BodySlide preset XML.
   Review the human controls and the read-only wolf calculation.
4. **Apply to both previews** writes the human vector to the human model and
   its mapped body outputs to the wolf. The optional **Apply human slider edits
   live** switch enables subsequent human slider edits; it starts unchecked.
5. **Zero owned wolf outputs** preserves the human vector, ears/tail and unrelated
   wolf controls. **Close comparison pair** disposes this plugin's two previews.

## Wolf presets are coefficient and function matrices

Open **Wolf preset — coefficient and function matrix** to edit ordered sparse
human-source/wolf-target edges. Each edge has a gain and a function. One cap is
shared by every edge to the same target; changing a cap updates all those edges.
Add source or constant edges, remove them, and change their accumulation order.
Duplicate source/target pairs, unknown targets, invalid parameters and nonfinite
numbers are rejected without replacing the last valid matrix. An absent edge
contributes zero. Matrix edits turn off live apply and calculate locally until
the explicit **Apply to both previews** action.

The function set is `linear`, `positive`, `negative`, `smoothstep`, `power`
(integer exponent 1..8, preserving input sign) and `constant` (empty source with a
finite value). Exact arithmetic is defined by the shared evaluator's
[matrix contract](../../docs/matrix-contract.md). Every target's contribution
details show original input, transformed input, gain and contribution.

**Export wolf preset JSON** preserves the complete matrix: profile ID, resource
family and version, sex, calibration, ordered edges, gains, caps, functions and
their parameters. The file envelope is
`{schemaVersion:1,kind:"claw-wolf-matrix",profile:{...}}`. Select the matching
human family before importing one. Import validates ID/family/version/sex before
replacing the current matrix. Pasting the same JSON into the matrix import box
avoids a native file picker. **Restore canonical matrix** discards local matrix
edits; it does not apply any coefficients. **Export mapping XML** produces the
complete native `MorphLinkProfiles` catalog: the edited matrix, the unchanged
other families and explicit male/female defaults. Select the intended female
family before exporting.

The numeric comparison shows edited-matrix output against the canonical matrix
at identical human inputs. An optional diagnostic coefficient snapshot can replace
that reference; it is explicitly named `claw-wolf-coefficient-snapshot` and is
not a wolf preset. The table reports every target, signed difference, maximum
absolute difference and RMS. Missing reference targets use preview zero.

Exports expose all text through a bounded pageable viewer with a suggested UTF-8
filename. Small presets fit one page; large vertex snapshots retain the complete
text without placing a multi-megabyte value in the DOM. The qualified host's optional
`exports.prepare` service creates an
immutable download in the parent window, outside the plugin sandbox. A host
without that service retains text export; no hidden filesystem write or
undocumented host endpoint is used. Preparing a download does not establish that
the user has saved it. The host advertises its export byte limit; its default
1 MiB is enough for matrices, but full geometry needs an explicitly configured
larger limit (the CLAW development host uses 32 MiB). The complete retained text,
not just the displayed page, is sent for a download.

## Read all vertices and their deltas

The optional public `previews.geometry {preview,shape}` capability supplies
detached current `vertices` and initial/rest `baseVertices` for each shape.
**Read all vertices in both previews** reads every shape in the plugin's two
owned models and computes `current − base` per vertex. The table pages through
all vertices, including zero deltas. Its complete JSON export retains every
current position, base position and three-component delta, with model/shape
names, vertex count, maximum displacement and RMS displacement.

Positions are in model space and game units. Initial means the selected NIF's
rest position, not the current camera view or an interpolated weight endpoint.
The host's browser morph deltas are int16-quantized; this is not a runtime skinning
measurement. Shapes are read sequentially, not as an atomic multi-shape snapshot.
Each snapshot also records the actual morph names and coefficients of both
models. The plugin reads them again after the sequential shape reads and rejects
a snapshot if either vector changed. Preview changes invalidate the retained
snapshot and require a fresh read.
Hosts without the scoped geometry capability show an explicit unavailable state;
the plugin does not fall back to the unrelated main model's geometry.

The controls expose all names in the loaded human TRI, with a filter. Imported
human-only fields such as `Butt`, `BigButt` or `MuscleAbs` remain in the human
preview even when no current CLAW rule uses them. The UI reports those names and
their nonzero values separately from mapped output. It never silently filters a
full human vector down to the configured conversion-source subset.

Resource family and sex are explicit declarations; filenames and available
morphs cannot establish donor provenance. Changing family clears only previously
acknowledged wolf outputs. Changing sex requires reopening matching resources.
Changing a model selection disables Apply until that pair is explicitly opened.
Scene notifications do not automatically apply coefficients.

## Fixed geometry and two input modes

Each preview uses the selected **fixed NIF**. The extension has no neutral
low/high geometry-weight interpolation API. For a weight-100 comparison choose
the matching human `_1` and wolf `_1` resources. A weight-30/50 actor shown on
one endpoint has a known neutral-geometry mismatch; interpolating preset
coefficients does not repair it.

**Already-effective human JSON** is accepted as signed finite float32 numbers.
It is never multiplied by weight again, including when an imported fixture has
NPC-weight metadata. Omitted names use zero for this preview, not an assertion
that an unobserved game value was zero. Full fixture imports preserve per-name
provenance. A configured conversion-source capture is not a complete capture of
every human TRI name or preset slider; reconstructed preset values must retain
their separate provenance.

**BodySlide preset XML** supplies `small`/`big` percentage endpoints. The selected
preset's coefficients are normalized once and interpolated at the separate
0..1 coefficient-weight control, including exact endpoint selection at 0 and 1.
Missing endpoints default to zero. Signed and extrapolated coefficients remain
valid; unknown sizes such as `both`, duplicate endpoints, unsafe names,
nonfinite/overflowing values and DTD/entity declarations are rejected. Comments
and standard predefined/numeric escapes pass to the browser's XML parser. This
strict import policy does not reproduce every BodySlide/OBody dialect quirk.
Preview interpolation uses normalized float32 endpoints and weight, selecting
the exact endpoint when that weight is 0 or 1. Interior weights use the binary64
convex sum `low*(1-weight) + high*weight`, bounded to the endpoint interval,
then rounded once to float32. This avoids overflowing a float32 endpoint delta
or cancelling a tiny endpoint. It is a declared preview reconstruction policy,
not an observed SKEE aggregate or a claim of bit-identical runtime OBody arithmetic.

Independent neutral geometry would require
`V0 + weight*(V1-V0) + sum(effectiveCoefficient*TRIDelta)`. The selected fixed NIF
does not implement its weight term. The current XML examples with equal preset
coefficient endpoints therefore produce the same coefficients at every weight.

## Arithmetic and lifecycle

The `core.js` public evaluator validates and marshals inputs. It contains no
conversion formulas. `distribution/shared/MatrixKernel.cpp` is compiled into the
game DLL and separately into WebAssembly; `matrix-kernel.template.js` only
marshals its28-byte rule ABI and reads results. The embedded WASM has no imports,
engine access, allocator or network calls. Composition uses float32 inputs/gains/caps,
binary64 function evaluation and accumulation in rule order, then
`float32(clamp(sum,0,1)*cap)`. Cap multiplication follows clamping;
NPC weight is absent. Negative target sums reach neutral. Opposed deformations
use explicit lean targets in compatible wolf resources and suitable source
functions; changing a gain does not invent a missing deformation.

The controller uses only explicit `previews.*` operations. Each immutable opaque
preview ID serves as its binding generation, alongside a local session epoch.
Both morph domains are validated before either write. Each host batch is atomic
within its own model; the two calls are **not** a cross-model transaction. A
partial or unknown write failure closes this plugin's pair and reports failure.
Failed cleanup retains exact owned handles for a retry. Another preview and the
main model are never cleanup targets. Closed/replaced sessions invalidate queued
work; unsent human vectors coalesce to the latest one.

The native `previews.link(..., properties:["orientation"])` handles rotation.
No pointer-event RPC echo loop is wired. `pair.js` retains its independent tested
camera/state foundation, but the actual host adapter uses the native link.
Model loads, frame lifetime and renderer disposal remain the host's contract.

## Build and verify

From CLAW with Python 3.12+ and Node.js 22+, using new external build directories:

```powershell
python tools/morphbench-addon/build.py --output-dir '<external-build>' --wasm-compiler '<external-clang.exe>'
python -m unittest discover -s tools/morphbench-addon/tests -p 'test_*.py'
node --require '<external-build>/matrix-kernel.js' tools/morphbench-addon/tests/core.test.cjs '<external-build>/catalog.json'
node --require '<external-build>/matrix-kernel.js' tools/morphbench-addon/tests/pair-state.test.cjs '<external-build>/catalog.json'
node tools/morphbench-addon/tests/input.test.cjs
node tools/morphbench-addon/tests/preview-controller.test.cjs
node --require '<external-build>/matrix-kernel.js' tools/morphbench-addon/tests/sdk-integration.cjs '<external-build>/catalog.json' '<host>/web/addon-sdk.js' '<external-real-pair-inputs>'
node --require '<external-build>/matrix-kernel.js' tools/morphbench-addon/tests/matrix.test.cjs '<external-build>/catalog.json' '<native-claw-preset-tool.exe>' '<external-checks>' '<external-real-pair-inputs>/fixtures-full-preset-reconstruction.json'
```

The builder reads canonical `distribution/profiles/MorphLinks.xml`, validates all
three resource families and preserves XML order. It emits ten local browser
assets in a deterministic ZIP, with an external catalog and SHA-256 build report.
The SDK is loaded from the host and is never copied into the package. The host's
CSP blocks fetch/XHR, so the mapping is a classic local JS asset and imports use
the browser File API or explicit pasted matrix text. Clang with wasm32/wasm-ld
support is an external build dependency; no compiler is bundled. Use
`CLAW_WASM_COMPILER` as an alternative to the command-line option.

Tests cover arithmetic, scoped ownership, cleanup/closure races, partial failure,
latest-input coalescing, family/sex changes, source provenance, complete real
human fixture vectors and the unchanged actual SDK in a detached DOM/message
harness. That harness is not an actual browser, renderer or installed-host test.
The real fixture resources remain outside Git and are not redistributed.
Textured paired-model appearance, user rotation in the qualified host, game
assignment, physics and runtime skinning require their separate acceptance.
