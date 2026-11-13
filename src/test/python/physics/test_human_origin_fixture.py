"""Actual fixture readback guards, with temporary in-memory ESP counterexamples."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import unittest
import zlib

HERE = Path(__file__).resolve().parents[2] / "resources/physics/human-origin-lifecycle"
SPEC = importlib.util.spec_from_file_location("claw_human_origin_fixture", HERE / "build_fixture.py")
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


class HumanOriginFixtureTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads((HERE / "fixture.json").read_text(encoding="utf-8"))

    def plugin(self, *, master="Skyrim.esm", extra=b"", ref_flags=0xC00,
               base=None, local=None, group_cell=0x32AE7, vmad=False, esl=False):
        b = fixture.binary
        header = b.rec("TES4", 0, b.sub("MAST", master.encode() + b"\0") + b.sub("DATA", bytes(8)), 0x200 if esl else 0)
        cell = b.rec("CELL", 0x32AE7, b.sub("EDID", b"QASmoke\0"))
        refs = []
        for i, row in enumerate(self.contract["references"]):
            data = (b.sub("EDID", ("test" + str(i)).encode() + b"\0") +
                    b.sub("NAME", struct.pack("<I", base if i == 0 and base is not None else int(row["baseLocalFormId"], 16))) +
                    b.sub("DATA", struct.pack("<6f", *row["storagePosition"], 0, 0, 0)))
            if vmad and i == 0:
                data += b.sub("VMAD", b"unwanted")
            form = 0x01000000 | (local if i == 0 and local is not None else int(row["referenceLocalId"], 16))
            refs.append(b.rec("ACHR", form, data, ref_flags))
        persistent = b.grp(struct.pack("<I", group_cell), 6, b"".join(refs))
        cell_group = b.grp(struct.pack("<I", 9), 3, cell + persistent)
        block = b.grp(struct.pack("<I", 1), 2, cell_group)
        return header + b.grp(b"CELL", 0, block) + extra

    def test_minimal_reference_only_fixture_uses_original_humans(self):
        proof = fixture.verify_plugin(self.plugin(), self.contract)
        self.assertEqual(proof["npcRecords"], 0)
        self.assertEqual(proof["persistentDisabledReferences"], 2)
        self.assertEqual(proof["masters"], ["Skyrim.esm"])
        female, male = self.contract["references"]
        self.assertEqual((female["baseLocalFormId"], female["sex"], female["weight"]), ("0A2C91", "female", 50))
        self.assertEqual((male["baseLocalFormId"], male["sex"], male["weightFloat32Hex"]), ("0A2C90", "male", "ffffef41"))

    def test_new_npcs_master_changes_and_esl_are_refused(self):
        for data in (self.plugin(extra=fixture.binary.rec("NPC_", 0x01000800, b"")),
                     self.plugin(master="test_CLAW - Human and Werewolf Comparison.esp"),
                     self.plugin(esl=True)):
            with self.subTest(data=data[:30]), self.assertRaises(ValueError):
                fixture.verify_plugin(data, self.contract)

    def test_ref_identity_enablement_base_and_script_changes_are_refused(self):
        for change in ({"ref_flags": 0x400}, {"ref_flags": 0x800}, {"base": 0x1000800},
                       {"local": 0x999}, {"group_cell": 0x123}, {"vmad": True}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                fixture.verify_plugin(self.plugin(**change), self.contract)

    def npc(self, *, female=True, race=0x13746, weight=50.0, template=False, compressed=False):
        expected = copy.deepcopy(self.contract["references"][0])
        b = fixture.binary
        raw = (b.sub("EDID", b"HousecarlRiften\0") + b.sub("ACBS", struct.pack("<I", int(female))) +
               b.sub("RNAM", struct.pack("<I", race)) + b.sub("NAM6", struct.pack("<f", 1)) +
               b.sub("NAM7", struct.pack("<f", weight)))
        if template:
            raw += b.sub("TPLT", struct.pack("<I", 0x123))
        if compressed:
            raw = struct.pack("<I", len(raw)) + zlib.compress(raw)
        record = b.rec("NPC_", 0xA2C91, raw, 0x40000 if compressed else 0)
        expected.update(sourceRecordBytes=len(record), sourceRecordSha256=hashlib.sha256(record).hexdigest())
        return record, expected

    def test_original_record_fields_and_compression_are_checked(self):
        for compressed in (False, True):
            record, expected = self.npc(compressed=compressed)
            result = fixture.source_npc(record, expected)
            self.assertEqual(result["sex"], "female")
            self.assertEqual(result["raceLocalFormId"], "013746")
            self.assertEqual(result["weight"], 50)

    def test_even_rehashed_wrong_sex_race_weight_or_template_is_refused(self):
        for change in ({"female": False}, {"race": 0xCDD84}, {"weight": 100}, {"template": True}):
            record, expected = self.npc(**change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                fixture.source_npc(record, expected)

    def test_unverified_original_bytes_are_refused(self):
        record, expected = self.npc()
        with self.assertRaisesRegex(ValueError, "record differs"):
            fixture.source_npc(record + b"changed", expected)


if __name__ == "__main__":
    unittest.main()
