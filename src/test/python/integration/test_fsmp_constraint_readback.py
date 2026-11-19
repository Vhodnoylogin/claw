"""Asset-free target binding/corruption controls, not game observations."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fsmp_constraint_readback as readback
sys.path.append(str(Path(__file__).resolve().parents[4] / 'src/test/cpp/fsmp_step_witness'))
from test_validate_snapshot import fixture, v3_window


def parameters(damping):
    return {'lowerLimit': [-.15]*6, 'upperLimit': [.15]*6,
            'springEnabled': [True]*6, 'stiffness': [40.]*6,
            'damping': [damping, .4, .4, .4, .4, .4], 'stopERP': [.2]*6,
            'stiffnessLimited': [True]*6, 'dampingLimited': [True]*6}


def symbolic():
    native = fixture(count=900, qpc=3100)
    native['schema'] = 'claw-fsmp-step-witness/4'
    window = v3_window()
    window['schemaVersion'] = 4
    original = window['objects'][0]
    window['objects'] = [dict(copy.deepcopy(original), token=token) for token in range(1, 5)]
    window['objectCount'] = 4
    expected = {name: parameters(damping) for name, damping in zip(readback.joint.DRIVERS, (0., .4))}
    rows = [{'token': token, 'bodyAToken': parent, 'bodyBToken': driver, 'type': 12,
             'enabled': True, 'status': 'spring2', 'spring2': copy.deepcopy(expected[name])}
            for token, parent, driver, name in ((1, 1, 2, readback.joint.DRIVERS[0]),
                                                (2, 3, 4, readback.joint.DRIVERS[1]))]
    window['incidentConstraints'] = {'status': 'observed',
        'scope': 'initial-pre configuration; identical at every captured callback',
        'axisOrder': 'linear xyz; angular xyz', 'perBodyReferenceLimit': 64,
        'uniqueConstraintCapacity': 256, 'constraintCount': 2, 'failureCode': 0, 'constraints': rows}
    native['sample']['objectWindow'] = window
    tokens = dict(zip((readback.joint.PARENTS[0], readback.joint.DRIVERS[0],
                       readback.joint.PARENTS[1], readback.joint.DRIVERS[1]), range(1, 5)))
    associated = {'pid': native['pid'], 'loadEpoch': window['loadEpoch'], 'nonce': window['nonce'],
                  'A': {'tokens': tokens}, 'B': {'tokens': dict(tokens)}}
    return associated, native, expected


class TargetConstraintTests(unittest.TestCase):
    def test_bilateral_values_and_float32_decimal_expectations(self):
        a, n, e = symbolic()
        for row in n['sample']['objectWindow']['incidentConstraints']['constraints']:
            for field in readback.PARAMETERS - readback.BOOLEAN_PARAMETERS:
                row['spring2'][field] = [readback.struct.unpack('<f', readback.struct.pack('<f', v))[0]
                                         for v in row['spring2'][field]]
        self.assertEqual(readback.verify_parameters(a, n, e)['status'],
                         'configured-target-spring2-values-observed')

    def test_unrelated_unsupported_type_does_not_fabricate_or_hide_target_values(self):
        a, n, e = symbolic()
        incident = n['sample']['objectWindow']['incidentConstraints']
        incident.update(status='unsupported', constraintCount=3)
        incident['constraints'].append({'token': 3, 'bodyAToken': 1, 'bodyBToken': 4, 'type': 3,
                                       'enabled': True, 'status': 'unsupported_type', 'spring2': None})
        self.assertEqual(len(readback.verify_parameters(a, n, e)['targets']), 2)

    def test_wrong_axis_or_coefficient_is_refused(self):
        for field in ('damping', 'stiffness', 'lowerLimit', 'upperLimit', 'stopERP'):
            a, n, e = symbolic()
            e[readback.joint.DRIVERS[0]][field][1] += .1
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, field):
                readback.verify_parameters(a, n, e)

    def test_missing_reversed_duplicate_and_disabled_target_are_refused(self):
        for kind in ('missing', 'reverse', 'duplicate', 'disabled'):
            a, n, e = symbolic()
            incident = n['sample']['objectWindow']['incidentConstraints']
            rows = incident['constraints']
            if kind == 'missing':
                rows.pop(); incident['constraintCount'] = 1
            elif kind == 'reverse':
                rows[0]['bodyAToken'], rows[0]['bodyBToken'] = rows[0]['bodyBToken'], rows[0]['bodyAToken']
            elif kind == 'duplicate':
                rows.append(dict(copy.deepcopy(rows[0]), token=3)); incident['constraintCount'] = 3
            else:
                rows[0]['enabled'] = False
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                readback.verify_parameters(a, n, e)

    def test_stale_process_epoch_nonce_and_role_mapping_are_refused(self):
        for field in ('pid', 'loadEpoch', 'nonce', 'tokens'):
            a, n, e = symbolic()
            if field == 'tokens': a['B']['tokens'][readback.joint.DRIVERS[0]] = 4
            else: a[field] += 1
            with self.subTest(field=field), self.assertRaises(ValueError):
                readback.verify_parameters(a, n, e)

    def test_legacy_observation_cannot_supply_missing_constraint_values(self):
        a, n, e = symbolic(); n['schema'] = 'claw-fsmp-step-witness/3'
        with self.assertRaisesRegex(ValueError, 'schema4'):
            readback.verify_parameters(a, n, e)

    def test_float_and_boolean_role_aliases_are_refused(self):
        for sides in (('A', 'B'), ('A',), ('B',)):
            for token in (1., True, 0, 5):
                a, n, e = symbolic()
                for side in sides:
                    a[side]['tokens'][readback.joint.PARENTS[0]] = token
                with self.subTest(sides=sides, token=token), self.assertRaisesRegex(ValueError, 'integer role'):
                    readback.verify_parameters(a, n, e)

    def test_expectations_must_not_omit_axes_or_accept_boolean_numbers(self):
        for kind in ('field', 'axis', 'bool', 'infinite'):
            a, n, e = symbolic(); wanted = e[readback.joint.DRIVERS[0]]
            if kind == 'field': del wanted['stopERP']
            elif kind == 'axis': wanted['damping'].pop()
            elif kind == 'bool': wanted['damping'][0] = False
            else: wanted['damping'][0] = float('inf')
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                readback.verify_parameters(a, n, e)


if __name__ == '__main__':
    unittest.main()
