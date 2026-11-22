"""Author and verify one original skinned FSMP contact probe outside the game."""

import argparse
import importlib.util
import json
from pathlib import Path
import struct
import xml.etree.ElementTree as ET


REPO = Path(__file__).resolve().parents[4]
SOURCE = REPO / "src/main/components/adult-anatomy/python/collision_candidate.py"
spec = importlib.util.spec_from_file_location("claw_anatomy_collision", SOURCE)
collision = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collision)
require = collision.require

SHAPE = "CLAWAnatomyContactProbe"
BONE = "NPC Pelvis [Pelv]"
SLOT = 35
MARGIN = 1.0
MESH = Path("meshes/claw/test/anatomy-contact/probe.nif")
CONFIG = Path("SKSE/Plugins/hdtSkinnedMeshConfigs/CLAW/CLAWAnatomyContactProbe.xml")
CONTROL = CONFIG.with_name(CONFIG.stem + "NoContact.xml")
PLUGIN = "test_CLAW - FSMP Contact Peer.esp"
HOOK_PATH = str(CONFIG).replace("/", "\\")
VERTICES = (
    (.0625, .0625, .0625), (-.0625, -.0625, .0625),
    (-.0625, .0625, -.0625), (.0625, -.0625, -.0625),
)
TRIANGLES = ((0, 1, 2), (0, 3, 1), (0, 2, 3), (1, 3, 2))


def peer_xml():
    root = ET.Element("system")
    bone = ET.SubElement(root, "bone", {"name": BONE})
    ET.SubElement(bone, "mass").text = "0"
    shape = ET.SubElement(root, "per-vertex-shape", {"name": SHAPE})
    for tag, value in (
        ("margin", str(MARGIN)), ("shared", "external"), ("tag", collision.PEER_TAG),
        ("can-collide-with-tag", collision.SURFACE_TAG),
    ):
        ET.SubElement(shape, tag).text = value
    collision.validate_peer_shape(ET.tostring(shape))
    ET.indent(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def write_mesh(api, path):
    nif = api.NifFile()
    nif.initialize("SKYRIMSE", str(path))
    identity = api.TransformBuf()
    identity.set_identity()
    shape = nif.createShapeFromData(
        SHAPE, VERTICES, TRIANGLES, ((0, 0), (1, 0), (0, 1), (1, 1)), ((0, 0, 1),) * len(VERTICES)
    )
    shape.skin()
    shape.add_bone(BONE, identity)
    shape.set_global_to_skin(identity)
    shape.set_skin_to_bone_xform(BONE, identity)
    shape.setShapeWeights(BONE, [(index, 1.0) for index in range(len(VERTICES))])
    shape.set_partitions([api.SkyPartition(part_id=SLOT, namedict=nif.dict)], [SLOT] * len(TRIANGLES))
    api.NiStringExtraData.New(nif, name=collision.HOOK, string_value=HOOK_PATH, parent=nif.root)
    nif.save()


def verify_packed_mesh(path, shape_id, root_id):
    _, types, indices, blocks, _, strings = collision._parts(path.read_bytes())
    root = blocks[root_id]
    extra_count, hook_id = struct.unpack_from("<II", root, 4)
    require(extra_count == 1 and types[indices[hook_id]] == "NiStringExtraData", "Expected one root hook")
    hook_name, hook_value = struct.unpack("<II", blocks[hook_id])
    require((strings[hook_name].decode(), strings[hook_value].decode()) == (collision.HOOK, HOOK_PATH),
            "Root hook differs")

    raw = blocks[shape_id]
    require(types[indices[shape_id]] == "BSTriShape" and struct.unpack_from("<I", raw, 4) == (0,),
            "Expected a single plain skinned BSTriShape")
    instance, = struct.unpack_from("<I", raw, 88)
    skin_data, partition, _, bones, bone_id = struct.unpack_from("<5I", blocks[instance])
    require([types[indices[i]] for i in (instance, skin_data, partition)]
            == ["BSDismemberSkinInstance", "NiSkinData", "NiSkinPartition"], "Native skin blocks differ")
    bone_name, = struct.unpack_from("<I", blocks[bone_id])
    require(bones == 1 and strings[bone_name].decode() == BONE, "Packed skin palette differs")

    # This descriptor is the writer's SSE format for positions, UV, normals,
    # tangents and skin. FSMP reaches its 4 half weights after 28 bytes.
    packed = blocks[partition]
    expected_format = (1, 40 * len(VERTICES), 40, 0x5B0007065040A)
    require(struct.unpack_from("<IIIQ", packed) == expected_format, "Probe packed vertex format differs")
    for index, vertex in enumerate(VERTICES):
        offset = 20 + index * 40
        require(struct.unpack_from("<3f", packed, offset) == vertex
                and struct.unpack_from("<4e4B", packed, offset + 28) == (1., 0., 0., 0., 0, 0, 0, 0),
                "Packed probe position or weight differs")
    counts = struct.unpack_from("<5H", packed, 20 + 40 * len(VERTICES))
    require(counts == (len(VERTICES), len(TRIANGLES), 1, 0, 4), "Probe partition header differs")


def verify_mesh(api, path):
    nif = api.NifFile(str(path))
    require(len(nif.shapes) == 1, "Expected one skinned probe shape")
    shape, = nif.shapes
    require(shape.name == SHAPE and not shape.flags & 1 and tuple(shape.verts) == VERTICES
            and tuple(shape.tris) == TRIANGLES and shape.bone_names == [BONE]
            and shape.bone_weights == {BONE: [(index, 1.) for index in range(len(VERTICES))]}
            and [partition.id for partition in shape.partitions] == [SLOT], "Native peer mesh differs")
    identity = api.TransformBuf()
    identity.set_identity()
    bind = shape.get_shape_skin_to_bone(BONE)
    require(bind is not None and bytes(bind) == bytes(identity), "Peer vertices must be local to the controlled bone")
    verify_packed_mesh(path, shape.id, nif.root.id)


def verify_plugin(data):
    reader_source = REPO / "src/test/resources/inspection/lighting/build_lighting.py"
    reader_spec = importlib.util.spec_from_file_location("claw_test_plugin_records", reader_source)
    reader = importlib.util.module_from_spec(reader_spec)
    reader_spec.loader.exec_module(reader)
    records = list(reader.records(data))
    require(sorted(kind for kind, *_ in records) == [b"ARMA", b"ARMO", b"TES4"],
            "Plugin must contain only the test armor, addon and header")
    header, armor, addon = ({row[0]: row for row in records}[kind] for kind in (b"TES4", b"ARMO", b"ARMA"))

    def fields(row, form, allowed):
        kind, actual_form, flags, payload, _, groups = row
        require((actual_form, flags) == (form, 0), "Fixture form or flags differ")
        require(len(groups) == bool(form) and (not groups or groups[0][8:12] == kind),
                "Fixture group differs")
        pairs = list(reader.subs(payload))
        values = dict(pairs)
        require(len(pairs) == len(values) and set(values) == set(allowed), "Fixture record fields differ")
        return values

    header_fields = fields(header, 0, (b"HEDR", b"CNAM", b"SNAM", b"MAST", b"DATA"))
    require(header_fields[b"MAST"] == b"Skyrim.esm\0", "Fixture master differs")
    item = fields(armor, 0x01000801, (b"EDID", b"OBND", b"FULL", b"BODT", b"RNAM", b"MODL", b"DATA", b"DNAM"))
    model = fields(addon, 0x01000800, (b"EDID", b"BODT", b"RNAM", b"DNAM", b"MOD2", b"MOD3"))
    slot_mask = 1 << (SLOT - 30)
    model_path = MESH.relative_to("meshes").as_posix().replace("/", "\\").encode() + b"\0"
    require(item[b"EDID"] == b"CLAWTestFSMPContactPeer\0"
            and model[b"EDID"] == b"CLAWTestFSMPContactPeerAddon\0"
            and item[b"MODL"] == struct.pack("<I", 0x01000800)
            and item[b"RNAM"] == model[b"RNAM"] == struct.pack("<I", 0x013746)
            and item[b"BODT"] == model[b"BODT"] == struct.pack("<III", slot_mask, 0, 2)
            and model[b"MOD2"] == model[b"MOD3"] == model_path
            and model[b"DNAM"] == bytes.fromhex("000000000000001700000000"),
            "Test armor slot, model, race or weight selection differs")
    return {"armorLocalFormId": "000801", "addonLocalFormId": "000800", "race": "NordRace",
            "singleSkyrimMaster": True, "gameRecordOverrides": 0, "weightSlider": False}


def build(pynifly, morphbench, esp, out):
    esp_bytes = esp.read_bytes()
    require(esp.name == PLUGIN, "Unexpected test plugin name")
    armor = verify_plugin(esp_bytes)
    api, patch, _, dependencies = collision._resource.dependencies(pynifly, morphbench)
    output = collision._resource.safe_output(out, [SOURCE, Path(__file__), esp, *dependencies])
    output.mkdir()
    mesh = output / "payload" / MESH
    mesh.parent.mkdir(parents=True)
    xml = output / "payload" / CONFIG
    xml.parent.mkdir(parents=True)
    configuration = peer_xml()
    xml.write_bytes(configuration)
    control = configuration.replace(collision.PEER_TAG.encode(), b"CLAW.NeutralAnatomy.Control.v1")
    require(configuration.count(collision.PEER_TAG.encode()) == 1, "Control must replace only the reciprocal tag")
    (output / "payload" / CONTROL).write_bytes(control)
    (output / "payload" / PLUGIN).write_bytes(esp_bytes)
    write_mesh(api, mesh)
    verify_mesh(api, mesh)
    require(patch(mesh).consistent() and xml.read_bytes() == configuration, "Peer file readback differs")
    report = {
        "status": "verified-offline-peer-mesh-and-policy", "mesh": MESH.as_posix(),
        "configuration": CONFIG.as_posix(), "tagMismatchControl": CONTROL.as_posix(),
        "shape": SHAPE, "skinBone": BONE, "slot": SLOT,
        "localPoints": VERTICES, "triangleCount": len(TRIANGLES), "probeMargin": MARGIN,
        "files": {path.as_posix(): collision.sha((output / "payload" / path).read_bytes())
                  for path in (MESH, CONFIG, CONTROL, Path(PLUGIN))},
        "inputs": dependencies, "sourceSha256": collision.sha(Path(__file__).read_bytes()),
        "armor": armor, "distinctLiveSkeletonVerified": False, "contactQualified": False,
        "runtimeRequires": ["Place probe armor on a separate nearby controlled actor",
                            "Observe both provider systems with distinct actor/skeleton identities",
                            "Record separated, overlapping, and separated controls plus contact evidence"],
    }
    (output / "peer-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("pynifly", "morphbench", "esp", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    result = build(**vars(parser.parse_args()))
    print(result["status"])
