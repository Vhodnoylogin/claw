"""Read-only static morph diagnostics; numeric evidence, never an anatomy oracle.

The core accepts complete decoded fields and explicit geometry. It does not
author geometry, infer a human-to-wolf mapping, or certify intersections.
"""
from __future__ import annotations

import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import platform
import sys

import numpy as np

import tri_patch

ROOT = Path(__file__).resolve().parents[1]


def shape_map(shapes):
    result = {}
    for shape in shapes:
        if shape.name in result:
            raise ValueError('Duplicate NIF shape name: '+shape.name)
        result[shape.name] = shape
    return result


def positions(values):
    result = np.asarray(values, dtype=float)
    if result.ndim != 2 or result.shape[1] != 3 or not np.isfinite(result).all():
        raise ValueError('Expected finite Nx3 positions/field')
    return result


def triangles(values, count):
    raw = np.asarray(values)
    if raw.ndim != 2 or raw.shape[1] != 3 or raw.dtype.kind not in 'iu':
        raise ValueError('Expected integer Nx3 triangle indices')
    result = raw.astype(np.int64)
    if np.any(result < 0) or np.any(result >= count):
        raise ValueError('Triangle vertex outside shape')
    return result


def field_pair(a, b, active_epsilon=1e-5):
    """Direction, support and best one-field fit, without calling fields aliases."""
    a, b = positions(a), positions(b)
    if a.shape != b.shape or not np.isfinite(active_epsilon) or active_epsilon < 0:
        raise ValueError('Compatible fields and nonnegative finite epsilon required')
    aa, bb, ab = float(np.sum(a*a)), float(np.sum(b*b)), float(np.sum(a*b))
    ma, mb = np.linalg.norm(a, axis=1) > active_epsilon, np.linalg.norm(b, axis=1) > active_epsilon
    union = int(np.count_nonzero(ma | mb))
    cosine = float(np.clip(ab / np.sqrt(aa*bb), -1, 1)) if aa and bb else None
    gain = ab / aa if aa else None
    return {'cosine': cosine, 'fitBFromAGain': gain,
            'relativeFitResidual': float(np.sqrt(np.sum((b-gain*a)**2)/bb)) if aa and bb else None,
            'activeIntersection': int(np.count_nonzero(ma & mb)), 'activeUnion': union,
            'supportJaccard': int(np.count_nonzero(ma & mb))/union if union else None,
            'energyA': aa, 'energyB': bb}


def field_summary(delta, bone_weights=None):
    delta = positions(delta)
    energy = np.sum(delta*delta, axis=1)
    lengths = np.sqrt(energy)
    result = {'activeVerticesOver1eMinus5': int(np.count_nonzero(lengths > 1e-5)),
              'peakDelta': float(lengths.max(initial=0)), 'squaredDeltaSum': float(energy.sum()),
              'peakVertex': int(np.argmax(lengths)) if len(lengths) else None}
    if bone_weights is not None:
        # Allocate delta energy by actual normalized stored weight, instead of
        # declaring a whole shape called "head" to be anatomical head tissue.
        sums = np.zeros(len(delta))
        for pairs in bone_weights.values():
            for vertex, weight in pairs:
                if not 0 <= vertex < len(delta) or not np.isfinite(weight) or weight < 0:
                    raise ValueError('Invalid stored skin weight')
                sums[vertex] += weight
        if np.any(sums <= 0):
            raise ValueError('Unweighted vertex in region diagnostic')
        rows = {}
        for bone, pairs in bone_weights.items():
            rows[bone] = float(sum(energy[i]*w/sums[i] for i, w in pairs))
        result['normalizedBoneAllocatedEnergy'] = dict(sorted(rows.items(), key=lambda row: (-row[1], row[0])))
        # These are declared proxy families, not an inferred anatomical segment.
        for key, tokens in [('headJawEarWeight', ('NPC Head', 'NPC Jaw', 'NPC Ear')),
                            ('spineClavicleWeight', ('NPC Spine', 'NPC Clavicle', 'NPC L Clavicle'))]:
            result[key+'EnergyFraction'] = sum(v for n, v in rows.items() if n.startswith(tokens))/float(energy.sum()) if energy.sum() else 0.
    return result


def boundary_vertices(faces, count):
    faces = triangles(faces, count)
    edges = np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1)
    unique, counts = np.unique(edges, axis=0, return_counts=True)
    return np.unique(unique[counts == 1])


def freeze_join(a, fa, b, fb, tolerance=1e-4):
    """All cross-shape boundary vertex pairs within a declared neutral distance.

    This deliberately reports vertex-pair candidates, not full surface seams.
    Chunking bounds memory; exact distance tests avoid quantized weld buckets.
    """
    a, b = positions(a), positions(b)
    if not np.isfinite(tolerance) or tolerance < 0:
        raise ValueError('Finite nonnegative join tolerance required')
    ia, ib = boundary_vertices(fa, len(a)), boundary_vertices(fb, len(b))
    pairs = []
    for start in range(0, len(ia), 128):
        block = ia[start:start+128]
        d2 = np.sum((a[block, None]-b[None, ib])**2, axis=-1)
        x, y = np.nonzero(d2 <= tolerance*tolerance)
        pairs.extend(zip(block[x].tolist(), ib[y].tolist()))
    return np.asarray(pairs, dtype=np.int64).reshape(-1, 2)


def join_metrics(a0, b0, a, b, pairs):
    pairs = np.asarray(pairs, dtype=np.int64).reshape(-1, 2)
    if not len(pairs):
        return {'candidatePairs': 0, 'maxNeutralDistance': None, 'maxDistance': None,
                'maxDistanceIncrease': None, 'maxRelativeDisplacement': None}
    old = positions(a0)[pairs[:, 0]]-positions(b0)[pairs[:, 1]]
    new = positions(a)[pairs[:, 0]]-positions(b)[pairs[:, 1]]
    before, after = np.linalg.norm(old, axis=1), np.linalg.norm(new, axis=1)
    drift = np.linalg.norm(new-old, axis=1)
    worst = int(np.argmax(drift))
    return {'candidatePairs': len(pairs), 'maxNeutralDistance': float(before.max()),
            'maxDistance': float(after.max()), 'maxDistanceIncrease': float((after-before).max()),
            'maxRelativeDisplacement': float(drift.max()), 'worstPair': pairs[worst].tolist()}


def surface_metrics(neutral, current, faces, area_epsilon=1e-10):
    """Finite-state area/edge and neutral-normal diagnostics, no collision test."""
    neutral, current = positions(neutral), positions(current)
    if neutral.shape != current.shape:
        raise ValueError('Incompatible surface positions')
    faces = triangles(faces, len(neutral))
    n, c = neutral[faces], current[faces]
    n_cross = np.cross(n[:, 1]-n[:, 0], n[:, 2]-n[:, 0])
    c_cross = np.cross(c[:, 1]-c[:, 0], c[:, 2]-c[:, 0])
    n_area, c_area = np.linalg.norm(n_cross, axis=1)/2, np.linalg.norm(c_cross, axis=1)/2
    valid = n_area > area_epsilon
    turned = valid & (np.sum(n_cross*c_cross, axis=1) < 0)
    collapsed = valid & (c_area <= area_epsilon)
    edges = np.unique(np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1), axis=0)
    ne = np.linalg.norm(neutral[edges[:, 1]]-neutral[edges[:, 0]], axis=1)
    ce = np.linalg.norm(current[edges[:, 1]]-current[edges[:, 0]], axis=1)
    edge_valid = ne > 1e-10
    strain = np.abs(ce[edge_valid]/ne[edge_valid]-1)
    return {'triangleCount': len(faces), 'neutralDegenerateCount': int(np.count_nonzero(~valid)),
            'normalTurnCount': int(np.count_nonzero(turned)), 'normalTurnTriangleIds': np.flatnonzero(turned).tolist(),
            'newCollapsedCount': int(np.count_nonzero(collapsed)), 'newCollapsedTriangleIds': np.flatnonzero(collapsed).tolist(),
            'minimumAreaRatio': float((c_area[valid]/n_area[valid]).min()) if valid.any() else None,
            'maximumAbsoluteEdgeStrain': float(strain.max()) if len(strain) else None}


def sample_states(names, pairs=()):
    names = sorted(names)
    if not names or len(names) != len(set(names)):
        raise ValueError('Nonempty unique morph names required')
    result = [('neutral', {})]
    result += [(name+'=1', {name: 1.}) for name in names]
    for a, b in sorted({tuple(sorted(pair)) for pair in pairs}):
        if a == b or a not in names or b not in names:
            raise ValueError('Invalid pair state')
        result.append((a+'+'+b, {a: 1., b: 1.}))
    result += [('all=0.5', dict.fromkeys(names, .5)), ('all=1', dict.fromkeys(names, 1.))]
    return result


def decode_fields(data, public, counts):
    """Complete independent sparse decode plus public-reader cross-check.

    PyNifly drops triples whose every component is at most 0.0001. Keep those
    serialized values in our measurements and explicitly account for the drop.
    """
    records = tri_patch.offsets(data)
    result = {}
    for shape, morphs in public.items():
        if shape not in counts:
            raise ValueError('TRI shape absent from NIF: '+shape)
        for morph in morphs:
            result[shape, morph] = np.zeros((counts[shape], 3))
    for (shape, morph, vertex), record in records.items():
        if (shape, morph) not in result or vertex >= counts[shape]:
            raise ValueError('TRI record outside NIF/public catalog')
        result[shape, morph][vertex] = np.asarray(record.packed)*record.scale
    seen = set()
    for shape, morphs in public.items():
        for morph, values in morphs.items():
            for vertex, delta in values:
                key = shape, morph, vertex
                if key not in records or key in seen or not np.array_equal(result[shape, morph][vertex], delta):
                    raise ValueError('Public TRI reader disagrees with complete decoder')
                seen.add(key)
    skipped = {key for key, rec in records.items() if max(abs(x*rec.scale) for x in rec.packed) <= .0001}
    if set(records)-seen != skipped:
        raise ValueError('Unexpected public-reader omission')
    return result, {'serializedPairs': len(records), 'publicReaderPairs': len(seen),
                    'retainedSubthresholdPairs': len(skipped)}


def pin(path):
    path = Path(path).resolve(strict=True)
    data = path.read_bytes()
    if data.startswith(b'version https://git-lfs.github.com/spec/v1'):
        raise ValueError('Unmaterialized LFS input: '+str(path))
    return {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}


def safe_output(path, inputs):
    out = Path(path).resolve()
    blocked = [ROOT, *[Path(p).resolve().parent for p in inputs]]
    if out.exists() or any(out == p or p in out.parents for p in blocked):
        raise ValueError('Output must be new and outside source directories/repository')
    if any(p.casefold() in {'mods', 'mo2', 'modorganizer', 'overwrite', 'skyrimvr', 'skyrim vr', 'skyrim special edition'} for p in out.parts):
        raise ValueError('Output points into a live game/mod-manager tree')
    return out


def transform(buf):
    result = np.eye(4)
    result[:3, :3] = np.asarray([list(x) for x in buf.rotation])*float(buf.scale)
    result[:3, 3] = list(buf.translation)
    if not np.isfinite(result).all() or abs(np.linalg.det(result[:3, :3])) < 1e-12:
        raise ValueError('Invalid shape transform')
    return result


def build(low, tri, output, *, high=None, skin=('body', 'head'), pynifly=None, join_tolerance=1e-4):
    import locate
    inputs = [Path(low).resolve(strict=True), Path(tri).resolve(strict=True)]
    if high is not None:
        inputs.append(Path(high).resolve(strict=True))
    addon = Path(pynifly or locate.local_config(__file__).get('pynifly', '')).resolve()
    if not (addon/'pyn/pynifly.py').is_file():
        raise ValueError('Configure PyNifly in build.local.json or --pynifly')
    files = [*inputs, Path(__file__), ROOT/'scripts/audit-morph-quality.py',
             ROOT/'scripts/tri_patch.py', ROOT/'scripts/locate.py', addon/'NiflyDLL.dll',
             *sorted((addon/'pyn').rglob('*.py')), addon/'tri/tripfile.py']
    pins = [pin(p) for p in files]
    out = safe_output(output, inputs)
    sys.path.insert(0, str(addon))
    from pyn import pynifly as api
    api.NifFile.Load(str(addon/'NiflyDLL.dll'))
    spec = importlib.util.spec_from_file_location('claw_quality_trip', addon/'tri/tripfile.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    low_nif = api.NifFile(str(inputs[0]))
    high_nif = api.NifFile(str(inputs[2])) if high is not None else low_nif
    low_shapes, high_shapes = (shape_map(nif.shapes) for nif in (low_nif, high_nif))
    if set(low_shapes) != set(high_shapes):
        raise ValueError('Duplicate/mismatched shape names')
    skin = tuple(skin)
    if not skin or len(set(skin)) != len(skin) or not set(skin) <= set(low_shapes):
        raise ValueError('Explicit unique existing skin shapes required')
    geometry, high_geometry, faces, matrices = {}, {}, {}, {}
    for name, shape in low_shapes.items():
        high_shape = high_shapes[name]
        v, hv = positions(shape.verts), positions(high_shape.verts)
        f, hf = triangles(shape.tris, len(v)), triangles(high_shape.tris, len(hv))
        matrix = transform(shape.global_transform)
        if v.shape != hv.shape or not np.array_equal(f, hf) or not np.array_equal(matrix, transform(high_shape.global_transform)):
            raise ValueError('Endpoint topology/shape frame changed: '+name)
        matrices[name] = matrix
        geometry[name] = v@matrix[:3, :3].T+matrix[:3, 3]
        high_geometry[name] = hv@matrix[:3, :3].T+matrix[:3, 3]
        faces[name] = f
    public = module.TripFile.from_filepath(str(inputs[1]))
    if not public.is_valid:
        raise ValueError('Public TRI reader rejected input')
    fields, decoded = decode_fields(inputs[1].read_bytes(), public.shapes, {n: len(v) for n, v in geometry.items()})
    for (name, morph), delta in fields.items():
        fields[name, morph] = delta@matrices[name][:3, :3].T
    names = sorted({m for n, m in fields})
    def field(name, morph):
        return fields.get((name, morph), np.zeros_like(geometry[name]))
    summaries = {m: {n: field_summary(field(n, m), low_shapes[n].bone_weights) for n in geometry} for m in names}
    vectors = {m: np.concatenate([field(n, m) for n in skin]) for m in names}
    pairs = []
    for a, b in itertools.combinations(names, 2):
        row = field_pair(vectors[a], vectors[b])
        if row['cosine'] is not None and abs(row['cosine']) >= .4:
            pairs.append({'a': a, 'b': b, **row})
    pairs.sort(key=lambda row: (-abs(row['cosine']), row['a'], row['b']))
    states = sample_states(names, [(p['a'], p['b']) for p in pairs])
    joins = {(a, b): freeze_join(geometry[a], faces[a], geometry[b], faces[b], join_tolerance)
             for a, b in itertools.combinations(skin, 2)}
    report = {'schemaVersion': 1, 'status': 'building', 'inputsAndExecutedFiles': pins,
              'environment': {'python': platform.python_version(), 'numpy': np.__version__},
              'scope': 'Complete serialized additive TRI in global shape/file coordinates. No skinning, skeleton poses, physics, renderer, anatomical region proof or global self-intersection test. Finite declared states are samples, not a continuous cube guarantee. Normal turns can include legitimate large rotations. Frozen boundary vertex pairs are candidates, not complete seams.',
              'skinShapes': skin, 'triDecode': decoded, 'publicNames': names, 'fieldSummaries': summaries,
              'skinPairsAbsoluteCosineAtLeast0Point4': pairs, 'joinTolerance': join_tolerance,
              'frozenJoinPairs': {a+'|'+b: p.tolist() for (a, b), p in joins.items()},
              'states': [{'name': n, 'values': v} for n, v in states], 'weights': {}}
    out.mkdir(parents=True)
    try:
        for weight in ((0., .5, 1.) if high is not None else (0.,)):
            neutral = {n: geometry[n]+weight*(high_geometry[n]-geometry[n]) for n in geometry}
            rows = {}
            for label, state in states:
                current = {n: v+sum((value*field(n, m) for m, value in state.items()), np.zeros_like(v)) for n, v in neutral.items()}
                rows[label] = {'surfaces': {n: surface_metrics(neutral[n], current[n], faces[n]) for n in geometry},
                               'joins': {a+'|'+b: join_metrics(neutral[a], neutral[b], current[a], current[b], p) for (a, b), p in joins.items()}}
            report['weights'][str(weight)] = rows
            print('MORPH_QUALITY|weight='+str(weight)+'|states='+str(len(states)), flush=True)
        if any(pin(row['path']) != row for row in pins):
            raise ValueError('Input/executed dependency changed during audit')
        report['status'] = 'completed-read-only-static-sample-diagnostics-visual-and-runtime-pending'
    except Exception:
        report['status'] = 'FAILED-incomplete-audit'
        raise
    finally:
        (out/'morph-quality.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    return out/'morph-quality.json'
