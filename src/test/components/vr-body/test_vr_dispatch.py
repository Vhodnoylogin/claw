"""Portable checks for VR CDD87 derivation and archive projection."""
import hashlib
import json
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory
import unittest
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT/"src/main/components/vr-body"), str(ROOT/"src/main/python/vr")]
import vr_dispatch as dispatch


def nif_fixture(tri_path, extra=b"BODYTRI", collision=None, shape_refs=(2,)):
    strings = [b"body", b"BODYTRI", dispatch.FSMP_HOOK, tri_path]
    blocks = [("NiNode", struct.pack("<III", 0, 0, 1)),
              ("BSTriShape", struct.pack(f"<{2 + len(shape_refs)}I", 0, len(shape_refs), *shape_refs)),
              ("NiStringExtraData", struct.pack("<II", strings.index(extra), 3))]
    if collision:
        blocks.append((collision, b""))
    def string(value):
        return struct.pack("<I", len(value)) + value
    return (b"Gamebryo File Format, Version 20.2.0.7\n" +
            struct.pack("<IBIII3BH", 0x14020007, 1, 12, len(blocks), 100, 0, 0, 0, len(blocks)) +
            b"".join(string(kind.encode("ascii")) for kind, _ in blocks) +
            b"".join(struct.pack("<H", i) for i in range(len(blocks))) +
            b"".join(struct.pack("<I", len(data)) for _, data in blocks) +
            struct.pack("<II", len(strings), max(map(len, strings))) +
            b"".join(map(string, strings)) + struct.pack("<I", 0) +
            b"".join(data for _, data in blocks) + struct.pack("<II", 1, 0))


class DispatchControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (dispatch.BASE/"ArmorAddons"/dispatch.ARMATURE).read_text(encoding="utf-8-sig")
        cls.header = (dispatch.BASE/"RecordData.yaml").read_text(encoding="utf-8-sig")

    def test_male_only_override_retains_world_and_female_weight(self):
        result = dispatch.armor_source(self.source, {"male"})
        self.assertIn("WeightSliderEnabled:\n  Male: False\n  Female: True\n",result)
        unchanged = lambda text: text.split("WorldModel:\n")[1].split("FirstPersonModel:\n")[0]
        self.assertEqual(unchanged(result),unchanged(self.source))
        for sex in dispatch.SEXES:
            self.assertIn(f"  {sex.capitalize()}:\n    File: {dispatch.armor_path(sex)}\n",result)
        self.assertIn("FormKey: 0CDD87:Skyrim.esm",result)

    def test_sex_controls_are_independent(self):
        self.assertIn("WeightSliderEnabled:\n  Male: True\n  Female: False\n",
                      dispatch.armor_source(self.source,{"female"}))
        self.assertIn("WeightSliderEnabled:\n  Male: False\n  Female: False\n",
                      dispatch.armor_source(self.source,{"male","female"}))

    def test_incomplete_or_ambiguous_base_fails(self):
        for source in (self.source.replace("FirstPersonModel:\n",""),
                       self.source.replace("0CDD87","000007"),
                       self.source + "\nFirstPersonModel:\n  Example:\n"):
            with self.subTest(source=source[:70]), self.assertRaises(ValueError):
                dispatch.armor_source(source,{"male"})
        for sexes in (set(),{"unknown"}):
            with self.subTest(sexes=sexes), self.assertRaises(ValueError):
                dispatch.armor_source(self.source,sexes)

    def test_header_requires_claw_load_order_without_small_flag(self):
        data = dispatch.addon_header(self.header)
        self.assertIn("ModKey: CLAW - VR Body.esp\n",data)
        self.assertNotIn("  - Small\n",data)
        self.assertIn("  - Master: Skyrim.esm\n    FileSize: 0\n  - Master: CLAW.esp\n",data)

    def test_assembly_layout_preserves_the_exact_first_person_namespace(self):
        files = {
            dispatch.resource_paths(sex, endpoint): "a" * 64
            for sex in dispatch.SEXES for endpoint in (None, 0, 1)
        }
        manifest = {
            "schemaVersion": 1, "component": "CLAW/vr-body", "files": files,
            "worldOverrides": [], "skeletonFiles": [], "textureFiles": [],
        }
        self.assertEqual(dispatch.resource_layout(manifest), files)
        for invalid in (
            {**manifest, "skeletonFiles": ["skeleton.nif"]},
            {**manifest, "files": {**files, "textures/body.dds": "a" * 64}},
            {**manifest, "files": {name: "bad" for name in files}},
        ):
            with self.subTest(manifest=invalid), self.assertRaises(ValueError):
                dispatch.resource_layout(invalid)

    def test_fixed_profile_requires_both_ranges_and_resource_candidate(self):
        for sexes, resources in (({"male"}, Path("unused")), (set(dispatch.SEXES), None)):
            with self.subTest(sexes=sexes, resources=resources), self.assertRaisesRegex(
                    ValueError, "requires both sexes range-disabled and --resources"):
                dispatch.build(Path("unused"), sexes, resource_candidate=resources, fixed_profile_fomod=True)

    def test_bodytri_must_be_referenced_by_the_shape(self):
        correct = dispatch.bodytri_path("male").encode("ascii")
        for refs in ((), (0,), (2, 2), (2, 255)):
            with self.subTest(refs=refs), self.assertRaisesRegex(ValueError, "exactly one same-sex BODYTRI"):
                dispatch.require_static_nif(nif_fixture(correct, shape_refs=refs), expected_sex="male")

    def test_archive_choices_only_change_the_fixed_alias(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            esp = root/dispatch.ADDON
            esp.write_bytes(b"synthetic compiled ESP")
            assets = {dispatch.ADDON: esp.read_bytes()}
            hashes = {}
            for sex in dispatch.SEXES:
                for endpoint in (None, 0, 1):
                    relative = dispatch.resource_paths(sex, endpoint)
                    asset = root/"resources"/relative
                    asset.parent.mkdir(parents=True, exist_ok=True)
                    assets[relative] = (nif_fixture(dispatch.bodytri_path(sex).encode("ascii"))
                                        if endpoint is not None else relative.encode())
                    asset.write_bytes(assets[relative])
                    hashes[relative] = hashlib.sha256(assets[relative]).hexdigest()
            (root/"install-manifest.json").write_text(json.dumps({
                "schemaVersion": 1, "component": "CLAW/vr-body", "files": hashes,
                "worldOverrides": [], "skeletonFiles": [], "textureFiles": [],
            }), encoding="utf-8")

            direct = root/"direct.zip"
            fixed = root/"fixed.zip"
            repeated = root/"repeated.zip"
            dispatch.assemble(esp, root, direct)
            receipt = dispatch.assemble(esp, root, fixed, fixed_profile_fomod=True)
            dispatch.assemble(esp, root, repeated, fixed_profile_fomod=True)
            self.assertEqual(fixed.read_bytes(), repeated.read_bytes())
            with ZipFile(direct) as archive:
                self.assertEqual(archive.namelist(), [dispatch.ADDON, *sorted(hashes)])
                self.assertEqual({name: archive.read(name) for name in archive.namelist()}, assets)

            with ZipFile(fixed) as archive:
                self.assertEqual(len(archive.namelist()), 11)
                self.assertEqual(receipt["payloadSha256"], {
                    name: hashlib.sha256(archive.read(name)).hexdigest() for name in archive.namelist()
                })
                config = ET.fromstring(archive.read("fomod/ModuleConfig.xml"))
                required = config.findall("requiredInstallFiles/file")
                self.assertEqual(len(required), 7)
                self.assertEqual({
                    node.attrib["destination"]: archive.read(node.attrib["source"]) for node in required
                }, assets)
                group, = config.findall("installSteps/installStep/optionalFileGroups/group")
                self.assertEqual(group.attrib["type"], "SelectExactlyOne")
                choices = group.findall("plugins/plugin")
                self.assertEqual([choice.attrib["name"] for choice in choices],
                                 ["Male player profile", "Female player profile"])
                for sex, choice in zip(dispatch.SEXES, choices):
                    alias, = choice.findall("files/file")
                    self.assertEqual(alias.attrib["destination"], dispatch.LEGACY_ALIAS)
                    self.assertEqual(archive.read(alias.attrib["source"]), assets[dispatch.resource_paths(sex, 1)])

            target = dispatch.resource_paths("male", 1)
            manifest = root / "install-manifest.json"
            initial = json.loads(manifest.read_bytes())
            male_tri = dispatch.bodytri_path("male").encode("ascii")
            invalid_nifs = (
                (nif_fixture(male_tri, extra=dispatch.FSMP_HOOK), "FSMP binding"),
                (nif_fixture(male_tri, collision="bhkRigidBody"), "collision block"),
                (nif_fixture(male_tri, collision="RootCollisionNode"), "collision block"),
                (nif_fixture(dispatch.bodytri_path("female").encode("ascii")), "namespaced Body.tri"),
                (nif_fixture(b"actors\\werewolfbeast\\character assets\\malebodywerewolf.tri"), "namespaced Body.tri"),
            )
            for raw, error in invalid_nifs:
                (root / "resources" / target).write_bytes(raw)
                initial["files"][target] = hashlib.sha256(raw).hexdigest()
                manifest.write_text(json.dumps(initial), encoding="utf-8")
                for fixed_profile in (False, True):
                    rejected = root / "rejected.zip"
                    with self.subTest(fixed_profile=fixed_profile, error=error), self.assertRaisesRegex(ValueError, error):
                        dispatch.assemble(esp, root, rejected, fixed_profile_fomod=fixed_profile)
                    self.assertFalse(rejected.exists())
