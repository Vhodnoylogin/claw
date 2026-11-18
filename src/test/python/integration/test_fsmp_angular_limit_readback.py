"""Portable angular math/discrimination; symbolic fixtures are never game evidence."""
from pathlib import Path
import copy
import math
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fsmp_angular_limit_readback as angular
import test_fsmp_joint_limit_readback as fixtures


def rx(value):
    return [1., 0., 0., 0., math.cos(value), -math.sin(value), 0., math.sin(value), math.cos(value)]


def associate(value):
    return angular.pair(value['worldA'], value['worldB'], value['witnessA'], value['witnessB'],
                        reference=value.get('reference', fixtures.REFERENCE), base=value.get('base', fixtures.BASE),
                        rest_local=value['restLocal'], expected_inverse_mass=dict.fromkeys(angular.DRIVERS, 20.))


def set_driver_angle(value, driver, angle, *, stages=angular.STAGES, final_only=False):
    """Independent forward fixture/corruption; includes the rotated rest pivot.

    Positive Bullet x deliberately uses ordinary Rx(-angle). Keep all typed
    envelopes from the shared portable fixture instead of forking a capture.
    """
    associated = associate(value)
    tokens = associated['A']['tokens']
    parent = angular.PARENTS[angular.DRIVERS.index(driver)]
    names = ('finalWitness',) if final_only else ('witnessA', 'witnessB', 'finalWitness')
    for name in names:
        objects = {item['token']: item for item in value[name]['sample']['objectWindow']['objects']}
        obj = objects[tokens[driver]]
        for stage in stages:
            p = objects[tokens[parent]][stage]['world']
            frame = fixtures.compose(fixtures.compose(fixtures.transform(p[9:], p[:9]),
                                     fixtures.transform(rotation=rx(-angle))), value['restLocal'][driver])
            obj[stage]['world'] = frame['rotationRowMajor'] + frame['translation']
        poses = [obj[stage]['world'] for stage in angular.STAGES]
        obj['minimumPostWorld'] = [min(p[i] for p in poses) for i in range(12)]
        obj['maximumPostWorld'] = [max(p[i] for p in poses) for i in range(12)]
        if name in ('witnessA', 'witnessB'):
            raw = value['worldA' if name == 'witnessA' else 'worldB']
            frame = obj['lastPost']['world']
            next(node for node in raw['nodes'] if node['name'] == driver)['world'] = fixtures.transform(frame[9:], frame[:9])


def symbolic_fixture(left=.005, right=0.):
    value = fixtures.symbolic_fixture(left=0., right=0.)
    for native in ('witnessA', 'witnessB', 'finalWitness'):
        value[native]['sample'].update(mainFreezeNextFrame=False, engineMultiplier=1., timerPauseCount=0)
    set_driver_angle(value, angular.DRIVERS[0], left)
    set_driver_angle(value, angular.DRIVERS[1], right)
    return value


def score(value):
    return angular.score_case(associate(value), value['finalWitness'], value['restLocal'],
                              native_a=value['witnessA'], native_b=value['witnessB'])


class PortableAngularMath(unittest.TestCase):
    def test_bullet_x_sign_is_opposite_ordinary_rx(self):
        self.assertAlmostEqual(angular.euler_xyz(rx(-.005))[0], .005, places=12)
        self.assertAlmostEqual(angular.euler_xyz(rx(.005))[0], -.005, places=12)
    def test_rotated_anchor_and_pivot_use_joint_frame(self):
        parent = fixtures.transform((10., 20., 30.), fixtures.YAW90)
        rest = fixtures.transform((0., 1., 0.))
        body = fixtures.compose(fixtures.compose(parent, fixtures.transform(rotation=rx(-.005))), rest)
        joint = angular.joint_frame(parent, body, rest)
        self.assertAlmostEqual(angular.euler_xyz(joint['rotationRowMajor'])[0], .005, places=12)
        self.assertGreater(abs(angular.euler_xyz(body['rotationRowMajor'])[2]), 1.)
        self.assertLess(max(abs(v) for v in joint['translation']), 1e-12)
        self.assertGreater(abs(body['translation'][2]-parent['translation'][2]), .0049)
    def test_invalid_unit_basis_and_regime_refused(self):
        with self.assertRaisesRegex(ValueError, 'unit'):
            angular.joint_frame(fixtures.transform(scale=2.), fixtures.transform(), fixtures.transform())
        for kind in ('reflection', 'nonfinite', 'nonorthogonal', 'regime'):
            r = fixtures.IDENTITY[:]
            if kind == 'reflection':r[0] = -1.
            elif kind == 'nonfinite':r[0] = float('nan')
            elif kind == 'nonorthogonal':r[0] = 1.1
            else:r = [math.cos(.03), 0., math.sin(.03), 0., 1., 0., -math.sin(.03), 0., math.cos(.03)]
            with self.subTest(kind=kind), self.assertRaises(ValueError):angular.euler_xyz(r)
    def test_reuses_canonical_pair_frame_and_validator(self):
        self.assertIs(angular.pair, fixtures.joint.pair)
        self.assertIs(angular.joint_frame, fixtures.joint.joint_frame)
        self.assertIs(angular.witness, fixtures.joint.witness)


class PortableAngularDiscrimination(unittest.TestCase):
    def test_symbolic_complete_positive_is_only_a_scorer_test(self):
        value = symbolic_fixture();before = copy.deepcopy(value)
        result = score(value)
        self.assertEqual(result['units'], 'radians')
        self.assertEqual(result['leftTarget'], .005)
        self.assertEqual(value, before)
    def test_zero_wrong_sign_degrees_and_right_control_refused(self):
        for left, right in ((0., 0.), (-.005, 0.), (math.degrees(.005), 0.), (.005, .005)):
            with self.subTest(left=left, right=right), self.assertRaises(ValueError):score(symbolic_fixture(left, right))
    def test_bilateral_angular_drift_inside_endpoints_refused(self):
        for driver in angular.DRIVERS:
            initial = .005-.00009 if driver == angular.DRIVERS[0] else -.00009
            final = .005+.00009 if driver == angular.DRIVERS[0] else .00009
            value = symbolic_fixture(left=initial if driver == angular.DRIVERS[0] else .005,
                                     right=initial if driver == angular.DRIVERS[1] else 0.)
            set_driver_angle(value, driver, final, stages=('lastPre', 'lastPost'), final_only=True)
            with self.subTest(driver=driver), self.assertRaisesRegex(ValueError, 'angular window was not settled'):score(value)
    def test_same900_window_and_normal_clock_required(self):
        for kind in ('nonce', 'pairs', 'pause', 'nextFrame', 'multiplier'):
            value = symbolic_fixture();sample = value['finalWitness']['sample']
            if kind == 'nonce':sample['objectWindow']['nonce'] += 1
            elif kind == 'pairs':sample['objectWindow'].update(status='collecting', pairedSteps=899)
            elif kind == 'pause':sample['mainFreezeTime'] = True
            elif kind == 'nextFrame':sample['mainFreezeNextFrame'] = True
            else:sample['engineMultiplier'] = .5
            with self.subTest(kind=kind), self.assertRaises(ValueError):score(value)


if __name__ == '__main__':unittest.main()
