"""Reject stale stereo evidence and exercise independent optics controls."""
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from zipfile import ZipFile

import numpy as np

from avatar_ear_stereo import (ADDON, BASE, CAPTURE_SCHEMA, CELL, EAR_DRIVERS, EAR_SHAPE, EQUIPPED_CAPTURE_SCHEMA,
                              EQUIPPED_RUN_SCHEMA, HEAD_BONE, ITEM, LEGACY_ALIAS, PLAYER, RACE, RUN_SCHEMA,
                              admitted_assets, admitted_baseline, admitted_sample, ear_motion, motion, motion_xml,
                              read_reply, require_legacy_motion_binding)
from stage_player_armor import PLUGIN, armor_path, resource_paths, world_armor_path, world_ear_path
from stereo_calibration import calibrate_head, calibrated_eye, transform_points
from test_vr_dispatch import nif_fixture

TRI = r'actors\werewolfbeast\claw\firstperson\female\earworldtrial.tri'


def payload():
    expected = {'pid': 492, 'nonce': 3, 'epoch': 7, 'handle': 80, 'sex': 'female', 'weight': 30, 'higgsBuild': 9,
                'armedAfterPhase': 7}
    model = r'Actors\WerewolfBeast\Character Assets\FemaleBodyWereWolf_1.NIF'
    body = {'slot': 32, 'item': ITEM, 'addon': ADDON, 'modelPath': model}
    active = {**body, 'cloneCull': {'effective': False}, 'predicates': dict.fromkeys(
        ('clonePresent', 'underActorRoot', 'expectedItem', 'expectedAddon', 'expectedModelPath'), True)}
    empty = {'item': 0, 'addon': 0, 'modelPath': '', 'predicates': {'clonePresent': False}}
    graph = {'slot': 32, 'sameLoadedRoot': False, 'visibleActiveClone': True, 'alternateViewQualified': True,
             'worldBufferedEmpty': True, 'actorRootCloneVisits': 1, 'stableChildCount': 22,
             'viewThirdPerson': {'active': active},
             'viewFirstPerson': {'actorRootCull': {'effective': True}, 'active': empty, 'buffered': deepcopy(empty)}}
    eyes = [{'eye': name, 'engineOrthographic': False, 'engineFrustumLTRB_NF': [-1, 1, 1, -1, 7, 700],
             'engineViewportLTRB': [0, 1, 1, 0], 'openVrProjectionRawLTRB': [-1, 1, -1, 1],
             'openVrEyeToHeadRows': [[1, 0, 0, offset], [0, 1, 0, 0], [0, 0, 1, 0]]}
            for name, offset in (('left', -.03), ('right', .03))]
    sample = {'phase': 'PostVrikPostHiggs', 'earStereoCaptureVersion': 1, 'player': PLAYER, 'base': BASE,
              'race': RACE, 'cell': CELL, 'handle': 80, 'sex': 1, 'rawWeight': 30, 'phaseSequence': 8,
              'higgsBuild': 9, 'biped': body, 'nearLeft': 7, 'eyeProjectionQualified': False,
              'atomicRenderSnapshot': False, 'renderedPixelsVerified': False, 'earBodyTri': TRI,
              'earVerticesObserved': 0, 'earTrianglesObserved': 2394, 'eyeOptics': eyes,
              'shapes': [{'name': EAR_SHAPE, 'skinned': True, 'ancestorCull': False}]}
    reply = dict(schema=CAPTURE_SCHEMA, pid=492, nonce=3, status='ready', epoch=7, sample=sample, body32=graph,
                 worldGate={'loading': False, 'generation': 7, 'initialDisarm': 'committed',
                            'higgsBuild': 9, 'postPhaseCount': 8})
    return reply, expected


def packet(reply):
    return {'called': True, 'returnedType': 'string', 'returned': json.dumps(reply)}


def equipped_trial(sex, *, occupied):
    reply, expected = payload()
    forms = {'item': 0x12000801, 'addon': 0x12000800}
    expected.update(schema=EQUIPPED_RUN_SCHEMA, fixtureForms=forms, sex=sex)
    reply['schema'] = EQUIPPED_CAPTURE_SCHEMA
    reply['sample'].update(earStereoCaptureVersion=2, sex=int(sex == 'female'),
                           earBodyTri=world_armor_path(sex, True).lower().replace('.nif', '.tri'))
    reply['sample']['biped'].update(forms, modelPath=world_armor_path(sex, True))
    graph = reply['body32']
    first = graph['viewFirstPerson']
    third = graph['viewThirdPerson']
    for row in (first['active'], first['buffered']):
        row.update(partHandle=False, cloneName='', cloneCull=None)
    third['buffered'] = deepcopy(first['buffered'])
    third['active'].update(forms, modelPath=world_armor_path(sex, True))
    third['active']['predicates']['underBipedRoot'] = False
    sex_marker = sex[0].upper()
    graph.update(worldDispatchMarker='W_' + sex_marker,
                 firstPersonDispatchMarker='P_' + sex_marker if occupied else None)
    if occupied:
        first['active'] = deepcopy(third['active'])
        first['active']['cloneCull']['effective'] = True
        first['active']['modelPath'] = armor_path(sex)
    return reply, expected


def pin_payload(payload):
    return {'bytes': len(payload), 'sha256': sha256(payload).hexdigest()}


def pin_file(path):
    return {'path': str(path), **pin_payload(path.read_bytes())}


def transform(position=(0, 0, 0), rotation=None, scale=1):
    return {'position': list(position), 'rotation': np.eye(3).tolist() if rotation is None else rotation,
            'scale': scale}


class StereoAdmissionTests(unittest.TestCase):
    def test_exact_ready_callback_and_world_route(self):
        reply, expected = payload()
        got, digest = read_reply(packet(reply), expected)
        self.assertEqual(len(digest), 64)
        _, eyes = admitted_sample(got, expected, TRI)
        self.assertEqual([eye['eye'] for eye in eyes], ['left', 'right'])

    def test_rejects_stale_callback_duplicate_fields_and_incoherent_scene(self):
        reply, expected = payload()
        with self.assertRaisesRegex(ValueError, 'epoch'):
            read_reply(packet(reply), expected | {'epoch': 8})
        with self.assertRaisesRegex(ValueError, 'world phase'):
            admitted_sample(reply, expected | {'armedAfterPhase': 8}, TRI)
        duplicate = packet(reply)
        duplicate['returned'] = '{"pid":492,' + duplicate['returned'][1:]
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON key'):
            read_reply(duplicate, expected)
        for field, value in (('rawWeight', 20), ('handle', 81), ('earBodyTri', TRI.replace('female', 'male')),
                             ('atomicRenderSnapshot', True), ('eyeOptics', list(reversed(reply['sample']['eyeOptics'])))):
            changed = deepcopy(reply)
            changed['sample'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                admitted_sample(changed, expected, TRI)
        reply['body32']['worldBufferedEmpty'] = False
        with self.assertRaisesRegex(ValueError, 'Body32'):
            admitted_sample(reply, expected, TRI)

    def test_separate_vfs_hashes_must_match(self):
        with TemporaryDirectory() as scratch:
            root = Path(scratch)
            witness = root / 'CLAWVRModelTopology.dll'
            witness.write_bytes(b'witness')
            archive = root / 'ears.zip'
            tri = 'Meshes/Actors/WerewolfBeast/CLAW/FirstPerson/female/EarWorldTrial.tri'
            nif = nif_fixture(TRI.encode('ascii'))
            members = {LEGACY_ALIAS: nif, tri: b'trial TRI'}
            with ZipFile(archive, 'w') as dest:
                for name, data in members.items():
                    dest.writestr(name, data)
            vfs = {name: pin_payload(data) for name, data in members.items()}
            admission = {'schema': RUN_SCHEMA, 'pid': 492, 'sex': 'female', 'mode': 'static', 'archive': pin_file(archive),
                         'effectiveVfs': vfs, 'witnessDll': pin_file(witness), 'mappedWitness': pin_file(witness) | {'pid': 492}}
            self.assertEqual(admitted_assets(admission), (nif, b'trial TRI', tri))
            vfs[tri]['sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'loaded VFS'):
                admitted_assets(admission)

    def test_legacy_motion_archive_rejects_hash_matched_malformed_xml(self):
        with TemporaryDirectory() as scratch:
            root = Path(scratch)
            witness = root / 'CLAWVRModelTopology.dll'
            witness.write_bytes(b'witness')
            archive = root / 'ears.zip'
            tri = world_ear_path('female', '.tri')
            members = {LEGACY_ALIAS: b'ear mesh', tri: b'trial TRI', motion_xml('female'): b'not XML'}
            with ZipFile(archive, 'w') as dest:
                for name, data in members.items():
                    dest.writestr(name, data)
            admission = {'schema': RUN_SCHEMA, 'pid': 492, 'sex': 'female', 'mode': 'fsmp', 'archive': pin_file(archive),
                         'effectiveVfs': {name: pin_payload(data) for name, data in members.items()},
                         'witnessDll': pin_file(witness), 'mappedWitness': pin_file(witness) | {'pid': 492}}
            with self.assertRaisesRegex(ValueError, 'authored rig for that sex'):
                admitted_assets(admission)

    def test_legacy_motion_binding_requires_the_selected_root_hook(self):
        static = nif_fixture(TRI.encode('ascii'))
        xml = motion_xml('female')
        bound, _ = motion.fsmp_motion.bind_nif(static, xml)
        wrong, _ = motion.fsmp_motion.bind_nif(static, motion_xml('male'))
        detached = motion.fsmp_motion.Nif(bound)
        detached.blocks[0] = motion.fsmp_motion.Nif(static).blocks[0]
        require_legacy_motion_binding(static, None)
        require_legacy_motion_binding(bound, xml)
        with self.assertRaisesRegex(ValueError, 'no FSMP binding'):
            require_legacy_motion_binding(bound, None)
        for payload in (static, wrong, detached.bytes()):
            with self.subTest(payload=sha256(payload).hexdigest()), self.assertRaisesRegex(ValueError, 'root FSMP binding'):
                require_legacy_motion_binding(payload, xml)

    def test_ear_motion_baseline_is_same_session_and_precedes_current_request(self):
        reply, expected = payload()
        reply['sample'].update(hmd=transform(), camera=transform())
        current = expected | {'nonce': 4, 'armedAfterPhase': 8}
        request = {key: expected[key] for key in ('nonce', 'armedAfterPhase')}
        sample, digest = admitted_baseline(packet(reply), request, current, TRI)
        self.assertEqual(sample['phaseSequence'], 8)
        self.assertEqual(len(digest), 64)
        with self.assertRaisesRegex(ValueError, 'must complete'):
            admitted_baseline(packet(reply), request, current | {'armedAfterPhase': 7}, TRI)
        with self.assertRaisesRegex(ValueError, 'epoch'):
            admitted_baseline(packet(reply), request, current | {'epoch': 8}, TRI)
        with self.assertRaisesRegex(ValueError, 'distinct'):
            admitted_baseline(packet(reply), request, current | {'nonce': request['nonce']}, TRI)


class EquippedAdmissionTests(unittest.TestCase):
    def test_both_sexes_and_clean_alternate_view_states(self):
        for sex in ('male', 'female'):
            for occupied in (True, False):
                with self.subTest(sex=sex, occupied=occupied):
                    reply, expected = equipped_trial(sex, occupied=occupied)
                    decoded, _ = read_reply(packet(reply), expected)
                    sample, eyes = admitted_sample(decoded, expected, world_ear_path(sex, '.tri'))
                    self.assertEqual(sample['sex'], int(sex == 'female'))
                    self.assertEqual(len(eyes), 2)

    def test_schema_and_runtime_forms_cannot_mix_stock_and_equipped_trials(self):
        reply, expected = equipped_trial('female', occupied=True)
        with self.assertRaisesRegex(ValueError, 'is not ready'):
            read_reply(packet(reply), expected | {'schema': RUN_SCHEMA})
        stock, _ = payload()
        with self.assertRaisesRegex(ValueError, 'is not ready'):
            read_reply(packet(stock), expected)
        for forms in (None, {'item': ITEM, 'addon': ADDON}, {'item': 0xFE000801, 'addon': 0xFE000800},
                      {'item': 0x13000801, 'addon': 0x12000800}, {'item': 0x13000801, 'addon': 0x13000800}):
            with self.subTest(forms=forms), self.assertRaisesRegex(ValueError, 'forms|route'):
                admitted_sample(reply, expected | {'fixtureForms': forms}, TRI)
        reply['sample']['earStereoCaptureVersion'] = 1
        with self.assertRaisesRegex(ValueError, 'out-of-phase'):
            admitted_sample(reply, expected, TRI)

    def test_wrong_view_marker_forms_visibility_or_residue_is_rejected(self):
        reply, expected = equipped_trial('female', occupied=True)
        changes = (
            (('worldDispatchMarker',), 'P_F'),
            (('worldDispatchMarker',), 'W_M'),
            (('firstPersonDispatchMarker',), None),
            (('firstPersonDispatchMarker',), 'W_F'),
            (('viewFirstPerson', 'active', 'modelPath'), world_armor_path('female', True)),
            (('viewFirstPerson', 'active', 'cloneCull', 'effective'), False),
            (('viewFirstPerson', 'active', 'predicates', 'underActorRoot'), False),
            (('viewFirstPerson', 'buffered', 'partHandle'), True),
            (('viewThirdPerson', 'buffered', 'cloneName'), 'unrelated mesh'),
            (('viewThirdPerson', 'active', 'addon'), ADDON),
        )
        for keys, value in changes:
            changed = deepcopy(reply)
            row = changed['body32']
            for key in keys[:-1]:
                row = row[key]
            row[keys[-1]] = value
            with self.subTest(keys=keys, value=value), self.assertRaisesRegex(ValueError, 'route'):
                admitted_sample(changed, expected, TRI)

    def test_baseline_requires_equipped_route_and_correct_identity(self):
        reply, prior = equipped_trial('female', occupied=True)
        reply['sample'].update(hmd=transform(), camera=transform())
        current = prior | {'nonce': 4, 'armedAfterPhase': 8}
        request = {key: prior[key] for key in ('nonce', 'armedAfterPhase')}
        self.assertEqual(admitted_baseline(packet(reply), request, current, TRI)[0]['phaseSequence'], 8)
        reply['body32']['worldDispatchMarker'] = 'W_M'
        with self.assertRaisesRegex(ValueError, 'route'):
            admitted_baseline(packet(reply), request, current, TRI)


@unittest.skipUnless(os.getenv('CLAW_VR_PLAYER_WORLD_EAR_ROOT'), 'Explicit built world-ear outfit required')
class EquippedArchiveTests(unittest.TestCase):
    def test_admits_exact_selected_winners_for_both_sexes_and_arms(self):
        root = Path(os.environ['CLAW_VR_PLAYER_WORLD_EAR_ROOT'])
        base = root / Path(PLUGIN).with_suffix('.zip')
        overlay = root / (Path(PLUGIN).stem + ' - World FSMP.zip')
        base_pin, overlay_pin = pin_file(base), pin_file(overlay)
        with TemporaryDirectory() as scratch, ZipFile(base) as static, ZipFile(overlay) as active:
            witness = Path(scratch) / 'CLAWVRModelTopology.dll'
            witness.write_bytes(b'witness')
            witness_pin = pin_file(witness)
            for sex in ('male', 'female'):
                for mode in ('static', 'fsmp'):
                    with self.subTest(sex=sex, mode=mode):
                        world, tri = (world_ear_path(sex, extension) for extension in ('.nif', '.tri'))
                        files = {name: static.read(name) for name in (PLUGIN, world, tri, resource_paths(sex, 1),
                                                                     resource_paths(sex))}
                        _, admission = equipped_trial(sex, occupied=True)
                        admission.update(mode=mode, archive=base_pin, witnessDll=witness_pin,
                                         mappedWitness=witness_pin | {'pid': admission['pid']})
                        if mode == 'fsmp':
                            files.update({name: active.read(name) for name in (world, motion_xml(sex))})
                            admission['motionArchive'] = overlay_pin
                        vfs = {name: pin_payload(data) for name, data in files.items()}
                        admission['effectiveVfs'] = vfs
                        self.assertEqual(admitted_assets(admission), (files[world], files[tri], tri))
                        wrong = vfs | {world: pin_payload((static if mode == 'fsmp' else active).read(world))}
                        with self.assertRaisesRegex(ValueError, 'loaded VFS'):
                            admitted_assets(admission | {'effectiveVfs': wrong})
                        if mode == 'static':
                            with self.assertRaisesRegex(ValueError, 'motion archive'):
                                admitted_assets(admission | {'motionArchive': overlay_pin})
                        else:
                            xml = motion_xml(sex)
                            other_xml = motion_xml('female' if sex == 'male' else 'male')
                            for bad_xml in (b'not XML', active.read(other_xml)):
                                repack = Path(scratch) / 'wrong-xml.zip'
                                with ZipFile(repack, 'w') as bad:
                                    for name in active.namelist():
                                        bad.writestr(name, bad_xml if name == xml else active.read(name))
                                with self.assertRaisesRegex(ValueError, 'authored rig for that sex'):
                                    admitted_assets(admission | {'motionArchive': pin_file(repack),
                                                                'effectiveVfs': vfs | {xml: pin_payload(bad_xml)}})
                            if sex == 'male':
                                repack = Path(scratch) / 'mislabeled.zip'
                                with ZipFile(repack, 'w') as bad:
                                    for name in active.namelist():
                                        member = static.read(world) if name == world else active.read(name)
                                        bad.writestr(name, member)
                                with self.assertRaisesRegex(ValueError, 'XML binding'):
                                    admitted_assets(admission | {'motionArchive': pin_file(repack), 'effectiveVfs': wrong})
                            del admission['motionArchive']
                            with self.assertRaisesRegex(ValueError, 'motion archive'):
                                admitted_assets(admission)


class EarMotionTests(unittest.TestCase):
    def setUp(self):
        self.spine = 'NPC Spine2 [Spn2]'
        bones = (HEAD_BONE, self.spine, *EAR_DRIVERS)
        count = 1354
        bind = SimpleNamespace(rotation=np.eye(3), scale=1, translation=(0, 0, 0))
        self.shape = SimpleNamespace(
            name=EAR_SHAPE, verts=[(i % 11, i % 3, i % 7) for i in range(count)],
            tris=[tuple((i + step) % count for step in range(3)) for i in range(2394)],
            bone_weights={bone: [(index, 1) for index in range(column, count, len(bones))]
                          for column, bone in enumerate(bones)},
            global_to_skin=bind, get_shape_skin_to_bone=lambda name: bind)
        self.records = {(EAR_SHAPE, 'CLAWHeadEarSize', 0): SimpleNamespace(packed=(1, 0, 0), scale=1)}
        self.baseline = {'earBones': {name: {'world': transform()} for name in bones},
                         'earEffectiveMorphs': {'CLAWHeadEarSize': .5}}

    def test_common_translation_rotation_and_scale_leave_head_relative_ears_fixed(self):
        moved = deepcopy(self.baseline)
        rigid = transform((20, 4, 9), [[0, -1, 0], [1, 0, 0], [0, 0, 1]], 1.5)
        for row in moved['earBones'].values():
            row['world'] = rigid
        moved['camera'] = transform((-10, 0, 14))
        result = ear_motion(self.shape, self.records, self.baseline, moved)
        self.assertGreater(result['worldDisplacementGu']['max'], 10)
        self.assertLess(result['headRelativeDisplacement']['max'], 1e-12)
        self.assertLess(result['earDriverContribution']['max'], 1e-12)

    def test_spine_and_ear_changes_are_separated_on_the_same_pose(self):
        moved = deepcopy(self.baseline)
        moved['earBones'][self.spine]['world'] = transform((0, 3, 0))
        moved['earBones'][EAR_DRIVERS[1]]['world'] = transform((0, 0, 2))
        result = ear_motion(self.shape, self.records, self.baseline, moved)
        self.assertEqual(result['vertices'], 1354)
        self.assertAlmostEqual(result['nonEarSkinContribution']['max'], 3)
        self.assertAlmostEqual(result['earDriverContribution']['max'], 2)
        self.assertAlmostEqual(result['headRelativeDisplacement']['max'], 3)
        moved['earEffectiveMorphs']['CLAWHeadEarSize'] = .6
        with self.assertRaisesRegex(ValueError, 'morphs changed'):
            ear_motion(self.shape, self.records, self.baseline, moved)


class StereoCalibrationTests(unittest.TestCase):
    def test_orthogonal_basis_holdout_and_bilateral_projection_controls(self):
        truth = np.eye(4)
        truth[:3, :3] = 70 * np.array([[0, 0, -1], [1, 0, 0], [0, -1, 0]])
        truth[:3, 3] = [10, 20, 30]
        game_hmd = np.eye(4)
        game_hmd[:3, 3] = [12, 18, 29]
        points = np.array([[0, 0, 0], [.1, 0, 0], [0, .2, 0], [0, 0, -.3]])

        def anchors(rows):
            return [{'providerHeadMeters': p.tolist(), 'worldGu': transform_points(truth, p).tolist()} for p in rows]

        holdout = anchors(points + [.08, .07, -.09])
        fit, scale, errors = calibrate_head(game_hmd, anchors(points), holdout)
        np.testing.assert_allclose(fit, truth, atol=1e-10)
        self.assertAlmostEqual(scale, 70)
        self.assertLess(errors['holdoutMaxErrorGu'], 1e-9)
        reply, expected = payload()
        _, eyes = admitted_sample(reply, expected, TRI)
        for eye in eyes:
            true_eye = np.eye(4)
            true_eye[:3] = eye['openVrEyeToHeadRows']
            eye_to_world = truth @ true_eye
            rays = dict(left=[-1, 0, -1], right=[1, 0, -1], bottom=[0, -1, -1], top=[0, 1, -1],
                        near=[0, 0, -.1], interior=[0, 0, -2])
            controls = {key: transform_points(eye_to_world, np.asarray(value)).tolist() for key, value in rays.items()}
            world_to_eye, planes = calibrated_eye(eye, controls, fit, scale)
            np.testing.assert_allclose(transform_points(world_to_eye, np.array(controls['interior'])), [0, 0, 2], atol=1e-10)
            self.assertAlmostEqual(planes['near'], .1)
            controls['left'], controls['right'] = controls['right'], controls['left']
            with self.assertRaisesRegex(ValueError, 'projected edge'):
                calibrated_eye(eye, controls, fit, scale)
        holdout[0]['worldGu'][0] += 1
        with self.assertRaisesRegex(ValueError, 'holdout tolerance'):
            calibrate_head(game_hmd, anchors(points), holdout)
        with self.assertRaisesRegex(ValueError, 'repeats'):
            calibrate_head(game_hmd, anchors(points), anchors(points))
