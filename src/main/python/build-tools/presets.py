"""Author and validate independent CLAW BodySlide XML preset packages.

CLAW presets live under SliderPresets/CLAW, which the companion reads separately
from OBody's human pool. Values in XML are percentages; authoring JSON uses 0..1.
This tool does not apply morphs, edit OBody settings or install files in the game.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
SETS = {"CLAW Male": "male", "CLAW Female": "female"}
MAX_BYTES = 1024 * 1024
MAX_PRESETS = 4096


def inventory():
    spec = json.loads((ROOT / 'src/main/resources/recipes/build.json').read_text(encoding="utf-8-sig"))
    adult = set(spec["adultMorphs"])
    common = {item["morph"] for item in json.loads(
        (ROOT / 'src/main/resources/recipes/full-body.json').read_text(encoding="utf-8-sig")) if "morph" in item}
    female = {item["morph"] for item in json.loads(
        (ROOT / 'src/main/resources/recipes/female.json').read_text(encoding="utf-8-sig")) if "morph" in item}
    return {"male": common - adult, "female": (common | female) - adult}


def number(value, upper=100.0):
    if isinstance(value, bool):
        raise ValueError("Boolean is not a morph coefficient")
    result = float(value)
    if not math.isfinite(result) or not 0 <= result <= upper:
        raise ValueError(f"Coefficient must be finite and in 0..{upper:g}")
    return result


def validate_name(name):
    if not isinstance(name, str) or not name.strip(" \t\r\n\f\v") or name != name.strip(" \t\r\n\f\v"):
        raise ValueError("Preset name must be nonempty without surrounding whitespace")
    if len(name.encode("utf-8")) > 160 or any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise ValueError("Preset name is too long or contains control characters")
    return name


def attributes(element, permitted):
    if set(element.attrib) - set(permitted):
        raise ValueError("Unsupported XML attributes on " + element.tag)
    if element.text and element.text.strip():
        raise ValueError("Unexpected text in " + element.tag)
    for child in element:
        if child.tail and child.tail.strip():
            raise ValueError("Unexpected text after " + child.tag)


def percentage(text):
    if not isinstance(text, str) or not re.fullmatch(r"-?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", text):
        raise ValueError("Use an unpadded decimal percentage")
    return number(text)


def read_xml(path, allowed=None):
    return parse_xml(Path(path).read_bytes(), allowed)


def parse_xml(payload, allowed=None):
    """Validate the exact bytes to be installed or packaged."""
    allowed = inventory() if allowed is None else allowed
    if len(payload) > MAX_BYTES or b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
        raise ValueError("Oversized XML or DTD/entities are not supported")
    root = ET.fromstring(payload.decode("utf-8-sig"))
    if root.tag != "SliderPresets":
        raise ValueError("Expected SliderPresets root")
    attributes(root, {"version"})
    presets, seen = [], set()
    for element in root:
        if element.tag != "Preset":
            raise ValueError("Unsupported XML element in SliderPresets")
        attributes(element, {"name", "set"})
        name = validate_name(element.get("name"))
        sex = SETS.get(element.get("set"))
        if not sex:
            raise ValueError("Expected exact CLAW Male or CLAW Female set")
        if name in seen:
            raise ValueError("Duplicate preset name: " + name)
        seen.add(name)
        morphs, endpoints = {}, set()
        for slider in element:
            if slider.tag == "Group":
                attributes(slider, {"name"})
                if slider.get("name") is None or len(slider):
                    raise ValueError("Invalid Group element")
                continue
            if slider.tag != "SetSlider":
                raise ValueError("Unsupported element in Preset")
            attributes(slider, {"name", "size", "value"})
            if len(slider):
                raise ValueError("SetSlider cannot have children")
            morph, size = slider.get("name"), slider.get("size")
            if morph not in allowed[sex] or size not in ("small", "big"):
                raise ValueError(f"Unsupported {sex} morph/endpoint: {morph}/{size}")
            if (morph, size) in endpoints:
                raise ValueError("Duplicate slider endpoint: " + morph + "/" + size)
            endpoints.add((morph, size))
            morphs.setdefault(morph, {"small": 0.0, "big": 0.0})[size] = percentage(slider.get("value")) / 100.0
        presets.append({"name": name, "sex": sex, "morphs": morphs})
        if len(presets) > MAX_PRESETS:
            raise ValueError("Too many presets")
    if not presets:
        raise ValueError("No CLAW presets found")
    return presets


def load_tree(path):
    path = Path(path)
    entries = [path] if path.is_file() else sorted(path.rglob("*"))
    if any(p.is_symlink() for p in entries):
        raise ValueError("Symlink entries are unsupported")
    files = [p for p in entries if p.is_file() and p.suffix.lower() == ".xml"]
    if len(files) > MAX_PRESETS:
        raise ValueError("Too many preset files")
    presets, names, inputs = [], set(), []
    for file in files:
        loaded = read_xml(file)
        for preset in loaded:
            if preset["name"] in names:
                raise ValueError("Duplicate preset name across files: " + preset["name"])
            names.add(preset["name"])
            presets.append(preset)
            if len(presets) > MAX_PRESETS:
                raise ValueError("Too many presets")
        inputs.append({"path": str(file), "sha256": hashlib.sha256(file.read_bytes()).hexdigest()})
    if not files:
        raise ValueError("No XML preset files at " + str(path))
    return {"presets": presets, "inputs": inputs}


def export_recipe(data):
    if data.get("schemaVersion") != 1:
        raise ValueError("Unsupported preset authoring schema")
    allowed = inventory()
    root, names = ET.Element("SliderPresets"), set()
    for preset in data["presets"]:
        name, sex = validate_name(preset["name"]), preset["sex"]
        if sex not in allowed or name in names:
            raise ValueError("Invalid sex or duplicate preset name")
        names.add(name)
        element = ET.SubElement(root, "Preset", {"name": name, "set": "CLAW " + sex.title()})
        ET.SubElement(element, "Group", {"name": "CLAW"})
        ET.SubElement(element, "Group", {"name": "CLAW " + sex.title()})
        for morph, endpoints in sorted(preset["morphs"].items()):
            if morph not in allowed[sex] or not isinstance(endpoints, dict) or set(endpoints) != {"small", "big"}:
                raise ValueError("Use known morphs and explicit small/big endpoints")
            for size in ("small", "big"):
                value = number(endpoints[size], 1.0) * 100
                ET.SubElement(element, "SetSlider", {"name": morph, "size": size, "value": format(value, ".8g")})
    if not names:
        raise ValueError("Authoring recipe has no presets")
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("path", type=Path)
    validate.add_argument("--weight", type=float, default=50)
    export = sub.add_parser("export")
    export.add_argument("recipe", type=Path)
    export.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "export":
            payload = export_recipe(json.loads(args.recipe.read_text(encoding="utf-8-sig")))
            if args.out.suffix.lower() != ".xml" or not args.out.parent.is_dir():
                raise ValueError("Output must be a new XML file in an existing staging directory")
            with args.out.open("xb") as stream:
                stream.write(payload)
            print(json.dumps({"written": str(args.out), "sha256": hashlib.sha256(payload).hexdigest()}))
        else:
            weight = number(args.weight) / 100
            result = load_tree(args.path)
            for preset in result["presets"]:
                preset["coefficients"] = {name: ends["small"] + weight * (ends["big"] - ends["small"])
                                          for name, ends in preset["morphs"].items()}
            print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError, ET.ParseError) as error:
        print("CLAW presets: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
