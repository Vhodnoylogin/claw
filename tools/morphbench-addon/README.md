# CLAW human/wolf comparison — Morphbench addon

This independent CLAW tool opens a human body and a wolf body in two host-rendered
preview panels. One full human morph vector controls the human preview and the
canonical many-to-many CLAW conversion. Wolf outputs are derived and read-only;
there is no inverse conversion. Rotating either panel follows the other through
the host's native orientation link. Zoom, pan and framing remain independent.

The consumer uses the documented additive API v1 independent-preview contract.
Published Application 0.8.0 lacks those capabilities: this addon displays a clear
message and retains calculation/import, without trying to modify the main view.
The inspected extension is in Morphbench's `feature/addon-multi-view` worktree;
qualified host revision and actual paired-browser acceptance are still pending.
An API number alone does not prove that the extension is present.
The dev-004 pilot opened the actual male HIMBO/CLAW pair in the isolated source
host. Browser import/apply acceptance remains incomplete after a file-chooser
timeout and a reported user stop of computer control; offline suites are not
substituted for that acceptance.

This tool installs or edits no game, MO2 profile, Distribution DLL, human preset,
texture or skeleton. It imports no Morphbench backend, private renderer or DOM.
It is a separate addon ZIP, not part of either CLAW game package.

## Use

1. Install the addon ZIP through Morphbench's addon manager, explicitly enable it
   and open its inspector. Updating the same ID requires disabling it, using the
   manager's update operation, and enabling it again. Dev-004 retains the original
   `claw-human-link-dev-001` ID and uses version `0.2.0-dev.4`.
2. Declare the actual human resources: **HIMBO 5.8 male**, **CBBE 2.0.3 female** or
   **3BA 2.48 female**. Select the exact human and wolf catalog entries and click
   **Open comparison pair**. The addon opens no models automatically.
3. Import a full human coefficient JSON, a retained evidence-fixture JSON with
   `humanValues` and optional per-name provenance, or a BodySlide preset XML.
   Review the human controls and the read-only wolf calculation.
4. **Apply to both previews** writes the human vector to the human model and
   its mapped body outputs to the wolf. The optional **Apply human slider edits
   live** switch enables subsequent human slider edits; it starts unchecked.
5. **Zero owned wolf outputs** preserves the human vector, ears/tail and unrelated
   wolf controls. **Close comparison pair** disposes this addon's two previews.

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

`core.js` remains byte-for-byte unchanged from dev-001. It implements native
`MorphLink::compose`: float32 inputs/gains/caps, double accumulation in XML rule
order, then `float32(clamp(sum,0,1)*cap)`. Cap multiplication follows clamping;
NPC weight is absent. Negative sums can reach neutral but cannot create an
opposed wolf deformation that does not exist in the current resource.

The controller uses only explicit `previews.*` operations. Each immutable opaque
preview ID serves as its binding generation, alongside a local session epoch.
Both morph domains are validated before either write. Each host batch is atomic
within its own model; the two calls are **not** a cross-model transaction. A
partial or unknown write failure closes this addon's pair and reports failure.
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
python tools/morphbench-addon/build.py --output-dir '<external-build>'
python -m unittest discover -s tools/morphbench-addon/tests -p 'test_*.py'
node tools/morphbench-addon/tests/core.test.cjs '<external-build>/catalog.json'
node tools/morphbench-addon/tests/pair-state.test.cjs '<external-build>/catalog.json'
node tools/morphbench-addon/tests/input.test.cjs
node tools/morphbench-addon/tests/preview-controller.test.cjs
node tools/morphbench-addon/tests/sdk-integration.cjs '<external-build>/catalog.json' '<host>/web/addon-sdk.js' '<external-real-pair-inputs>'
node tools/morphbench-addon/tests/real-inputs.test.cjs '<external-build>/catalog.json' '<external-real-pair-inputs>'
```

The builder reads canonical `distribution/profiles/MorphLinks.xml`, validates all
three resource families and preserves XML order. It emits nine local browser
assets in a deterministic ZIP, with an external catalog and SHA-256 build report.
The SDK is loaded from the host and is never copied into the package. The host's
CSP blocks fetch/XHR, so the mapping is a classic local JS asset and imports use
the browser File API.

Tests cover arithmetic, scoped ownership, cleanup/closure races, partial failure,
latest-input coalescing, family/sex changes, source provenance, complete real
human fixture vectors and the unchanged actual SDK in a detached DOM/message
harness. That harness is not an actual browser, renderer or installed-host test.
The real fixture resources remain outside Git and are not redistributed.
Textured paired-model appearance, user rotation in the qualified host, game
assignment, physics and runtime skinning require their separate acceptance.
