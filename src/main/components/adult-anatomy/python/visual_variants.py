"""Reversible file-visibility separation of the reviewed neutral anatomy shape.

The base keeps the original data embedded but hides only ``genitals``. The add-on
restores the exact reviewed original bytes. Neither operation changes physics.
Native readback and a local topology check are separate from game rendering.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import types
import zipfile
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
TOOLS = REPO/'src/main/python/build-tools'
VR = REPO/'src/main/python/vr'
MESH = 'Meshes/Actors/WerewolfBeast/Character Assets/'
HOOK = 'HDT Skinned Mesh Physics Object'
CORE_SHA = 'f571ad5e486600c3fcd06432034eeed9a2837be2706ca59bc0f72be28262c91a'
TRI_SHA = '3ff00f50493664ec68bbbfbe4843bd64f268df9a5659e6a6bd4baea14ae085fc'
SKELETON_SHA = 'b64b614d06eb854512ef4a9d6b08777fe0f9580f47d495d20db16dabb9fc2dd0'
SOURCES = {
    'static': ('6a7fa9e262a8a329dd3dc41a725edbf8c9da0a577176ed8c04dbae9924c45210', None),
    'core-fsmp': ('7abd65601c1383272f50b413792e7d54e12a5caf17270fb4f018c9868085c36d',
                  'SKSE/Plugins/hdtSkinnedMeshConfigs/CLAW/CLAWMotionMale.xml'),
    'anatomy3': ('b4270d4a781dec510ec4bc67623cb7d2bb1a7ee8284f1554b85bca4d1481c9f3',
                 'SKSE/Plugins/hdtSkinnedMeshConfigs/CLAW/CLAWNeutralAnatomy.xml'),
    'combined12': ('f93d5038cb17493517cf8f80dba63601edbf1f98678d781c3ae31589da7ff89d',
                   'SKSE/Plugins/hdtSkinnedMeshConfigs/CLAW/CLAWMotionNeutralAnatomyMale.xml'),
}


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def _load(path, payload):
    module = types.ModuleType('claw_anatomy_visibility_' + path.stem.replace('-', '_'))
    module.__file__ = str(path)
    exec(compile(payload, str(path), 'exec'), module.__dict__)
    return module


# Load only existing stdlib container/flag helpers. Pure byte APIs below read no
# files, need no native runtime or machine configuration, and perform no writes.
_HELPER_PATHS = (TOOLS/'player_only_materials.py', VR/'body_resource.py')
_HELPER_BYTES = {path: path.read_bytes() for path in _HELPER_PATHS}
_materials, _resource = (_load(path, _HELPER_BYTES[path]) for path in _HELPER_PATHS)


def _shape_record(payload):
    _, middle, kinds, indices, blocks, footer = _materials.container(payload)
    reader = _materials.Reader(middle)
    count, _ = reader.unpack('<II')
    strings = [reader.string() for _ in range(count)]
    require(reader.unpack('<I') == (0,) and reader.pos == len(middle), 'Unsupported string table')
    offset = len(payload) - sum(map(len, blocks)) - len(footer)
    records = []
    for index, block in enumerate(blocks):
        if kinds[indices[index]] == 'BSTriShape':
            name, extras = struct.unpack_from('<II', block)
            require(name < len(strings), 'Shape name index is invalid')
            if strings[name] == b'genitals':
                flags_at = 12 + 4*extras
                require(flags_at + 4 <= len(block), 'Truncated anatomy flag field')
                records.append({'name': 'genitals', 'block': index, 'offset': offset,
                                'size': len(block), 'type': 'BSTriShape',
                                'flags': struct.unpack_from('<I', block, flags_at)[0]})
        offset += len(block)
    require(len(records) == 1, 'Exactly one separate genitals BSTriShape required')
    return records[0]


def hide_anatomy(payload):
    """Return ``(base_bytes, ledger)`` for one of the four exact visible inputs.

    Only the shape's kHidden bit changes. Geometry remains embedded. No extra
    FSMP hook, skin edit, material, TRI, node, bounds or root reference is edited.
    """
    source = sha(payload)
    families = [name for name, (pin, _) in SOURCES.items() if pin == source]
    require(len(families) == 1, 'Only an exact reviewed visible anatomy source is accepted')
    record = _shape_record(payload)
    hidden, edits = _resource.patch_hidden(payload, [record], ['genitals'])
    require(_resource.verify_bytes(payload, hidden, edits) == 1, 'Expected exactly one changed flag byte')
    ledger = {'schemaVersion': 1, 'family': families[0], 'shapeBlock': record['block'],
              'sourceSha256': source, 'baseSha256': sha(hidden), 'edit': edits[0],
              'geometryRemainsEmbedded': True}
    return hidden, ledger


def restore_anatomy(payload, ledger):
    """Restore exact original add-on bytes; refuse changed bases or edit ledgers."""
    require(set(ledger) == {'schemaVersion', 'family', 'shapeBlock', 'sourceSha256', 'baseSha256',
                           'edit', 'geometryRemainsEmbedded'} and ledger['schemaVersion'] == 1
            and ledger['family'] in SOURCES and ledger['geometryRemainsEmbedded'] is True,
            'Exact anatomy visibility ledger required')
    require(sha(payload) == ledger['baseSha256']
            and ledger['sourceSha256'] == SOURCES[ledger['family']][0], 'Hidden base or source pin changed')
    record = _shape_record(payload)
    edit = ledger['edit']
    require(set(edit) == {'shape', 'offset', 'before', 'after'} and edit['shape'] == 'genitals'
            and record['block'] == ledger['shapeBlock'] and edit['after'] == edit['before'] | 1
            and not edit['before'] & 1 and record['flags'] == edit['after'], 'Changed anatomy flag ledger')
    offset = _resource.flags_offset(payload, record['offset'], record['size'], record['type'], record['flags'])
    require(offset == edit['offset'], 'Anatomy flag offset changed')
    result = bytearray(payload)
    struct.pack_into('<I', result, offset, edit['before'])
    result = bytes(result)
    require(sha(result) == ledger['sourceSha256'], 'Restored add-on is not the exact reviewed original')
    _resource.verify_bytes(result, payload, [edit])
    return result


def closure_audit(vertices, triangles, anatomy_vertices, *, weld_vertices=None, margin=4.0):
    """Finite local topology evidence, not a global solid or appearance oracle.

    Weld only exact serialized body coordinates (UV seam duplicates). Embedding
    coordinates may be full-rest LBS positions. All global defects are retained.
    A four-unit box margin selects the surrounding patch; it is not a mesh repair
    tolerance and changes no coordinates or topology.
    """
    import numpy as np
    v, t, anatomy = np.asarray(vertices, float), np.asarray(triangles), np.asarray(anatomy_vertices, float)
    keys = v if weld_vertices is None else np.asarray(weld_vertices, float)
    require(v.ndim == 2 and v.shape[1] == 3 and keys.shape == v.shape and anatomy.ndim == 2
            and anatomy.shape[1] == 3 and len(anatomy) and np.isfinite(v).all() and np.isfinite(keys).all()
            and np.isfinite(anatomy).all() and t.ndim == 2 and t.shape[1] == 3
            and np.issubdtype(t.dtype, np.integer) and len(t) and t.min() >= 0 and t.max() < len(v),
            'Finite native body/anatomy arrays and integer triangles required')
    require(type(margin) in (int, float) and np.isfinite(margin) and margin > 0, 'Positive finite local patch margin required')
    _, inverse, counts = np.unique(keys, axis=0, return_inverse=True, return_counts=True)
    welded = np.zeros((len(counts), 3)); np.add.at(welded, inverse, v); welded /= counts[:, None]
    faces = inverse[t]
    edges = np.concatenate((faces[:, (0, 1)], faces[:, (1, 2)], faces[:, (2, 0)]))
    edges, edge_counts = np.unique(np.sort(edges, axis=1), axis=0, return_counts=True)
    xyz = welded[edges]
    low, high = anatomy.min(0), anatomy.max(0)
    roi_low, roi_high = low-margin, high+margin
    local = ((xyz.min(1) <= roi_high).all(1) & (xyz.max(1) >= roi_low).all(1))
    face_xyz = v[t]
    local_faces = (face_xyz.min(1) <= roi_high).all(1) & (face_xyz.max(1) >= roi_low).all(1)
    boundary = xyz[edge_counts == 1]
    distances = np.linalg.norm(np.maximum(low-boundary.max(1), 0) + np.maximum(boundary.min(1)-high, 0), axis=1)
    degenerate = np.any(np.diff(np.sort(faces, axis=1), axis=1) == 0, axis=1)
    return {'method': 'Exact serialized-coordinate seam weld; unchanged native rest-LBS surface; edge incidence in local anatomy AABB',
            'localPatchMarginGU': margin, 'anatomyRestBounds': [low.tolist(), high.tolist()],
            'patchBounds': [roi_low.tolist(), roi_high.tolist()], 'bodyTriangles': len(t),
            'localBodyTriangles': int(local_faces.sum()), 'globalBoundaryEdges': int((edge_counts == 1).sum()),
            'globalNonManifoldEdges': int((edge_counts > 2).sum()),
            'localBoundaryEdges': int(((edge_counts == 1) & local).sum()),
            'localNonManifoldEdges': int(((edge_counts > 2) & local).sum()),
            'localDegenerateTriangles': int((degenerate & local_faces).sum()),
            'boundaryAabbDistanceLowerBoundGU': float(distances.min()) if len(distances) else None,
            'maxInheritedRestSpreadAtWeldGU': float(np.linalg.norm(v-welded[inverse], axis=1).max()),
            'localClosurePassed': bool(local_faces.any() and not ((edge_counts != 2) & local).any()
                                       and not (degenerate & local_faces).any()),
            'limits': 'Local rest topology only. Existing global openings/nonmanifold edges remain. No renderer, culling, pose/intersection or aesthetic acceptance.'}


def verify_native_pair(base, addon, tri, skeleton, api, Patch, Trip, rig):
    """Read actual written files independently with PyNifly and Morphbench."""
    import numpy as np
    before, after = api.NifFile(str(addon)), api.NifFile(str(base))
    a, b = {s.name: s for s in before.shapes}, {s.name: s for s in after.shapes}
    require(list(a) == list(b) and len(a) == 16, 'Native shape inventory changed')
    require(len(a['genitals'].verts) == 886 and len(a['genitals'].tris) == 1760, 'Neutral anatomy layout changed')
    require(not a['genitals'].flags & 1 and b['genitals'].flags == a['genitals'].flags | 1, 'Native anatomy flags disagree')
    for name, old in a.items():
        new = b[name]
        require((new.flags == old.flags if name != 'genitals' else new.flags == old.flags | 1)
                and (old.verts, old.tris, old.uvs, old.normals, old.textures, old.bone_names, old.bone_weights) ==
                    (new.verts, new.tris, new.uvs, new.normals, new.textures, new.bone_names, new.bone_weights)
                and _resource.bodytri(old) == _resource.bodytri(new), 'Native surrounding/skin/material/TRI fields changed: '+name)
        require(np.array_equal(rig.matrix(old.global_to_skin), rig.matrix(new.global_to_skin)), 'Skin frame changed')
        require(all(np.array_equal(rig.matrix(old.get_shape_skin_to_bone(bone)), rig.matrix(new.get_shape_skin_to_bone(bone)))
                    for bone in old.bone_names), 'Skin bind changed')
    require(list(before.nodes) == list(after.nodes) and all(
        np.array_equal(rig.matrix(node.global_transform), rig.matrix(after.nodes[name].global_transform))
        for name, node in before.nodes.items()), 'Native node graph changed')
    visible = {name for name, shape in a.items() if _resource.visible_by_hidden_flags(shape)}
    require({name for name, shape in b.items() if _resource.visible_by_hidden_flags(shape)} == visible-{'genitals'},
            'Effective native file visibility changed outside anatomy')
    hook_values = []
    for nif in (before, after):
        extra = nif.root.get_extra_data(blockname='NiStringExtraData', name=HOOK)
        hook_values.append(extra.string_data if extra else None)
    require(hook_values[0] == hook_values[1], 'Unrelated FSMP binding changed')
    require(Patch(base).consistent() and Patch(addon).consistent(), 'Morphbench block readback inconsistent')
    morphs = _resource.tri_contract(Trip, tri, after, 30)
    skel = api.NifFile(str(skeleton))
    def rest(shape):
        names = shape.bone_names
        matrices = np.asarray([[rig.matrix(skel.nodes[n].global_transform) @ rig.matrix(shape.get_shape_skin_to_bone(n))
                                @ rig.matrix(shape.global_to_skin) for n in names]])
        return rig.lbs(shape.verts, rig.read_weights(shape, names), matrices, normalize=True)[0]
    closure = closure_audit(rest(a['body']), a['body'].tris, rest(a['genitals']), weld_vertices=a['body'].verts)
    require(closure['localClosurePassed'], 'Underlying body has a local opening/defect; do not claim an accepted base variant')
    return {'all16NativeShapesDataExact': True, 'onlyAnatomyFileVisibilityChanged': True,
            'allNativeBindsNodesMaterialsAndBodytriExact': True, 'morphbenchBlockReadback': True,
            'publicMorphCount': len(morphs), 'fsmpHook': hook_values[0], 'geometryRemainsEmbedded': True,
            'localBodyClosure': closure, 'runtimeRenderingQualified': False}


def build(*, core_archive, anatomy, combined, skeleton, pynifly, morphbench, out):
    source_paths = [Path(__file__), TOOLS/'build-unified-release.py', TOOLS/'breast_rig.py',
                    TOOLS/'vr_head.py', TOOLS/'surface_collar.py', TOOLS/'build-genitals.py', *_HELPER_PATHS]
    sources = {p: p.read_bytes() for p in source_paths}
    require(all(sources[p] == value for p, value in _HELPER_BYTES.items()), 'Loaded container/flag helper changed')
    reader = _load(source_paths[1], sources[source_paths[1]])
    inputs = {Path(core_archive).resolve(): Path(core_archive).read_bytes(), Path(skeleton).resolve(): Path(skeleton).read_bytes()}
    require(sha(inputs[Path(core_archive).resolve()]) == CORE_SHA and sha(inputs[Path(skeleton).resolve()]) == SKELETON_SHA,
            'Reviewed core archive or existing XP32 input differs')
    with zipfile.ZipFile(io.BytesIO(inputs[Path(core_archive).resolve()])) as archive:
        require(archive.testzip() is None, 'Core archive CRC failed')
        core = {name: archive.read(name) for name in archive.namelist()}
    config = ET.fromstring(core['fomod/ModuleConfig.xml'])
    families, source_routes = {}, {}
    for family, motion in (('static', 'none'), ('core-fsmp', 'fsmp')):
        mapping = reader.resolve_selection(config, core, native=True, male_family='HIMBO', family='Vanilla',
                                           additional_active=('HIMBO.esp',), physics=motion)
        routes = {MESH+'male'+route+'_'+str(weight)+'.nif': mapping[MESH+'male'+route+'_'+str(weight)+'.nif']
                  for route in ('bodywerewolf', 'PlayerWerewolf') for weight in (0, 1)}
        values = [core[path] for path in routes.values()]
        require(all(sha(value) == SOURCES[family][0] and value == values[0] for value in values), 'Core endpoint/armor route equivalence failed')
        families[family], source_routes[family] = [values[0], values[0]], routes
    tri_bytes = core['00 Base/'+MESH+'malebodywerewolf.tri']
    require(sha(tri_bytes) == TRI_SHA, 'Core TRI differs')
    for family, root in (('anatomy3', Path(anatomy)), ('combined12', Path(combined))):
        paths = [root/MESH/('malebodywerewolf_'+str(weight)+'.nif') for weight in (0, 1)]
        for path in (*paths, root/MESH/'malebodywerewolf.tri'):
            inputs[path.resolve()] = path.read_bytes()
        families[family] = [inputs[path.resolve()] for path in paths]
        require(all(sha(value) == SOURCES[family][0] for value in families[family])
                and families[family][0] == families[family][1] and sha(inputs[(root/MESH/'malebodywerewolf.tri').resolve()]) == TRI_SHA,
                'Frozen anatomy endpoints/TRI differ')
        source_routes[family] = [str(path.resolve()) for path in paths]
    # Capture native-reader inputs before importing/using them. Normal Python
    # dependency code is end-checked below; neither reader is used to resave NIFs.
    dependency_roots = (Path(pynifly).resolve(), Path(morphbench).resolve())
    dependency_bytes = {p.resolve(): p.read_bytes() for root in dependency_roots for p in root.rglob('*.py')}
    dll = Path(pynifly).resolve()/'NiflyDLL.dll'; dependency_bytes[dll] = dll.read_bytes()
    api, Patch, Trip, dependencies = _resource.dependencies(pynifly, morphbench)
    require(Path(api.__file__).resolve() == Path(pynifly).resolve()/'pyn/pynifly.py', 'A different native NIF reader is loaded')
    sys.path.insert(0, str(TOOLS))
    import breast_rig as rig
    require(Path(rig.__file__).resolve() == TOOLS/'breast_rig.py', 'A different rig helper is loaded')
    destination = _resource.safe_output(out, {**sources, **inputs, **dependency_bytes})
    require(destination.parent.is_dir(), 'External output parent must already exist')
    destination.mkdir()
    tri = destination/'common/malebodywerewolf.tri'; tri.parent.mkdir(); tri.write_bytes(tri_bytes)
    report = {'status': 'incomplete-not-for-installation', 'geometryRemainsEmbedded': True, 'families': {},
              'sourceRoutes': source_routes, 'sharedTri': {'path': str(tri), 'sha256': TRI_SHA},
              'skeletonSha256': SKELETON_SHA, 'skeletonWritten': False, 'runtimeRenderingQualified': False,
              'appearanceQualified': False, 'contactQualified': False, 'installed': False, 'gameStarted': False}
    report_path = destination/'visual-variants-report.json'
    try:
        for family, endpoints in families.items():
            items = []
            for weight, original in enumerate(endpoints):
                hidden, ledger = hide_anatomy(original)
                restored = restore_anatomy(hidden, ledger)
                require(restored == original, 'Visible add-on failed exact byte restoration')
                paths = {kind: destination/kind/family/('malebodywerewolf_'+str(weight)+'.nif') for kind in ('base', 'addon')}
                for kind, data in (('base', hidden), ('addon', restored)):
                    paths[kind].parent.mkdir(parents=True, exist_ok=True); paths[kind].write_bytes(data)
                native = verify_native_pair(paths['base'], paths['addon'], tri, skeleton, api, Patch, Trip, rig)
                require(native['fsmpHook'] == SOURCES[family][1], 'Family FSMP binding differs from its reviewed source')
                items.append({'weight': weight, 'base': {'path': str(paths['base']), 'sha256': sha(hidden)},
                              'addon': {'path': str(paths['addon']), 'sha256': sha(restored)}, 'ledger': ledger, 'readback': native})
            require(items[0]['base']['sha256'] == items[1]['base']['sha256']
                    and items[0]['addon']['sha256'] == items[1]['addon']['sha256'], 'Endpoint byte equivalence changed')
            report['families'][family] = {'strictEndpointByteEquivalence': True, 'endpoints': items}
        consumed = set(dependencies)
        consumed.update(str(Path(module.__file__).resolve()) for module in tuple(sys.modules.values())
                        if getattr(module, '__file__', None) and Path(module.__file__).resolve() in dependency_bytes)
        require(all(Path(path).read_bytes() == dependency_bytes[Path(path)] for path in consumed), 'A consumed native reader changed')
        require(all(path.read_bytes() == data for path, data in {**sources, **inputs}.items()), 'A source/resource changed during build')
        report.update(status='verified-offline-hidden-base-and-exact-visible-addon-local-closure-passed',
                      sourceInputs={str(p): sha(b) for p, b in sources.items()},
                      resourceInputs={str(p): sha(b) for p, b in inputs.items()},
                      dependencies={path: sha(dependency_bytes[Path(path)]) for path in sorted(consumed)},
                      limits=['Only the separate genitals shape hidden flag changes; all geometry and anatomy physics data stay embedded.',
                              'Local underlying body topology and exact surrounding surfaces are verified. Existing global openings/defects remain.',
                              'Source TRI and all morph/material/bind data remain exact. No state controller, reclosure, aesthetic tuning or game acceptance.'])
        return report
    finally:
        report_path.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('core-archive', 'anatomy', 'combined', 'skeleton', 'pynifly', 'morphbench', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build(**vars(args))
        print(json.dumps({'status': result['status'], 'families': len(result['families']), 'output': str(args.out)}))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
