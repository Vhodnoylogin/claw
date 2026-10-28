"""First-person-only visibility resources for the pinned composed anatomical family.

The explicit reviewed head-side shape list replaces whole-head-bone shrinking.
Only eleven hidden bits change per NIF. This prepares file attributes, not a
runtime visibility adapter, engine dispatch patch or camera-clearance proof.
"""
from __future__ import annotations

from pathlib import Path
import json
import sys

import body_resource as resource

PROFILE = Path(__file__).with_name('composed-visibility-profile.json')


def load_profile(path=PROFILE):
    profile = resource.read_json(path)
    if profile != resource.read_json(PROFILE):
        raise ValueError('Only the reviewed composed first-person visibility profile is supported')
    return profile


def resource_name(graph, sex, endpoint):
    """An offline selection contract; it never resolves an engine filename."""
    if graph != 'first-person':
        raise ValueError('Visibility resources are restricted to the first-person graph')
    if sex not in ('female', 'male') or type(endpoint) is not int or endpoint not in (0, 1):
        raise ValueError('Explicit sex and neutral weight endpoint 0 or 1 required')
    return f'{sex}/first-person_{endpoint}.nif'


def admission(nif, trip, profile, sex, *, hidden=False):
    """Check actual split anatomy and all breast/hand support independently."""
    pin = profile['bodies'][sex]
    shapes = {s.name: s for s in nif.shapes}
    if len(shapes) != len(nif.shapes) or len(nif.shapes) != pin['shapeCount'] or len(nif.nodes) != pin['nodeCount'] or nif.game != 'SKYRIMSE':
        raise ValueError('Composed body structure changed')
    selected = set(profile['hiddenShapes'])
    if not selected <= shapes.keys() or not set(profile['retainedTorsoShapes']) <= shapes.keys():
        raise ValueError('Missing reviewed head-side or retained torso shapes')
    if selected & set(profile['retainedTorsoShapes']):
        raise ValueError('Visibility selection includes retained torso geometry')
    hands = {bone: 0 for bone in resource.HAND_BONES}
    breast = {}
    selection = {}
    for name, shape in shapes.items():
        visible = resource.visible_by_hidden_flags(shape)
        expected_visible = not (hidden and name in selected)
        if visible != expected_visible:
            raise ValueError('Unexpected shape or ancestor visibility: ' + name)
        support = len(trip.shapes[name].get('CLAWTorsoBreastSize', []))
        if support:
            if name in selected or not visible:
                raise ValueError('Cannot hide breast morph support: ' + name)
            breast[name] = support
        for bone in hands:
            count = sum(w > 0 for _, w in shape.bone_weights.get(bone, []))
            if count and (name in selected or not visible):
                raise ValueError('Cannot hide weighted hand geometry: ' + name)
            hands[bone] += count
        expected_tri = 'actors\\werewolfbeast\\character assets\\' + sex + 'bodywerewolf.tri'
        if resource.bodytri(shape) != [('BODYTRI', expected_tri)]:
            raise ValueError('Composed BODYTRI path changed: ' + name)
        if name in selected or name in profile['retainedTorsoShapes']:
            selection[name] = {'blockId': shape.id, 'vertices': len(shape.verts), 'triangles': len(shape.tris),
                               'visibleByFileFlags': visible, 'breastMorphVertices': support,
                               'textures': dict(shape.textures)}
    if breast != pin['breastSupport']:
        raise ValueError('Pinned visible breast morph support changed')
    if list(hands.values()) != [846, 1571]:
        raise ValueError('Pinned bilateral weighted hand support changed')
    return {'shapes': selection, 'visibleBreastMorphSupport': breast, 'visibleWeightedHandVertices': hands}


def compare_readback(original, result, selected):
    """Independent native semantic check in addition to the complete byte proof."""
    if set(original.nodes) != set(result.nodes) or [s.name for s in original.shapes] != [s.name for s in result.shapes]:
        raise ValueError('Native readback graph or shape names changed')
    for a, b in zip(original.shapes, result.shapes):
        expected = a.flags | resource.HIDDEN if a.name in selected else a.flags
        if (b.flags != expected or a.verts != b.verts or a.tris != b.tris or a.uvs != b.uvs
                or a.bone_names != b.bone_names or a.bone_weights != b.bone_weights
                or resource.bodytri(a) != resource.bodytri(b)
                or (a.shader_block_name, bytes(a.shader.properties), a.textures)
                != (b.shader_block_name, bytes(b.shader.properties), b.textures)):
            raise ValueError('Native readback changed geometry, skin or material: ' + a.name)


def build(body_root, skeleton_file, output, *, profile_file=PROFILE, pynifly=None, morphbench=None):
    profile = load_profile(profile_file)
    body_root, skeleton_file = Path(body_root).resolve(strict=True), Path(skeleton_file).resolve(strict=True)
    inputs = [Path(profile_file).resolve(strict=True), skeleton_file]
    # Keep the digests admitted here as the baseline through dependency loading
    # and every native read. Recapturing it later would admit changed inputs.
    source_hashes = {str(inputs[0]): resource.sha256(inputs[0])}
    # Admit all six exact source files before loading native dependencies or writing.
    for sex, pin in profile['bodies'].items():
        names = [(sex + 'bodywerewolf.tri', pin['triSha256'])]
        names += [(f'{sex}bodywerewolf_{endpoint}.nif', digest) for endpoint, digest in enumerate(pin['nifSha256'])]
        for name, digest in names:
            source = body_root / name
            admitted_digest = resource.sha256(source)
            if admitted_digest != digest:
                raise ValueError('Unsupported composed source: ' + name)
            source_hashes[str(source)] = admitted_digest
            inputs.append(source)
    admitted_skeleton_digest = resource.sha256(skeleton_file)
    if admitted_skeleton_digest != profile['skeletonSha256']:
        raise ValueError('Unsupported exact XP32 skeleton input')
    source_hashes[str(skeleton_file)] = admitted_skeleton_digest
    out = resource.safe_output(output, inputs)
    api, NifPatch, TripFile, dependencies = resource.dependencies(pynifly, morphbench)
    if any(resource.sha256(p) != digest for p, digest in source_hashes.items()):
        raise ValueError('A source changed after admission during dependency loading')
    skeleton = api.NifFile(str(skeleton_file))
    descendants = resource.head_descendant_names(skeleton, 'NPC Head [Head]')
    prepared = {}
    for sex, pin in profile['bodies'].items():
        for endpoint in (0, 1):
            source = body_root / f'{sex}bodywerewolf_{endpoint}.nif'
            nif = api.NifFile(str(source))
            morphs, trip = resource.tri_contract(TripFile, body_root / (sex + 'bodywerewolf.tri'), nif, pin['publicMorphCount'], include_trip=True)
            admission(nif, trip, profile, sex)
            missing = {b for s in nif.shapes for b in s.bone_names} - set(skeleton.nodes)
            if missing:
                raise ValueError('Composed body uses bones absent from XP32')
            table = NifPatch(source)
            if not table.consistent() or table.bs_version != 100:
                raise ValueError('Unsupported NIF block table')
            rows = [{'name': s.name, 'flags': s.flags, 'type': table.types[s.id],
                     'offset': table.offsets[s.id], 'size': table.sizes[s.id]} for s in nif.shapes]
            raw, ledger = resource.patch_hidden(table.raw, rows, profile['hiddenShapes'])
            prepared[sex, endpoint] = nif, trip, morphs, raw, ledger
    # The filenames deliberately have no game load tree and never replace world models.
    out.mkdir(parents=True, exist_ok=False)
    (out / 'NOT_INSTALLABLE.txt').write_text(
        'Offline first-person-only CLAW visibility resources. No world model replacement.\n'
        'Eleven anatomical head-side shapes have hidden file flags. The retained torso keeps Head influence.\n'
        'No engine path, sex/weight dispatch, runtime flag persistence, camera, IK or interaction acceptance.\n'
        'Do not install this directory as a mod. No plugin, skeleton, animation or live configuration is supplied.\n', encoding='utf-8')
    report = {'schemaVersion': 1, 'status': 'building', 'installable': False,
              'sourceFamily': profile['sourceFamily'], 'sourceSha256': source_hashes,
              'dependencySha256': dependencies, 'pythonVersion': sys.version,
              'builderSourceSha256': {p.name: resource.sha256(p) for p in [Path(__file__), Path(resource.__file__), Path(__file__).with_name('prepare_first_person.py')]},
              'selection': {'graph': 'first-person', 'engineFilename': None, 'engineDispatch': 'unqualified',
                            'thirdPersonOverrides': [], 'hiddenShapes': profile['hiddenShapes'],
                            'headBoneTransformChanges': False, 'skeletonOutput': None},
              'runtimeGates': ['native filename and weight dispatch', 'sex selection', 'loaded BODYTRI application',
                               'file-hidden flag persistence through graph reload and morph updates',
                               'VRIK head-bone visibility behavior on retained Head-influenced torso',
                               'headset camera/neck clearance', 'IK, HIGGS and PLANCK contacts',
                               'transformation return and save/load'], 'bodies': {}}
    try:
        for sex, pin in profile['bodies'].items():
            directory = out / sex
            directory.mkdir()
            tri_target = directory / (sex + 'bodywerewolf.tri')
            tri_target.write_bytes((body_root / tri_target.name).read_bytes())
            if resource.sha256(tri_target) != pin['triSha256']:
                raise ValueError('Shared absolute TRI bytes changed')
            report['bodies'][sex] = {'tri': str(tri_target.relative_to(out)), 'triSha256': resource.sha256(tri_target), 'endpoints': {}}
            for endpoint in (0, 1):
                original, trip, morphs, raw, ledger = prepared[sex, endpoint]
                target = out / resource_name('first-person', sex, endpoint)
                target.write_bytes(raw)
                source = body_root / f'{sex}bodywerewolf_{endpoint}.nif'
                changed = resource.verify_bytes(source.read_bytes(), target.read_bytes(), ledger)
                result = api.NifFile(str(target))
                compare_readback(original, result, profile['hiddenShapes'])
                verification = admission(result, trip, profile, sex, hidden=True)
                resource.tri_contract(TripFile, tri_target, result, pin['publicMorphCount'])
                residual = {s.name: len({i for bone, rows in s.bone_weights.items() if bone in descendants for i, w in rows if w > 0})
                            for s in result.shapes if resource.visible_by_hidden_flags(s)}
                verification['remainingVisibleHeadInfluence'] = {k: v for k, v in residual.items() if v}
                verification.update(allOtherNifBytesIdentical=True, triBytesIdentical=True,
                                    nativeReadback=True, materialsUvsSkinAndMorphIndicesUnchanged=True)
                report['bodies'][sex]['endpoints'][str(endpoint)] = {
                    'resource': str(target.relative_to(out)), 'nifSha256': resource.sha256(target),
                    'bytesChanged': changed, 'editLedger': ledger, 'publicMorphs': morphs, 'verification': verification}
        if any(resource.sha256(p) != digest for p, digest in source_hashes.items()):
            raise ValueError('A source changed during build')
        report['status'] = 'offline-first-person-visibility-candidate'
    except Exception as exc:
        report['status'], report['failure'] = 'failed', str(exc)
        raise
    finally:
        (out / 'first-person-visibility-report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report
