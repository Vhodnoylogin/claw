"""Independent mathematical checks for the read-only head-motion diagnostic."""
from pathlib import Path
import sys
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'src/main/python/build-tools'))
import vr_head as vr
import breast_rig as rig


class HeadPoseTests(unittest.TestCase):
    def test_descendants_include_actual_chain_not_name_substrings(self):
        parents = {'Root': None, vr.HEAD: 'Root', 'Ear': vr.HEAD, 'TorsoHeadNamed': 'Root'}
        self.assertEqual(vr.descendants(parents, vr.HEAD), {vr.HEAD, 'Ear'})
        with self.assertRaises(ValueError):
            vr.descendants({'Root': None, vr.HEAD: 'bad'}, vr.HEAD)

    def test_head_only_pose_keeps_spine_with_nonidentity_parent_scale(self):
        root = rig.rotation(1, 20); root[:3, :3] *= 1.25; root[:3, 3] = [4, 5, 6]
        local = np.eye(4); local[:3, 3] = [0, 2, 4]
        rest = {'Root': root, vr.HEAD: root@local, 'Spine': root.copy()}
        parents = {'Root': None, vr.HEAD: 'Root', 'Spine': 'Root'}
        replacement = local.copy(); replacement[:3, :3] *= .01; replacement[:3, 3] *= .25
        got = vr.impose(rest, parents, {vr.HEAD: replacement})
        np.testing.assert_allclose(got[vr.HEAD], root@replacement, atol=1e-14)
        np.testing.assert_array_equal(got['Spine'], root)

    def test_partial_head_weight_moves_torso_even_in_a_shape_named_head(self):
        vertices = np.asarray([[0., 0., 100.], [0., 0., 100.]])
        weights = np.asarray([[1., 0.], [.9, .1]])
        poses = np.repeat(np.eye(4)[None, None], 2, axis=0)
        poses = np.repeat(poses, 2, axis=1)
        poses[1, 1, 1, 3] = 20
        actual = rig.lbs(vertices, weights, poses, True)
        np.testing.assert_allclose(actual[1]-actual[0], [[0, 0, 0], [0, 2, 0]], atol=1e-14)

    def test_raw_weight_sum_bias_does_not_become_head_movement(self):
        vertices = np.asarray([[0., 0., 100.]])
        weights = np.asarray([[.9996, 0.]])
        poses = np.repeat(np.eye(4)[None, None], 2, axis=0)
        poses = np.repeat(poses, 2, axis=1); poses[1, 1, 2, 3] = 20
        result = rig.lbs(vertices, weights, poses, False)
        np.testing.assert_array_equal(result[0], result[1])
        self.assertAlmostEqual(result[0, 0, 2], 99.96)

    def test_male_roi_requires_torso_support_and_bounds(self):
        v = [[0, 20, 95], [0, 20, 95], [0, 70, 95]]
        w = np.asarray([[.5, .5], [1., 0.], [.5, .5]])
        np.testing.assert_array_equal(vr.region_indices(v, w, ['Head', 'Spine2']), [0])


if __name__ == '__main__':
    unittest.main()
