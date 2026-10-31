"""Regression for the empty-alias chain failure and refusal of used aliases."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str((Path(__file__).resolve().parents[4] / 'src/main/python/vr')))
from rig_lookup import LEFT_ARM, alias_plan, renamed_graph, trace_left_arm


class RigLookupTests(unittest.TestCase):
    def fixture(self):
        parents = {'NPC Spine2 [Spn2]': None}
        last = 'NPC Spine2 [Spn2]'
        for preferred, beast in LEFT_ARM:
            parents[beast], parents[preferred] = last, beast
            last = beast
        return parents, {LEFT_ARM[-1][1]: 100}

    def test_empty_alias_breaks_hierarchical_lookup_and_names_only_fix_restores_it(self):
        parents, weights = self.fixture()
        self.assertEqual(LEFT_ARM[0][0], trace_left_arm(parents)[0]['selected'])
        self.assertIsNone(trace_left_arm(parents)[1]['selected'])
        plan = alias_plan(parents, weights)
        repaired = renamed_graph(parents, plan)
        self.assertEqual([b for _, b in LEFT_ARM], [row['selected'] for row in trace_left_arm(repaired)])
        self.assertEqual(len(parents), len(repaired))
        self.assertEqual(4, len(plan))

    def test_weighted_alias_refused(self):
        parents, weights = self.fixture()
        weights[LEFT_ARM[0][0]] = 1
        with self.assertRaisesRegex(ValueError, 'weighted or non-leaf'):
            alias_plan(parents, weights)

    def test_nonleaf_or_reparented_alias_refused(self):
        for mode in ('child', 'reparent'):
            parents, weights = self.fixture()
            if mode == 'child':
                parents['attachment'] = LEFT_ARM[0][0]
            else:
                parents[LEFT_ARM[0][0]] = 'NPC Spine2 [Spn2]'
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                alias_plan(parents, weights)

    def test_incomplete_graph_and_missing_weighted_bone_refused(self):
        parents, weights = self.fixture()
        parents[LEFT_ARM[0][1]] = 'missing'
        with self.assertRaises(ValueError):
            alias_plan(parents, weights)
        parents, weights = self.fixture()
        weights['missing'] = 1
        with self.assertRaises(ValueError):
            alias_plan(parents, weights)
        parents, weights = self.fixture()
        parents['NPC Spine2 [Spn2]'] = LEFT_ARM[-1][1]
        with self.assertRaisesRegex(ValueError, 'Cyclic'):
            alias_plan(parents, weights)


if __name__ == '__main__':
    unittest.main()
