"""Opt-in, shape-only BreastSize profile on the repaired female rest surface.

The three private fields are composed into the existing public morph. This module
never changes Basis, topology, UVs, skin weights, armatures or skeletons.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import numpy as np
import surface_collar as surface

PUBLIC_MORPH = 'CLAWTorsoBreastSize'
CHANNELS = ('mass', 'lowerProjection', 'sag')
# PyNifly 28.1 TripFile.set_morphs / _coord_nonzero use a strict per-axis
# 0.0001 cutoff. The serialized-file check below is the authoritative gate.
TRIP_COMPONENT_EPSILON = .0001


def semantic_sha256(value):
    """Ignore recipe prose, but retain every executable value and array order."""
    def clean(item):
        if isinstance(item, dict):
            return {k: clean(v) for k, v in item.items() if not k.startswith('_')}
        if isinstance(item, list):
            return [clean(v) for v in item]
        return item
    encoded = json.dumps(clean(value), sort_keys=True, separators=(',', ':'),
                         ensure_ascii=False, allow_nan=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def validate_profile(profile, female_recipe, full_recipe, collar_recipe, slim):
    if profile.get('schemaVersion') != 1 or profile.get('publicMorph') != PUBLIC_MORPH:
        raise ValueError('Unsupported breast shape profile/public morph')
    if collar_recipe is None:
        raise ValueError('--breast-shape requires --surface-collars')
    if slim != profile['source']['slim']:
        raise ValueError('Breast shape requires the pinned SLIM amount')
    rows = [r for r in female_recipe if r.get('morph') == PUBLIC_MORPH]
    if len(rows) != 1 or semantic_sha256(rows[0]) != profile['source']['femaleMorphSemanticSha256']:
        raise ValueError('Breast shape source morph semantics changed')
    if semantic_sha256(full_recipe) != profile['source']['fullRecipeSemanticSha256']:
        raise ValueError('Breast shape full-body recipe semantics changed')
    if semantic_sha256(collar_recipe) != profile['source']['collarRecipeSemanticSha256']:
        raise ValueError('Breast shape requires the pinned surface collar repair')
    coefficients = profile['coefficients']
    if set(coefficients) != set(CHANNELS):
        raise ValueError('Expected exactly three private field coefficients')
    for name, value in coefficients.items():
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not np.isfinite(value) or not 0 <= value <= 1:
            raise ValueError('Invalid breast field coefficient: ' + name)
    if not any(coefficients.values()):
        raise ValueError('Breast profile must retain a nonzero public BreastSize')
    positive = ('sourceAmplitude', 'supportWidth', 'midlineWidth', 'mirrorTolerance',
                'lowerWidth', 'massForward', 'massLateral', 'projectionForward',
                'projectionDown', 'sagDown')
    for name in positive:
        value = profile['fields'][name]
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not np.isfinite(value) or value <= 0:
            raise ValueError('Invalid breast field parameter: ' + name)
    for name in ('midlineStart', 'lowerTop'):
        value = profile['fields'][name]
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not np.isfinite(value):
            raise ValueError('Invalid breast field parameter: ' + name)
    surface.region_weight(np.zeros((1, 3)), profile['fields']['bounds'])
    return profile


def smooth(value):
    value = np.clip(value, 0, 1)
    return value * value * (3 - 2 * value)


def paired_mask(vertices, mask, tolerance):
    """Pair active positive-X vertices with a frozen, mirrored rest vertex.

    Brute-force nearest search is bounded to the small active lobe (452 vertices
    in the pinned donor), requires no new scientific/Blender dependency.
    """
    result, pairs = mask.copy(), []
    for i in np.flatnonzero((vertices[:, 0] > 0) & (mask > 0)):
        point = vertices[i] * [-1, 1, 1]
        distance = np.sum((vertices - point) ** 2, axis=1)
        j = int(distance.argmin())
        if distance[j] >= tolerance ** 2:
            # The repaired donor itself is slightly asymmetric near the collar.
            # Preserve its local support instead of pairing a different surface.
            continue
        pairs.append((int(i), j))
        result[i] = result[j] = .5 * (mask[i] + mask[j])
    return result, pairs


def shape_fields(vertices, old_delta, geodesic_distance, profile):
    """Private displacement fields; distances refer to the current neutral collar."""
    v, d = surface.positions(vertices), surface.positions(old_delta)
    distance = np.asarray(geodesic_distance, dtype=float)
    if d.shape != v.shape or distance.shape != (len(v),) or np.isnan(distance).any() or (distance < 0).any():
        raise ValueError('Invalid breast source delta/support distance')
    p = profile['fields']
    mask = np.linalg.norm(d, axis=1) / p['sourceAmplitude']
    mask *= smooth(distance / p['supportWidth'])
    mask *= smooth((abs(v[:, 0]) - p['midlineStart']) / p['midlineWidth'])
    bounds = np.asarray(p['bounds'])
    mask *= ((v > bounds[0]) & (v < bounds[1])).all(axis=1)
    mask, pairs = paired_mask(v, mask, p['mirrorTolerance'])
    # Symmetrization must never move a pinned boundary or escape the stated ROI.
    mask[distance == 0] = 0
    mask *= ((v > bounds[0]) & (v < bounds[1])).all(axis=1)
    lower = smooth((p['lowerTop'] - v[:, 2]) / p['lowerWidth'])
    zero = np.zeros(len(v))
    fields = {
        'mass': np.column_stack([np.sign(v[:, 0]) * p['massLateral'] * mask,
                                 p['massForward'] * mask, zero]),
        'lowerProjection': np.column_stack([zero, p['projectionForward'] * mask * lower,
                                            -p['projectionDown'] * mask * lower]),
        'sag': np.column_stack([zero, zero, -p['sagDown'] * mask * lower])}
    composite = sum(profile['coefficients'][name] * fields[name] for name in CHANNELS)
    return composite, fields, pairs


def attachment_metrics(collar, body_delta, head_delta):
    relative = head_delta[collar.anchors] - collar.binding.evaluate(body_delta)
    return {str(value): float(np.linalg.norm(value * relative, axis=1).max())
            for value in (0., .5, 1.)}


def require_exportable_composite(delta):
    """Reject empty/nonfinite/unrepresentable local key deltas before writes."""
    delta = surface.positions(delta)
    if not len(delta) or np.max(abs(delta)) > np.finfo(np.float32).max:
        raise ValueError('Breast composite is not representable by the exporter')
    if not np.any(abs(delta) > TRIP_COMPONENT_EPSILON):
        raise ValueError('Breast composite is empty or below the TRIP component threshold')
    return delta


def load_tripfile_type():
    """Use the active add-on, or its configured public module outside Blender."""
    try:
        from io_scene_nifly.tri.tripfile import TripFile
        return TripFile
    except ModuleNotFoundError:
        # The ignored standalone-build configuration owns machine paths. Loading
        # this dependency-free module avoids importing bpy in numeric/unit tools.
        import locate
        config = locate.local_config(Path(__file__))
        filename = Path(config.get('pynifly', '')) / 'tri' / 'tripfile.py'
        if not filename.is_file():
            raise RuntimeError('TRIP verification requires active PyNifly or build.local.json pynifly')
        spec = importlib.util.spec_from_file_location('claw_pynifly_tripfile', filename)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.TripFile


def verify_serialized_morphs(nif_path, expected_names):
    """Read the actual exported TRIP, not Blender's pre-serialization key list."""
    filename = Path(nif_path).with_suffix('.tri')
    trip = load_tripfile_type().from_filepath(str(filename))
    if not trip.is_valid:
        raise ValueError('Breast shape export did not produce a valid TRIP')
    actual = {name for morphs in trip.shapes.values() for name in morphs
              if name.startswith('CLAW')}
    expected = set(expected_names)
    if actual != expected:
        raise ValueError('Serialized TRI public morph contract mismatch: missing=%s extra=%s'
                         % (sorted(expected - actual), sorted(actual - expected)))
    return {'publicMorphs': sorted(actual), 'triSha256': hashlib.sha256(filename.read_bytes()).hexdigest()}


def replace_fields(session, fields, key_name, epsilon):
    """Clear old nonzero contributions too; never retain the legacy body field."""
    for name, delta in fields.items():
        keys = session.objects[name].data.shape_keys
        exists = keys is not None and keys.key_blocks.get(key_name) is not None
        if exists or np.max(abs(delta)) > epsilon:
            session._put_delta(name, key_name, delta)


def invariant_digest(objects):
    """Neutral geometry, UV loops and all original group weights (not key data)."""
    result = {}
    for name, obj in objects.items():
        obj.data.calc_loop_triangles()
        digest = hashlib.sha256()
        digest.update(np.asarray([tuple(v.co) for v in obj.data.vertices], dtype='<f4').tobytes())
        digest.update(np.asarray([tuple(t.vertices) for t in obj.data.loop_triangles], dtype='<i8').tobytes())
        for layer in obj.data.uv_layers:
            digest.update(layer.name.encode('utf-8'))
            digest.update(np.asarray([tuple(loop.uv) for loop in layer.data], dtype='<f4').tobytes())
        names = {g.index: g.name for g in obj.vertex_groups}
        weights = [[(names[g.group], g.weight) for g in v.groups] for v in obj.data.vertices]
        digest.update(json.dumps(weights, separators=(',', ':')).encode('utf-8'))
        result[name] = digest.hexdigest()
    return result


def apply_profile(session, profile, log=print):
    """Blender adapter, after collar neutral correction and morph reconciliation."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    def projector(vertices, faces):
        tree = BVHTree.FromPolygons([Vector(p) for p in vertices], faces.tolist(), all_triangles=True)
        def project(point):
            nearest, _normal, index, distance = tree.find_nearest(Vector(point))
            if index is None:
                raise ValueError('Cannot project breast attachment')
            return np.asarray(nearest), index, distance
        return project

    before = invariant_digest(session.objects)
    key = '>' + PUBLIC_MORPH
    names_before = {k.name for obj in session.objects.values() if obj.data.shape_keys
                    for k in obj.data.shape_keys.key_blocks if k.name.startswith('>CLAW')}
    owners = {name for name, obj in session.objects.items() if obj.data.shape_keys
              and obj.data.shape_keys.key_blocks.get(key) is not None}
    allowed = set(profile['neutralShapes'])
    if not {'body', 'head'} <= owners or owners - allowed:
        raise ValueError('Unexpected BreastSize source shape ownership')
    vertices, faces = {}, {}
    for name, expected in profile['neutralShapes'].items():
        obj = session.objects[name]
        vertices[name] = np.asarray([obj.matrix_world @ v.co for v in obj.data.vertices], dtype=float)
        faces[name] = np.asarray([tuple(t.vertices) for t in obj.data.loop_triangles], dtype=int)
        surface.validate_geometry(vertices[name], faces[name], expected, profile['boundsTolerance'])
    source = session._key_delta('head', key)
    peak = float(np.linalg.norm(source, axis=1).max())
    if abs(peak - profile['source']['headPeak']) > profile['source']['headPeakTolerance']:
        raise ValueError('Unexpected repaired source BreastSize amplitude')
    rule = session.recipe['collars'][0]
    collar = surface.Collar(vertices['body'], faces['body'], vertices['head'], faces['head'],
                            rule, projector(vertices['body'], faces['body']))
    if len(collar.anchors) != profile['anchorCount']:
        raise ValueError('Breast support attachment count changed')
    head_delta, private_fields, pairs = shape_fields(vertices['head'], source,
        collar.distance[collar.inverse], profile)
    # Check the local coordinates the key writer will receive. Float32 rounding
    # at this neutral Basis can itself erase a tiny requested contribution.
    require_exportable_composite(head_delta)
    obj = session.objects['head']
    inverse = np.asarray(obj.matrix_world.to_3x3().inverted(), dtype=float)
    basis = np.asarray([tuple(v.co) for v in obj.data.shape_keys.key_blocks[0].data], dtype=float)
    local = head_delta @ inverse.T
    with np.errstate(over='ignore', invalid='ignore'):
        rounded_local = (basis + local).astype(np.float32).astype(float) - basis
    require_exportable_composite(rounded_local)
    values = {name: np.zeros_like(v) for name, v in vertices.items()}
    values['head'] = head_delta
    offsets = attachment_metrics(collar, values['body'], head_delta)
    # Also check the original frozen donor bindings used by the repair session.
    donor_offsets = [attachment_metrics(c, values['body'], head_delta)
                     for r, c in session.collars if r['source'] == 'body' and r['target'] == 'head']
    if max(offsets.values()) > 1e-8 or any(max(m.values()) > 1e-8 for m in donor_offsets):
        raise ValueError('Breast field breaks a repaired body/head attachment')
    skin = np.concatenate([vertices['body'], vertices['head']])
    skin_faces = np.concatenate([faces['body'], faces['head'] + len(vertices['body'])])
    skin_delta = np.concatenate([values['body'], head_delta])
    for layer_rule in session.recipe['layers']:
        name = layer_rule['shape']
        layer = surface.Layer(vertices[name], faces[name], skin, skin_faces,
                              layer_rule, projector(skin, skin_faces))
        values[name] = layer.reconcile(values[name], skin_delta)
    replace_fields(session, values, key, session.recipe['fieldEpsilon'])
    after = invariant_digest(session.objects)
    if before != after:
        raise ValueError('Breast profile changed neutral geometry, UVs, topology or weights')
    public_names = sorted({k.name[1:] for obj in session.objects.values() if obj.data.shape_keys
                           for k in obj.data.shape_keys.key_blocks if k.name.startswith('>CLAW')})
    if {name[1:] for name in names_before} != set(public_names):
        raise ValueError('Breast profile changed the public morph name contract')
    if any(name.startswith('CLAWProto') for name in public_names):
        raise ValueError('Private breast fields leaked into public morph names')
    v, t = vertices['head'], faces['head']
    old_normal = np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]])
    nv = v + head_delta
    new_normal = np.cross(nv[t[:, 1]] - nv[t[:, 0]], nv[t[:, 2]] - nv[t[:, 0]])
    report = {'profile': profile['name'], 'publicMorph': PUBLIC_MORPH,
              'status': 'shape-only-candidate-visual-and-runtime-acceptance-pending',
              'sourceHeadPeak': peak, 'privateFieldPeaks': {name: float(np.linalg.norm(d, axis=1).max())
                    for name, d in private_fields.items()},
              'newHeadPeak': float(np.linalg.norm(head_delta, axis=1).max()),
              'headVerticesMoved': int((np.linalg.norm(head_delta, axis=1) > 1e-8).sum()),
              'anchorCount': len(collar.anchors), 'relativeAttachmentOffsetError': offsets,
              'frozenDonorAttachmentOffsetError': donor_offsets,
              'bodyPeak': float(np.linalg.norm(values['body'], axis=1).max()),
              'faceBeyondY45Peak': float(np.linalg.norm(head_delta[v[:, 1] > 45], axis=1).max()),
              'pairedSymmetryMaxError': max([float(np.linalg.norm(head_delta[i] -
                   head_delta[j] * [-1, 1, 1])) for i, j in pairs] or [0]),
              'mirroredPairCount': len(pairs),
              'unpairedPositiveMovedVertices': int(((v[:, 0] > 0) &
                    (np.linalg.norm(head_delta, axis=1) > 1e-8)).sum()) - len(pairs),
              'headNormalReversalsAtFull': int(((old_normal * new_normal).sum(axis=1) < 0).sum()),
              'layerPeaks': {name: float(np.linalg.norm(values[name], axis=1).max())
                             for name in values if name not in ('body', 'head')},
              'publicMorphs': public_names, 'neutralTopologyUvWeightsDigest': after}
    log('BREAST_SHAPE|' + json.dumps(report, sort_keys=True))
    return report
