"""Read-only head-bone motion audit on the published CLAW body resources.

This imposes named mathematical poses; it does not observe a camera or execute
VRIK. A shape name and its visibility flag do not describe its skin influences.
"""
from pathlib import Path
import json
import numpy as np
import breast_rig as rig

ROOT = Path(__file__).resolve().parents[1]
HEAD = 'NPC Head [Head]'


def descendants(parents, root):
    if root not in parents:
        raise ValueError('Head node missing')
    result = set()
    for name in parents:
        n, seen = name, set()
        while n is not None:
            if n in seen or n not in parents:
                raise ValueError('Invalid node ancestry')
            seen.add(n)
            if n == root:
                result.add(name)
            n = parents[n]
    return result


def impose(rest, parents, replacements):
    """Full local replacement, retaining actual rest scale and ancestor frames."""
    local = {n: np.linalg.inv(rest[parents[n]])@g if parents[n] else g.copy() for n, g in rest.items()}
    if not set(replacements) <= set(local):
        raise ValueError('Replacement node absent')
    if any(np.asarray(x).shape != (4, 4) or not np.isfinite(x).all() for x in replacements.values()):
        raise ValueError('Invalid replacement transform')
    local.update(replacements)
    result = {}
    affected = set().union(*(descendants(parents, n) for n in replacements)) if replacements else set()
    def visit(n):
        if n not in result:
            result[n] = ((visit(parents[n]) if parents[n] else np.eye(4))@local[n]
                         if n in affected else rest[n].copy())
        return result[n]
    for name in rest:
        visit(name)
    return result


def pose_bank(rest, parents):
    local = np.linalg.inv(rest[parents[HEAD]])@rest[HEAD] if parents[HEAD] else rest[HEAD].copy()
    bank = [('rest', {}, 'rest')]
    shrunk = local.copy(); shrunk[:3, :3] *= .01; shrunk[:3, 3] *= .25
    bank.append(('head-local-scale0.01-position0.25', {HEAD: shrunk}, 'visibility-operation-example'))
    for axis in range(3):
        for sign in (-1, 1):
            bank.append((f'head-local-rotate-axis{axis}-{sign*15}', {HEAD: local@rig.rotation(axis, sign*15)}, 'rotation-example'))
    for sign in (-1, 1):
        shifted = local.copy(); shifted[1, 3] += sign*20
        bank.append((f'head-local-y-offset-{sign*20}', {HEAD: shifted}, 'offset-example-not-an-HMD-trace'))
    return bank


def region_indices(vertices, weights, names):
    """Explicit male comparison ROI, not an anatomical segmentation claim."""
    v = np.asarray(vertices)
    support = [i for i, n in enumerate(names) if 'Spine' in n or 'Clavicle' in n]
    if not support:
        return np.asarray([], int)
    inside = ((v >= [-25, 8, 82]) & (v <= [25, 46, 108])).all(axis=1)
    return np.flatnonzero(inside & (weights[:, support].sum(axis=1) > 0))


def audit_shape(shape, raw, names, rest, transforms, head_names, female):
    weights = rig.read_weights(shape, names)
    delta = rig.dense_morph(raw, shape.name, 'CLAWTorsoBreastSize', len(shape.verts))
    ids = np.flatnonzero(np.any(delta != 0, axis=1)) if female else region_indices(shape.verts, weights, names)
    if not len(ids):
        return None
    bind = np.zeros((len(names), 4, 4))
    if not shape.has_global_to_skin:
        raise ValueError('Actual stored global-to-skin missing: '+shape.name)
    for name in shape.bone_weights:
        bind[names.index(name)] = rig.matrix(shape.get_shape_skin_to_bone(name))@rig.matrix(shape.global_to_skin)
    effective = np.einsum('pbjk,bkl->pbjl', transforms, bind)
    head_columns = [i for i, n in enumerate(names) if n in head_names]
    head_mass = weights[ids][:, head_columns].sum(axis=1)
    rows = {}
    for normalized in (False, True):
        mode = 'normalized' if normalized else 'rawPacked'
        rows[mode] = {}
        for coefficient in ((0., .5, 1.) if female else (0.,)):
            vertices = np.asarray(shape.verts)[ids]+coefficient*delta[ids]
            result = rig.lbs(vertices, weights[ids], effective, normalized)
            distance = np.linalg.norm(result-result[:1], axis=-1)
            poses = []
            for i in range(len(transforms)):
                worst = int(np.argmax(distance[i]))
                poses.append({'maxDisplacement': float(distance[i, worst]),
                              'movingVertices': int((distance[i] > 1e-8).sum()),
                              'worstVertex': int(ids[worst])})
            rows[mode][str(coefficient)] = poses
    return {'selection': 'actual nonzero BreastSize support' if female else 'explicit thorax ROI with Spine/Clavicle support',
            'selectedCount': len(ids), 'selectedVertices': ids.tolist(),
            'positiveHeadDescendantCount': int((head_mass > 0).sum()), 'maxPackedHeadWeight': float(head_mass.max()),
            'measurements': rows}


def build_report(body_root, skeleton, profile, output, pynifly=None):
    body_root, skeleton, profile = [Path(x).resolve(strict=True) for x in (body_root, skeleton, profile)]
    import sys
    sys.path.insert(0, str(ROOT/'vr'))
    import body_resource as vr
    p = vr.load_profile(profile)
    inputs = [skeleton, profile, *[body_root/b[k] for b in p['bodies'].values() for k in ('nif', 'tri')]]
    expected = {str(skeleton): p['skeletonSha256']}
    for body in p['bodies'].values():
        expected.update({str(body_root/body[k]): body[k+'Sha256'] for k in ('nif', 'tri')})
    if any(rig.sha256(path) != value for path, value in expected.items()):
        raise ValueError('Published resource/skeleton pin mismatch')
    before = {str(x): rig.sha256(x) for x in inputs}
    source = [Path(__file__), ROOT/'scripts/audit-vr-head.py', ROOT/'scripts/breast_rig.py', ROOT/'scripts/surface_collar.py', ROOT/'vr/body_resource.py']
    source_before = {str(x): rig.sha256(x) for x in source}
    out = rig.safe_output(output, inputs)
    api, Trip, dependency = rig.load_pynifly(pynifly)
    dependencies = [*sorted((dependency/'pyn').glob('*.py')),
                    *sorted((dependency/'tri').glob('*.py')), dependency/'NiflyDLL.dll']
    dependency_before = {str(x): rig.sha256(x) for x in dependencies}
    skel = api.NifFile(str(skeleton))
    rest = {n: rig.matrix(node.global_transform) for n, node in skel.nodes.items()}
    parent = {n: node.parent.name if node.parent else None for n, node in skel.nodes.items()}
    head_names = descendants(parent, HEAD)
    bank = pose_bank(rest, parent)
    all_poses = [impose(rest, parent, edits) for _, edits, _ in bank]
    report = {'status': 'offline-head-only-motion-audit-no-runtime-or-camera-acceptance',
              'inputs': before, 'sourceSha256': source_before, 'bodies': {},
              'poses': [{'name': name, 'kind': kind, 'localReplacements': {n: x.tolist() for n, x in edit.items()}}
                        for name, edit, kind in bank],
              'convention': 'Actual serialized B/C frames and scale. Raw packed and normalized LBS are separate mathematical models.',
              'limits': ['Only Head and descendants move; real VRIK also changes torso/arms and consumes tracked HMD frames.',
                         'Scale0.01/position0.25 represents the inspected visibility operation, not its active runtime branch on this setup.',
                         'Y+/-20 and +/-15degree rotations are explicitly imposed examples, not safe ranges or actual motion traces.',
                         'Female selection uses existing BreastSize deltas; male ROI is an explicit geometric comparison, not automatic anatomy detection.',
                         'No skeleton/mesh/weights/flags are written. No camera clearance, engine routing, physics or runtime conclusion.']}
    for sex, body in p['bodies'].items():
        nif = api.NifFile(str(body_root/body['nif']))
        raw = Trip.from_filepath(str(body_root/body['tri'])).shapes
        names = sorted({n for s in nif.shapes for n in s.bone_weights})
        if not set(names) <= set(rest):
            raise ValueError('Weighted node missing from pinned skeleton')
        transforms = np.asarray([[pose[n] for n in names] for pose in all_poses])
        shapes = {}
        for shape in nif.shapes:
            row = audit_shape(shape, raw, names, rest, transforms, head_names, sex == 'female')
            if row is not None:
                shapes[shape.name] = row
        report['bodies'][sex] = shapes
    if any(rig.sha256(path) != value for path, value in {**before, **source_before, **dependency_before}.items()):
        raise ValueError('Input/source/dependency changed during audit')
    report['dependencySha256'] = dependency_before
    out.mkdir(parents=True, exist_ok=False)
    target = out/'head-motion-report.json'
    target.write_text(json.dumps(report, indent=2), encoding='utf-8')
    return target
