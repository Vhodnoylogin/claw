"""Build a VR-only werewolf armor addon from CLAW's existing authored record."""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import sys
import xml.etree.ElementTree as ET
import zipfile


ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / "src/main/python/vr"), str(ROOT / "src/main/python/build-tools")]
BASE = ROOT / "src/main/resources/plugins/CLAW"
ADDON = "CLAW - VR Body.esp"
ARMATURE = "NakedTorsoWerewolfBeast - 0CDD87_Skyrim.esm.yaml"
NAMESPACE = "Meshes/Actors/WerewolfBeast/CLAW/FirstPerson"
SEXES = ("male", "female")
STOCK_FIRST_PERSON = {
    "male": r"Actors\Character\Character Assets\1stPersonMaleBody_1.NIF",
    "female": r"Actors\Character\Character Assets\1stPersonFemaleBody_1.nif",
}
LEGACY_ALIAS = "Meshes/Actors/character/character assets/1stperson_werewolf_hands.nif"
FIXED_PROFILE_NAME = "CLAW VR Body - Fixed Profile Diagnostic"
COLLISION_BLOCKS = {"NiCollisionData", "NiCollisionObject", "NiCollisionSwitch", "RootCollisionNode"}
FSMP_HOOK = b"hdt skinned mesh physics object"


def resource_paths(sex, endpoint=None):
    if sex not in SEXES or (endpoint is not None and (type(endpoint) is not int or endpoint not in (0, 1))):
        raise ValueError("Explicit sex and endpoint0/1 required")
    base = f"{NAMESPACE}/{sex}"
    return f"{base}/Body.tri" if endpoint is None else f"{base}/Body_{endpoint}.nif"


def armor_path(sex):
    return resource_paths(sex, 1).removeprefix("Meshes/").replace("/", "\\")


def bodytri_path(sex):
    return resource_paths(sex).removeprefix("Meshes/").replace("/", "\\").lower()


def resource_layout(manifest):
    """Accept only the authored first-person assets emitted by the body builder."""
    expected = {resource_paths(sex, endpoint) for sex in SEXES for endpoint in (None, 0, 1)}
    if (not isinstance(manifest, dict) or type(manifest.get("schemaVersion")) is not int or manifest["schemaVersion"] != 1
            or manifest.get("component") != "CLAW/vr-body"
            or any(manifest.get(field) != [] for field in ("worldOverrides", "skeletonFiles", "textureFiles"))):
        raise ValueError("Expected the independent CLAW first-person resource manifest")
    files = manifest.get("files")
    if (not isinstance(files, dict) or set(files) != expected
            or any(not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha) for sha in files.values())):
        raise ValueError("Expected the six checked first-person asset paths and hashes")
    return files


def require_static_nif(data, *, expected_sex=None, expected_tri=None):
    """Check static resources and, for packaged bodies, their actual shape TRI links."""
    from player_only_materials import Reader, container

    _, middle, types, indices, blocks, _ = container(data)
    reader = Reader(middle)
    count, _ = reader.unpack("<II")
    strings = [reader.string() for _ in range(count)]
    bodytri_blocks, shape_blocks = set(), []
    if expected_sex is not None:
        expected_tri = bodytri_path(expected_sex)
    expected_tri = expected_tri.encode("ascii") if expected_tri is not None else None
    for index, (kind_index, block) in enumerate(zip(indices, blocks, strict=True)):
        kind = types[kind_index]
        if kind.casefold().startswith("bhk") or kind in COLLISION_BLOCKS:
            raise ValueError(f"Static VR body contains collision block {kind}")
        if kind == "NiStringExtraData":
            if len(block) != 8:
                raise ValueError("Unsupported VR body string extra")
            name, value = struct.unpack("<II", block)
            if max(name, value) >= len(strings):
                raise ValueError("Invalid VR body string extra index")
            if strings[name].strip().lower() == FSMP_HOOK:
                raise ValueError("Static VR body contains an FSMP binding")
            if expected_tri is not None and strings[name] == b"BODYTRI":
                if strings[value] != expected_tri:
                    label = "namespaced Body.tri" if expected_sex is not None else "declared world TRI"
                    raise ValueError("VR BODYTRI must name its own sex's " + label)
                bodytri_blocks.add(index)
        if expected_tri is not None and kind.endswith(("TriShape", "TriStrips")):
            shape_blocks.append(block)
    if expected_tri is not None:
        if not shape_blocks:
            raise ValueError("First-person NIF must contain shapes with a BODYTRI link")
        for block in shape_blocks:
            shape = Reader(block)
            _, count = shape.unpack("<II")  # NiObjectNET name and extra-data count.
            refs = shape.unpack(f"<{count}I")
            if any(ref >= len(blocks) for ref in refs) or sum(ref in bodytri_blocks for ref in refs) != 1:
                raise ValueError("First-person shape must link exactly one same-sex BODYTRI block")


def fixed_profile_xml(shared, alternatives):
    def encode(root):
        ET.indent(root)
        return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"

    config = ET.Element("config", {
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "xsi:noNamespaceSchemaLocation": "http://qconsulting.ca/fo3/ModConfig5.0.xsd",
    })
    ET.SubElement(config, "moduleName").text = FIXED_PROFILE_NAME
    required = ET.SubElement(config, "requiredInstallFiles")
    for destination, source in shared.items():
        ET.SubElement(required, "file", source=source, destination=destination, priority="0")
    steps = ET.SubElement(config, "installSteps", order="Explicit")
    step = ET.SubElement(steps, "installStep", name="Choose the player mesh for this MO2 profile")
    groups = ET.SubElement(step, "optionalFileGroups", order="Explicit")
    group = ET.SubElement(groups, "group", name="Fixed legacy mesh for this profile", type="SelectExactlyOne")
    plugins = ET.SubElement(group, "plugins", order="Explicit")
    for sex, source in alternatives.items():
        plugin = ET.SubElement(plugins, "plugin", name=f"{sex.capitalize()} player profile")
        ET.SubElement(plugin, "description").text = (
            f"Close Skyrim VR first. Use the fixed {sex} player mesh in a disposable MO2 test profile. "
            "Reinstall and restart to switch."
        )
        files = ET.SubElement(plugin, "files")
        ET.SubElement(files, "file", source=source, destination=LEGACY_ALIAS, priority="0")
        descriptor = ET.SubElement(plugin, "typeDescriptor")
        ET.SubElement(descriptor, "type", name="Optional")

    info = ET.Element("fomod")
    ET.SubElement(info, "Name").text = FIXED_PROFILE_NAME
    ET.SubElement(info, "Version").text = "Diagnostic"
    ET.SubElement(info, "Description").text = "Private CLAW diagnostic for a disposable MO2 Skyrim VR profile."
    return {"fomod/ModuleConfig.xml": encode(config), "fomod/info.xml": encode(info)}


def assemble(esp, resource_candidate, archive, *, fixed_profile_fomod=False):
    from body_resource import read_json, sha256

    candidate = Path(resource_candidate).resolve(strict=True)
    manifest = candidate / "install-manifest.json"
    manifest_sha = sha256(manifest)
    files = resource_layout(read_json(manifest))
    assets = {esp.name: (esp, sha256(esp))}
    for relative, digest in sorted(files.items()):
        source = candidate / "resources" / relative
        if source.resolve(strict=True) != source:
            raise ValueError("Mismatched first-person resource " + relative)
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("Mismatched first-person resource " + relative)
        if source.suffix == ".nif":
            require_static_nif(data, expected_sex=source.parent.name)
        assets[relative] = (source, digest)
    metadata = {}
    if fixed_profile_fomod:
        shared = {destination: f"shared/{destination}" for destination in assets}
        alternatives = {sex: f"profiles/{sex}/{Path(LEGACY_ALIAS).name}" for sex in SEXES}
        members = {source: assets[destination] for destination, source in shared.items()}
        members.update({source: assets[resource_paths(sex, 1)] for sex, source in alternatives.items()})
        metadata = fixed_profile_xml(shared, alternatives)
    else:
        members = assets
    payload = {name: digest for name, (_, digest) in members.items()}
    payload.update({name: hashlib.sha256(raw).hexdigest() for name, raw in metadata.items()})
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as writer:
        for relative, (source, _) in members.items():
            entry = zipfile.ZipInfo(relative)
            entry.compress_type = zipfile.ZIP_DEFLATED
            with source.open("rb") as content, writer.open(entry, "w") as target:
                shutil.copyfileobj(content, target)
        for relative, raw in metadata.items():
            entry = zipfile.ZipInfo(relative)
            entry.compress_type = zipfile.ZIP_DEFLATED
            writer.writestr(entry, raw)
    with zipfile.ZipFile(archive) as opened:
        if len(opened.namelist()) != len(payload) or set(opened.namelist()) != set(payload) or any(
                hashlib.sha256(opened.read(name)).hexdigest() != digest for name, digest in payload.items()):
            raise ValueError("Assembled VR archive differs from its authored payload")
    if sha256(manifest) != manifest_sha:
        raise ValueError("First-person manifest changed during assembly")
    return {"archive": archive.name, "archiveSha256": sha256(archive),
            "resourceManifestSha256": manifest_sha, "payloadSha256": payload}


def replace_once(text, pattern, replacement, description):
    matches = list(re.finditer(pattern, text, flags=re.MULTILINE))
    if len(matches) != 1:
        raise ValueError(f"Expected one {description} in the authored CDD87 record")
    match = matches[0]
    return text[:match.start()] + replacement(match) + text[match.end():]


def armor_source(text, disabled, *, keep_stock_first_person=False):
    disabled = frozenset(disabled)
    if not disabled or not disabled.issubset(SEXES):
        raise ValueError("Explicit male and/or female model-range policy required")
    if not re.search(r"^FormKey: 0CDD87:Skyrim\.esm$", text, flags=re.MULTILINE):
        raise ValueError("Expected the base werewolf CDD87 armor addon")
    for sex in disabled:
        label = sex.capitalize()
        pattern = rf"(^WeightSliderEnabled:\n(?:(?:  Male|  Female): (?:True|False)\n)*?  {label}: )True$"
        text = replace_once(text, pattern, lambda match: match[1] + "False", f"{sex} weight slider")
    if keep_stock_first_person:
        return text
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


def verify_record(esp, disabled, *, keep_stock_first_person=False):
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
        expected_first_person = (STOCK_FIRST_PERSON if keep_stock_first_person else
                                 {sex: armor_path(sex) for sex in SEXES})
        if paths != expected_first_person:
            raise ValueError("Compiled armor add-on first-person model paths differ from the selected mode")
        return {"formKey": target.text(), "modelRangeBytes": flags, "worldModels": expected_world,
                "firstPersonRecordModels": paths}


def build(output, disabled, *, compiler=None, resource_candidate=None, fixed_profile_fomod=False,
          keep_stock_first_person=False):
    disabled = frozenset(disabled)
    if keep_stock_first_person and resource_candidate is not None:
        raise ValueError("--keep-stock-first-person requires a loose override without --resources")
    if fixed_profile_fomod and (disabled != frozenset(SEXES) or resource_candidate is None):
        raise ValueError("--fixed-profile-fomod requires both sexes range-disabled and --resources")
    from body_resource import safe_output, sha256
    from plugin import Spriggit, WRAPPER

    inputs = [BASE/"ArmorAddons"/ARMATURE, BASE/"RecordData.yaml", BASE/"spriggit-meta.json"]
    resource_inputs = [Path(resource_candidate) / "install-manifest.json"] if resource_candidate is not None else []
    output = safe_output(output, [*inputs, *resource_inputs])
    originals = [p.read_text(encoding="utf-8-sig") for p in inputs]
    source = armor_source(originals[0], disabled, keep_stock_first_person=keep_stock_first_person)
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
    result = verify_record(esp, disabled, keep_stock_first_person=keep_stock_first_person)
    if pins != {str(path):sha256(path) for path in inputs}:
        raise ValueError("Authored base record changed during the build")
    receipt = {"status":"VR_DISPATCH_CANDIDATE", "platform":"SkyrimVR",
               "baseInputSha256":pins, "addon":ADDON, "addonSha256":sha256(esp),
               "bytes":esp.stat().st_size, "runtimeQualified":False, **result}
    if resource_candidate is not None:
        archive_name = FIXED_PROFILE_NAME if fixed_profile_fomod else Path(ADDON).stem
        receipt.update(assemble(esp, resource_candidate, output / (archive_name + ".zip"),
                                fixed_profile_fomod=fixed_profile_fomod))
    if fixed_profile_fomod:
        receipt.update({"archiveMode": "fixed-profile-fomod", "legacyAlias": LEGACY_ALIAS})
    (output/"dispatch-build.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disable-range", choices=SEXES, action="append", required=True)
    parser.add_argument("--spriggit", type=Path)
    parser.add_argument("--resources", type=Path, help="Body candidate directory with install-manifest.json")
    parser.add_argument("--fixed-profile-fomod", action="store_true",
                        help="Private MO2 diagnostic with a fixed male or female legacy mesh selection")
    parser.add_argument("--keep-stock-first-person", action="store_true",
                        help="Change only the world body weight-range flags and retain the base first-person paths")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.out, args.disable_range, compiler=args.spriggit, resource_candidate=args.resources,
                           fixed_profile_fomod=args.fixed_profile_fomod,
                           keep_stock_first_person=args.keep_stock_first_person)))


if __name__ == "__main__":
    main()
