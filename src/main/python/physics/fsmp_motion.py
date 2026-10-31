"""Separate original FSMP motion XML and lossless hooks on cloned CLAW bodies."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import xml.etree.ElementTree as ET

import motion_adapter as common

TOOLS = common.ROOT.parent / "build-tools"
sys.path.insert(0, str(TOOLS))
from head_split import Nif

HOOK = "HDT Skinned Mesh Physics Object"
MESH = "Meshes/Actors/WerewolfBeast/Character Assets/"
XML_ROOT = "SKSE/Plugins/hdtSkinnedMeshConfigs/CLAW/"
SOURCE = "https://github.com/DaymareOn/hdtSMP64/blob/e52ad960048c14e637d14fcbd65314ca017fc3b8/src/"


def bind_nif(payload, xml_path):
    """Append one root string hook; all existing geometry/skin blocks stay exact."""
    original, result = Nif(payload), Nif(payload)
    if original.kind(0) != "NiNode":
        raise ValueError("FSMP hook requires the existing Scene Root NiNode")
    for index, block in enumerate(original.blocks):
        if original.kind(index) == "NiStringExtraData":
            if len(block) != 8:
                raise ValueError("Unsupported string extra-data layout")
            name, _ = struct.unpack("<II", block)
            if original.strings[name].decode("utf-8") == HOOK:
                raise ValueError("Input NIF already has an FSMP binding; two systems are refused")
    if "NiStringExtraData" not in result.type_names:
        result.type_names.append("NiStringExtraData")
    new_id = result.append("NiStringExtraData", struct.pack("<II", result.name(HOOK), result.name(xml_path)))
    root = original.blocks[0]
    count = struct.unpack_from("<I", root, 4)[0]
    end = 8 + 4 * count
    if end > len(root):
        raise ValueError("Truncated Scene Root extra-data array")
    result.blocks[0] = root[:4] + struct.pack("<I", count + 1) + root[8:end] + struct.pack("<I", new_id) + root[end:]
    after = result.bytes()
    verified = Nif(after)
    if verified.blocks[1:len(original.blocks)] != original.blocks[1:] or verified.blocks[0] != result.blocks[0]:
        raise ValueError("FSMP binding changed an original non-root block")
    if verified.strings[:len(original.strings)] != original.strings or verified.footer != original.footer:
        raise ValueError("FSMP binding changed existing string indices or roots")
    return after, {"addedBlock": new_id, "oldBlockCount": len(original.blocks), "newBlockCount": len(verified.blocks),
                   "unchangedOriginalNonRootBlocks": len(original.blocks) - 1,
                   "originalShapeSkinMaterialBlocksExact": True, "xml": xml_path}


def render_xml(breast=False):
    """Original small-motion parameters using inspected FSMP parser names."""
    chains = [("NPC Head [Head]", common.source.NODES[:2]),
              ("NPC Head [Head]", common.source.NODES[2:4]),
              ("Tails", common.source.NODES[4:])]
    if breast:
        chains += [("NPC L PreBreast P1", (common.source.BREAST_NODES[0],)),
                   ("NPC R PreBreast P1", (common.source.BREAST_NODES[1],))]
    root = ET.Element("system")
    root.append(ET.Comment(" Original CLAW motion-only adapter; no collision shapes or shared settings. "))
    for anchor in dict.fromkeys(anchor for anchor, _ in chains):
        bone = ET.SubElement(root, "bone", name=anchor)
        ET.SubElement(bone, "mass").text = "0"
    for anchor, chain in chains:
        parent = anchor
        for node in chain:
            bone = ET.SubElement(root, "bone", name=node)
            ET.SubElement(bone, "mass").text = "0.05"
            ET.SubElement(bone, "inertia", x="0.1", y="0.1", z="0.1")
            for name, value in (("linearDamping", ".4"), ("angularDamping", ".4"),
                                ("gravity-factor", "0"), ("wind-factor", "0")):
                ET.SubElement(bone, name).text = value
            constraint = ET.SubElement(root, "generic-constraint", bodyA=parent, bodyB=node)
            # FrameInB identity is resolved against the actual loaded rest
            # transforms by calcFrame; intermediary CME nodes remain untouched.
            ET.SubElement(constraint, "frameInB")
            for name, value in (("linearLowerLimit", "-.15"), ("linearUpperLimit", ".15"),
                                ("angularLowerLimit", "-.01"), ("angularUpperLimit", ".01"),
                                ("linearStiffness", "1"), ("angularStiffness", ".5"),
                                ("linearDamping", ".4"), ("angularDamping", ".4"),
                                ("linearEquilibrium", "0"), ("angularEquilibrium", "0")):
                ET.SubElement(constraint, name, x=value, y=value, z=value)
            parent = node
    ET.indent(root)
    payload = ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"
    parsed = ET.fromstring(payload)
    dynamic = {bone.attrib["name"] for bone in parsed.findall("bone") if bone.findtext("mass") != "0"}
    expected = set(common.source.NODES + (common.source.BREAST_NODES if breast else ()))
    if dynamic != expected or len(parsed.findall("generic-constraint")) != len(expected):
        raise ValueError("Incomplete FSMP driver/constraint graph")
    return payload


def build_adapter(out, provider_snapshot, resources, pynifly, *, breast=False, api=None):
    out = common.source.destination(out)
    if set(resources) != set(common.BODY_ROLES) | {"skeleton"}:
        raise ValueError("Explicit male/female weight endpoints and skeleton are required")
    resources = {role: Path(path).resolve() for role, path in resources.items()}
    if len(set(resources.values())) != 5:
        raise ValueError("Each selected resource needs its own explicit path")
    for directory in (Path(provider_snapshot).resolve(), *[path.parent for path in resources.values()]):
        if directory == out or directory in out.parents:
            raise ValueError("FSMP adapter output cannot be inside its inputs")
    pins = {role: common.pin(path) for role, path in resources.items()}
    inputs = common.source.SourceInputs(breast=breast)
    if pins["skeleton"]["sha256"] != inputs.json("capsules.json")["provenance"]["xp32Sha256"]:
        raise ValueError("FSMP adapter skeleton differs from existing reviewed XP32")
    audit = common.source.audit_provider(provider_snapshot)
    common.source.require_provider_clear(audit, breast=breast)
    dependencies = []
    if api is None:
        api, dependencies = common.load_pynifly(Path(pynifly))
    coverage = common.inspect_resources(api, resources, breast)
    sources = [common.pin(Path(__file__)), common.pin(Path(common.__file__)), common.pin(TOOLS / "head_split.py"),
               common.pin(common.ROOT / "motion-adapters.md")]
    files = {}
    for sex in ("male", "female"):
        files[XML_ROOT + "CLAWMotion" + sex.title() + ".xml"] = render_xml(breast and sex == "female")
    bindings = {}
    for role in common.BODY_ROLES:
        sex = "female" if role.startswith("female") else "male"
        name = sex + "bodywerewolf_" + role[-1] + ".nif"
        xml_path = XML_ROOT + "CLAWMotion" + sex.title() + ".xml"
        files[MESH + name], bindings[role] = bind_nif(resources[role].read_bytes(), xml_path)
    files["README.txt"] = ("CLAW Physics - FSMP Motion\n\nSeparate optional motion adapter for exact inspected CLAW bodies.\n"
        "Requires a separately installed runtime-matched Faster HDT-SMP provider and the selected CLAW core/XP32.\n"
        "Place after the selected CLAW body mod. Choose this OR CLAW CBPC motion; never both.\n"
        "Cloned body NIFs contain only a new Scene Root XML hook; all original non-root blocks stay exact.\n"
        "No TRI, skeleton, provider binary, collider/contact configuration, Papyrus host or global defaultBBPs is bundled.\n"
        "Spring constraints use existing ear/tail nodes; female P1 is " + ("included" if breast else "excluded") + ".\n"
        "Current linked morphs retain the same skin weights; these constants do not refit contacts or rest pivots.\n"
        "Game/visible-motion and provider compatibility remain pending.\n"
        "Source: https://github.com/Vhodnoylogin/claw/tree/feature/post-070-backlog/src/main/python/physics\n").encode()
    common.unchanged([*pins.values(), *dependencies, *sources])
    inputs.verify()
    common.source.verify_provider_unchanged(audit)
    out.mkdir(parents=True, exist_ok=False)
    pending = out / "FAILED-unverified-do-not-install"
    pending.write_text("FSMP adapter incomplete.\n")
    package = out / "package"
    for name, payload in files.items():
        target = package / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    # Public native readback independently resolves all four actual root hooks.
    for role in common.BODY_ROLES:
        sex = "female" if role.startswith("female") else "male"
        path = package / (MESH + sex + "bodywerewolf_" + role[-1] + ".nif")
        nif = api.NifFile(str(path))
        hook = nif.root.get_extra_data(blockname="NiStringExtraData", name=HOOK)
        if hook is None or hook.string_data != bindings[role]["xml"]:
            raise ValueError("Written FSMP root hook failed native readback")
        common.inspect_body(nif, common.source.NODES + (common.source.BREAST_NODES if breast and sex == "female" else ()), role)
    archive = out / "CLAW Physics - FSMP Motion.zip"
    common.archive(archive, files)
    common.unchanged([*pins.values(), *dependencies, *sources])
    inputs.verify()
    common.source.verify_provider_unchanged(audit)
    binary = next((row for row in audit["files"] if row["path"].casefold() == "hdtsmp64.dll" and row["bytes"]), None)
    report = {"schemaVersion": 1, "status": "built-offline-FSMP-motion-runtime-pending",
              "provider": "fsmp", "providerBinary": binary, "runtimeMatchedProviderRequired": True,
              "runtimeQualified": False, "gameValidated": False, "releaseReady": False,
              "sourceContracts": {"binding": SOURCE + "hdtDefaultBBP.cpp", "constraints": SOURCE + "hdtSkyrimSystem.cpp"},
              "collisionResponseEnabled": False, "resources": pins, "storedWeightCoverage": coverage,
              "bindings": bindings, "sourceInputs": [*inputs.rows(), *sources], "dependencies": dependencies,
              "providerAudit": audit,
              "files": [{"path": name, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
                        for name, payload in sorted(files.items())], "archive": common.pin(archive)}
    (out / "fsmp-motion-build.json").write_text(json.dumps(report, indent=2) + "\n")
    pending.unlink()
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider-snapshot", type=Path, required=True)
    for role in (*common.BODY_ROLES, "skeleton"):
        parser.add_argument("--" + role, type=Path, required=True)
    parser.add_argument("--pynifly", type=Path, required=True)
    parser.add_argument("--with-breast-motion", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = build_adapter(args.out, args.provider_snapshot,
                               {role: getattr(args, role) for role in (*common.BODY_ROLES, "skeleton")},
                               args.pynifly, breast=args.with_breast_motion)
        print(json.dumps({"status": report["status"], "archive": report["archive"]["path"], "providerBinaryPresent": report["providerBinary"] is not None}))
        return 0
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
        print("CLAW FSMP motion: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
