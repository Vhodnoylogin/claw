# CLAW VR body resource prototype

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
