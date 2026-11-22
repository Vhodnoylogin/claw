"""Derive the nonshipping coat fixture meshes from the retained female SE subject."""

import argparse
import json
from pathlib import Path
import shutil
import struct
import sys

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / 'src/main/python/build-tools'))
from breast_rig import load_pynifly, safe_output, sha256
from head_split import Nif


SOURCE_NIF = '6638401ebc43a7d0a0c7d9aa227090d6ea84981c3c116c678c6037845089d961'
SOURCE_TRI = '34744d5599531026f53a36e5438b39be3f880cd2cb7d9a0056b00bf343d05192'
PYNIFLY_DLL = '21d34ab298e6d7ab5faf5659c6e8b15355c421627c4a92def60509859e908b13'
MESH_DIR = Path('Meshes/claw/test/coat-turnover')
DONOR_TRI = r'actors\werewolfbeast\character assets\femalebodywerewolf.tri'
FIXTURE_TRI = r'claw\test\coat-turnover\coat-wolf.tri'
BODY, HEAD, TAIL = 32, 30, 40


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def root_children(nif):
    root = nif.blocks[0]
    require(nif.kind(0) == 'NiNode', 'Unexpected scene root type')
    offset = 72 + 4 * struct.unpack_from('<I', root, 4)[0]
    count, = struct.unpack_from('<I', root, offset)
    end = offset + 4 + 4 * count
    require(root[end:] == b'\x00' * 4, 'Unexpected scene root children/effects')
    children = struct.unpack_from(f'<{count}I', root, offset + 4)
    require(len(set(children)) == count, 'Duplicate scene root child')
    return root, offset, children


def skin_links(nif, shape):
    block = nif.blocks[shape.id]
    extras, = struct.unpack_from('<I', block, 4)
    require(nif.kind(shape.id) == 'BSTriShape' and len(block) == 120 + 4 * extras,
            f'Unsupported shape layout: {shape.name}')
    index, = struct.unpack_from('<I', block, 88 + 4 * extras)
    require(nif.kind(index) == 'BSDismemberSkinInstance', f'Missing skin instance: {shape.name}')
    data, partition, skeleton, bones = struct.unpack_from('<IIII', nif.blocks[index])
    require(skeleton == 0 and nif.kind(data) == 'NiSkinData' and nif.kind(partition) == 'NiSkinPartition',
            f'Unexpected skin references: {shape.name}')
    return index, data, partition, 16 + 4 * bones


def make_variant(source, inventory, names, slot):
    nif = Nif(source)
    root, offset, children = root_children(nif)
    excluded = {shape.id for name, shape in inventory.items() if name not in names}
    attached = [index for index in children if index not in excluded]
    nif.blocks[0] = root[:offset] + struct.pack(f'<I{len(attached)}I', len(attached), *attached) + b'\x00' * 4
    tri = nif.strings.index(DONOR_TRI.encode())
    nif.strings[tri] = FIXTURE_TRI.encode()

    for name in names:
        shape = inventory[name]
        instance, _, _, start = skin_links(nif, shape)
        block = bytearray(nif.blocks[instance])
        partitions = [(part.flags, part.id) for part in shape.partitions]
        expected = struct.pack(f'<I{2 * len(partitions)}H', len(partitions), *(v for pair in partitions for v in pair))
        require(partitions and all(part == BODY for _, part in partitions) and block[start:] == expected,
                f'Unreviewed partition header: {name}')
        for index in range(len(partitions)):
            struct.pack_into('<H', block, start + 6 + 4 * index, slot)
        nif.blocks[instance] = bytes(block)
    return nif.bytes()


def keep_packed_skin(api, source, inventory, pruned):
    # Nifly can rewrite float weight lanes while saving, even when their
    # effective half weights are unchanged. These blocks have no NIF block
    # references. Copy their original bytes back after IDs have been compacted.
    nif = Nif(pruned.read_bytes())
    for actual in api.NifFile(str(pruned)).shapes:
        old = inventory[actual.name.casefold()]
        _, old_data, old_partition, _ = skin_links(source, old)
        _, new_data, new_partition, _ = skin_links(nif, actual)
        nif.blocks[new_data] = source.blocks[old_data]
        nif.blocks[new_partition] = source.blocks[old_partition]
    return nif.bytes()


def material(shape):
    source = shape.shader.properties
    properties = type(source).from_buffer_copy(bytes(source))
    properties.textureSetID = 0  # File-local reference can be renumbered by pruning.
    alpha = bytes(shape.alpha_property.properties) if shape.alpha_property else None
    return shape.shader_block_name, bytes(properties), shape.textures, alpha


def readback(source, source_nif, native, output, names, slot):
    nif = Nif(output.read_bytes())
    shapes = {shape.name.casefold(): shape for shape in native.shapes}
    require(len(shapes) == len(native.shapes) and shapes.keys() == names, 'Unexpected retained or duplicate shape')
    _, _, children = root_children(nif)
    require({shape.id for shape in shapes.values()} <= set(children), 'Retained shape is not attached to the scene root')

    for name, actual in shapes.items():
        old = source[name]
        _, old_data, old_partition, _ = skin_links(source_nif, old)
        _, new_data, new_partition, _ = skin_links(nif, actual)
        bodytri = [(e.name, e.string_data) for e in actual.extra_data('NiStringExtraData') if e.name == 'BODYTRI']
        require(actual.parent is not None and actual.parent.id == 0 and old.verts == actual.verts
                and old.tris == actual.tris and old.uvs == actual.uvs and old.normals == actual.normals
                and old.colors == actual.colors and old.flags == actual.flags and old.bone_names == actual.bone_names
                and bytes(old.transform) == bytes(actual.transform) and old.has_global_to_skin == actual.has_global_to_skin
                and bytes(old.global_to_skin) == bytes(actual.global_to_skin)
                and material(old) == material(actual) and bodytri == [('BODYTRI', FIXTURE_TRI)],
                f'Geometry, transforms, flags, material or morph path changed: {name}')
        require(source_nif.blocks[old_data] == nif.blocks[new_data]
                and source_nif.blocks[old_partition] == nif.blocks[new_partition],
                f'Packed skin weights, transforms or partition topology changed: {name}')
        require([(part.flags, part.id) for part in actual.partitions] == [(part.flags, slot) for part in old.partitions],
                f'Body slot or visibility flags differ: {name}')
    return {'shapes': sorted(shapes), 'slot': slot, 'blocks': len(nif.blocks), 'sha256': sha256(output)}


def build(donor, tri, pynifly, output):
    require(sha256(donor) == SOURCE_NIF and sha256(tri) == SOURCE_TRI, 'Use the pinned female coat NIF and TRI')
    require(sha256(Path(pynifly) / 'NiflyDLL.dll') == PYNIFLY_DLL, 'Use the pinned PyNifly DLL')
    fresh = safe_output(output, [donor, tri])
    api, trip_file, dependency = load_pynifly(pynifly)
    source = donor.read_bytes()
    source_nif = Nif(source)
    native = api.NifFile(str(donor))
    names = {shape.name.casefold(): shape for shape in native.shapes}
    _, _, children = root_children(source_nif)
    trip_names = {name.casefold() for name in trip_file.from_filepath(str(tri)).shapes}
    require(source_nif.bytes() == source and len(names) == len(native.shapes) == 15
            and {'body', 'head'} <= names.keys() and trip_names == names.keys()
            and {shape.id for shape in names.values()} <= set(children)
            and all(shape.parent is not None and shape.parent.id == 0 for shape in names.values()),
            'The pinned donor must have fifteen direct, TRI-addressable shapes')

    target = fresh / 'Data' / MESH_DIR
    target.mkdir(parents=True)
    scratch = fresh / 'intermediate'
    scratch.mkdir()
    reports = {}
    for members, slot, variants in (
        ({'body'}, BODY, ('body-a.nif', 'body-b.nif')),
        ({'head'}, HEAD, ('head-a.nif', 'head-b.nif')),
        (names.keys() - {'body', 'head'}, TAIL, ('rest.nif',)),
    ):
        # Save through Nifly to prune unreferenced serialized blocks. Reattach
        # the original packed skin buffers and verify the final readback.
        draft = scratch / variants[0]
        draft.write_bytes(make_variant(source, names, members, slot))
        pruned = api.NifFile(str(draft))
        compacted = scratch / ('pruned-' + variants[0])
        pruned.filepath = str(compacted)
        pruned.save()
        first = target / variants[0]
        first.write_bytes(keep_packed_skin(api, source_nif, names, compacted))
        for name in variants:
            current = target / name
            if current != first:
                shutil.copyfile(first, current)
            reports[name] = readback(names, source_nif, api.NifFile(str(current)), current, members, slot)
    fixture_tri = target / 'coat-wolf.tri'
    shutil.copyfile(tri, fixture_tri)
    require(sha256(fixture_tri) == SOURCE_TRI, 'Fixture TRI differs from its donor')
    report = {'scope': 'offline fixture meshes', 'gameVerified': False,
              'sourceNif': {'path': donor.resolve().as_posix(), 'sha256': SOURCE_NIF},
              'sourceTri': {'path': tri.resolve().as_posix(), 'sha256': SOURCE_TRI},
              'pynifly': {'path': dependency.resolve().as_posix(), 'dllSha256': PYNIFLY_DLL},
              'meshDirectory': MESH_DIR.as_posix(), 'variants': reports, 'fixtureTriSha256': SOURCE_TRI}
    (fresh / 'mesh-verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for parameter in ('donor', 'tri', 'pynifly', 'output'):
        parser.add_argument(f'--{parameter}', required=True, type=Path)
    print(json.dumps(build(**vars(parser.parse_args())), indent=2))
