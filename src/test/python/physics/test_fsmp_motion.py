"""Lossless FSMP hook edits and complete original motion constraint graphs."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[4] / "src/main/python/physics"
sys.path.insert(0, str(ROOT))
import fsmp_motion as fsmp


def fixture(extra=False):
    kinds = ["NiNode", "BSTriShape", "NiStringExtraData"]
    strings = [b"Scene Root", b"BODYTRI", b"existing/path.tri"]
    root = struct.pack("<II", 0, int(extra)) + (struct.pack("<I", 2) if extra else b"") + b"opaque root rest"
    blocks = [root, b"opaque original geometry skin material bytes", struct.pack("<II", 1, 2)]
    prefix = b"Gamebryo File Format, Version 20.2.0.7\n" + struct.pack("<IBIII", 0x14020007, 1, 12, len(blocks), 100) + b"\0\0\0"
    return (prefix + struct.pack("<H", len(kinds)) + b"".join(struct.pack("<I", len(k)) + k.encode() for k in kinds)
            + struct.pack("<3H", 0, 1, 2) + struct.pack("<3I", *map(len, blocks))
            + struct.pack("<II", len(strings), max(map(len, strings)))
            + b"".join(struct.pack("<I", len(s)) + s for s in strings) + struct.pack("<I", 0)
            + b"".join(blocks) + struct.pack("<II", 1, 0))


def written_hook(payload, name):
    """Read the actual root references, without trusting the builder's report."""
    nif = fsmp.Nif(payload)
    count = struct.unpack_from("<I", nif.blocks[0], 4)[0]
    for offset in range(8, 8 + count * 4, 4):
        index = struct.unpack_from("<I", nif.blocks[0], offset)[0]
        if nif.kind(index) == "NiStringExtraData":
            key, value = struct.unpack("<II", nif.blocks[index])
            if nif.strings[key].decode() == name:
                return nif.strings[value].decode()
    return None


class FsmpMotionTests(unittest.TestCase):
    def builder_fixture(self, directory):
        root = Path(directory)
        inputs, baseline = root / "inputs", root / "baseline"
        inputs.mkdir()
        baseline.mkdir()
        resources = {}
        for index, role in enumerate((*fsmp.common.BODY_ROLES, "skeleton")):
            resources[role] = inputs / (role + ".nif")
            resources[role].write_bytes(fixture(extra=bool(index % 2)))
        (baseline / "hdtSMP64.dll").write_bytes(b"synthetic provider presence, not an executable")
        reads = []

        def read_nif(path):
            path = Path(path)
            reads.append(path)
            # The API boundary is synthetic; hook readback still consumes the
            # newly written binary, including its actual root extra-data array.
            payload = path.read_bytes()
            female = path.name.startswith("female")
            nodes = fsmp.common.source.NODES + fsmp.common.source.BREAST_NODES
            weighted = fsmp.common.source.NODES + (fsmp.common.source.BREAST_NODES if female else ())
            shape = SimpleNamespace(name="skin", verts=[(), ()],
                                    bone_weights={node: [(0, .5)] for node in weighted})

            def extra_data(*, blockname, name):
                self.assertEqual(blockname, "NiStringExtraData")
                value = written_hook(payload, name)
                return None if value is None else SimpleNamespace(string_data=value)

            return SimpleNamespace(nodes={node: None for node in nodes}, shapes=[shape],
                                   root=SimpleNamespace(get_extra_data=extra_data))

        original_json = fsmp.common.source.SourceInputs.json

        def fixture_json(instance, name):
            data = original_json(instance, name)
            if name == "capsules.json":
                data["provenance"]["xp32Sha256"] = hashlib.sha256(resources["skeleton"].read_bytes()).hexdigest()
            return data

        return (resources, baseline, SimpleNamespace(NifFile=read_nif), reads,
                patch.object(fsmp.common.source.SourceInputs, "json", fixture_json))

    def test_hook_adds_only_one_root_reference_and_string_block(self):
        for existing in (False, True):
            with self.subTest(existing=existing):
                before = fsmp.Nif(fixture(existing))
                payload, report = fsmp.bind_nif(fixture(existing), "SKSE/Plugins/hdtSkinnedMeshConfigs/CLAW/test.xml")
                after = fsmp.Nif(payload)
                self.assertEqual(after.blocks[1:len(before.blocks)], before.blocks[1:])
                self.assertEqual(len(after.blocks), len(before.blocks) + 1)
                self.assertEqual(struct.unpack_from("<I", after.blocks[0], 4)[0], int(existing) + 1)
                if existing:
                    self.assertEqual(struct.unpack_from("<I", after.blocks[0], 8)[0], 2)
                self.assertTrue(report["originalShapeSkinMaterialBlocksExact"])
                self.assertEqual(after.strings[:len(before.strings)], before.strings)

    def test_existing_fsmp_hook_is_never_silently_replaced_or_duplicated(self):
        first, _ = fsmp.bind_nif(fixture(), "first.xml")
        with self.assertRaisesRegex(ValueError, "already has an FSMP binding"):
            fsmp.bind_nif(first, "second.xml")

    def test_graph_drives_all_requested_nodes_with_restoring_springs_and_no_contact_shapes(self):
        for breast in (False, True):
            root = ET.fromstring(fsmp.render_xml(breast))
            bones = {element.attrib["name"]: element for element in root.findall("bone")}
            dynamic = {name for name, element in bones.items() if float(element.findtext("mass")) > 0}
            expected = set(fsmp.common.source.NODES + (fsmp.common.source.BREAST_NODES if breast else ()))
            self.assertEqual(dynamic, expected)
            self.assertFalse(root.findall(".//shape"))
            constraints = root.findall("generic-constraint")
            self.assertEqual(len(constraints), len(expected))
            for element in constraints:
                self.assertIn(element.attrib["bodyA"], bones)
                self.assertIn(element.attrib["bodyB"], dynamic)
                self.assertEqual(set(element.find("angularUpperLimit").attrib.values()), {".01"})
                self.assertGreater(float(element.find("angularStiffness").attrib["x"]), 0)

    def test_only_p1_joint_frames_change_from_the_pinned_runtime_xml(self):
        male = fsmp.render_xml(False)
        female = fsmp.render_xml(True)
        self.assertEqual(hashlib.sha256(male).hexdigest(), "b42bfa436a4e53baa48ff2249d4659718603798dabdb1e6b9427dc37efa0ea34")
        self.assertEqual(female.count(b"<frameInA />"), 2)
        self.assertEqual(hashlib.sha256(female.replace(b"<frameInA />", b"<frameInB />")).hexdigest(),
                         "1e68bc9a8cb3551b8c7e855742add251d34dc2ad262f1a3ea6e0f0cf17478717")
        constraints = ET.fromstring(female).findall("generic-constraint")
        for constraint in constraints:
            breast = constraint.attrib["bodyB"] in fsmp.common.source.BREAST_NODES
            self.assertEqual(constraint.find("frameInA") is not None, breast)
            self.assertEqual(constraint.find("frameInB") is not None, not breast)
            if breast:
                side = "L" if " L " in constraint.attrib["bodyB"] else "R"
                self.assertEqual(constraint.attrib["bodyA"], "NPC " + side + " PreBreast P1")

    def test_complete_builder_binds_all_endpoints_and_archives_only_motion_resources(self):
        for breast in (False, True):
            with self.subTest(breast=breast), tempfile.TemporaryDirectory() as directory:
                resources, baseline, api, reads, source_fixture = self.builder_fixture(directory)
                out = Path(directory) / "candidate"
                with source_fixture:
                    report = fsmp.build_adapter(out, baseline, resources, None, breast=breast, api=api)
                self.assertEqual(["hdtSMP64.dll"], [path.name for path in baseline.iterdir()])
                expected = {"README.txt", *(fsmp.XML_ROOT + "CLAWMotion" + sex + ".xml"
                                             for sex in ("Male", "Female")),
                            *(fsmp.MESH + sex + "bodywerewolf_" + endpoint + ".nif"
                              for sex in ("male", "female") for endpoint in ("0", "1"))}
                with zipfile.ZipFile(report["archive"]["path"]) as archive:
                    self.assertEqual(set(archive.namelist()), expected)
                    self.assertIsNone(archive.testzip())
                    for row in report["files"]:
                        payload = archive.read(row["path"])
                        self.assertEqual(payload, (out / "package" / row["path"]).read_bytes())
                        self.assertEqual(len(payload), row["bytes"])
                        self.assertEqual(hashlib.sha256(payload).hexdigest(), row["sha256"])
                    for role in fsmp.common.BODY_ROLES:
                        sex = "female" if role.startswith("female") else "male"
                        member = fsmp.MESH + sex + "bodywerewolf_" + role[-1] + ".nif"
                        payload = archive.read(member)
                        before, after = fsmp.Nif(resources[role].read_bytes()), fsmp.Nif(payload)
                        self.assertEqual(after.blocks[1:len(before.blocks)], before.blocks[1:])
                        self.assertEqual(after.strings[:len(before.strings)], before.strings)
                        self.assertEqual(after.footer, before.footer)
                        self.assertEqual(written_hook(payload, "BODYTRI"), written_hook(resources[role].read_bytes(), "BODYTRI"))
                        xml = written_hook(payload, fsmp.HOOK)
                        self.assertEqual(xml, fsmp.XML_ROOT + "CLAWMotion" + sex.title() + ".xml")
                        dynamic = {bone.attrib["name"] for bone in ET.fromstring(archive.read(xml)).findall("bone")
                                   if float(bone.findtext("mass")) > 0}
                        nodes = set(fsmp.common.source.NODES)
                        if breast and sex == "female":
                            nodes.update(fsmp.common.source.BREAST_NODES)
                        self.assertEqual(dynamic, nodes)
                        self.assertEqual(set(report["storedWeightCoverage"][role]), nodes)
                        self.assertEqual(reads.count(out / "package" / member), 1)
                self.assertEqual(json.loads((out / "fsmp-motion-build.json").read_text()), report)
                self.assertEqual(report["providerBinary"]["sha256"], fsmp.common.pin(baseline / "hdtSMP64.dll")["sha256"])
                for key in ("runtimeQualified", "gameValidated", "releaseReady", "collisionResponseEnabled"):
                    self.assertFalse(report[key])
                self.assertFalse((out / "FAILED-unverified-do-not-install").exists())

    def test_fsmp_only_build_still_rejects_present_provider_conflicts_and_invalid_xml(self):
        cases = (
            ("CBPCMasterConfig_Other.txt", "[ConfigMap]\nTailBone01=Other\n"),
            ("CBPConfig_Other.txt", "CLAW_EarL.stiffness 0.9\n"),
            ("other.xml", '<system><bone name="TailBone01"/></system>'),
            ("other.xml", '<system><bone name="NPC Spine2 [Spn2]"/></system>'),
            ("other.xml", "<system>"),
        )
        for name, text in cases:
            with self.subTest(name=name, text=text), tempfile.TemporaryDirectory() as directory:
                resources, baseline, api, _, source_fixture = self.builder_fixture(directory)
                (baseline / name).write_text(text)
                out = Path(directory) / "candidate"
                with source_fixture, self.assertRaisesRegex(ValueError, "Provider snapshot unresolved"):
                    fsmp.build_adapter(out, baseline, resources, None, breast=True, api=api)
                self.assertFalse(out.exists())

    def test_written_hook_readback_failure_cannot_report_a_successful_build(self):
        with tempfile.TemporaryDirectory() as directory:
            resources, baseline, api, _, source_fixture = self.builder_fixture(directory)
            original_read = api.NifFile

            def missing_written_hook(path):
                nif = original_read(path)
                if "package" in Path(path).parts:
                    nif.root.get_extra_data = lambda **unused: None
                return nif

            out = Path(directory) / "candidate"
            with source_fixture, self.assertRaisesRegex(ValueError, "Written FSMP root hook failed native readback"):
                fsmp.build_adapter(out, baseline, resources, None, api=SimpleNamespace(NifFile=missing_written_hook))
            self.assertTrue((out / "FAILED-unverified-do-not-install").exists())
            self.assertFalse((out / "fsmp-motion-build.json").exists())
            self.assertFalse((out / "CLAW Physics - FSMP Motion.zip").exists())

    def test_post_archive_input_changes_retain_failure_marker_without_success_report(self):
        for changed in ("body", "provider-inventory"):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as directory:
                resources, baseline, api, _, source_fixture = self.builder_fixture(directory)
                original_archive = fsmp.common.archive

                def archive_then_change(path, files):
                    original_archive(path, files)
                    if changed == "body":
                        resources["female1"].write_bytes(b"changed after packaging")
                    else:
                        (baseline / "added.xml").write_text("<system/>")

                out = Path(directory) / "candidate"
                expected_error = "Input changed" if changed == "body" else "Provider snapshot"
                with source_fixture, patch.object(fsmp.common, "archive", archive_then_change), self.assertRaisesRegex(ValueError, expected_error):
                    fsmp.build_adapter(out, baseline, resources, None, breast=True, api=api)
                self.assertTrue((out / "FAILED-unverified-do-not-install").exists())
                self.assertFalse((out / "fsmp-motion-build.json").exists())


if __name__ == "__main__":
    unittest.main()
