"""Compose reviewed first-person Neck resources with the male collar TRI repair.

This stages explicit external resources, never an installation layout. It copies
admitted NIFs unchanged, verifies the one-record TRI extension and measures the
visible collar using actual skin binds. Hidden head-side boundaries intentionally
do not follow the new Neck policy during Head-local motion.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import numpy as np

import body_resource as resource
sys.path.insert(0, str(resource.ROOT / 'scripts'))
import geometry_audit
import morph_quality
import morph_seam
import tri_patch


def check_file(row):
    path = Path(row['path']).resolve(strict=True)
    if resource.sha256(path) != row['sha256'] or path.stat().st_size != row['bytes']:
        raise ValueError('Artifact changed: ' + str(path))
    return path


def reviewed_profile():
    path = resource.ROOT / 'vr/composed-visibility-profile.json'
    return resource.read_json(path), path


def admit(neck_root, seam_manifest):
    neck_root = Path(neck_root).resolve(strict=True)
    neck_path = neck_root / 'head-isolation-report.json'
    neck = resource.read_json(neck_path)
    if neck.get('status') != 'offline-first-person-neck-graft-native-verified-joins-measured-runtime-pending':
        raise ValueError('A completed Neck resource candidate is required')
    bodies = neck.get('bodies', {})
    if set(bodies) != {'female0', 'female1', 'male0', 'male1'} or set(neck.get('joins', {})) != {'female', 'male'}:
        raise ValueError('Four native resource receipts and both join reports are required')
    pins = {str(neck_path): resource.sha256(neck_path)}
    profile, profile_path = reviewed_profile()
    expected = {'skeleton.nif': profile['skeletonSha256'], profile_path.name: resource.sha256(profile_path)}
    for sex, body in profile['bodies'].items():
        expected[sex+'bodywerewolf.tri'] = body['triSha256']
        expected.update({f'{sex}bodywerewolf_{i}.nif': value for i, value in enumerate(body['nifSha256'])})
    inputs = neck.get('inputSha256', {})
    if not isinstance(inputs, dict) or len(inputs) != len(expected):
        raise ValueError('The complete reviewed Neck source family is required')
    for basename, digest in expected.items():
        found = [path for path, value in inputs.items() if Path(path).name == basename and value == digest]
        if len(found) != 1 or resource.sha256(found[0]) != digest:
            raise ValueError('Neck source family differs from the reviewed profile: ' + basename)
        pins[found[0]] = digest
    sources = {}
    for sex in ('female', 'male'):
        for endpoint in (0, 1):
            row = bodies[sex + str(endpoint)]
            native = row.get('serializedCandidate')
            if row.get('numericPlanPasses') is not True or row.get('numericFailures') != [] or not isinstance(native, dict):
                raise ValueError('Rejected or missing native Neck resource receipt')
            required = ('nativeProtectedGeometryMaterialsUvFramesAndForeignWeightsExact',
                        'originalNodesAndBindsExact', 'originalBlockIdsStable', 'originalStringIdsStable')
            if any(native.get(key) is not True for key in required):
                raise ValueError('Native protected-field preservation was not confirmed')
            path = neck_root / 'resources' / sex / f'first-person_{endpoint}.nif'
            if resource.sha256(path) != native['nifSha256']:
                raise ValueError('Neck NIF does not match its native readback receipt')
            sources[f'{sex}/first-person_{endpoint}.nif'] = path
            pins[str(path)] = native['nifSha256']
        path = neck_root / 'resources' / sex / (sex + 'bodywerewolf.tri')
        expected = [digest for path_, digest in neck['inputSha256'].items()
                    if Path(path_).name == path.name]
        if len(expected) != 1 or resource.sha256(path) != expected[0]:
            raise ValueError('Original Neck TRI source identity is ambiguous or changed')
        sources[f'{sex}/{path.name}'] = path
        pins[str(path)] = expected[0]
        join = neck['joins'][sex]
        if resource.sha256(join['report']) != join['sha256']:
            raise ValueError('Neck join report changed')
        pins[join['report']] = join['sha256']
    seam_manifest = Path(seam_manifest).resolve(strict=True)
    seam = resource.read_json(seam_manifest)
    male_tri = check_file(seam['candidateTri'])
    old_tri = check_file(seam['sourceTri'])
    if old_tri.read_bytes() != sources['male/malebodywerewolf.tri'].read_bytes():
        raise ValueError('The seam and Neck stages use different male source TRIs')
    if (not isinstance(seam.get('unchangedNifs'), list) or len(seam['unchangedNifs']) != 2
            or sorted(Path(row['path']).name for row in seam['unchangedNifs'])
            != ['malebodywerewolf_0.nif', 'malebodywerewolf_1.nif']):
        raise ValueError('Both distinct unchanged male NIF endpoint receipts are required')
    for row in seam['unchangedNifs']:
        original = check_file(row)
        if neck['inputSha256'].get(str(original)) != row['sha256']:
            raise ValueError('The seam and Neck stages use different male NIF endpoints')
        pins[str(original)] = row['sha256']
    original, extended = tri_patch.offsets(old_tri.read_bytes()), tri_patch.offsets(male_tri.read_bytes())
    if any(key not in extended or original[key].scale != extended[key].scale
           or original[key].packed != extended[key].packed for key in original):
        raise ValueError('A pre-existing serialized TRI field changed')
    added = set(extended) - set(original)
    if not added or any(key[:2] != ('head', 'CLAWTorsoWaistNarrow') for key in added):
        raise ValueError('Only the missing male head WaistNarrow record may be added')
    scales = {extended[key].scale for key in added}
    if len(scales) != 1:
        raise ValueError('A single serialized scale is required')
    reconstructed, _ = morph_seam.append_record(old_tri.read_bytes(), 'head', 'CLAWTorsoWaistNarrow',
                                               next(iter(scales)), {key[2]: extended[key].packed for key in added})
    if reconstructed != male_tri.read_bytes():
        raise ValueError('The candidate is not the exact one-record extension of its source')
    pins.update({str(seam_manifest): resource.sha256(seam_manifest),
                 str(old_tri): resource.sha256(old_tri), str(male_tri): resource.sha256(male_tri)})
    sources['male/malebodywerewolf.tri'] = male_tri
    return sources, pins


def build(neck_root, seam_manifest, skeleton_file, output, pynifly=None, morphbench=None):
    sources, pins = admit(neck_root, seam_manifest)
    skeleton_file = Path(skeleton_file).resolve(strict=True)
    pins[str(skeleton_file)] = resource.sha256(skeleton_file)
    if pins[str(skeleton_file)] != resource.read_json(resource.ROOT / 'vr/composed-visibility-profile.json')['skeletonSha256']:
        raise ValueError('The composed candidate requires its reviewed existing XP32 skeleton')
    for path in [Path(__file__), *sorted((resource.ROOT / 'scripts').glob('*.py')), Path(resource.__file__)]:
        pins[str(path.resolve())] = resource.sha256(path)
    out = resource.safe_output(output, pins)
    api, _, Trip, dependencies = resource.dependencies(pynifly, morphbench)
    pins.update({str(path): digest for path, digest in dependencies.items()})
    if any(resource.sha256(path) != digest for path, digest in pins.items()):
        raise ValueError('An admitted input changed before composition')
    skeleton = api.NifFile(str(skeleton_file))
    low = api.NifFile(str(sources['male/first-person_0.nif']))
    high = api.NifFile(str(sources['male/first-person_1.nif']))
    raw = Trip.from_filepath(str(sources['male/malebodywerewolf.tri'])).shapes
    model = geometry_audit.Model(low, high, skeleton, raw)
    shapes = {shape.name: shape for shape in low.shapes}
    pairs = morph_quality.freeze_join(shapes['body'].verts, shapes['body'].tris,
                                     shapes['head'].verts, shapes['head'].tris, 1e-4)
    if len(pairs) != 135:
        raise ValueError('The reviewed visible collar must retain all 135 frozen pairs')
    states = {'neutral': {}, 'waistHalf': {'CLAWTorsoWaistNarrow': .5},
              'waistFull': {'CLAWTorsoWaistNarrow': 1.}}
    audit = {}
    for weight in (0., .5, 1.):
        rows = {}
        for label, state in states.items():
            rows[label] = {}
            for normalized in (False, True):
                first = model.positions('body', pairs[:, 0], weight, state, normalized)
                second = model.positions('head', pairs[:, 1], weight, state, normalized)
                distance = np.linalg.norm(first-second, axis=-1)
                rows[label]['normalized' if normalized else 'rawPacked'] = {
                    'maximumPosedDistance': float(distance.max()),
                    'restMaximumDistance': float(distance[0].max()),
                    'p95PosedDistance': float(np.quantile(distance, .95)),
                    'worstPose': model.poses[int(np.unravel_index(distance.argmax(), distance.shape)[0])][0]}
        audit[str(weight)] = rows
    out.mkdir(parents=True)
    for relative, source in sources.items():
        target = out / 'resources' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if resource.sha256(target) != pins[str(source)]:
            raise ValueError('Composition changed an admitted resource byte')
    if any(resource.sha256(path) != digest for path, digest in pins.items()):
        raise ValueError('An input or dependency changed during composition')
    result = {'schemaVersion': 1, 'status': 'composed-offline-resources-measured-runtime-pending',
              'inputSha256': pins, 'resources': {key: resource.sha256(out/'resources'/key) for key in sources},
              'visibleCollarPairs': pairs.tolist(), 'posedVisibleCollar': audit,
              'scope': 'Unchanged Neck NIFs, unchanged female TRI and one-record male TRI extension.135visible pairs,160 imposed poses,three independent weights,neutral/half/full WaistNarrow,raw/normalized LBS. No camera,render,futurephysicsbinding or whole-fur acceptance.',
              'installable': False, 'oldAcceptanceInherited': False}
    (out/'composition-report.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('neck-root', 'seam-manifest', 'skeleton', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--pynifly', type=Path)
    parser.add_argument('--morphbench', type=Path)
    args = parser.parse_args()
    try:
        build(args.neck_root, args.seam_manifest, args.skeleton, args.out, args.pynifly, args.morphbench)
    except (ValueError, OSError, RuntimeError, KeyError) as error:
        parser.exit(2, 'VR resource composition refused: '+str(error)+'\n')
