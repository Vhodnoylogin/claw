"""Receive one admitted ear capture and reconstruct its skinned triangles."""
from __future__ import annotations

from argparse import ArgumentParser
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
from zipfile import BadZipFile, ZipFile

import numpy as np

from avatar_torso import Skin, matrix, observation_plan, offsets, read_pinned_asset, require
from stage_player_armor import (PLAYER_ARMOR_MARKERS, PLAYER_WORLD_MARKERS, PLUGIN, SEXES, armor_path,
                                require_static_nif, verify_record, world_ear_path)
from stage_visible_ears import EAR_DRIVERS, EAR_SHAPE, LEGACY_ALIAS, bodytri, motion, resource_paths
from stereo_calibration import calibrate_head, calibrated_eye, finite_array, transform_points
from stereo_frustum import clip_frustum

CAPTURE_SCHEMA = 'claw-vr-vrik-ear-stereo/1'
RUN_SCHEMA = 'claw-vr-ear-stereo-admission/1'
EQUIPPED_CAPTURE_SCHEMA = 'claw-vr-vrik-ear-stereo/2'
EQUIPPED_RUN_SCHEMA = 'claw-vr-ear-stereo-admission/2'
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


def equipped_case(expected):
    schema = expected.get('schema', RUN_SCHEMA)
    require(schema in (RUN_SCHEMA, EQUIPPED_RUN_SCHEMA), 'Expected a separately admitted ear case')
    return schema == EQUIPPED_RUN_SCHEMA


def read_reply(raw, expected):
    require(type(raw) is dict and raw.get('called') is True and raw.get('returnedType') == 'string'
            and type(raw.get('returned')) is str, 'Expected bounded Papyrus readback from the ear witness')
    payload = raw['returned'].encode('utf-8')
    require(0 < len(payload) <= 32768, 'Papyrus ear witness reply is outside its byte limit')
    reply = read_json(payload)
    schema = EQUIPPED_CAPTURE_SCHEMA if equipped_case(expected) else CAPTURE_SCHEMA
    require(type(reply) is dict and reply.get('schema') == schema and reply.get('status') == 'ready',
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


def fixture_forms(expected):
    forms = expected.get('fixtureForms')
    require(type(forms) is dict and set(forms) == {'item', 'addon'}, 'Expected independently admitted Body32 forms')
    item, addon = forms['item'], forms['addon']
    require(positive_int(item) and positive_int(addon) and 0 < item >> 24 < 0xfe and item & 0xFFFFFF == 0x801
            and addon == item - 1, 'Invalid equipped Body32 plugin index or local forms')
    return item, addon


def qualified_body(slot, forms, path, *, culled):
    return ((slot['item'], slot['addon']) == forms and normalized(slot['modelPath']) == path
            and slot['cloneCull']['effective'] is culled
            and all(slot['predicates'][key] is True for key in
                    ('clonePresent', 'underActorRoot', 'expectedItem', 'expectedAddon', 'expectedModelPath')))


def empty_body(slot):
    return (slot['predicates']['clonePresent'] is False
            and (slot['item'], slot['addon'], slot['modelPath']) == (0, 0, ''))


def empty_equipped_body(slot):
    return empty_body(slot) and slot['partHandle'] is False and slot['cloneName'] == '' and slot['cloneCull'] is None


def admitted_body_route(graph, biped, expected, equipped):
    sex = expected['sex']
    third, first = graph['viewThirdPerson'], graph['viewFirstPerson']
    if equipped:
        forms = fixture_forms(expected)
        model = normalized(world_ear_path(sex, '.nif')).removeprefix('meshes\\')
        first_marker = graph['firstPersonDispatchMarker']
        first_active = first['active']
        if first_marker is None:
            first_route_ok = empty_equipped_body(first_active)
        else:
            first_route_ok = (first_marker == PLAYER_ARMOR_MARKERS[sex]
                              and qualified_body(first_active, forms, normalized(armor_path(sex)), culled=True))
        alternate = (graph['worldDispatchMarker'] == PLAYER_WORLD_MARKERS[sex]
                     and empty_equipped_body(third['buffered'])
                     and empty_equipped_body(first['buffered']) and first_route_ok)
    else:
        forms = ITEM, ADDON
        model = normalized(f'actors/werewolfbeast/character assets/{sex}bodywerewolf_1.nif')
        alternate = all(empty_body(first[bank]) for bank in ('active', 'buffered'))
    require((biped['slot'], biped['item'], biped['addon']) == (32, *forms)
            and normalized(biped['modelPath']) == model and qualified_body(third['active'], forms, model, culled=False)
            and first['actorRootCull']['effective'] is True and alternate,
            'Wrong effective world or first-person model route')


def admitted_sample(reply, expected, ear_tri):
    sex = expected['sex']
    weight, equipped = expected['weight'], equipped_case(expected)
    require(sex in ('male', 'female') and type(weight) in (int, float) and 0 <= weight <= 100,
            'Expected a fixed admitted sex and weight')
    sample = reply['sample']
    require(sample['phase'] == 'PostVrikPostHiggs' and type(sample['earStereoCaptureVersion']) is int
            and sample['earStereoCaptureVersion'] == (2 if equipped else 1)
            and (sample['player'], sample['base'], sample['race'], sample['cell'])
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
    admitted_body_route(graph, sample['biped'], expected, equipped)
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


def archive_payload(data, inventory, selected):
    with ZipFile(BytesIO(data)) as archive:
        names = archive.namelist()
        require(set(names) == inventory and len(names) == len(inventory), 'Unexpected ear trial archive inventory')
        return {name: archive.read(name) for name in selected}


def motion_xml(sex):
    return motion.fsmp_motion.XML_ROOT + f'CLAWMotion{sex.title()}.xml'


def require_motion_xml(files, sex):
    require(files[motion_xml(sex)] == motion.fsmp_motion.render_xml(sex == 'female'),
            'World FSMP XML must match the authored rig for that sex')


def require_legacy_motion_binding(data, expected_xml):
    nif = motion.fsmp_motion.Nif(data)
    require(nif.kind(0) == 'NiNode', 'Expected a legacy ear scene root')
    hook = motion.fsmp_motion.HOOK.lower().encode('ascii')
    bindings = []
    for index, block in enumerate(nif.blocks):
        if nif.kind(index) == 'NiStringExtraData':
            require(len(block) == 8, 'Invalid legacy ear string extra')
            name, value = struct.unpack('<II', block)
            require(max(name, value) < len(nif.strings), 'Invalid legacy ear string index')
            if nif.strings[name].strip().lower() == hook:
                bindings.append((index, nif.strings[value]))
    if expected_xml is None:
        require(not bindings, 'Static legacy ear NIF must have no FSMP binding')
        return
    root = nif.blocks[0]
    require(len(root) >= 8, 'Truncated legacy ear root')
    count = struct.unpack_from('<I', root, 4)[0]
    require(8 + 4 * count <= len(root), 'Truncated legacy ear root extras')
    refs = struct.unpack_from(f'<{count}I', root, 8)
    require(len(bindings) == 1 and bindings[0][1] == expected_xml.encode('ascii')
            and refs.count(bindings[0][0]) == 1,
            'Legacy ear NIF must have exactly one root FSMP binding to its authored XML')


def equipped_payload(data, admission, sex, mode):
    fixture_forms(admission)
    require(('motionArchive' in admission) == (mode == 'fsmp'), 'Equipped FSMP arm requires exactly one motion archive')
    world, tri = (world_ear_path(sex, extension) for extension in ('.nif', '.tri'))
    first = resource_paths(sex, 1)
    base = {PLUGIN, *(resource_paths(s, endpoint) for s in SEXES for endpoint in (None, 0, 1)),
            *(world_ear_path(s, extension) for s in SEXES for extension in ('.nif', '.tri'))}
    files = archive_payload(data, base, {PLUGIN, world, tri, first, resource_paths(sex)})
    require_static_nif(files[first], expected_sex=sex)
    require_static_nif(files[world], expected_tri=normalized(tri).removeprefix('meshes\\'))
    if mode == 'fsmp':
        _, overlay = read_pinned_asset(admission['motionArchive'])
        active = {path for s in SEXES for path in (world_ear_path(s, '.nif'), motion_xml(s))}
        xml = motion_xml(sex)
        selected = archive_payload(overlay, active, {world, xml})
        require_motion_xml(selected, sex)
        require(selected[world] == motion.fsmp_motion.bind_nif(files[world], xml)[0],
                'Equipped world FSMP NIF must add only the corresponding XML binding')
        files.update(selected)
    return world, tri, files


def admitted_assets(admission):
    equipped = equipped_case(admission)
    require('schema' in admission, 'Expected a separately admitted ear case')
    witness, dll = read_pinned_asset(admission['witnessDll'])
    mapped = admission['mappedWitness']
    require(witness.name.casefold() == 'clawvrmodeltopology.dll' and mapped['pid'] == admission['pid']
            and pin_bytes(dll, mapped), 'Mapped witness differs from the admitted native DLL')
    _, data = read_pinned_asset(admission['archive'])
    sex, mode = admission['sex'], admission['mode']
    require(sex in ('male', 'female') and mode in ('static', 'fsmp'), 'Unexpected trial package arm')
    if equipped:
        nif, tri, files = equipped_payload(data, admission, sex, mode)
    else:
        nif, tri = LEGACY_ALIAS, world_ear_path(sex, '.tri')
        expected = {nif, tri}
        if mode == 'fsmp':
            expected.add(motion_xml(sex))
        files = archive_payload(data, expected, expected)
        if mode == 'fsmp':
            require_motion_xml(files, sex)
        require_legacy_motion_binding(files[nif], motion_xml(sex) if mode == 'fsmp' else None)
    observed = admission['effectiveVfs']
    require(set(files) == set(observed), 'Admitted VFS inventory differs from the trial archive')
    require(all(pin_bytes(payload, observed[name]) for name, payload in files.items()), 'A loaded VFS asset differs from the exact trial arm')
    if equipped:
        with TemporaryDirectory(prefix='claw-ear-stereo-fixture-') as scratch:
            plugin = Path(scratch) / PLUGIN
            plugin.write_bytes(files[PLUGIN])
            verify_record(plugin, visible_ears=True)
    return files[nif], files[tri], tri


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
    report = {'schema': f'claw-vr-ear-stereo-replay/{sample["earStereoCaptureVersion"]}',
              'captureSha256': digest, 'phaseSequence': sample['phaseSequence'],
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
