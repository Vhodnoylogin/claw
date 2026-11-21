import unittest

if __package__:
    from .fsmp_animation_writeback import (compare_animated_joint_x, hierarchy_residual,
                                          preceding_frame_sync, world_sample_qpc)
else:
    from fsmp_animation_writeback import (compare_animated_joint_x, hierarchy_residual,
                                         preceding_frame_sync, world_sample_qpc)


class AnimatedWritebackTests(unittest.TestCase):
    def test_world_clock_must_fit_the_independent_request(self):
        self.assertEqual(world_sample_qpc(110_000, 5, 900, 1300, 10_000_000), (1100, 1161))
        with self.assertRaisesRegex(ValueError, 'host request interval'):
            world_sample_qpc(110_000, 5, 900, 1160, 10_000_000)

    def test_scene_read_must_fall_fully_between_two_observed_writers(self):
        syncs = [(10, 12), (20, 25), (30, 32), (80, 90)]
        self.assertEqual(preceding_frame_sync(syncs, 27, 29, 20), 1)
        self.assertIsNone(preceding_frame_sync(syncs, 12, 13, 20))
        self.assertIsNone(preceding_frame_sync(syncs, 12, 20, 20))
        self.assertIsNone(preceding_frame_sync(syncs, 29, 31, 20))
        self.assertIsNone(preceding_frame_sync(syncs, 33, 37, 20))
        self.assertIsNone(preceding_frame_sync(syncs, 92, 94, 20))
        with self.assertRaisesRegex(ValueError, 'nonoverlapping'):
            preceding_frame_sync([(10, 25), (20, 28)], 30, 35, 20)

    def test_hierarchy_residual_uses_rotated_scaled_parent(self):
        identity = [1, 0, 0, 0, 1, 0, 0, 0, 1]
        quarter_turn = [0, -1, 0, 1, 0, 0, 0, 0, 1]
        parent = {'translation': [3, 4, 5], 'rotationRowMajor': quarter_turn, 'scale': 2}
        local = {'translation': [1, 0, 0], 'rotationRowMajor': identity, 'scale': .5}
        recomposed = {'translation': [3, 6, 5], 'rotationRowMajor': quarter_turn, 'scale': 1}
        self.assertEqual(hierarchy_residual(parent, recomposed, local),
                         {'translationGU': 0., 'rotationComponent': 0., 'scale': 0.})
        written = dict(recomposed, translation=[3.1, 6, 5])
        self.assertAlmostEqual(hierarchy_residual(parent, written, local)['translationGU'], .1)

    def test_uses_conservative_neighbors_instead_of_nearest_single_pose(self):
        native = [(10, .05), (20, .07), (30, .13), (40, .18), (50, .2), (60, .15)]
        result = compare_animated_joint_x(native, [(23, 26, .08), (41, 44, .01)],
                                          tolerance=.005, maximum_interval_ticks=20)
        self.assertEqual([row['status'] for row in result], ['within', 'outside'])
        self.assertEqual(result[0]['solverRangeGU'], [.07, .13])
        self.assertAlmostEqual(result[1]['outsideRangeGU'], .17)

    def test_does_not_fill_missing_or_excessively_distant_phases(self):
        native = [(10, 0), (20, .05), (60, .1)]
        result = compare_animated_joint_x(native, [(8, 9, .05), (23, 25, .05), (60, 70, .1)],
                                          tolerance=.005, maximum_interval_ticks=20)
        self.assertEqual([row['status'] for row in result], ['unbracketed'] * 3)

    def test_rejects_disordered_or_invalid_clock_data(self):
        native = [(10, 0), (20, .05), (60, .1)]
        with self.assertRaisesRegex(ValueError, 'ordered scene'):
            compare_animated_joint_x(native, [(12, 15, .05), (13, 17, .05)],
                                     tolerance=.005, maximum_interval_ticks=20)
        with self.assertRaisesRegex(ValueError, 'advancing native'):
            compare_animated_joint_x(native[::-1], [(12, 15, .05)],
                                     tolerance=.005, maximum_interval_ticks=20)
