# CLAW VR body resource prototype

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
weighted geometry. Selective head masking remains unimplemented.

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
