"""Stage four exact mesh-identity controls for the optional VR world-motion overlays."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src/main/components/vr-body"))
from vr_dispatch import ADDON, LEGACY_ALIAS, SEXES, resource_paths
import world_motion as motion
from body_resource import safe_output
from head_isolation import node_children

Nif = motion.fsmp_motion.Nif
MARKERS = {
    ("male", "static"): "H_M_STATIC",
    ("female", "static"): "H_F_STATIC",
    ("male", "fsmp"): "H_M_FSMP",
    ("female", "fsmp"): "H_F_FSMP",
}
PLAYER_ARMOR_MARKERS = {"male": "P_M", "female": "P_F"}
MOTION_ZIPS = {
    "male": "d4f2313413a078d914fc06238d5525de70eda07c4e4be8ec6a6d47a02d6d1ca2",
    "female": "b2597f9d0204d7f53db21e73c69d472fd1ab0fa481ddc87cd92dc011c58c15f1",
}


def add_marker(payload, token):
    """Append only one empty NiNode; preserve skin data and any existing root hook."""
    if token not in MARKERS.values() and token not in PLAYER_ARMOR_MARKERS.values():
        raise ValueError("Unsupported dispatch marker token")
    name = "CLAW_VR_DISPATCH_PROBE_" + token
    nif = Nif(payload)
    if nif.kind(0) != "NiNode" or nif.bytes() != payload:
        raise ValueError("Expected the reversible NiNode scene container")
    if any(value.startswith(b"CLAW_VR_DISPATCH_PROBE_") for value in nif.strings):
        raise ValueError("The input already contains a dispatch marker")
    original_root = nif.blocks[0]
    offset, old_children = node_children(original_root)
    identity = (0., 0., 0., 1., 0., 0., 0., 1., 0., 0., 0., 1., 1.)
    marker = struct.pack("<4I13f3I", nif.name(name), 0, 0xFFFFFFFF, 14, *identity, 0xFFFFFFFF, 0, 0)
    marker_id = nif.append("NiNode", marker)
    end = offset + 4 + len(old_children) * 4
    nif.blocks[0] = (original_root[:offset] + struct.pack("<I", len(old_children) + 1)
                     + original_root[offset + 4:end] + struct.pack("<I", marker_id) + original_root[end:])
    result = nif.bytes()
    actual = Nif(result)
    if actual.blocks != nif.blocks or actual.strings != nif.strings or actual.footer != nif.footer:
        raise ValueError("Marker placement did not round-trip")
    return result


def build(fixed_profile, motion_dir, witness, pynifly, out):
    common = motion.fsmp_motion.common
    packaging_source = ROOT / "src/main/python/build-tools/package-source-build.py"
    fixed_profile, motion_dir, witness = (Path(p).resolve(strict=True) for p in (fixed_profile, motion_dir, witness))
    proof_path = witness / "WITNESS-BUILD.json"
    witness_binaries = {
        "dll": "SKSE/Plugins/CLAWVRModelTopology.dll",
        "pex": "Scripts/CLAWVRModelTopology.pex",
    }
    overlay_paths = {sex: motion_dir / f"test_CLAW VR World Motion - {sex.capitalize()}.zip" for sex in SEXES}
    inputs = [fixed_profile, proof_path, *overlay_paths.values(),
              *(witness / Path(path).name for path in witness_binaries.values())]
    out = Path(out).absolute()
    if any(path.is_junction() or path.is_symlink() for path in (out, *out.parents)):
        raise ValueError("Output ancestry must use real directories")
    out = safe_output(out, inputs)
    sources = [Path(__file__), packaging_source, Path(motion.__file__),
               Path(motion.fsmp_motion.__file__), motion.fsmp_motion.RIG_SOURCE,
               Path(sys.modules["vr_dispatch"].__file__), Path(sys.modules["head_isolation"].__file__)]
    dependencies = [common.pin(path) for path in [*inputs, *sources]]
    hashes = {Path(entry["path"]): entry["sha256"] for entry in dependencies}
    pack = motion.open_tools(packaging_source)

    def read_pinned(path):
        data = path.read_bytes()
        if pack.sha(data) != hashes[path]:
            raise ValueError("Fixture input changed while staging: " + str(path))
        return data

    fixed_zip = read_pinned(fixed_profile)
    if pack.sha(fixed_zip) != motion.FIXED_SHA256:
        raise ValueError("Expected the exact fixed-profile archive")
    fixed = pack.read_zip(fixed_zip)
    config = ET.fromstring(fixed["fomod/ModuleConfig.xml"])
    expected = {ADDON, *(resource_paths(sex, index) for sex in SEXES for index in (0, 1, None))}
    required = config.findall("requiredInstallFiles/file")
    if {row.attrib["destination"] for row in required} != expected or len(required) != len(expected):
        raise ValueError("Unexpected shared fixed-profile resource inventory")
    shared = {row.attrib["destination"]: fixed[row.attrib["source"]] for row in required}

    proof = json.loads(read_pinned(proof_path))
    if proof.get("schema") != "claw-vr-model-topology-6-offline-build/1":
        raise ValueError("Expected rebuilt capture /6 witness")
    for role, filename in witness_binaries.items():
        data = read_pinned(witness / Path(filename).name)
        if pack.sha(data) != proof[role]["sha256"]:
            raise ValueError("Witness binary differs from its build receipt")
        shared[filename] = data

    arms = {}
    for sex, path in overlay_paths.items():
        payload = read_pinned(path)
        if pack.sha(payload) != MOTION_ZIPS[sex]:
            raise ValueError("Expected the exact fixed-profile FSMP overlay")
        overlay = pack.read_zip(payload)
        source = fixed[motion.alias_member(config, fixed, sex)]
        xml = pack.MOTION_XML + sex.title() + ".xml"
        exact = motion.fsmp_motion.render_xml(sex == "female")
        expected_mesh, _ = motion.fsmp_motion.bind_nif(source, xml)
        if overlay != {LEGACY_ALIAS: expected_mesh, xml: exact}:
            raise ValueError("Overlay differs from its static input plus one exact FSMP binding")
        arms[sex, "static"] = {LEGACY_ALIAS: add_marker(source, MARKERS[sex, "static"])}
        arms[sex, "fsmp"] = {LEGACY_ALIAS: add_marker(expected_mesh, MARKERS[sex, "fsmp"]), xml: exact}

    api, reader_pins = common.load_pynifly(Path(pynifly))

    def write_members(folder, assets):
        paths = {}
        for path, data in sorted(assets.items()):
            target = folder / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            if target.read_bytes() != data:
                raise ValueError("Detached staging readback differs: " + path)
            paths[path] = common.pin(target)
        return paths

    report = {"schema": "claw-vr-world-motion-marker-arms/1", "common": write_members(out/"common/Data", shared),
              "arms": {}, "inputs": dependencies, "reader": reader_pins,
              "observation": {"script": "CLAWVRModelTopology", "capture": "CaptureDispatch",
                              "schema": "claw-vr-model-topology/6", "requiredView": "thirdPerson",
                              "requiredBank": "active"},
              "corePhysicsSelection": "None", "installed": False, "gameStarted": False,
              "runtimeQualified": False, "singleLiveSystemVerified": False}
    for (sex, mode), members in arms.items():
        token = MARKERS[sex, mode]
        files = write_members(out/f"{sex}-{mode}/Data", members)
        nif = api.NifFile(files[LEGACY_ALIAS]["path"])
        marker = nif.nodes.get("CLAW_VR_DISPATCH_PROBE_" + token)
        binding = nif.root.get_extra_data(blockname="NiStringExtraData", name=motion.fsmp_motion.HOOK)
        xml = pack.MOTION_XML + sex.title() + ".xml"
        if (marker is None or marker.parent is None or marker.parent.id != nif.root.id
                or (binding.string_data if binding is not None else None) != (xml if mode == "fsmp" else None)):
            raise ValueError("Native marker/FSMP hook readback differs from the selected arm")
        report["arms"][f"{sex}-{mode}"] = {"expectedMarker": token, "files": files}
    common.unchanged([*dependencies, *reader_pins])
    (out/"staging.json").write_bytes(pack.encoded(report))
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("fixed-profile", "motion-dir", "witness", "pynifly", "out"):
        parser.add_argument("--"+name, type=Path, required=True)
    try:
        report = build(**vars(parser.parse_args()))
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print(f"CLAW VR world-motion marker fixture: {error}", file=sys.stderr)
        return 2
    print("Staged " + ", ".join(report["arms"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
