"""Bounded abdomen/thigh triangle clearance on actual serialized LBS surfaces.

Frozen neutral anatomy/UV-weld exclusions, exact narrow-phase triangle distance
and proper edge/face crossings. This is not a whole-body collision oracle.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from numba import njit
from scipy.spatial import cKDTree

import expressive_body as body
import breast_rig as rig


@njit
def point_segment(p, a, b):
    u = b-a
    t = max(0., min(1., np.dot(p-a, u)/max(np.dot(u, u), 1e-30)))
    q = p-a-t*u
    return np.dot(q, q)


@njit
def point_triangle(p, a, b, c):
    u, v, w = b-a, c-a, p-a
    aa, ab, bb = np.dot(u, u), np.dot(u, v), np.dot(v, v)
    au, bu = np.dot(w, u), np.dot(w, v)
    den = aa*bb-ab*ab
    if den > 1e-24:
        s, t = (au*bb-bu*ab)/den, (bu*aa-au*ab)/den
        if s >= 0 and t >= 0 and s+t <= 1:
            q = w-s*u-t*v
            return np.dot(q, q)
    return min(point_segment(p, a, b), point_segment(p, b, c), point_segment(p, c, a))


@njit
def segment_segment(a, b, c, d):
    u, v, w = b-a, d-c, a-c
    aa, ab, bb = np.dot(u, u), np.dot(u, v), np.dot(v, v)
    au, bu = np.dot(u, w), np.dot(v, w)
    den = aa*bb-ab*ab
    result = min(point_segment(a, c, d), point_segment(b, c, d),
                 point_segment(c, a, b), point_segment(d, a, b))
    if den > 1e-24:
        s, t = (ab*bu-bb*au)/den, (aa*bu-ab*au)/den
        if 0 < s < 1 and 0 < t < 1:
            q = w+s*u-t*v
            result = min(result, np.dot(q, q))
    return result


@njit
def proper_piercing(p, q, triangle):
    a, b, c = triangle[0], triangle[1], triangle[2]
    u, v, edge = b-a, c-a, q-p
    normal = np.cross(u, v)
    den = np.dot(normal, edge)
    if abs(den) <= 1e-10*max(np.linalg.norm(normal)*np.linalg.norm(edge), 1e-20):
        return False
    along = np.dot(normal, a-p)/den
    if not 1e-8 < along < 1-1e-8:
        return False
    point = p+along*edge-a
    aa, ab, bb = np.dot(u, u), np.dot(u, v), np.dot(v, v)
    det = aa*bb-ab*ab
    if det <= 1e-24:
        return False
    s = (np.dot(point, u)*bb-np.dot(point, v)*ab)/det
    t = (np.dot(point, v)*aa-np.dot(point, u)*ab)/det
    return s > 1e-8 and t > 1e-8 and s+t < 1-1e-8


@njit
def triangle_distance(a, b):
    proper = False
    for i in range(3):
        proper |= proper_piercing(a[i], a[(i+1)%3], b)
        proper |= proper_piercing(b[i], b[(i+1)%3], a)
    if proper:
        return 0., True
    squared = 1e300
    for i in range(3):
        squared = min(squared, point_triangle(a[i], b[0], b[1], b[2]),
                      point_triangle(b[i], a[0], a[1], a[2]))
        for j in range(3):
            squared = min(squared, segment_segment(a[i], a[(i+1)%3], b[j], b[(j+1)%3]))
    return np.sqrt(max(squared, 0.)), False


@njit
def narrow_phase(triangles, pairs):
    distances = np.empty(len(pairs))
    crossing = np.zeros(len(pairs), dtype=np.bool_)
    for k in range(len(pairs)):
        distances[k], crossing[k] = triangle_distance(triangles[pairs[k, 0]], triangles[pairs[k, 1]])
    return distances, crossing


@njit
def proper_crossings(triangles, pairs):
    result = np.zeros(len(pairs), dtype=np.bool_)
    for k in range(len(pairs)):
        a, b = triangles[pairs[k, 0]], triangles[pairs[k, 1]]
        for i in range(3):
            if proper_piercing(a[i], a[(i+1)%3], b) or proper_piercing(b[i], b[(i+1)%3], a):
                result[k] = True
                break
    return result


def freeze_regions(shape):
    v, f = np.asarray(shape.verts), np.asarray(shape.tris, int)
    centres = v[f].mean(axis=1)
    weights = np.zeros(len(v))
    for name, values in shape.bone_weights.items():
        if 'Thigh' in name:
            for i, weight in values:
                weights[i] += weight
    ownership = weights[f].mean(axis=1)
    x, y, z = centres.T
    abdomen = (abs(x)<25)&(y>-8)&(z>65)&(z<99)&(ownership<.6)
    thighs = (abs(x)<32)&(abs(x)>2)&(y>-20)&(z>40)&(z<89)&(ownership>.25)
    area = np.linalg.norm(np.cross(v[f[:, 1]]-v[f[:, 0]], v[f[:, 2]]-v[f[:, 0]]), axis=1)
    _, weld = np.unique(np.round(v, 5), axis=0, return_inverse=True)
    return np.flatnonzero(abdomen&(area>1e-10)), np.flatnonzero(thighs&(area>1e-10)), weld[f]


def clearance(vertices, faces, frozen, search=3.):
    abdomen, thighs, welded = frozen
    triangles = np.asarray(vertices)[faces]
    centres = triangles.mean(axis=1)
    radii = np.linalg.norm(triangles-centres[:, None], axis=2).max(axis=1)
    tree = cKDTree(centres[thighs])
    choices = tree.query_ball_point(centres[abdomen], radii[abdomen]+radii[thighs].max()+search)
    pairs = np.array([(int(a), int(thighs[j])) for a, ids in zip(abdomen, choices) for j in ids], int).reshape(-1, 2)
    if len(pairs):
        # All UV-split equivalents are adjacent too. Coincident shared corners
        # must not masquerade as genuine nonadjacent self contacts.
        shared = (welded[pairs[:, 0], :, None] == welded[pairs[:, 1], None, :]).any(axis=(1, 2))
        pairs = np.unique(np.sort(pairs[~shared], axis=1), axis=0)
        a, b = triangles[pairs[:, 0]], triangles[pairs[:, 1]]
        gap = np.maximum(np.maximum(a.min(1)-b.max(1), b.min(1)-a.max(1)), 0)
        pairs = pairs[np.linalg.norm(gap, axis=1)<=search]
    if len(pairs):
        a, b = triangles[pairs[:, 0]], triangles[pairs[:, 1]]
        gaps = np.maximum(np.maximum(a.min(1)-b.max(1), b.min(1)-a.max(1)), 0)
        lower = np.linalg.norm(gaps, axis=1)
    else:
        lower = np.array([])
    overlapping = pairs[lower<1e-9]
    crossing = proper_crossings(triangles, overlapping)
    # AABB distance is a rigorous lower bound on triangle distance. Evaluate
    # only pairs that can improve the current minimum; all proper crossings
    # are tested independently, so early-out never hides a piercing pair.
    minimum, witness, tested, touching = search, None, 0, 0
    if crossing.any():
        minimum, witness = 0., overlapping[np.flatnonzero(crossing)[0]]
    else:
        order = np.argsort(lower)
        for index in order:
            if lower[index] > minimum+1e-9:
                break
            distance, _ = triangle_distance(triangles[pairs[index, 0]], triangles[pairs[index, 1]])
            tested += 1
            if distance < minimum:
                minimum, witness = distance, pairs[index]
            if distance < 1e-6:
                touching += 1
    return {'abdomenTriangles': len(abdomen), 'thighTriangles': len(thighs),
            'broadPhasePairs': len(pairs), 'crossingNarrowPhasePairs': len(overlapping),
            'distanceNarrowPhasePairs': tested, 'searchDistance': search,
            'minimumTriangleClearanceClippedAtSearch': float(minimum),
            'properCrossingPairs': overlapping[crossing].tolist(), 'properCrossingCount': int(crossing.sum()),
            'evaluatedTouchingOrCoplanarPairsBelow1eMinus6': touching,
            'minimumWitness': None if witness is None else {'triangles': witness.tolist(),
                'distance': float(minimum), 'points': triangles[witness].tolist()}}


def observed_matrix(value):
    m = np.eye(4)
    m[:3, :3] = np.asarray(value['rotationRowMajor']).reshape(3, 3)*value['scale']
    m[:3, 3] = value['translation']
    return m


def actual_pose(snapshot, form, rest, parents):
    actor = next(r for r in snapshot['refs'] if r['identity']['form'].lower()==form.lower())
    root_inverse = np.linalg.inv(observed_matrix(actor['sceneTransform']))
    captures = {n['name']: n for n in snapshot['nodes'] if n['form'].lower()==form.lower() and n['status']=='available'}
    explicit = {name: root_inverse@observed_matrix(row['world']) for name, row in captures.items()}
    derived = {}
    for name in ('NPC R Thigh [RThg]', 'NPC R Calf [RClf]'):
        if name in captures:
            alias = parents[name]
            explicit[alias] = explicit[name]@np.linalg.inv(observed_matrix(captures[name]['local']))
            derived[alias] = {'capturedChild': name, 'formula': 'inverse(actorRootWorld) * childWorld * inverse(childLocal)'}
    posed = {}
    def visit(name):
        if name not in posed:
            parent = parents[name]
            local = np.linalg.inv(rest[parent])@rest[name] if parent else rest[name]
            posed[name] = explicit[name] if name in explicit else (visit(parent) if parent else np.eye(4))@local
        return posed[name]
    for name in rest:
        visit(name)
    return posed, {'actorForm': form, 'actorRoot': actor['sceneTransform'], 'capturedBones': sorted(captures),
                   'derivedAliasParents': derived, 'otherBones': 'Pinned rest-local relation propagated from observed ancestors; not live-observed full skeleton.'}


def skin(shape, vertices, globals_):
    names = list(shape.bone_weights)
    binds = np.array([rig.matrix(shape.get_shape_skin_to_bone(n))@rig.matrix(shape.global_to_skin) for n in names])
    matrices = np.array([globals_[n] for n in names])@binds
    return rig.lbs(vertices, rig.read_weights(shape, names), matrices[None], False)[0]


def stress_poses(rest, parents, actual):
    controls = ['NPC L Thigh [LThg]', 'NPC R Thigh [LThg]', 'NPC L Calf [LClf]', 'NPC R Calf [LClf]']
    poses = [('rest', rest), ('observed-owner-pose', actual)]
    names = list(rest)
    for degrees in (10, 25, 45):
        for sign in (-1, 1):
            for control in controls:
                edits = {control: rig.rotation(0, degrees*sign)}
                array = rig.posed_globals(rest, parents, names, [('stress', edits, '')])[0]
                poses.append((control+':localX:'+str(degrees*sign), dict(zip(names, array))))
            edits = {controls[0]: rig.rotation(0, degrees*sign), controls[1]: rig.rotation(0, degrees*sign),
                     controls[2]: rig.rotation(0, -degrees*sign), controls[3]: rig.rotation(0, -degrees*sign)}
            array = rig.posed_globals(rest, parents, names, [('stress', edits, '')])[0]
            poses.append(('coupled-hips-opposite-knees:'+str(degrees*sign), dict(zip(names, array))))
    return poses


def analyze(reference, candidate, snapshot_path, vectors_path, output, actual_only=False):
    reference, candidate, output = map(Path, (reference, candidate, output))
    body.authored_output(output)
    snapshot = json.loads(Path(snapshot_path).read_bytes())
    vectors = json.loads(Path(vectors_path).read_bytes())
    api, _ = body.load_api()
    skeleton = api.NifFile(str(body.ROOT/'src/main/resources/donors/skeleton.nif'))
    rest = {n: rig.matrix(v.global_transform) for n, v in skeleton.nodes.items()}
    parents = {n: v.parent.name if v.parent else None for n, v in skeleton.nodes.items()}
    report = {'schema': 'claw-abdomen-thigh-clearance/1', 'scriptSha256': body.sha(Path(__file__).read_bytes()),
              'snapshotSha256': body.sha(Path(snapshot_path).read_bytes()), 'vectorsSha256': body.sha(Path(vectors_path).read_bytes()),
              'scope': __doc__, 'skinConvention': 'Actual raw packed LBS; morphs applied before skinning.', 'sexes': {}}
    for sex, tag in [('male', 'MHeavy'), ('female', 'FHeavy')]:
        nif = api.NifFile(str(reference/(sex+'bodywerewolf_0.nif')))
        shape = next(s for s in nif.shapes if s.name=='body')
        vertices, faces = np.asarray(shape.verts), np.asarray(shape.tris, int)
        counts = {s.name: len(s.verts) for s in nif.shapes}
        fields = {label: body.decode((p/(sex+'bodywerewolf.tri')).read_bytes(), counts)
                  for label, p in [('reference', reference), ('candidate', candidate)]}
        vector = next(r for r in vectors if r['fixture']==tag)
        form = vector['actorForm']
        actual, provenance = actual_pose(snapshot, form, rest, parents)
        frozen = freeze_regions(shape)
        rest_error = float(np.linalg.norm(skin(shape, vertices, rest)-vertices, axis=1).max())
        rows = {}
        states = [('neutral', {}), ('current-heavy', vector['values']),
                  ('belly-thigh-torso-max', {'CLAWTorsoBellyRound': 1., 'CLAWLegThighGirth': 1., 'CLAWTorsoGirth': 1.})]
        for label, bank in fields.items():
            rows[label] = {}
            for state, values in states:
                current = vertices+sum((bank.get(('body', m), np.zeros_like(vertices))*c for m, c in values.items()), np.zeros_like(vertices))
                poses = [('observed-owner-pose', actual)] if actual_only else stress_poses(rest, parents, actual)
                rows[label][state] = {name: clearance(skin(shape, current, pose), faces, frozen) for name, pose in poses}
                print(sex, label, state, 'actualCrossings', rows[label][state]['observed-owner-pose']['properCrossingCount'], flush=True)
        report['sexes'][sex] = {'restRawLbsIdentityMaxError': rest_error, 'actualPoseProvenance': provenance, 'states': rows}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('reference', 'candidate', 'snapshot', 'vectors', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    analyze(args.reference, args.candidate, args.snapshot, args.vectors, args.out)
