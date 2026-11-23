"""Receive one admitted ear capture and reconstruct its skinned triangles."""
from __future__ import annotations

from argparse import ArgumentParser
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import BadZipFile, ZipFile

import numpy as np

from avatar_torso import Skin, matrix, observation_plan, offsets, read_pinned_asset, require
from stage_visible_ears import EAR_DRIVERS, EAR_SHAPE, LEGACY_ALIAS, bodytri, motion, resource_paths
from stereo_calibration import calibrate_head, calibrated_eye, finite_array, transform_points
from stereo_frustum import clip_frustum

CAPTURE_SCHEMA = 'claw-vr-vrik-ear-stereo/1'
RUN_SCHEMA = 'claw-vr-ear-stereo-admission/1'
CALIBRATION_SCHEMA = 'claw-vr-ear-stereo-calibration/1'
PLAYER, BASE, RACE, CELL, ITEM, ADDON = 0x14, 7, 0xCDD84, 0x0A01A5C6, 0xCDD86, 0xCDD87
HEAD_BONE = 'NPC Head [Head]'


def read_json(raw):
    def unique(pairs):
        result = dict(pairs)
        require(len(result) == len(pairs), 'Duplicate JSON key')
        return result

    def reject_constant(value):
        raise ValueError('Unsupported JSON constant: ' + value)

    return json.loads(raw, object_pairs_hook=unique, parse_constant=reject_constant)


def normalized(path):
    return path.replace('/', '\\').casefold()


def positive_int(value):
    return type(value) is int and value > 0


def read_reply(raw, expected):
    require(type(raw) is dict and raw.get('called') is True and raw.get('returnedType') == 'string'
            and type(raw.get('returned')) is str, 'Expected bounded Papyrus readback from the ear witness')
    payload = raw['returned'].encode('utf-8')
    require(0 < len(payload) <= 32768, 'Papyrus ear witness reply is outside its byte limit')
    reply = read_json(payload)
    require(type(reply) is dict and reply.get('schema') == CAPTURE_SCHEMA and reply.get('status') == 'ready',
            'Ear witness is not ready')
    for key in ('pid', 'nonce', 'epoch'):
        require(positive_int(expected[key]) and positive_int(reply.get(key)) and reply[key] == expected[key],
                'Witness differs from the admitted ' + key)
    return reply, sha256(payload).hexdigest()


def read_eye(record, name):
    require(record['eye'] == name and type(record['engineOrthographic']) is bool, 'Unexpected eye fields or order')
    eye = {
        **record, 'engineFrustumLTRB_NF': finite_array(record['engineFrustumLTRB_NF'], (6,)),
        'engineViewportLTRB': finite_array(record['engineViewportLTRB'], (4,)),
        'openVrProjectionRawLTRB': finite_array(record['openVrProjectionRawLTRB'], (4,)),
        'openVrEyeToHeadRows': finite_array(record['openVrEyeToHeadRows'], (3, 4)),
    }
    for key in ('engineFrustumLTRB_NF', 'engineViewportLTRB', 'openVrProjectionRawLTRB'):
        left, right, top, bottom = eye[key][:4]
        require(left != right and top != bottom, 'Degenerate raw eye aperture')
    near, far = eye['engineFrustumLTRB_NF'][4:]
    require(0 < near < far, 'Invalid engine eye depth')
    rotation = eye['openVrEyeToHeadRows'][:, :3]
    require(np.allclose(rotation.T @ rotation, np.eye(3), atol=2e-4, rtol=0) and np.linalg.det(rotation) > 0,
            'Invalid OpenVR eye rotation')
    return eye


def admitted_sample(reply, expected, ear_tri):
    sex = expected['sex']
    weight = expected['weight']
    require(sex in ('male', 'female') and type(weight) in (int, float) and 0 <= weight <= 100,
            'Expected a fixed admitted sex and weight')
    sample = reply['sample']
    require(sample['phase'] == 'PostVrikPostHiggs' and type(sample['earStereoCaptureVersion']) is int
            and sample['earStereoCaptureVersion'] == 1 and (sample['player'], sample['base'], sample['race'], sample['cell'])
            == (PLAYER, BASE, RACE, CELL) and positive_int(expected['handle']) and positive_int(sample['handle'])
            and sample['handle'] == expected['handle'] and type(sample['sex']) is int and sample['sex'] == (sex == 'female')
            and type(sample['rawWeight']) in (int, float) and sample['rawWeight'] == weight,
            'Unexpected actor or out-of-phase ear sample')
    notice = reply['worldGate']
    armed_after = expected['armedAfterPhase']
    require(notice['generation'] == reply['epoch'] and notice['loading'] is False
            and notice['initialDisarm'] in ('committed', 'authoritative-world') and positive_int(expected['higgsBuild'])
            and sample['higgsBuild'] == notice['higgsBuild'] == expected['higgsBuild']
            and type(armed_after) is int and armed_after >= 0 and positive_int(sample['phaseSequence'])
            and positive_int(notice['postPhaseCount']) and notice['postPhaseCount'] >= sample['phaseSequence'] > armed_after,
            'Ear sample does not match the admitted world phase')
    require(all(sample[key] is False for key in ('eyeProjectionQualified', 'atomicRenderSnapshot', 'renderedPixelsVerified')),
            'Raw witness must not claim calibrated or rendered evidence')
    graph = reply['body32']
    require(graph['slot'] == 32 and graph['sameLoadedRoot'] is False and graph['visibleActiveClone'] is True
            and graph['alternateViewQualified'] is True and graph['worldBufferedEmpty'] is True
            and type(graph['actorRootCloneVisits']) is int and graph['actorRootCloneVisits'] == 1
            and type(graph['stableChildCount']) is int and 1 < graph['stableChildCount'] <= 60,
            'Active world Body32 or inactive view controls failed')
    model = normalized(f'actors/werewolfbeast/character assets/{sex}bodywerewolf_1.nif')
    third, first = graph['viewThirdPerson']['active'], graph['viewFirstPerson']
    biped = sample['biped']
    require((biped['slot'], biped['item'], biped['addon']) == (32, ITEM, ADDON)
            and (third['item'], third['addon']) == (ITEM, ADDON)
            and normalized(biped['modelPath']) == normalized(third['modelPath']) == model
            and third['cloneCull']['effective'] is False
            and all(third['predicates'][key] is True for key in
                    ('clonePresent', 'underActorRoot', 'expectedItem', 'expectedAddon', 'expectedModelPath'))
            and first['actorRootCull']['effective'] is True
            and all(first[bank]['predicates']['clonePresent'] is False and
                    (first[bank]['item'], first[bank]['addon'], first[bank]['modelPath']) == (0, 0, '')
                    for bank in ('active', 'buffered')), 'Wrong effective world or first-person model route')
    require(sample['earBodyTri'] == normalized(ear_tri).removeprefix('meshes\\')
            and type(sample['earVerticesObserved']) is int and sample['earVerticesObserved'] in (0, 1354)
            and type(sample['earTrianglesObserved']) is int and sample['earTrianglesObserved'] in (0, 2394),
            'Wrong ear TRI or incompatible observed topology')
    ears = [shape for shape in sample['shapes'] if shape['name'].casefold() == EAR_SHAPE.casefold()]
    require(len(ears) == 1 and ears[0]['skinned'] is True and ears[0]['ancestorCull'] is False,
            'One active unculled skinned ear shape is required')
    left, right = sample['eyeOptics']
    eyes = [read_eye(left, 'left'), read_eye(right, 'right')]
    require(sample['nearLeft'] == eyes[0]['engineFrustumLTRB_NF'][4], 'Incoherent left-eye near observations')
    return sample, eyes


def pin_bytes(data, info):
    return type(info.get('bytes')) is int and len(data) == info['bytes'] and sha256(data).hexdigest() == info['sha256']


def admitted_assets(admission):
    require(admission['schema'] == RUN_SCHEMA, 'Expected a separately admitted ear case')
    witness, dll = read_pinned_asset(admission['witnessDll'])
    mapped = admission['mappedWitness']
    require(witness.name.casefold() == 'clawvrmodeltopology.dll' and mapped['pid'] == admission['pid']
            and pin_bytes(dll, mapped), 'Mapped witness differs from the admitted native DLL')
    _, data = read_pinned_asset(admission['archive'])
    sex, mode = admission['sex'], admission['mode']
    require(sex in ('male', 'female') and mode in ('static', 'fsmp'), 'Unexpected trial package arm')
    tri = Path(resource_paths(sex)).with_name('EarWorldTrial.tri').as_posix()
    expected = {LEGACY_ALIAS, tri}
    if mode == 'fsmp':
        expected.add(motion.fsmp_motion.XML_ROOT + f'CLAWMotion{sex.title()}.xml')
    observed = admission['effectiveVfs']
    with ZipFile(BytesIO(data)) as archive:
        names = archive.namelist()
        require(set(names) == expected == set(observed) and len(names) == len(expected), 'Admitted VFS inventory differs from the trial archive')
        files = {name: archive.read(name) for name in names}
    require(all(pin_bytes(payload, observed[name]) for name, payload in files.items()), 'A loaded VFS asset differs from the exact trial arm')
    return files[LEGACY_ALIAS], files[tri], tri


def ear_frames(plan, sample):
    transforms, values = sample['earBones'], sample['earEffectiveMorphs']
    require(set(plan['bones']) == set(transforms) and set(plan['morphs']) == set(values) and
            all(type(value) in (float, int) and np.isfinite(value) for value in values.values()),
            'Expected the exact co-sampled ear bone and morph inventory')
    return {name: matrix(transforms[name]['world']) for name in plan['bones']}


def reconstruct(shape, records, sample):
    plan = observation_plan(shape, records)
    require((plan['vertices'], plan['triangles']) == (1354, 2394), 'Wrong authored ear topology')
    frames = ear_frames(plan, sample)
    skin = Skin(shape, records, sample['earEffectiveMorphs'])
    used, triangles = np.unique(skin.faces, return_inverse=True)
    return skin.support(used, frames, None)[triangles.reshape(-1, 3)]


def ear_motion(shape, records, baseline, sample):
    """Compare the observed ear with the same pose carrying the baseline ear bones."""
    plan = observation_plan(shape, records)
    require((plan['vertices'], plan['triangles']) == (1354, 2394), 'Wrong authored ear topology')
    require({HEAD_BONE, *EAR_DRIVERS} <= set(plan['bones']), 'Expected the head and all four ear drivers')
    old, current = ear_frames(plan, baseline), ear_frames(plan, sample)
    values = sample['earEffectiveMorphs']
    require(baseline['earEffectiveMorphs'] == values, 'Effective ear morphs changed between captures')
    skin = Skin(shape, records, values)
    vertices = np.unique(skin.faces)
    carry = current[HEAD_BONE] @ np.linalg.inv(old[HEAD_BONE])
    held = current | {name: carry @ old[name] for name in EAR_DRIVERS}
    old_world = skin.support(vertices, old, None)
    current_world = skin.support(vertices, current, None)
    old_local = skin.support(vertices, old, HEAD_BONE)
    held_local = skin.support(vertices, held, HEAD_BONE)
    current_local = skin.support(vertices, current, HEAD_BONE)

    def displacement(delta):
        lengths = np.linalg.norm(delta, axis=1)
        return {'max': float(lengths.max()), 'rms': float(np.sqrt(np.mean(lengths ** 2)))}

    return {'vertices': len(vertices),
            'worldDisplacementGu': displacement(current_world - old_world),
            'headRelativeDisplacement': displacement(current_local - old_local),
            'nonEarSkinContribution': displacement(held_local - old_local),
            'earDriverContribution': displacement(current_local - held_local)}


def admitted_baseline(packet, request, admission, ear_tri):
    require(set(request) == {'nonce', 'armedAfterPhase'} and request['nonce'] != admission['nonce'],
            'Expected a distinct independently admitted baseline request')
    expected = admission | request
    reply, digest = read_reply(packet, expected)
    sample, _ = admitted_sample(reply, expected, ear_tri)
    require(sample['phaseSequence'] <= admission['armedAfterPhase'],
            'Baseline must complete before the measured request is armed')
    matrix(sample['camera'])
    matrix(sample['hmd'])
    return sample, digest


def replay(packet, admission, pynifly, calibration=None, *, baseline_packet=None, baseline_request=None):
    require((baseline_packet is None) == (baseline_request is None), 'Both the baseline packet and its request are required')
    nif, tri, tri_path = admitted_assets(admission)
    reply, digest = read_reply(packet, admission)
    sample, eyes = admitted_sample(reply, admission, tri_path)
    hmd_world = matrix(sample['hmd'])
    matrix(sample['camera'])
    paired = {}
    if baseline_packet is not None:
        baseline, baseline_digest = admitted_baseline(baseline_packet, baseline_request, admission, tri_path)
    api, _ = motion.fsmp_motion.common.load_pynifly(Path(pynifly))
    with TemporaryDirectory(prefix='claw-ear-stereo-replay-') as scratch:
        path = Path(scratch) / 'trial.nif'
        path.write_bytes(nif)
        parsed = api.NifFile(str(path))
        shape, = [row for row in parsed.shapes if row.name == EAR_SHAPE]
        require(bodytri(shape) == [('BODYTRI', sample['earBodyTri'])], 'Serialized ear does not bind the observed TRI')
        records = {k: v for k, v in offsets(tri).items() if k[0] == EAR_SHAPE}
        points = reconstruct(shape, records, sample)
        if baseline_packet is not None:
            paired = {'baselineCaptureSha256': baseline_digest, 'baselinePhaseSequence': baseline['phaseSequence'],
                      'earMotion': ear_motion(shape, records, baseline, sample)}
    report = {'schema': 'claw-vr-ear-stereo-replay/1', 'captureSha256': digest, 'phaseSequence': sample['phaseSequence'],
              'triangles': len(points), 'worldBoundsGu': [points.min(axis=(0, 1)).tolist(), points.max(axis=(0, 1)).tolist()],
              'projectionControlsConsistent': False, 'engineProjectionQualified': False, 'renderedPixelsVerified': False,
              **paired}
    if calibration is not None:
        require(calibration['schema'] == CALIBRATION_SCHEMA and calibration['captureSha256'] == digest,
                'Calibration controls are for another capture')
        provider_to_world, scale, basis = calibrate_head(hmd_world, calibration['headFit'], calibration['headHoldout'])
        results = {}
        for eye in eyes:
            name = eye['eye']
            world_to_eye, planes = calibrated_eye(eye, calibration['eyes'][name], provider_to_world, scale)
            results[name] = clip_frustum(transform_points(world_to_eye, points), **planes)
        report.update(projectionControlsConsistent=True, gameUnitsPerMetre=scale, basis=basis,
                      providerFrustumIntersection=results)
    return report


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--admission', type=Path, required=True)
    parser.add_argument('--pynifly', type=Path, required=True)
    parser.add_argument('--calibration', type=Path)
    parser.add_argument('--baseline-packet', type=Path, help='Earlier native ear packet from the same admitted trial')
    parser.add_argument('--baseline-request', type=Path, help='JSON with the baseline nonce and armedAfterPhase')
    args = parser.parse_args()
    try:
        report = replay(read_json(args.packet.read_bytes()), read_json(args.admission.read_bytes()), args.pynifly,
                        read_json(args.calibration.read_bytes()) if args.calibration else None,
                        baseline_packet=read_json(args.baseline_packet.read_bytes()) if args.baseline_packet else None,
                        baseline_request=read_json(args.baseline_request.read_bytes()) if args.baseline_request else None)
    except (BadZipFile, OSError, ValueError, KeyError, TypeError, RuntimeError, np.linalg.LinAlgError) as error:
        parser.exit(2, f'CLAW ear stereo replay: {error}\n')
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
