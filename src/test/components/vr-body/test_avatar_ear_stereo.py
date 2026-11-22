"""Reject stale stereo evidence and exercise independent optics controls."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

import numpy as np

from avatar_ear_stereo import (ADDON, BASE, CAPTURE_SCHEMA, CELL, EAR_SHAPE, ITEM, LEGACY_ALIAS, PLAYER, RACE,
                               RUN_SCHEMA, admitted_assets, admitted_sample, read_reply)
from stereo_calibration import calibrate_head, calibrated_eye, transform_points

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
        def pin(path):
            data = path.read_bytes()
            return {'path': str(path), 'sha256': sha256(data).hexdigest(), 'bytes': len(data)}

        with TemporaryDirectory() as scratch:
            root = Path(scratch)
            witness = root / 'CLAWVRModelTopology.dll'
            witness.write_bytes(b'witness')
            archive = root / 'ears.zip'
            tri = 'Meshes/Actors/WerewolfBeast/CLAW/FirstPerson/female/EarWorldTrial.tri'
            members = {LEGACY_ALIAS: b'ear mesh', tri: b'trial TRI'}
            with ZipFile(archive, 'w') as dest:
                for name, data in members.items():
                    dest.writestr(name, data)
            vfs = {name: {'bytes': len(data), 'sha256': sha256(data).hexdigest()} for name, data in members.items()}
            admission = {'schema': RUN_SCHEMA, 'pid': 492, 'sex': 'female', 'mode': 'static', 'archive': pin(archive),
                         'effectiveVfs': vfs, 'witnessDll': pin(witness), 'mappedWitness': pin(witness) | {'pid': 492}}
            self.assertEqual(admitted_assets(admission), (b'ear mesh', b'trial TRI', tri))
            vfs[tri]['sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'loaded VFS'):
                admitted_assets(admission)


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
