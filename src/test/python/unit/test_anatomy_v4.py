"""Separate arm mechanisms and the bounded abdomen/thigh metric contract."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[4]/'src/main/python/build-tools'))
import expressive_body as body
import body_clearance as contact


class AnatomyV4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recipe = json.loads((body.ROOT/'src/main/resources/recipes/expressive-body-v4.json').read_text())
        cls.p = cls.recipe['parameters']

    def test_biceps_and_triceps_are_opposite_local_channels(self):
        v = np.array([[33., 15., 98.], [33., 1., 98.], [22., 14., 106.], [52., 20., 84.]])
        fields = body.fields(v, 'body', self.p)
        self.assertGreater(np.linalg.norm(fields['CLAWArmBiceps'][0]), 4)
        self.assertGreater(np.linalg.norm(fields['CLAWArmTriceps'][1]), 4)
        self.assertLess(np.linalg.norm(fields['CLAWArmTriceps'][0]), .5)
        self.assertLess(np.linalg.norm(fields['CLAWArmBiceps'][1]), .5)
        for name in body.ARM_MUSCLES:
            np.testing.assert_array_equal(fields[name][2:], np.zeros((2, 3)))
            np.testing.assert_array_equal(fields[name][:, 0], np.zeros(4))

    def test_soft_girth_reduces_radial_ridge_contrast_without_becoming_lean(self):
        v = np.array([[33., 18., 96.], [33., 22., 96.]])
        field = body.fields(v, 'body', self.p)['CLAWArmGirth']
        self.assertTrue(np.all(field[:, 1]>0))
        self.assertGreater(field[0, 1], field[1, 1])
        self.assertLess((v+field)[1, 1]-(v+field)[0, 1], v[1, 1]-v[0, 1])

    def test_belly_ownership_excludes_thigh_skin_and_keeps_abdomen(self):
        shape = SimpleNamespace(verts=np.zeros((4, 3)), bone_weights={
            'NPC L Thigh [LThg]': [(0, 0), (1, .2), (2, .65), (3, 1.)]})
        mask = body.belly_anatomical_mask(shape, self.p['bellyAnatomy'])
        self.assertEqual(mask[0], 1)
        self.assertTrue(0<mask[1]<1)
        np.testing.assert_array_equal(mask[2:], [0, 0])

    def test_upper_abdominal_prominence_is_retained_at_the_hip_crease(self):
        z = np.linspace(53, 108, 1101)
        v = np.c_[np.zeros(len(z)), np.full(len(z), 15.), z]
        field = body.fields(v, 'body', self.p)['CLAWTorsoBellyRound']
        self.assertGreater(field[:, 1].max(), 17.99)
        np.testing.assert_array_equal(field[z<=65], np.zeros_like(field[z<=65]))


class TriangleClearanceTests(unittest.TestCase):
    def setUp(self):
        self.a = np.array([[0., 0., 0.], [2., 0., 0.], [0., 2., 0.]])

    def test_real_piercing_is_distinct_from_normal_orientation(self):
        b = np.array([[.5, .5, -1.], [.5, .5, 1.], [1.5, .5, 1.]])
        distance, proper = contact.triangle_distance(self.a, b)
        self.assertTrue(proper)
        self.assertEqual(distance, 0)

    def test_disjoint_parallel_and_coplanar_distances(self):
        distance, proper = contact.triangle_distance(self.a, self.a+[0, 0, 1.75])
        self.assertFalse(proper)
        self.assertAlmostEqual(distance, 1.75)
        distance, proper = contact.triangle_distance(self.a, self.a+[3, 0, 0])
        self.assertFalse(proper)
        self.assertAlmostEqual(distance, 1.)

    def test_uv_split_adjacent_corners_are_excluded(self):
        v = np.r_[self.a, self.a+[0, 0, .1]]
        f = np.array([[0, 1, 2], [3, 4, 5]])
        frozen = (np.array([0]), np.array([1]), np.array([[0, 1, 2], [0, 4, 5]]))
        row = contact.clearance(v, f, frozen)
        self.assertEqual(row['properCrossingCount'], 0)
        self.assertEqual(row['broadPhasePairs'], 0)

    def test_observed_alias_parent_is_recovered_from_child_local(self):
        root, alias, local = np.eye(4), np.eye(4), np.eye(4)
        root[:3, 3] = [10, 20, 30]
        alias[:3, 3] = [1, 2, 3]
        local[:3, 3] = [0, 0, 5]
        def observed(m):
            return {'rotationRowMajor': m[:3, :3].reshape(-1).tolist(), 'translation': m[:3, 3].tolist(), 'scale': 1.}
        name = 'NPC R Thigh [RThg]'
        snapshot = {'refs': [{'identity': {'form': '0x123'}, 'sceneTransform': observed(root)}],
                    'nodes': [{'form': '0x123', 'name': name, 'status': 'available',
                               'world': observed(root@alias@local), 'local': observed(local)}]}
        rest = {'root': np.eye(4), 'NPC R Thigh [LThg]': alias, name: alias@local}
        parents = {'root': None, 'NPC R Thigh [LThg]': 'root', name: 'NPC R Thigh [LThg]'}
        posed, _ = contact.actual_pose(snapshot, '0x123', rest, parents)
        np.testing.assert_allclose(posed['NPC R Thigh [LThg]'], alias)


if __name__ == '__main__':
    unittest.main()
