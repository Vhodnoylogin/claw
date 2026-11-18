"""Compile/read back NONSHIPPING source only; never acquire, install or launch."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
PLUGIN = "test_CLAW - Beast and Mixed Families.esp"

spec = importlib.util.spec_from_file_location(
    "claw_beast_fixture_helpers",
    HERE.parents[1] / "physics/human-origin-lifecycle/build_fixture.py")
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
binary, inputs, single, pin = helpers.binary, helpers.inputs, helpers.single, helpers.pin


def form(local):
    return 0x01000000 | int(local, 16)


def text_field(fields, key):
    value = single(fields, key)
    if not value.endswith(b"\0") or b"\0" in value[:-1]:
        raise ValueError("Invalid fixture string: " + key)
    return value[:-1].decode("utf-8")


def u32(fields, key):
    return struct.unpack("<I", single(fields, key, 4))[0]


def verify_plugin(data, fixture):
    """Independent structural gate; no mesh, FaceGen, winner or engine proof."""
    rows = list(binary.records(data))
    required = Counter({b"TES4": 1, b"CELL": 1, b"NPC_": 6,
                        b"ACHR": 6, b"ARMA": 3, b"ARMO": 1})
    if Counter(r[0] for r in rows) != required or len({r[1] for r in rows}) != len(rows):
        raise ValueError("Fixture record scope/identity differs")
    header, = [r for r in rows if r[0] == b"TES4"]
    h = inputs.subrecords(header[3])
    if header[1] or header[2] or h["MAST"] != [b"Skyrim.esm\0"]:
        raise ValueError("Regular unlocalized ESP with Skyrim.esm only required")
    cell, = [r for r in rows if r[0] == b"CELL"]
    c = inputs.subrecords(cell[3])
    if (cell[1] != 0x32AE7 or cell[2] or text_field(c, "EDID") != "QASmoke" or
            single(c, "DATA", 2) != b"\x03\0" or
            single(c, "LTMP", 4) != bytes(4) or
            set(c) != {"EDID", "FULL", "DATA", "XCLL", "LTMP", "XCLW", "XCIM"}):
        raise ValueError("Bounded QASmoke CELL scope differs")

    expected = {form(a["npcLocalId"]): a for a in fixture["actors"]}
    npcs = {r[1]: r for r in rows if r[0] == b"NPC_"}
    if set(npcs) != set(expected):
        raise ValueError("Authored NPC identities differ")
    for ident, actor in expected.items():
        _, _, flags, raw, *_ = npcs[ident]
        f = inputs.subrecords(raw)
        config = single(f, "ACBS", 24)
        face = struct.unpack("<19f", single(f, "NAM9", 76))
        wanted_face = [0.0] * 19
        for index, value in zip((0, 3, 4, 14, 16), actor["faceSlots"]):
            wanted_face[index] = value
        skin = form("000820") if actor["npcLocalId"] == "000805" else None
        if (flags or text_field(f, "EDID") != actor["editorId"] or
                struct.unpack_from("<I", config)[0] != (0x11 if actor["sex"] == "female" else 0x10) or
                u32(f, "RNAM") != int(actor["raceLocalId"], 16) or
                single(f, "NAM6", 4) != struct.pack("<f", 1.0) or
                single(f, "NAM7", 4) != struct.pack("<f", actor["weight"]) or
                single(f, "NAM9") != struct.pack("<19f", *wanted_face) or
                (u32(f, "WNAM") if "WNAM" in f else None) != skin or
                any(k in f for k in ("TPLT", "VMAD", "SPLO", "DOFT", "OTFT", "PKID", "SNAM", "PRKR", "PNAM", "FTST", "NAMA")) or
                not all(abs(v) <= 1 for v in face)):
            raise ValueError("Authored human NPC sex/race/skin/weight/face/scope differs")

    refs = {r[1]: r for r in rows if r[0] == b"ACHR"}
    if set(refs) != {form(a["referenceLocalId"]) for a in expected.values()}:
        raise ValueError("Reference identities differ")
    for actor in expected.values():
        _, _, flags, raw, _, parents = refs[form(actor["referenceLocalId"])]
        f = inputs.subrecords(raw)
        ancestry = [(struct.unpack_from("<i", p, 12)[0], struct.unpack_from("<I", p, 8)[0]) for p in parents]
        if (flags != 0xC00 or ancestry[-2:] != [(6, 0x32AE7), (8, 0x32AE7)] or
                text_field(f, "EDID") != actor["editorId"] + "Ref" or
                u32(f, "NAME") != form(actor["npcLocalId"]) or
                single(f, "DATA", 24) != struct.pack("<6f", *actor["storagePosition"], 0, 0, 0) or
                set(f) != {"EDID", "NAME", "DATA"}):
            raise ValueError("Persistent disabled reference/base/placement/scope differs")

    skin = fixture["customSkin"]
    addons = {r[1]: r for r in rows if r[0] == b"ARMA"}
    if set(addons) != {form(a["localId"]) for a in skin["addons"]}:
        raise ValueError("Custom skin addon identities differ")
    for addon in skin["addons"]:
        _, _, flags, raw, *_ = addons[form(addon["localId"])]
        f = inputs.subrecords(raw)
        if (flags or text_field(f, "EDID") != addon["editorId"] or
                u32(f, "RNAM") != int(skin["raceLocalId"], 16) or
                single(f, "BOD2", 8) != struct.pack("<II", addon["slotMask"], 2) or
                single(f, "DNAM", 12) != bytes.fromhex("000000020000001700000000") or
                text_field(f, "MOD3").replace("\\", "/").lower() != addon["model"].lower() or
                set(f) != {"EDID", "BOD2", "RNAM", "DNAM", "MOD3"}):
            raise ValueError("Female-only custom skin addon/path/slot/scope differs")
    armor, = [r for r in rows if r[0] == b"ARMO"]
    f = inputs.subrecords(armor[3])
    if (skin["externalWolfAddon"] != "0CDD87:Skyrim.esm" or
            armor[1] != form(skin["localId"]) or armor[2] or
            text_field(f, "EDID") != "CLAWTestBHUNPSkin" or
            u32(f, "RNAM") != int(skin["raceLocalId"], 16) or
            single(f, "BOD2", 8) != struct.pack("<II", skin["bodySlotMask"], 2) or
            f["MODL"] != [*[struct.pack("<I", form(a["localId"])) for a in skin["addons"]],
                          struct.pack("<I", 0x0CDD87)] or
            set(f) != {"EDID", "OBND", "BOD2", "RNAM", "MODL", "DATA", "DNAM"}):
        raise ValueError("Custom body/hands/feet/wolf skin armor differs")
    return {"masters": ["Skyrim.esm"], "authoredHumanNpcs": 6,
            "persistentDisabledReferences": 6, "customFemaleSkinAddons": 3,
            "externalWolfAddon": skin["externalWolfAddon"],
            "cellPayloadSha256": hashlib.sha256(cell[3]).hexdigest(),
            "externalAssetsVerified": False, "gameValidated": False}


def build(spriggit, assembly, cache, out):
    out = inputs.safe_output(out)
    if (pin(spriggit)["sha256"] != "6d4f73d92a71e908ace57f7f9ebd2d852d474fa38a822f1a639fc626027bf662" or
            pin(assembly)["sha256"] != "dc1e32c8db6a44eaabd0666f927feb89618f48be85d0cc4ad5630ebe94a62484"):
        raise ValueError("Expected existing Spriggit 0.41.0 tool/assembly")
    expected_cache = Path(tempfile.gettempdir()) / "Spriggit/Translations/Spriggit.Yaml.Skyrim/0.41.0"
    if cache.resolve() != expected_cache.resolve() or not (cache / "Spriggit.Yaml.Skyrim.exe").is_file():
        raise ValueError("Existing translation cache required; no acquisition")
    fixture = json.loads((HERE / "fixture.json").read_text(encoding="utf-8"))
    sources = [p for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    dependencies = [spriggit, assembly, Path(helpers.__file__), Path(binary.__file__), Path(inputs.__file__),
                    *[p for p in cache.rglob("*") if p.is_file()]]
    pins = [pin(p) for p in sorted(set(sources + dependencies))]
    out.mkdir(parents=True)
    pending = out / "FAILED-unverified-do-not-stage"
    pending.write_text("Source compilation/readback incomplete.\n", encoding="utf-8")
    commands = []

    def run(name, args):
        command = [str(spriggit), *args]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
        (out / (name + ".stdout.log")).write_bytes(result.stdout)
        (out / (name + ".stderr.log")).write_bytes(result.stderr)
        commands.append({"argv": command, "exitCode": result.returncode})
        if result.returncode:
            raise ValueError("Spriggit failed: " + name)

    esp = out / PLUGIN
    run("build", ["deserialize", "-i", str(HERE / "plugin-source"), "-o", str(esp), "-t", "1"])
    proof = verify_plugin(esp.read_bytes(), fixture)
    run("readback", ["serialize", "-i", str(esp), "-o", str(out / "readback"), "-g", "SkyrimSE", "-p", "Spriggit.Yaml", "-v", "0.41.0", "-t", "1"])
    (out / "roundtrip").mkdir()
    again = out / "roundtrip" / PLUGIN
    run("rebuild", ["deserialize", "-i", str(out / "readback"), "-o", str(again), "-t", "1"])
    if esp.read_bytes() != again.read_bytes() or verify_plugin(again.read_bytes(), fixture) != proof:
        raise ValueError("Official roundtrip changed fixture bytes")
    if any(pin(Path(p["path"])) != p for p in pins):
        raise ValueError("Fixture/tool inputs changed during compilation")
    report = {"schema": "claw-beast-mixed-fixture-build/1",
              "status": "OFFLINE_STRUCTURAL_ONLY_EXTERNAL_ASSETS_REQUIRED",
              "plugin": pin(esp), "binaryProof": proof, "sourceAndToolPins": pins,
              "commands": commands, "roundtripBytesIdentical": True,
              "missingPreparation": fixture["customSkin"]["requiredExternalPreparation"],
              "installed": False, "gameValidated": False, "readyToStage": False}
    (out / "build-receipt.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    pending.unlink()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("spriggit", "spriggit-assembly", "translation-cache", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = build(args.spriggit, args.spriggit_assembly, args.translation_cache, args.out)
    print(json.dumps({"status": result["status"], "plugin": result["plugin"], "readyToStage": False}))
