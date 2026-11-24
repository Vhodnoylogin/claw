"""Build optional FSMP overlays for the fixed-profile VRIK world-body experiment."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import xml.etree.ElementTree as ET

from vr_dispatch import LEGACY_ALIAS, ROOT, SEXES, require_static_nif, resource_paths
from body_resource import bodytri, read_json, safe_output, visible_by_hidden_flags
from core_archive import (ANATOMY_VISIBILITY_SOURCE, CORE_INPUT_SOURCE, PACKAGER, anatomy_visibility, open_tools,
                          read_core_archive, require_reviewed_body, static_routes)
from core_package_input import core_version

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


def read_fixed_profile(pack, raw, archive_name, receipt=None):
    if receipt is None:
        if pack.sha(raw) != FIXED_SHA256:
            raise ValueError("Expected the reviewed fixed-profile archive or its dispatch receipt")
        return pack.read_zip(raw)

    files = pack.read_zip(raw)
    if (not isinstance(receipt, dict) or receipt.get("status") != "VR_DISPATCH_CANDIDATE" or
            receipt.get("archiveMode") != "fixed-profile-fomod" or receipt.get("legacyAlias") != LEGACY_ALIAS or
            receipt.get("archive") != archive_name or receipt.get("archiveSha256") != pack.sha(raw) or
            receipt.get("payloadSha256") != {name: pack.sha(data) for name, data in files.items()}):
        raise ValueError("Fixed-profile archive differs from its dispatch receipt")
    return files


def build(fixed_profile, core_release, skeleton, pynifly, out, *, core_receipt=None, fixed_profile_receipt=None):
    common = fsmp_motion.common
    pack = open_tools(PACKAGER)
    fixed_profile, core_release, skeleton = (Path(path).resolve(strict=True)
                                            for path in (fixed_profile, core_release, skeleton))
    out = Path(out).absolute()
    if any(path.is_junction() or path.is_symlink() for path in (out, *out.parents)):
        raise ValueError("Output ancestry must use real directories")
    inputs = (fixed_profile, core_release, skeleton, *(
        path for path in (core_receipt, fixed_profile_receipt) if path is not None))
    out = safe_output(out, inputs)
    fixed_payload = fixed_profile.read_bytes()
    if common.pin(skeleton)["sha256"] != SKELETON_SHA256:
        raise ValueError("Expected the exact verified XP32 skeleton")
    fixed_pin = common.pin(Path(fixed_profile_receipt)) if fixed_profile_receipt is not None else None
    proof = read_json(fixed_profile_receipt) if fixed_pin is not None else None
    if fixed_pin is not None and not isinstance(proof, dict):
        raise ValueError("Expected the fixed-profile dispatch receipt object")
    fixed = read_fixed_profile(pack, fixed_payload, fixed_profile.name, proof)
    core, core_plans, core_pins = read_core_archive(pack, core_release, receipt_path=core_receipt, known_digest=CORE_SHA256)
    legacy = core_pins[str(core_release)] == CORE_SHA256
    configuration_inputs = pack.Inputs()
    rig, core_chains = pack._fsmp_core_chains(configuration_inputs)
    profile = Path(__file__).with_name('current-010.json')
    _, male_anatomy_hidden = require_reviewed_body(pack, core, core_plans, read_json(profile))
    sources = (Path(__file__), profile, PACKAGER, PACKAGER.with_name("build-unified-release.py"), CORE_INPUT_SOURCE,
               Path(sys.modules["core_archive"].__file__), ANATOMY_VISIBILITY_SOURCE,
               Path(fsmp_motion.__file__), Path(common.__file__), fsmp_motion.RIG_SOURCE,
               Path(fsmp_motion.head_split.__file__), Path(fsmp_motion.materials.__file__),
               Path(sys.modules["vr_dispatch"].__file__), Path(sys.modules["body_resource"].__file__))
    pins = [common.pin(path) for path in (fixed_profile, skeleton, *sources)]
    if fixed_pin is not None:
        pins.append(fixed_pin)
    for path, digest in core_pins.items():
        pin = common.pin(Path(path))
        if pin['sha256'] != digest:
            raise ValueError('Core archive or receipt changed after readback')
        pins.append(pin)
    config = ET.fromstring(fixed["fomod/ModuleConfig.xml"])
    static_plans = [plan for plan in core_plans if plan.get("physics") in {None, "none"}]
    motion_paths = {pack.MOTION_XML + sex.title() + ".xml" for sex in SEXES}
    motion_routes = [{row["path"]: row["source"] for row in plan["files"] if row["path"] in motion_paths}
                     for plan in core_plans if plan.get("physics") == "fsmp"]
    if not motion_routes or set(motion_routes[0]) != motion_paths or any(row != motion_routes[0] for row in motion_routes):
        raise ValueError("Core FSMP selections must share the same two motion XML routes")
    if any({row["path"] for row in plan["files"]} & (motion_paths | {LEGACY_ALIAS}) for plan in static_plans):
        raise ValueError("Core None selection conflicts with the world motion overlay")
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
        xml_payload = core[motion_routes[0][xml]]
        authored = fsmp_motion.render_xml(breast)
        expected = authored if legacy else pack._tail_only_fsmp_rig(authored, rig, core_chains[sex.title()])
        if xml_payload != expected:
            raise ValueError("Released FSMP motion XML differs from its authored rig")
        root = ET.fromstring(xml_payload)
        required = {bone.get("name") for bone in root.findall("bone")}
        if not required <= set(skel.nodes):
            raise ValueError("Pinned XP32 skeleton lacks a motion bone")
        drivers = tuple(link.get("bodyB") for link in root.findall("generic-constraint"))
        anatomy_edit = None
        if sex == "male" and male_anatomy_hidden:
            original, anatomy_edit = anatomy_visibility.hide_core_anatomy(original)
        overlay, binding = fsmp_motion.bind_nif(original, xml)
        staged[sex] = (source, xml, xml_payload, drivers, overlay, binding, anatomy_edit)

    out.mkdir(parents=True)
    report = {"schema": "claw-fixed-profile-vr-world-motion/1", "inputs": pins, "dependencies": dependencies,
              "coreVersion": core_version(core), "baseSelection": "None", "overlayDestination": LEGACY_ALIAS,
              "motionRig": "legacy-full" if legacy else "tail-only",
              "maleAnatomy": "hidden" if male_anatomy_hidden else "visible-legacy-diagnostic",
              "coreOffModelHashes": {dest: pack.sha(core[source]) for dest, source in core_off.items()},
              "requiredCoreStaticPlans": len(static_plans), "outputs": {},
              "installed": False, "gameValidated": False, "releaseReady": False}
    validated = {}
    with TemporaryDirectory(prefix="native-readback-", dir=out) as scratch:
        for sex, (source, xml, xml_payload, drivers, overlay, binding, anatomy_edit) in staged.items():
            path = Path(scratch) / f"{sex}.nif"
            path.write_bytes(overlay)
            nif = api.NifFile(str(path))
            hook = nif.root.get_extra_data(blockname="NiStringExtraData", name=fsmp_motion.HOOK)
            expected_tri = resource_paths(sex).removeprefix("Meshes/").replace("/", "\\").lower()
            if hook is None or hook.string_data != xml or any(bodytri(shape) != [("BODYTRI", expected_tri)] for shape in nif.shapes):
                raise ValueError("Native readback differs for FSMP hook or namespaced TRI")
            coverage = common.inspect_body(nif, drivers, "Fixed-profile " + sex)
            visible = {shape.name for shape in nif.shapes if visible_by_hidden_flags(shape)}
            if sex == "male" and ("genitals" not in nif.shape_dict or ("genitals" in visible) == male_anatomy_hidden):
                raise ValueError("Fixed male carrier does not preserve the reviewed anatomy visibility")
            members = {LEGACY_ALIAS: overlay, xml: xml_payload}
            visible_counts = {bone: sum(count for name, count in shapes.items() if name in visible)
                              for bone, shapes in coverage.items()}
            moving = (common.source.NODES[4:] + (common.source.BREAST_NODES if sex == "female" else ())) if legacy else drivers
            if any(not visible_counts[bone] for bone in moving):
                raise ValueError("Missing visible influence for an expected motion driver")
            validated[sex] = members
            report["outputs"][sex] = {"fromAliasMember": source,
                                       "members": {name: pack.sha(data) for name, data in members.items()},
                                       "requiredTri": {"path": resource_paths(sex),
                                                       "sha256": pack.sha(fixed["shared/" + resource_paths(sex)])},
                                       "binding": binding, "anatomyFlagEdit": anatomy_edit, "driverVertices": coverage,
                                       "visibleDriverVertices": visible_counts}
    configuration_inputs.verify()
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
    parser.add_argument('--fixed-profile-receipt', type=Path, help='Read a freshly built fixed-profile ZIP through its dispatch receipt')
    try:
        report = build(**vars(parser.parse_args(argv)))
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print(f"CLAW VR world motion: {error}", file=sys.stderr)
        return 2
    print("World-motion overlays: " + ", ".join(report["outputs"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
