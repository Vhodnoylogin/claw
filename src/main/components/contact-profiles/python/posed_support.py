"""Emit immutable pose/TRI support for the VR head, ear and tail slots."""
from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path
import sys

import numpy as np

import profile_contract as contract
from profile_contract import EQUIPPED_EARS, EQUIPPED_SKIN
from build_profiles import runtime_inputs

TOOLS = contract.ROOT / 'src/main/python/build-tools'
sys.path.insert(0, str(TOOLS))
from breast_rig import load_pynifly, matrix, read_weights
from tri_patch import offsets

HEAD = 'NPC Head [Head]'
NIF_HIDDEN = 1  # NiAVObject::Flag::kHidden


def require(value, message):
    if not value:
        raise ValueError(message)


class Skin:
    def __init__(self, shape):
        self.points = np.asarray(shape.verts, dtype=float)
        self.faces = np.asarray(shape.tris, dtype=int)
        self.bones = sorted(shape.bone_weights)
        require(self.points.ndim == 2 and self.points.shape[1] == 3 and np.isfinite(self.points).all()
                and self.faces.ndim == 2 and self.faces.shape[1] == 3 and len(self.faces) > 0
                and self.faces.min() >= 0 and self.faces.max() < len(self.points), 'Invalid source skin topology')
        weights = read_weights(shape, self.bones)
        self.weights = weights / weights.sum(axis=1, keepdims=True)
        frame = matrix(shape.global_to_skin)
        self.binds = np.asarray([matrix(shape.get_shape_skin_to_bone(name)) @ frame for name in self.bones])
        require(np.isfinite(self.binds).all(), 'Nonfinite serialized support bind')
        self.bodytri = tuple(entry.string_data for entry in shape.extra_data('NiStringExtraData') if entry.name == 'BODYTRI')

    def weight_delta(self, high):
        # Equal blended rest matrices alone cannot establish equal animated skin.
        require(self.bones == high.bones and self.points.shape == high.points.shape
                and np.array_equal(self.faces, high.faces) and np.array_equal(self.weights, high.weights)
                and np.array_equal(self.binds, high.binds) and self.bodytri == high.bodytri,
                'Weight endpoints change actual pose skin')
        return high.points - self.points


def selected_slots(model, *, ear_tail_only=False):
    contract.host.validate_fitted_model(model)
    require('priorSourceInputs' not in model and model.get('supportProfile') == contract.settings.VR_PROFILE
            and len(model['slots']) == contract.PROFILES['vr'][2],
            'Expected the standard fitted detailed VR model')
    required = {node: 4 for node in sorted(contract.EAR_TAIL_CONTACT_NODES)}
    if not ear_tail_only:
        required = {HEAD: 10, **required}
    selected = [(index, slot) for index, slot in enumerate(model['slots']) if slot['node'] in required]
    counts = {node: sum(slot['node'] == node for _, slot in selected) for node in required}
    require(counts == required and all(slot['sexMask'] == 'both' for _, slot in selected),
            'The detailed profile must retain the exact requested both-sex head/ear/tail slot counts')
    indices = list(range(88, 120))
    if not ear_tail_only:
        indices = list(range(20, 30)) + indices
    owners = [node for node, count in required.items() for _ in range(count)]
    require([(index, slot['node']) for index, slot in selected] == list(zip(indices, owners, strict=True)),
            'Posed contact slots or their owner order differ from the detailed VR profile')
    return selected


def selected_source_shapes(model, selected, sex, *, equipped=False):
    shapes = set()
    head_source = EQUIPPED_EARS if equipped else 'head'
    for node in {slot['node'] for _, slot in selected}:
        sources = [source['shape'] for source in model['regions'][sex + '/' + node]['sources']]
        if equipped and node == HEAD:
            allowed = {'body', 'head', EQUIPPED_EARS}
            require(sources and len(set(sources)) == len(sources) and set(sources) <= allowed,
                    f'Posed head region for {sex} must use visible equipped shapes')
        else:
            expected = 'body' if node.startswith('TailBone') else head_source
            require(sources == [expected], f'Posed contact region {sex}/{node} must use the native {expected} shape')
        shapes.update(sources)
    return shapes


def region_vertices(region, skins):
    """Translate concatenated fitted point indices back to the original shape vertices."""
    points, faces, names = [], [], set()
    for source in region['sources']:
        name = source['shape']
        require(name not in names, 'Duplicate shape in a fitted contact region')
        names.add(name)
        skin = skins[name]
        ids = source['vertices']
        face_ids = source['sourceTriangleIndices']
        require(len(ids) == len(set(ids)) and all(type(i) is int and 0 <= i < len(skin.points) for i in ids)
                and len(face_ids) == len(set(face_ids))
                and all(type(i) is int and 0 <= i < len(skin.faces) for i in face_ids), 'Invalid fitted source vertex or face')
        local = np.asarray(source['fullRegionTriangles'], dtype=int)
        require(local.shape == (len(face_ids), 3) and len(local) > 0 and local.min() >= 0 and local.max() < len(ids)
                and np.array_equal(np.asarray(ids)[local], skin.faces[face_ids]), 'Fitted source triangle differs from its NIF')
        faces.extend((local + len(points)).tolist())
        points.extend((name, index) for index in ids)
    require(len(points) == len(region['points']) and faces == region['faces'], 'Fitted region differs from its source chunks')
    return points


def sparse_fields(records, points, morphs):
    fields = {point: [] for point in points}
    indexes = {name: index for index, name in enumerate(morphs)}
    for (shape, name, index), record in records.items():
        point = (shape, index)
        if point in fields and any(record.packed) and record.scale != 0:
            require(name in indexes, 'Pose support contains a TRI channel outside the fitted model: ' + name)
            delta = np.asarray(record.packed) * record.scale
            require(np.isfinite(delta).all(), 'Nonfinite posed support TRI delta')
            fields[point].append((indexes[name], delta.tolist()))
    return fields


def compose_sex(model, selected, sex, low, high, records):
    regions = model['regions']
    points_by_node, memberships, ranges = {}, [], []
    keys = {}
    for index, slot in selected:
        node = slot['node']
        region = regions[sex + '/' + node]
        if node not in points_by_node:
            points_by_node[node] = region_vertices(region, low)
        support = slot[sex]['partitionIndices']
        face_ids = slot[sex]['triangleIndices']
        require(len(face_ids) == len(set(face_ids)) and all(type(i) is int and 0 <= i < len(region['faces']) for i in face_ids),
                'Capsule partition has invalid region triangle indices')
        faces = [region['faces'][i] for i in face_ids]
        require(sorted(support) == sorted({point for face in faces for point in face}),
                'Capsule partition must retain all of its triangle vertices')
        start = len(memberships)
        for point in support:
            key = points_by_node[node][point]
            memberships.append(keys.setdefault(key, len(keys)))
        ranges.append((node, start, len(support), region['padding']))

    used = {name for name, _ in keys}
    displacement = {name: low[name].weight_delta(high[name]) for name in used}
    fields = sparse_fields(records, keys, model['morphs'])
    used_bones = {node for node, _, _, _ in ranges}
    bind_indices, binds, influence_refs, vertices, deltas, vertex_fields = {}, [], [], [], [], []
    for shape, vertex in keys:
        skin = low[shape]
        influence_start = len(influence_refs)
        for index in np.flatnonzero(skin.weights[vertex]):
            bone = skin.bones[index]
            used_bones.add(bone)
            key = (shape, bone)
            if key not in bind_indices:
                bind_indices[key] = len(binds)
                binds.append(skin.binds[index, :3, :3].tolist())
            neutral = (skin.binds[index] @ np.r_[skin.points[vertex], 1.])[:3]
            influence_refs.append((bone, skin.weights[vertex, index], neutral.tolist(), bind_indices[key]))
        vertices.append((influence_start, len(influence_refs) - influence_start))
        point_fields = fields[shape, vertex]
        vertex_fields.append((displacement[shape][vertex].tolist(), len(deltas), len(point_fields)))
        deltas.extend(sorted(point_fields))

    bones = sorted(used_bones)
    bone_index = {name: index for index, name in enumerate(bones)}
    return {'bones': bones, 'binds': binds, 'vertices': vertices, 'memberships': memberships,
            'influences': [(bone_index[bone], weight, point, bind) for bone, weight, point, bind in influence_refs],
            'ranges': [(bone_index[node], first, count, padding) for node, first, count, padding in ranges],
            'fields': vertex_fields, 'deltas': deltas, 'slotIndexes': [index for index, _ in selected]}


def values(row):
    if isinstance(row, (list, tuple)):
        return '{' + ', '.join(values(value) for value in row) + '}'
    if isinstance(row, str):
        require(row.isascii() and all(c.isprintable() for c in row), 'Invalid generated contact name')
        return json.dumps(row)
    require(np.isfinite(row), 'Nonfinite generated pose support')
    return repr(float(row)) if isinstance(row, (float, np.floating)) else str(int(row))


def render(model, sexes, *, equipped=False, shared_types=False):
    standalone_equipped = equipped and not shared_types
    route_type = 'EquippedPoseShapeRoute' if standalone_equipped else 'PoseShapeRoute'
    support_type = 'CompiledEquippedPosedVRSupport' if standalone_equipped else 'CompiledPosedVRSupport'
    accessor = 'CompiledEquippedVRPoseSupport' if equipped else 'CompiledVRPoseSupport'
    lines = ['#pragma once', '#include "claw/PosedContactSupport.h"', '#include <string_view>',
             'namespace claw::physics {']
    if not shared_types:
        lines.extend([f'struct {route_type} {{',
                      '    std::string_view name, bodyTri;',
                      '    std::size_t vertices, triangles, bones;',
                      '};',
                      f'struct {support_type} {{',
                      '    std::string_view modelIdentity;',
                      '    std::span<const std::string_view> bones, morphs;',
                      '    std::span<const std::size_t> slotIndexes;',
                      '    PosedContactModel model;',
                      f'    std::span<const {route_type}> shapes;', '};'])
    lines.extend([f'inline const {support_type}& {accessor}(bool female) {{',
                  'static constexpr std::string_view morphs[] = ' + values(model['morphs']) + ';'])
    for sex, data in sexes.items():
        lines.append(f'static const auto {sex} = [] {{')
        for kind, key in (('std::string_view', 'bones'), ('PoseInfluence', 'influences'), ('PoseVertex', 'vertices'),
                          ('std::size_t', 'memberships'), ('std::size_t', 'slotIndexes'), ('PoseRegion', 'ranges'),
                          ('PoseLinear', 'binds'), (route_type, 'shapes')):
            rows = [(bind,) for bind in data[key]] if key == 'binds' else data[key]
            lines.append(f'    static constexpr {kind} {key}[] = {{')
            lines.extend('        ' + values(row) + ',' for row in rows)
            lines.append('    };')
        lines.append(f'    static constexpr std::array<PoseMorphDelta, {len(data["deltas"])}> deltas = {{{{')
        lines.extend('        ' + values(row) + ',' for row in data['deltas'])
        lines.extend(['    }};', '    static constexpr PoseVertexFields fields[] = {'])
        for delta, begin, count in data['fields']:
            lines.append(f'        {{{values(delta)}, std::span{{deltas}}.subspan({begin}, {count})}},')
        lines.extend(['    };', f'    return {support_type}{{{values(model["modelIdentity"])}, bones, morphs, slotIndexes,',
                      '        {influences, vertices, memberships, ranges, std::size(bones), std::size(morphs), fields, binds}, shapes};',
                      '}();'])
    lines.extend(['    return female ? femaleData : maleData;', '}'])
    if shared_types:
        lines.append('inline std::span<const PoseShapeRoute> CompiledEquippedVRContactShapes(bool female) {')
        for sex, data in sexes.items():
            lines.append(f'    static constexpr PoseShapeRoute {sex}[] = {{')
            lines.extend('        ' + values(row) + ',' for row in data['restShapes'])
            lines.append('    };')
        lines.extend(['    return female ? std::span<const PoseShapeRoute>{femaleData} : std::span<const PoseShapeRoute>{maleData};', '}'])
    lines.extend(['} // namespace claw::physics', ''])
    return '\n'.join(lines)


def read_paired_build(directory, model_pin, *, ear_tail_only=False):
    report = json.loads((directory / 'contact-profiles-build.json').read_bytes())
    require(report.get('status') == 'offline-model-pair-generated-game-pending'
            and report['profiles']['vr']['model'] == model_pin, 'Paired build and posed model differ')
    content = (directory / 'physics-fit-model.h').read_bytes()
    require({'sha256': sha256(content).hexdigest(), 'bytes': len(content)} == report['pairedHeader']
            and b'CLAW_PHYSICS_POSED_VR_SUPPORT' not in content, 'Paired build header differs from its base receipt')
    # Older paired model emitters materialized large initializer lists on the
    # native worker stack. Exact archive reproduction still accepts that base.
    legacy = (b's.points={', b's.weightDeltas={', b's.fields.push_back({', b's.triangles={')
    require(ear_tail_only or (b'static const Vec3 data[]=' in content and not any(field in content for field in legacy)),
            'Head support needs a paired header with static numeric storage; regenerate it with the current fitter')
    return content


def equipped_build_inputs(directory):
    receipt = json.loads((directory / 'equipped-contact-build.json').read_bytes())
    require(receipt.get('schema') == 'claw-vr-equipped-contact-build/1' and
            receipt.get('status') == 'offline-fit-built' and receipt.get('exitCode') == 0 and
            receipt.get('runtimeQualified') is False and receipt.get('gameValidated') is False,
            'Expected the completed equipped world-model fit')
    paths = (
        (directory / 'fit/fitted-capsules.json').resolve(),
        (directory / 'inputs/runtime-inputs.json').resolve(),
    )
    for path, key in zip(paths, ('model', 'runtimeInputs'), strict=True):
        pinned = receipt[key]
        require(Path(pinned['path']).resolve() == path and
                contract.pin(path) == {field: pinned[field] for field in ('bytes', 'sha256')},
                'Equipped model or runtime manifest differs from its build receipt')
    return receipt, paths[0], paths[1]


def validate_runtime_banks(stock, equipped):
    def layout(model):
        return [(row['node'], row['partition'], row['sexMask'], row['male'] is not None, row['female'] is not None)
                for row in model['slots']]

    require(stock.get('coveredShapes') == ['body', 'head', 'claws'] and
            equipped.get('coveredShapes') == list(EQUIPPED_SKIN),
            'Compound contact header requires distinct stock and equipped world meshes')
    require(stock['modelIdentity'] != equipped['modelIdentity'] and
            stock['morphs'] == equipped['morphs'] and layout(stock) == layout(equipped) and
            all(stock.get(key) == equipped.get(key)
                for key in ('domain', 'weightDomain', 'weightDependent', 'contactPasses')) and
            all(stock['supportDeclaration'][key] == equipped['supportDeclaration'][key]
                for key in ('regions', 'skeletonSha256')),
            'Equipped model differs from the stock contact slot, bone or morph ABI')


def build(model_path, runtime_manifest, pynifly, output, *, paired_build=None, ear_tail_only=False,
          equipped=False, equipped_build=None, shared_types=False):
    require(equipped_build is None or (paired_build is not None and not equipped and not ear_tail_only),
            'The equipped build requires full stock pose support and a paired header')
    require(not shared_types or equipped, 'Only the equipped compound bank can reuse stock pose types')
    require(not equipped or paired_build is None, 'An equipped support bank cannot modify the stock paired header')
    model_pin = contract.pin(model_path)
    paired = read_paired_build(paired_build, model_pin, ear_tail_only=ear_tail_only) if paired_build is not None else None
    model = json.loads(model_path.read_bytes())
    if equipped:
        require(model.get('coveredShapes') == list(EQUIPPED_SKIN), 'Expected fitted visible equipped body and ear skin')
    selected = selected_slots(model, ear_tail_only=ear_tail_only)
    files = runtime_inputs(runtime_manifest)
    fitted_pins = {Path(row['path']).name: {key: row[key] for key in ('bytes', 'sha256')}
                   for row in model['sourceInputs']}
    require(all(contract.pin(path) == fitted_pins.get(name) for name, path in files.items()),
            'Runtime NIF and TRI pins differ from the fitted model')
    api, _, _ = load_pynifly(pynifly)
    profiles = {}
    for sex in ('male', 'female'):
        prefix = sex + 'bodywerewolf'
        endpoint_meshes = [api.NifFile(str(files[prefix + suffix])) for suffix in ('_0.nif', '_1.nif')]
        shapes = selected_source_shapes(model, selected, sex, equipped=equipped)
        if equipped:
            for mesh in endpoint_meshes:
                observed = [shape for shape in mesh.shapes if shape.name in EQUIPPED_SKIN]
                require(sorted(shape.name for shape in observed) == sorted(EQUIPPED_SKIN) and
                        all(not shape.flags & NIF_HIDDEN for shape in observed),
                        'Equipped contact input has a hidden or duplicate skin role')
        low, high = ({name: Skin(mesh.shape_dict[name]) for name in shapes} for mesh in endpoint_meshes)
        data = compose_sex(model, selected, sex, low, high, offsets(files[prefix+'.tri'].read_bytes()))
        body_tri = (rf'actors\werewolfbeast\claw\firstperson\{sex}\earworldtrial.tri' if equipped else
                    rf'actors\werewolfbeast\character assets\{prefix}.tri')
        routes = []
        for name, skin in sorted(low.items()):
            require(len(skin.bodytri) == 1 and skin.bodytri[0].replace('/', '\\').casefold() == body_tri,
                    'The posed shape must link the pinned world TRI')
            routes.append((name, skin.bodytri[0], len(skin.points), len(skin.faces), len(skin.bones)))
        data['shapes'] = routes
        if shared_types:
            names = sorted(set(EQUIPPED_SKIN) - shapes)
            endpoints = []
            for mesh in endpoint_meshes:
                rows = []
                for name in names:
                    shape = mesh.shape_dict[name]
                    tri = tuple(entry.string_data for entry in shape.extra_data('NiStringExtraData')
                                if entry.name == 'BODYTRI')
                    require(len(tri) == 1 and tri[0].replace('/', '\\').casefold() == body_tri,
                            'An equipped rest-only contact shape must link the pinned world TRI')
                    rows.append((name, tri[0], len(shape.verts), len(shape.tris), len(shape.bone_weights)))
                endpoints.append(rows)
            require(endpoints[0] == endpoints[1], 'An equipped rest-only contact shape changes with actor weight')
            data['restShapes'] = endpoints[0]
        profiles[sex + 'Data'] = data
    require(contract.pin(model_path) == model_pin and all(contract.pin(path) == fitted_pins[name] for name, path in files.items()),
            'Posed support inputs changed during extraction')
    out = contract.host.destination(output)
    out.mkdir(parents=True, exist_ok=False)
    header_name = 'posed-equipped-vr-support' if equipped else 'posed-vr-support'
    header = out / (header_name + ('.inc' if shared_types else '.h'))
    payload = render(model, profiles, equipped=equipped, shared_types=shared_types).encode('ascii')
    header.write_bytes(payload)
    record = {'modelIdentity': model['modelIdentity'], 'model': model_pin, 'source': contract.pin(Path(__file__)),
              'assets': {name: fitted_pins[name] for name in files}, 'generatedHeader': contract.pin(header),
              'scope': 'ear-tail' if ear_tail_only else 'head-ear-tail',
              'slots': [index for index, _ in selected], 'morphs': model['morphs'],
              'sexes': {key.removesuffix('Data'): {'bones': value['bones'], 'shapes': value['shapes'],
                        **{field: len(value[field]) for field in ('vertices', 'memberships', 'influences', 'deltas')}}
                        for key, value in profiles.items()}, 'providerRuntimeVerified': False}
    if equipped:
        record['modelRoute'] = 'equipped-world-ear'
    if shared_types:
        for key, profile in profiles.items():
            record['sexes'][key.removesuffix('Data')]['restShapes'] = profile['restShapes']
    if paired is not None:
        combined = out / 'physics-fit-model.h'
        compiled = paired + b'\n#define CLAW_PHYSICS_POSED_VR_SUPPORT 1\n' + payload
        if equipped_build is not None:
            outfitted_receipt, outfitted_model_path, outfitted_manifest = equipped_build_inputs(equipped_build)
            outfitted = json.loads(outfitted_model_path.read_bytes())
            require(outfitted['modelIdentity'] == outfitted_receipt['modelIdentity'],
                    'Equipped model identity differs from the fitted receipt')
            validate_runtime_banks(model, outfitted)
            outfitted_out = out / 'equipped'
            outfitted_pose = build(outfitted_model_path, outfitted_manifest, pynifly, outfitted_out, equipped=True, shared_types=True)
            require(outfitted_pose['model'] == {key: outfitted_receipt['model'][key] for key in ('sha256', 'bytes')} and
                    outfitted_pose['slots'] == record['slots'],
                    'Equipped pose data differs from the fitted bank or stock slot ABI')
            rest = outfitted_out / 'equipped-vr-contact.h'
            contract.fit.write_cpp_model(outfitted, rest, function_name='CompiledEquippedVRContactModel')
            pose = outfitted_out / 'posed-equipped-vr-support.inc'
            require(contract.pin(pose) == outfitted_pose['generatedHeader'],
                    'Equipped pose header changed during composition')
            compiled += (b'\n#define CLAW_PHYSICS_EQUIPPED_VR_SUPPORT 1\n'
                         + rest.read_bytes().removeprefix(b'#pragma once\n')
                         + pose.read_bytes().removeprefix(b'#pragma once\n'))
            record['equippedBank'] = {'build': contract.pin(equipped_build / 'equipped-contact-build.json'),
                                      'restHeader': contract.pin(rest), 'pose': outfitted_pose}
        combined.write_bytes(compiled)
        record['combinedHeader'] = contract.pin(combined)
    (out / 'posed-vr-support.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vr-model', type=Path, required=True)
    parser.add_argument('--runtime-inputs', type=Path, required=True)
    parser.add_argument('--pynifly', type=Path)
    parser.add_argument('--paired-build', type=Path, help='Also emit a native header from the exact paired build')
    parser.add_argument('--ear-tail-only', action='store_true', help='Reproduce the retained 32-slot support without Head')
    parser.add_argument('--equipped', action='store_true', help='Emit a separate equipped world-model pose bank')
    parser.add_argument('--equipped-build', type=Path, help='Embed the verified equipped world-model fit in the stock paired header')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.vr_model, args.runtime_inputs, args.pynifly, args.out,
                           paired_build=args.paired_build, ear_tail_only=args.ear_tail_only,
                           equipped=args.equipped, equipped_build=args.equipped_build), indent=2))


if __name__ == '__main__':
    main()
