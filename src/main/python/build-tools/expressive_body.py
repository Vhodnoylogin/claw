"""Reproducible bounded body-field candidate on the immutable 30 October core.

Only TRIP records change. NIF bytes, vertex order, UVs, skin and material data
are copied exactly. Coefficients remain nonnegative 0..1; lean is authored as
its own field, never a negative runtime coefficient or TRI extrapolation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
import sys

import numpy as np

import morph_quality as quality
import surface_collar as surface
from surface_edits import trip_records, write_trip

ROOT = Path(__file__).resolve().parents[4]
NAMES = ('CLAWArmLean', 'CLAWLegThighLean', 'CLAWLegCalfLean', 'CLAWTorsoLean',
         'CLAWArmGirth', 'CLAWLegThighGirth', 'CLAWLegCalfGirth',
         'CLAWTorsoGirth', 'CLAWTorsoBellyRound', 'CLAWTorsoShoulderGirth', 'CLAWTorsoChestSize')
COAT = ('fur_arms', 'fur_back', 'fur_belly', 'fur_chest', 'fur_shoulders', 'ChestBlend')


def smooth(value):
    value = np.clip(value, 0, 1)
    return value * value * (3 - 2 * value)


def window(value, low, high, fade):
    return smooth((value-low)/fade) * smooth((high-value)/fade)


def belly_support(vertices, shape, rule):
    """Compact abdomen support, with an optional smooth elliptical dome.

    The released v1 recipe deliberately retains its original plateau. New
    recipes can redistribute forward growth towards the abdominal centre
    without changing vertex indices, joins, materials or runtime coefficients.
    This is an authored geometric profile, not an anatomical calibration.
    """
    x, y, z = quality.positions(vertices).T
    support = window(z, *rule['range'], rule['fade'])
    support *= 1-smooth((np.abs(x)-rule['widthFull'])/rule['widthFade'])
    support *= smooth((y-rule['backZero'])/rule['backFade'])
    if shape in ('body', 'head', 'genitals'):
        support *= 1-smooth((y-rule['skinFrontFull'])/rule['skinFrontFade'])
    dome = rule.get('dome')
    if dome is not None:
        if (not isinstance(dome, dict) or set(dome) != {'centreZ', 'sigmaX', 'sigmaZ'} or
                any(isinstance(value, bool) or not isinstance(value, (int, float)) or
                    not np.isfinite(value) for value in dome.values()) or
                dome['sigmaX'] <= 0 or dome['sigmaZ'] <= 0):
            raise ValueError('Finite dome centre and positive X/Z widths required')
        support *= np.exp(-.5*((x/dome['sigmaX'])**2 +
                              ((z-dome['centreZ'])/dome['sigmaZ'])**2))
    return support


def fields(vertices, shape, recipe):
    """One continuous anatomical rest-frame warp, shared at welded vertices.

    Arms preserve X (length), legs preserve Z, torso preserves Z. Smooth compact
    supports avoid the joints, feet and face. The separately documented belly
    coat support bends long downward cards instead of leaving their tips fixed.
    """
    v = quality.positions(vertices)
    result = {name: np.zeros_like(v) for name in NAMES}
    if shape not in ('body', 'head', *COAT, 'genitals'):
        return result
    x, y, z = v.T
    ax = np.abs(x)
    # Limb axes are recipe-authored in the pinned model frame, checked against
    # stored bone-region centroids. No vertex-index or nearest-sex assumptions.
    arm = recipe['arm']
    cy = np.interp(ax, arm['axisX'], arm['axisY'])
    cz = np.interp(ax, arm['axisX'], arm['axisZ'])
    radial = np.c_[np.zeros(len(v)), y-cy, z-cz]
    radius = np.linalg.norm(radial, axis=1)
    support = window(ax, *arm['range'], arm['fade']) * (1-smooth((radius-arm['radiusFull'])/arm['radiusFade']))
    # Two broad bellies suggest biceps/triceps and forearm mass while retaining
    # the elbow/wrist transition, rather than translating the entire upper arm.
    muscle = arm['base'] + arm['upperPeak']*np.exp(-((ax-arm['upperCentre'])/arm['upperWidth'])**2)
    muscle += arm['forePeak']*np.exp(-((ax-arm['foreCentre'])/arm['foreWidth'])**2)
    radial[:, 1] *= arm['depthAspect']
    shoulder = recipe['shoulder']
    shoulder_support = window(ax, *shoulder['rangeX'], shoulder['fade'])
    shoulder_support *= 1-smooth((radius-arm['radiusFull'])/arm['radiusFade'])
    result['CLAWTorsoShoulderGirth'] = radial*(shoulder['growth']*shoulder_support)[:, None]
    for name, amount in [('CLAWArmLean', arm['lean']), ('CLAWArmGirth', arm['growth'])]:
        result[name] = radial * (amount*support*muscle)[:, None]
    for region, prefix in [('thigh', 'CLAWLegThigh'), ('calf', 'CLAWLegCalf')]:
        rule = recipe[region]
        cy = np.interp(z, rule['axisZ'], rule['axisY'])
        cx = np.interp(z, rule['axisZ'], rule['axisX'])
        radial = np.c_[x-np.where(x<0, -cx, cx), y-cy, np.zeros(len(v))]
        radius = np.linalg.norm(radial, axis=1)
        support = window(z, *rule['range'], rule['fade']) * smooth(ax/rule['centreFade'])
        support *= 1-smooth((radius-rule['radiusFull'])/rule['radiusFade'])
        radial[:, 1] *= rule['depthAspect']
        for suffix, amount in [('Lean', rule['lean']), ('Girth', rule['growth'])]:
            result[prefix+suffix] = radial*(support*amount)[:, None]
    torso = recipe['torso']
    support = window(z, *torso['range'], torso['fade'])
    support *= 1-smooth((ax-torso['widthFull'])/torso['widthFade'])
    support *= 1-smooth((y-torso['frontFull'])/torso['frontFade'])
    for name, scale in [('CLAWTorsoLean', torso['lean']), ('CLAWTorsoGirth', torso['growth'])]:
        result[name][:, 0] = x*scale[0]*support
        result[name][:, 1] = (y-torso['axisY'])*scale[1]*support
    chest = recipe['chest']
    support = window(z, *chest['range'], chest['fade'])
    support *= 1-smooth((ax-chest['widthFull'])/chest['widthFade'])
    support *= smooth((y-chest['backZero'])/chest['backFade'])
    support *= 1-smooth((y-chest['frontFull'])/chest['frontFade'])
    result['CLAWTorsoChestSize'][:, 0] = x*chest['lateral']*support
    result['CLAWTorsoChestSize'][:, 1] = chest['forward']*support
    result['CLAWTorsoChestSize'][:, 2] = -chest['down']*support
    belly = recipe['belly']
    support = belly_support(v, shape, belly)
    result['CLAWTorsoBellyRound'][:, 1] = belly['forward']*support
    result['CLAWTorsoBellyRound'][:, 2] = -belly['down']*support
    result['CLAWTorsoBellyRound'][:, 0] = x*belly['lateral']*support
    return result


def encode_field(name, delta):
    delta = quality.positions(delta)
    peak = float(np.max(np.abs(delta), initial=0))
    if peak == 0:
        return [name, 1., []]
    # Explicit float32 scale and round-to-nearest; audit the decoded result.
    scale = float(np.float32(peak/32760))
    packed = np.rint(delta/scale).astype(np.int64)
    if np.any(abs(packed)>32767):
        raise ValueError('TRIP quantization overflow')
    ids = np.flatnonzero(np.any(packed != 0, axis=1))
    if len(ids)>65535:
        raise ValueError('TRIP record too large')
    return [name, scale, [[int(i), *map(int, packed[i])] for i in ids]]


def decode(data, counts):
    _, shapes = trip_records(data)
    result = {}
    for shape, records in shapes:
        if shape not in counts:
            raise ValueError('TRIP shape absent from NIF')
        for name, scale, rows in records:
            value = np.zeros((counts[shape], 3))
            for i, *delta in rows:
                if i >= counts[shape]:
                    raise ValueError('TRIP vertex outside NIF')
                value[i] = np.asarray(delta)*scale
            result[shape, name] = value
    return result


def sha(data):
    return hashlib.sha256(data).hexdigest()


def authored_output(path, inputs=()):
    """Allow new ignored target outputs without permitting writes into sources."""
    out = Path(path).resolve()
    if ROOT/'target' not in out.parents:
        return quality.safe_output(out, inputs)
    blocked = [Path(p).resolve().parent for p in inputs]
    if out.exists() or any(out == p or p in out.parents for p in blocked):
        raise ValueError('Output must be new and separate from its input directory')
    for ancestor in (out, *out.parents):
        if ancestor.exists() and (ancestor.is_symlink() or ancestor.is_junction()):
            raise ValueError('Target output ancestry cannot contain a link/junction')
    return out


def coat_followers(geometry, faces, generated):
    """Rigid per-card followers with explicit frozen skin-triangle bindings.

    A KD-tree proposes root candidates; exact point/triangle projection chooses
    among incident triangles of the nearest 12 skin vertices. This is a declared
    local projection, not a claim to a globally exact nearest-surface search.
    Belly alone retains its smooth ambient card bending to move the long
    downward coat which otherwise hides the upper female abdomen.
    """
    from scipy.spatial import cKDTree
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    skin = np.r_[geometry['body'], geometry['head']]
    skin_faces = np.r_[faces['body'], faces['head']+len(geometry['body'])]
    tree = cKDTree(skin)
    skin_delta = {m: np.r_[generated['body'][m], generated['head'][m]] for m in NAMES}
    incident = [[] for _ in skin]
    for index, face in enumerate(skin_faces):
        for vertex in face:
            incident[vertex].append(index)
    report = {}
    for name in COAT:
        if name not in geometry:
            continue
        v, f = geometry[name], faces[name]
        _, inverse = np.unique(np.round(v, 5), axis=0, return_inverse=True)
        edges = inverse[f[:, [0, 1, 1, 2, 2, 0]]].reshape(-1, 2)
        count, labels = connected_components(coo_matrix((np.ones(len(edges)), (edges[:, 0], edges[:, 1])),
                                                       shape=(int(inverse.max())+1,)*2), directed=False)
        groups = [np.flatnonzero(labels[inverse] == i) for i in range(count)]
        if name == 'ChestBlend':
            groups = [np.array([i]) for i in range(len(v))]
        distance, nearest = tree.query(v, k=12)
        root_errors = []; root_distances = []
        for group in groups:
            choices = group[np.argsort(distance[group, 0], kind='stable')[:4]]
            best = (np.inf, None, None, None)
            for index in choices:
                triangles = np.unique([t for vertex in nearest[index] for t in incident[vertex]])
                point, local, dist = surface.closest_surface(v[index], skin, skin_faces[triangles])
                if dist < best[0]:
                    face = skin_faces[triangles[local]]
                    best = dist, index, face, surface.barycentric(point, skin[face])
            dist, index, face, bary = best
            root_distances.append(float(dist))
            for morph in NAMES:
                if morph == 'CLAWTorsoBellyRound':
                    continue
                inherited = np.sum(skin_delta[morph][face]*bary[:, None], axis=0)
                generated[name][morph][group] = inherited
                root_errors.append(float(np.linalg.norm(generated[name][morph][index]-inherited)))
        report[name] = {'groups': len(groups), 'largestGroup': max(map(len, groups)),
                        'rootDistanceMax': max(root_distances), 'rootDistanceP95': float(np.quantile(root_distances, .95)),
                        'idealRootFollowerErrorMax': max(root_errors)}
    return report


def load_api(path=None):
    import locate
    addon = Path(path or locate.local_config(__file__).get('pynifly', '')).resolve()
    sys.path.insert(0, str(addon))
    from pyn import pynifly as api
    api.NifFile.Load(str(addon/'NiflyDLL.dll'))
    return api, addon


def section(vertices, faces, axis, level, mask=None):
    """Triangle/plane envelope, explicitly alpha-ignorant and model-space."""
    t = np.asarray(vertices)[np.asarray(faces)]
    points = []
    for a, b in ((0, 1), (1, 2), (2, 0)):
        u, w = t[:, a], t[:, b]
        den = w[:, axis]-u[:, axis]
        ok = (abs(den)>1e-12) & ((u[:, axis]-level)*(w[:, axis]-level)<=0)
        p = u[ok] + ((level-u[ok, axis])/den[ok])[:, None]*(w[ok]-u[ok])
        if mask is not None:
            p = p[mask(p)]
        points.extend(p.tolist())
    points = np.asarray(points).reshape(-1, 3)
    if not len(points):
        return None
    axes = [i for i in range(3) if i != axis]
    q = points[:, axes]
    from scipy.spatial import ConvexHull, QhullError
    try:
        area = float(ConvexHull(q).volume)
    except QhullError:
        area = 0.
    return {'points': len(q), 'width': float(np.ptp(q[:, 0])), 'depth': float(np.ptp(q[:, 1])),
            'front': float(q[:, 1].max()), 'hullArea': area,
            'central90Width': float(np.ptp(np.quantile(q[:, 0], [.05, .95]))),
            'central90Depth': float(np.ptp(np.quantile(q[:, 1], [.05, .95])))}


def audit(geometry, faces, before, after, extra_states=()):
    joins = quality.freeze_join(geometry['body'], faces['body'], geometry['head'], faces['head'])
    collar = make_collar(geometry, faces)
    states = [('neutral', {})]
    for name in NAMES:
        states += [(name+'='+str(value), {name: value}) for value in (.25, .5, .75, 1.)]
    states += [('lean-all', dict.fromkeys(NAMES[:4], 1.)),
               ('growth-all', dict.fromkeys(NAMES[4:], 1.)),
               ('mixed-half', dict.fromkeys(NAMES, .5))]
    states += list(extra_states)
    states += [('baseline:'+n, state) for n, state in extra_states]
    rows = {}
    for label, state in states:
        source = before if label.startswith('baseline:') else after
        current = {n: v+sum((source.get((n, m), np.zeros_like(v))*c for m, c in state.items()), np.zeros_like(v)) for n, v in geometry.items()}
        surfaces = {n: quality.surface_metrics(v, current[n], faces[n]) for n, v in geometry.items()}
        joins_row = quality.join_metrics(geometry['body'], geometry['head'], current['body'], current['head'], joins)
        for row in surfaces.values():
            # Full triangle IDs remain in the external report for diagnosis.
            row['newNormalTurnsRelativeToNeutral'] = row['normalTurnCount']
        rows[label] = {'surfaces': surfaces, 'bodyHeadJoin': joins_row,
                       'frozenCollarAttachments': collar.metrics(current['body'], current['head'])}
    # Frozen anatomical planes and masks, shared by both sexes and every state.
    planes = {'upperArm': (0, 33., lambda p: (p[:, 2]>65)&(p[:, 2]<118)),
              'forearm': (0, 52., lambda p: (p[:, 2]>60)&(p[:, 2]<112)),
              'thigh': (2, 62., lambda p: (p[:, 0]>4)&(p[:, 0]<29)&(p[:, 1]>-18)&(p[:, 1]<25)),
              'calf': (2, 31., lambda p: (p[:, 0]>4)&(p[:, 0]<29)&(p[:, 1]>-18)&(p[:, 1]<25)),
              'waist': (2, 84., lambda p: abs(p[:, 0])<23),
              'belly80': (2, 80., lambda p: abs(p[:, 0])<10),
              'belly84': (2, 84., lambda p: abs(p[:, 0])<10)}
    measurements = {}
    for label, state in [('neutral', {}), *[(m, {m: 1.}) for m in NAMES],
                         *[('baseline:'+m, {m: 1.}) for m in NAMES[4:]],
                         *extra_states, *[('baseline:'+n, v) for n, v in extra_states]]:
        measurements[label] = {}
        source = before if label.startswith('baseline:') else after
        for family, selected in [('skin', ('body', 'head')), ('fur', COAT)]:
            selected = [n for n in selected if n in geometry]
            vertices = []; triangles = []; neutral_vertices = []; start = 0
            for n in selected:
                v = geometry[n]+sum((source.get((n, m), np.zeros_like(geometry[n]))*c for m, c in state.items()), np.zeros_like(geometry[n]))
                vertices.append(v); neutral_vertices.append(geometry[n]); triangles.append(faces[n]+start); start += len(v)
            vertices, triangles, neutral_vertices = np.concatenate(vertices), np.concatenate(triangles), np.concatenate(neutral_vertices)
            centres = neutral_vertices[triangles].mean(1)
            measurements[label][family] = {region: section(vertices, triangles[mask(centres)], axis, level) for region, (axis, level, mask) in planes.items()}
    issues = []
    for state, row in rows.items():
        for shape, surface in row['surfaces'].items():
            if not state.startswith('baseline:') and (surface['newCollapsedCount'] or surface['normalTurnCount']):
                issues.append({'state': state, 'shape': shape, 'turns': surface['normalTurnCount'], 'collapsed': surface['newCollapsedCount']})
    return {'scope': 'Exact decoded TRIP, rest-space, finite states, alpha-ignorant triangle-plane convex-hull envelope (not true concave cross-section area). Equal weight NIFs make 0/.5/1 identical. No posed skinning, global intersection, UV appearance, lighting or artistic acceptance.',
            'sectionDefinitions': {n: {'planeAxis': axis, 'level': level, 'projectedAxes': [i for i in range(3) if i != axis],
                                      'roi': 'Frozen neutral triangle-centroid mask; see source and expressive-body.md'} for n, (axis, level, _) in planes.items()},
            'states': rows, 'sections': measurements, 'normalOrCollapseIssues': issues}


def make_collar(geometry, faces):
    from body_weight import Projector
    rule = {'anchorBounds': [[-23, 10, 85], [23, 45, 103]], 'anchorMaxDistance': 1.,
            'anchorCountRange': [1, 500], 'width': 2., 'weldDecimals': 5,
            'maxIterations': 400, 'solverTolerance': 1e-8}
    return surface.Collar(geometry['body'], faces['body'], geometry['head'], faces['head'], rule,
                          Projector(geometry['body'], faces['body']))


def build(base, recipe_path, out, pynifly=None, vectors=None):
    base, out = Path(base).resolve(), Path(out).resolve()
    authored_output(out, [base/'malebodywerewolf_0.nif'])
    recipe = json.loads(Path(recipe_path).read_text(encoding='utf-8'))
    if recipe['schema'] != 'claw-expressive-body/1':
        raise ValueError('Unsupported recipe')
    names = [sex+'bodywerewolf'+suffix for sex in ('male', 'female') for suffix in ('_0.nif', '_1.nif', '.tri')]
    original = {name: (base/name).read_bytes() for name in names}
    if {n: sha(v) for n, v in original.items()} != recipe['baselineSha256']:
        raise ValueError('Repaired body input hash mismatch; build the pinned source stages first')
    api, addon = load_api(pynifly)
    import scipy
    vector_rows = json.loads(Path(vectors).read_text(encoding='utf-8')) if vectors else []
    for row in vector_rows:
        if row['sex'] not in ('male', 'female') or any(not np.isfinite(c) or not 0 <= c <= 1 for c in row['values'].values()):
            raise ValueError('Invalid fixture vector')
    report = {'schema': 'claw-expressive-body-report/1', 'baselineSha256': recipe['baselineSha256'],
              'recipeSha256': sha(Path(recipe_path).read_bytes()), 'scriptSha256': sha(Path(__file__).read_bytes()),
              'dependenciesSha256': {str(p): sha(p.read_bytes()) for p in [ROOT / 'src/main/python/build-tools/morph_quality.py', ROOT / 'src/main/python/build-tools/surface_edits.py',
                  ROOT / 'src/main/python/build-tools/surface_collar.py', ROOT / 'src/main/python/build-tools/body_weight.py', ROOT / 'src/main/python/build-tools/head_split.py', ROOT / 'src/main/python/build-tools/tri_patch.py', addon/'NiflyDLL.dll', addon/'pyn/pynifly.py']},
              'environment': {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__},
              'fixtureVectors': vector_rows, 'fixtureVectorsSha256': sha(Path(vectors).read_bytes()) if vectors else None,
              'status': 'building', 'sexes': {}, 'outputSha256': {}}
    payload = {}
    for sex in ('male', 'female'):
        nif = api.NifFile(str(base/(sex+'bodywerewolf_0.nif')))
        if original[sex+'bodywerewolf_0.nif'] != original[sex+'bodywerewolf_1.nif']:
            raise ValueError('This recipe requires frozen equal weight endpoints')
        geometry = {s.name: np.asarray(s.verts, float) for s in nif.shapes}
        faces = {s.name: np.asarray(s.tris, int) for s in nif.shapes}
        for shape in nif.shapes:
            if any(not np.isfinite(weight) or weight < 0 or not 0 <= index < len(shape.verts)
                   for pairs in shape.bone_weights.values() for index, weight in pairs):
                raise ValueError('Invalid baseline serialized skin weight')
        if any(not np.allclose(quality.transform(s.global_transform), np.eye(4), rtol=0, atol=1e-5) for s in nif.shapes):
            raise ValueError('Recipe requires identity shape frames')
        magic, records = trip_records(original[sex+'bodywerewolf.tri'])
        before = decode(original[sex+'bodywerewolf.tri'], {n: len(v) for n, v in geometry.items()})
        generated = {n: fields(v, n, recipe['parameters']) for n, v in geometry.items()}
        collar = make_collar(geometry, faces)
        for morph in NAMES:
            generated['head'][morph] = collar.reconcile(generated['body'][morph], generated['head'][morph])
        coat_bindings = coat_followers(geometry, faces, generated)
        by_shape = {n: rows for n, rows in records}
        for shape in geometry:
            rows = by_shape.setdefault(shape, [])
            changed = {name: encode_field(name, generated[shape][name]) for name in NAMES}
            # Keep all non-body records exact and retain existing relative order.
            rows[:] = [changed.pop(row[0], row) for row in rows]
            rows.extend(row for name, row in changed.items() if row[2])
        for shape in geometry:
            if shape not in {n for n, _ in records} and by_shape[shape]:
                records.append([shape, by_shape[shape]])
        result = write_trip(magic, records)
        after = decode(result, {n: len(v) for n, v in geometry.items()})
        extra_states = [('fixture:'+r['fixture'], r['values']) for r in vector_rows if r['sex'] == sex]
        available = {m for n, m in after}
        if any(c and m not in available for _, state in extra_states for m, c in state.items()):
            raise ValueError('Nonzero fixture target absent from serialized TRI')
        measurements = audit(geometry, faces, before, after, extra_states)
        measurements['coatBindings'] = coat_bindings
        protected = geometry['head'][:, 1] >= max(recipe['parameters']['torso']['frontFull']+recipe['parameters']['torso']['frontFade'],
                                                   recipe['parameters']['belly']['skinFrontFull']+recipe['parameters']['belly']['skinFrontFade'])
        measurements['protectedHeadAheadOfBodySupport'] = {'vertices': int(protected.sum()),
            'maximumDecodedAuthoredDisplacement': max(float(np.linalg.norm(after.get(('head', m), np.zeros_like(geometry['head']))[protected], axis=1).max(initial=0)) for m in NAMES)}
        measurements['baselineSkinWeightsFiniteNonnegative'] = True
        report['sexes'][sex] = measurements
        payload[sex+'bodywerewolf.tri'] = result
        for suffix in ('_0.nif', '_1.nif'):
            payload[sex+'bodywerewolf'+suffix] = original[sex+'bodywerewolf'+suffix]
    if any(sha((base/n).read_bytes()) != sha(value) for n, value in original.items()):
        raise ValueError('Frozen input changed during build')
    out.mkdir(parents=True)
    target = out/'Meshes/Actors/WerewolfBeast/Character Assets'; target.mkdir(parents=True)
    for name, value in payload.items():
        (target/name).write_bytes(value)
        report['outputSha256'][name] = sha(value)
    report['status'] = 'offline-candidate-quality-issues' if any(r['normalOrCollapseIssues'] for r in report['sexes'].values()) else 'offline-candidate-static-sample-gates-pass-visual-runtime-pending'
    report['nifBytesUnchanged'] = all(payload[n] == original[n] for n in names if n.endswith('.nif'))
    (out/'expressive-body-report.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=ROOT / 'target/bodies/fresh/repaired/Meshes/Actors/WerewolfBeast/Character Assets')
    parser.add_argument('--recipe', type=Path, default=ROOT / 'src/main/resources/recipes/expressive-body-v1.json')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--pynifly', type=Path)
    parser.add_argument('--vectors', type=Path, help='Optional pinned six-fixture matrix output JSON')
    args = parser.parse_args()
    result = build(args.base, args.recipe, args.out, args.pynifly, args.vectors)
    print(json.dumps({'status': result['status'], 'outputSha256': result['outputSha256'],
                      'issues': {s: r['normalOrCollapseIssues'] for s, r in result['sexes'].items()}}, indent=2))


if __name__ == '__main__':
    main()
