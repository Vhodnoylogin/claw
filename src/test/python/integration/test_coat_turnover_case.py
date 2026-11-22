"""Offline discrimination controls for the eventual SE result packet."""

import unittest

import coat_turnover_case as plan
from test_coat_turnover_readback import case


def retained_fixture():
    observations, expected = case()
    del expected['foreign_body_path']
    phases = {
        'baseline': (plan.BODY_A, plan.HEAD_A), 'foreign': (plan.BODY_A, plan.HEAD_A),
        'sibling': (plan.BODY_A, plan.HEAD_B), 'recovered': (plan.BODY_B, plan.HEAD_B),
    }
    data = {
        plan.SAMPLE_NAMES[phase]: {
            'fixture': {'skin': plan.form(plan.SKIN), 'fixedAddon': plan.form(plan.REST),
                        'bodyWorn': plan.form(body), 'headWorn': plan.form(head)},
            'coat': observations[phase],
        }
        for phase, (body, head) in phases.items()
    }
    baseline = observations['baseline']
    ref = baseline['reference']
    creation = 'b59031f9b7be453897895140f186b07c'
    base = '0x0D000800'
    fixture = {
        'status': 'created', 'runId': baseline['runId'], 'reference': ref, 'createdReference': ref,
        'base': base, 'creationId': creation, 'worldGeneration': baseline['worldGeneration'],
        'game': {'pid': baseline['pid']}, 'incarnation': {'runtimeHandle': baseline['runtimeHandle']},
        'creationWitness': {'runId': baseline['runId'], 'creationId': creation, 'reference': ref, 'base': base,
                            'nativeReturned': True, 'forcePersist': False, 'count': 1},
    }
    checks = [{'name': check['name'], 'result': 'passed', 'observation': data.get(check['name'], {})}
              for check in plan.prepare()['testing']['checks']]
    return ({'id': baseline['runId'], 'result': 'passed', 'restored': True, 'restoreErrors': [],
             'collectionComplete': True, 'collectionErrors': [], 'checks': checks,
             'interactiveActorFixtures': {plan.TAG: fixture}}, expected)


class TurnoverCaseTests(unittest.TestCase):
    def test_boundary_and_single_mutations_are_declared(self):
        prepared = plan.prepare()
        steps = prepared['subjectPlan']['steps']
        self.assertEqual(prepared['testing']['start'], {'kind': 'check', 'name': 'coat-baseline'})
        self.assertEqual([s['name'] for s in steps], [s['name'] for s in prepared['testing']['checks']])
        self.assertEqual(len({s['name'] for s in steps}), len(steps))
        self.assertFalse(any(s.get('poll') for s in steps if s['operation'] == 'object.perform'))
        self.assertEqual([s['name'] for s in steps if s.get('parameters', {}).get('request', {}).get('action') == 'equip'],
                         ['equip-body-a', 'equip-head-a', 'equip-head-b', 'equip-body-b'])

    def test_pass_requires_actual_coat_and_worn_forms(self):
        result, expected = retained_fixture()
        self.assertEqual(plan.verify_run(result, **expected)['replacedGeometry'], {'head': '14', 'body': '15'})
        sibling = next(row for row in result['checks'] if row['name'] == 'coat-sibling')
        sibling['observation']['fixture']['headWorn'] = plan.form(plan.HEAD_A)
        with self.assertRaisesRegex(ValueError, 'worn form differs'):
            plan.verify_run(result, **expected)

    def test_historical_or_foreign_actor_cannot_supply_an_audit(self):
        result, expected = retained_fixture()
        for row in result['checks']:
            if 'coat' in row['observation']:
                row['observation']['coat']['reference'] = '0xFF001111'
        with self.assertRaisesRegex(ValueError, 'owned game attempt'):
            plan.verify_run(result, **expected)
        result['interactiveActorFixtures'] = {}
        with self.assertRaisesRegex(ValueError, 'owned creation record'):
            plan.verify_run(result, **expected)

    def test_incomplete_collection_or_changed_step_order_is_rejected(self):
        result, expected = retained_fixture()
        result['checks'].reverse()
        with self.assertRaisesRegex(ValueError, 'reordered'):
            plan.verify_run(result, **expected)
        result['collectionComplete'] = False
        with self.assertRaisesRegex(ValueError, 'restored attempt'):
            plan.verify_run(result, **expected)


if __name__ == '__main__':
    unittest.main()
