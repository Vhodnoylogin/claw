"""Build a VR-only werewolf armor addon from CLAW's existing authored record."""
from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / "src/main/resources/plugins/CLAW"
ADDON = "CLAW - VR Body.esp"
ARMATURE = "NakedTorsoWerewolfBeast - 0CDD87_Skyrim.esm.yaml"
NAMESPACE = "Meshes/Actors/WerewolfBeast/CLAW/FirstPerson"
SEXES = ("male", "female")


def resource_paths(sex, endpoint=None):
    if sex not in SEXES or (endpoint is not None and (type(endpoint) is not int or endpoint not in (0, 1))):
        raise ValueError("Explicit sex and endpoint0/1 required")
    base = f"{NAMESPACE}/{sex}"
    return f"{base}/Body.tri" if endpoint is None else f"{base}/Body_{endpoint}.nif"


def armor_path(sex):
    return resource_paths(sex, 1).removeprefix("Meshes/").replace("/", "\\")


def replace_once(text, pattern, replacement, description):
    matches = list(re.finditer(pattern, text, flags=re.MULTILINE))
    if len(matches) != 1:
        raise ValueError(f"Expected one {description} in the authored CDD87 record")
    match = matches[0]
    return text[:match.start()] + replacement(match) + text[match.end():]


def armor_source(text, disabled):
    disabled = frozenset(disabled)
    if not disabled or not disabled.issubset(SEXES):
        raise ValueError("Explicit male and/or female model-range policy required")
    if not re.search(r"^FormKey: 0CDD87:Skyrim\.esm$", text, flags=re.MULTILINE):
        raise ValueError("Expected the base werewolf CDD87 armor addon")
    for sex in disabled:
        label = sex.capitalize()
        pattern = rf"(^WeightSliderEnabled:\n(?:(?:  Male|  Female): (?:True|False)\n)*?  {label}: )True$"
        text = replace_once(text, pattern, lambda match: match[1] + "False", f"{sex} weight slider")
    pattern = r"^FirstPersonModel:\n(?: +[^\n]+\n)+"
    fields = "".join(f"  {sex.capitalize()}:\n    File: {armor_path(sex)}\n" for sex in SEXES)
    return replace_once(text, pattern, lambda _match: "FirstPersonModel:\n" + fields, "first-person models")


def addon_header(base_header):
    text = replace_once(base_header, r"^ModKey: CLAW\.esp$", lambda _match: f"ModKey: {ADDON}", "base mod key")
    text = replace_once(text, r"^  Flags:\n  - Small\n", lambda _match: "", "base small flag")
    return replace_once(
        text, r"^  MasterReferences:\n  - Master: Skyrim\.esm\n    FileSize: 0$",
        lambda match: match[0] + "\n  - Master: CLAW.esp\n    FileSize: 0", "base master list",
    )


def verify_record(esp, disabled):
    """Read back the file emitted by Spriggit before handing it to packaging."""
    from engine_audit import arma_summary
    from record_reader import FormKey, PluginFile

    with closing(PluginFile(esp)) as parsed:
        target = FormKey("Skyrim.esm", 0xCDD87)
        if parsed.masters != ["skyrim.esm", "claw.esp"] or set(parsed.records) != {target}:
            raise ValueError("VR add-on must contain only the declared CDD87 override")
        record = parsed.records[target]
        if record.signature != "ARMA":
            raise ValueError("Expected an armor add-on record")
        details = arma_summary(record)
        flags = [details["weightFlagBytes"][sex] for sex in SEXES]
        if flags != [0 if sex in disabled else 2 for sex in SEXES]:
            raise ValueError("Compiled model-range policy did not match the selected sexes")
        if details["race"] != FormKey("Skyrim.esm", 0xCDD84).text() or details["biped"]["mask"] != 4:
            raise ValueError("VR add-on must retain the werewolf race and body slot")
        expected_world = {
            sex: rf"Actors\WerewolfBeast\Character Assets\{sex.capitalize()}BodyWereWolf_1.NIF" for sex in SEXES
        }
        if details["worldModels"] != expected_world:
            raise ValueError("VR add-on must retain the same world models")
        paths = details["firstPersonRecordModels"]
        if paths != {sex: armor_path(sex) for sex in SEXES}:
            raise ValueError("Compiled armor add-on must reference the first-person namespace")
        return {"formKey": target.text(), "modelRangeBytes": flags, "worldModels": expected_world,
                "firstPersonRecordModels": paths}


def build(output, disabled, *, compiler=None):
    sys.path[:0] = [str(ROOT/"src/main/python/vr"), str(ROOT/"src/main/python/build-tools")]
    from body_resource import safe_output, sha256
    from plugin import Spriggit, WRAPPER

    disabled = frozenset(disabled)
    inputs = [BASE/"ArmorAddons"/ARMATURE, BASE/"RecordData.yaml", BASE/"spriggit-meta.json"]
    output = safe_output(output, inputs)
    originals = [p.read_text(encoding="utf-8-sig") for p in inputs]
    source = armor_source(originals[0], disabled)
    header = addon_header(originals[1])
    meta = json.loads(originals[2])
    meta["ModKey"] = ADDON
    pins = {str(path):sha256(path) for path in inputs}
    output.mkdir(parents=True)
    generated = output/"sources"
    records = generated/"ArmorAddons"
    records.mkdir(parents=True)
    (records/ARMATURE).write_text(source,encoding="utf-8",newline="\n")
    (generated/"RecordData.yaml").write_text(header,encoding="utf-8",newline="\n")
    (generated/"spriggit-meta.json").write_text(json.dumps(meta,indent=2)+"\n",encoding="utf-8")

    package = output/"package"
    package.mkdir()
    esp = package/ADDON
    Spriggit(Path(compiler) if compiler else WRAPPER).build(generated, esp)
    result = verify_record(esp, disabled)
    if pins != {str(path):sha256(path) for path in inputs}:
        raise ValueError("Authored base record changed during the build")
    receipt = {"status":"VR_DISPATCH_CANDIDATE", "platform":"SkyrimVR",
               "baseInputSha256":pins, "addon":ADDON, "addonSha256":sha256(esp),
               "bytes":esp.stat().st_size, "runtimeQualified":False, **result}
    (output/"dispatch-build.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disable-range", choices=SEXES, action="append", required=True)
    parser.add_argument("--spriggit", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.out,args.disable_range,compiler=args.spriggit)))


if __name__ == "__main__":
    main()
