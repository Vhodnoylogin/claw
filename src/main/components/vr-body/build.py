"""Build a namespaced, first-person-only resource candidate; never install or run.

Uses CLAW's existing lossless split, verified Neck skin graft and bone-bound
adapters. Engine first-person dispatch remains a separate prospective VR probe.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path, PurePosixPath
import shutil
import struct
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT/'src/main/python/vr'), str(ROOT/'src/main/python/build-tools')]
import body_resource as resource
import head_split
import head_isolation as isolation
import neck_bounds
import breast_rig as rig
import morph_quality

NAMESPACE = 'Meshes/Actors/WerewolfBeast/CLAW/FirstPerson'
REFERENCE_ENTRY = 'meshes/actors/character/character assets/1stperson_werewolf_hands.nif'
LIMITS = dict(isolation.LIMITS)
BOX_PAD = 1e-8


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf8')


def resource_paths(sex, endpoint=None):
    if sex not in ('female', 'male') or (endpoint is not None and (type(endpoint) is not int or endpoint not in (0, 1))):
        raise ValueError('Explicit sex and endpoint0/1 required')
    base = f'{NAMESPACE}/{sex}'
    return f'{base}/Body.tri' if endpoint is None else f'{base}/Body_{endpoint}.nif'


def bodytri_path(sex):
    return str(PurePosixPath(resource_paths(sex)).relative_to('Meshes')).replace('/', '\\').lower()


def namespace_bodytri(data, old, new):
    """Only one shared BODYTRI string changes; every block/id remains exact."""
    if old == new or not new.startswith('actors\\werewolfbeast\\claw\\firstperson\\'):
        raise ValueError('A separate first-person BODYTRI namespace is required')
    before = head_split.Nif(data)
    indexes = [i for i, text in enumerate(before.strings) if text == old.encode('utf8')]
    if len(indexes) != 1:
        raise ValueError('Source BODYTRI shared string is missing or ambiguous')
    index = indexes[0]
    before.strings[index] = new.encode('utf8')
    result = before.bytes()
    check = head_split.Nif(result)
    original = head_split.Nif(data)
    if check.blocks != original.blocks or check.kinds != original.kinds or check.footer != original.footer:
        raise ValueError('BODYTRI path edit changed a NIF block or index')
    if any(a != b for i, (a, b) in enumerate(zip(check.strings, original.strings)) if i != index):
        raise ValueError('BODYTRI path edit changed an unrelated string')
    return result, {'stringIndex': index, 'before': old, 'after': new,
                    'allBlocksAndIdsExact': True, 'allOtherStringsExact': True}


def affine_box_bound(matrices, vertices, fields):
    """Bound affine displacement over independent coefficients0..1.

    Matrices are pose/vertex/3x4. These finite binary64 calculations include a
    declared pad; the emitted skin sphere additionally rounds outward to f32.
    """
    m, v = np.asarray(matrices, float), np.asarray(vertices, float)
    if m.ndim != 4 or m.shape[1:] != (len(v), 3, 4) or v.shape != (len(v), 3) or not np.isfinite(m).all() or not np.isfinite(v).all():
        raise ValueError('Finite per-pose/vertex3x4 affine maps required')
    base = np.einsum('pvij,vj->pvi', m[..., :3], v) + m[..., 3]
    low, high = base.copy(), base.copy()
    for field in fields:
        field = np.asarray(field, float)
        if field.shape != v.shape or not np.isfinite(field).all():
            raise ValueError('Complete finite vertex direction required')
        value = np.einsum('pvij,vj->pvi', m[..., :3], field)
        low += np.minimum(value, 0); high += np.maximum(value, 0)
    return float(np.linalg.norm(np.maximum(abs(low), abs(high)) + BOX_PAD, axis=-1).max())


def shape_fields(fields, name):
    return [value for (shape, _), value in fields.items() if shape == name]


def protect_selection(faces, selected, protected, cards):
    """Keep actual protected support visible; connected cards remain whole."""
    faces, selected, protected = np.asarray(faces), np.asarray(selected, bool), np.asarray(protected, bool)
    if faces.ndim != 2 or faces.shape[1] != 3 or faces.dtype.kind not in 'iu' or selected.shape != (len(faces),) or protected.ndim != 1 or np.any(faces < 0) or np.any(faces >= len(protected)):
        raise ValueError('Finite triangle selection and protected vertex mask required')
    keep = np.any(protected[faces], axis=1)
    if cards:
        groups = head_split.components(faces, len(protected))
        keep = np.isin(groups[faces[:, 0]], np.unique(groups[protected]))
    result = selected & ~keep
    if np.any(protected[np.unique(faces[result])]): raise ValueError('Protected support entered the hidden subset')
    return result


def anatomical_plan(nif, fields, head_names, protected_names):
    """Original ownership cut, with explicit current-field visibility protection."""
    result, changes = {}, {}
    for shape in nif.shapes:
        if shape.name.endswith(head_split.SUFFIX): raise ValueError('Already split input')
        vertices, faces = np.asarray(shape.verts), np.asarray(shape.tris, int)
        names = list(shape.bone_weights); weights = rig.read_weights(shape, names)
        mass = weights[:, [i for i, n in enumerate(names) if n in head_names]].sum(1) / weights.sum(1)
        cards = shape.name.startswith('fur_') or shape.name.endswith('Blend')
        selected = head_split.classify(vertices, faces, mass, .5, cards)
        protected = np.zeros(len(vertices), bool)
        for name in protected_names:
            if (shape.name, name) in fields: protected |= np.any(fields[shape.name, name] != 0, axis=1)
        actual = protect_selection(faces, selected, protected, cards)
        if np.any(selected != actual):
            changes[shape.name] = {'originalHeadTriangles': int(selected.sum()), 'retainedHeadSideTriangles': int((selected & ~actual).sum()),
                                   'protectedVertices': int(protected.sum()), 'wholeConnectedCardsPreserved': cards}
        mapping = head_split.mapping(faces, actual, len(vertices))
        result[shape.name] = {'mapping': mapping, 'action': 'head' if actual.all() else 'torso' if not actual.any() else 'split',
                              'sourceBlock': shape.id, 'cards': cards}
    if result['head']['action'] != 'split': raise ValueError('Protected source no longer has the reviewed mixed-head split')
    return result, changes


def desired_error(study, fields, actual=None):
    """Actual packed weights/binds, complete current TRI, all declared poses."""
    rows = {}
    for name, plan in study.plans.items():
        ids = plan['ids']; shape = study.shapes[name]
        vertices = np.asarray(shape.verts, float)[ids]
        directions = [v[ids] for v in shape_fields(fields, name)]
        weights = plan['candidateWeights']
        binds = plan['candidateBinds']
        if actual is not None:
            shape_actual = next(s for s in actual.shapes if s.name == name)
            names = [*study.names, isolation.NECK]
            weights = rig.read_weights(shape_actual, names)
            binds = np.zeros((len(names), 4, 4))
            frame = rig.matrix(shape_actual.global_to_skin)
            for bone in shape_actual.bone_names:
                binds[names.index(bone)] = rig.matrix(shape_actual.get_shape_skin_to_bone(bone)) @ frame
        packed_change = float(abs(weights.sum(1)-plan['weights'].sum(1)).max())
        if packed_change > LIMITS['packedSumChange']:
            raise ValueError('Packed sum change exceeds the unchanged Neck limit')
        desired = np.einsum('pbij,bjk->pbik', plan['desiredGlobals'], plan['binds'])
        candidate = np.einsum('pbij,bjk->pbik', plan['candidateGlobals'], binds)
        modes = {}
        for normalized in (False, True):
            old, new = plan['weights'][ids].copy(), weights[ids].copy()
            if normalized:
                old /= old.sum(1)[:, None]; new /= new.sum(1)[:, None]
            worst = p1 = 0.; baseline = None
            for first in range(0, len(candidate), 8):
                sl = slice(first, first+8)
                error = (np.einsum('vb,pbij->pvij', new, candidate[sl, :, :3, :], optimize=True)
                         - np.einsum('vb,pbij->pvij', old, desired[sl, :, :3, :], optimize=True))
                if first == 0: baseline = error[:1].copy()
                worst = max(worst, affine_box_bound(error, vertices, directions))
                local = [i-first for i in study.pure_p1 if first <= i < first+len(error)]
                if local:
                    p1 = max(p1, affine_box_bound(error[local]-baseline, vertices, directions))
            limit = LIMITS['normalizedDesiredMax' if normalized else 'rawDesiredMax']
            if worst > limit or p1 > LIMITS['pureP1MotionChange']:
                raise ValueError('Complete-current-TRI Neck enclosure rejected: '+name)
            modes['normalized' if normalized else 'rawPacked'] = {'desiredReferenceErrorBound': worst, 'pureP1ChangeBound': p1}
        rows[name] = {'vertices': len(ids), 'completeMorphFields': len(directions), 'packedSumMaxChange': packed_change, 'modes': modes}
    if not rows: raise ValueError('No visible mixed Head/Neck support was found')
    return {'shapes': rows, 'poseCount': len(study.labels), 'limits': LIMITS, 'binary64BoxPad': BOX_PAD,
            'coefficientDomain': [0, 1], 'independentWeight': 'actual input endpoints; current0.10 pairs identical',
            'runtimeOrCameraAcceptance': False}


def expand_new_neck(api, Patch, nif_path, tri, output):
    """Reuse only the reviewed new-Neck sphere operation, with current fields."""
    before = api.NifFile(str(nif_path)); container = head_split.Nif(nif_path.read_bytes()); table = Patch(nif_path)
    shapes = {s.name: s for s in before.shapes}
    public = api_trip(tri)
    fields, decoder = morph_quality.decode_fields(tri.read_bytes(), public, {n: len(s.verts) for n, s in shapes.items()})
    ledger = []
    for name, shape in shapes.items():
        if isolation.NECK not in shape.bone_names: continue
        data_id, offset, sphere = neck_bounds.neck_record(container, shape)
        ids, bind, _ = neck_bounds.verify_rest_frame(shape, sphere)
        complete = [v[ids] for v in shape_fields(fields, name)]
        low, high = neck_bounds.local_boxes(np.asarray(shape.verts)[ids], np.asarray(shape.verts)[ids], complete, bind)
        reach = neck_bounds.reach(low, high, sphere[:3])
        radius = neck_bounds.outward_float32(max(float(sphere[3]), reach*neck_bounds.MARGIN + neck_bounds.ABSOLUTE_MARGIN))
        ledger.append({'shape': name, 'bone': isolation.NECK, 'skinDataBlock': data_id,
                       'offset': table.offsets[data_id]+offset, 'oldSphere': sphere.tolist(),
                       'newSphere': [*sphere[:3].tolist(), radius], 'completeTriCubeReach': reach})
    if len(ledger) != 7: raise ValueError('Expected seven mixed-shape new-Neck spheres')
    raw = neck_bounds.patch_spheres(nif_path.read_bytes(), ledger)
    proof = neck_bounds.verify_bytes(nif_path.read_bytes(), raw, ledger)
    output.write_bytes(raw)
    actual = api.NifFile(str(output)); actual_container = head_split.Nif(raw)
    for row in ledger:
        sh = next(s for s in actual.shapes if s.name == row['shape'])
        _, _, got = neck_bounds.neck_record(actual_container, sh)
        if not np.array_equal(got, row['newSphere']): raise ValueError('Stored new-Neck sphere differs')
        ids = np.asarray([i for i, weight in sh.bone_weights[isolation.NECK] if weight > 0], int)
        bind = rig.matrix(sh.get_shape_skin_to_bone(isolation.NECK))
        low, high = neck_bounds.local_boxes(np.asarray(sh.verts)[ids], np.asarray(sh.verts)[ids], [v[ids] for v in shape_fields(fields, sh.name)], bind)
        for bits in np.ndindex(2, 2, 2):
            if np.linalg.norm(np.where(np.asarray(bits)[None, :], high, low)-got[:3], axis=1).max() > got[3]:
                raise ValueError('Serialized current-TRI box escapes new-Neck sphere')
    return actual, {'byteProof': proof, 'spheres': ledger, 'completeTriDecoder': decoder, 'allEightCornersContained': True,
                    'oldBoneBoundsUnchangedNotRequalified': True}


TRIP = None
def api_trip(path):
    if TRIP is None: raise RuntimeError('Native TRI reader was not configured')
    return TRIP.from_filepath(str(path)).shapes


def reference_proof(root, expected):
    root = Path(root).resolve(strict=True)
    mesh, meta = root/REFERENCE_ENTRY, root/'meta.ini'
    if resource.sha256(mesh) != expected['meshSha256'] or resource.sha256(meta) != expected['metadataSha256']:
        raise ValueError('Explicit installed-reference source pin differs')
    return {'mesh': str(mesh), 'sha256': resource.sha256(mesh), 'metadata': str(meta), 'metadataSha256': resource.sha256(meta),
            'entry': REFERENCE_ENTRY, 'copiedIntoCandidate': False,
            'meaning': 'Installed reference and saved author metadata use this first-person path; not native sex/weight/path dispatch proof'}


def verify_first_person(nif, Trip, tri, sex, profile, head_descendants):
    raw = Trip.from_filepath(str(tri)).shapes
    fields, _ = morph_quality.decode_fields(Path(tri).read_bytes(), raw, {s.name: len(s.verts) for s in nif.shapes})
    hidden = set(profile['hiddenShapes'])
    if len(nif.shapes) != len({s.name for s in nif.shapes}) or not hidden <= {s.name for s in nif.shapes}:
        raise ValueError('Missing or duplicate first-person shape')
    hands = {name: 0 for name in resource.HAND_BONES}; breast = 0
    for shape in nif.shapes:
        visible = resource.visible_by_hidden_flags(shape)
        if resource.bodytri(shape) != [('BODYTRI', bodytri_path(sex))]:
            raise ValueError('Native BODYTRI namespace readback differs')
        if visible != (shape.name not in hidden):
            raise ValueError('First-person visibility readback differs')
        head = sum(weight > 0 for bone, values in shape.bone_weights.items() if bone in head_descendants for _, weight in values)
        if visible and head: raise ValueError('Visible first-person shape retains Head-subtree weight')
        support = sum(int(np.any(fields[shape.name, name] != 0, axis=1).sum()) for name in profile['protectedMorphs'][sex] if (shape.name, name) in fields)
        if support and not visible: raise ValueError('Hidden breast morph support')
        breast += support
        for bone in hands:
            count = sum(weight > 0 for _, weight in shape.bone_weights.get(bone, []))
            if count and not visible: raise ValueError('Hidden weighted hand support')
            hands[bone] += count
    if not all(hands.values()) or (sex == 'female' and not breast):
        raise ValueError('Required hand/breast support is missing')
    resource.tri_contract(Trip, tri, nif, profile['publicMorphCount'][sex])
    return {'nativeReadback': True, 'visibleHeadSubtreeWeights': 0, 'handSupportVertices': hands,
            'visibleBreastMorphPairs': breast, 'publicMorphCount': profile['publicMorphCount'][sex]}


def build(body_root, skeleton_path, output, pynifly, morphbench, reference_mod, runtime_receipt, profile_path=HERE/'current-010.json'):
    global TRIP
    body_root, skeleton_path = Path(body_root).resolve(strict=True), Path(skeleton_path).resolve(strict=True)
    profile = resource.read_json(profile_path)
    if profile != resource.read_json(HERE/'current-010.json'): raise ValueError('Only the pinned current0.10 composition is admitted')
    inputs = {str(body_root/name): h for name, h in profile['inputSha256'].items()}
    inputs[str(skeleton_path)] = profile['skeletonSha256']
    runtime_receipt = Path(runtime_receipt).resolve(strict=True)
    if resource.sha256(runtime_receipt) != profile['runtimeReceiptSha256']:
        raise ValueError('Final archive runtime composition receipt differs')
    archive = resource.read_json(runtime_receipt)
    if Path(archive['bodies']).resolve() != body_root or archive['sourceCommit'] != profile['sourceCommit'] or archive['archiveSha256'] != profile['archiveSha256']:
        raise ValueError('Final runtime inputs do not match the declared archive/source')
    if resource.sha256(archive['archive']) != profile['archiveSha256']:
        raise ValueError('Actual source archive changed')
    inputs.update({str(runtime_receipt): profile['runtimeReceiptSha256'], archive['archive']: profile['archiveSha256']})
    if any(resource.sha256(p) != h for p, h in inputs.items()): raise ValueError('Current source body/TRI/skeleton pin differs')
    proof = reference_proof(reference_mod, profile['reference'])
    inputs.update({proof['mesh']: proof['sha256'], proof['metadata']: proof['metadataSha256'], str(profile_path): resource.sha256(profile_path)})
    out = resource.safe_output(output, inputs)
    api, Patch, Trip, dependencies = resource.dependencies(pynifly, morphbench); TRIP = Trip
    if any(resource.sha256(p) != h for p, h in inputs.items()): raise ValueError('Input changed during dependency loading')
    sources = [Path(__file__), Path(resource.__file__), Path(head_split.__file__), Path(isolation.__file__), Path(neck_bounds.__file__), Path(rig.__file__), Path(morph_quality.__file__)]
    pins = {**inputs, **dependencies, **{str(p): resource.sha256(p) for p in sources}}
    out.mkdir(parents=True)
    report = {'schemaVersion': 1, 'status': 'building', 'sourceVersion': '0.10.0', 'inputSha256': inputs,
              'executedSourceAndDependencies': pins, 'worldBodiesWritten': False, 'texturesSupplied': False,
              'nativeDispatchQualified': False, 'installedReferenceProof': proof, 'sexes': {}}
    try:
        skeleton = api.NifFile(str(skeleton_path)); head = resource.head_descendant_names(skeleton, isolation.HEAD)
        for sex in ('female', 'male'):
            if (body_root/f'{sex}bodywerewolf_0.nif').read_bytes() != (body_root/f'{sex}bodywerewolf_1.nif').read_bytes():
                raise ValueError('Current0.10 equal-endpoint contract changed; no interpolation assumptions allowed')
            work = out/sex; work.mkdir()
            source = body_root/f'{sex}bodywerewolf_0.nif'; source_tri = body_root/f'{sex}bodywerewolf.tri'
            native = api.NifFile(str(source)); raw = api_trip(source_tri)
            original_fields, _ = morph_quality.decode_fields(source_tri.read_bytes(), raw, {s.name: len(s.verts) for s in native.shapes})
            actual_protected = sorted({m for _, m in original_fields if 'breast' in m.casefold()})
            if actual_protected != profile['protectedMorphs'][sex]: raise ValueError('Actual current breast target catalog differs')
            plan, protected = anatomical_plan(native, original_fields, head, actual_protected)
            hidden = sorted([n for n, p in plan.items() if p['action'] == 'head'] + [n+head_split.SUFFIX for n, p in plan.items() if p['action'] == 'split'])
            if hidden != sorted(profile['hiddenShapes']): raise ValueError('Actual anatomical head selection differs from reviewed contract')
            split = work/'split.nif'; tri = work/'split.tri'
            raw_split, split_receipt = head_split.split_nif(source.read_bytes(), plan, native.nodes)
            split.write_bytes(raw_split); tri.write_bytes(head_split.split_trip(source_tri.read_bytes(), plan))
            verified = head_split.verify(api, Trip, source, split, source_tri, tri, plan)
            split_native = api.NifFile(str(split))
            for shape in split_native.shapes:
                if shape.name in hidden: shape.flags |= resource.HIDDEN
            study = isolation.Study(split_native, skeleton)
            decoded, decoder = morph_quality.decode_fields(tri.read_bytes(), api_trip(tri), {s.name: len(s.verts) for s in split_native.shapes})
            preflight = desired_error(study, decoded)
            graft = work/'neck.nif'
            actual, graft_receipt = isolation.graft_resource(api, split, study, skeleton, graft, work/'public-scratch.nif', hidden)
            serialized = desired_error(study, decoded, actual)
            bounded = work/'bounded.nif'; actual, bounds = expand_new_neck(api, Patch, graft, tri, bounded)
            before_paths = {value for s in actual.shapes for key, value in resource.bodytri(s) if key == 'BODYTRI'}
            if len(before_paths) != 1: raise ValueError('First-person source has inconsistent BODYTRI')
            namespaced, path_receipt = namespace_bodytri(bounded.read_bytes(), next(iter(before_paths)), bodytri_path(sex))
            tri_target = out/'resources'/resource_paths(sex); tri_target.parent.mkdir(parents=True, exist_ok=True); tri_target.write_bytes(tri.read_bytes())
            endpoints = {}
            for endpoint in (0, 1):
                target = out/'resources'/resource_paths(sex, endpoint); target.write_bytes(namespaced)
                reopened = api.NifFile(str(target))
                final_receipt = verify_first_person(reopened, Trip, tri_target, sex, profile, head)
                endpoints[str(endpoint)] = {'path': resource_paths(sex, endpoint), 'sha256': resource.sha256(target), 'verification': final_receipt}
            report['sexes'][sex] = {'sourceEndpointsIdentical': True, 'morphCount': profile['publicMorphCount'][sex],
                'protectedActualMorphNames': actual_protected, 'retainedHeadSideVisibility': protected,
                'split': split_receipt, 'nativeSplitVerification': verified, 'completeTriDecoder': decoder,
                'plannedNeckEnclosure': preflight, 'serializedNeckEnclosure': serialized, 'graft': graft_receipt,
                'newNeckBounds': bounds, 'bodytriNamespace': path_receipt, 'endpoints': endpoints,
                'tri': {'path': resource_paths(sex), 'sha256': resource.sha256(tri_target)}}
            dump(out/'build-report.json', report)
            print('VR_COMPONENT|'+sex+'|current TRI split/Neck/bounds/namespace verified', flush=True)
        if any(resource.sha256(p) != h for p, h in pins.items()): raise ValueError('Input/source/dependency changed during build')
        files = {str(p.relative_to(out/'resources')).replace('\\', '/'): resource.sha256(p) for p in (out/'resources').rglob('*') if p.is_file()}
        if set(files) != {resource_paths(s, e) for s in ('female', 'male') for e in (None, 0, 1)}: raise ValueError('Unexpected component payload')
        manifest = {'schemaVersion': 1, 'component': 'CLAW/vr-body', 'status': 'offline-resource-candidate-dispatch-unqualified',
            'sourceVersion': '0.10.0', 'files': files, 'worldOverrides': [], 'skeletonFiles': [], 'textureFiles': [],
            'nativeDispatchQualified': False, 'defaultInstallEnabled': False,
            'selection': 'Namespaced first-person assets only; no native load route is asserted or installed',
            'prospectiveProbeEntry': REFERENCE_ENTRY, 'prospectiveProbeChoices': [
                {'sex': s, 'endpoint': e, 'source': resource_paths(s, e), 'target': REFERENCE_ENTRY,
                 'fixedSexAndWeightOnly': True, 'enabled': False} for s in ('female', 'male') for e in (0, 1)],
            'gates': ['Actual native first-person path and sex/weight branch', 'First-person BODYTRI morph and reload coherence',
                      'First-person coat/material lifecycle', 'Head-camera and Neck clearance', 'Installed VRIK/XP32 arm resolution',
                      'Hand/ear/tail contact and headset verification', 'Human return and save/load'],
            'runtimeAccepted': False, 'installed': False}
        dump(out/'install-manifest.json', manifest)
        report['status'] = 'offline-current010-first-person-candidate-verified-dispatch-pending'
    except BaseException as error:
        report.update(status='failed-candidate-not-admitted', failure=repr(error)); raise
    finally:
        dump(out/'build-report.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('body-root', 'skeleton', 'out', 'pynifly', 'morphbench', 'reference-mod', 'runtime-receipt'):
        parser.add_argument('--'+name, type=Path, required=True)
    a = parser.parse_args()
    build(a.body_root, a.skeleton, a.out, a.pynifly, a.morphbench, a.reference_mod, a.runtime_receipt)


if __name__ == '__main__': main()
