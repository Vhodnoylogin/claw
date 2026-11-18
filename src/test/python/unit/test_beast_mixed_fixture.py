"""Source-case invariants and binary-reader rejection tests; no installed inputs."""
import importlib.util
import json
from pathlib import Path
import struct
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
HERE = ROOT / "src/test/resources/inspection/beast-mixed-families"
SPEC = importlib.util.spec_from_file_location("claw_beast_mixed_fixture", HERE / "build_fixture.py")
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


class BeastMixedFixtureTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads((HERE / "fixture.json").read_text(encoding="utf-8"))

    def reader_input(self, mutate=lambda kind, ident, fields: fields, *, ref_flags=0xC00, extra=b""):
        """Synthetic parser input, never a compiled/game-valid fixture claim."""
        b = fixture.binary

        def record(kind, ident, fields, flags=0):
            fields = mutate(kind, ident, fields)
            return b.rec(kind, ident, b"".join(b.sub(k, v) for k, v in fields), flags)

        header = record("TES4", 0, [("MAST", b"Skyrim.esm\0"), ("DATA", bytes(8))])
        cell = record("CELL", 0x32AE7, [("EDID", b"QASmoke\0"), ("FULL", b"Editor Smoke Test Cell\0"),
                     ("DATA", b"\x03\0"), ("XCLL", bytes(92)), ("LTMP", bytes(4)),
                     ("XCLW", struct.pack("<f", -2147483648.0)), ("XCIM", struct.pack("<I", 0x13B32))])
        npcs, refs, addons = [], [], []
        for a in self.contract["actors"]:
            face = [0.0] * 19
            for i, value in zip((0, 3, 4, 14, 16), a["faceSlots"]):
                face[i] = value
            fields = [("EDID", a["editorId"].encode() + b"\0"),
                      ("ACBS", struct.pack("<I", 0x11 if a["sex"] == "female" else 0x10) + bytes(20)),
                      ("RNAM", struct.pack("<I", int(a["raceLocalId"], 16))),
                      ("NAM6", struct.pack("<f", 1)), ("NAM7", struct.pack("<f", a["weight"])),
                      ("NAM9", struct.pack("<19f", *face))]
            if a["npcLocalId"] == "000805":
                fields.append(("WNAM", struct.pack("<I", fixture.form("000820"))))
            npcs.append(record("NPC_", fixture.form(a["npcLocalId"]), fields))
            refs.append(record("ACHR", fixture.form(a["referenceLocalId"]),
                        [("EDID", (a["editorId"] + "Ref").encode() + b"\0"),
                         ("NAME", struct.pack("<I", fixture.form(a["npcLocalId"]))),
                         ("DATA", struct.pack("<6f", *a["storagePosition"], 0, 0, 0))], ref_flags))
        for a in self.contract["customSkin"]["addons"]:
            addons.append(record("ARMA", fixture.form(a["localId"]),
                          [("EDID", a["editorId"].encode() + b"\0"),
                           ("BOD2", struct.pack("<II", a["slotMask"], 2)),
                           ("RNAM", struct.pack("<I", 0x13746)),
                           ("DNAM", bytes.fromhex("000000020000001700000000")),
                           ("MOD3", a["model"].encode() + b"\0")]))
        armor = record("ARMO", fixture.form("000820"),
                       [("EDID", b"CLAWTestBHUNPSkin\0"), ("OBND", bytes(12)),
                        ("BOD2", struct.pack("<II", 140, 2)), ("RNAM", struct.pack("<I", 0x13746)),
                        *[("MODL", struct.pack("<I", fixture.form(a["localId"]))) for a in self.contract["customSkin"]["addons"]],
                        ("MODL", struct.pack("<I", 0x0CDD87)),
                        ("DATA", bytes(8)), ("DNAM", bytes(4))])
        persistent = b.grp(struct.pack("<I", 0x32AE7), 6,
                           b.grp(struct.pack("<I", 0x32AE7), 8, b"".join(refs)))
        cells = b.grp(b"CELL", 0, b.grp(struct.pack("<I", 1), 2,
                      b.grp(struct.pack("<I", 9), 3, cell + persistent)))
        return (header + b.grp(b"NPC_", 0, b"".join(npcs)) + b.grp(b"ARMA", 0, b"".join(addons)) +
                b.grp(b"ARMO", 0, armor) + cells + extra)

    def replace(self, kind, ident, field, value):
        return lambda k, i, fields: [(key, value if key == field else raw) for key, raw in fields] if (k, i) == (kind, ident) else fields

    def test_six_authored_human_cases_and_sources_are_bounded(self):
        actors = self.contract["actors"]
        self.assertEqual([(a["raceLocalId"], a["sex"]) for a in actors[:4]],
                         [("013745", "male"), ("013745", "female"), ("013740", "male"), ("013740", "female")])
        self.assertEqual([(a["raceLocalId"], a["sex"]) for a in actors[4:]], [("013746", "female")] * 2)
        self.assertEqual(actors[4]["skin"], "race-inherited")
        self.assertTrue(actors[5]["skin"].startswith("000820:"))
        self.assertEqual(len({a["npcLocalId"] for a in actors}), 6)
        self.assertEqual(self.contract["customSkin"]["externalWolfAddon"], "0CDD87:Skyrim.esm")
        self.assertEqual(len(self.contract["customSkin"]["addons"]), 3)
        source = HERE / "plugin-source"
        npc_paths = list((source / "Npcs").glob("*.yaml"))
        self.assertEqual(len(npc_paths), 6)
        for actor in actors:
            path, = [p for p in npc_paths if p.name.startswith(actor["editorId"] + " - ")]
            text = path.read_text(encoding="utf-8")
            self.assertIn("Race: " + actor["raceLocalId"] + ":Skyrim.esm\n", text)
            self.assertNotIn("Template:", text)
            self.assertNotIn("HeadParts:", text)
            self.assertNotIn("VirtualMachineAdapter:", text)
        cell, = source.glob("Cells/1/9/*/RecordData.yaml")
        self.assertEqual(cell.read_text(encoding="utf-8").count("MajorRecordFlagsRaw: 3072"), 6)
        self.assertTrue(all(p.suffix in (".yaml", ".json") for p in source.rglob("*") if p.is_file()))
        armor, = (source / "Armors").glob("*.yaml")
        self.assertIn("- 0CDD87:Skyrim.esm\n", armor.read_text(encoding="utf-8"))

    def test_both_endpoint_bindings_require_real_female_profiles(self):
        bindings = ET.parse(HERE / "BodyFamilyBindings.xml").getroot()
        self.assertEqual(bindings.tag, "BodyFamilyBindings")
        self.assertEqual(len(bindings), 4)
        profiles = {p.get("id"): p for p in ET.parse(ROOT / "src/main/resources/profiles/MorphLinks.xml").getroot()}
        for actor in self.contract["actors"][4:]:
            profile = actor["expectedProfile"]
            self.assertEqual(profiles[profile].get("sex"), "female")
            rows = [b for b in bindings if b.get("profile") == profile]
            self.assertEqual(len(rows), 2)
            self.assertTrue(all(b.get("sex") == "female" for b in rows))
            self.assertEqual({b.get("mesh")[-5:] for b in rows}, {"0.nif", "1.nif"})
        custom = [b.get("mesh") for b in bindings if b.get("profile") == self.contract["actors"][5]["expectedProfile"]]
        self.assertIn(self.contract["customSkin"]["addons"][0]["model"], custom)

    def test_static_proof_never_claims_assets_installation_or_game_acceptance(self):
        proof = fixture.verify_plugin(self.reader_input(), self.contract)
        self.assertEqual(proof["authoredHumanNpcs"], 6)
        self.assertEqual(proof["persistentDisabledReferences"], 6)
        self.assertEqual(proof["customFemaleSkinAddons"], 3)
        self.assertEqual(proof["externalWolfAddon"], "0CDD87:Skyrim.esm")
        self.assertFalse(proof["externalAssetsVerified"])
        self.assertFalse(self.contract["installed"])
        self.assertFalse(self.contract["gameValidated"])
        self.assertFalse(self.contract["customSkin"]["assetsIncluded"])
        self.assertFalse(self.contract["customSkin"]["texturesIncluded"])

    def test_enabled_or_nonpersistent_refs_are_rejected(self):
        for flags in (0, 0x400, 0x800):
            with self.subTest(flags=flags), self.assertRaises(ValueError):
                fixture.verify_plugin(self.reader_input(ref_flags=flags), self.contract)

    def test_wolf_wrong_sex_shared_base_and_template_are_rejected(self):
        changes = [self.replace("NPC_", fixture.form("000800"), "RNAM", struct.pack("<I", 0xCDD84)),
                   self.replace("NPC_", fixture.form("000800"), "ACBS", struct.pack("<I", 0x11) + bytes(20)),
                   self.replace("ACHR", fixture.form("000900"), "NAME", struct.pack("<I", fixture.form("000801"))),
                   lambda k, i, f: f + [("TPLT", struct.pack("<I", 0xA2C91))] if k == "NPC_" else f]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                fixture.verify_plugin(self.reader_input(change), self.contract)

    def test_custom_skin_requires_unique_compatible_attachment_paths_and_slots(self):
        changes = [self.replace("ARMA", fixture.form("000811"), "MOD3", b"actors/character/character assets/femalehands_1.nif\0"),
                   self.replace("ARMA", fixture.form("000812"), "BOD2", struct.pack("<II", 4, 2)),
                   self.replace("ARMA", fixture.form("000810"), "RNAM", struct.pack("<I", 0x13745)),
                   self.replace("NPC_", fixture.form("000805"), "WNAM", struct.pack("<I", 0xD64))]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                fixture.verify_plugin(self.reader_input(change), self.contract)

    def test_custom_skin_cannot_omit_change_or_duplicate_wolf_addon(self):
        wolf = struct.pack("<I", 0x0CDD87)
        for replacement in (None, struct.pack("<I", 0x0CDD86), struct.pack("<I", fixture.form("000810"))):
            def change(kind, ident, fields):
                if kind != "ARMO":
                    return fields
                return [(key, replacement if key == "MODL" and raw == wolf else raw)
                        for key, raw in fields if not (key == "MODL" and raw == wolf and replacement is None)]
            with self.subTest(replacement=replacement), self.assertRaisesRegex(ValueError, "wolf skin armor"):
                fixture.verify_plugin(self.reader_input(change), self.contract)
        with self.assertRaisesRegex(ValueError, "wolf skin armor"):
            fixture.verify_plugin(self.reader_input(
                lambda k, i, f: f + [("MODL", wolf)] if k == "ARMO" else f), self.contract)

    def test_added_scripts_masters_and_races_are_rejected(self):
        for change in (lambda k, i, f: f + [("VMAD", b"script")] if k == "ACHR" else f,
                       lambda k, i, f: f + [("MAST", b"Unaccounted.esp\0")] if k == "TES4" else f):
            with self.assertRaises(ValueError):
                fixture.verify_plugin(self.reader_input(change), self.contract)
        with self.assertRaises(ValueError):
            fixture.verify_plugin(self.reader_input(extra=fixture.binary.rec("RACE", fixture.form("000830"), b"")), self.contract)

    def test_outputs_cannot_target_source_or_live_mods(self):
        for path in (HERE, HERE / "generated-output", ROOT.parent.parent / "mo2 test se/mods/fixture-output"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                fixture.inputs.safe_output(path)


if __name__ == "__main__":
    unittest.main()
