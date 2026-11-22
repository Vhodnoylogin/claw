"""Build a three-vertex breast-fur attachment trial from the exact CLAW 0.10.0 FSMP carrier."""
from __future__ import annotations

import argparse
import importlib.util
from hashlib import sha256
from pathlib import Path
import struct
import sys
import xml.etree.ElementTree as ET

import numpy as np

TOOLS = Path(__file__).resolve().parents[1] / "build-tools"
sys.path.insert(0, str(TOOLS))
from head_split import Nif, Partition, Reader

RELEASE_SHA256 = "f571ad5e486600c3fcd06432034eeed9a2837be2706ca59bc0f72be28262c91a"
CARRIER_SHA256 = "e5a9d6b5572dfeb101afe149e79cf1961f73614ce108b23f98b4237c3a2e1212"
TRANSFERS = {578: 0.0281982421875, 581: 0.0284423828125, 582: 0.0284423828125}
P1_BONES = (b"NPC L Breast P1", b"NPC R Breast P1")
FIELDS = {2: struct.Struct("<4e"), 4: struct.Struct("<4f")}


def move_pair(weight_bytes, index_bytes, left, right, shift):
    """Fill the spare slot without touching any foreign influence or changing the row sum."""
    encoding = FIELDS[len(weight_bytes) // 4]
    weights = list(encoding.unpack(weight_bytes))
    indices = list(index_bytes)
    active = [index for weight, index in zip(weights, indices, strict=True) if weight > 0]
    if len(active) != 3 or len(set(active)) != 3 or left not in active or right in active:
        raise ValueError("Expected the original three influences and one spare slot")
    old_slot, new_slot = indices.index(left), weights.index(0)
    original = weights[old_slot]
    if not 0 < shift < original:
        raise ValueError("Weight transfer does not fit its source influence")
    weights[old_slot], weights[new_slot] = original - shift, shift
    indices[new_slot] = right
    packed = encoding.pack(*weights)
    moved = encoding.unpack(packed)
    if moved[old_slot] + moved[new_slot] != original:
        raise ValueError("Packed P1 sum is no longer exact")
    return packed, bytes(indices), (original, moved[old_slot], moved[new_slot])


def patch_skin_data(payload, left, right, transfers):
    """Update the matching float weights while preserving every other stored entry and bind."""
    reader = Reader(payload)
    frame = reader.take(52)
    count, has_weights = reader.unpack("<IB")
    if has_weights != 1 or not 0 <= left < right < count:
        raise ValueError("Unexpected skin weight layout")
    output = [frame, struct.pack("<IB", count, has_weights)]
    for bone in range(count):
        output.append(reader.take(68))
        size, = reader.unpack("<H")
        if bone not in (left, right):
            output.extend([struct.pack("<H", size), reader.take(size * 6)])
            continue
        records = {}
        for _ in range(size):
            row = reader.take(6)
            vertex, = struct.unpack_from("<H", row)
            if vertex in records:
                raise ValueError("Duplicate skin weight vertex")
            records[vertex] = row
        if bone == right and list(records) != sorted(records):
            raise ValueError("Original right P1 weights require ascending vertex order")
        for vertex, (before, after_l, after_r) in transfers.items():
            if bone == left:
                if records.get(vertex) != struct.pack("<Hf", vertex, before):
                    raise ValueError("Partition float weights disagree with skin data")
                records[vertex] = struct.pack("<Hf", vertex, after_l)
            else:
                if vertex in records:
                    raise ValueError("Unexpected stored right P1 influence")
                records[vertex] = struct.pack("<Hf", vertex, after_r)
        output.append(struct.pack("<H", len(records)))
        output.extend(records.values() if bone == left else (records[v] for v in sorted(records)))
    reader.done()
    return b"".join(output)


def patch_carrier(payload):
    if sha256(payload).hexdigest() != CARRIER_SHA256:
        raise ValueError("Only the reviewed final 0.10.0 female FSMP carrier is supported")
    nif = Nif(payload)
    if nif.bytes() != payload:
        raise ValueError("Unsupported NIF round trip")
    shape_id, skin_id, data_id, partition_id = 113, 115, 116, 117
    if tuple(nif.kind(i) for i in (shape_id, skin_id, data_id, partition_id)) != (
            "BSTriShape", "BSDismemberSkinInstance", "NiSkinData", "NiSkinPartition"):
        raise ValueError("Unexpected fur skin block layout")
    shape = nif.blocks[shape_id]
    name, extras = struct.unpack_from("<II", shape)
    instance = nif.blocks[skin_id]
    if (nif.strings[name] != b"fur_belly" or struct.unpack_from("<I", shape, 88 + 4 * extras)[0] != skin_id
            or struct.unpack_from("<II", instance) != (data_id, partition_id)):
        raise ValueError("Carrier is missing the reviewed belly skin references")
    left, right = 14, 15
    for bone, expected in zip((left, right), P1_BONES, strict=True):
        node, = struct.unpack_from("<I", instance, 16 + 4 * bone)
        name, = struct.unpack_from("<I", nif.blocks[node])
        if nif.strings[name] != expected:
            raise ValueError("Carrier P1 bone order differs")
    old_data, old_partition = nif.blocks[data_id], nif.blocks[partition_id]
    partition = Partition(old_partition)
    palette = tuple(v for (v,) in struct.iter_unpack("<H", partition.bones))
    left_index, right_index = palette.index(left), palette.index(right)
    verts = np.arange(len(partition.vertices))
    faces = np.arange(len(partition.triangles))
    if partition.subset(verts, faces) != old_partition:
        raise ValueError("Unsupported skin partition round trip")

    transfers = {}
    for vertex, shift in TRANSFERS.items():
        packed = partition.vertices[vertex]
        weights, indices, _ = move_pair(packed[28:36].tobytes(), packed[36:40].tobytes(), left_index, right_index, shift)
        packed[28:40] = np.frombuffer(weights + indices, dtype=np.uint8)
        weights, indices, transfers[vertex] = move_pair(
            partition.weights[vertex].tobytes(), partition.indices[vertex].tobytes(), left_index, right_index, shift)
        partition.weights[vertex] = np.frombuffer(weights, dtype=np.uint8)
        partition.indices[vertex] = np.frombuffer(indices, dtype=np.uint8)
    original_blocks = nif.blocks.copy()
    nif.blocks[data_id] = patch_skin_data(old_data, left, right, transfers)
    nif.blocks[partition_id] = partition.subset(verts, faces)
    updated = nif.bytes()
    reopened = Nif(updated)
    changes = [i for i, (a, b) in enumerate(zip(original_blocks, reopened.blocks, strict=True)) if a != b]
    if changes != [data_id, partition_id] or reopened.blocks != nif.blocks or reopened.bytes() != updated:
        raise ValueError("Unauthorized block changes during serialization")
    return updated


def load_tool(name, source):
    spec = importlib.util.spec_from_file_location(name, source)
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


def build(release, out):
    pack_path, reader_path = (TOOLS / name for name in ("package-source-build.py", "build-unified-release.py"))
    pack = load_tool("claw_attachment_package", pack_path)
    reader = load_tool("claw_attachment_fomod", reader_path)
    release = Path(release).resolve(strict=True)
    original_out = Path(out).absolute()
    if any(p.is_symlink() or p.is_junction() for p in (original_out, *original_out.parents)):
        raise ValueError("Output ancestry cannot contain links or junctions")
    out = reader.output_directory(original_out)
    if release.parent in out.parents:
        raise ValueError("Choose an output directory outside the original inputs")
    payload = release.read_bytes()
    if pack.sha(payload) != RELEASE_SHA256:
        raise ValueError("Expected the original final CLAW 0.10.0 archive")
    entries = pack.read_zip(payload)
    config = ET.fromstring(entries["fomod/ModuleConfig.xml"])
    selected = reader.resolve_selection(config, entries, native=True, male_family="Vanilla",
                                        family="Vanilla", obody=False, physics="fsmp")
    for item in config.findall("requiredInstallFiles/file"):
        name, source = item.attrib["destination"], item.attrib["source"]
        if name in selected or source not in entries:
            raise ValueError("Invalid required release route")
        selected[name] = source
    models = {f"{pack.MESH}/female{route}_{endpoint}.nif"
              for route in ("bodywerewolf", "PlayerWerewolf") for endpoint in (0, 1)}
    winner = f"40 Motion/FSMP/{pack.MESH}/femalebodywerewolf_0.nif"
    if {selected.get(name) for name in models} != {winner}:
        raise ValueError("The four reviewed female FSMP model routes must share the pinned carrier")
    trial = patch_carrier(entries[winner])
    outputs = dict.fromkeys(sorted(models), trial)
    zip_payload = pack.zip_bytes(outputs)
    archive = out / "test_CLAW FSMP Breast Attachment.zip"
    retained = [f"{pack.MESH}/femalebodywerewolf.tri", pack.MOTION_XML + "Female.xml"]
    receipt = {
        "schema": "claw-fsmp-breast-attachment-trial/1",
        "releaseSha256": pack.sha(payload),
        "carrierSha256": CARRIER_SHA256,
        "trialSha256": pack.sha(trial),
        "patch": {"shape": "fur_belly", "changedBlocks": [116, 117], "leftToRight": TRANSFERS},
        "archive": {"name": archive.name, "sha256": pack.sha(zip_payload), "members": sorted(outputs)},
        "requiresOriginal": {name: pack.sha(entries[selected[name]]) for name in retained},
        "sourceSha256": {file.name: pack.sha(file.read_bytes()) for file in
                         (Path(__file__), TOOLS / "head_split.py", pack_path, reader_path)},
        "installed": False, "gameValidated": False, "releaseReady": False,
    }
    out.mkdir(parents=True)
    archive.write_bytes(zip_payload)
    if pack.read_zip(archive.read_bytes()) != outputs:
        raise ValueError("Written trial archive failed readback")
    (out / "trial.json").write_bytes(pack.encoded(receipt))
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = build(args.release, args.out)
    except (OSError, ValueError, KeyError, struct.error) as error:
        print(f"CLAW breast attachment trial: {error}", file=sys.stderr)
        return 2
    print(result["trialSha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
