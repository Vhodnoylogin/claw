"""Build the CLAW browser addon from its own sources and canonical MorphLinks.xml.

Only the Python standard library is used. All generated output must stay outside
the CLAW checkout. ZIP contents and timestamps are deterministic.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct
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
            if (rule.tag != "Rule" or set(rule.attrib) != {"source", "target", "gain", "cap"}
                    or len(rule)):
                raise ValueError("Unexpected rule element or metadata")
            source, target = rule.attrib["source"], rule.attrib["target"]
            gain, cap = float32(rule.attrib["gain"]), float32(rule.attrib["cap"])
            if (not identifier(source) or source.startswith("CLAW") or target not in BODY_TARGETS
                    or (family == "HIMBO" and target == "CLAWTorsoBreastSize")
                    or not 0 < cap <= 1 or (source, target) in pairs
                    or (target in caps and caps[target] != cap)):
                raise ValueError("Invalid/duplicate morph rule or inconsistent cap")
            pairs.add((source, target))
            caps[target] = cap
            rules.append({"source": source, "target": target, "gain": gain, "cap": cap})
        if not 0 < len(rules) <= 128:
            raise ValueError("Invalid rule count")
        metadata["rules"] = rules
        profiles.append(metadata)
    if families != {"CBBE", "3BA", "HIMBO"}:
        raise ValueError("Expected one current CBBE, 3BA and HIMBO profile")
    return {"schemaVersion": 1,
            "source": {"path": "distribution/profiles/MorphLinks.xml",
                       "sha256": hashlib.sha256(data).hexdigest()},
            "numericContract": "float32 inputs/gains/caps; double sum in XML order; float32(clamp(sum,0,1)*cap)",
            "profiles": profiles}


def build(output_dir: Path) -> dict:
    output_dir = output_dir.resolve()
    if output_dir == REPOSITORY or REPOSITORY in output_dir.parents:
        raise ValueError("Generated output must be outside the CLAW checkout")
    catalog = catalog_from_bytes(SOURCE.read_bytes())
    catalog["generator"] = {"path": "tools/morphbench-addon/build.py",
                            "sha256": hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest()}
    assets = {name: (HERE / "src" / name).read_bytes().replace(b"\r\n", b"\n") for name in ASSETS}
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
              "profiles": {profile["id"]: len(profile["rules"]) for profile in catalog["profiles"]}}
    (output_dir / "build-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.output_dir), indent=2))


if __name__ == "__main__":
    main()
