"""Build optional FSMP overlays for the fixed-profile VRIK world-body experiment."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import xml.etree.ElementTree as ET

from vr_dispatch import LEGACY_ALIAS, ROOT, SEXES, require_static_nif, resource_paths
from body_resource import bodytri, read_json, safe_output, visible_by_hidden_flags
from core_archive import PACKAGER, open_tools, read_core_archive, require_reviewed_body, static_routes

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


def build(fixed_profile, core_release, skeleton, pynifly, out, *, core_receipt=None):
    common = fsmp_motion.common
    pack = open_tools(PACKAGER)
    fixed_profile, core_release, skeleton = (Path(path).resolve(strict=True)
                                            for path in (fixed_profile, core_release, skeleton))
    out = Path(out).absolute()
    if any(path.is_junction() or path.is_symlink() for path in (out, *out.parents)):
        raise ValueError("Output ancestry must use real directories")
    inputs = (fixed_profile, core_release, skeleton)
    out = safe_output(out, inputs if core_receipt is None else (*inputs, core_receipt))
    fixed_payload = fixed_profile.read_bytes()
    if pack.sha(fixed_payload) != FIXED_SHA256 or common.pin(skeleton)["sha256"] != SKELETON_SHA256:
        raise ValueError("Expected the exact verified fixed-profile archive and XP32 skeleton")
    core, core_plans, core_pins = read_core_archive(pack, core_release, receipt_path=core_receipt, known_digest=CORE_SHA256)
    profile = Path(__file__).with_name('current-010.json')
    require_reviewed_body(pack, core, core_plans, read_json(profile))
    sources = (Path(__file__), profile, PACKAGER, PACKAGER.with_name("build-unified-release.py"),
               Path(sys.modules["core_archive"].__file__),
               Path(fsmp_motion.__file__), Path(common.__file__), fsmp_motion.RIG_SOURCE,
               Path(fsmp_motion.head_split.__file__), Path(fsmp_motion.materials.__file__),
               Path(sys.modules["vr_dispatch"].__file__), Path(sys.modules["body_resource"].__file__))
    pins = [common.pin(path) for path in (fixed_profile, skeleton, *sources)]
    for path, digest in core_pins.items():
        pin = common.pin(Path(path))
        if pin['sha256'] != digest:
            raise ValueError('Core archive or receipt changed after readback')
        pins.append(pin)
    fixed = pack.read_zip(fixed_payload)
    config = ET.fromstring(fixed["fomod/ModuleConfig.xml"])
    static_plans = [plan for plan in core_plans if plan.get("physics") in {None, "none"}]
    destinations = {f"{pack.MESH}/{sex}{role}_{weight}.nif" for sex in SEXES
                    for role in ("bodywerewolf", "PlayerWerewolf") for weight in (0, 1)}
    core_off = static_routes(static_plans, destinations)
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
    parser.add_argument('--core-receipt', type=Path, help='Read the exact current core ZIP through its build receipt')
    try:
        report = build(**vars(parser.parse_args(argv)))
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print(f"CLAW VR world motion: {error}", file=sys.stderr)
        return 2
    print("World-motion overlays: " + ", ".join(report["outputs"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
