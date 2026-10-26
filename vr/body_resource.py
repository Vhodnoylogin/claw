"""Pinned, offline first-person body visibility resources; no runtime integration.

Only the hidden flag of five verified face-only BSTriShapes is changed. The mixed
head/torso shape stays visible. All other NIF bytes and the entire TRI are retained.
Morphbench supplies its existing NIF block table reader; PyNifly independently
checks names, flags, breast-morph visibility and serialized skin.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
HIDDEN = 1  # NiAVObject::Flag::kHidden, CommonLibSSE-NG RE/N/NiAVObject.h.
ENGINE_ENTRY = 'meshes/actors/character/character assets/1stperson_werewolf_hands.nif'
HIDDEN_SHAPES = ['eyes', 'fur_face', 'FurfaceBlend', 'mouth', 'ScalpFurBlend']
HAND_BONES = ['NPC L Hand [RHnd]', 'NPC R Hand [RHnd]']
LIVE_NAMES = {'mods', 'mo2', 'modorganizer', 'overwrite', 'skyrimvr',
              'skyrim vr', 'skyrim special edition'}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON field: ' + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8-sig'), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def load_profile(path):
    profile = read_json(path)
    required = {'schemaVersion', 'sourceRelease', 'hiddenShapes', 'torsoMaximumZ', 'handBones', 'headBone',
                'skeletonSha256', 'bodies'}
    if not isinstance(profile, dict) or set(profile) != required or type(profile['schemaVersion']) is not int or profile['schemaVersion'] != 2:
        raise ValueError('Unsupported VR resource profile')
    if (profile['sourceRelease'] != '0.6.2.0' or profile['hiddenShapes'] != HIDDEN_SHAPES
            or profile['handBones'] != HAND_BONES or profile['headBone'] != 'NPC Head [Head]'
            or type(profile['torsoMaximumZ']) not in (int, float) or profile['torsoMaximumZ'] != 103.0):
        raise ValueError('The first candidate preserves the published body and hand ownership contract')
    if not isinstance(profile['bodies'], dict) or set(profile['bodies']) != {'male', 'female'}:
        raise ValueError('Both sexes are required')
    hashes = [profile['skeletonSha256']]
    for sex, body in profile['bodies'].items():
        if not isinstance(body, dict) or set(body) != {'nif', 'nifSha256', 'tri', 'triSha256', 'nodeCount', 'shapeCount', 'publicMorphCount'}:
            raise ValueError('Unsupported body entry')
        if body['nif'] != sex + 'bodywerewolf_0.nif' or body['tri'] != sex + 'bodywerewolf.tri':
            raise ValueError('Only the published low-weight body filenames are supported')
        if any(type(body[key]) is not int or body[key] <= 0 for key in ('nodeCount', 'shapeCount', 'publicMorphCount')):
            raise ValueError('Invalid body count pin')
        hashes.extend([body['nifSha256'], body['triSha256']])
    if any(not isinstance(h, str) or len(h) != 64 or any(c not in '0123456789abcdef' for c in h) for h in hashes):
        raise ValueError('Invalid SHA256 pin')
    # This MVP is deliberately one reviewed source recipe, not a general mesh editor.
    if profile != read_json(Path(__file__).with_name('profile.json')):
        raise ValueError('This builder supports only the reviewed published source profile')
    return profile


def safe_output(output, inputs, repo=ROOT):
    out = Path(output).resolve()
    if out.exists():
        raise ValueError('Output must be a new directory')
    blocked = [Path(repo).resolve(), *[Path(p).resolve().parent for p in inputs]]
    if any(out == p or p in out.parents for p in blocked):
        raise ValueError('Output is inside a repository or source directory')
    if any(p.casefold() in LIVE_NAMES for p in out.parts):
        raise ValueError('Output points into a live game/mod-manager tree')
    if any((parent / '.git').exists() for parent in out.parents):
        raise ValueError('Generated resources cannot be written inside a Git checkout')
    return out


def flags_offset(raw, block_offset, block_size, block_type, expected_flags):
    """Locate the fixed NiAVObject flag field only for Skyrim SE BSTriShape.

    Name index, extra-data count/references, controller index, then 32-bit flags.
    A native parser must independently provide the shape id/type/current flags.
    """
    if block_type != 'BSTriShape' or block_offset < 0 or block_size < 16 or block_offset + block_size > len(raw):
        raise ValueError('Unsupported or truncated shape block')
    extra = struct.unpack_from('<I', raw, block_offset + 4)[0]
    off = block_offset + 12 + 4 * extra
    if off + 4 > block_offset + block_size:
        raise ValueError('Shape extra-data references exceed the block')
    if struct.unpack_from('<I', raw, off)[0] != expected_flags:
        raise ValueError('Native and binary shape flags disagree')
    return off


def patch_hidden(raw, shapes, hidden_shapes):
    """Return changed bytes and an exact byte-edit ledger; no geometry serialization."""
    if len(hidden_shapes) != len(set(hidden_shapes)):
        raise ValueError('Duplicate hidden shape')
    by_name = {s['name']: s for s in shapes}
    if len(by_name) != len(shapes) or not set(hidden_shapes) <= set(by_name):
        raise ValueError('Missing or duplicate NIF shape')
    result = bytearray(raw)
    ledger = []
    for name in hidden_shapes:
        s = by_name[name]
        if s['flags'] & HIDDEN:
            raise ValueError('Source face shape is already hidden')
        off = flags_offset(raw, s['offset'], s['size'], s['type'], s['flags'])
        if any(abs(off - e['offset']) < 4 for e in ledger):
            raise ValueError('Overlapping shape flag fields')
        struct.pack_into('<I', result, off, s['flags'] | HIDDEN)
        ledger.append({'shape': name, 'offset': off, 'before': s['flags'], 'after': s['flags'] | HIDDEN})
    verify_bytes(raw, result, ledger)
    return bytes(result), ledger


def verify_bytes(before, after, ledger):
    """Prove the serialized candidate differs at only the planned hidden bits."""
    if len(before) != len(after):
        raise ValueError('NIF byte count changed')
    expected = bytearray(before)
    offsets = set()
    for entry in ledger:
        off = entry['offset']
        if off < 0 or off + 4 > len(before) or any(i in offsets for i in range(off, off + 4)):
            raise ValueError('Invalid or overlapping edit ledger')
        offsets.update(range(off, off + 4))
        old = struct.unpack_from('<I', before, off)[0]
        if old != entry['before'] or old & HIDDEN or entry['after'] != old | HIDDEN:
            raise ValueError('Edit does not only set the hidden bit')
        struct.pack_into('<I', expected, off, entry['after'])
    if bytes(expected) != bytes(after):
        raise ValueError('Unplanned bytes changed outside the face visibility flags')
    return sum(a != b for a, b in zip(before, after))


def dependencies(pynifly=None, morphbench=None):
    config_file = ROOT / 'build.local.json'
    config = read_json(config_file) if config_file.exists() else {}
    addon_value = pynifly or config.get('pynifly')
    mb_value = morphbench or config.get('morphbench')
    if not addon_value or not mb_value:
        raise ValueError('Configure PyNifly and Morphbench in build.local.json or explicit arguments')
    addon = Path(addon_value).resolve(strict=True)
    mb = Path(mb_value)
    if not mb.is_absolute():
        mb = ROOT / mb
    mb = mb.resolve(strict=True)
    if mb.is_file():
        mb = mb.parent
    required = [addon / 'pyn/pynifly.py', addon / 'NiflyDLL.dll', addon / 'tri/tripfile.py', mb / 'morphbench/nifpatch.py']
    if not all(p.is_file() for p in required):
        raise ValueError('Missing configured PyNifly/Morphbench files')
    sys.path.insert(0, str(addon))
    sys.path.insert(0, str(mb))
    from pyn import pynifly as api
    from morphbench.nifpatch import NifPatch
    api.NifFile.Load(str(addon / 'NiflyDLL.dll'))
    spec = importlib.util.spec_from_file_location('claw_vr_tripfile', addon / 'tri/tripfile.py')
    trip = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(trip)
    return api, NifPatch, trip.TripFile, {str(p): sha256(p) for p in required}


def tri_contract(TripFile, filename, nif, morph_count, *, include_trip=False):
    trip = TripFile()
    with Path(filename).open('rb') as stream:
        if trip.read(stream) != 0 or not trip.is_valid:
            raise ValueError('Invalid body TRI')
    shapes = {s.name: s for s in nif.shapes}
    if set(trip.shapes) != set(shapes):
        raise ValueError('TRI shape names do not match the pinned body')
    morphs = sorted({m for shape in trip.shapes.values() for m in shape})
    if len(morphs) != morph_count:
        raise ValueError('Public morph count changed')
    for shape, entries in trip.shapes.items():
        for morph, deltas in entries.items():
            seen = set()
            for index, delta in deltas:
                if index in seen or type(index) is not int or not 0 <= index < len(shapes[shape].verts):
                    raise ValueError('Invalid TRI vertex index')
                seen.add(index)
                if len(delta) != 3 or not all(math.isfinite(x) for x in delta):
                    raise ValueError('Nonfinite TRI delta')
    return (morphs, trip) if include_trip else morphs


def bodytri(shape):
    return [(e.name, e.string_data) for e in shape.extra_data('NiStringExtraData') if e.name == 'BODYTRI']


def head_descendant_names(skeleton, head_bone):
    if head_bone not in skeleton.nodes:
        raise ValueError('Pinned head bone is missing')
    descendants = {head_bone}
    for name, node in skeleton.nodes.items():
        parent = node.parent
        seen = {name}
        while parent:
            if parent.name in seen:
                raise ValueError('Cyclic skeleton ancestry')
            seen.add(parent.name)
            if parent.name == head_bone:
                descendants.add(name)
                break
            parent = parent.parent
    return descendants


def visible_by_hidden_flags(shape):
    """File attributes only: no claim about shaders, bone scale or runtime culling."""
    node = shape
    seen = set()
    while node:
        if node.name in seen:
            raise ValueError('Cyclic shape ancestry')
        seen.add(node.name)
        if node.flags & HIDDEN:
            return False
        node = node.parent
    return True


def visibility_admission(nif, skeleton, profile, trip):
    """Refuse whole-shape hiding of mixed torso anatomy before any byte edit.

    BreastSize presence is independently guarded even if its delta list is empty.
    Any torso morph entry also disqualifies a shape. The second guard detects
    torso-level non-head weighted geometry without relying on a morph's existence
    (needed for the published male head). z<=103 is the pinned torso/upper-chest
    extent used by this prototype, not a measured camera exclusion volume.
    """
    hidden = set(profile['hiddenShapes'])
    descendants = head_descendant_names(skeleton, profile['headBone'])
    decisions, breasts, mixed_head = {}, {}, None
    for shape in nif.shapes:
        morphs = trip.shapes[shape.name]
        torso_morphs = sorted(m for m in morphs if m.startswith('CLAWTorso'))
        torso_vertices = {i for bone, weights in shape.bone_weights.items() if bone not in descendants
                          for i, weight in weights if weight > 0 and shape.verts[i][2] <= profile['torsoMaximumZ']}
        if shape.name in hidden:
            if 'CLAWTorsoBreastSize' in morphs:
                raise ValueError('Cannot auto-hide a shape carrying CLAWTorsoBreastSize: ' + shape.name)
            if torso_morphs:
                raise ValueError('Cannot auto-hide a shape carrying torso morphs: ' + shape.name)
            if torso_vertices:
                raise ValueError('Cannot auto-hide torso-level non-head geometry: ' + shape.name)
            decisions[shape.name] = {'blockId': shape.id, 'torsoMorphEntries': [],
                                    'torsoLevelNonHeadWeightedVertices': 0}
        breast = morphs.get('CLAWTorsoBreastSize')
        if breast is not None:
            visible = visible_by_hidden_flags(shape)
            if breast and (shape.name in hidden or not visible):
                raise ValueError('Breast morph support would be hidden: ' + shape.name)
            breasts[shape.name] = {'blockId': shape.id, 'nonzeroDeltaCount': len(breast),
                                   'visibleByFileHiddenFlags': visible, 'shapeFlags': shape.flags}
        if shape.name == 'head':
            # The public shape name is misleading: both sexes include upper torso.
            if shape.name in hidden or not visible_by_hidden_flags(shape):
                raise ValueError('The mixed head/torso shape must remain visible')
            weights = shape.bone_weights
            mixed_head = {'blockId': shape.id, 'shapeFlags': shape.flags,
                          'visibleByFileHiddenFlags': True,
                          'spine2WeightedVertices': sum(w > 0 for _, w in weights.get('NPC Spine2 [Spn2]', [])),
                          'clavicleWeightedVertices': {bone: sum(w > 0 for _, w in rows)
                                                      for bone, rows in weights.items() if 'Clavicle' in bone},
                          'torsoLevelNonHeadWeightedVertices': len(torso_vertices),
                          'breastSizeNonzeroDeltaCount': len(breast or [])}
            if breast:
                points = [shape.verts[i] for i, _ in breast]
                mixed_head['breastSupportBounds'] = {'minimum': [min(p[a] for p in points) for a in range(3)],
                                                     'maximum': [max(p[a] for p in points) for a in range(3)]}
    if set(decisions) != hidden or mixed_head is None:
        raise ValueError('Missing verified face-only or retained mixed anatomy shape')
    return {'hiddenShapeAdmission': decisions, 'retainedMixedHead': mixed_head,
            'breastMorphSupport': breasts, 'torsoGeometryGuardMaximumZ': profile['torsoMaximumZ'],
            'breastMorphRuntimeRendering': 'unqualified; file flags and morph support are retained only'}


def audit_body(nif, skeleton, profile, sex):
    pin = profile['bodies'][sex]
    if len(nif.nodes) != pin['nodeCount'] or len(nif.shapes) != pin['shapeCount'] or nif.game != 'SKYRIMSE':
        raise ValueError('Pinned body structure changed')
    hidden = set(profile['hiddenShapes'])
    if not hidden <= {s.name for s in nif.shapes}:
        raise ValueError('Verified face-only shapes are missing')
    weighted = {b for s in nif.shapes for b in s.bone_names}
    missing = sorted(weighted - set(skeleton.nodes))
    if missing:
        raise ValueError('Body uses bones absent from pinned XP32: ' + ', '.join(missing))
    expected_tri = 'actors\\werewolfbeast\\character assets\\' + pin['tri']
    head_descendants = head_descendant_names(skeleton, profile['headBone'])
    hands = {bone: 0 for bone in profile['handBones']}
    residual = {}
    for shape in nif.shapes:
        if bodytri(shape) != [('BODYTRI', expected_tri)]:
            raise ValueError('BODYTRI differs from the published reference: ' + shape.name)
        for bone in hands:
            count = sum(w > 0 for _, w in shape.bone_weights.get(bone, []))
            if count and shape.name in hidden:
                raise ValueError('Visibility policy would hide hand geometry')
            hands[bone] += count
        if shape.name not in hidden:
            ids = {i for bone, rows in shape.bone_weights.items() if bone in head_descendants for i, w in rows if w > 0}
            if ids:
                residual[shape.name] = len(ids)
    if not all(hands.values()):
        raise ValueError('Both weighted hands must remain visible')
    return {'weightedBonesPresentInXP32': True, 'weightedHandVertices': hands,
            'remainingVisibleHeadDescendantWeightedVertices': residual,
            'cameraClearance': 'unqualified: mixed head/torso and body/fur shapes remain visible; no tracked camera pose was observed',
            'bodytri': expected_tri, 'nodeCount': len(nif.nodes), 'shapeCount': len(nif.shapes)}


def compare_skeletons(base, reference, body_bones):
    """Read-only diagnostic; a matching palette does not qualify IK or collision."""
    def transform(node):
        t = node.transform
        return [*t.translation, *[x for row in t.rotation for x in row], t.scale]
    changed = []
    for name in sorted(set(base.nodes) & set(reference.nodes)):
        a, b = base.nodes[name], reference.nodes[name]
        ap, bp = a.parent.name if a.parent else None, b.parent.name if b.parent else None
        error = max(abs(float(x) - float(y)) for x, y in zip(transform(a), transform(b)))
        if ap != bp or error > 1e-6:
            changed.append({'node': name, 'baseParent': ap, 'referenceParent': bp, 'localMaxDifference': error})
    return {'baseNodes': len(base.nodes), 'referenceNodes': len(reference.nodes),
            'added': sorted(set(reference.nodes) - set(base.nodes)),
            'removed': sorted(set(base.nodes) - set(reference.nodes)), 'changedLocalOrParent': changed,
            'bodyWeightedBonesMissingInReference': sorted(body_bones - set(reference.nodes)),
            'qualification': 'structural diagnostic only; no IK, camera or physics compatibility claim'}


def build(body_root, skeleton_file, profile_file, output, pynifly=None, morphbench=None, reference_vr_skeleton=None):
    profile = load_profile(profile_file)
    body_root = Path(body_root).resolve(strict=True)
    skeleton_file = Path(skeleton_file).resolve(strict=True)
    inputs = [skeleton_file, Path(profile_file).resolve(strict=True)]
    for entry in profile['bodies'].values():
        for name in ('nif', 'tri'):
            path = body_root / entry[name]
            if sha256(path) != entry[name + 'Sha256']:
                raise ValueError('Unsupported exact input: ' + entry[name])
            inputs.append(path)
    if sha256(skeleton_file) != profile['skeletonSha256']:
        raise ValueError('Unsupported exact XP32 skeleton input')
    if reference_vr_skeleton:
        reference_vr_skeleton = Path(reference_vr_skeleton).resolve(strict=True)
        inputs.append(reference_vr_skeleton)
    out = safe_output(output, inputs)
    api, NifPatch, TripFile, dependency_hashes = dependencies(pynifly, morphbench)
    skeleton = api.NifFile(str(skeleton_file))
    # Preflight both sexes before creating any output.
    prepared = {}
    body_bones = set()
    for sex, pin in profile['bodies'].items():
        source = body_root / pin['nif']
        nif = api.NifFile(str(source))
        audit = audit_body(nif, skeleton, profile, sex)
        morphs, trip = tri_contract(TripFile, body_root / pin['tri'], nif, pin['publicMorphCount'], include_trip=True)
        visibility = visibility_admission(nif, skeleton, profile, trip)
        table = NifPatch(source)
        if not table.consistent() or table.bs_version != 100:
            raise ValueError('Only the checked Skyrim SE NIF block table is supported')
        rows = [{'name': s.name, 'flags': s.flags, 'type': table.types[s.id],
                 'offset': table.offsets[s.id], 'size': table.sizes[s.id]} for s in nif.shapes]
        raw, ledger = patch_hidden(table.raw, rows, profile['hiddenShapes'])
        body_bones.update(b for s in nif.shapes for b in s.bone_names)
        prepared[sex] = (nif, audit, morphs, raw, ledger, trip, visibility)
    reference_audit = None
    if reference_vr_skeleton:
        reference_audit = compare_skeletons(skeleton, api.NifFile(str(reference_vr_skeleton)), body_bones)
        reference_audit['path'] = str(reference_vr_skeleton)
        reference_audit['sha256'] = sha256(reference_vr_skeleton)
    out.mkdir(parents=True, exist_ok=False)
    (out / 'NOT_INSTALLABLE.txt').write_text(
        'Offline CLAW VR body resources. No engine dispatch, weight-slider patch, skeleton patch, '
        'sex selection, morph application, camera or interaction qualification. Do not install as a mod.\n'
        'The mixed head/torso shape stays visible. Selective head masking is unimplemented.\n', encoding='utf-8')
    report = {'schemaVersion': 1, 'status': 'building', 'installable': False, 'sourceRelease': profile['sourceRelease'],
              'knownEngineEntry': ENGINE_ENTRY, 'skeletonOutput': None,
              'sourceSha256': {str(p): sha256(p) for p in inputs}, 'dependencySha256': dependency_hashes,
              'builderSourceSha256': {p.name: sha256(p) for p in [Path(__file__), Path(__file__).with_name('build_body.py')]},
              'pythonVersion': sys.version,
              'referenceSkeletonDiagnostic': reference_audit, 'bodies': {}}
    try:
        for sex, pin in profile['bodies'].items():
            original, audit, morphs, raw, ledger, trip, visibility = prepared[sex]
            directory = out / sex
            directory.mkdir()
            target = directory / 'face-hidden-resource.nif'
            target.write_bytes(raw)
            tri_target = directory / pin['tri']
            tri_target.write_bytes((body_root / pin['tri']).read_bytes())
            changed = verify_bytes((body_root / pin['nif']).read_bytes(), target.read_bytes(), ledger)
            result = api.NifFile(str(target))
            if len(result.nodes) != len(original.nodes) or [s.name for s in result.shapes] != [s.name for s in original.shapes]:
                raise ValueError('Native readback shape/node graph changed')
            for a, b in zip(original.shapes, result.shapes):
                expected = a.flags | HIDDEN if a.name in profile['hiddenShapes'] else a.flags
                if b.flags != expected or a.verts != b.verts or a.tris != b.tris or a.uvs != b.uvs or a.bone_weights != b.bone_weights or bodytri(a) != bodytri(b):
                    raise ValueError('Native readback changed the resource contract: ' + a.name)
            if sha256(tri_target) != pin['triSha256']:
                raise ValueError('TRI was not copied byte for byte')
            tri_contract(TripFile, tri_target, result, pin['publicMorphCount'])
            result_visibility = visibility_admission(result, skeleton, profile, trip)
            if (result_visibility['retainedMixedHead'] != visibility['retainedMixedHead']
                    or result_visibility['breastMorphSupport'] != visibility['breastMorphSupport']):
                raise ValueError('Serialized candidate changed mixed anatomy or breast morph file visibility')
            report['bodies'][sex] = {'resource': str(target.relative_to(out)), 'nifSha256': sha256(target),
                                     'tri': str(tri_target.relative_to(out)), 'triSha256': sha256(tri_target),
                                     'bytesChanged': changed, 'editLedger': ledger, 'publicMorphs': morphs,
                                     'verification': {'allOtherNifBytesIdentical': True, 'nativeReadback': True,
                                                      'triBytesIdentical': True, **audit, **result_visibility}}
        for p, before in report['sourceSha256'].items():
            if sha256(p) != before:
                raise ValueError('Source changed during build')
        report['status'] = 'offline-resource-candidate'
    except Exception as exc:
        report['status'] = 'failed'
        report['failure'] = str(exc)
        raise
    finally:
        (out / 'vr-body-report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report
