"""Build/read back two disabled persistent refs; never install or launch."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import zlib

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
PLUGIN = "test_CLAW - Physics Probe.esp"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


# Reuse the existing nonshipping record reader and output/path guards.
binary = module("claw_lifecycle_binary", HERE.parents[1] / "inspection/lighting/build_lighting.py")
inputs = module("claw_lifecycle_inputs", REPO / "src/main/python/build-tools/build-test-fixture-package.py")


def pin(path):
    data = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def single(fields, key, size=None):
    values = fields.get(key, [])
    if len(values) != 1 or size is not None and len(values[0]) != size:
        raise ValueError("Missing/ambiguous fixture field: " + key)
    return values[0]


def source_npc(record, expected):
    """Verify original selected record bytes; never copy a face/NPC to output."""
    if len(record) != expected["sourceRecordBytes"] or hashlib.sha256(record).hexdigest() != expected["sourceRecordSha256"]:
        raise ValueError("Original NPC record differs")
    kind, size, flags, form = struct.unpack_from("<4sIII", record)
    if kind != b"NPC_" or form != int(expected["baseLocalFormId"], 16) or size + 24 != len(record):
        raise ValueError("Original NPC identity differs")
    payload = record[24:]
    if flags & 0x40000:
        count = struct.unpack_from("<I", payload)[0]
        payload = zlib.decompress(payload[4:])
        if len(payload) != count:
            raise ValueError("Original NPC compressed size differs")
    fields = inputs.subrecords(payload)
    actual = {
        "editorId": single(fields, "EDID").rstrip(b"\0").decode("ascii"),
        "sex": "female" if struct.unpack_from("<I", single(fields, "ACBS"))[0] & 1 else "male",
        "raceLocalFormId": f'{struct.unpack("<I", single(fields, "RNAM", 4))[0]:06X}',
        "height": struct.unpack("<f", single(fields, "NAM6", 4))[0],
        "weight": struct.unpack("<f", single(fields, "NAM7", 4))[0],
        "weightFloat32Hex": single(fields, "NAM7", 4).hex(),
    }
    if "TPLT" in fields or any(actual[key] != expected[key] for key in actual):
        raise ValueError("Original human NPC sex/race/weight/template differs")
    return actual


def source_records(master, fixture):
    if master.name.casefold() != "skyrim.esm":
        raise ValueError("Explicit original Skyrim.esm required")
    rows = []
    with master.open("rb") as stream:
        for expected in fixture["references"]:
            stream.seek(expected["sourceRecordOffset"])
            record = stream.read(expected["sourceRecordBytes"])
            rows.append({**expected, "verifiedSourceFields": source_npc(record, expected)})
    return rows


def verify_plugin(data, fixture):
    records = list(binary.records(data))
    if sorted(kind for kind, *_ in records) != [b"ACHR", b"ACHR", b"CELL", b"TES4"]:
        raise ValueError("Only header, one CELL and two references are permitted; no NPC/assets/scripts")
    header, = [r for r in records if r[0] == b"TES4"]
    fields = inputs.subrecords(header[3])
    if header[2] & (1 | 0x80 | 0x200) or [v.rstrip(b"\0").decode("ascii") for v in fields["MAST"]] != ["Skyrim.esm"]:
        raise ValueError("Regular unlocalized ESP with Skyrim.esm only is required")
    cell, = [r for r in records if r[0] == b"CELL"]
    if cell[1] != 0x32AE7 or single(inputs.subrecords(cell[3]), "EDID") != b"QASmoke\0":
        raise ValueError("QASmoke CELL identity differs")
    expected_refs = {0x01000000 | int(r["referenceLocalId"], 16): r for r in fixture["references"]}
    refs = [r for r in records if r[0] == b"ACHR"]
    if {r[1] for r in refs} != set(expected_refs):
        raise ValueError("Reference identities differ")
    for _, form, flags, raw, _, parents in refs:
        expected = expected_refs[form]
        fields = inputs.subrecords(raw)
        ancestry = [(struct.unpack_from("<i", p, 12)[0], struct.unpack_from("<I", p, 8)[0]) for p in parents]
        if (flags != 0xC00 or (6, 0x32AE7) not in ancestry or
                struct.unpack("<I", single(fields, "NAME", 4))[0] != int(expected["baseLocalFormId"], 16) or
                single(fields, "DATA", 24) != struct.pack("<6f", *expected["storagePosition"], 0, 0, 0) or
                set(fields) != {"EDID", "NAME", "DATA"}):
            raise ValueError("Persistent disabled reference/base/placement/scope differs")
    return {"masters": ["Skyrim.esm"], "npcRecords": 0, "persistentDisabledReferences": 2,
            "referenceLocalIds": [r["referenceLocalId"] for r in fixture["references"]],
            "cellPayloadSha256": hashlib.sha256(cell[3]).hexdigest()}


def build(master, spriggit, assembly, cache, out):
    out = inputs.safe_output(out)
    fixture = json.loads((HERE / "fixture.json").read_text(encoding="utf-8"))
    # This exact installed tool/cache was already used for the existing probes.
    if (pin(spriggit)["sha256"] != "6d4f73d92a71e908ace57f7f9ebd2d852d474fa38a822f1a639fc626027bf662" or
            pin(assembly)["sha256"] != "dc1e32c8db6a44eaabd0666f927feb89618f48be85d0cc4ad5630ebe94a62484"):
        raise ValueError("Expected installed Spriggit0.41.0 tool/assembly")
    expected_cache = Path(tempfile.gettempdir()) / "Spriggit/Translations/Spriggit.Yaml.Skyrim/0.41.0"
    if cache.resolve() != expected_cache.resolve() or not (cache / "Spriggit.Yaml.Skyrim.exe").is_file():
        raise ValueError("Existing installed translation cache required; no acquisition")
    source_files = [p for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    dependencies = [spriggit, assembly, Path(binary.__file__), Path(inputs.__file__),
                    *[p for p in cache.rglob("*") if p.is_file()]]
    pins = [pin(p) for p in sorted(set(source_files + dependencies))]
    originals = source_records(master, fixture)
    out.mkdir(parents=True)
    pending = out / "FAILED-unverified-do-not-stage"
    pending.write_text("Fixture build/readback incomplete.\n", encoding="utf-8")
    calls = []
    def run(name, args):
        command = [str(spriggit), *args]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
        (out / (name + ".stdout.log")).write_bytes(result.stdout)
        (out / (name + ".stderr.log")).write_bytes(result.stderr)
        calls.append({"argv": command, "exitCode": result.returncode})
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
    if originals != source_records(master, fixture) or any(pin(Path(p["path"])) != p for p in pins):
        raise ValueError("Fixture/tool/original NPC inputs changed during build")
    report = {"schema": "claw-human-origin-fixture-build/1", "status": "OFFLINE_VERIFIED_NOT_STAGED",
              "plugin": pin(esp), "binaryProof": proof, "originalHumanRecords": originals,
              "master": {"path": str(master.resolve()), "bytes": master.stat().st_size,
                         "scope": "Exact selected NPC records verified; not an active-profile winning-override claim"},
              "sourceAndToolPins": pins, "commands": calls, "roundtripBytesIdentical": True,
              "gameValidated": False, "installed": False}
    (out / "build-receipt.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    pending.unlink()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("master", "spriggit", "spriggit-assembly", "translation-cache", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = build(args.master, args.spriggit, args.spriggit_assembly, args.translation_cache, args.out)
    print(json.dumps({"status": result["status"], "plugin": result["plugin"]}))
