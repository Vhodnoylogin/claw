"""Experimental post-export head-collar weights; no default build integration.

NumPy geometry/LBS functions are independent of Blender. The adapter uses public
PyNifly methods and verifies the serialized NIF, not an in-memory success claim.
"""
from __future__ import annotations

import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path
import sys

import numpy as np
import surface_collar as surface

REPO = Path(__file__).resolve().parents[4]
CANONICAL_NIF = 'meshes/actors/werewolfbeast/character assets/femalebodywerewolf.nif'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def number(value, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value):
        raise ValueError('Expected a finite numeric profile value')
    if positive and value <= 0:
        raise ValueError('Expected a positive numeric profile value')
    return value


def integer(value, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError('Expected an integer profile value')
    return value


def validate_profile(profile):
    if profile.get('schemaVersion') != 1:
        raise ValueError('Unsupported collar weight profile')
    pins = profile['pins']
    for name in ('nifSha256', 'triSha256', 'skeletonSha256'):
        value = pins[name]
        if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('Invalid exact input hash pin')
    for name in ('nodeCount', 'publicMorphCount', 'anchorCount', 'activeVertexCount'):
        integer(pins[name], 1)
    anchors = profile['anchors']
    if len(anchors) != pins['anchorCount']:
        raise ValueError('Pinned anchor count mismatch')
    seen = set()
    for row in anchors:
        head = integer(row['head'])
        integer(row['bodyTriangle'])
        if head in seen:
            raise ValueError('Duplicate head anchor')
        seen.add(head)
        bary = np.asarray([number(v) for v in row['barycentric']], dtype=float)
        if bary.shape != (3,) or np.min(bary) < 0 or abs(bary.sum() - 1) > 1e-8:
            raise ValueError('Invalid barycentric attachment')
    collar = profile['collar']
    number(collar['width'], True)
    integer(collar['weldDecimals'])
    integer(collar['maxIterations'], 1)
    number(collar['solverTolerance'], True)
    number(collar['faceMinY'])
    fit = profile['fitting']
    if integer(fit['maxInfluences'], 1) != 4:
        raise ValueError('This MVP requires the four-influence contract')
    number(fit['referenceRegularizer'], True)
    number(fit['supportEpsilon'], True)
    controls = profile['poses']['ordinaryControls']
    if not controls or len({x['bone'] for x in controls}) != len(controls):
        raise ValueError('Expected distinct ordinary pose controls')
    for control in controls:
        if not isinstance(control['bone'], str) or 'Breast' in control['bone']:
            raise ValueError('Collar stage cannot introduce a breast-bone control')
        number(control['degrees'], True)
    integer(profile['poses']['seed'])
    integer(profile['poses']['heldoutCount'], 1)
    relative = Path(profile['relativeNifPath'])
    if relative.is_absolute() or '..' in relative.parts or ':' in str(relative) or relative.suffix.lower() != '.nif':
        raise ValueError('Invalid relative output NIF path')
    if profile['relativeNifPath'] != CANONICAL_NIF:
        raise ValueError('Output must retain the pinned BODYTRI-relative filename')
    return profile


def guard_output(path, inputs=(), forbidden_roots=()):
    path = Path(path)
    resolved = path.resolve()
    if path.exists() or path.is_symlink():
        raise ValueError('Output directory must be new; overwrite is forbidden')
    if not resolved.parent.is_dir():
        raise ValueError('Output directory parent must already exist')
    if any(part.lower() in ('data', 'mods', 'overwrite') for part in resolved.parts):
        raise ValueError('Output must be external staging, outside Data/mods/Overwrite trees')
    for root in (REPO, *forbidden_roots):
        if resolved.is_relative_to(Path(root).resolve()):
            raise ValueError('Output must be outside source/live directories')
    for source in inputs:
        if Path(source).resolve().is_relative_to(resolved):
            raise ValueError('Output directory cannot contain an input')
    return resolved


def validate_inputs(nif, tri, skeleton, profile):
    validate_profile(profile)
    paths = [Path(p).resolve(strict=True) for p in (nif, tri, skeleton)]
    if len(set(paths)) != 3 or any(not p.is_file() for p in paths):
        raise ValueError('Expected three distinct input files')
    for p, name in zip(paths, ('nifSha256', 'triSha256', 'skeletonSha256')):
        if sha256(p) != profile['pins'][name]:
            raise ValueError('Unsupported exact input: ' + name)
    return paths


def dependencies(addon_path=None):
    """Machine paths come from explicit CLI input or ignored build.local.json."""
    if addon_path is None:
        import locate
        addon_path = locate.local_config(REPO).get('pynifly')
    if not addon_path:
        raise ValueError('Configure PyNifly in build.local.json or --pynifly')
    addon = Path(addon_path).resolve(strict=True)
    sys.path.insert(0, str(addon))
    from pyn import pynifly
    pynifly.NifFile.Load(str(addon / 'NiflyDLL.dll'))
    spec = importlib.util.spec_from_file_location('claw_collar_tripfile', addon / 'tri/tripfile.py')
    trip = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(trip)
    return pynifly, trip.TripFile, addon


def matrix(transform):
    result = np.eye(4)
    result[:3, :3] = np.asarray(transform.rotation) * float(transform.scale)
    result[:3, 3] = list(transform.translation)
    return result


def normalize(weights):
    weights = np.asarray(weights, dtype=float)
    if weights.ndim != 2 or not np.isfinite(weights).all() or weights.min() < 0 or (weights.sum(axis=1) <= 0).any():
        raise ValueError('Expected finite nonnegative weights with positive row sums')
    return weights / weights.sum(axis=1)[:, None]


def rotation(axis, degrees):
    angle = math.radians(degrees)
    c, s = math.cos(angle), math.sin(angle)
    result = np.eye(4)
    i, j = ((1, 2), (2, 0), (0, 1))[axis]
    result[i, i] = result[j, j] = c
    result[j, i], result[i, j] = s, -s
    return result


def pose_definitions(profile):
    controls = profile['poses']['ordinaryControls']
    poses = [('rest', {})]
    for control in controls:
        bone, degrees = control['bone'], control['degrees']
        for axis in range(3):
            for sign in (-1, 1):
                poses.append((f'{bone}:{axis}:{sign * degrees}', {bone: rotation(axis, sign * degrees)}))
    train_count = len(poses)
    rng = np.random.default_rng(profile['poses']['seed'])
    for i in range(profile['poses']['heldoutCount']):
        edits = {c['bone']: rotation(int(rng.integers(3)), float(rng.uniform(-c['degrees'], c['degrees'])))
                 for c in controls}
        poses.append((f'heldout-combined-{i}', edits))
    return poses, train_count


def sparse_fit(points, target, reference, fitting):
    """Nonnegative simplex fit using at most four existing donor supports."""
    points, target, reference = np.asarray(points), np.asarray(target), np.asarray(reference)
    if points.ndim != 3 or points.shape[2] != 3 or target.shape != (len(points), 3) or reference.shape != (points.shape[1],):
        raise ValueError('Invalid sparse fit arrays')
    if not all(np.isfinite(a).all() for a in (points, target, reference)) or np.min(reference) < 0:
        raise ValueError('Nonfinite/negative sparse fit input')
    columns = (points - points[:1]).transpose(0, 2, 1).reshape(-1, points.shape[1])
    wanted = (target - target[:1]).reshape(-1)
    support = np.flatnonzero(reference > fitting['supportEpsilon'])
    best = None
    regularizer = fitting['referenceRegularizer']
    for count in range(1, min(4, len(support)) + 1):
        for indices in itertools.combinations(support, count):
            indices = np.asarray(indices)
            values = columns[:, indices]
            hessian = values.T @ values + regularizer * np.eye(count)
            system = np.block([[hessian, np.ones((count, 1))], [np.ones((1, count)), np.zeros((1, 1))]])
            rhs = np.r_[values.T @ wanted + regularizer * reference[indices], 1.]
            answer = np.linalg.lstsq(system, rhs, rcond=1e-12)[0][:count]
            if answer.min() < -1e-9:
                continue
            answer = np.maximum(answer, 0)
            answer /= answer.sum()
            error = values @ answer - wanted
            objective = float(error @ error) + regularizer * float(np.sum((answer - reference[indices]) ** 2))
            if best is None or objective < best[0]:
                result = np.zeros_like(reference)
                result[indices] = answer
                best = objective, result
    if best is None:
        raise ValueError('No finite four-influence simplex solution')
    return best[1]


def blend_band(vertices, faces, anchors, seed_weights, old_weights, collar):
    """Absolute harmonic weight blend; outside the narrow band stays fixed."""
    import heapq
    first, inverse, graph = surface.welded_graph(vertices, faces, collar['weldDecimals'])
    seeds = inverse[anchors]
    if len(set(seeds)) != len(seeds):
        raise ValueError('Pinned anchors must have distinct welded solver vertices')
    distance = np.full(len(first), np.inf)
    queue = []
    for i in seeds:
        distance[i] = 0
        heapq.heappush(queue, (0, int(i)))
    while queue:
        d, i = heapq.heappop(queue)
        if d != distance[i] or d >= collar['width']:
            continue
        for j, length in graph[i]:
            proposal = d + length
            if proposal < distance[j]:
                distance[j] = proposal
                heapq.heappush(queue, (proposal, j))
    free = np.asarray([i for i in np.flatnonzero(distance < collar['width']) if i not in set(seeds)], dtype=int)
    field = old_weights[first].copy()
    field[seeds] = seed_weights
    for iteration in range(collar['maxIterations']):
        new = field.copy()
        for i in free:
            adjacent = graph[i]
            weights = np.asarray([1 / length for _, length in adjacent])
            new[i] = (field[[j for j, _ in adjacent]] * weights[:, None]).sum(axis=0) / weights.sum()
        error = float(abs(new - field).max())
        field = new
        if error < collar['solverTolerance']:
            break
    else:
        raise ValueError('Collar weight solver did not converge')
    active = np.flatnonzero(distance[inverse] < collar['width'])
    return field[inverse], active, distance[inverse], {'iterations': iteration + 1, 'residual': error, 'freeWeldVertices': len(free)}


def exact_half_weights(weights):
    """Choose nearby half values summing exactly to one; never add a support."""
    target = np.asarray(weights, dtype=float)
    if target.ndim != 1 or not np.isfinite(target).all() or target.min() < 0 or abs(target.sum() - 1) > 1e-9:
        raise ValueError('Invalid normalized weight vector')
    ids = np.flatnonzero(target > 0)
    if not 1 <= len(ids) <= 4:
        raise ValueError('Half packing requires one to four influences')
    rounded = target[ids].astype(np.float16)
    best = None
    for steps in itertools.product((-1, 0, 1), repeat=len(ids)):
        values = rounded.copy()
        for j, step in enumerate(steps):
            if step:
                values[j] = np.nextafter(values[j], np.float16(np.inf if step > 0 else -np.inf), dtype=np.float16)
        values = values.astype(float)
        for j in range(len(values)):
            proposed = values.copy()
            proposed[j] += 1 - proposed.sum()
            if proposed.min() < 0 or proposed.max() > 1 or float(np.float16(proposed[j])) != proposed[j]:
                continue
            score = float(np.sum((proposed - target[ids]) ** 2))
            if best is None or score < best[0]:
                result = np.zeros_like(target)
                result[ids] = proposed
                best = score, result
    if best is None:
        raise ValueError('Cannot represent normalized weights within the bounded half neighborhood')
    return best[1]


def write_active_weights(shape, weights, active, names):
    """Absent map entries do not clear old packed slots: explicit zeros first."""
    columns = {name: i for i, name in enumerate(names)}
    if any(names[i] not in shape.bone_weights for i in np.flatnonzero(weights[active].sum(axis=0))):
        raise ValueError('Weight repair cannot add bone references')
    bones = list(shape.bone_weights)
    for bone in bones:
        shape.setShapeWeights(bone, [(int(i), 0.) for i in active])
    for bone in bones:
        column = columns[bone]
        shape.setShapeWeights(bone, [(int(i), float(weights[i, column])) for i in active if weights[i, column] > 0])


def stat(value):
    value = np.asarray(value, dtype=float)
    return {'n': int(value.size), 'p95': float(np.quantile(value, .95)) if value.size else 0.,
            'max': float(value.max()) if value.size else 0.,
            'rms': float(np.sqrt(np.mean(value * value))) if value.size else 0.}


class Model:
    """Actual input NIF binds and pinned XP32 globals; no assumed identity C."""
    def __init__(self, nif, skeleton, profile):
        self.nif, self.skeleton = nif, skeleton
        self.shapes = {shape.name: shape for shape in nif.shapes}
        if len(nif.nodes) != profile['pins']['nodeCount'] or not {'body', 'head'} <= set(self.shapes):
            raise ValueError('Unsupported carrier node/shape contract')
        self.names = sorted({bone for shape in nif.shapes for bone in shape.bone_weights})
        self.index = {name: i for i, name in enumerate(self.names)}
        if not set(self.names) <= set(skeleton.nodes):
            raise ValueError('A weighted bone is absent from the pinned skeleton')
        self.rest = {name: matrix(node.global_transform) for name, node in skeleton.nodes.items()}
        local = {name: np.linalg.inv(self.rest[node.parent.name]) @ self.rest[name] if node.parent else self.rest[name]
                 for name, node in skeleton.nodes.items()}
        self.poses, self.train_count = pose_definitions(profile)
        transforms = []
        for _, edits in self.poses:
            if not set(edits) <= set(skeleton.nodes):
                raise ValueError('Pose control absent from skeleton')
            posed = {}
            def visit(name):
                if name not in posed:
                    parent = skeleton.nodes[name].parent
                    posed[name] = (visit(parent.name) if parent else np.eye(4)) @ local[name] @ edits.get(name, np.eye(4))
                return posed[name]
            transforms.append([visit(name) for name in self.names])
        self.transforms = np.asarray(transforms)
        self.delta_transforms = np.einsum('pbjk,bkl->pbjl', self.transforms,
            np.asarray([np.linalg.inv(self.rest[name]) for name in self.names]))
        self.weights, self.binds = {}, {}
        for name, shape in self.shapes.items():
            self.weights[name] = self.weight_matrix(shape)
            binds = np.zeros((len(self.names), 4, 4))
            for bone in shape.bone_weights:
                bind = shape.get_shape_skin_to_bone(bone)
                if bind is None:
                    raise ValueError('Missing existing skin bind: ' + bone)
                binds[self.index[bone]] = matrix(bind) @ matrix(shape.global_to_skin)
            self.binds[name] = binds
        # Public NIF setters mutate this carrier in place. Preserve plain,
        # detached pre-write metadata; comparing against that same live object
        # would let a setter-induced bind/geometry mutation validate itself.
        def frozen(value):
            result = np.array(value, copy=True)
            result.setflags(write=False)
            return result
        self.original_nodes = {name: {'parent': node.parent.name if node.parent else None,
            'global': frozen(matrix(node.global_transform))} for name, node in nif.nodes.items()}
        self.original_shapes = {}
        for name, shape in self.shapes.items():
            self.original_shapes[name] = {
                'vertices': frozen(shape.verts), 'triangles': frozen(shape.tris), 'uvs': frozen(shape.uvs),
                'boneNames': tuple(shape.bone_names), 'boneIds': tuple(shape.bone_ids),
                'globalToSkin': frozen(matrix(shape.global_to_skin)),
                'binds': {bone: frozen(matrix(shape.get_shape_skin_to_bone(bone))) for bone in shape.bone_weights}}
            self.weights[name].setflags(write=False)
            self.binds[name].setflags(write=False)
        self.anchors = np.asarray([row['head'] for row in profile['anchors']], dtype=int)
        triangles = np.asarray(self.shapes['body'].tris)
        indices = np.asarray([row['bodyTriangle'] for row in profile['anchors']], dtype=int)
        if self.anchors.max() >= len(self.shapes['head'].verts) or indices.max() >= len(triangles):
            raise ValueError('Pinned attachment index outside input shape')
        self.triangles = triangles[indices]
        self.bary = np.asarray([row['barycentric'] for row in profile['anchors']])
        self.body_bary_weights = (normalize(self.weights['body'])[self.triangles] * self.bary[:, :, None]).sum(axis=1)
        target_bones = {self.names[j] for j in np.flatnonzero(self.body_bary_weights.sum(axis=0))}
        if not target_bones <= set(self.shapes['head'].bone_weights):
            raise ValueError('Body-bary transfer would require a new head bone reference')
        count = len(self.poses)
        self.body_tri_positions = {mode: self.evaluate('body', self.triangles.ravel(), normalized=mode).reshape(count, len(self.anchors), 3, 3)
                                   for mode in (False, True)}
        self.body_points = {mode: (value * self.bary[None, :, :, None]).sum(axis=2)
                            for mode, value in self.body_tri_positions.items()}
        self.base_head = {mode: self.evaluate('head', self.anchors, normalized=mode) for mode in (False, True)}
        rotation_blend = np.einsum('nb,pbij->pnij', self.body_bary_weights, self.delta_transforms[:, :, :3, :3])
        self.expected = {mode: self.body_points[mode] + np.einsum('pnij,nj->pni', rotation_blend,
            self.base_head[mode][0] - self.body_points[mode][0]) for mode in (False, True)}
        self.pose_sets = {'ordinary': np.arange(self.train_count),
                          'unseenCombined': np.arange(self.train_count, count)}

    def weight_matrix(self, shape):
        result = np.zeros((len(shape.verts), len(self.names)))
        for bone, pairs in shape.bone_weights.items():
            if bone not in self.index:
                raise ValueError('Unexpected serialized bone reference')
            for i, value in pairs:
                result[i, self.index[bone]] += value
        normalize(result)  # validate only; retain packed sums here
        return result

    def points(self, name, ids):
        vertices = self.original_shapes[name]['vertices'][ids]
        homogeneous = np.c_[vertices, np.ones(len(vertices))]
        effective = np.einsum('pbjk,bkl->pbjl', self.transforms, self.binds[name])
        return np.einsum('pbjk,nk->pnbj', effective, homogeneous)[..., :3]

    def evaluate(self, name, ids, weights=None, normalized=True):
        weights = self.weights[name][ids] if weights is None else weights
        if normalized:
            weights = normalize(weights)
        return np.einsum('pnbj,nb->pnj', self.points(name, ids), weights)


def plan_weights(model, profile):
    bar, anchors = model.body_bary_weights, model.anchors
    point = model.points('head', anchors)
    fitting, train = profile['fitting'], model.train_count
    seed_weights = np.asarray([sparse_fit(point[:train, i], model.expected[True][:train, i], bar[i], fitting)
                               for i in range(len(anchors))])
    head = model.shapes['head']
    vertices, faces = np.asarray(head.verts), np.asarray(head.tris)
    old = normalize(model.weights['head'])
    full, active, distance, solver = blend_band(vertices, faces, anchors, seed_weights, old, profile['collar'])
    if len(active) != profile['pins']['activeVertexCount']:
        raise ValueError('Pinned active collar vertex count changed')
    if (vertices[active, 1] > profile['collar']['faceMinY']).any():
        raise ValueError('Weight collar reaches the protected face')
    point = model.points('head', active)
    desired = np.einsum('pnbj,nb->pnj', point, full[active])
    candidate = model.weights['head'].copy()
    lookup = {int(i): j for j, i in enumerate(anchors)}
    mathematical = candidate.copy()
    for j, i in enumerate(active):
        fitted = seed_weights[lookup[i]] if i in lookup else sparse_fit(point[:train, j], desired[:train, j], full[i], fitting)
        mathematical[i] = fitted
        candidate[i] = exact_half_weights(fitted)
    outside = np.ones(len(vertices), dtype=bool)
    outside[active] = False
    if not np.array_equal(candidate[outside], model.weights['head'][outside]):
        raise ValueError('Planner changed packed weights outside its collar')
    removed_old = np.sum(np.where(mathematical <= 1e-12, old, 0), axis=1)
    removed_bary = np.sum(np.where(mathematical[anchors] <= 1e-12, bar, 0), axis=1)
    full_prediction = np.einsum('pnbj,nb->pnj', model.points('head', anchors), bar)
    report = {'activeVertices': len(active), 'anchorCount': len(anchors), 'solver': solver,
              'bodyBaryInfluenceCounts': {str(i): int(((bar > 1e-12).sum(axis=1) == i).sum())
                                         for i in np.unique((bar > 1e-12).sum(axis=1))},
              'fullBlendMaxInfluences': int((full[active] > 1e-12).sum(axis=1).max()),
              'oldSupportMassRemoved': stat(removed_old[active]),
              'bodyBarySupportMassRemoved': stat(removed_bary),
              'halfPackingMaxAbsAdjustment': float(abs(candidate[active] - mathematical[active]).max()),
              'directBaryCovarianceResidual': {name: stat(np.linalg.norm(full_prediction - model.expected[True], axis=-1)[ids])
                                                for name, ids in model.pose_sets.items()},
              'covarianceNote': 'Residual of direct weight interpolation; not a global lower bound on every fitted skinning solution.'}
    return candidate, active, report


def triangle_distances(point, triangles):
    """Distance and signed plane gap to each actual posed frozen donor triangle."""
    a, b, c = (triangles[:, :, i] for i in range(3))
    ab, ac, ap = b - a, c - a, point - a
    normal = np.cross(ab, ac)
    length = np.linalg.norm(normal, axis=-1, keepdims=True)
    if (length <= 1e-12).any():
        raise ValueError('Degenerate posed donor triangle')
    normal /= length
    signed = (ap * normal).sum(axis=-1)
    projection = point - normal * signed[:, :, None]
    aq = projection - a
    d00, d01, d11 = (ab * ab).sum(axis=-1), (ab * ac).sum(axis=-1), (ac * ac).sum(axis=-1)
    d20, d21 = (aq * ab).sum(axis=-1), (aq * ac).sum(axis=-1)
    denominator = d00 * d11 - d01 * d01
    v, w = (d11 * d20 - d01 * d21) / denominator, (d00 * d21 - d01 * d20) / denominator
    distance = np.where((v >= 0) & (w >= 0) & (v + w <= 1), abs(signed), np.inf)
    for x, y in ((a, b), (b, c), (c, a)):
        edge = y - x
        u = np.clip(((point - x) * edge).sum(axis=-1) / (edge * edge).sum(axis=-1), 0, 1)
        distance = np.minimum(distance, np.linalg.norm(point - (x + u[:, :, None] * edge), axis=-1))
    return distance, signed


def pose_metrics(model, weights):
    report = {'reference': 'actual posed body barypoint + donor-bary weighted posedGlobal*inverse(restGlobal) 3x3 applied to original actual-bind rest offset; includes old common-C frame, permits natural LBS rotation/stretch',
              'note': 'Weighted-offset error, absolute triangle distance and normal-gap change are distinct. World-fixed offset drift alone is not proof of a gap. Raw-packed/normalized modes are hypothetical LBS evaluations, not engine shader claims.',
              'fittingPoseCount': model.train_count, 'unseenPoseCount': len(model.poses) - model.train_count,
              'modes': {}}
    for mode in (False, True):
        entries = {}
        for label, point in (('baseline', model.base_head[mode]),
                             ('candidate', model.evaluate('head', model.anchors, weights[model.anchors], normalized=mode))):
            distance, signed = triangle_distances(point, model.body_tri_positions[mode])
            offset = point - model.body_points[mode]
            arrays = {'weightedOffsetError': np.linalg.norm(point - model.expected[mode], axis=-1),
                      'absoluteTriangleDistance': distance,
                      'triangleDistanceChange': abs(distance - distance[:1]),
                      'absoluteNormalGap': abs(signed), 'normalGapChange': abs(signed - signed[:1]),
                      'offsetLengthChange': abs(np.linalg.norm(offset, axis=-1) - np.linalg.norm(offset[:1], axis=-1)),
                      'worldFixedOffsetDrift': np.linalg.norm(offset - offset[:1], axis=-1)}
            entries[label] = {name: {group: stat(values[ids]) for group, ids in model.pose_sets.items()}
                              for name, values in arrays.items()}
            entries[label]['neutralTriangleDistance'] = stat(distance[0])
            entries[label]['restOffsetChangeMax'] = float(np.linalg.norm(point[0] - model.base_head[mode][0], axis=-1).max())
            entries[label]['normalSignCrossings'] = {group: int((signed[ids] * signed[:1] < 0).sum())
                                                     for group, ids in model.pose_sets.items()}
        report['modes']['normalized' if mode else 'rawPacked'] = entries
    return report


def verify_readback(model, result, planned, active):
    """Fail closed on any change beyond the explicitly allowed packed weights."""
    if set(result.nodes) != set(model.original_nodes):
        raise ValueError('Serialized node set changed')
    for name, node in result.nodes.items():
        old = model.original_nodes[name]
        parent = node.parent.name if node.parent else None
        if parent != old['parent'] or not np.array_equal(matrix(node.global_transform), old['global']):
            raise ValueError('Serialized node ancestry/matrix changed')
    shapes = {s.name: s for s in result.shapes}
    if set(shapes) != set(model.original_shapes):
        raise ValueError('Serialized shape set changed')
    report = {}
    outside = np.ones(len(planned), dtype=bool)
    outside[active] = False
    actual_head = None
    for name, old in model.original_shapes.items():
        shape = shapes[name]
        if not all(np.array_equal(value, expected) for value, expected in (
                (shape.verts, old['vertices']), (shape.tris, old['triangles']), (shape.uvs, old['uvs']))):
            raise ValueError('Serialized neutral geometry/topology/UV changed: ' + name)
        if tuple(shape.bone_names) != old['boneNames'] or tuple(shape.bone_ids) != old['boneIds']:
            raise ValueError('Serialized bone references changed: ' + name)
        if not np.array_equal(matrix(shape.global_to_skin), old['globalToSkin']):
            raise ValueError('Serialized global-to-skin changed: ' + name)
        for bone, expected in old['binds'].items():
            if not np.array_equal(matrix(shape.get_shape_skin_to_bone(bone)), expected):
                raise ValueError('Serialized skin bind changed: ' + name)
        weights = model.weight_matrix(shape)
        if name == 'head':
            if not np.array_equal(weights[outside], model.weights[name][outside]) or not np.array_equal(weights, planned):
                raise ValueError('Serialized head weights differ from the permitted exact-half plan')
            if np.max((weights[active] > 0).sum(axis=1)) > 4 or np.max(abs(weights[active].sum(axis=1) - 1)) != 0:
                raise ValueError('Serialized active weights violate four-slot/normalization contract')
            actual_head = weights
        elif not np.array_equal(weights, model.weights[name]):
            raise ValueError('Serialized other packed weights changed: ' + name)
        report[name] = {'neutralGeometryTopologyUvUnchanged': True, 'refsAndBindsUnchanged': True,
                        'changedWeightVertices': int((np.max(abs(weights - model.weights[name]), axis=1) > 0).sum())}
    return actual_head, {'nodeCount': len(result.nodes), 'shapes': report,
                         'outsidePackedWeightsExact': True, 'activePackedSumError': 0., 'maxInfluences': 4}


def repair(nif_path, tri_path, skeleton_path, profile_path, output_dir, addon_path=None):
    """Explicit standalone stage. Only a new external output directory is written."""
    profile_path = Path(profile_path).resolve(strict=True)
    profile = json.loads(profile_path.read_text(encoding='utf-8-sig'))
    inputs = validate_inputs(nif_path, tri_path, skeleton_path, profile)
    import locate
    config = locate.local_config(REPO)
    forbidden = [config['mods']] if config.get('mods') else []
    output = guard_output(output_dir, inputs, forbidden)
    pynifly, trip_type, addon = dependencies(addon_path)
    source_tri = trip_type.from_filepath(str(inputs[1]))
    public = sorted({name for morphs in source_tri.shapes.values() for name in morphs})
    if not source_tri.is_valid or len(public) != profile['pins']['publicMorphCount']:
        raise ValueError('Pinned public TRI contract mismatch')
    model = Model(pynifly.NifFile(str(inputs[0])), pynifly.NifFile(str(inputs[2])), profile)
    planned, active, planning = plan_weights(model, profile)
    # This pinned TRI has zero BreastSize movement at the common boundary, so
    # these anchor pose checks also cover BreastSize0/.5/1 without changing TRI.
    for name, ids in (('head', model.anchors), ('body', model.triangles.ravel())):
        delta = np.zeros((len(model.shapes[name].verts), 3))
        for i, value in source_tri.shapes.get(name, {}).get('CLAWTorsoBreastSize', []):
            delta[i] = value
        if np.max(abs(delta[ids])) != 0:
            raise ValueError('Pinned BreastSize boundary is no longer stationary')
    output.mkdir()
    target = output / profile['relativeNifPath']
    target.parent.mkdir(parents=True)
    write_active_weights(model.shapes['head'], planned, active, model.names)
    model.nif.filepath = str(target)
    model.nif.save()
    target.with_suffix('.tri').write_bytes(inputs[1].read_bytes())
    actual, verification = verify_readback(model, pynifly.NifFile(str(target)), planned, active)
    copied = trip_type.from_filepath(str(target.with_suffix('.tri')))
    actual_public = sorted({name for morphs in copied.shapes.values() for name in morphs})
    if sha256(target.with_suffix('.tri')) != profile['pins']['triSha256'] or not copied.is_valid or actual_public != public:
        raise ValueError('Serialized TRI bytes/public names changed')
    # Fail if an input changed concurrently as well as if this stage altered it.
    validate_inputs(*inputs, profile)
    report = {'schemaVersion': 1, 'status': 'experimental-local-candidate-not-complete-geometry-fix',
              'profile': profile['name'], 'inputs': {str(p): sha256(p) for p in inputs},
              'profileSha256': sha256(profile_path),
              'sourceSha256': {p.name: sha256(p) for p in (Path(__file__), REPO / 'src/main/python/build-tools/repair-collar-weights.py', REPO / 'src/main/python/build-tools/surface_collar.py')},
              'dependencySha256': {str(p): sha256(p) for p in (addon / 'NiflyDLL.dll', addon / 'pyn/pynifly.py', addon / 'tri/tripfile.py')},
              'outputs': {str(p.relative_to(output)): sha256(p) for p in (target, target.with_suffix('.tri'))},
              'publicMorphs': public, 'planning': planning, 'verification': verification,
              'activeHeadVertices': active.tolist(), 'breastAnchorStates': [0., .5, 1.],
              'capacityAfter': {str(i): int(((actual[model.anchors] > 0).sum(axis=1) == i).sum()) for i in range(1, 5)},
              'poses': pose_metrics(model, actual),
              'ordering': 'surface-collar geometry + moderate BreastSize export -> this85-node weight repair -> explicitly recomputed P1 capacity/weights/binds; old frozen P1 weights are invalid for the new base',
              'limitations': ['Controlled synthetic pose fitting is not animation/game/visual acceptance.',
                  'Only the104 head collar weights change; fur/root inheritance and P1 are excluded.',
                  'Raw-packed rest-offset shift and support mass removed are explicit report metrics; other packed weights are unchanged.',
                  'Weighted-offset error is not absolute gap distance or geometric-normal attachment.',
                  'Shoulder join, fur coverage, other morph combinations and bounds remain unqualified.',
                  'MVP exact input pins intentionally reject composed/rigged/later inputs; composition requires a new explicit measured profile.']}
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report
