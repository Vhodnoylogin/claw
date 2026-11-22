"""Offline, source-pinned FSMP surface registration; no working-contact claim.

Keep the frozen anatomy3/combined12 motion graph and every visible/skin block.
Only redirect its existing root hook to a private XML with one tagged surface.
The surface admits a reciprocal tagged skinned peer on a different skeleton.
No peer, provider binary, installation or runtime qualification is supplied.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import sys
import types
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
TOOLS = REPO/'src/main/python/build-tools'
VR = REPO/'src/main/python/vr'
MESH = 'Meshes/Actors/WerewolfBeast/Character Assets/'
PREFIX = 'SKSE/Plugins/hdtSkinnedMeshConfigs/CLAW/'
HOOK = 'HDT Skinned Mesh Physics Object'
SURFACE_TAG = 'CLAW.NeutralAnatomy.Surface.v1'
PEER_TAG = 'CLAW.NeutralAnatomy.Peer.v1'
PELVIS = 'NPC Pelvis [Pelv]'
ANATOMY_DRIVERS = ('WWD 2', 'WWLB 1', 'WWRB 1')
CORE_DRIVERS = ('NPC EarL [EarL]Bone01', 'NPC EarL [EarL]Bone02',
                'NPC EarR [EarR]Bone01', 'NPC EarR [EarR]Bone02',
                'TailBone01', 'TailBone02', 'TailBone03', 'TailBone04', 'TailBone05')
TRI_SHA = '3ff00f50493664ec68bbbfbe4843bd64f268df9a5659e6a6bd4baea14ae085fc'
FAMILIES = {
    'anatomy3': ('b4270d4a781dec510ec4bc67623cb7d2bb1a7ee8284f1554b85bca4d1481c9f3',
                 '9bf501b9f5e5ecd0b33fe725af74779a28c4213ee4ae1e2ce9edfcc0269b0529',
                 PREFIX+'CLAWNeutralAnatomy.xml', PREFIX+'CLAWNeutralAnatomyContact.xml'),
    'combined12': ('f93d5038cb17493517cf8f80dba63601edbf1f98678d781c3ae31589da7ff89d',
                   '7cb169385c37b28038643c406c07d6b91937672b872c908420e2172822647d8e',
                   PREFIX+'CLAWMotionNeutralAnatomyMale.xml', PREFIX+'CLAWMotionNeutralAnatomyContactMale.xml'),
}
PROVIDER_ZIP_SHA = 'cc7b62e0f8325cdea94383b18b692f672823c14b4c021f8f336c9df31b5c6bad'
PROVIDER_COMMIT = '2215ec3ba09adf0843a3291ed0437a6ca6d385e2'
PROVIDER_FILES = {
    'src/hdtSkyrimSystem.cpp': '339db6e9f56d2412d201d32175936c54b452ea7d1d34f5625efcf4d5a079fd35',
    'src/hdtSkyrimSystem.h': '3673a20871794dea07a2b2a21948c9df3021cd05db33ab0844e8f613db3ac51a',
    'src/hdtSkyrimBody.cpp': 'c9a22e6748d823517ce5a073dc19d5d1a28134ff88385eb43c760fc9372799d1',
    'src/hdtSkinnedMesh/hdtSkinnedMeshBody.cpp': '9ef03369c179e8d8e5cc98603f356061693e055d654b4f21b8119cdc2d197851',
    'src/hdtSkinnedMesh/hdtSkinnedMeshBody.h': '75dccc0f6dbf64256c887a0291f8719dc64cf87cd27cb2c571f42a971ca8ab86',
    'src/hdtSkinnedMesh/hdtDispatcher.cpp': '16c5749769c2037b6ea7b4bfb68327b78573508e96c94c2d15012251c3e5cfde',
    'src/hdtSkinnedMesh/hdtSkinnedMeshShape.cpp': '30a68216f8df3749f4e954e1ad4869bef5c7f51a8d6b07909a83f2472865e2b6',
    'src/hdtSkinnedMesh/hdtSkinnedMeshShape.h': '3938eb6cf3889206c44abcf78428e9d45e01cfe00bb84fe569a693e7f98313e8',
    'src/hdtSkinnedMesh/hdtSkinnedMeshAlgorithm.cpp': 'e2e5da1b2f82482c8d26fb54381bfb71f179e1f161ba4aabc1d970e144a6f5a5',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def _load(path, payload):
    module = types.ModuleType('claw_anatomy_collision_'+path.stem.replace('-', '_'))
    module.__file__ = str(path)
    exec(compile(payload, str(path), 'exec'), module.__dict__)
    return module


_HELPERS = (TOOLS/'player_only_materials.py', HERE/'compose_motion.py', VR/'body_resource.py')
_HELPER_BYTES = {p: p.read_bytes() for p in _HELPERS}
_container, _motion, _resource = (_load(p, _HELPER_BYTES[p]) for p in _HELPERS)


def provider_contract(archive_bytes, source_bytes):
    """Require the exact local release source, not an unpinned grammar guess."""
    require(sha(archive_bytes) == PROVIDER_ZIP_SHA, 'Published provider source archive differs')
    require(set(source_bytes) == set(PROVIDER_FILES), 'All authoritative provider files required')
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        for name, expected in PROVIDER_FILES.items():
            entries = [x for x in archive.namelist() if x.endswith('/'+name)]
            require(len(entries) == 1 and sha(source_bytes[name]) == expected
                    and archive.read(entries[0]) == source_bytes[name], 'Provider source differs: '+name)
    return {'releaseCommit': PROVIDER_COMMIT, 'archiveSha256': PROVIDER_ZIP_SHA,
            'files': PROVIDER_FILES, 'selectedFilesExactToReleaseArchive': True,
            'installedBinaryEquivalenceProved': False, 'providerParserExecuted': False,
            'rules': {
                'shape': 'readPerTriangleShape resolves the exact skinned mesh name and actual partition triangles.',
                'sharing': 'SHARED_EXTERNAL excludes the same skeleton pointer; dispatcher requires both skinned bodies.',
                'tags': 'A nonempty can-collide-with-tag list takes precedence over the blacklist; both bodies must admit each other.',
                'threshold': 'clipColliders retains any corner influence with w > FLT_EPSILON AND w > bone.weightThreshold.',
                'zeroSurface': 'Zero margin and penetration use the source surface, two-sided; a peer needs positive collision radius.',
            }}


def _motion_graph(payload, family):
    require(family in FAMILIES and sha(payload) == FAMILIES[family][1], 'Exact reviewed motion XML required')
    drivers = ANATOMY_DRIVERS+(CORE_DRIVERS if family == 'combined12' else ())
    anchors = ('WWD 1',)+(('NPC Head [Head]', 'Tails') if family == 'combined12' else ())
    root, _ = _motion.inspect_xml(payload, drivers, anchors)
    return root


def _extension():
    # Explicitly declare the already-present skin anchor before shape creation.
    # Provider otherwise creates it implicitly from a default bone template.
    anchor = ET.Element('bone', {'name': PELVIS})
    ET.SubElement(anchor, 'mass').text = '0'
    shape = ET.Element('per-triangle-shape', {'name': 'genitals'})
    for tag, value in [('margin', '0'), ('penetration', '0'), ('shared', 'external'),
                       ('tag', SURFACE_TAG), ('can-collide-with-tag', PEER_TAG)]:
        ET.SubElement(shape, tag).text = value
    for name in (PELVIS, *ANATOMY_DRIVERS):
        ET.SubElement(shape, 'weight-threshold', {'bone': name}).text = '1' if name == PELVIS else '0'
    return anchor, shape


def collision_xml(original, family):
    root = copy.deepcopy(_motion_graph(original, family))
    root.extend(_extension())
    ET.indent(root)
    result = ET.tostring(root, encoding='utf-8', xml_declaration=True)+b'\n'
    inspect_collision_xml(result, original, family)
    return result


def inspect_collision_xml(payload, original, family):
    motion = _motion_graph(original, family)
    require(isinstance(payload, bytes) and len(payload) < 100000
            and not any(x in payload.upper() for x in (b'<!DOCTYPE', b'<!ENTITY')), 'Bounded collision XML required')
    root = ET.fromstring(payload)
    expected = [*motion, *_extension()]
    require(root.tag == 'system' and not root.attrib and not (root.text or '').strip()
            and len(root) == len(expected)
            and all(_motion.signature(a) == _motion.signature(b) and not (a.tail or '').strip()
                    for a, b in zip(root, expected)), 'Original motion or exact collision policy changed')
    return {'motionRecordsExact': len(motion), 'dynamicDrivers': 3 if family == 'anatomy3' else 12,
            'newDynamicDrivers': 0, 'existingSkinAnchorExplicit': PELVIS,
            'surface': 'genitals', 'surfaceTag': SURFACE_TAG, 'peerTag': PEER_TAG,
            'shared': 'external', 'margin': 0, 'penetration': 0,
            'noPeerBound': True, 'contactQualified': False}


def _parts(payload):
    prefix, middle, types_, indices, blocks, footer = _container.container(payload)
    reader = _container.Reader(middle)
    count, _ = reader.unpack('<II')
    strings = [reader.string() for _ in range(count)]
    require(reader.unpack('<I') == (0,) and reader.pos == len(middle), 'Unknown NIF string table')
    return prefix, types_, indices, list(blocks), footer, strings


def bind_candidate(payload, family):
    """Pure bytes API. Only exact reviewed visible anatomy3/combined12 inputs."""
    require(family in FAMILIES and sha(payload) == FAMILIES[family][0], 'Exact reviewed visible anatomy NIF required')
    prefix, types_, indices, blocks, footer, strings = _parts(payload)
    kind = lambda i: types_[indices[i]]
    require(kind(0) == 'NiNode', 'Known Scene Root required')
    hooks, owners = [], []
    for index, raw in enumerate(blocks):
        if kind(index) == 'NiStringExtraData':
            require(len(raw) == 8, 'Unsupported string-extra record')
            name, value = struct.unpack('<II', raw)
            require(max(name, value) < len(strings), 'Invalid string-extra index')
            if strings[name] == HOOK.encode():
                require(strings[value] == FAMILIES[family][2].encode(), 'Unknown FSMP namespace')
                hooks.append(index)
    require(len(hooks) == 1, 'Exactly one known FSMP hook required')
    hook = hooks[0]
    for index, raw in enumerate(blocks):
        if kind(index) in ('NiNode', 'BSFadeNode', 'BSTriShape', 'NiTriShape'):
            count, = struct.unpack_from('<I', raw, 4)
            require(8+4*count <= len(raw), 'Truncated extra-data array')
            owners.extend(index for ref in struct.unpack_from('<'+str(count)+'I', raw, 8) if ref == hook)
    require(owners == [0], 'Hook must have exactly one root owner')
    replacement = FAMILIES[family][3].encode()
    require(replacement not in strings, 'Candidate hook already present')
    changed = list(blocks)
    changed[hook] = struct.pack('<II', struct.unpack_from('<I', blocks[hook])[0], len(strings))
    updated_strings = [*strings, replacement]
    middle = (struct.pack('<II', len(updated_strings), max(map(len, updated_strings)))
              + b''.join(struct.pack('<I', len(x))+x for x in updated_strings)+struct.pack('<I', 0))
    result = prefix+struct.pack('<'+str(len(changed))+'I', *map(len, changed))+middle+b''.join(changed)+footer
    after = _parts(result)
    require(after[0:3] == (prefix, types_, indices) and after[4:] == (footer, updated_strings)
            and all(raw == after[3][i] for i, raw in enumerate(blocks) if i != hook)
            and after[3][hook] == changed[hook], 'Hook edit changed unrelated NIF bytes')
    return result, {'hookBlock': hook, 'allOtherBlocksExact': True, 'originalStringIndicesExact': True,
                    'rootBlockExact': True, 'before': FAMILIES[family][2], 'after': FAMILIES[family][3],
                    'geometrySkinMaterialsBindsBoundsFlagsAndBodytriExact': True}


def retained_support(influences, triangles):
    """Published strict FP32-epsilon test on actual FP16-decoded corner weights."""
    thresholds = {PELVIS: 1., **dict.fromkeys(ANATOMY_DRIVERS, 0.)}
    require(influences and triangles, 'Actual packed influence and triangle evidence required')
    vertices, counts = [], dict.fromkeys(ANATOMY_DRIVERS, 0)
    for row in influences:
        require(len(row) == 4 and all(name in thresholds and math.isfinite(w) and 0 <= w <= 1
                                      for name, w in row), 'Unknown/invalid actual skin weight')
        keep = False
        for name, weight in row:
            if weight > 2**-23 and weight > thresholds[name]:
                keep = True
                if name in counts: counts[name] += 1
        vertices.append(keep)
    retained = []
    for index, tri in enumerate(triangles):
        require(len(tri) == 3 and len(set(tri)) == 3 and all(type(i) is int and 0 <= i < len(vertices) for i in tri),
                'Invalid actual triangle')
        if any(vertices[i] for i in tri): retained.append(index)
    require(retained and all(counts.values()), 'Each actual dynamic driver needs retained support')
    return {'packedVertexCount': len(vertices), 'sourceTriangleCount': len(triangles),
            'retainedDynamicVertices': sum(vertices), 'retainedTriangles': len(retained),
            'excludedPelvisOnlyTriangles': len(triangles)-len(retained),
            'positivePackedDriverRows': counts, 'retainedTriangleIndicesSha256': sha(struct.pack('<'+str(len(retained))+'I', *retained)),
            'comparison': 'any corner influence: w > FLT_EPSILON && w > threshold; no summed/average threshold'}


def native_readback(original, candidate, tri, api, Patch, Trip):
    before, after = api.NifFile(str(original)), api.NifFile(str(candidate))
    require([s.name for s in before.shapes] == [s.name for s in after.shapes] and len(after.shapes) == 16,
            'Native shape inventory changed')
    require(list(before.nodes) == list(after.nodes), 'Native bone/node inventory changed')
    for a, b in zip(before.shapes, after.shapes):
        require((a.flags, a.verts, a.tris, a.uvs, a.normals, a.textures, a.bone_names, a.bone_weights, _resource.bodytri(a))
                == (b.flags, b.verts, b.tris, b.uvs, b.normals, b.textures, b.bone_names, b.bone_weights, _resource.bodytri(b)),
                'Native visible/skin/material/TRI readback changed: '+a.name)
    hook = after.root.get_extra_data(blockname='NiStringExtraData', name=HOOK)
    require(hook is not None and hook.string_data in {v[3] for v in FAMILIES.values()}, 'Native root hook differs')
    require(Patch(original).consistent() and Patch(candidate).consistent(), 'Morphbench block readback inconsistent')
    morphs = _resource.tri_contract(Trip, tri, after, 30)
    shape = next(s for s in after.shapes if s.name == 'genitals')
    require((len(shape.verts), len(shape.tris)) == (886, 1760) and not shape.flags & 1
            and set(shape.bone_names) == {PELVIS, *ANATOMY_DRIVERS}, 'Exact visible anatomy skin shape required')
    _, types_, indices, blocks, _, strings = _parts(Path(candidate).read_bytes())
    raw = blocks[shape.id]
    extra, = struct.unpack_from('<I', raw, 4)
    instance, = struct.unpack_from('<I', raw, 88+4*extra)
    data, partition, _, bone_count = struct.unpack_from('<4I', blocks[instance])
    require([types_[indices[i]] for i in (instance, data, partition)] == ['NiSkinInstance', 'NiSkinData', 'NiSkinPartition']
            and bone_count == 4, 'Exact native skin instance required')
    bone_ids = struct.unpack_from('<4I', blocks[instance], 16)
    names = [strings[struct.unpack_from('<I', blocks[i])[0]].decode() for i in bone_ids]
    require(names == shape.bone_names, 'Packed/native bone palette differs')
    part = blocks[partition]
    require(struct.unpack_from('<IIIQ', part) == (1, 886*40, 40, 1600890815710218), 'Exact SSE packed skin format required')
    # The provider consumes partition.triList, not an assumed native/DCC index
    # list. Prove its identity map and both stored oriented triangle copies.
    reader = _container.Reader(part)
    reader.take(20+886*40)
    require(reader.unpack('<5H') == (886, 1760, 4, 0, 4), 'Exact partition counts required')
    require(reader.unpack('<4H') == (0, 1, 2, 3) and reader.unpack('<B') == (1,), 'Exact partition palette required')
    require(reader.unpack('<886H') == tuple(range(886)) and reader.unpack('<B') == (1,), 'Identity partition vertex map required')
    reader.take(886*16)  # Separate NiSkinPartition FP32 rows are not provider weights.
    require(reader.unpack('<B') == (1,), 'Actual partition triangle list required')
    triangle_bytes = reader.take(1760*6)
    partition_triangles = [tuple(values) for values in struct.iter_unpack('<3H', triangle_bytes)]
    require(partition_triangles == shape.tris and reader.unpack('<B') == (1,), 'Packed/native oriented triangle list differs')
    reader.take(886*4+10)
    require(reader.take(1760*6) == triangle_bytes and reader.pos == len(part), 'Partition triangle copies differ')
    influences = []
    for i, vertex in enumerate(shape.verts):
        start = 20+i*40
        require(struct.unpack_from('<3f', part, start) == vertex, 'Packed/native vertex correspondence differs')
        values = struct.unpack_from('<4e4B', part, start+28)
        require(all(j < len(names) for j in values[4:]), 'Invalid packed bone palette index')
        influences.append([(names[j], float(w)) for w, j in zip(values[:4], values[4:])])
    support = retained_support(influences, partition_triangles)
    return {'all16ShapesVisibleSkinUvMaterialFieldsExact': True, 'nodeInventoryExact': True,
            'morphbenchBlockReadback': True, 'publicMorphCount': len(morphs), 'nativeHook': hook.string_data,
            'packedPartitionOrientedTriangleOrderExact': True,
            'packedProviderSupport': support, 'solverExecuted': False, 'contactQualified': False}


def eligible_pair(peer_tags, peer_whitelist, *, same_skeleton=False, peer_skinned=True, both_kinematic=False):
    """Bounded source eligibility control, NOT a collision/impulse simulation."""
    return (peer_skinned and not same_skeleton and not both_kinematic
            and PEER_TAG in peer_tags and SURFACE_TAG in peer_whitelist)


def validate_peer_shape(payload):
    """Check an explicit prospective peer XML fragment; it remains unbound.

    A complete peer still requires an actual skinned NIF, hook/name/weight
    readback and a different live skeleton; this function cannot establish them.
    """
    require(isinstance(payload, bytes) and len(payload) < 10000
            and not any(x in payload.upper() for x in (b'<!DOCTYPE', b'<!ENTITY')), 'Bounded peer XML required')
    node = ET.fromstring(payload)
    require(node.tag == 'per-vertex-shape' and set(node.attrib) == {'name'} and node.get('name')
            and not (node.text or '').strip(), 'Explicit per-vertex peer shape required')
    require([x.tag for x in node] == ['margin', 'shared', 'tag', 'can-collide-with-tag']
            and all(not x.attrib and not len(x) and not (x.tail or '').strip() for x in node), 'Exact reciprocal peer fields required')
    radius = float(node.findtext('margin'))
    require(math.isfinite(radius) and radius > 0 and node.findtext('shared') == 'external'
            and node.findtext('tag') == PEER_TAG and node.findtext('can-collide-with-tag') == SURFACE_TAG,
            'Positive radius, external sharing and reciprocal peer tags required')
    return {'shape': node.get('name'), 'margin': radius, 'xmlContractPassed': True,
            'nativeBindingVerified': False, 'distinctLiveSkeletonVerified': False, 'contactQualified': False}


def build(*, anatomy, combined, provider_archive, provider_source, pynifly, morphbench, out):
    roots = {'anatomy3': Path(anatomy).resolve(), 'combined12': Path(combined).resolve()}
    source_paths = {Path(__file__), *_HELPERS}
    sources = {p: p.read_bytes() for p in source_paths}
    require(all(sources[p] == b for p, b in _HELPER_BYTES.items()), 'Loaded helper source changed')
    inputs = {Path(provider_archive).resolve(): Path(provider_archive).read_bytes()}
    provider = {name: (Path(provider_source)/name).read_bytes() for name in PROVIDER_FILES}
    inputs.update({(Path(provider_source)/name).resolve(): data for name, data in provider.items()})
    contract = provider_contract(inputs[Path(provider_archive).resolve()], provider)
    for family, root in roots.items():
        for rel in (FAMILIES[family][2], MESH+'malebodywerewolf.tri',
                    MESH+'malebodywerewolf_0.nif', MESH+'malebodywerewolf_1.nif'):
            path = root/rel
            inputs[path] = path.read_bytes()
        require(sha(inputs[root/MESH/'malebodywerewolf.tri']) == TRI_SHA, 'Reviewed TRI differs')
        require(inputs[root/MESH/'malebodywerewolf_0.nif'] == inputs[root/MESH/'malebodywerewolf_1.nif'],
                'Both actual endpoints must remain byte-equivalent')
    # Capture dependencies before import/use and check them again after readback.
    dependencies = {p.resolve(): p.read_bytes() for root in (Path(pynifly).resolve(), Path(morphbench).resolve())
                    for p in root.rglob('*.py')}
    dll = Path(pynifly).resolve()/'NiflyDLL.dll'
    dependencies[dll] = dll.read_bytes()
    api, Patch, Trip, consumed = _resource.dependencies(pynifly, morphbench)
    require(Path(api.__file__).resolve() == Path(pynifly).resolve()/'pyn/pynifly.py', 'Different native reader loaded')
    destination = _resource.safe_output(out, {**inputs, **sources, **dependencies})
    require(destination.parent.is_dir(), 'External output parent must exist')
    destination.mkdir()
    report = {'status': 'incomplete-do-not-install', 'providerSourceContract': contract, 'families': {},
              'peerAssetsSupplied': False, 'contactQualified': False, 'motionRuntimeQualified': False,
              'installed': False, 'gameStarted': False, 'providerBinarySupplied': False}
    try:
        for family, root in roots.items():
            output = destination/family
            original = inputs[root/FAMILIES[family][2]]
            xml = collision_xml(original, family)
            path = output/FAMILIES[family][3]
            path.parent.mkdir(parents=True); path.write_bytes(xml)
            tri = output/MESH/'malebodywerewolf.tri'
            tri.parent.mkdir(parents=True); tri.write_bytes(inputs[root/MESH/tri.name])
            rows = []
            for weight in (0, 1):
                before = root/MESH/f'malebodywerewolf_{weight}.nif'
                data, proof = bind_candidate(inputs[before], family)
                target = output/MESH/before.name
                target.write_bytes(data)
                proof['nativeReadback'] = native_readback(before, target, tri, api, Patch, Trip)
                rows.append({'weight': weight, 'path': str(target), 'sha256': sha(data), 'proof': proof})
            require(rows[0]['sha256'] == rows[1]['sha256'], 'Output endpoint equivalence differs')
            report['families'][family] = {'xml': {'path': str(path), 'sha256': sha(xml)},
                'xmlProof': inspect_collision_xml(path.read_bytes(), original, family), 'endpoints': rows,
                'triSha256': TRI_SHA, 'strictEndpointByteEquivalence': True}
        controls = {
            'reciprocalTaggedSkinnedDifferentSkeleton': eligible_pair({PEER_TAG}, {SURFACE_TAG}),
            'sameSkeletonRejected': not eligible_pair({PEER_TAG}, {SURFACE_TAG}, same_skeleton=True),
            'missingPeerTagRejected': not eligible_pair(set(), {SURFACE_TAG}),
            'missingReciprocalWhitelistRejected': not eligible_pair({PEER_TAG}, set()),
            'genericRigidObjectRejected': not eligible_pair({PEER_TAG}, {SURFACE_TAG}, peer_skinned=False),
            'twoKinematicObjectsRejected': not eligible_pair({PEER_TAG}, {SURFACE_TAG}, both_kinematic=True),
        }
        require(all(controls.values()), 'Source eligibility controls failed')
        peer_contract = {'surfaceTag': SURFACE_TAG, 'requiredPeerTag': PEER_TAG,
            'requiredPeerCanCollideWithTag': SURFACE_TAG, 'requiredPeerShape': 'per-vertex-shape',
            'requiredPeerMargin': 'finite and > 0, to be chosen/qualified against an actual peer asset',
            'requiredShared': 'external', 'eligibilityControls': controls,
            'controlKind': 'source-rule replay only; provider parser/solver not executed',
            'missing': ['Actual peer skinned NIF and source-pinned hook/shape/skin evidence.',
                        'A separate live skeleton, provider object creation and reciprocal filtering.',
                        'Measured contact/impulse response, stability and unchanged motion under contact.'],
            'genericHavokHiggsPlanckContactSupported': False, 'contactQualified': False}
        (destination/'peer-contract.json').write_text(json.dumps(peer_contract, indent=2)+'\n')
        consumed_paths = {Path(p) for p in consumed}
        consumed_paths.update(Path(m.__file__).resolve() for m in tuple(sys.modules.values())
                              if getattr(m, '__file__', None) and Path(m.__file__).resolve() in dependencies)
        require(all(p.read_bytes() == dependencies[p] for p in consumed_paths), 'Consumed native dependency changed')
        require(all(p.read_bytes() == data for p, data in {**sources, **inputs}.items()), 'Source/input changed during build')
        report.update(status='verified-offline-surface-binding-and-source-eligibility-only',
            sourceInputs={str(p): sha(b) for p, b in sources.items()}, resourceInputs={str(p): sha(b) for p, b in inputs.items()},
            dependencies={str(p): sha(dependencies[p]) for p in sorted(consumed_paths)},
            invocation={'anatomy': str(roots['anatomy3']), 'combined': str(roots['combined12']),
                        'provider_archive': str(Path(provider_archive).resolve()), 'provider_source': str(Path(provider_source).resolve()),
                        'pynifly': str(Path(pynifly).resolve()), 'morphbench': str(Path(morphbench).resolve()), 'out': str(destination)},
            limits=['Original 3/12 motion records retained; historical failed native male12 motion remains unqualified.',
                    'Only the known root hook value changes in NIFs; all other blocks, visible geometry, weights, TRI and bounds remain exact.',
                    'No peer is bound; registration alone cannot provide contact. No environment/HIGGS/PLANCK bridge is implemented.',
                    'Source rules are exact to the archived published grammar; loaded-provider behavior and binary/source equivalence are unproved.',
                    'Zero-thickness two-sided surface requires a positive-radius peer; no contact radius tuning or visual acceptance performed.'])
        return report
    finally:
        report['files'] = {str(p.relative_to(destination)).replace('\\', '/'): sha(p.read_bytes())
                           for p in sorted(destination.rglob('*')) if p.is_file() and p.name != 'collision-report.json'}
        (destination/'collision-report.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('anatomy', 'combined', 'provider-archive', 'provider-source', 'pynifly', 'morphbench', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build(**vars(args))
        print(json.dumps({'status': result['status'], 'families': len(result['families']), 'contactQualified': False}))
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
