"""Opt-in layer-only P1 coupling experiment using actual serialized skin frames.

Only full-weight belly cards are eligible. This is not a physics driver and does
not change the repaired skin, XP32, geometry, TRI or the production recipe.
"""
from __future__ import annotations

from pathlib import Path
import json
import math
import shutil
import numpy as np
import breast_rig as rig
import surface_collar as surface
from collar_weights import write_active_weights

ROOT = Path(__file__).resolve().parents[1]


def fit_scalar(basis, target, lower, upper):
    """Bounded one-dimensional least squares; never fit an unobserved response."""
    x, y = np.asarray(basis, float), np.asarray(target, float)
    if (x.shape != y.shape or not np.isfinite(x).all() or not np.isfinite(y).all()
            or not all(math.isfinite(z) for z in (lower, upper)) or lower > upper):
        raise ValueError('Invalid bounded motion fit')
    denominator = float(np.sum(x*x))
    if denominator <= 1e-20:
        raise ValueError('Unobservable P1 response')
    return float(np.clip(np.sum(x*y)/denominator, lower, upper))


def exact_half_pair(spine, p1, desired):
    """Transfer only this pair, preserving its exact packed sum and old support.

    The original pair is always a feasible fallback. Enumerating every positive
    finite half up to the pair sum avoids guessing a neighbourhood of a rounding
    boundary. A positive original Spine2 is retained.
    """
    original = np.asarray([spine, p1], float)
    if (not np.isfinite(original).all() or np.min(original) < 0 or
            not np.array_equal(original.astype(np.float16).astype(float), original)
            or not math.isfinite(desired)):
        raise ValueError('Expected finite nonnegative packed half weights')
    total = float(spine+p1)
    if total <= 0:
        return original.copy()
    values = np.arange(0, 0x3c01, dtype=np.uint16).view(np.float16).astype(float)
    remaining = total-values
    good = ((remaining >= 0) & (values <= total) &
            (remaining.astype(np.float16).astype(float) == remaining))
    if spine > 0:
        good &= remaining > 0
    choices = values[good]
    if not len(choices):
        raise ValueError('No exact packed transfer pair')
    choice = float(choices[np.argmin(abs(choices-desired))])
    return np.asarray([total-choice, choice])


def transfer_card(weights, ids, root, requested, spine, p1, other_p1):
    """Common additive fraction of the existing Spine2/P1 pool per card.

    Retain every other packed influence exactly, including the opposite breast.
    Four-old-influence vertices with no P1 have no spare slot and remain fixed.
    """
    old = np.asarray(weights, float)
    ids = np.asarray(ids, int)
    if (old.ndim != 2 or not np.isfinite(old).all() or old.min() < 0 or
            len(set((spine, p1, other_p1))) != 3 or len(set(ids.tolist())) != len(ids)
            or not len(ids) or ids.min() < 0 or ids.max() >= len(old) or
            max(spine, p1, other_p1) >= old.shape[1] or min(spine, p1, other_p1) < 0
            or not math.isfinite(requested)):
        raise ValueError('Invalid card transfer input')
    if root not in ids or (old[:, other_p1] > 0).any():
        raise ValueError('Card crosses the bilateral P1 support contract')
    pool = old[:, spine]+old[:, p1]
    if pool[root] <= 0:
        raise ValueError('Root has no transferable Spine2 pool')
    fraction = (requested-old[root, p1])/pool[root]
    result = old.copy()
    for i in ids:
        if old[i, p1] == 0 and np.count_nonzero(old[i]) >= 4:
            continue
        wanted = float(np.clip(old[i, p1]+fraction*pool[i], 0, pool[i]))
        result[i, [spine, p1]] = exact_half_pair(old[i, spine], old[i, p1], wanted)
    if (np.count_nonzero(result, axis=1) > 4).any():
        raise ValueError('Transfer exceeds four influences')
    if not np.array_equal(result.sum(axis=1), old.sum(axis=1)):
        raise ValueError('Packed sums changed')
    return result


def snapshot(nif):
    """Detached arrays: mutation of the writer must not mutate the oracle."""
    def extras(node):
        return tuple((type(e).__name__, e.name,
                      e.string_data if hasattr(e, 'string_data') else bytes(e.properties).hex())
                     for e in node.extra_data())
    return {
        'nodes': {n: (node.parent.name if node.parent else None,
                      rig.matrix(node.transform).copy(), rig.matrix(node.global_transform).copy(), extras(node))
                  for n, node in nif.nodes.items()},
        'shapes': {s.name: {
            'vertices': np.asarray(s.verts).copy(), 'triangles': np.asarray(s.tris).copy(),
            'uvs': np.asarray(s.uvs).copy(), 'frame': rig.matrix(s.global_to_skin).copy(),
            'normals': np.asarray(s.normals).copy(), 'colors': np.asarray(s.colors).copy(),
            'transform': rig.matrix(s.transform).copy(),
            'render': (s.shader_block_name, bytes(s.shader.properties).hex(), dict(s.textures),
                       bytes(s.alpha_property.properties).hex() if s.alpha_property else None),
            'extras': extras(s),
            'partitions': (tuple((x.id, x.flags) for x in s.partitions), tuple(s.partition_tris)),
            'hasFrame': bool(s.has_global_to_skin),
            'bones': tuple(s.bone_weights),
            'binds': {n: rig.matrix(s.get_shape_skin_to_bone(n)).copy() for n in s.bone_weights},
            'weights': {n: tuple((int(i), float(w)) for i, w in pairs)
                        for n, pairs in s.bone_weights.items()}}
                   for s in nif.shapes}}


def verify_snapshot(before, actual, layer, planned, names):
    after = snapshot(actual)
    if set(before['nodes']) != set(after['nodes']) or set(before['shapes']) != set(after['shapes']):
        raise ValueError('Node or shape inventory changed')
    for name, old in before['nodes'].items():
        new = after['nodes'][name]
        if old[0] != new[0] or old[3] != new[3] or any(not np.array_equal(a, b) for a, b in zip(old[1:3], new[1:3])):
            raise ValueError('Node ancestry or transform changed: '+name)
    for name, old in before['shapes'].items():
        new = after['shapes'][name]
        for key in ('vertices', 'triangles', 'uvs', 'frame', 'normals', 'colors', 'transform'):
            if not np.array_equal(old[key], new[key]):
                raise ValueError('Protected '+key+' changed: '+name)
        for key in ('render', 'extras', 'partitions'):
            if old[key] != new[key]:
                raise ValueError('Protected '+key+' changed: '+name)
        if old['hasFrame'] != new['hasFrame'] or old['bones'] != new['bones']:
            raise ValueError('Skin reference/frame presence changed: '+name)
        if any(not np.array_equal(old['binds'][n], new['binds'][n]) for n in old['binds']):
            raise ValueError('Skin bind changed: '+name)
        if name != layer and old['weights'] != new['weights']:
            raise ValueError('Non-layer weights changed: '+name)
    shape = next(s for s in actual.shapes if s.name == layer)
    if not np.array_equal(rig.read_weights(shape, names), planned):
        raise ValueError('Actual serialized layer weights differ from exact-half plan')


def load_profile(filename):
    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                raise ValueError('Duplicate fur-motion profile key')
            result[k] = v
        return result
    p = json.loads(Path(filename).read_text(encoding='utf-8-sig'), object_pairs_hook=unique,
                   parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite profile')))
    template = json.loads((ROOT/'recipes/fur-motion.json').read_text())
    if set(p) != set(template) or p['schemaVersion'] != 1 or p['layer'] != 'fur_belly':
        raise ValueError('Unknown fur-motion profile contract')
    if p['inputs'] != template['inputs'] or p['rigProfile'] != template['rigProfile']:
        raise ValueError('This experiment requires the frozen collar/P1 composition')
    if p['outputRelativeNif'] != template['outputRelativeNif']:
        raise ValueError('Output must retain its embedded BODYTRI filename')
    for k in ('maximumCardStrainChange', 'normalizedOrdinaryMaxError', 'rawOrdinaryMaxError'):
        if isinstance(p[k], bool) or not isinstance(p[k], (int, float)) or not 0 < p[k] <= template[k]:
            raise ValueError('Invalid or weakened experiment tolerance: '+k)
    return p


class MotionModel:
    def __init__(self, nif, skeleton, raw, profile, rig_profile):
        self.nif, self.raw, self.profile = nif, raw, profile
        self.shapes = {s.name: s for s in nif.shapes}
        self.names = sorted({n for s in nif.shapes for n in s.bone_weights})
        self.index = {n: i for i, n in enumerate(self.names)}
        self.rest = {n: rig.matrix(x.global_transform) for n, x in skeleton.nodes.items()}
        parent = {n: x.parent.name if x.parent else None for n, x in skeleton.nodes.items()}
        self.poses = rig.pose_definitions(rig_profile['p1Bones'], 3, int(rig_profile['verification']['seed']))
        self.globals = rig.posed_globals(self.rest, parent, self.names, self.poses)
        self.pure = [i for i, x in enumerate(self.poses) if x[2].startswith('p1-')]
        self.ordinary = [i for i, x in enumerate(self.poses) if x[2] in ('ordinary', 'heldout')]
        self.weights = {n: rig.read_weights(s, self.names) for n, s in self.shapes.items()}
        self.binds = {}
        for n, shape in self.shapes.items():
            if not shape.has_global_to_skin:
                raise ValueError('Missing actual stored skin frame: '+n)
            bind = np.zeros((len(self.names), 4, 4))
            for bone in shape.bone_weights:
                bind[self.index[bone]] = rig.matrix(shape.get_shape_skin_to_bone(bone))@rig.matrix(shape.global_to_skin)
            self.binds[n] = bind

    def points(self, name, ids, coefficient):
        shape = self.shapes[name]
        v = np.asarray(shape.verts)[ids]+coefficient*rig.dense_morph(self.raw, name, 'CLAWTorsoBreastSize', len(shape.verts))[ids]
        effective = np.einsum('pbjk,bkl->pbjl', self.globals, self.binds[name])
        return np.einsum('pbjk,nk->pnbj', effective, np.c_[v, np.ones(len(v))])[..., :3]

    def evaluate(self, name, ids, coefficient, weights=None, normalized=True):
        w = self.weights[name][ids] if weights is None else np.asarray(weights)[ids]
        if normalized:
            w = w/w.sum(axis=1)[:, None]
        return np.einsum('pnbj,nb->pnj', self.points(name, ids, coefficient), w)

    def target(self, layer, group, root, coefficient, normalized=True):
        """Frozen skin barypoint plus naturally transported original root offset."""
        ids = layer.binding.faces[layer.binding.indices[group]]
        bary = layer.binding.weights[group]
        body_n = len(self.shapes['body'].verts)
        source_points = np.zeros((len(self.poses), 3, 3))
        weighted = np.zeros(len(self.names))
        for k, sid in enumerate(ids):
            name, local = ('body', int(sid)) if sid < body_n else ('head', int(sid-body_n))
            source_points[:, k] = self.evaluate(name, [local], coefficient, normalized=normalized)[:, 0]
            w = self.weights[name][local]
            weighted += bary[k]*w/w.sum()
        attach = np.einsum('pkj,k->pj', source_points, bary)
        root_rest = self.evaluate(self.profile['layer'], [root], coefficient, normalized=normalized)[0, 0]
        offset = root_rest-attach[0]
        transport = np.zeros_like(attach)
        for j, weight in enumerate(weighted):
            if weight:
                r = self.globals[:, j, :3, :3]@np.linalg.inv(self.rest[self.names[j]][:3, :3])
                transport += weight*np.einsum('pjk,k->pj', r, offset)
        expected = attach+transport
        return expected-expected[:1]


def card_metrics(model, layer, group, root, ids, candidate):
    name = model.profile['layer']; shape = model.shapes[name]
    selected = np.asarray(ids, int)
    triangles = np.asarray(shape.tris)
    triangles = triangles[np.all(np.isin(triangles, selected), axis=1)]
    edges = np.unique(np.sort(np.r_[triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]], axis=1), axis=0)
    local = {int(x): i for i, x in enumerate(selected)}
    edge_ids = np.asarray([[local[int(a)], local[int(b)]] for a, b in edges], int)
    report = {}
    for normalized in (True, False):
        key = 'normalized' if normalized else 'rawPacked'
        old_residual, new_residual, ordinary, strain = [], [], [], []
        for c in (0., .5, 1.):
            target = model.target(layer, group, root, c, normalized)
            old = model.evaluate(name, selected, c, normalized=normalized)
            new = model.evaluate(name, selected, c, candidate, normalized)
            root_i = local[root]
            old_residual.append(np.linalg.norm((old-old[:1])[:, root_i]-target, axis=-1))
            new_residual.append(np.linalg.norm((new-new[:1])[:, root_i]-target, axis=-1))
            ordinary.append(np.linalg.norm(new[model.ordinary]-old[model.ordinary], axis=-1))
            if len(edges):
                def lengths(v):
                    return np.linalg.norm(v[:, edge_ids[:, 0]]-v[:, edge_ids[:, 1]], axis=-1)
                old_l, new_l = lengths(old), lengths(new)
                if np.min(old_l[0]) <= 1e-10:
                    raise ValueError('Degenerate original card edge')
                strain.append(abs((new_l-old_l)/old_l[:1]))
        report[key] = {'rootTransportedOffsetBefore': rig.stats(old_residual),
                       'rootTransportedOffsetAfter': rig.stats(new_residual),
                       'rootSquaredErrorBefore': float(np.sum(np.square(old_residual))),
                       'rootSquaredErrorAfter': float(np.sum(np.square(new_residual))),
                       'ordinaryChangedVertexError': rig.stats(ordinary),
                       'edgeStrainChange': rig.stats(strain)}
        old_pure = np.asarray(old_residual)[:, model.pure]
        new_pure = np.asarray(new_residual)[:, model.pure]
        report[key]['pureP1RootBefore'] = rig.stats(old_pure)
        report[key]['pureP1RootAfter'] = rig.stats(new_pure)
        report[key]['pureP1SquaredBefore'] = float(np.sum(old_pure*old_pure))
        report[key]['pureP1SquaredAfter'] = float(np.sum(new_pure*new_pure))
    return report


def plan_motion(model, layer):
    name = model.profile['layer']; old = model.weights[name]; result = old.copy()
    spine = model.index['NPC Spine2 [Spn2]']; p1 = [model.index[n] for n in ('NPC L Breast P1', 'NPC R Breast P1')]
    vertices = np.asarray(model.shapes[name].verts); rows = []; changed = []
    for g, ids in enumerate(layer.groups):
        if layer.weights[g] < 1-1e-6:
            rows.append({'group': g, 'status': 'unchanged-fade-or-disabled'}); continue
        matches = ids[np.all(vertices[ids] == layer.binding.points[g], axis=1)]
        if not len(matches):
            raise ValueError('Frozen representative does not identify a card root')
        root = int(matches[0]); side = int(vertices[root, 0] >= 0); bone = p1[side]
        if np.any(old[ids, p1[1-side]]) or (old[root, bone] == 0 and np.count_nonzero(old[root]) >= 4):
            rows.append({'group': g, 'root': root, 'status': 'unchanged-unsupported-palette'}); continue
        pool = float(old[root, spine]+old[root, bone]); total = float(old[root].sum())
        if pool <= 0:
            rows.append({'group': g, 'root': root, 'status': 'unchanged-no-spine-pool'}); continue
        basis, target = [], []
        for c in (0., .5, 1.):
            points = model.points(name, [root], c)[:, 0]
            x = points[:, bone]-points[:, spine]
            basis.append((x-x[:1])[model.pure])
            target.append(model.target(layer, g, root, c)[model.pure])
        try:
            q = fit_scalar(basis, target, 0., pool/total)*total
            candidate = transfer_card(old[ids], np.arange(len(ids)), int(np.flatnonzero(ids == root)[0]), q,
                                      spine, bone, p1[1-side])
        except ValueError as exc:
            rows.append({'group': g, 'root': root, 'status': 'unchanged-unobservable', 'reason': str(exc)}); continue
        proposed = result.copy(); proposed[ids] = candidate
        metrics = card_metrics(model, layer, g, root, ids, proposed)
        accept = True
        for mode, r in metrics.items():
            tolerance = model.profile['normalizedOrdinaryMaxError' if mode == 'normalized' else 'rawOrdinaryMaxError']
            accept &= (r['pureP1RootAfter']['max'] <= r['pureP1RootBefore']['max']+1e-8 and
                       r['pureP1SquaredAfter'] <= r['pureP1SquaredBefore']+1e-12 and
                       r['ordinaryChangedVertexError']['max'] <= tolerance and
                       r['edgeStrainChange']['max'] <= model.profile['maximumCardStrainChange'])
        measured = metrics['normalized']
        accept &= measured['pureP1SquaredBefore']-measured['pureP1SquaredAfter'] > max(1e-8, .01*measured['pureP1SquaredBefore'])
        active = ids[np.any(candidate != old[ids], axis=1)]
        accept &= bool(len(active))
        rows.append({'group': g, 'root': root, 'status': 'accepted-offline' if accept else 'unchanged-nonimproving-or-budget',
                     'requestedRootP1': q, 'metrics': metrics, 'changedVertices': active.tolist() if accept else []})
        if accept:
            result[ids] = candidate; changed.extend(active.tolist())
    if not changed:
        raise ValueError('No card improved within declared budgets; no-op candidate rejected')
    return result, np.asarray(sorted(set(changed)), int), rows


def build_candidate(body, tri, skeleton, profile_file, output, pynifly=None):
    inputs = [Path(x).resolve(strict=True) for x in (body, tri, skeleton, profile_file)]
    body, tri, skeleton, profile_file = inputs
    before_hash = {str(x): rig.sha256(x) for x in inputs}
    p = load_profile(profile_file)
    for path, key in ((body, 'bodyNifSha256'), (tri, 'triSha256'), (skeleton, 'skeletonSha256')):
        if rig.sha256(path) != p['inputs'][key]:
            raise ValueError('Pinned input mismatch: '+key)
    out = rig.safe_output(output, inputs)
    api, Trip, dependency = rig.load_pynifly(pynifly)
    executed = [Path(__file__), ROOT/'scripts/follow-fur-motion.py', ROOT/'scripts/breast_rig.py',
                ROOT/'scripts/surface_collar.py', ROOT/'scripts/collar_weights.py',
                ROOT/'scripts/locate.py', ROOT/'recipes/breast-rig.json',
                ROOT/'recipes'/p['rigProfile'], ROOT/'recipes/fur-motion.json']
    executed += [*sorted((dependency/'pyn').glob('*.py')), *sorted((dependency/'tri').glob('*.py')),
                 dependency/'NiflyDLL.dll']
    executed_before = {str(x): rig.sha256(x) for x in executed}
    source = api.NifFile(str(body)); skel = api.NifFile(str(skeleton)); raw = Trip.from_filepath(str(tri)).shapes
    frozen = snapshot(source)
    if len(source.nodes) != 91:
        raise ValueError('Expected existing 91-node composition')
    rp = rig.load_profile(ROOT/'recipes'/p['rigProfile'])
    model = MotionModel(source, skel, raw, p, rp)
    s = model.shapes; skin = np.r_[s['body'].verts, s['head'].verts]
    faces = np.r_[s['body'].tris, np.asarray(s['head'].tris)+len(s['body'].verts)]
    rule = next(x for x in rp['layers'] if x['shape'] == p['layer'])
    layer = surface.Layer(s[p['layer']].verts, s[p['layer']].tris, skin, faces, rule, rig.SurfaceProjector(skin, faces))
    planned, active, rows = plan_motion(model, layer)
    bindings = [{'group': i, 'vertices': ids.tolist(), 'rootPoint': layer.binding.points[i].tolist(),
                 'skinVertices': layer.binding.faces[layer.binding.indices[i]].tolist(),
                 'barycentric': layer.binding.weights[i].tolist(), 'weight': float(layer.weights[i])}
                for i, ids in enumerate(layer.groups)]
    out.mkdir(parents=True, exist_ok=False)
    (out/'status.json').write_text(json.dumps({'status': 'building-unverified-do-not-install'}))
    try:
        target = out/p['outputRelativeNif']; target.parent.mkdir(parents=True)
        write_active_weights(s[p['layer']], planned, active, model.names)
        source.filepath = str(target); source.save(); shutil.copyfile(tri, target.with_suffix('.tri'))
        actual = api.NifFile(str(target))
        verify_snapshot(frozen, actual, p['layer'], planned, model.names)
        if rig.sha256(target.with_suffix('.tri')) != rig.sha256(tri):
            raise ValueError('TRI changed')
        if any(rig.sha256(path) != value for path, value in before_hash.items()):
            raise ValueError('Input changed during build')
        if any(rig.sha256(path) != value for path, value in executed_before.items()):
            raise ValueError('Executed source, profile or dependency changed during build')
        report = {'status': 'verified-offline-layer-candidate-runtime-appearance-pending', 'profile': p,
                  'inputs': before_hash, 'outputSha256': {str(x.relative_to(out)): rig.sha256(x) for x in (target, target.with_suffix('.tri'))},
                  'executedFilesSha256': executed_before,
                  'dependencyDirectory': str(dependency), 'changedVertexCount': len(active), 'changedVertices': active.tolist(),
                  'groups': rows, 'frozenBindings': bindings,
                  'protected': 'Checked91 nodes/ancestry/transforms/extra data; vertices/triangles/UV/normals/colors/shape transforms/shaders/textures/alpha/partitions/extra data; binds/frames; non-belly weights and exact TRI. Exact packed sums and non-Spine2/P1 support retained. This is selected-field readback, not whole-NIF byte equality.',
                  'limits': ['Only full belly cards; fade cards, chest, shoulders and ChestBlend unchanged.',
                             'Normalized fitting uses24pureP1 poses; metrics include151ordinary/heldout/P1 poses at BreastSize0/0.5/1.',
                             'Transported offsets allow natural rotation; neither residual nor edge strain establishes contact, fur coverage or appearance.',
                             'Four-influence capacity can prevent exact following. Unsupported groups remain unchanged.',
                             'No production/default/installed files changed; skeleton and physics driver ownership remain separate.']}
        (out/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        (out/'status.json').write_text(json.dumps({'status': report['status'], 'report': 'report.json'}))
        return out/'report.json'
    except Exception as exc:
        (out/'status.json').write_text(json.dumps({'status': 'FAILED-unverified-do-not-install', 'error': str(exc)})); raise
