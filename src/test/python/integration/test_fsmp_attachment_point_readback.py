"""Portable kinematics and opt-in immutable v3 replay; no assets or live calls."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fsmp_attachment_point_readback as points
import test_fsmp_joint_limit_readback as fixtures
sys.path.append(str(Path(__file__).resolve().parents[4] / 'src/test/cpp/fsmp_step_witness'))
from test_validate_snapshot import fixture as witness_fixture

EVIDENCE_ENV = 'CLAW_FSMP_ATTACHMENT_POINT_EVIDENCE'
REQUIRED_ENV = 'CLAW_FSMP_ATTACHMENT_POINT_REQUIRED'
ARCHIVED_SHA256 = 'd742a7709ebee5aef07f53b449c704a50da0e601d765f10f9f397bf4679c8059'


def pose(frame=None, velocity=(0., 0., 0.), angular=(0., 0., 0.), *, dynamic=True):
    frame = frame or fixtures.transform()
    return {'world': frame['rotationRowMajor']+frame['translation'], 'rigidBody': True,
            'inverseMass': 20. if dynamic else 0., 'flags': 0 if dynamic else 2,
            'linearVelocity': list(velocity), 'angularVelocity': list(angular),
            'inverseLocalInertia': [10., 10., 10.] if dynamic else [0., 0., 0.]}


def symbolic_native():
    value = fixtures.symbolic_fixture(left=0., right=0.)
    associated = fixtures.associate(value)
    native = value['finalWitness']; native['schema'] = 'claw-fsmp-step-witness/3'
    window = native['sample']['objectWindow']; dt = window['lastTimeStep']
    window.update(schemaVersion=3, minimumPairedHostTimeStep=dt, summedPairedHostTimeStep=900*dt,
                  timeStepStatisticsScope=points.witness.HOST_DT_SCOPE)
    for row in window['objects']:
        stages = [row['initialPre'], row['lastPre'], row['lastPost']]
        if row['firstNonzeroPair']: stages += list(row['firstNonzeroPair'].values())
        for p in stages:
            p.update(linearVelocity=[0., 0., 0.], angularVelocity=[0., 0., 0.], inverseLocalInertia=[0., 0., 0.])
    parent, driver = [associated['A']['tokens'][name] for name in (points.joint.PARENTS[0], points.joint.DRIVERS[0])]
    rest = fixtures.transform((0., 1., 0.)); a = fixtures.transform(); b = fixtures.compose(a, rest)
    pairs = [({'pre': pose(a, (6., 0., 0.), dynamic=False), 'post': pose(fixtures.transform((.1, 0., 0.)), (6., 0., 0.), dynamic=False)}, parent),
             ({'pre': pose(b), 'post': pose(fixtures.compose(fixtures.transform((.07, 0., 0.)), rest), (4.2, 0., 0.))}, driver)]
    for pair, token in pairs:
        window['objects'][token-1].update(firstNonzeroStep=1, firstNonzeroPreQpc=window['firstPreQpc'],
            firstNonzeroPostQpc=window['firstPreQpc']+1, firstNonzeroPair=pair)
    envelope = witness_fixture(serial=1, count=900, qpc=window['lastPostQpc']+100)
    envelope['schema'] = 'claw-fsmp-step-witness/3'
    envelope['sample'].update(loadEpoch=window['loadEpoch'], objectWindow=window)
    return envelope, parent, driver, rest


def read_selected_actual():
    selected = os.environ.get(EVIDENCE_ENV)
    if not selected:
        if os.environ.get(REQUIRED_ENV) == '1': raise AssertionError('Required v3 attachment evidence not selected')
        raise unittest.SkipTest('Optional actual v3 attachment evidence not selected; set '+EVIDENCE_ENV)
    payload = Path(selected).expanduser().resolve(strict=True).read_bytes()
    if hashlib.sha256(payload).hexdigest() != ARCHIVED_SHA256:
        raise AssertionError('Explicit v3 attachment bundle hash differs; new evidence requires review')
    value = json.loads(payload)
    if value.get('schema') != 'claw-actual-v3-attachment-point-replay/1':
        raise AssertionError('Reviewed v3 attachment bundle required')
    return value


class PortablePointMath(unittest.TestCase):
    def test_angular_lever_velocity_is_not_com_velocity(self):
        rest = fixtures.transform((0., 1., 0.))
        result = points.attachment_state(pose(dynamic=False), pose(fixtures.transform((.08, 1., 0.)), angular=(0., 0., 2.)), rest)
        self.assertAlmostEqual(result['jointCoordinate'], .08)
        self.assertEqual(result['bodyPointTangentVelocity'], [2., 0., 0.])
        self.assertEqual(result['relativePointVelocityAxis'], 2.)
    def test_rotated_joint_axis_cannot_be_raw_world_x(self):
        anchor = fixtures.transform((10., 20., 30.), fixtures.YAW90)
        rest = fixtures.transform((0., 1., 0.))
        body = fixtures.compose(fixtures.compose(anchor, fixtures.transform((.08, 0., 0.))), rest)
        result = points.attachment_state(pose(anchor, dynamic=False), pose(body, angular=(0., 0., 2.)), rest)
        self.assertAlmostEqual(result['jointCoordinate'], .08)
        self.assertEqual(result['axis'], [0., 1., 0.])
        self.assertEqual(result['bodyPointVelocity'][0], 0.)
        self.assertEqual(result['relativePointVelocityAxis'], 2.)
    def test_nontrivial_rest_rotation_uses_inverse_rest_pivot(self):
        rest = fixtures.transform((0., 1., 0.), fixtures.YAW90)
        body = fixtures.compose(fixtures.transform((.2, 0., 0.)), rest)
        result = points.attachment_state(pose(dynamic=False), pose(body, angular=(0., 0., 3.)), rest)
        self.assertEqual(result['bodyPointOffset'], [0., -1., 0.])
        self.assertAlmostEqual(result['jointCoordinate'], .2)
        self.assertEqual(result['relativePointVelocityAxis'], 3.)
    def test_equal_linear_boost_cancels_and_input_is_unchanged(self):
        a, b = pose(dynamic=False), pose(fixtures.transform((.1, 1., 0.)), angular=(0., 0., 2.))
        rest = fixtures.transform((0., 1., 0.)); original = copy.deepcopy((a, b, rest))
        first = points.attachment_state(a, b, rest)
        self.assertEqual((a, b, rest), original)
        for p in (a, b): p['linearVelocity'] = [4., -2., 1.]
        self.assertEqual(points.attachment_state(a, b, rest)['relativePointVelocityAxis'], first['relativePointVelocityAxis'])
    def test_rotating_anchor_axis_derivative_is_separate(self):
        result = points.attachment_state(pose(angular=(0., 0., 1.), dynamic=False),
                                        pose(fixtures.transform((0., 2., 0.))), fixtures.transform())
        self.assertEqual(result['relativePointVelocityAxis'], 0.)
        self.assertEqual(result['axisRotationContribution'], 2.)
        self.assertEqual(result['coordinateDerivative'], 2.)
    def test_reuses_sole_v3_pose_validator_and_canonical_joint_frame(self):
        self.assertIs(points.witness, points.joint.witness)
        with patch.object(points.witness, 'pose', wraps=points.witness.pose) as checked:
            points.attachment_state(pose(dynamic=False), pose(), fixtures.transform())
            self.assertEqual(checked.call_count, 2)
            self.assertTrue(all(call.args[1] == 3 for call in checked.call_args_list))
    def test_missing_nonrigid_nonfinite_and_negative_inertia_refuse(self):
        for change in ('v2', 'nonrigid', 'nan', 'inertia'):
            p = pose()
            if change == 'v2': del p['linearVelocity']
            elif change == 'nonrigid':
                p['rigidBody'] = False
                for key in points.witness.DYNAMICS_FIELDS: p[key] = None
            elif change == 'nan': p['angularVelocity'][0] = float('nan')
            else: p['inverseLocalInertia'][0] = -1.
            with self.subTest(change=change), self.assertRaises(ValueError): points.attachment_state(pose(), p, fixtures.transform())
    def test_bad_unit_basis_scale_and_axis_refuse(self):
        for axis in (True, -1, 3):
            with self.assertRaises(ValueError): points.attachment_state(pose(), pose(), fixtures.transform(), axis)
        with self.assertRaises(ValueError): points.attachment_state(pose(), pose(), fixtures.transform(scale=2.))
        bad = pose(); bad['world'][0] = -1.
        with self.assertRaises(ValueError): points.attachment_state(bad, pose(), fixtures.transform())


class PortableOnset(unittest.TestCase):
    def test_conditional_lower_row_is_math_without_acceptance(self):
        native, a, b, rest = symbolic_native()
        result = points.analyze_first_pair(native, a, b, rest, lower_limit=-.15, fps=60., stop_erp=.2)
        self.assertAlmostEqual(result['conditionalLowerRow']['targetRelativeVelocity'], -1.8)
        self.assertAlmostEqual(result['conditionalLowerRow']['observedMinusTarget'], 0.)
        for key in ('dampingQualified', 'constraintParametersDirectlyObserved', 'solverFpsDirectlyObserved', 'integratedSimulationTimeProven'):
            self.assertIs(result[key], False)
    def test_object_onsets_must_match_step_and_both_qpcs(self):
        for key in ('firstNonzeroStep', 'firstNonzeroPreQpc', 'firstNonzeroPostQpc'):
            n, a, b, rest = symbolic_native(); n['sample']['objectWindow']['objects'][b-1][key] += 1
            with self.subTest(key=key), self.assertRaises(ValueError): points.analyze_first_pair(n, a, b, rest)
    def test_v2_missing_alias_and_bad_parameters_refuse(self):
        n, a, b, rest = symbolic_native()
        for tokens in ((a, a), (a, 999), (True, b)):
            with self.assertRaises(ValueError): points.analyze_first_pair(n, *tokens, rest)
        n['schema'] = 'claw-fsmp-step-witness/2'
        with self.assertRaises(ValueError): points.analyze_first_pair(n, a, b, rest)
        n, a, b, rest = symbolic_native()
        for values in ({'fps': 60.}, {'lower_limit': -.15, 'fps': 0., 'stop_erp': .2},
                       {'lower_limit': -.15, 'fps': 60., 'stop_erp': True}):
            with self.assertRaises(ValueError): points.analyze_first_pair(n, a, b, rest, **values)
    def test_conditional_comparison_refuses_rotating_parent(self):
        n, a, b, rest = symbolic_native()
        n['sample']['objectWindow']['objects'][a-1]['firstNonzeroPair']['post']['angularVelocity'][2] = 1.
        with self.assertRaisesRegex(ValueError, 'nonrotating'): points.analyze_first_pair(n, a, b, rest, lower_limit=-.15, fps=60., stop_erp=.2)
    def test_zero_angular_velocity_does_not_hide_a_discontinuous_axis_change(self):
        n, a, b, rest = symbolic_native()
        n['sample']['objectWindow']['objects'][a-1]['firstNonzeroPair']['post']['world'][:9] = fixtures.YAW90
        with self.assertRaisesRegex(ValueError, 'same observed axis'):
            points.analyze_first_pair(n, a, b, rest, lower_limit=-.15, fps=60., stop_erp=.2)


class ExplicitActualPointReplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.actual = read_selected_actual()
    def test_root_reviewed_pair_and_residual_recompute_without_mutation(self):
        a = self.actual; original = copy.deepcopy(a)
        with patch.object(points.joint.cached, 'module_admission', side_effect=AssertionError('Historical admission must not run')):
            result = points.analyze_first_pair(a['native'], a['parentToken'], a['driverToken'], a['restLocal'], **a['conditionalParameters'])
        e = a['expected']; self.assertEqual(result['pair'], e['pair'])
        self.assertAlmostEqual(result['pre']['relativePointVelocityAxis'], e['preRelativePointVelocity'], places=10)
        self.assertAlmostEqual(result['post']['relativePointVelocityAxis'], e['postRelativePointVelocity'], places=10)
        self.assertAlmostEqual(result['post']['bodyPointTangentVelocity'][1], e['postTangentY'], places=10)
        self.assertAlmostEqual(result['conditionalLowerRow']['observedMinusTarget'], e['conditionalResidual'], places=10)
        self.assertEqual(a, original); self.assertEqual(a['scope']['originalDampingResult'], 'failed')
        self.assertFalse(result['dampingQualified']); self.assertFalse(result['solverFpsDirectlyObserved'])
    def test_v3_host_statistics_and_observed_inertia_are_not_solver_time(self):
        a = self.actual; result = points.analyze_first_pair(a['native'], a['parentToken'], a['driverToken'], a['restLocal'])
        self.assertEqual(result['hostCallbackStatistics']['minimum'], a['expected']['hostMinimum'])
        self.assertEqual(result['hostCallbackStatistics']['sum'], a['expected']['hostSum'])
        self.assertFalse(result['integratedSimulationTimeProven'])
        obj = a['native']['sample']['objectWindow']['objects'][a['driverToken']-1]
        self.assertEqual(obj['firstNonzeroPair']['post']['inverseLocalInertia'], [10., 10., 10.])
    def test_actual_corruption_cannot_splice_a_different_onset(self):
        a = copy.deepcopy(self.actual)
        a['native']['sample']['objectWindow']['objects'][a['parentToken']-1]['firstNonzeroStep'] += 1
        with self.assertRaises(ValueError): points.analyze_first_pair(a['native'], a['parentToken'], a['driverToken'], a['restLocal'])


class SelectionContract(unittest.TestCase):
    def test_unset_is_visible_skip_and_required_selection_fails(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(unittest.SkipTest): read_selected_actual()
            os.environ[REQUIRED_ENV] = '1'
            with self.assertRaises(AssertionError): read_selected_actual()
    def test_explicit_missing_or_hash_changed_input_fails(self):
        target = Path(__file__).resolve().parents[4] / 'target'; target.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=target) as directory:
            path = Path(directory)/'selected.json'
            with patch.dict(os.environ, {EVIDENCE_ENV: str(path)}, clear=True):
                with self.assertRaises(FileNotFoundError): read_selected_actual()
                path.write_text('{}', encoding='utf-8')
                with self.assertRaisesRegex(AssertionError, 'hash differs'): read_selected_actual()


if __name__ == '__main__': unittest.main(verbosity=2)
