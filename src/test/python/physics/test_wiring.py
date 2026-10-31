"""Finite source wiring and independent binary-reader failure contracts.

The small binary fixture tests corrupt record data; it is not a Papyrus runtime.
The external build also verifies the real Spriggit ESP and text round-trip.
"""
import copy
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = (Path(__file__).resolve().parents[4] / 'src/main/python/physics')
spec = importlib.util.spec_from_file_location("claw_physics_wiring", ROOT / "wiring.py")
wiring = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wiring)


def string(value):
    raw = value.encode()
    return struct.pack("<H", len(raw)) + raw


def field(name, data):
    return name.encode() + struct.pack("<H", len(data)) + data


def record(name, data, form=0, flags=0):
    return struct.pack("<4sIIIIHH", name.encode(), len(data), flags, form, 0, 43, 0) + data


def fixture(*, wrong_owner=False, wrong_array_alias=False, gate_true=False, opt_in=False,
            nonoptional=False, filled_actor=False, alias_scan=False, starts=False, extra_record=False,
            wrong_alias_script=False, wrong_player=False, duplicate_alias=False, missing_null_fill=False):
    quest = 0x02000800
    def obj(alias, owner=quest):
        return struct.pack("<HhI", 0, alias, owner)
    def boolean(name, value=False):
        return string(name) + bytes([5, 1, value])
    def script(name, properties):
        return string(name) + b"\0" + struct.pack("<H", len(properties)) + b"".join(properties)
    slots = b"".join(obj(16 if wrong_array_alias and a == 0 else a, 0x01000800 if wrong_owner and a == 0 else quest) for a in range(16))
    array = string("ActorSlots") + bytes([11, 1]) + struct.pack("<I", 16) + slots
    adapter = struct.pack("<HHH", 5, 2, 1) + script("CLAWPhysicsHost", [array, boolean("IntegrationOptIn", opt_in)])
    adapter += struct.pack("<BH", 2, 0) + string("") + struct.pack("<H", 17)
    aliases = b""
    for a in range(17):
        actor = a < 16
        properties = [boolean(n, gate_true and a == 0 and n == "ProviderQualified") for n in wiring.GATES] if actor else []
        name = "CLAWPhysicsActor" if actor else "CLAWPhysicsLoadRelay"
        if wrong_alias_script and a == 0:
            name = "ForeignAliasScript"
        adapter += obj(a) + struct.pack("<HHH", 5, 2, 1) + script(name, properties)
        aliases += field("ALST", struct.pack("<I", 0 if duplicate_alias and a == 1 else a))
        aliases += field("ALID", (f"CLAWPhysicsActor{a:02d}" if actor else "CLAWPhysicsPlayerLoad").encode() + b"\0")
        aliases += field("FNAM", struct.pack("<I", 8 if nonoptional and a == 0 else 10))
        if not (missing_null_fill and a == 0):
            forced = (0x14 if filled_actor and a == 0 else 0) if actor else (0 if wrong_player else 0x14)
            aliases += field("ALFR", struct.pack("<I", forced))
        if alias_scan and a == 0:
            aliases += field("CTDA", bytes(32))
        aliases += field("ALED", b"")
    qdata = struct.pack("<HBBII", int(starts), 10, 255, 0, 0)
    fields = field("EDID", b"CLAWPhysicsHostQuest\0") + field("VMAD", adapter) + field("DNAM", qdata)
    fields += field("NEXT", b"") + field("ANAM", struct.pack("<I", 17)) + aliases
    header = b"".join(field("MAST", name.encode() + b"\0") + field("DATA", bytes(8)) for name in ("Skyrim.esm", "CLAW.esp"))
    payload = record("TES4", header) + record("QUST", fields, quest)
    return payload + (record("GLOB", b"", 0x02000801) if extra_record else b"")


class HostWiringTests(unittest.TestCase):
    def test_recipe_refuses_changed_ids_auto_start_or_true_default_gates(self):
        valid = wiring.recipe()
        for key, value in (("startGameEnabled", True), ("integrationOptIn", True), ("providerQualified", True),
                           ("exclusiveIndexRange", True), ("staticPoseAccepted", True), ("questFormId", "000801"),
                           ("actorAliasIds", list(range(1, 17))), ("playerAliasId", 15), ("schemaVersion", True)):
            bad = copy.deepcopy(valid)
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                wiring.validate_recipe(bad)

    def test_generated_tree_has_exact_same_quest_array_optional_null_fills_and_relay(self):
        value = wiring.recipe()
        rows = wiring.records(value)
        quest = next(v for k, v in rows.items() if k.startswith("Quests/"))
        self.assertNotIn("Flags", quest)  # no StartGameEnabled
        self.assertEqual([a["ID"] for a in quest["Aliases"]], list(range(17)))
        for alias in quest["Aliases"][:16]:
            self.assertEqual(alias["Flags"], ["Optional", "AllowReuseInQuest"])
            self.assertEqual(alias["ForcedReference"], "Null")
        self.assertEqual(quest["Aliases"][16]["ForcedReference"], "000014:Skyrim.esm")
        self.assertEqual(quest["VirtualMachineAdapter"]["Scripts"][0]["Properties"][0]["Objects"],
                         [{"Object": wiring.QUEST, "Alias": i} for i in range(16)])
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "source"
            wiring.write_sources(out, value)
            wiring.validate_source_tree(out, value)
            path = next((out / "Quests").iterdir())
            data = json.loads(path.read_text())
            data["VirtualMachineAdapter"]["Scripts"][0]["Properties"][0]["Objects"][0]["Alias"] = 16
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError): wiring.validate_source_tree(out, value)

    def test_binary_reader_accepts_only_complete_finite_wiring(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / wiring.PLUGIN
            path.write_bytes(fixture())
            result = wiring.validate_plugin(path, wiring.recipe())
            self.assertEqual(len(result["aliases"]), 17)
            self.assertEqual(result["questForm"], 0x02000800)
            for failure in ("wrong_owner", "wrong_array_alias", "gate_true", "opt_in", "nonoptional", "filled_actor", "alias_scan",
                            "starts", "extra_record", "wrong_alias_script", "wrong_player", "duplicate_alias", "missing_null_fill"):
                path.write_bytes(fixture(**{failure: True}))
                with self.subTest(failure=failure), self.assertRaises(ValueError):
                    wiring.validate_plugin(path, wiring.recipe())

    def test_truncated_plugin_and_wrong_object_format_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / wiring.PLUGIN
            for size in (1, 9, 23, 50, len(fixture()) - 1):
                path.write_bytes(fixture()[:size])
                with self.subTest(size=size), self.assertRaises(ValueError): wiring.inspect_plugin(path)
        with self.assertRaises(ValueError): wiring.Reader(bytes(8)).object(1)

    def test_host_only_package_refuses_independently_loaded_motion_config(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            names = ("CLAWPhysicsData.psc", "CLAWPhysicsActor.psc", "CLAWPhysicsHost.psc", "CLAWPhysicsLoadRelay.psc", "CLAWPhysicsControl.psc")
            paths = [wiring.PLUGIN, "README.md"]
            paths += ["Scripts/Source/" + n for n in names]
            paths += ["Scripts/" + Path(n).with_suffix(".pex").name for n in names]
            for relative in paths:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"fixture")
            wiring.validate_host_package(root, names)
            extra = root / "SKSE/Plugins/CBPCMasterConfig_CLAWPhysics.txt"
            extra.parent.mkdir(parents=True)
            extra.write_text("[ConfigMap]\n")
            with self.assertRaises(ValueError): wiring.validate_host_package(root, names)


if __name__ == "__main__":
    unittest.main()
