import unittest

if __package__:
    from .fsmp_animation_writeback import (compare_animated_joint_x, evaluate_translation, hierarchy_residual,
                                          preceding_frame_sync, world_sample_qpc)
else:
    from fsmp_animation_writeback import (compare_animated_joint_x, evaluate_translation, hierarchy_residual,
                                         preceding_frame_sync, world_sample_qpc)


def transform(x, y=0., *, turns=False, qpc=1):
    rotation = [0, -1, 0, 1, 0, 0, 0, 0, 1] if turns else [1, 0, 0, 0, 1, 0, 0, 0, 1]
    return {'translation': [x, y, 0.], 'rotationRowMajor': rotation, 'scale': 1., 'qpc': qpc}


def phases(*, target=1.2, assigned=1.2, sync_end=1.2):
    return {'writer': 'observed', 'before': transform(1., qpc=10), 'target': transform(target, qpc=11),
            'after': transform(assigned, qpc=12), 'final': transform(sync_end, qpc=13)}


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

    def test_joint_write_retained_under_whole_actor_motion_and_rotation(self):
        result = evaluate_translation(
            phases(), sync_end_parent=transform(0.), scene_parent=transform(100., 20., turns=True),
            scene_world=transform(100., 21.2, turns=True), scene_local=transform(1.),
            rest_local=transform(1.), tolerance=.005)
        self.assertEqual(result['status'], 'retained-at-world-sample')
        self.assertAlmostEqual(result['syncEndVsNextWorldJointGU'], 0.)
        self.assertAlmostEqual(result['hierarchyResidualGU'], .2)

    def test_stock_assignment_sync_return_and_later_hierarchy_are_distinct(self):
        for writes, scene_x, expected in (
                (phases(assigned=1.1), 1., 'assignment-differs-from-target'),
                (phases(sync_end=1.1), 1., 'changed-by-sync-return'),
                (phases(), 1., 'later-world-matches-hierarchy'),
                (phases(), 1.1, 'later-world-moved')):
            with self.subTest(expected=expected):
                result = evaluate_translation(
                    writes, sync_end_parent=transform(0.), scene_parent=transform(0.),
                    scene_world=transform(scene_x), scene_local=transform(1.),
                    rest_local=transform(1.), tolerance=.005)
                self.assertEqual(result['status'], expected)
        self.assertAlmostEqual(result['stockDisplacementGU'], .2)

    def test_counts_displacement_from_the_immediate_writer_before(self):
        writer = phases()
        writer['writerBefore'] = transform(1.15, qpc=11)
        result = evaluate_translation(
            writer, sync_end_parent=transform(0.), scene_parent=transform(0.),
            scene_world=transform(1.), scene_local=transform(1.), rest_local=transform(1.), tolerance=.005)
        self.assertAlmostEqual(result['stockDisplacementGU'], .05)
        self.assertEqual(result['status'], 'later-world-matches-hierarchy')

    def test_unobserved_and_incomplete_phases_cannot_infer_a_later_write(self):
        scene = dict(sync_end_parent=transform(0.), scene_parent=transform(0.), scene_world=transform(1.),
                     scene_local=transform(1.), rest_local=transform(1.), tolerance=.005)
        self.assertEqual(evaluate_translation({'writer': 'unobserved'}, **scene),
                         {'writer': 'unobserved', 'hierarchyResidualGU': 0.})
        for phase, point in (('target', None), ('final', transform(1.2, qpc=11))):
            with self.subTest(phase=phase), self.assertRaisesRegex(ValueError, 'incomplete or reversed'):
                evaluate_translation(dict(phases(), **{phase: point}), **scene)

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
