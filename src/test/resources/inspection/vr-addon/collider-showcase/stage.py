"""Build the fixed VR collider inspection fixture in a detached directory."""

from __future__ import annotations

import argparse
from collections import defaultdict
import importlib.util
import json
from pathlib import Path
import struct
import sys

import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
sys.path.insert(0, str(ROOT / 'src/main/python/physics'))
sys.path.insert(0, str(ROOT / 'src/main/python/vr'))
from body_resource import dependencies, safe_output, sha256
from contact_fit import evaluate, signed_capsules

FIXTURE = 'test_CLAW - VR CBPC Contact Fixture.esp'
PLUGIN = 'test_CLAW - VR Collider Showcase.esp'
RACE = 0xCDD84
BASE = 0x800
ADDON = 0x800
ARMOR = 0x801
SLOT = 60
MODEL = Path('meshes/claw/test/vr-collider-showcase/wires.nif')
TEXTURE = Path('textures/claw/test/vr-collider-showcase/base.dds')
CONFIG = Path('SKSE/Plugins')
WANDS = ('LeftWandNode', 'RightWandNode')
WAND = (0., -6., -2., 3.)
TUNING = 'CBPConfig_CLAWCBPCBench.txt'
ALIAS = 'CLAW_CBPCBenchTail'
SOURCE_CONFIGS = ('CBPCMasterConfig.txt', 'CBPCollisionConfig.txt',
                  'CBPCPlayerCollisionEventConfig.txt', TUNING)
FILE_HASHES = {
    'profile': 'd76db2c6a1b5d337db9a604a2ed1f20ebb285e63b535800f9a97da5395687403',
    'fixture': '2eef81e8f56022d2adba1991b80f038d06e5f9689fb666edf53b00d8ad314305',
    'template': 'c2bcb9de0396f0f6003e3de6e1b87f74bb5301607e7929e9d731baf757367975',
}
WEIGHT = 50.
SEGMENTS = 12
COLORS = {
    'ears': (1., .72, .14), 'muzzle and head': (.20, 1., .42), 'tail': (.72, .38, 1.),
    'chest and trunk': (.14, .78, 1.), 'arms and paws': (1., .38, .19),
    'legs and hind paws': (.94, .24, .70),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def pinned(path, digest):
    require(sha256(path) == digest, f'Unexpected input bytes: {path.name}')


def category(node):
    if 'Ear' in node:
        return 'ears'
    if 'Head' in node:
        return 'muzzle and head'
    if node.startswith('TailBone'):
        return 'tail'
    if any(part in node for part in ('Arm', 'Forearm', 'Hand')):
        return 'arms and paws'
    if any(part in node for part in ('Thigh', 'Calf', 'Foot')):
        return 'legs and hind paws'
    return 'chest and trunk'


def fitted_bank(profile):
    require(profile['frame'] == 'node-local-game-units', 'Wrong capsule coordinate frame')
    result = []
    regions = {}
    for index, slot in enumerate(profile['slots']):
        if slot['male'] is None:
            continue
        node = slot['node']
        require(node and node.strip() == node and all(c not in node for c in '\r\n=<>#,()\0'),
                'Unexpected CBPC node name')
        region = profile['regions'][f'male/{node}']
        if node not in regions:
            regions[node] = evaluate(region, {}, weight=WEIGHT / 100.)
        partition = slot['partition']
        require(region['partitions'][partition] == slot['male']['partitionIndices'], 'Slot support changed')
        fit = regions[node][partition]
        packed = np.asarray([*fit['p1'], *fit['p2'], fit['radius']], dtype=np.float32).tolist()
        require(np.isfinite(packed).all() and packed[6] > 0, 'Invalid fitted capsule')
        result.append({'slot': index, 'node': node, 'region': category(node),
                       'p1': packed[:3], 'p2': packed[3:6], 'radius': packed[6]})
    require((len(profile['slots']), len(result), len(regions)) == (128, 120, 25),
            'Expected the complete 120 active male capsules on 25 nodes')
    require({row['region'] for row in result} == set(COLORS), 'Every contact region is required')
    return result


def row_text(row):
    def endpoint(p):
        return ','.join(format(number, '.9g') for number in (*p, row['radius']))

    return endpoint(row['p1']) + ' & ' + endpoint(row['p2'])


def configs(bank, tuning):
    groups = defaultdict(list)
    for row in bank:
        groups[row['node']].append(row)
    condition = f'IsRaceFormId(Skyrim.esm|{RACE:06X}) AND IsMale() AND IsActorBase({FIXTURE}|{BASE:06X})'
    master = '[Settings]\nTuningMode=0\nMalePhysics=1\n\n[ConfigMap]\n'
    master += ''.join(f'{node}={ALIAS}={condition}\n' for node in groups)
    content = '[ExtraOptions]\nBellyBulge=0\nBellyBulgeMax=0\nVaginaOpeningMultiplier=0\nAnusOpeningMultiplier=0\n'
    content += '\n[PlayerNodes]\n' + '\n'.join(WANDS) + '\n'
    content += '\n[AffectedNodes]\n' + '\n'.join(groups) + '\n\n[ColliderNodes]\n'
    for node, rows in groups.items():
        content += f'\n[{node}]\n' + ''.join(row_text(row) + '\n' for row in rows)
    for wand in WANDS:
        content += f'\n[{wand}]\n' + ','.join(format(number, 'g') for number in WAND) + '\n'
    # Parse the actual strings using the same Float32 width as the provider.
    written = [tuple(np.asarray(line.replace(' & ', ',').split(','), dtype=np.float32))
               for line in content.splitlines() if ' & ' in line]
    expected = [tuple((*row['p1'], row['radius'], *row['p2'], row['radius']))
                for rows in groups.values() for row in rows]
    require(written == expected, 'Capsule serialization no longer round-trips to the shared bank')
    events = '[Settings]\nMinimumCollisionDuration=0.3\n\n[PlayerCollisionEventNodes]\n'
    return {name: text for name, text in zip(SOURCE_CONFIGS,
            (master, content, events + '\n'.join(WANDS) + '\n', tuning), strict=True)}


def wires(cap):
    """Draw rings and four longitudes on the exact Morphbench capsule mesh."""
    from morphbench.colliders import Capsule

    capsule = Capsule(cap['node'], cap['slot'], cap['p1'], cap['p2'], cap['radius'])
    mesh, _ = capsule.mesh(SEGMENTS)
    mesh = mesh.astype(float).reshape(-1, SEGMENTS, 3)
    require(np.max(np.abs(signed_capsules(mesh, [cap]))) <= 2e-5, 'Morphbench surface differs from fitted capsule')
    p1 = np.asarray(cap['p1'], dtype=float)
    axis = np.asarray(cap['p2'], dtype=float) - p1
    length = float(np.linalg.norm(axis))
    edges = [(ring[i], ring[(i + 1) % SEGMENTS]) for ring in mesh[2:-2:2] for i in range(SEGMENTS)]
    edges += [(first[i], second[i]) for first, second in zip(mesh[:-1], mesh[1:], strict=True)
              for i in range(0, SEGMENTS, SEGMENTS // 4)]
    thickness = min(.105, cap['radius'] * .045)
    vertices, triangles, normals = [], [], []
    for a, b in edges:
        vector = b - a
        if np.linalg.norm(vector) < 1e-5:
            continue
        center = (a + b) * .5
        parameter = float(np.clip(((center - p1) @ axis) / (length ** 2), 0., 1.)) if length > 1e-6 else 0.
        outward = center - p1 - parameter * axis
        outward /= np.linalg.norm(outward)
        across = np.cross(outward, vector)
        across *= thickness / np.linalg.norm(across)
        index = len(vertices)
        vertices.extend((a + across, a - across, b - across, b + across))
        normals.extend([outward] * 4)
        triangles.extend(((index, index + 1, index + 2), (index, index + 2, index + 3)))
    require(bool(triangles), 'Capsule has no visible lines')
    return vertices, triangles, normals


def write_mesh(api, path, bank, skeleton):
    nif = api.NifFile()
    nif.initialize('SKYRIMSE', str(path))
    identity = api.TransformBuf()
    identity.set_identity()
    layouts = {}
    for row in bank:
        node = row['node']
        # The skin palette is resolved by bone name at run time. Vertices and
        # the identity bind are in that bone frame, as used by CBPC offsets.
        require(node in skeleton.nodes, 'Fitted bone absent from the pinned skeleton: ' + node)
        verts, tris, normals = wires(row)
        name = f'CLAWCollider{row["slot"]:03d}'
        shape = nif.createShapeFromData(name, list(map(tuple, verts)), tris, [(0., 0.)] * len(verts),
                                        list(map(tuple, normals)))
        shape.skin()
        shape.add_bone(node, identity)
        shape.set_global_to_skin(identity)
        shape.set_skin_to_bone_xform(node, identity)
        shape.setShapeWeights(node, [(i, 1.) for i in range(len(verts))])
        shape.set_partitions([api.SkyPartition(part_id=SLOT, namedict=nif.dict)], [SLOT] * len(tris))
        shader = shape.shader.properties
        shader.shaderflags1_set(api.ShaderFlags1.OWN_EMIT)
        shader.shaderflags2_set(api.ShaderFlags2.DOUBLE_SIDED)
        shader.Emissive_Color = (*COLORS[row['region']], 1.)
        shader.Emissive_Mult = 1.2
        shader.Alpha = 1.
        shape.save_shader_attributes()
        shape.set_texture('Diffuse', TEXTURE.as_posix().replace('/', '\\'))
        layouts[name] = (row, np.asarray(verts), tuple(tris))
    nif.save()
    check = api.NifFile(str(path))
    require({shape.name for shape in check.shapes} == set(layouts), 'Incomplete render geometry')
    for shape in check.shapes:
        row, verts, tris = layouts[shape.name]
        node = row['node']
        shader = shape.shader.properties
        require(shape.bone_names == [node] and tuple(shape.tris) == tris and
                bytes(shape.get_shape_skin_to_bone(node)) == bytes(identity) and
                [part.id for part in shape.partitions] == [SLOT] and not shape.flags & 1 and
                sorted(shape.bone_weights[node]) == [(i, 1.) for i in range(len(verts))] and
                np.allclose(shape.verts, verts, rtol=0., atol=2e-5), f'Wire binding differs: {shape.name}')
        require(shader.shaderflags1_test(api.ShaderFlags1.SKINNED) and
                shader.shaderflags1_test(api.ShaderFlags1.OWN_EMIT) and
                shader.shaderflags2_test(api.ShaderFlags2.DOUBLE_SIDED) and
                np.allclose(tuple(shader.Emissive_Color)[:3], COLORS[row['region']]) and
                np.isclose(shader.Emissive_Mult, 1.2) and
                shape.textures['Diffuse'].replace('\\', '/') == TEXTURE.as_posix(),
                f'Wire material differs: {shape.name}')
    return sum(len(tris) for _, _, tris in layouts.values())


def base_dds():
    header = (124, 0x100F, 4, 4, 16, 0, 0, *(0,) * 11, 32, 0x41, 0, 32,
              0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000, 0x1000, 0, 0, 0, 0)
    return b'DDS ' + struct.pack('<31I', *header) + bytes((32, 32, 32, 255)) * 16


def record_tools():
    src = ROOT / 'src/test/resources/inspection/lighting/build_lighting.py'
    spec = importlib.util.spec_from_file_location('claw_showcase_records', src)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def armor_plugin(r):
    form = lambda value: struct.pack('<I', value)
    record = lambda kind, key, pairs: r.rec(kind, key, b''.join(r.sub(k, v) for k, v in pairs))
    header = record('TES4', 0, [('HEDR', struct.pack('<fII', 1.7, 4, ARMOR + 1)),
                              ('CNAM', b'CLAW VR test fixture\0'), ('MAST', b'Skyrim.esm\0'), ('DATA', bytes(8))])
    slots = struct.pack('<III', 1 << (SLOT - 30), 0, 2)
    model = MODEL.relative_to('meshes').as_posix().replace('/', '\\').encode('ascii') + b'\0'
    addon = record('ARMA', 0x01000000 | ADDON, [('EDID', b'CLAWVRColliderShowcaseAddon\0'), ('BODT', slots),
                  ('RNAM', form(RACE)), ('DNAM', bytes.fromhex('000000000000001700000000')),
                  ('MOD2', model), ('MOD3', model)])
    armor = record('ARMO', 0x01000000 | ARMOR, [('EDID', b'CLAWVRColliderShowcaseWires\0'), ('OBND', bytes(12)),
                  ('FULL', b'CLAW VR Collider Showcase\0'), ('BODT', slots), ('RNAM', form(RACE)),
                  ('MODL', form(0x01000000 | ADDON)), ('DATA', bytes(8)), ('DNAM', bytes(4))])
    plugin = header + r.grp(b'ARMA', 0, addon) + r.grp(b'ARMO', 0, armor)
    readback = {kind: (key, dict(r.subs(fields))) for kind, key, _, fields, *_ in r.records(plugin)}
    require(set(readback) == {b'TES4', b'ARMA', b'ARMO'} and readback[b'TES4'][1][b'MAST'] == b'Skyrim.esm\0' and
            readback[b'ARMO'][1][b'MODL'] == form(readback[b'ARMA'][0]) and
            all(readback[name][1][b'RNAM'] == form(RACE) and readback[name][1][b'BODT'] == slots
                for name in (b'ARMO', b'ARMA')), 'Unexpected wearable test plugin readback')
    return plugin


def stage(args):
    pinned(args.profile, FILE_HASHES['profile'])
    pinned(args.fixture, FILE_HASHES['fixture'])
    pinned(args.tuning, FILE_HASHES['template'])
    profile = json.loads(args.profile.read_text(encoding='utf-8'))
    skeleton_pin = next(row for row in profile['sourceInputs'] if Path(row['path']).name == 'skeleton.nif')
    pinned(args.skeleton, skeleton_pin['sha256'])
    api, patch, _, tool_pins = dependencies(args.pynifly, args.morphbench)
    from morphbench import colliders

    skeleton = api.NifFile(str(args.skeleton))
    r = record_tools()
    rows = list(r.records(args.fixture.read_bytes()))
    require([(row[0], row[1]) for row in rows] == [(b'TES4', 0), (b'NPC_', 0x01000800)], 'Expected the admitted stationary actor fixture')
    npc = dict(r.subs(rows[1][3]))
    require(args.fixture.name == FIXTURE and struct.unpack('<I', npc[b'RNAM'])[0] == RACE and
            struct.unpack('<f', npc[b'NAM7'])[0] == WEIGHT, 'Fixture race or weight does not match the capsule bank')
    bank = fitted_bank(profile)
    manifest = json.loads((HERE / 'scene.json').read_text(encoding='utf-8'))
    output = safe_output(args.out, [args.profile, args.fixture, args.tuning, args.skeleton])
    output.mkdir(parents=True)
    payload = output / 'payload'
    files = {MODEL, TEXTURE, Path(PLUGIN), Path(FIXTURE), *(CONFIG / name for name in SOURCE_CONFIGS)}
    for path in files:
        (payload / path).parent.mkdir(parents=True, exist_ok=True)
    triangles = write_mesh(api, payload / MODEL, bank, skeleton)
    require(patch(payload / MODEL).consistent(), 'Morphbench rejected the wearable mesh container')
    (payload / TEXTURE).write_bytes(base_dds())
    (payload / PLUGIN).write_bytes(armor_plugin(r))
    (payload / FIXTURE).write_bytes(args.fixture.read_bytes())
    for name, value in configs(bank, args.tuning.read_text(encoding='ascii')).items():
        (payload / CONFIG / name).write_bytes(value.encode('ascii'))
    receipt = {'schema': 'claw-vr-collider-showcase-stage/1', 'modelIdentity': profile['modelIdentity'],
               'sourceHashes': FILE_HASHES | {'skeleton': skeleton_pin['sha256'], 'builder': sha256(Path(__file__))},
               'profileSources': profile['sourceInputs'], 'tools': tool_pins | {'Morphbench Capsule': sha256(Path(colliders.__file__))},
               'weight': WEIGHT, 'morphs': {}, 'slots': bank, 'triangles': triangles, 'colors': COLORS,
               'scene': manifest, 'files': {path.as_posix(): sha256(payload / path) for path in sorted(files)},
               'runtimeChecked': False}
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(f'Staged {len(bank)} illustrated capsules and two wand sources. Runtime remains unverified.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('profile', 'fixture', 'tuning', 'skeleton', 'pynifly', 'morphbench', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    stage(parser.parse_args())
