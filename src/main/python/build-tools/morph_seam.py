"""Opt-in local TRI seam repair, preserving every existing morph record byte.

Only a missing, explicitly named target-shape record is added. Exact duplicate
boundary constraints are mandatory; an infeasible band is rejected, not relaxed.
"""
from __future__ import annotations

import heapq
import json
from pathlib import Path
import struct
import sys

import numpy as np

import morph_quality as quality
import tri_patch


def append_record(data, shape, morph, scale, packed):
    """Append one missing shape/morph record, preserving the old envelope exactly."""
    tri_patch.offsets(data)  # Reject duplicate names/vertices and unsupported tails.
    if any(type(i) is not int for i in packed):
        raise ValueError('Integer vertex keys required')
    packed = {i: tuple(v) for i, v in packed.items()}
    if not packed or len(packed) > 65535 or not np.isfinite(scale) or scale <= 0:
        raise ValueError('Nonempty bounded packed field and positive scale required')
    if any(not 0 <= i <= 65535 or len(v) != 3 or any(type(x) is not int or not -32768 <= x <= 32767 for x in v) for i, v in packed.items()):
        raise ValueError('Invalid signed int16 record')
    cursor = 4
    def take(fmt):
        nonlocal cursor
        value = struct.unpack_from(fmt, data, cursor)
        cursor += struct.calcsize(fmt)
        return value
    def name():
        nonlocal cursor
        size, = take('<B')
        value = data[cursor:cursor+size].decode('iso-8859-15')
        cursor += size
        return value
    found = None
    for _ in range(take('<H')[0]):
        current = name(); count_at = cursor; count, = take('<H')
        for _ in range(count):
            current_morph = name(); _, size = take('<fH'); cursor += size*8
            if current == shape and current_morph == morph:
                raise ValueError('Target morph already exists; replacement is unsupported')
        if current == shape:
            found = count_at, count, cursor
    if found is None:
        raise ValueError('Target shape absent from TRI')
    count_at, count, insert_at = found
    if count == 65535:
        raise ValueError('TRI morph count overflow')
    encoded = morph.encode('iso-8859-15')
    if not 0 < len(encoded) <= 255:
        raise ValueError('Invalid TRI morph name')
    record = struct.pack('<B', len(encoded))+encoded+struct.pack('<fH', scale, len(packed))
    record += b''.join(struct.pack('<H3h', i, *v) for i, v in sorted(packed.items()))
    output = bytearray(data[:insert_at]+record+data[insert_at:])
    struct.pack_into('<H', output, count_at, count+1)
    restored = bytearray(output[:insert_at]+output[insert_at+len(record):])
    struct.pack_into('<H', restored, count_at, count)
    if bytes(restored) != data:
        raise ValueError('Unrelated TRI envelope changed')
    tri_patch.offsets(output)
    return bytes(output), {'changedOriginalField': 'target shape uint16 morph count only',
                           'countOffset': count_at, 'insertionOffset': insert_at,
                           'insertedBytes': len(record), 'originalStreamReconstructionExact': True}


def harmonic_band(vertices, faces, anchors, values, protected, width):
    """Exact-coordinate weld graph, Dirichlet anchors, zero outside geodesic band."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.linalg import spsolve
    vertices = quality.positions(vertices)
    faces = quality.triangles(faces, len(vertices))
    anchors = np.asarray(anchors, dtype=np.int64)
    values = quality.positions(values)
    protected = np.asarray(protected, dtype=np.int64)
    if values.shape != (len(anchors), 3) or not len(anchors) or not np.isfinite(width) or width <= 0:
        raise ValueError('Finite nonempty constraints and positive band width required')
    if np.any(anchors < 0) or np.any(anchors >= len(vertices)) or np.any(protected < 0) or np.any(protected >= len(vertices)):
        raise ValueError('Constraint vertex out of range')
    unique, inverse = np.unique(vertices, axis=0, return_inverse=True)
    seeds = {}
    for i, value in zip(inverse[anchors], values):
        if i in seeds and not np.array_equal(seeds[i], value):
            raise ValueError('Inconsistent exact duplicate seam constraints')
        seeds[int(i)] = value
    zero = set(inverse[protected].tolist())
    if any(np.any(value != 0) for i, value in seeds.items() if i in zero):
        raise ValueError('Nonzero seam constraint conflicts with protected split seam')
    welded = inverse[faces]
    edges = np.unique(np.sort(np.concatenate([welded[:, [0, 1]], welded[:, [1, 2]], welded[:, [2, 0]]]), axis=1), axis=0)
    edges = edges[edges[:, 0] != edges[:, 1]]
    adjacency = [[] for _ in unique]
    for (a, b), length in zip(edges, np.linalg.norm(unique[edges[:, 0]]-unique[edges[:, 1]], axis=1)):
        if length <= 0:
            raise ValueError('Invalid welded solver edge')
        adjacency[a].append((int(b), float(length)))
        adjacency[b].append((int(a), float(length)))
    distance = np.full(len(unique), np.inf)
    queue = []
    for i in seeds:
        distance[i] = 0.; heapq.heappush(queue, (0., i))
    while queue:
        old, i = heapq.heappop(queue)
        if old != distance[i] or old >= width:
            continue
        for j, length in adjacency[i]:
            new = old+length
            if new < distance[j]:
                distance[j] = new; heapq.heappush(queue, (new, j))
    free = [i for i in np.flatnonzero(distance < width) if i not in seeds and i not in zero]
    index = {int(i): j for j, i in enumerate(free)}
    correction = np.zeros((len(unique), 3))
    for i, value in seeds.items():
        correction[i] = value
    if free:
        rows, columns, entries = [], [], []
        rhs = np.zeros((len(free), 3))
        for i in free:
            row = index[i]; total = 0.
            for j, length in adjacency[i]:
                weight = 1./length; total += weight
                if j in index:
                    rows.append(row); columns.append(index[j]); entries.append(-weight)
                else:
                    rhs[row] += weight*correction[j]
            rows.append(row); columns.append(row); entries.append(total)
        matrix = coo_matrix((entries, (rows, columns)), shape=(len(free), len(free))).tocsr()
        correction[free] = spsolve(matrix, rhs)
        residual = float(np.max(abs(matrix@correction[free]-rhs)))
    else:
        residual = 0.
    if not np.isfinite(correction).all() or residual > 1e-8:
        raise ValueError('Nonfinite or inaccurate harmonic solve')
    result = correction[inverse]
    if not np.array_equal(result[anchors], values) or np.any(result[protected] != 0) or np.any(result[distance[inverse] >= width] != 0):
        raise ValueError('Exact fixed constraints failed')
    return result, {'width': float(width), 'freeWeldedVertices': len(free),
                    'nonzeroVertices': int(np.any(result != 0, axis=1).sum()),
                    'outsideBandVertices': np.flatnonzero(distance[inverse] >= width).tolist(),
                    'fixedProtectedVertices': protected.tolist(), 'solverResidual': residual}


def quantize(delta, scale):
    delta = quality.positions(delta)
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError('Invalid quantization scale')
    integer = np.rint(delta/scale)
    if np.max(abs(integer), initial=0) > 32767:
        raise ValueError('Correction outside source quantization scale')
    integer = integer.astype(np.int16)
    return integer, integer.astype(float)*scale


def reference_band(vertices, faces, anchors, values, protected, width, reference):
    """Nearest-body field with a C1 geodesic taper; exact Dirichlet constraints.

    Reference vectors come from actual frozen source triangles, not a new waist
    formula. The taper's derivative is zero at both ends of the declared band.
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import dijkstra
    vertices, reference, values = map(quality.positions, (vertices, reference, values))
    faces = quality.triangles(faces, len(vertices))
    anchors, protected = (np.asarray(a, dtype=np.int64) for a in (anchors, protected))
    if reference.shape != vertices.shape or values.shape != (len(anchors), 3) or not len(anchors) or not np.isfinite(width) or width <= 0:
        raise ValueError('Finite reference field and positive width required')
    if np.any(anchors < 0) or np.any(anchors >= len(vertices)) or np.any(protected < 0) or np.any(protected >= len(vertices)):
        raise ValueError('Constraint vertex out of range')
    unique, inverse = np.unique(vertices, axis=0, return_inverse=True)
    seeds = {}
    for i, value in zip(inverse[anchors], values):
        if i in seeds and not np.array_equal(seeds[i], value):
            raise ValueError('Inconsistent exact duplicate seam constraints')
        seeds[int(i)] = value
    protected_groups = set(inverse[protected].tolist())
    if any(np.any(v != 0) for i, v in seeds.items() if i in protected_groups):
        raise ValueError('Nonzero seam constraint conflicts with protected split seam')
    welded = inverse[faces]
    edges = np.unique(np.sort(np.concatenate([welded[:, [0, 1]], welded[:, [1, 2]], welded[:, [2, 0]]]), axis=1), axis=0)
    edges = edges[edges[:, 0] != edges[:, 1]]
    length = np.linalg.norm(unique[edges[:, 0]]-unique[edges[:, 1]], axis=1)
    graph = coo_matrix((np.r_[length, length], (np.r_[edges[:, 0], edges[:, 1]], np.r_[edges[:, 1], edges[:, 0]])), shape=(len(unique), len(unique))).tocsr()
    distance = dijkstra(graph, directed=False, indices=sorted(seeds), min_only=True, limit=width)
    fraction = np.clip(distance[inverse]/width, 0, 1)
    result = reference*(1-fraction*fraction*(3-2*fraction))[:, None]
    result[np.isin(inverse, list(protected_groups))] = 0.
    for i, value in seeds.items(): result[inverse == i] = value
    if not np.array_equal(result[anchors], values) or np.any(result[protected] != 0) or np.any(result[distance[inverse] >= width] != 0):
        raise ValueError('Exact fixed constraints failed')
    return result, {'width': float(width), 'method': 'actual-body-triangle-field-C1-geodesic-taper',
                    'nonzeroVertices': int(np.any(result != 0, axis=1).sum()),
                    'outsideBandVertices': np.flatnonzero(distance[inverse] >= width).tolist(),
                    'fixedProtectedVertices': np.asarray(protected).tolist()}


def build(low, high, tri, output, *, skeleton=None, pynifly=None,
          widths=(2., 4., 6., 8., 8.5, 9., 10., 12., 16.), expected_pairs=135):
    import breast_rig as rig
    import locate
    import scipy
    inputs = [Path(x).resolve(strict=True) for x in (low, high, tri)]
    low, high, tri = inputs
    if skeleton is not None:
        skeleton = Path(skeleton).resolve(strict=True); inputs.append(skeleton)
    widths = tuple(float(x) for x in widths)
    if not widths or tuple(sorted(set(widths))) != widths or not np.isfinite(widths).all() or min(widths) <= 0 or max(widths) > 16:
        raise ValueError('Explicit ascending unique band widths in (0,16] required')
    addon = Path(pynifly or locate.local_config(__file__).get('pynifly', '')).resolve(strict=True)
    source_files = [Path(__file__), quality.ROOT / 'src/main/python/build-tools/repair-morph-seam.py', quality.ROOT / 'src/main/python/build-tools/morph_quality.py',
                    quality.ROOT / 'src/main/python/build-tools/tri_patch.py', quality.ROOT / 'src/main/python/build-tools/breast_rig.py',
                    quality.ROOT / 'src/main/python/build-tools/locate.py', quality.ROOT / 'src/main/python/build-tools/surface_collar.py',
                    *sorted((addon/'pyn').rglob('*.py')), addon/'tri/tripfile.py', addon/'NiflyDLL.dll']
    source_files += [quality.ROOT / 'src/main/resources/recipes/surface-collars.json', quality.ROOT / 'src/main/python/build-tools/body_weight.py',
                     quality.ROOT / 'src/main/python/build-tools/morph_calibration.py', quality.ROOT / 'src/main/python/build-tools/head_split.py',
                     quality.ROOT / 'src/main/python/build-tools/vr_head.py']
    if skeleton is not None:
        source_files += [quality.ROOT / 'src/main/python/build-tools/composed_vr.py', quality.ROOT / 'src/main/python/build-tools/head_split.py', quality.ROOT / 'src/main/python/build-tools/vr_head.py']
    pins = [quality.pin(p) for p in [*inputs, *source_files]]
    out = quality.safe_output(output, inputs)
    api, Trip, _ = rig.load_pynifly(addon)
    n0, n1 = (api.NifFile(str(p)) for p in (low, high))
    shapes, ends = (quality.shape_map(nif.shapes) for nif in (n0, n1))
    if set(shapes) != set(ends) or not {'body', 'head', 'head_CLAWHead'} <= set(shapes):
        raise ValueError('Expected composed male skin family')
    for name, shape in shapes.items():
        if shape.tris != ends[name].tris or len(shape.verts) != len(ends[name].verts) or shape.bone_weights != ends[name].bone_weights:
            raise ValueError('Endpoint topology/weights differ')
        if not shape.has_global_to_skin or not ends[name].has_global_to_skin:
            raise ValueError('Explicit endpoint skin frames required')
        if not np.array_equal(rig.matrix(shape.global_to_skin), rig.matrix(ends[name].global_to_skin)):
            raise ValueError('Endpoint skin frames differ')
        if any(not np.array_equal(rig.matrix(shape.get_shape_skin_to_bone(bone)), rig.matrix(ends[name].get_shape_skin_to_bone(bone))) for bone in shape.bone_weights):
            raise ValueError('Endpoint bone binds differ')
        if not np.array_equal(quality.transform(shape.global_transform), np.eye(4)) or not np.array_equal(quality.transform(ends[name].global_transform), np.eye(4)):
            raise ValueError('Repair requires the reviewed common identity shape frame')
    vertices = {n: np.asarray(s.verts, float) for n, s in shapes.items()}
    high_vertices = {n: np.asarray(s.verts, float) for n, s in ends.items()}
    target = 'CLAWTorsoWaistNarrow'
    source_data = tri.read_bytes()
    raw = Trip.from_filepath(str(tri))
    if not raw.is_valid:
        raise ValueError('Public TRI read rejected')
    fields, decode = quality.decode_fields(source_data, raw.shapes, {n: len(v) for n, v in vertices.items()})
    if ('head', target) in fields:
        raise ValueError('This repair requires the missing male target/head record')
    offsets = tri_patch.offsets(source_data)
    body_records = {i: r for (n, m, i), r in offsets.items() if n == 'body' and m == target}
    scales = {r.scale for r in body_records.values()}
    if len(scales) != 1:
        raise ValueError('Expected one existing source scale')
    scale = scales.pop()
    pairs = quality.freeze_join(vertices['body'], shapes['body'].tris, vertices['head'], shapes['head'].tris, 0.)
    protected_pairs = quality.freeze_join(vertices['head'], shapes['head'].tris, vertices['head_CLAWHead'], shapes['head_CLAWHead'].tris, 0.)
    if len(pairs) != expected_pairs or len(protected_pairs) != 141:
        raise ValueError('Exact reviewed boundary count changed')
    anchors = pairs[:, 1]
    values = np.asarray([body_records[int(i)].packed if int(i) in body_records else (0, 0, 0) for i in pairs[:, 0]], dtype=float)*scale
    protected = np.unique(protected_pairs[:, 0])
    import surface_collar as surface
    from body_weight import Projector
    reference_binding = surface.Bindings(vertices['head'], vertices['body'], shapes['body'].tris,
                                         Projector(vertices['body'], shapes['body'].tris))
    reference = reference_binding.evaluate(fields['body', target])
    reference_anchor_error = float(np.linalg.norm(reference[anchors]-values, axis=1).max())
    if reference_anchor_error != 0:
        raise ValueError('Actual body-triangle field disagrees with exact anchor constraints')
    weights = (0., .5, 1.)
    # Existing source-body strain is an explicit numerical budget, not an
    # invented claim that a particular stretch looks good.
    budgets = {}
    for weight in weights:
        v = vertices['body']+weight*(high_vertices['body']-vertices['body'])
        budgets[weight] = quality.surface_metrics(v, v+fields['body', target], shapes['body'].tris)['maximumAbsoluteEdgeStrain']
    candidates = []; chosen = None
    for width in widths:
        delta, detail = reference_band(vertices['head'], shapes['head'].tris, anchors, values, protected, width, reference)
        integer, delta = quantize(delta, scale)
        if not np.array_equal(delta[anchors], values) or np.any(delta[protected] != 0):
            raise ValueError('Quantization violated exact fixed constraints')
        metrics = {}; passed = True
        for weight in weights:
            v = vertices['head']+weight*(high_vertices['head']-vertices['head'])
            for coefficient in (.5, 1.):
                row = quality.surface_metrics(v, v+coefficient*delta, shapes['head'].tris)
                metrics[str(weight)+'|'+str(coefficient)] = row
                passed &= row['normalTurnCount'] == 0 and row['newCollapsedCount'] == 0 and row['maximumAbsoluteEdgeStrain'] <= budgets[weight]+1e-12
        candidates.append({**detail, 'numericGatePassed': bool(passed), 'sampledHeadMetrics': metrics})
        if passed and chosen is None:
            chosen = integer, delta, detail
    if chosen is None:
        raise ValueError('No bounded collar band met exact constraints and source-body strain budget')
    integer, delta, selected = chosen
    packed = {i: tuple(int(x) for x in v) for i, v in enumerate(integer) if np.any(v != 0)}
    candidate_data, envelope = append_record(source_data, 'head', target, scale, packed)
    output_records = tri_patch.offsets(candidate_data)
    if any(output_records.get(key).scale != old.scale or output_records[key].packed != old.packed for key, old in offsets.items()):
        raise ValueError('Original serialized record changed')
    if set(output_records)-set(offsets) != {('head', target, i) for i in packed}:
        raise ValueError('Unrelated serialized records added')
    names = sorted({m for n, m in fields})
    vectors = {m: np.concatenate([fields.get((n, m), np.zeros_like(vertices[n])) for n in ('body', 'head', 'head_CLAWHead')]) for m in names}
    comparisons = [pair for pair in __import__('itertools').combinations(names, 2)
                   if (lambda x: x is not None and abs(x) >= .4)(quality.field_pair(vectors[pair[0]], vectors[pair[1]])['cosine'])]
    extra = [(target, n) for n in ('CLAWTorsoGirth', 'CLAWTorsoBellyRound', 'CLAWHeadSize', 'CLAWTorsoChestSize')]
    states = quality.sample_states(names, comparisons+extra)
    report = {'schemaVersion': 1, 'status': 'building', 'inputsAndExecutedFiles': pins,
              'environment': {'python': sys.version, 'numpy': np.__version__, 'scipy': scipy.__version__},
              'target': {'shape': 'head', 'morph': target, 'sourceScale': scale}, 'sourceTriDecode': decode,
              'method': 'Actual frozen nearest-body-triangle field with exact-coordinate welded C1 geodesic taper; exact body boundary packed triples, exact zero at protected split seam/outside band; new record uses unchanged body scale, round-to-nearest-even interior quantization.',
              'numericSelectionGate': 'Smallest declared width with zero isolated half/full normal turns/collapses and head maximum absolute edge strain no greater than original body WaistNarrow strain at each of three weights. Numerical feasibility only, no appearance criterion.',
              'bodyStrainBudgetsByWeight': {str(k): v for k, v in budgets.items()},
              'referenceAnchorError': reference_anchor_error,
              'frozenReferenceBodyTriangleIds': reference_binding.indices.tolist(),
              'frozenReferenceBarycentrics': reference_binding.weights.tolist(),
              'bandCandidates': candidates, 'selectedBand': selected, 'changedHeadVertices': sorted(packed),
              'boundaryPairs': pairs.tolist(), 'protectedSplitPairs': protected_pairs.tolist(),
              'byteEnvelope': envelope, 'states': [{'name': n, 'values': v} for n, v in states], 'weights': {},
              'limitations': ['TRI-only resource candidate, not an installation package or visual acceptance.',
                              'Following fur/blend TRI fields remain exact and have not been refitted; shared skin/fur motion and coverage remain unqualified.',
                              'NIF geometry, weights, materials and bounds stay byte-identical. Bounds for the added combined morph field require separate requalification.',
                              'The new TRI hash changes resource identity. Geometry/model bindings, morph-family calibration and physics/VR resource hash contracts require rebind/recalibration assessment; old acceptance/model identity is not inherited.',
                              'Finite static and declared LBS samples do not prove global intersection freedom, continuous animation or physics behavior.']}
    out.mkdir(parents=True)
    try:
        candidate = out/tri.name
        candidate.write_bytes(candidate_data)
        readback = Trip.from_filepath(str(candidate))
        output_fields, output_decode = quality.decode_fields(candidate.read_bytes(), readback.shapes, {n: len(v) for n, v in vertices.items()})
        if not readback.is_valid or not np.array_equal(output_fields['head', target], delta) or {m for n, m in output_fields} != set(names):
            raise ValueError('Actual public readback/name/quantization mismatch')
        report['candidateTriDecode'] = output_decode
        report['unchangedNifArtifacts'] = [quality.pin(low), quality.pin(high)]
        report['candidateTriArtifact'] = quality.pin(candidate)
        (out/'artifact-manifest.json').write_text(json.dumps({
            'schemaVersion': 1, 'status': 'tri-only-offline-resource-candidate-not-installation-package',
            'unchangedNifs': report['unchangedNifArtifacts'], 'candidateTri': report['candidateTriArtifact'],
            'sourceTri': quality.pin(tri), 'report': str(out/'morph-seam-report.json'),
            'resourceIdentityChanged': True, 'oldAcceptanceInherited': False,
            'requiredAssessment': ['bounds', 'geometry/model resource bindings', 'morph-family calibration',
                                   'physics and VR resource hash contracts', 'fur coupling', 'visual and runtime acceptance']
        }, indent=2), encoding='utf-8')
        for weight in weights:
            neutral = {n: v+weight*(high_vertices[n]-v) for n, v in vertices.items()}
            rows = {}
            for label, state in states:
                before = {n: v+sum((value*fields.get((n, m), np.zeros_like(v)) for m, value in state.items()), np.zeros_like(v)) for n, v in neutral.items()}
                after = dict(before); after['head'] = before['head']+state.get(target, 0.)*delta
                old_surface = quality.surface_metrics(neutral['head'], before['head'], shapes['head'].tris)
                new_surface = quality.surface_metrics(neutral['head'], after['head'], shapes['head'].tris)
                old_join = quality.join_metrics(neutral['body'], neutral['head'], before['body'], before['head'], pairs)
                new_join = quality.join_metrics(neutral['body'], neutral['head'], after['body'], after['head'], pairs)
                split_join = quality.join_metrics(neutral['head'], neutral['head_CLAWHead'], after['head'], after['head_CLAWHead'], protected_pairs)
                rows[label] = {'beforeJoin': old_join, 'afterJoin': new_join, 'protectedSplitJoin': split_join,
                               'beforeHeadSurface': old_surface, 'afterHeadSurface': new_surface,
                               'newNormalTurnTriangleIds': sorted(set(new_surface['normalTurnTriangleIds'])-set(old_surface['normalTurnTriangleIds']))}
            report['weights'][str(weight)] = rows
        if skeleton is not None:
            report['posedSeams'] = pose_report(api, shapes, high_vertices, vertices, fields, delta, pairs, protected_pairs, skeleton, states)
        report['frozenFurRoots'] = fur_report(shapes, vertices, fields, delta)
        if any(quality.pin(row['path']) != row for row in pins):
            raise ValueError('Input/source changed during repair')
        report['status'] = 'completed-local-exact-static-skin-seam-candidate-fur-bounds-visual-runtime-pending'
    except Exception:
        report['status'] = 'FAILED-incomplete-candidate'
        raise
    finally:
        (out/'morph-seam-report.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    return out/'morph-seam-report.json'


def fur_report(shapes, vertices, fields, delta):
    """Reuse the existing Layer root/barycentric contract, without writing fur."""
    import surface_collar as surface
    from body_weight import Projector
    profile = json.loads((quality.ROOT / 'src/main/resources/recipes/surface-collars.json').read_text())
    names = ('body', 'head', 'head_CLAWHead')
    skin = np.concatenate([vertices[n] for n in names])
    skin_faces = []; base = 0
    for name in names:
        skin_faces.append(np.asarray(shapes[name].tris, int)+base); base += len(vertices[name])
    skin_faces = np.concatenate(skin_faces)
    projector = Projector(skin, skin_faces)
    target = 'CLAWTorsoWaistNarrow'
    before = np.concatenate([fields.get((n, target), np.zeros_like(vertices[n])) for n in names])
    added = np.concatenate([np.zeros_like(vertices['body']), delta, np.zeros_like(vertices['head_CLAWHead'])])
    report = {'scope': 'Frozen current-neutral Layer roots using existing surface-collars layer rules on explicit selected split skin. Unit WaistNarrow translation-target offset drift only; finite static linear field, no posed offset transport, surface-contact or fur-coverage proof. All fur fields remain exact.', 'layers': {}}
    for rule in profile['layers']:
        name = rule['shape']
        layer = surface.Layer(vertices[name], shapes[name].tris, skin, skin_faces, rule, projector)
        old = fields.get((name, target), np.zeros_like(vertices[name]))
        inherited_before = layer.binding.evaluate(before)
        inherited_after = inherited_before+layer.binding.evaluate(added)
        roots = [int(group[np.flatnonzero(np.all(vertices[name][group] == point, axis=1))[0]]) for group, point in zip(layer.groups, layer.binding.points)]
        roots = np.asarray(roots, int)
        enabled = layer.weights > 0
        changed = enabled & np.any(inherited_before != inherited_after, axis=1)
        e0 = np.linalg.norm(old[roots]-inherited_before, axis=1)
        e1 = np.linalg.norm(old[roots]-inherited_after, axis=1)
        def stats(mask):
            return {'roots': int(mask.sum()), 'beforeMaximumOffsetDrift': float(e0[mask].max()) if mask.any() else None,
                    'afterMaximumOffsetDrift': float(e1[mask].max()) if mask.any() else None,
                    'beforeSquaredOffsetDrift': float(np.sum(e0[mask]**2)), 'afterSquaredOffsetDrift': float(np.sum(e1[mask]**2))}
        report['layers'][name] = {'enabled': stats(enabled), 'rootsAffectedByAddedSkinField': stats(changed),
                                'affectedRootIds': roots[changed].tolist(),
                                'frozenSkinTriangleIds': layer.binding.indices[changed].tolist(),
                                'frozenSkinBarycentrics': layer.binding.weights[changed].tolist(),
                                'frozenSkinFaces': layer.binding.faces[layer.binding.indices[changed]].tolist()}
        print('MORPH_SEAM|fur='+name+'|affectedRoots='+str(int(changed.sum())), flush=True)
    return report


def pose_report(api, shapes, high, low, fields, delta, pairs, split_pairs, skeleton, states):
    import breast_rig as rig
    from composed_vr import pose_bank
    skel = api.NifFile(str(skeleton))
    _, _, poses, globals_ = pose_bank(skel)
    ids = {'body': np.unique(pairs[:, 0]), 'head': np.unique(np.r_[pairs[:, 1], split_pairs[:, 0]]), 'head_CLAWHead': np.unique(split_pairs[:, 1])}
    indices = {n: {int(i): k for k, i in enumerate(v)} for n, v in ids.items()}
    maps = {'collar': ('body', 'head', np.asarray([[indices['body'][int(a)], indices['head'][int(b)]] for a, b in pairs])),
            'split': ('head', 'head_CLAWHead', np.asarray([[indices['head'][int(a)], indices['head_CLAWHead'][int(b)]] for a, b in split_pairs]))}
    matrices = {}
    for mode in ('rawPacked', 'normalized'):
        matrices[mode] = {}
        for name, select in ids.items():
            shape = shapes[name]; bones = list(shape.bone_weights)
            if not shape.has_global_to_skin:
                raise ValueError('Pose audit requires explicit stored skin frame')
            W = rig.read_weights(shape, bones)[select]
            if mode == 'normalized': W = W/W.sum(1)[:, None]
            binds = np.asarray([rig.matrix(shape.get_shape_skin_to_bone(n))@rig.matrix(shape.global_to_skin) for n in bones])
            products = np.asarray([[pose[n] for n in bones] for pose in globals_])@binds
            matrices[mode][name] = np.einsum('nb,pbij->pnij', W, products)
    result = {'poseCount': len(poses), 'poseNames': [p[0] for p in poses], 'rows': {}}
    chosen_states = [(n, s) for n, s in states if 'CLAWTorsoWaistNarrow' in s or n == 'neutral']
    for weight in (0., .5, 1.):
        for label, state in chosen_states:
            row = {}
            for mode in matrices:
                before, after = {}, {}
                for name, select in ids.items():
                    v = low[name][select]+weight*(high[name][select]-low[name][select])
                    for m, c in state.items(): v += c*fields.get((name, m), np.zeros_like(low[name]))[select]
                    matrix = matrices[mode][name]
                    before[name] = np.einsum('pnij,nj->pni', matrix[:, :, :3], np.c_[v, np.ones(len(v))])
                    if name == 'head': v = v+state.get('CLAWTorsoWaistNarrow', 0.)*delta[select]
                    after[name] = np.einsum('pnij,nj->pni', matrix[:, :, :3], np.c_[v, np.ones(len(v))])
                detail = {}
                for join, (a, b, mapping) in maps.items():
                    old = np.linalg.norm(before[a][:, mapping[:, 0]]-before[b][:, mapping[:, 1]], axis=-1)
                    new = np.linalg.norm(after[a][:, mapping[:, 0]]-after[b][:, mapping[:, 1]], axis=-1)
                    p, i = np.unravel_index(int(new.argmax()), new.shape)
                    detail[join] = {'beforeMaximumDistance': float(old.max()), 'afterMaximumDistance': float(new.max()),
                                    'maximumDistanceIncrease': float((new-old).max()), 'worstAfterPose': poses[p][0], 'worstAfterPairIndex': int(i)}
                row[mode] = detail
            result['rows'][str(weight)+'|'+label] = row
    return result
