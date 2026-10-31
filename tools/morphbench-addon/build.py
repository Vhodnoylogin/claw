"""Build the CLAW browser addon from its own sources and canonical MorphLinks.xml.

Only the Python standard library is used. All generated output must stay outside
the CLAW checkout. ZIP contents and timestamps are deterministic.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[1]
SOURCE = REPOSITORY / "distribution/profiles/MorphLinks.xml"
BODY_TARGETS = frozenset((
    "CLAWArmGirth", "CLAWLegCalfGirth", "CLAWLegThighGirth",
    "CLAWTorsoBackWide", "CLAWTorsoBellyRound", "CLAWTorsoBreastSize",
    "CLAWTorsoChestSize", "CLAWTorsoFlankWidth", "CLAWTorsoGirth",
    "CLAWTorsoNeckGirth", "CLAWTorsoShoulderGirth", "CLAWTorsoWaistNarrow",
    "CLAWArmLean", "CLAWLegThighLean", "CLAWLegCalfLean", "CLAWTorsoLean",
))
ASSETS = ("addon.json", "index.html", "core.js", "pair.js", "input.js", "preview-controller.js", "main.js", "style.css")


def identifier(value: str) -> bool:
    return (0 < len(value.encode("utf-8")) <= 160
            and ord(value[0]) > 32 and ord(value[-1]) > 32
            and not any(ord(char) < 32 or ord(char) == 127 for char in value)
            and value not in {"__proto__", "prototype", "constructor"})


def float32(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Mapping numbers must be finite")
    result = struct.unpack("<f", struct.pack("<f", number))[0]
    if not math.isfinite(result):
        raise ValueError("Mapping numbers must fit float32")
    return result


def catalog_from_bytes(data: bytes) -> dict:
    if len(data) > 1024 * 1024 or b"<!" in data:
        raise ValueError("Oversize XML or unsupported declarations/entities")
    root = ET.fromstring(data.decode("utf-8-sig"))
    for element in root.iter():
        if (element.text and element.text.strip()) or (element.tail and element.tail.strip()):
            raise ValueError("Substantive XML text is unsupported")
    if root.tag != "MorphLinkProfiles" or root.attrib != {"schemaVersion": "1"}:
        raise ValueError("Unsupported morph catalog schema")
    profiles, ids, families = [], set(), set()
    for child in root:
        if child.tag != "Profile" or set(child.attrib) != {"id", "family", "version", "sex", "calibration"}:
            raise ValueError("Unexpected profile element or metadata")
        metadata = dict(child.attrib)
        profile_id, family = metadata["id"], metadata["family"]
        if (not all(identifier(value) for value in metadata.values()) or profile_id in ids
                or family in families or family not in {"CBBE", "3BA", "HIMBO"}
                or metadata["sex"] != ("male" if family == "HIMBO" else "female")):
            raise ValueError("Invalid, duplicate or wrong-sex resource family")
        ids.add(profile_id)
        families.add(family)
        rules, pairs, caps = [], set(), {}
        for rule in child:
            function = rule.attrib.get("function", "linear")
            expected = {"source", "target", "gain", "cap"}
            if "function" in rule.attrib:
                expected.add("function")
            if function == "power":
                expected.add("exponent")
            if function == "constant":
                expected.add("value")
            if (rule.tag != "Rule" or set(rule.attrib) != expected
                    or len(rule)):
                raise ValueError("Unexpected rule element or metadata")
            source, target = rule.attrib["source"], rule.attrib["target"]
            gain, cap = float32(rule.attrib["gain"]), float32(rule.attrib["cap"])
            if ((source != "" if function == "constant" else (not identifier(source) or source.startswith("CLAW")))
                    or function not in {"linear", "positive", "negative", "smoothstep", "power", "constant"}
                    or target not in BODY_TARGETS
                    or (family == "HIMBO" and target == "CLAWTorsoBreastSize")
                    or not 0 < cap <= 1 or (source, target) in pairs
                    or (target in caps and caps[target] != cap)):
                raise ValueError("Invalid/duplicate morph rule or inconsistent cap")
            pairs.add((source, target))
            caps[target] = cap
            edge = {"source": source, "target": target, "gain": gain, "cap": cap}
            if "function" in rule.attrib:
                edge["function"] = function
            if function == "power":
                if not re.fullmatch(r"[0-9]+", rule.attrib["exponent"]):
                    raise ValueError("Invalid power exponent")
                edge["exponent"] = int(rule.attrib["exponent"])
                if not 1 <= edge["exponent"] <= 8:
                    raise ValueError("Power exponent must be in 1..8")
            if function == "constant":
                edge["value"] = float32(rule.attrib["value"])
            rules.append(edge)
        if not 0 < len(rules) <= 128:
            raise ValueError("Invalid rule count")
        metadata["rules"] = rules
        profiles.append(metadata)
    if families != {"CBBE", "3BA", "HIMBO"}:
        raise ValueError("Expected one current CBBE, 3BA and HIMBO profile")
    return {"schemaVersion": 1,
            "source": {"path": "distribution/profiles/MorphLinks.xml",
                       "sha256": hashlib.sha256(data).hexdigest()},
            "numericContract": "float32 inputs/gains/caps/constants; binary64 function evaluation and sum(gain*F(input)) in XML order; float32(clamp(sum,0,1)*cap); docs/matrix-contract.md",
            "profiles": profiles}


def compile_kernel(output_dir: Path, compiler: str | None = None) -> tuple[bytes, dict]:
    compiler = compiler or os.environ.get("CLAW_WASM_COMPILER") or shutil.which("clang")
    if not compiler:
        raise ValueError("Provide --wasm-compiler or CLAW_WASM_COMPILER pointing to clang with wasm-ld support")
    shared = REPOSITORY / "distribution/shared"
    sources = {name: (shared / name).read_bytes() for name in ("MatrixKernel.h", "MatrixKernel.cpp")}
    digest = hashlib.sha256(b"".join(name.encode()+b"\0"+data for name, data in sources.items())).hexdigest()
    wasm = output_dir / "matrix-kernel.wasm"
    command = [str(compiler), "--target=wasm32", "-x", "c++", "-std=c++17", "-O2", "-nostdlib",
               "-fno-exceptions", "-fno-rtti", "-fno-builtin", "-ffp-contract=off", "-fno-fast-math",
               "-Wl,--no-entry", "-Wl,--export-memory", "-Wl,--export=__heap_base",
               *["-Wl,--export="+name for name in ("claw_matrix_transform", "claw_matrix_contribution", "claw_matrix_clamp", "claw_matrix_evaluate")],
               str(shared / "MatrixKernel.cpp"), "-o", str(wasm)]
    subprocess.run(command, check=True, capture_output=True, text=True)
    for name, data in sources.items():
        if (shared / name).read_bytes() != data:
            raise ValueError("Shared kernel changed during compilation")
    data = wasm.read_bytes()
    if not data.startswith(b"\x00asm\x01\x00\x00\x00"):
        raise ValueError("Invalid WASM kernel")
    wasm_sha = hashlib.sha256(data).hexdigest()
    template = (HERE / "src/matrix-kernel.template.js").read_text(encoding="utf-8")
    bridge = template.replace("__CLAW_WASM_BASE64__", base64.b64encode(data).decode()).replace("__CLAW_SOURCE_SHA256__", digest).replace("__CLAW_WASM_SHA256__", wasm_sha).encode()
    (output_dir / "matrix-kernel.js").write_bytes(bridge)
    return bridge, {"abi": 1, "sourceSha256": digest, "wasmSha256": wasm_sha,
                    "sourceFiles": {name: hashlib.sha256(value).hexdigest() for name,value in sources.items()},
                    "compilerVersion": subprocess.check_output([str(compiler), "--version"],text=True).splitlines()[0],
                    "command": command, "bytes": len(data)}


def build(output_dir: Path, compiler: str | None = None) -> dict:
    output_dir = output_dir.resolve()
    if output_dir == REPOSITORY or REPOSITORY in output_dir.parents:
        raise ValueError("Generated output must be outside the CLAW checkout")
    output_dir.mkdir(parents=True, exist_ok=True)
    bridge, kernel = compile_kernel(output_dir, compiler)
    catalog = catalog_from_bytes(SOURCE.read_bytes())
    catalog["generator"] = {"path": "tools/morphbench-addon/build.py",
                            "sha256": hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest()}
    assets = {name: (HERE / "src" / name).read_bytes().replace(b"\r\n", b"\n") for name in ASSETS}
    assets["matrix-kernel.js"] = bridge
    catalog["sharedKernel"] = {key:value for key,value in kernel.items() if key not in ("command", "compilerVersion")}
    catalog["evaluator"] = {"path": "tools/morphbench-addon/src/core.js",
                            "sha256": hashlib.sha256(assets["core.js"]).hexdigest()}
    manifest = json.loads(assets["addon.json"])
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", manifest["id"]):
        raise ValueError("Invalid addon ID")
    encoded = json.dumps(catalog, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assets["catalog.js"] = b'"use strict";\nwindow.CLAWMorphCatalog = ' + encoded + b";\n"
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / (manifest["id"] + ".zip")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as package:
        for name, content in sorted(assets.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            package.writestr(info, content)
    # This loose snapshot is for offline inspection/tests, never an installed addon.
    (output_dir / "catalog.json").write_bytes(encoded + b"\n")
    report = {"archive": str(archive), "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
              "bytes": archive.stat().st_size, "files": sorted(assets),
              "mappingSha256": catalog["source"]["sha256"],
              "generatorSha256": catalog["generator"]["sha256"],
              "evaluatorSha256": catalog["evaluator"]["sha256"],
              "profiles": {profile["id"]: len(profile["rules"]) for profile in catalog["profiles"]},
              "sharedKernel": kernel}
    (output_dir / "build-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--wasm-compiler", help="External clang executable with wasm32/wasm-ld support")
    args = parser.parse_args()
    print(json.dumps(build(args.output_dir, args.wasm_compiler), indent=2))


if __name__ == "__main__":
    main()
