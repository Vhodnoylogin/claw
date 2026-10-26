"""Pinned offline head/torso influence experiment; admission is separate from writing.

Only a bounded actual BreastSize support field and skin-root-selected fur cards
can change. Existing bind frames, P1 and every non-head/non-Spine2 weight survive.
A measured rejected NIF is diagnostic evidence, never an installable result.
"""
from __future__ import annotations

from pathlib import Path
import heapq
import json
import math
import shutil
import numpy as np
import breast_rig as rig
import surface_collar as surface
import vr_head
from collar_weights import write_active_weights
from fur_motion import exact_half_pair, snapshot

ROOT = Path(__file__).resolve().parents[1]
SPINE = 'NPC Spine2 [Spn2]'
MORPH = 'CLAWTorsoBreastSize'
CEILINGS = {
    'coreHideMaxDisplacement': .0001, 'ordinaryMaxNormalized': .25,
    'ordinaryMaxRawPacked': .325, 'ordinaryRms': .05, 'pureP1MaxChange': .005,
    'collarOffsetIncrease': .01, 'furRootResidualIncrease': .02,
    'maximumCardStrainChange': .01}


def strict_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate profile key: '+key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8-sig'), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite profile')))


def load_profile(path):
    p = strict_json(path)
    template = strict_json(ROOT/'recipes/vr-torso-weights.json')
    if set(p) != set(template) or type(p['schemaVersion']) is not int or p['schemaVersion'] != 1:
        raise ValueError('Unknown VR torso profile schema')
    for key in ('inputs', 'region', 'rigProfile', 'outputRelativeNif'):
        if p[key] != template[key]:
            raise ValueError('Frozen VR torso contract changed: '+key)
    if set(p['limits']) != set(template['limits']):
        raise ValueError('Unknown VR torso limits')
    for key, maximum in CEILINGS.items():
        value = p['limits'][key]
        if type(value) not in (float, int) or not math.isfinite(value) or not 0 < value <= maximum:
            raise ValueError('Invalid/weakened limit: '+key)
    minimum = p['limits']['minimumHideReduction']
    if type(minimum) not in (float, int) or not .9 <= minimum <= 1:
        raise ValueError('Invalid/weakened hide reduction')
    return p


def band_field(vertices, faces, seeds, width, decimals, protected=()):
    """Full seed removal; smooth welded-geodesic decay in one bounded band."""
    vertices = surface.positions(vertices)
    seeds = np.asarray(seeds, int)
    if width <= 0 or not math.isfinite(width) or not len(seeds):
        raise ValueError('Expected nonempty support and positive band width')
    first, inverse, graph = surface.welded_graph(vertices, faces, decimals)
    distance = np.full(len(first), np.inf); queue = []
    for index in np.unique(inverse[seeds]):
        distance[index] = 0.; heapq.heappush(queue, (0., int(index)))
    while queue:
        value, index = heapq.heappop(queue)
        if value != distance[index] or value >= width:
            continue
        for neighbor, length in graph[index]:
            proposal = value+length
            if proposal < distance[neighbor]:
                distance[neighbor] = proposal; heapq.heappush(queue, (proposal, neighbor))
    field = 1-rig.smooth(distance[inverse]/width)
    field[np.asarray(protected, int)] = 0
    return field


def transfer_head(weights, field, spine, head_columns):
    """Remove head descendants to an existing Spine2 palette entry, exactly packed.

    Exact preservation of a half pair's sum can leave a small head residual. It
    is measured rather than silently normalized away or rounded to zero.
    """
    old = np.asarray(weights, float)
    field = np.asarray(field, float)
    if (old.ndim != 2 or field.shape != (len(old),) or not np.isfinite(old).all()
            or old.min() < 0 or not np.isfinite(field).all() or field.min() < 0 or field.max() > 1
            or not np.array_equal(old.astype(np.float16).astype(float), old)
            or (old > 0).sum(axis=1).max() > 4):
        raise ValueError('Invalid packed weights or correction field')
    result = old.copy()
    for i in np.flatnonzero(field > 0):
        for j in head_columns:
            if result[i, j]:
                result[i, [spine, j]] = exact_half_pair(result[i, spine], result[i, j],
                                                      result[i, j]*(1-field[i]))
    other = [j for j in range(old.shape[1]) if j not in [spine, *head_columns]]
    if (not np.array_equal(result[:, other], old[:, other])
            or not np.array_equal(result.sum(axis=1), old.sum(axis=1))
            or (result > 0).sum(axis=1).max() > 4):
        raise ValueError('Transfer changed protected support/sums/four-slot budget')
    return result


class Model:
    def __init__(self, nif, skeleton, raw, rp):
        self.shapes = {s.name: s for s in nif.shapes}; self.raw = raw
        self.names = sorted({n for s in nif.shapes for n in s.bone_weights})
        self.index = {n: i for i, n in enumerate(self.names)}
        self.rest = {n: rig.matrix(node.global_transform) for n, node in skeleton.nodes.items()}
        self.parents = {n: node.parent.name if node.parent else None for n, node in skeleton.nodes.items()}
        if not set(self.names) <= set(self.rest):
            raise ValueError('Weighted node absent from pinned XP32')
        self.head_columns = [self.index[n] for n in sorted(vr_head.descendants(self.parents, vr_head.HEAD)) if n in self.index]
        self.poses = rig.pose_definitions(rp['p1Bones'], 3., int(rp['verification']['seed']))
        ordinary = rig.posed_globals(self.rest, self.parents, self.names, self.poses)
        self.hide_poses = vr_head.pose_bank(self.rest, self.parents)[1:]
        imposed = [vr_head.impose(self.rest, self.parents, replacements)
                   for _, replacements, _ in self.hide_poses]
        self.globals = np.r_[ordinary, np.asarray([[pose[n] for n in self.names] for pose in imposed])]
        self.ordinary = [i for i, x in enumerate(self.poses) if x[2] in ('ordinary', 'heldout')]
        self.pure_p1 = [i for i, x in enumerate(self.poses) if x[2].startswith('p1-')]
        self.combined_p1 = [i for i, x in enumerate(self.poses) if x[2] == 'combined-p1']
        self.hide_index = len(self.poses)
        self.weights = {n: rig.read_weights(s, self.names) for n, s in self.shapes.items()}
        self.vertices = {n: np.asarray(s.verts, float).copy() for n, s in self.shapes.items()}
        self.triangles = {n: np.asarray(s.tris, int).copy() for n, s in self.shapes.items()}
        self.deltas = {n: rig.dense_morph(raw, n, MORPH, len(s.verts)) for n, s in self.shapes.items()}
        self.effective = {}
        for name, shape in self.shapes.items():
            if not shape.has_global_to_skin:
                raise ValueError('Actual stored global-to-skin absent: '+name)
            binds = np.zeros((len(self.names), 4, 4))
            for bone in shape.bone_weights:
                bind = shape.get_shape_skin_to_bone(bone)
                if bind is None:
                    raise ValueError('Actual bone bind absent: '+bone)
                binds[self.index[bone]] = rig.matrix(bind)@rig.matrix(shape.global_to_skin)
            self.effective[name] = np.einsum('pbij,bjk->pbik', self.globals, binds)

    def evaluate(self, name, ids, coefficient, weights=None, normalized=True):
        ids = np.asarray(ids, int)
        weights = self.weights[name] if weights is None else weights
        selected = weights[ids]
        if normalized:
            selected = selected/selected.sum(axis=1)[:, None]
        vertices = self.vertices[name][ids]+coefficient*self.deltas[name][ids]
        homogeneous = np.c_[vertices, np.ones(len(ids))]
        result = np.zeros((len(self.globals), len(ids), 3))
        for j in np.flatnonzero(selected.sum(axis=0)):
            result += np.einsum('pij,nj->pni', self.effective[name][:, j, :3], homogeneous)*selected[None, :, j, None]
        return result


def plan(model, profile, rp):
    region = profile['region']; vertices = model.vertices['head']
    inside = surface.region_weight(vertices, region['bounds']) > 0
    core = np.flatnonzero(inside & np.any(model.deltas['head'] != 0, axis=1)
                          & (vertices[:, 1] < region['faceMinY']))
    collar = surface.Collar(model.vertices['body'], model.triangles['body'], vertices,
                           model.triangles['head'], rp['collar'],
                           rig.SurfaceProjector(model.vertices['body'], model.triangles['body']))
    if len(collar.anchors) != 55 or np.intersect1d(core, collar.anchors).size:
        raise ValueError('Breast core/collar contract changed')
    protected = np.unique(np.r_[collar.anchors, np.flatnonzero(vertices[:, 1] >= region['faceMinY'])])
    field = band_field(vertices, model.triangles['head'], core, region['bandWidth'],
                       region['weldDecimals'], protected)
    field[~inside] = 0
    fields = {'head': field}; plans = {}; spine = model.index[SPINE]
    skins = np.r_[model.vertices['body'], vertices]
    skin_faces = np.r_[model.triangles['body'], model.triangles['head']+len(model.vertices['body'])]
    skin_field = np.r_[np.zeros(len(model.vertices['body'])), field]
    layers = {}; selected = {}
    projector = rig.SurfaceProjector(skins, skin_faces)
    for rule in rp['layers']:
        name = rule['shape']; layer = surface.Layer(model.vertices[name], model.triangles[name], skins,
                                                  skin_faces, rule, projector)
        layers[name] = layer
        influence = layer.binding.evaluate(np.c_[skin_field, np.zeros((len(skins), 2))])[:, 0]
        field_layer = np.zeros(len(model.vertices[name])); groups = []
        if rule['mode'] == 'cards':
            for g, ids in enumerate(layer.groups):
                root = layer.binding.points[g]
                if (layer.weights[g] >= 1-1e-6 and influence[g] >= region['minimumRootField']
                        and surface.region_weight(np.asarray([root]), region['bounds'])[0]
                        and model.vertices[name][ids, 1].max() < region['faceMinY']):
                    field_layer[ids] = 1.; groups.append(g)
        fields[name] = field_layer; selected[name] = groups
    for name, field in fields.items():
        if SPINE not in model.shapes[name].bone_weights:
            raise ValueError('Correction requires an existing Spine2 palette entry: '+name)
        weights = transfer_head(model.weights[name], field, spine, model.head_columns)
        active = np.flatnonzero(np.any(weights != model.weights[name], axis=1))
        if len(active):
            plans[name] = {'weights': weights, 'active': active}
    if not plans:
        raise ValueError('No head-driven torso influence in the declared field')
    return plans, core, collar, layers, selected, fields


def verify_readback(before, actual, plans, names):
    after = snapshot(actual)
    if set(after['nodes']) != set(before['nodes']) or set(after['shapes']) != set(before['shapes']):
        raise ValueError('Node/shape inventory changed')
    for name, old in before['nodes'].items():
        new = after['nodes'][name]
        if old[0] != new[0] or old[3] != new[3] or any(not np.array_equal(a, b) for a, b in zip(old[1:3], new[1:3])):
            raise ValueError('Protected node ancestry/transform/extra changed: '+name)
    for name, old in before['shapes'].items():
        new = after['shapes'][name]
        for key in ('vertices', 'triangles', 'uvs', 'frame', 'normals', 'colors', 'transform'):
            if not np.array_equal(old[key], new[key]):
                raise ValueError('Protected shape field changed: '+name+'/'+key)
        for key in ('render', 'extras', 'partitions', 'hasFrame', 'bones'):
            if old[key] != new[key]:
                raise ValueError('Protected shape metadata changed: '+name+'/'+key)
        for bone, bind in old['binds'].items():
            if not np.array_equal(bind, new['binds'][bone]):
                raise ValueError('Protected skin bind changed: '+name+'/'+bone)
        if name not in plans and old['weights'] != new['weights']:
            raise ValueError('Unplanned shape weights changed: '+name)
    shapes = {s.name: s for s in actual.shapes}
    for name, entry in plans.items():
        if not np.array_equal(rig.read_weights(shapes[name], names), entry['weights']):
            raise ValueError('Actual packed weights differ from plan: '+name)
    return {'protectedMetadataEqual': True, 'actualPackedPlanEqual': True,
            'protectedShapeFields': ['geometry', 'UV', 'normals', 'colors', 'shapeTransforms', 'renderMetadata',
                                     'BODYTRI/extraData', 'partitions', 'skinPalette', 'binds', 'storedGlobalToSkin']}


def summary(values):
    arrays = [np.asarray(x, float).ravel() for x in values]
    array = np.concatenate(arrays) if arrays else np.asarray([], float)
    if array.size and not np.isfinite(array).all():
        raise ValueError('Nonfinite measurement')
    return {'n': int(array.size), 'max': float(array.max()) if array.size else 0.,
            'p95': float(np.quantile(array, .95)) if array.size else 0.,
            'rms': float(np.sqrt(np.mean(array*array))) if array.size else 0.}


def shape_metrics(model, plans, core):
    report = {}
    for name, entry in plans.items():
        ids = entry['active']; old = model.weights[name]; new = entry['weights']; rows = {}
        protected_ids = core if name == 'head' else ids
        for normalized in (True, False):
            mode = 'normalized' if normalized else 'rawPacked'
            ordinary = []; pure = []; before_hide = []; after_hide = []; imposed = []; combined = []; controlled = []
            for coefficient in (0., .5, 1.):
                a = model.evaluate(name, ids, coefficient, normalized=normalized)
                b = model.evaluate(name, ids, coefficient, new, normalized)
                error = np.linalg.norm(b-a, axis=-1)
                ordinary.append(error[model.ordinary]); pure.append(np.linalg.norm(
                    (b[model.pure_p1]-b[:1])-(a[model.pure_p1]-a[:1]), axis=-1))
                controlled.append(error[:len(model.poses)]); combined.append(error[model.combined_p1])
                imposed.append(error[model.hide_index:])
                a = model.evaluate(name, protected_ids, coefficient, normalized=normalized)
                b = model.evaluate(name, protected_ids, coefficient, new, normalized)
                before_hide.append(np.linalg.norm(a[model.hide_index]-a[0], axis=-1))
                after_hide.append(np.linalg.norm(b[model.hide_index]-b[0], axis=-1))
            rows[mode] = {'ordinaryChange': summary(ordinary), 'pureP1MotionChange': summary(pure),
                          'combinedP1ChangedMotion': summary(combined),
                          'all151ControlledChangedMotion': summary(controlled),
                          'headOnlyChangedMotion': summary(imposed),
                          'coreHideBefore': summary(before_hide), 'coreHideAfter': summary(after_hide)}
        report[name] = {'changedVertexCount': len(ids), 'changedVertices': ids.tolist(), 'measurements': rows,
                        'packedSumMaxError': float(abs(new.sum(axis=1)-1).max()),
                        'originalPackedSumsEqual': bool(np.array_equal(new.sum(axis=1), old.sum(axis=1))),
                        'maxInfluences': int((new > 0).sum(axis=1).max()),
                        'coreHeadMassBefore': float(old[protected_ids][:, model.head_columns].sum(axis=1).max()),
                        'coreHeadMassAfter': float(new[protected_ids][:, model.head_columns].sum(axis=1).max())}
    return report


def skin_attachment(model, skin_ids, coefficient, plans, normalized):
    body_count = len(model.vertices['body']); result = np.zeros((len(model.globals), len(skin_ids), 3, 3))
    for k in range(3):
        for name, take in [('body', skin_ids[:, k] < body_count), ('head', skin_ids[:, k] >= body_count)]:
            ids = skin_ids[take, k]-(body_count if name == 'head' else 0)
            if len(ids):
                w = plans[name]['weights'] if name in plans else model.weights[name]
                result[:, take, k] = model.evaluate(name, ids, coefficient, w, normalized)
    return result


def edge_change(old, new, edges):
    if not len(edges):
        return np.asarray([], float)
    old_length = np.linalg.norm(old[:, edges[:, 0]]-old[:, edges[:, 1]], axis=-1)
    new_length = np.linalg.norm(new[:, edges[:, 0]]-new[:, edges[:, 1]], axis=-1)
    if np.any(old_length[0] <= 1e-10):
        raise ValueError('Degenerate edge in measured component')
    return abs((new_length-old_length)/old_length[:1])


def join_metrics(model, plans, collar, layers):
    result = {'collar': {}, 'layers': {}}; body_count = len(model.vertices['body'])
    delta_rotation = np.einsum('pbij,bjk->pbik', model.globals,
                              np.asarray([np.linalg.inv(model.rest[n]) for n in model.names]))[:, :, :3, :3]
    for normalized in (True, False):
        mode = 'normalized' if normalized else 'rawPacked'; increase = []
        for coefficient in (0., .5, 1.):
            offsets = []
            for candidate in (False, True):
                planned = plans if candidate else {}
                body = model.evaluate('body', collar.binding.faces[collar.binding.indices].ravel(), coefficient,
                                      normalized=normalized).reshape(len(model.globals), len(collar.anchors), 3, 3)
                attach = (body*collar.binding.weights[None, :, :, None]).sum(axis=2)
                head = model.evaluate('head', collar.anchors, coefficient,
                                      plans['head']['weights'] if candidate and 'head' in plans else None, normalized)
                offsets.append(head-attach)
            a, b = [np.linalg.norm(x-x[:1], axis=-1) for x in offsets]
            increase.append(np.maximum(b-a, 0))
        result['collar'][mode] = {'offsetDriftIncrease': summary(increase)}
    changed_skin = np.r_[np.zeros(body_count, bool), np.any(plans['head']['weights'] != model.weights['head'], axis=1)]
    for name, layer in layers.items():
        skin_ids = layer.binding.faces[layer.binding.indices]
        changed = np.zeros(len(model.vertices[name]), bool)
        if name in plans:
            changed[plans[name]['active']] = True
        affected = np.flatnonzero(changed_skin[skin_ids].any(axis=1) |
                                 np.asarray([changed[ids].any() for ids in layer.groups]))
        if not len(affected):
            result['layers'][name] = {'affectedGroups': 0}; continue
        roots = np.asarray([next(int(i) for i in layer.groups[g]
                                 if np.array_equal(model.vertices[name][i], layer.binding.points[g])) for g in affected])
        ids = skin_ids[affected]; bary = layer.binding.weights[affected]
        full = layer.weights[affected] >= 1-1e-6
        all_ids = np.unique(np.concatenate([layer.groups[g] for g in affected if layer.weights[g] >= 1-1e-6])) if full.any() else np.asarray([], int)
        triangles = model.triangles[name]; triangles = triangles[np.all(np.isin(triangles, all_ids), axis=1)]
        edges = np.unique(np.sort(np.r_[triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]], axis=1), axis=0)
        local = {int(value): i for i, value in enumerate(all_ids)}
        edges = np.asarray([[local[int(a)], local[int(b)]] for a, b in edges], int)
        rows = {}
        for normalized in (True, False):
            mode = 'normalized' if normalized else 'rawPacked'; before = []; after = []; distance_increase = []; residual_increase = []; strain = []
            for coefficient in (0., .5, 1.):
                residuals = []; distances = []
                for candidate in (False, True):
                    selected = plans if candidate else {}
                    points = skin_attachment(model, ids, coefficient, selected, normalized)
                    attach = np.einsum('pgkj,gk->pgj', points, bary)
                    root = model.evaluate(name, roots, coefficient,
                                          plans[name]['weights'] if candidate and name in plans else None, normalized)
                    weighted = np.zeros((len(affected), len(model.names)))
                    for k in range(3):
                        for skin_name, take in [('body', ids[:, k] < body_count), ('head', ids[:, k] >= body_count)]:
                            at = ids[take, k]-(body_count if skin_name == 'head' else 0)
                            w = selected[skin_name]['weights'] if skin_name in selected else model.weights[skin_name]
                            weighted[take] += bary[take, k, None]*(w[at]/w[at].sum(axis=1)[:, None])
                    offset = root[0]-attach[0]
                    transported = np.einsum('gb,pbij,gj->pgi', weighted, delta_rotation, offset)
                    residuals.append(np.linalg.norm(root-attach-transported, axis=-1))
                    distance = np.linalg.norm(root-attach, axis=-1)
                    distances.append(abs(distance-distance[:1]))
                before.append(residuals[0]); after.append(residuals[1]); distance_increase.append(np.maximum(distances[1]-distances[0], 0))
                residual_increase.append(np.maximum(residuals[1]-residuals[0], 0))
                if len(all_ids):
                    a = model.evaluate(name, all_ids, coefficient, normalized=normalized)
                    b = model.evaluate(name, all_ids, coefficient,
                                       plans[name]['weights'] if name in plans else None, normalized)
                    strain.append(edge_change(a, b, edges))
            rows[mode] = {'rootTransportResidualBefore': summary(before), 'rootTransportResidualAfter': summary(after),
                          'pointwiseRootResidualIncrease': summary(residual_increase),
                          'rootDistanceDriftIncrease': summary(distance_increase), 'fullCardEdgeChange': summary(strain)}
        result['layers'][name] = {'affectedGroups': len(affected), 'groups': affected.tolist(), 'rootVertices': roots.tolist(),
                                'measurements': rows}
    return result


def admission(shapes, joins, limits):
    failures = []
    for name, row in shapes.items():
        for mode, values in row['measurements'].items():
            prefix = name+'/'+mode
            old, new = values['coreHideBefore']['max'], values['coreHideAfter']['max']
            if new > limits['coreHideMaxDisplacement'] or (old > 1e-8 and new > old*(1-limits['minimumHideReduction'])):
                failures.append(prefix+': head-hide isolation')
            maximum = limits['ordinaryMaxNormalized' if mode == 'normalized' else 'ordinaryMaxRawPacked']
            if values['ordinaryChange']['max'] > maximum or values['ordinaryChange']['rms'] > limits['ordinaryRms']:
                failures.append(prefix+': ordinary motion change budget')
            if values['pureP1MotionChange']['max'] > limits['pureP1MaxChange']:
                failures.append(prefix+': P1 motion change budget')
    for mode, row in joins['collar'].items():
        if row['offsetDriftIncrease']['max'] > limits['collarOffsetIncrease']:
            failures.append('collar/'+mode+': attachment drift increase')
    for name, layer in joins['layers'].items():
        for mode, row in layer.get('measurements', {}).items():
            if (row['pointwiseRootResidualIncrease']['max'] > limits['furRootResidualIncrease']
                    or row['rootDistanceDriftIncrease']['max'] > limits['furRootResidualIncrease']):
                failures.append(name+'/'+mode+': fur attachment increase')
            if row['fullCardEdgeChange']['max'] > limits['maximumCardStrainChange']:
                failures.append(name+'/'+mode+': full-card strain change')
    return failures


def build_candidate(body, tri, skeleton, profile_file, output, pynifly=None):
    inputs = [Path(x).resolve(strict=True) for x in (body, tri, skeleton, profile_file)]
    body, tri, skeleton, profile_file = inputs; profile = load_profile(profile_file)
    before_hash = {str(path): rig.sha256(path) for path in inputs}
    for path, key in ((body, 'bodyNifSha256'), (tri, 'triSha256'), (skeleton, 'skeletonSha256')):
        if rig.sha256(path) != profile['inputs'][key]:
            raise ValueError('Unsupported pinned input: '+key)
    source_files = [Path(__file__), ROOT/'scripts/repair-vr-torso.py', ROOT/'scripts/vr_head.py',
                    ROOT/'scripts/breast_rig.py', ROOT/'scripts/surface_collar.py', ROOT/'scripts/collar_weights.py',
                    ROOT/'scripts/fur_motion.py', ROOT/'recipes'/profile['rigProfile'], ROOT/'recipes/vr-torso-weights.json']
    source_hash = {str(path): rig.sha256(path) for path in source_files}
    api, Trip, dependency = rig.load_pynifly(pynifly)
    dependency_hash = {str(path): rig.sha256(path) for path in
                       (dependency/'pyn/pynifly.py', dependency/'tri/tripfile.py', dependency/'NiflyDLL.dll')}
    out = rig.safe_output(output, inputs)
    out.mkdir(parents=True, exist_ok=False)
    status = out/'status.json'; status.write_text(json.dumps({'status': 'building-unverified-do-not-install'}))
    try:
        nif = api.NifFile(str(body)); skel = api.NifFile(str(skeleton)); raw = Trip.from_filepath(str(tri)).shapes
        if len(nif.nodes) != 91 or len({name for morphs in raw.values() for name in morphs}) != 25:
            raise ValueError('Pinned node/public morph contract changed')
        frozen = snapshot(nif); rp = rig.load_profile(ROOT/'recipes'/profile['rigProfile'])
        model = Model(nif, skel, raw, rp)
        plans, core, collar, layers, selected, fields = plan(model, profile, rp)
        target = out/profile['outputRelativeNif']; target.parent.mkdir(parents=True)
        for name, entry in plans.items():
            write_active_weights(model.shapes[name], entry['weights'], entry['active'], model.names)
        nif.filepath = str(target); nif.save(); shutil.copyfile(tri, target.with_suffix('.tri'))
        actual = api.NifFile(str(target)); verified = verify_readback(frozen, actual, plans, model.names)
        # Measurements use the detached input oracle plus the exact read-back packed weights.
        actual_plans = {name: {'weights': rig.read_weights(next(s for s in actual.shapes if s.name == name), model.names),
                               'active': entry['active']} for name, entry in plans.items()}
        shapes = shape_metrics(model, actual_plans, core)
        joins = join_metrics(model, actual_plans, collar, layers)
        failures = admission(shapes, joins, profile['limits'])
        if rig.sha256(target.with_suffix('.tri')) != before_hash[str(tri)]:
            raise ValueError('TRI bytes changed')
        if any(rig.sha256(path) != value for path, value in {**before_hash, **source_hash, **dependency_hash}.items()):
            raise ValueError('Input/executed source/dependency changed during build')
        report = {'status': 'admitted-offline-candidate-runtime-pending' if not failures else 'REJECTED-measured-do-not-install',
                  'admitted': not failures, 'failures': failures, 'profile': profile,
                  'inputs': before_hash, 'sourceSha256': source_hash, 'dependencySha256': dependency_hash,
                  'outputs': {str(path.relative_to(out)): rig.sha256(path) for path in (target, target.with_suffix('.tri'))},
                  'verification': verified, 'coreVertices': core.tolist(), 'collarAnchors': collar.anchors.tolist(),
                  'selectedFurGroups': selected, 'fieldVertexCounts': {n: int((f > 0).sum()) for n, f in fields.items()},
                  'shapes': shapes, 'joins': joins,
                  'poses': [{'name': n, 'group': g, 'localPostRotations': {k: m.tolist() for k, m in edits.items()}}
                            for n, edits, g in model.poses],
                  'headOnlyPoses': [{'name': n, 'kind': kind, 'localReplacements': {k: m.tolist() for k, m in edits.items()}}
                                    for n, edits, kind in model.hide_poses],
                  'convention': 'Actual serialized B/C and scale;151 controlled +9 imposed head-only poses at BreastSize0/.5/1. Raw-packed and normalized LBS are separate mathematical models.',
                  'limits': ['Changes ordinary head/torso motion; no assertion of ordinary-animation equality.',
                             'Conservative existing-Spine2 transfer, not fitted animation weights or a skeleton edit.',
                             'Exact half-pair sums can retain head residuals; admission uses actual displacement.',
                             'Face,55collar anchor weights, body, unselected cards and non-head/non-Spine2 weights are protected.',
                             'Selected fur cards are full-weight, thorax-root-attached and do not cross faceMinY; fade/disabled groups and ChestBlend remain unchanged.',
                             'Imposed shrink/offset examples are not an active VRIK branch qualification or HMD trace.',
                             'No install, runtime visibility, camera clearance, physics, collision or appearance acceptance.']}
        path = out/'report.json'; path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        status.write_text(json.dumps({'status': report['status'], 'report': 'report.json'}))
        return path
    except Exception as exc:
        status.write_text(json.dumps({'status': 'FAILED-unverified-do-not-install', 'error': str(exc)})); raise
