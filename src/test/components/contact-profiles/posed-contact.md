# Offline posed contact geometry check

Use the external conservative 128-slot `fitted-capsules.json`, a ready
`claw-vr-npc-pose/1` response and a separately recorded complete target morph
vector for that same witness snapshot. The vector record must contain these
fields.

- `pid` and `sequence` from the witness response.
- `actor`, `base`, `runtimeHandle`, `loadEpoch`, `rootToken`, `qpcBegin`
  and `qpcEnd` from the witness sample.
- `modelIdentity`, `sex` (`male` or `female`), normalized `weight` and
  `morphs`. Include every model morph by name, including zeros.

The harness is responsible for acquiring the effective vector in the same
observation and for retaining the archive and witness provenance. The
identity fields let the checker refuse mismatched inputs.
Use `--native-effective` in place of `--vector` for a witness that carries
the complete RaceMenu vector in that same snapshot. Out-of-range inputs
remain a refusal for this fitted model. `--observed-assets` accepts a JSON
object with `low`, `high` and `tri` source pins with `path`, `bytes` and
`sha256`. The caller obtains these from the actual model route and VFS.
The checker requires identical observed endpoints, the original TRI bytes,
and exact vertices, faces, skin weights and bind data for the two named
support shapes. Other NIF blocks can differ.

```text
python src/test/components/contact-profiles/posed_contact.py --model <fitted-capsules.json> --model-sha256 <sha256> --pose <witness.json> --vector <vector.json> --pynifly <PyNifly-dir>
```

The default check covers the right ear and the TailBone03 and TailBone05
regions. Repeat `--slot` to choose individual ear or tail slots. For example,
slot 108 requires `NPC Pelvis [Pelv]` in addition to the currently observed
tail drivers. The checker refuses any missing bone with positive weight.

The archived NIF and TRI hashes, source triangles and reconstructed rest
points are checked before the comparison. Each comparison uses the same
posed support triangles for the original rest-fit capsule and the posed
refit. Distances are in the capsule owner's local units. Each slot's
assigned excess and sampled surface distances describe that snapshot.
Provider contact and runtime fitting remain separate.

VR63 provided a fully independently bracketed male NPC sample and all 31
effective RaceMenu inputs at zero, actor weight 50. Against the actual
pinned VFS geometry, 24 support slots had sufficient named pose bones. The
largest measured vertex excess outside its rest capsule was 0.154986 in
owner-local units. An enclosing fit built from that same sampled set left
no assigned vertex excess beyond floating-point error. This is a single
pose comparison without holdout or false-positive contact qualification.
The second native sample lacked its final independent observer bracket.
The exact geometry replay SHA-256 is
`8c5a415b8b2a35d10587b565f242142d24c20c6bfbfdd2cde11cdbd319b2510e`.

Stock HIGGS 1.10.10 reports hand, mass and separating velocity in its
collision callback. Its deliberate-grab API can identify the held object
and node on the next update. Stock PLANCK 0.8.2 identifies the target and
node of a registered melee hit. Neither API exposes registration for this
capsule set or per-bone passive contact. The verified installed binaries
for these reviews were `82105ee512767be621eadf73db038adf108c6cb3edb736838c60b78ffbc6a527`
and `c613d7ede46e5f1ab32eed64fb962c420b29c21a3871b9c804f7c6b7a27a37e7`.
The separately installed PLANCK stability patch has different bytes.

The CLAW contact host uses CBPC capsule indices. A prospective internal
overlap comparison can use its actor/node/duration mod event with the
same hand path before attach, after one attach and after removal. This
requires a separately verified provider and exact target ownership.

## Stationary controller contrast for a TRI refit

Run `prepare_tail_refit_contrast.py` with the retained VR `fitted-capsules.json`
and `claw-contact-profile-numeric.exe`. The script pins both inputs and writes
one new external JSON report. It exercises the complete compiled male VR bank
at weight .5 with `CLAWTailLength` 0, 1 and 0. The third bank must equal the
first bank exactly. It measures all four TailBone02 slots together because
stock callback events identify the node without distinguishing its slots.

```powershell
python src/test/components/contact-profiles/prepare_tail_refit_contrast.py `
  --profile <retained-VR-fitted-capsules.json> --numeric <retained-numeric-exe> `
  --out <new-external-report.json>
```

Using the provisionally assumed unit scale and a radius-three sphere, the
retained report found a stationary center with 1.015 owner-local units of
separation at neutral, 1.063 units of overlap at full morph and 1.015 units
of separation after returning to neutral. The report is
`TAIL02-FIXED-SPHERE.json`, SHA-256
`40e4bc0d6de967e0a0d0199d59721287b928d40a5d9842ee7b7d59c8e5838be5`.

The live check still needs the same owned actor/root, the observed aggregate
RaceMenu vector, the exact active capsule bank, actual controller scale and
co-sampled poses. Correlate same-node callbacks with the measured overlap and
verify the neutral-return cleanup before any release claim. The offline grid
provides a search target. In-game confirmation still depends on a reachable
controller pose, the animated mesh and actual provider contact events.

After the adaptive VR run, check its retained manifest and raw step log:

```powershell
python src/test/components/contact-profiles/verify_tail_refit.py `
  --manifest <adaptive-capture.json> --steps <raw-steps.jsonl> `
  --profile <retained-VR-fitted-capsules.json> --basis <TAIL02-FIXED-SPHERE.json>
```

The verifier requires the same actor and a fixed controller pose across the
neutral, morphed and returned holds. It compares the four active native slots
with their neutral bank, the aggregate RaceMenu vector and the scoped CBPC
events. It also checks for quiet holds before attachment and after detachment.
Provider events identify the bone shared by the four slots. The earlier
fixed-sphere run cannot qualify as evidence for this scenario.

## Native timing replay

The optional replay uses the exact VR65 native input and geometry result
recorded in the [VR evidence](../../docs/vr-readiness-20261119.md). It
extracts packed skin weights and projects the current morph's vertices
into each influencing bone's bind frame. Shared vertices are skinned
once. The existing C++ enclosing fitter then consumes each slot's support
in its owner's local frame. The generated header stays external.

```powershell
python src/test/components/contact-profiles/export_pose_fit_benchmark.py --native <VR65-NATIVE-INPUTS.json> --geometry <VR65-POSED-GEOMETRY.json> --model <fitted-capsules.json> --out <external-input-directory>
cmake -S src/test/components/contact-profiles/native-replay -B <external-build-directory> -DCLAW_POSE_BENCH_INPUT_DIR=<external-input-directory>
cmake --build <external-build-directory> --config Release
```

Run the resulting `claw_pose_support` executable. It checks all 64 fitted
capsules against independent replay coordinates before printing separate
reconstruction and fit timings. Timings omit provider updates, acquisition
of game state and any model change. The executable is a test target.
