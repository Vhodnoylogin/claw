# CLAW VR body resource prototype

## Selective visibility on the composed family

`prepare_first_person.py` now prepares a separate **first-person-only** visibility
candidate from the exact six `final-composed-004` files pinned in
`composed-visibility-profile.json`. It sets the hidden file flag on the eleven
reviewed anatomical head-side shapes, including `head_CLAWHead`. The retained
`head` shape is the torso piece with its original head texture/material; the
female's 450 BreastSize deltas in that piece stay visible. Selection uses exact
shape names, never a substring or an entire Head bone.

```powershell
python vr/prepare_first_person.py --body-root '<final-composed-004>/meshes/actors/werewolfbeast/character assets' `
  --out-dir '<new-external-directory>/first-person'
```

The new directory contains `female/first-person_0.nif`, `first-person_1.nif`,
the analogous male pair, the two unchanged absolute TRIs and a verification
report. These deliberately have **no game load tree**. The report restricts
selection to the first-person graph and supplies no engine filename, world-model
override, plugin, skeleton or installation step. Every source file is checked
again after building. Source world bodies remain unchanged.
The admitted source hashes are captured before dependency loading and retained
through final verification; a source changed during dependency loading is
rejected before output creation.

Each of the four endpoints changes exactly eleven bytes. Complete byte
reconstruction proves that only the intended hidden bits changed; independent
native readback verifies geometry, topology, UVs, materials, skinning, shape names,
BODYTRI paths and morph-index correspondence. It also refuses hiding any nonzero
BreastSize support or either hand's weighted vertices, and checks retained shape
and ancestor visibility. Both neutral weight endpoints retain their distinct
geometry and their sex's original shared TRI.

The 28 October offline result is
`D:/Skyrim VR Modding/Builds/claw-parallel-20261028/vr/first-person-002/`.
Its `first-person-visibility-report.json` records the four exact byte ledgers,
resource/dependency/source hashes, material paths, preserved breast/hand support
and **remaining visible Head influences**. File-hidden flags do not establish
camera clearance or runtime visibility. VRIK may still shrink retained
Head-influenced torso vertices; actual graph ownership, flag persistence during
reload/morph updates, sex/weight dispatch, camera/neck appearance, IK and physical
contacts remain open runtime gates. This is not an installable VR mod.

To include the three native regressions for that output in the existing suite:

```powershell
$env:CLAW_VR_COMPOSED_ROOT='<final-composed-004>/meshes/actors/werewolfbeast/character assets'
$env:CLAW_VR_VISIBILITY_ROOT='<new-external-directory>/first-person'
python -m unittest discover -s vr/tests -v
```

Without both explicit resource roots those three checks are skipped. A copied-NIF
regression changes `head.dds` to `heax.dds` during dependency loading and verifies
rejection without writing a candidate. Seven
dependency-free regressions cover graph restriction, exact head/torso selection,
ancestor visibility and refusal of hidden breast/hand support.

## Retained initial visibility prototype

The newer anatomical/composed builders live in `scripts/split-vr-body.py` and
`scripts/compose-vr-body.py`; they preserve the head-textured torso as a separate
material part and support the corrected body carrier. The optional
`prepare_ik_aliases.py` produces a names-only XP32 alias compatibility experiment
in a new external directory. It preserves every block and node, but is not
installed or runtime-qualified. See [the current VR analysis](../docs/vr-body.md)
before using the retained initial visibility-only prototype below.

The standalone builder prepares both-sex first-person body resources from the
hash-pinned published 0.6.2.0 bodies. It sets five verified face-only shapes hidden
and proves that every other NIF byte and every TRI byte remains unchanged. The
mixed `head` shape stays visible: it also contains upper torso/breast geometry.
The guard rejects hiding BreastSize/torso morph support or torso-level non-head
weighted geometry. Selective head masking is absent from this initial builder;
the separate composed-family candidate above implements file visibility only.

These are **offline resources, not an installable VR mod**. A working weight-enabled
engine entry, sex selection, first-person morph application, suitable XP32-compatible
IK and actual camera/hand collision behavior remain unqualified. No skeleton,
plugin, native hook, preset or interaction configuration is generated.

Build into a **new external directory**, with local dependencies configured in
the ignored `build.local.json`:

```powershell
python vr/build_body.py --out-dir '<external>/claw-vr-body/resources'
python -m unittest discover -s vr/tests -v
$env:CLAW_VR_NATIVE_TESTS='1'
python -m unittest discover -s vr/tests -v
```

The [mechanism, measured results and remaining gates](../docs/vr-body.md) explain
why a complete runtime implementation cannot yet be packaged.

The [record auditor](engine_audit.py) reads an explicit Skyrim/CLAW record chain,
checks the race/skin/addon slots and exact corrected resource hashes, and compares
an optional reference plugin separately. It refuses plugin/layout generation
because the native VR beast filename and weight branch remain unresolved.

```powershell
python vr/engine_audit.py --master '<SkyrimVR>/Data/Skyrim.esm' `
  --resources '<external>/verified-resources-002' --out-dir '<new-external>/record-audit'
```

Exit code **2** is the expected completed refusal with a JSON report; code **1**
means malformed, missing or unsupported input. This command does not read or
change the active profile. See the full documentation for the optional installed
record tests and declared override/reference arguments.
