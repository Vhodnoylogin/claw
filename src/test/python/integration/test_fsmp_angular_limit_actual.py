"""Optional explicit immutable angular replay; portable fixtures stay separate."""
from pathlib import Path
import copy
import hashlib
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fsmp_angular_limit_readback as angular
from test_fsmp_angular_limit_readback import associate, score, set_driver_angle

EVIDENCE_ENV = 'CLAW_FSMP_ANGULAR_LIMIT_READBACK_EVIDENCE'
REQUIRED_ENV = 'CLAW_FSMP_ANGULAR_LIMIT_READBACK_REQUIRED'
ARCHIVED_EVIDENCE_SHA256 = '218264a5acacaa09c64f3dbbfd2c0ace5e2255e2614bc189005dd56e79a65dc6'


def read_selected_actual():
    selected = os.environ.get(EVIDENCE_ENV)
    if not selected:
        if os.environ.get(REQUIRED_ENV) == '1':
            raise AssertionError('Required actual angular-limit evidence missing: set ' + EVIDENCE_ENV)
        raise unittest.SkipTest('Optional actual angular-limit proof not selected; set ' + EVIDENCE_ENV)
    payload = Path(selected).expanduser().resolve(strict=True).read_bytes()
    if hashlib.sha256(payload).hexdigest() != ARCHIVED_EVIDENCE_SHA256:
        raise AssertionError('Explicit actual angular-limit proof hash differs; new evidence requires review')
    actual = json.loads(payload)
    if actual.get('schema') != 'claw-actual-angular-limit-replay/1' or not {
            'rawPair', 'finalWitness', 'restLocal', 'reference', 'base', 'sourceRun'} <= set(actual):
        raise AssertionError('Complete reviewed actual angular-limit bundle required')
    if not {'worldA', 'worldB', 'witnessA', 'witnessB', 'matches', 'limitResult'} <= set(actual['rawPair']):
        raise AssertionError('Complete actual angular paused pair required')
    return actual


def prepared(actual):
    return {**actual['rawPair'], **{key: actual[key] for key in ('finalWitness', 'restLocal', 'reference', 'base')}}


class ExplicitActualAngularLimitReadback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.actual = read_selected_actual()
    def test_actual_paused_and_completed900_replay(self):
        value = prepared(self.actual)
        with patch.object(angular.cached, 'module_admission', side_effect=AssertionError('Historical admission must not run')):
            associated = associate(value)
            self.assertEqual(associated, self.actual['rawPair']['matches'])
            self.assertEqual(angular.score_limit(associated, value['witnessA'], value['witnessB'], value['restLocal']),
                             self.actual['rawPair']['limitResult'])
            result = score(value)
        self.assertEqual(result['units'], 'radians')
        self.assertEqual(result['rotationOrder'], 'Bullet RO_XYZ')
        for stage in angular.STAGES:
            angles = result['completed900AngularCoordinates']['anglesRadians'][stage]
            self.assertAlmostEqual(angles[angular.DRIVERS[0]][0], .005, delta=.0001)
            self.assertAlmostEqual(angles[angular.DRIVERS[1]][0], 0., delta=.0001)
        self.assertEqual(value['finalWitness']['sample']['objectWindow']['pairedSteps'], 900)
    def test_zero_and_opposite_sign_corruption_cannot_become_angular_positive(self):
        for value in (0., -.005):
            corrupted = prepared(copy.deepcopy(self.actual))
            set_driver_angle(corrupted, angular.DRIVERS[0], value)
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'Left positive angular'):score(corrupted)
    def test_actual_right_drift_inside_endpoint_gate_refused(self):
        value = prepared(copy.deepcopy(self.actual))
        set_driver_angle(value, angular.DRIVERS[1], .000095, stages=('lastPre', 'lastPost'), final_only=True)
        with self.assertRaisesRegex(ValueError, 'angular window was not settled'):score(value)
    def test_actual_mass_and_stale_observation_corruptions_refused(self):
        for kind in ('mass', 'clock', 'pid'):
            value = prepared(copy.deepcopy(self.actual))
            if kind == 'mass':
                token = value['matches']['A']['tokens'][angular.DRIVERS[0]]
                for native in ('witnessA', 'witnessB'):
                    obj = next(item for item in value[native]['sample']['objectWindow']['objects'] if item['token'] == token)
                    for stage in angular.STAGES:obj[stage]['inverseMass'] = 10.
            elif kind == 'clock':value['worldB']['sampleId'] = value['worldA']['sampleId']
            else:value['witnessB']['pid'] += 1
            with self.subTest(kind=kind), self.assertRaises(ValueError):score(value)


class ExplicitAngularSelectionContract(unittest.TestCase):
    def test_unset_optional_skips_and_required_unset_fails(self):
        for required, error in (('', unittest.SkipTest), ('1', AssertionError)):
            with self.subTest(required=required), patch.dict(os.environ, {EVIDENCE_ENV: '', REQUIRED_ENV: required}), self.assertRaises(error):
                read_selected_actual()
    def test_selected_missing_or_wrong_digest_fails(self):
        target = Path(__file__).resolve().parents[4]/'target/test-inputs/fsmp-angular-limit'
        target.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='selection-', dir=target) as folder:
            missing = Path(folder)/'missing.json'
            with patch.dict(os.environ, {EVIDENCE_ENV: str(missing)}), self.assertRaises(FileNotFoundError):read_selected_actual()
            damaged = Path(folder)/'damaged.json';damaged.write_text('{}', encoding='utf-8')
            with patch.dict(os.environ, {EVIDENCE_ENV: str(damaged)}), self.assertRaisesRegex(AssertionError, 'hash differs'):read_selected_actual()


if __name__ == '__main__':unittest.main()
