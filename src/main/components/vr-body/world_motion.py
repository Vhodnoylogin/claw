"""Build optional FSMP overlays for the fixed-profile VRIK world-body experiment."""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import xml.etree.ElementTree as ET

from vr_dispatch import LEGACY_ALIAS, ROOT, SEXES, require_static_nif, resource_paths
from body_resource import bodytri, safe_output, visible_by_hidden_flags

PHYSICS = ROOT / "src/main/python/physics"
sys.path.insert(0, str(PHYSICS))
import fsmp_motion

FIXED_SHA256 = "e6c4660c4873e4cbc54845a17767bbdd26835e2d15897277f5dc216dc9e32699"
CORE_SHA256 = "f571ad5e486600c3fcd06432034eeed9a2837be2706ca59bc0f72be28262c91a"
SKELETON_SHA256 = "b64b614d06eb854512ef4a9d6b08777fe0f9580f47d495d20db16dabb9fc2dd0"


def alias_member(config, files, sex):
    """Use the selected fixed-profile FOMOD branch, not a filename heuristic."""
    if sex not in SEXES:
        raise ValueError("An explicit fixed-profile sex is required")
    groups = config.findall("./installSteps/installStep/optionalFileGroups/group")
    if len(groups) != 1 or groups[0].get("type") != "SelectExactlyOne":
        raise ValueError("Expected one mutually exclusive fixed-profile FOMOD group")
    options = groups[0].findall("plugins/plugin")
    by_name = {node.get("name"): node for node in options}
    if len(options) != len(SEXES) or set(by_name) != {f"{value.capitalize()} player profile" for value in SEXES}:
        raise ValueError("Unexpected fixed-profile options")
    expected = f"profiles/{sex}/{Path(LEGACY_ALIAS).name}"
    mapping = by_name[f"{sex.capitalize()} player profile"].find("files")
    rows = [] if mapping is None else list(mapping)
    if len(rows) != 1 or rows[0].tag != "file" or rows[0].get("source") != expected or rows[0].get("destination") != LEGACY_ALIAS:
        raise ValueError("Fixed-profile choice must select exactly its own legacy body alias")
    extra_mappings = config.findall("requiredInstallFiles/file") + config.findall("conditionalFileInstalls//file")
    if any(row.get("destination", "").casefold() == LEGACY_ALIAS.casefold() for row in extra_mappings):
        raise ValueError("The legacy alias must be selected only by the fixed-profile choice")
    if expected not in files or files.get("shared/" + resource_paths(sex, 1)) != files[expected]:
        raise ValueError("Fixed-profile alias does not match its packaged namespaced carrier")
    return expected


def open_tools(path):
    spec = importlib.util.spec_from_file_location("claw_vr_world_motion_archive", path)
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


def build(fixed_profile, core_release, skeleton, pynifly, out):
    common = fsmp_motion.common
    source_file = ROOT / "src/main/python/build-tools/package-source-build.py"
    pack = open_tools(source_file)
    fixed_profile, core_release, skeleton = (Path(path).resolve(strict=True)
                                            for path in (fixed_profile, core_release, skeleton))
    out = Path(out).absolute()
    if any(path.is_junction() or path.is_symlink() for path in (out, *out.parents)):
        raise ValueError("Output ancestry must use real directories")
    out = safe_output(out, (fixed_profile, core_release, skeleton))
    core_payload, fixed_payload = core_release.read_bytes(), fixed_profile.read_bytes()
    if (pack.sha(core_payload), pack.sha(fixed_payload), common.pin(skeleton)["sha256"]) != (
            CORE_SHA256, FIXED_SHA256, SKELETON_SHA256):
        raise ValueError("Expected the exact released core, verified fixed-profile archive and XP32 skeleton")
    sources = (Path(__file__), source_file, source_file.with_name("build-unified-release.py"),
               Path(fsmp_motion.__file__), Path(common.__file__), fsmp_motion.RIG_SOURCE,
               Path(fsmp_motion.head_split.__file__), Path(fsmp_motion.materials.__file__),
               Path(sys.modules["vr_dispatch"].__file__), Path(sys.modules["body_resource"].__file__))
    pins = [common.pin(path) for path in (fixed_profile, core_release, skeleton, *sources)]
    core, fixed = pack.read_zip(core_payload), pack.read_zip(fixed_payload)
    config = ET.fromstring(fixed["fomod/ModuleConfig.xml"])
    core_plans = pack.selection_audit(core)
    static_plans = [plan for plan in core_plans if plan["physics"] == "none"]
    if len(static_plans) != 20:
        raise ValueError("Missing original physics-off install choices")
    core_routes = [{row["path"]: row["source"] for row in plan["files"]
                    if row["path"].endswith(".nif") or row["path"].startswith(pack.MOTION_XML)}
                   for plan in static_plans]
    core_off = core_routes[0]
    if (len(core_off) != 8 or any(not name.endswith(".nif") for name in core_off)
            or any(routes != core_off for routes in core_routes)):
        raise ValueError("Core physics-off choices must share the eight static model routes")
    for source in set(core_off.values()):
        require_static_nif(core[source])
    api, dependencies = common.load_pynifly(Path(pynifly))
    skel = api.NifFile(str(skeleton))
    staged = {}
    for sex in SEXES:
        source = alias_member(config, fixed, sex)
        original = fixed[source]
        require_static_nif(original, expected_sex=sex)
        breast = sex == "female"
        xml = pack.MOTION_XML + sex.title() + ".xml"
        xml_payload = core[pack.MOTION_PREFIX + "FSMP/" + xml]
        if xml_payload != fsmp_motion.render_xml(breast):
            raise ValueError("Released FSMP motion XML differs from its authored rig")
        root = ET.fromstring(xml_payload)
        required = {bone.get("name") for bone in root.findall("bone")}
        if not required <= set(skel.nodes):
            raise ValueError("Pinned XP32 skeleton lacks a motion bone")
        drivers = tuple(link.get("bodyB") for link in root.findall("generic-constraint"))
        overlay, binding = fsmp_motion.bind_nif(original, xml)
        staged[sex] = (source, xml, xml_payload, drivers, overlay, binding)

    out.mkdir(parents=True)
    report = {"schema": "claw-fixed-profile-vr-world-motion/1", "inputs": pins, "dependencies": dependencies,
              "baseSelection": "None", "overlayDestination": LEGACY_ALIAS,
              "coreOffModelHashes": {dest: pack.sha(core[source]) for dest, source in core_off.items()},
              "requiredCoreStaticPlans": len(static_plans), "outputs": {},
              "installed": False, "gameValidated": False, "releaseReady": False}
    validated = {}
    with TemporaryDirectory(prefix="native-readback-", dir=out) as scratch:
        for sex, (source, xml, xml_payload, drivers, overlay, binding) in staged.items():
            path = Path(scratch) / f"{sex}.nif"
            path.write_bytes(overlay)
            nif = api.NifFile(str(path))
            hook = nif.root.get_extra_data(blockname="NiStringExtraData", name=fsmp_motion.HOOK)
            expected_tri = resource_paths(sex).removeprefix("Meshes/").replace("/", "\\").lower()
            if hook is None or hook.string_data != xml or any(bodytri(shape) != [("BODYTRI", expected_tri)] for shape in nif.shapes):
                raise ValueError("Native readback differs for FSMP hook or namespaced TRI")
            coverage = common.inspect_body(nif, drivers, "Fixed-profile " + sex)
            visible = {shape.name for shape in nif.shapes if visible_by_hidden_flags(shape)}
            members = {LEGACY_ALIAS: overlay, xml: xml_payload}
            visible_counts = {bone: sum(count for name, count in shapes.items() if name in visible)
                              for bone, shapes in coverage.items()}
            moving = set(common.source.NODES[4:] + (common.source.BREAST_NODES if sex == "female" else ()))
            if any(not visible_counts[bone] for bone in moving):
                raise ValueError("Missing visible tail or breast influence")
            validated[sex] = members
            report["outputs"][sex] = {"fromAliasMember": source,
                                       "members": {name: pack.sha(data) for name, data in members.items()},
                                       "requiredTri": {"path": resource_paths(sex),
                                                       "sha256": pack.sha(fixed["shared/" + resource_paths(sex)])},
                                       "binding": binding, "driverVertices": coverage,
                                       "visibleDriverVertices": visible_counts}
    common.unchanged([*pins, *dependencies])
    for sex, members in validated.items():
        archive = out / f"test_CLAW VR World Motion - {sex.capitalize()}.zip"
        archive.write_bytes(pack.zip_bytes(members))
        if pack.read_zip(archive.read_bytes()) != members:
            raise ValueError("Written world motion overlay failed archive readback")
        report["outputs"][sex]["archive"] = common.pin(archive)
    (out / "world-motion.json").write_bytes(pack.encoded(report))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("fixed-profile", "core-release", "skeleton", "pynifly", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    try:
        report = build(**vars(parser.parse_args(argv)))
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print(f"CLAW VR world motion: {error}", file=sys.stderr)
        return 2
    print("World-motion overlays: " + ", ".join(report["outputs"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
