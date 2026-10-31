"""Lossless FSMP hook edits and complete original motion constraint graphs."""
from pathlib import Path
import struct
import sys
import unittest
import xml.etree.ElementTree as ET

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


class FsmpMotionTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
