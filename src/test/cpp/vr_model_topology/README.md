# Skyrim VR model topology witness

This test-only SKSE plugin examines the current wolf player's default,
explicit third-person and explicit first-person model roots. It includes
both biped roots and active/buffered part clones. Each graph receives an alias
valid only within its capture, and the inventory uses CLAW's four target
geometry roles. A second route read checks that the same player, race, base,
cell, roots and slot routes were present at both ends of the task.

Build with the same cross-runtime CommonLib flags as the CLAW DLL. The
standalone source exports the legacy Skyrim VR loader interface and admits
Skyrim VR 1.4.15 with SKSEVR 2.0.12 or newer. Compile the adjacent Papyrus
declaration as its companion. This component is outside the release build.

Capture takes an increasing positive nonce and queues one SKSE task. Read
polls that nonce without queuing work. A capture expires after three seconds
and permits up to 48 distinct roots. The witness allows 4096 objects, 128 geometries and 8192 child links per
graph, independently from the original application bounds. A capture reports
the selected model path and whether a part handle is present. The handle is
never dereferenced. A load transition invalidates cached replies.

Schema 3 also inventories the typed player VR world, room, height,
headset, wand, melee-offset, hand and clavicle roots. A capture records
the raw weapon state and checks it again at the end of the same task. Each
graph includes a bounded list of geometry names, types, local application
cull flags and available triangle-shape vertex/triangle counts. The details
are limited to 16 entries per graph and carry a completeness flag.

Schema 4 adds the local application cull flag for each observed root, then
reads up to 16 parent cull flags in nearest-first order. A known set flag
is reported even if the remaining chain is incomplete. A clear chain
requires reaching its end. Depth limits and cycles remain explicit.
The same task rechecks parent identities and flags and records the raw
live camera state ID when available. Pointer identities stay in the task.
The pure chain traversal is covered by `claw-vr-root-cull` in CTest.

The game paths are read-only. Graph membership and matching observations do
not establish rendered geometry, continuous attachment or applied physics.

## Loaded Body32 origin

Use `CaptureDispatch(nonce)` to add the schema 8 marker observation. The
original `Capture(nonce)` returns schema 4. `Read(nonce)` preserves the
requested mode. The marker capture adds the runtime handle, actor-base sex
and readable weight, and a native QPC interval for the same task.

The four rows are ordered third-person active/buffered and first-person
active/buffered. Each scans the exact Body32 clone only when it belongs to
the current wolf's body item, armor addon and corresponding actor graph.
The nine count positions are `M0`, `M1`, `F0`, `F1`, `H_M0`, `H_M_STATIC`,
`H_F_STATIC`, `H_M_FSMP` and `H_F_FSMP`. The walk
checks reciprocal attachment and the authored empty marker node, then
repeats the observation to catch intervening changes. An absent clone,
foreign slot, missing attachment, incomplete walk, zero markers or
conflicting markers are distinct results.

Use the detached marker assets only in an admitted test. In the retained
fixture, `M0/M1` and `F0/F1` label the four namespaced NIFs. `H_M0` labels
the older male legacy-path fixture. The four new markers identify the
fixed-profile legacy-path candidates by sex and by static or FSMP binding.
Schema 7 recognizes the private player armor pair from `test_CLAW - VR Player Body32.esp`.
The marker names `P_M` and `P_F` identify its two authored models. The capture
resolves the exact two local forms before each scan, checks that the armor links
to the addon, and reports their runtime IDs in `playerBody32Fixture`. The verifier
requires separately observed fixture IDs before claiming its model origin:

```text
python src/test/components/vr-body/verify_dispatch_markers.py CAPTURE.json --view thirdPerson --pid PID --nonce NONCE --epoch EPOCH --fixture-forms ITEM ADDON --expect P_M
```

Use `P_F` for a female trial. Remove the armor and take a separate stock-route
sample after the trial. Compare the installed winners to the staged archive in
the same run. The marker reader also accepts historical schema 5 and 6 captures
with their original widths.

Schema 8 adds `W_M` and `W_F` for the equipped world models with visible
ear skin. These markers require the admitted fixture pair, the active world
clone and the matching reported `EarWorldTrial.nif` path. The first-person
models retain the `P_M` and `P_F` markers. Both motion variants use the same
world marker because the marker establishes the model route. Verify the
exact installed NIF and its FSMP registration separately. The verifier still
accepts schema 7 with its original marker counts.

In dispatch captures, the attached active Body32 clones allow up to 32 detail
entries. When present, `head_CLAWHead` and `head_CLAWHead_CLAWEars` include
the live shape's `BODYTRI` link and its skin partition vertex and triangle
counts under `meshSource`. These fields are sampled once in the same task as
the route recheck. Unavailable fields are null.
These measurements can distinguish the split ear skin from the unsplit head
when an empty fixture marker is missing. They describe the attached geometry.
Identical files at different paths still require a controlled asset comparison.

For the separate world/first-person outfit, classify both views from the same
schema 8 capture:

```text
python src/test/components/vr-body/verify_dispatch_markers.py CAPTURE.json --paired --pid PID --nonce NONCE --epoch EPOCH --fixture-forms ITEM ADDON
```

This checks the sex-specific world and first-person paths and markers together.
It distinguishes two independent active clones, a world clone with both
first-person banks empty, and an unresolved first-person route. The report
includes the raw camera state and effective application cull for each actor
root and active clone. A loaded clone can be culled. A marker in the buffered
bank cannot establish an active model. Only two separately observed active
routes give exit code 0 in this mode. This command does not test the older
outfit that deliberately used a shared model in both views.

Confirm the actual installed winner bytes and the effective
armor record alongside each process-owned capture. Review the
requested active slot with the verifier in `src/test/components/vr-body`:

```text
python src/test/components/vr-body/verify_dispatch_markers.py CAPTURE.json --view firstPerson --pid PID --nonce NONCE --epoch EPOCH
```

Use a fresh nonce for each observation. The verifier treats overlapping views
and a marker only in a buffered clone as unresolved results. Its successful
verdict identifies the observed marker's fixture asset. Weight interpolation
and headset visibility require their own measurements.

`stage_world_motion_markers.py` in `src/test/components/vr-body` prepares
one common fixture and four mutually exclusive world-motion arms. Supply
the exact fixed-profile ZIP, the directory containing the two exact motion
ZIPs, the rebuilt witness directory with `WITNESS-BUILD.json`, PyNifly and a
new output directory. The arms use the released core with physics set to
None. Use the active third-person row for this test and compare it with
the selected arm and VFS winner. An observed FSMP marker identifies the
loaded mesh. A separate provider observation must establish registration
of exactly one actor-owned system and its normal retirement.

The initial offline build produced the DLL and PEX. The local build receipt
is under Builds/claw-vr-model-topology-20261119/build-02, SHA-256
544932afc4afc9852e61a6c7eec6ed689998f80f3f46c55517cd9745e8444832.
The first isolated VR run reached its 15 baseline checks but SKSEVR
rejected the witness query before any transformation. The installed loader's
version carries a VR subtype nibble. The witness now uses CLAW's existing
runtime-target check and keeps the exact VR-family filter. The fixed binary
compiled with the same SDK and its own companion PEX. Its first game
qualification is recorded separately from the build.

## Post-phase torso capture

`build_torso_capture.py` builds a distinct diagnostic from the retained R06
observer using its sealed source, commands and MSVC dependencies. Supply the
R06 build directory, the pinned RaceMenu API header, the retained compiler
environment script and a new external output directory:

```text
python src/test/cpp/vr_model_topology/build_torso_capture.py --r06 <native-r06> --skee <IPluginInterface.h> --environment <capture-environment.cmd> --out <new-external-directory>
```

This preserves the original Papyrus declarations and five-bone packet. The
extension adds `torsoCaptureVersion`, `torsoBodyTri`, `torsoBones` and
`effectiveMorphs` in the same post-VRIK/HIGGS sample. `TorsoPose.h` observes
the loaded `HEAD` skin's actual palette and brackets it with readings of the
effective RaceMenu values. The R06 candidate retains its male fixture gate.
The helper's female palette is checked against its NIF/TRI separately.
Pass an independently admitted capture to the VR torso replay to reconstruct
clearance. The candidate does not acquire rendered pixels or modify the game,
and remains a separate test build.

### Post-phase ear and stereo sample

Use the same build command with `--subject ears` and a separate output
directory. This variant captures the exact trial ear shape and its
sex-specific `EarWorldTrial.tri` route on the player's active world Body32.
The same post-phase callback reads six skin bones, five effective TRI values,
both typed engine frusta and viewports, and OpenVR's per-eye projection extents
and eye-to-head transforms. Camera, HMD, active Body32 and optics are checked
again before publishing. Positive topology counts must match the trial. A zero
runtime count is recorded as unavailable and requires independent asset proof.

Use the retained R06 PEX and match the deployed mesh and TRI to the
exact trial archive independently. OpenVR transforms retain their own basis
and units. The stereo sample records `eyeProjectionQualified` and
`atomicRenderSnapshot` as false. Calibrate eye orientation and game scale on
controlled points and geometry before using the packet to judge clearance.

Replay the admitted Papyrus reply with:

```text
python -B src/test/components/vr-body/avatar_ear_stereo.py --packet <raw-reply.json> --admission <run-evidence.json> --pynifly <path> [--calibration <controls.json>]
```

The executor supplies `claw-vr-ear-stereo-admission/1` with `pid`, `epoch`,
`nonce`, actor `handle`, `sex`, `weight`, `higgsBuild`, the `static` or `fsmp`
`mode`, and `armedAfterPhase` from the last completed post-phase count before
the request. Use a fresh nonce and retain its request timestamp. `archive`
and `witnessDll` each need `path`, `bytes` and `sha256`. Supply `mappedWitness`
with its independently observed `pid`, `bytes` and `sha256` for the loaded
module, and `effectiveVfs` with independently measured `bytes` and `sha256` for
each trial archive member keyed by its archive path. Keep the request, exact
asset pins and winner/module evidence in the same run record. The replay
validates their agreement. The caller supplies their provenance.

With just the admitted reply, the replay reconstructs the ear mesh from pose,
skin weights and TRI offsets and reports world bounds in game units. Optional
`claw-vr-ear-stereo-calibration/1` controls must match `captureSha256` for the
inner reply. Provide disjoint `headFit` and `headHoldout` 3D point pairs with
`providerHeadMeters` and `worldGu`, plus independently measured `left`, `right`,
`bottom`, `top`, `near` and `interior` world points for each eye in `eyes`.
`projectionControlsConsistent` reports numerical agreement with those
points. Use `providerFrustumIntersection` for geometric counts and depths in
metres. The captured engine side planes and rendered pixels remain separate
evidence. `engineProjectionQualified` and `renderedPixelsVerified` stay false.

For motion, pass `--baseline-packet` and `--baseline-request` alongside the measured
packet. The baseline request has its own `nonce` and `armedAfterPhase`. Use the
same admitted actor, world and assets, and complete that request before arming
the measured one. Both captures must have the same effective ear morphs.

The replay reports movement in world coordinates and in the head frame. It
also reconstructs the later pose carrying the earlier ear drivers relative to
the head, with the later non-ear support intact. The difference isolates the
ear driver contribution. Head-relative distances use the head's local scale.
Use matched static and provider-on controls to attribute motion to FSMP.

### Equipped player ear sample

Use `--subject equipped-ears --papyrus <PapyrusCompiler.exe>` with a separate
build directory. This produces `CLAWVREquippedEarPose.dll` and its own
`CLAWVREquippedEarPose.pex`, which can be staged with the ordinary schema 8
`CLAWVRModelTopology` DLL and PEX without a file or script override. Call
`CLAWVREquippedEarPose.Capture(nonce)` and `Read(nonce)` for the ear sample. It
reports `claw-vr-vrik-ear-stereo/2` with `qpcBegin`, `qpcEnd` and `qpcFrequency`
from the post-VRIK/HIGGS callback. It resolves the fixture ESP's own armor
and single addon at runtime, then checks the active sex-specific
`EarWorldTrial.nif` world route and its `W_M` or `W_F` marker. It accepts an
empty first-person slot or a separately owned, culled `Body_1.nif` slot with
the matching `P_M` or `P_F` marker. Both buffered slots must be empty. It
checks body ownership, slots, visibility and marker attachment again before
returning the sample. This is the world-body trial with the other view hidden.

Use `--subject equipped-tail --papyrus <PapyrusCompiler.exe>` to build the
separate `CLAWVREquippedTailPose` DLL and script. Its `Capture` and `Read`
return `claw-vr-equipped-tail-contact/1` under the same equipped route and
QPC checks. The observer uses the `body` shape, with 18,359 vertices,
34,195 triangles and a 65-entry skin palette. It checks the fixture's
sex-specific `BODYTRI` and confirms that name lookup from the actor root
finds the same `TailBone02` used by the skin. The capture includes the five
bones and eight effective RaceMenu channels of the four TailBone02 support
slots, together with the pose of the left wand. It does not require the
stereo optics sample. `verify_equipped_turnover.py` accepts its capture as
an optional `tailPose` during the equipped phase, in addition to `earPose`.
Compare the returned geometry inputs with the acknowledged fit and use
separate CBPC callback evidence for the contact verdict.

Use the same replay command with `claw-vr-ear-stereo-admission/2`. Supply the
`fixtureForms` object containing the independently observed runtime `item`
and `addon` IDs. The full IDs must share the loaded fixture ESP index and
have local IDs 0x801 and 0x800. Pin the base player Body32 ZIP in `archive`.
Include a pin for the world FSMP ZIP in `motionArchive` only for the FSMP arm.

For `effectiveVfs`, pin the fixture ESP and the selected sex's
`EarWorldTrial.nif`, `EarWorldTrial.tri`, `Body_1.nif` and `Body.tri`. Add
the chosen XML for the active arm. That arm takes its world NIF and XML
from the overlay, with the remaining files still supplied by the base.
The replay checks both ZIP inventories and reparses the admitted ESP.
Use separate provider records to establish FSMP registration, teardown,
or contact. The ear samples establish motion and route once captured in
an admitted game, with no inference about rendered pixels.
