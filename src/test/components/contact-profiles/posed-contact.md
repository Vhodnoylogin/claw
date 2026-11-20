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
