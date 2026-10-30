# CLAW human morph link — Morphbench addon

This first consumer previews the current `distribution/profiles/MorphLinks.xml`
with Morphbench's documented browser SDK v1. It is an independent CLAW tool;
it imports no Morphbench backend, native module, private viewer objects or DOM.
It does not install or alter the game, MO2, Distribution, human presets or OBody.

Requires the Morphbench `feature/addons` development host, baseline contract verified at
`8751e0caea425f7b1e90846e18cea3f43afd73ac` (`docs/addons.md` and
`web/addon-sdk.js`). The public 0.8.0 archive does not supply this host.

The same dev-001 ZIP was subsequently exercised in an actual isolated browser
against host `5fff9022abdc3c4cfd6a86c6e00f5901f4d14f43`: installation/enable,
SDK/CSP connection, calculate/apply, family cleanup, preserved ears/tail, reset
with invalid edited JSON and atomic missing-target refusal passed. Synthetic
full/missing-target NIF/TRIP fixtures were used; this is host integration evidence,
not a real-body or game visual acceptance.

Host `5fff902` adds capability-discovered `state.get/set/reset` and explicit
disabled-package updates. Dev-001 still uses the smaller baseline API and does
not restore its controls through that new state service. Statements below about
missing update/storage support describe the baseline `8751e0c` host, not the
newer capabilities. A later consumer slice can adopt them without automatic
application to a newly opened model.

## Build and verify

From the CLAW repository root, with Python 3.12+ and Node.js 22+:

```powershell
python tools/morphbench-addon/build.py --output-dir 'D:/Skyrim VR Modding/Builds/claw-morphbench-addon-20261030'
python -m unittest discover -s tools/morphbench-addon/tests -p 'test_*.py'
node tools/morphbench-addon/tests/core.test.cjs 'D:/Skyrim VR Modding/Builds/claw-morphbench-addon-20261030/catalog.json'
node tools/morphbench-addon/tests/sdk-integration.cjs 'D:/Skyrim VR Modding/Builds/claw-morphbench-addon-20261030/catalog.json' 'D:/Skyrim VR Modding/Repositories/morphbench/web/addon-sdk.js'
```

The output directory is required and must be outside the CLAW checkout. The
standard-library builder reads the canonical XML, checks the current three
families and body-target allowlist, preserves XML rule order, and generates
`catalog.js` directly into a deterministic ZIP. ZIP member times, order, modes
and stored bytes are fixed; the SDK is loaded from the host and is not copied.
Only six local browser assets ship. The external `build-report.json` records
the archive, XML, generator and evaluator SHA-256 hashes; `catalog.json` is an inspection/test snapshot.
No generated mapping or ZIP needs to be added to Git.
The SDK integration test executes the host's actual SDK unchanged in an offline
DOM/message harness. It is not an installed-host, real-browser or visual test.

## Use

Install the built ZIP through Morphbench's addon manager, explicitly enable it,
and open its inspector tab. Open the intended CLAW body with the host's normal
model controls. Select **CBBE 2.0.3**, **3BA 2.48**, or **HIMBO 5.8** explicitly;
the addon does not infer a human resource family from a wolf filename or sex.

Paste or import a JSON object of effective **aggregate human morph values**, for
example HIMBO male heavy input:

```json
{"BellyPot":0.5,"BellyRounder":0.2,"TorsoBelly":0.6,"TorsoBellyChub":0.35}
```

These are already applied human coefficients after morph-key aggregation,
not BodySlide percentage endpoints, an OBody preset name or proof of an actual
OBody assignment. No game capture occurs. Omitted source names mean zero;
unmapped human names are reported and ignored. Non-numbers, nonfinite/overflowing
float32 values, invalid or unsafe names, CLAW input names and unknown profiles
are rejected. Negative human values remain valid inputs.

**Calculate** shows every linked target, the contributing sources and gains,
the raw sum, clamping and final output. It reproduces native `MorphLink::compose`:
float32 source/gain/cap, double accumulation in XML order, then
`float32(clamp(sum, 0, 1) * cap)`. The cap multiplies the clamped sum; it is not
an upper bound applied directly to the raw sum. NPC weight is never applied again.

**Apply linked body targets** revalidates input, confirms a model is open and
checks that every required target already exists in `morphs.get`. A missing
target rejects the entire operation before any write. One `morphs.set` batch
includes zeros for every recognized linked body target, even names with no source
rules (for example neck girth, or HIMBO back width). Ears, tail and other
non-body controls remain outside this addon's scope. When changing families in the same
frame, formerly written targets absent from the new family are zeroed as well.
This validates available target names, not the donor provenance or sex of a model.

**Zero linked body targets** writes zero only to the selected sex's linked body
targets and any targets this frame previously wrote. It never calls
`morphs.reset`, never changes ears/tail/head/paw/claw/adult controls and does not
restore values that existed before applying. SDK v1 has one shared preview
value per name, without per-addon morph-key ownership; explicit apply/reset can
therefore replace a user's values on those same linked body controls.

The current catalog clamps output nonnegative. Source reductions with no opposed
wolf deformation can reach zero but cannot reproduce slimmer-than-neutral
geometry. This preview establishes mapping arithmetic only. It does not prove
game assignment, rendered quality, runtime skinning, contacts or physics.

## Development updates and current API gaps

Baseline host `8751e0c` rejects an already installed ID (`alreadyInstalled`). Use
a fresh external addon directory/configuration or a distinct development ID there.
Host `5fff902` supports explicit update of a disabled package with the same ID:
validate/install the new ZIP through the addon manager, then explicitly enable it.
Rebuilding unchanged sources reproduces the same package. Editing installed files
is never the update workflow; old hosts cannot read the newer registry format.

Changing models recreates this frame and clears its memory. Dev-001 has not yet
adopted the new host's namespaced state methods, so copy the JSON outside the frame
before switching and paste/import it again, then reselect the family. The addon
does not use opaque-origin local storage, private host state or browser internals.
No automatic write follows a scene event or model reload. Model opening is left
to the host in this slice. The newer `state.get/set/reset` service has tab-session
scope, not durable project storage; future adoption must restore controls only.

The SDK has no model revision token for a read/validate/write transaction;
the host validates the entire `morphs.set` batch against its current morph list
atomically. A navigation normally destroys this frame. Later anatomical metrics
will additionally need skin weights and appropriate bind/node transforms: v1
`scene.geometry` exposes bone names and model-space vertices, not those skinning
data. Those gaps do not prevent this first mapping consumer.
