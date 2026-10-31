"""Expand only the new Neck NiSkinData spheres after explicit VR composition.

Bone-local spheres use serialized skin-to-bone B applied to raw shape vertices,
not B*C. Every serialized TRI delta, including public-reader tiny omissions, is
retained. This is an offline authoring enclosure, not runtime-culling acceptance.
"""
from __future__ import annotations

from pathlib import Path
import json
import shutil
import struct
import sys
import numpy as np

import body_resource as resource
import selective_visibility
sys.path.insert(0, str(resource.ROOT / 'src/main/python/build-tools'))
import breast_rig as rig
import head_split
import morph_quality
import tri_patch

NECK = 'NPC Neck [Neck]'
MARGIN = 1.01
ABSOLUTE_MARGIN = .001
PINS = {
    'female/first-person_0.nif': 'c5975ee4c37d77cbeb36c0d89c8314d6290f843c826d2d8779cbb099b0eef3e0',
    'female/first-person_1.nif': 'f27196b0dccba1d44671a52ce8cc7df14787b9a7189cefaa492ef710120165d1',
    'female/femalebodywerewolf.tri': '04cc835c9287756065fc76f78d70bee414fc25eb0a6e41363f6e16f19f3eac04',
    'male/first-person_0.nif': '1c35f5bb35dd5683778c2f89f9c4ff3dadfcd5eed0c39bf9c95e6d81de066ba3',
    'male/first-person_1.nif': '81a906c897a76620e930e6a94f8b2a5a7583934db7708e38f53a29e24e3b380d',
    'male/malebodywerewolf.tri': 'a6087d542776888ee03a7884a311e005d33b537b7eb794769d93a45042767467'}


def outward_float32(value):
    if not np.isfinite(value) or value < 0:
        raise ValueError('Expected finite nonnegative radius')
    result = np.float32(value)
    if float(result) < value:
        result = np.nextafter(result, np.float32(np.inf), dtype=np.float32)
    if not np.isfinite(result):
        raise ValueError('Radius is not representable as finite float32')
    return float(result)


def local_boxes(low, high, fields, bind):
    """All independent additive0..1 fields and weight0..1, in actual B frame."""
    low, high, bind = np.asarray(low, float), np.asarray(high, float), np.asarray(bind, float)
    if (low.shape != high.shape or low.ndim != 2 or low.shape[1] != 3 or bind.shape != (4, 4)
            or not all(np.isfinite(x).all() for x in (low, high, bind))):
        raise ValueError('Invalid paired geometry or bind')
    base = low @ bind[:3, :3].T + bind[:3, 3]
    lower, upper = base.copy(), base.copy()
    for field in [high-low, *fields]:
        field = np.asarray(field, float)
        if field.shape != low.shape or not np.isfinite(field).all():
            raise ValueError('Invalid complete morph direction')
        moved = field @ bind[:3, :3].T
        lower += np.minimum(moved, 0)
        upper += np.maximum(moved, 0)
    return lower, upper


def reach(lower, upper, center):
    lower, upper, center = [np.asarray(x, float) for x in (lower, upper, center)]
    if (lower.shape != upper.shape or lower.ndim != 2 or lower.shape[1] != 3 or center.shape != (3,)
            or not all(np.isfinite(x).all() for x in (lower, upper, center)) or np.any(lower > upper)):
        raise ValueError('Invalid finite coordinate enclosure')
    return float(np.linalg.norm(np.maximum(abs(lower-center), abs(upper-center)), axis=1).max())


def neck_record(container, shape):
    """Locate the exact sixteen-byte sphere of the reviewed SSE NiSkinData."""
    block = container.blocks[shape.id]
    extra, = struct.unpack_from('<I', block, 4)
    skin, = struct.unpack_from('<I', block, 88 + 4*extra)
    data_id, = struct.unpack_from('<I', container.blocks[skin])
    if container.kind(skin) != 'BSDismemberSkinInstance' or container.kind(data_id) != 'NiSkinData':
        raise ValueError('Unsupported serialized skin chain')
    r = head_split.Reader(container.blocks[data_id]); r.take(52)
    count, present = r.unpack('<IB')
    if count != len(shape.bone_names) or present != 1 or shape.bone_names.count(NECK) != 1:
        raise ValueError('Expected one new Neck palette entry and explicit skin records')
    result = None
    for name in shape.bone_names:
        offset = r.pos + 52
        fixed = r.take(68)
        count, = r.unpack('<H'); r.take(count*6)
        if name == NECK:
            values = np.asarray(struct.unpack('<4f', fixed[52:]), float)
            if not np.isfinite(values).all() or values[3] <= 0:
                raise ValueError('New Neck sphere is uninitialized or invalid')
            result = data_id, offset, values
    r.done()
    return result


def patch_spheres(before, ledger):
    result = bytearray(before); used = set()
    for row in ledger:
        offset = row['offset']
        if offset < 0 or offset+16 > len(result) or used & set(range(offset, offset+16)):
            raise ValueError('Overlapping or invalid sphere offset')
        used.update(range(offset, offset+16))
        old = tuple(struct.unpack_from('<4f', before, offset)); new = tuple(row['newSphere'])
        if old != tuple(row['oldSphere']) or old[:3] != new[:3] or not np.isfinite(new).all() or new[3] < old[3]:
            raise ValueError('Sphere edit changed center, shrank radius or disagrees with source')
        struct.pack_into('<4f', result, offset, *new)
    return bytes(result)


def verify_bytes(before, after, ledger):
    if len(before) != len(after) or patch_spheres(before, ledger) != after:
        raise ValueError('Opaque bytes changed outside the new Neck sphere fields')
    return {'onlyNewNeckSphereFieldsMayChange': True, 'centersByteExact': True,
            'bytesChanged': sum(a != b for a, b in zip(before, after)),
            'allOldBoneFieldsGeometryWeightsBindsMaterialsControllersAlphaExact': True}


def verify_rest_frame(shape, sphere):
    ids = np.asarray([i for i, w in shape.bone_weights[NECK] if w > 0], int)
    if not len(ids):
        raise ValueError('Neck palette entry has no positive support')
    bind = rig.matrix(shape.get_shape_skin_to_bone(NECK))
    vertices = np.asarray(shape.verts, float)[ids]
    local = vertices @ bind[:3, :3].T + bind[:3, 3]
    rest_reach = float(np.linalg.norm(local-sphere[:3], axis=1).max())
    if abs(rest_reach-sphere[3]) > 1e-4:
        raise ValueError('Stored native rest sphere does not identify the serialized B/raw-vertex frame')
    wrong = bind @ rig.matrix(shape.global_to_skin)
    wrong_points = vertices @ wrong[:3, :3].T + wrong[:3, 3]
    return ids, bind, {'boneFrame': 'serialized skin-to-bone B applied to raw vertices; global-to-skin C excluded',
                       'positiveSupport': len(ids), 'BRestReach': rest_reach,
                       'BRestRadiusResidual': rest_reach-float(sphere[3]),
                       'BCDiagnosticRestRadiusResidual': float(np.linalg.norm(wrong_points-sphere[:3], axis=1).max()-sphere[3])}


def build(resources, composition_report, output, morphbench, pynifly=None):
    resources, composition_report = [Path(p).resolve(strict=True) for p in (resources, composition_report)]
    admitted_report = resource.sha256(composition_report)
    composition = resource.read_json(composition_report)
    if (composition.get('status') != 'composed-offline-resources-measured-runtime-pending'
            or composition.get('resources') != PINS or resource.sha256(composition_report) != admitted_report):
        raise ValueError('Expected the explicitly reviewed composed-neck-seam-003 family')
    inputs = {str(composition_report): admitted_report, **{str(resources/name): value for name, value in PINS.items()}}
    if any(resource.sha256(path) != value for path, value in inputs.items()):
        raise ValueError('Reviewed composition resource changed')
    out = resource.safe_output(output, inputs)
    api, NifPatch, Trip, dependencies = resource.dependencies(pynifly, morphbench)
    if any(resource.sha256(path) != value for path, value in inputs.items()):
        raise ValueError('Admitted input changed during dependency loading')
    sources = [Path(__file__), Path(__file__).with_name('expand_neck_bounds.py'), Path(resource.__file__),
               Path(selective_visibility.__file__), Path(rig.__file__), Path(head_split.__file__),
               Path(morph_quality.__file__), Path(tri_patch.__file__)]
    source_pins = {str(path): resource.sha256(path) for path in sources}
    report = {'schemaVersion': 1, 'status': 'building', 'installable': False,
              'inputSha256': inputs, 'executedSourceSha256': source_pins, 'dependencySha256': dependencies,
              'marginMultiplier': MARGIN, 'absoluteMargin': ABSOLUTE_MARGIN, 'resources': {}, 'bodies': {},
              'scope': 'Only new Neck NiSkinData radii. Original center float32 bytes and every other input byte retained. Full decoded serialized TRI coefficients independently0..1 and independent neutral weight0..1 in B/raw-vertex frame. Equal low/high Neck bind frames are explicitly required. No runtime-culling/camera/appearance claim. No old bone bounds are changed.'}
    out.mkdir(parents=True)
    (out/'NOT_INSTALLABLE.txt').write_text('Offline post-composition new-Neck bone-bound enclosure. No game/runtime culling, camera or visual acceptance. No install layout or skeleton asset.\n', encoding='utf-8')
    try:
        for sex in ('female', 'male'):
            paths = [resources/sex/f'first-person_{i}.nif' for i in (0, 1)]
            native = [api.NifFile(str(path)) for path in paths]
            containers = [head_split.Nif(path.read_bytes()) for path in paths]
            tables = [NifPatch(path) for path in paths]
            if any(not t.consistent() or t.bs_version != 100 for t in tables):
                raise ValueError('Unsupported NIF block table')
            shapes = [{s.name: s for s in nif.shapes} for nif in native]
            if set(shapes[0]) != set(shapes[1]):
                raise ValueError('Endpoint shape inventory differs')
            tri = resources/sex/(sex+'bodywerewolf.tri')
            public = Trip.from_filepath(str(tri)).shapes
            fields, decoder = morph_quality.decode_fields(tri.read_bytes(), public,
                                              {name: len(s.verts) for name, s in shapes[0].items()})
            ledgers = [[], []]; plans = {}; receipts = {}
            for name, low in shapes[0].items():
                high = shapes[1][name]
                if low.tris != high.tris or len(low.verts) != len(high.verts):
                    raise ValueError('Endpoint topology changed')
                if NECK not in low.bone_names and NECK not in high.bone_names:
                    continue
                if NECK not in low.bone_names or NECK not in high.bone_names:
                    raise ValueError('Neck palette exists at only one endpoint')
                records = [neck_record(c, sh) for c, sh in zip(containers, (low, high))]
                rest = [verify_rest_frame(sh, row[2]) for sh, row in zip((low, high), records)]
                if not np.array_equal(rest[0][1], rest[1][1]):
                    raise ValueError('Differing endpoint Neck bind frames require a separately qualified interpolation model')
                ids = np.union1d(rest[0][0], rest[1][0])
                complete = [value[ids] for (shape, _), value in fields.items() if shape == name]
                endpoint_rows = []
                for endpoint, (shape, (data_id, relative_offset, old), frame) in enumerate(zip((low, high), records, rest)):
                    lower, upper = local_boxes(np.asarray(low.verts)[ids], np.asarray(high.verts)[ids], complete, frame[1])
                    required = reach(lower, upper, old[:3])
                    radius = outward_float32(max(float(old[3]), required*MARGIN+ABSOLUTE_MARGIN))
                    new = [*old[:3].tolist(), radius]
                    absolute = tables[endpoint].offsets[data_id] + relative_offset
                    ledger = {'shape': name, 'bone': NECK, 'skinDataBlock': data_id, 'offset': absolute,
                              'oldSphere': old.tolist(), 'newSphere': new}
                    ledgers[endpoint].append(ledger)
                    plans[endpoint, name] = (ids, lower, upper, new)
                    endpoint_rows.append({**frame[2], 'sphereBefore': old.tolist(), 'sphereAfter': new,
                                          'fullCubeCoordinateBoxReach': required, 'beforeCubeExcess': required-float(old[3]),
                                          'afterCubeClearance': radius-required, 'completeMorphFields': len(complete),
                                          'pairedEndpointBindFramesExact': True, 'supportUnionVertices': len(ids)})
                receipts[name] = endpoint_rows
            if len(receipts) != 7:
                raise ValueError('Expected exactly seven newly Neck-weighted visible mixed shapes')
            for endpoint, path in enumerate(paths):
                before = path.read_bytes(); after = patch_spheres(before, ledgers[endpoint])
                byte_proof = verify_bytes(before, after, ledgers[endpoint])
                target = out/'resources'/sex/path.name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(after)
                actual = api.NifFile(str(target)); actual_container = head_split.Nif(after)
                selective_visibility.compare_readback(native[endpoint], actual, [])
                for shape in actual.shapes:
                    if (endpoint, shape.name) not in plans:
                        continue
                    ids, lower, upper, expected = plans[endpoint, shape.name]
                    _, _, sphere = neck_record(actual_container, shape)
                    if not np.array_equal(sphere, expected):
                        raise ValueError('Native serialized sphere does not equal the outward plan')
                    # Independent explicit eight-corner readback check.
                    for bits in np.ndindex(2, 2, 2):
                        corners = np.where(np.asarray(bits)[None, :], upper, lower)
                        if np.linalg.norm(corners-sphere[:3], axis=1).max() > sphere[3]:
                            raise ValueError('A full morph/weight enclosure corner escapes the actual sphere')
                relative = str(target.relative_to(out/'resources')).replace('\\', '/')
                report['resources'][relative] = resource.sha256(target)
                report['bodies'][sex+str(endpoint)] = {'byteProof': byte_proof, 'editLedger': ledgers[endpoint],
                                                       'nativeReadback': True, 'allBoxCornersContained': True}
            target_tri = out/'resources'/sex/tri.name; shutil.copyfile(tri, target_tri)
            if target_tri.read_bytes() != tri.read_bytes():
                raise ValueError('TRI bytes changed')
            report['resources'][sex+'/'+tri.name] = resource.sha256(target_tri)
            report.setdefault('measurements', {})[sex] = {'completeTriDecoder': decoder, 'shapes': receipts}
            print('NECK_BOUNDS|' + sex + '|14new-sphere fields verified', flush=True)
        if set(report['resources']) != set(PINS) or set(report['bodies']) != {'female0', 'female1', 'male0', 'male1'}:
            raise ValueError('Incomplete four-endpoint bone-bound result')
        if any(resource.sha256(path) != value for path, value in {**inputs, **source_pins, **dependencies}.items()):
            raise ValueError('Input, executed source or dependency changed during authoring')
        report['status'] = 'offline-new-neck-bone-bounds-enclosed-byte-verified-runtime-pending'
    except Exception as exc:
        report['status'], report['failure'] = 'failed', str(exc)
        raise
    finally:
        (out/'neck-bounds-report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report
