import unittest

if __package__:
    from .fsmp_scene_writeback import decompose, score_right_control
else:
    from fsmp_scene_writeback import decompose, score_right_control


class FsmpSceneWritebackTests(unittest.TestCase):
    def test_scene_reset_does_not_pass_stock_gate(self):
        origin = (0., 0., 0.)
        measurement = decompose(
            scene_read=origin, scene_before_write=origin, target_before_step=(.031, 0., 0.),
            target_after_step=(.028, 0., 0.), scene_after_write=(.028, 0., 0.),
            scene_after_update=origin,
        )
        self.assertEqual(measurement["sceneReadToOuterReturnGU"], origin)
        self.assertEqual(measurement["postWriteToOuterReturnGU"], (-.028, 0., 0.))
        self.assertFalse(score_right_control(measurement)["absoluteRightGateMet"])

    def test_decomposes_prewriter_drift_and_target_write_error(self):
        measurement = decompose(
            scene_read=(1, 2, 3), scene_before_write=(2, 2, 3), target_before_step=(4, 2, 3),
            target_after_step=(4, 3, 3), scene_after_write=(4, 3, 4),
            scene_after_update=(2, 2, 3),
        )
        self.assertEqual(measurement["stockWriteDeltaGU"], (2, 1, 1))
        self.assertEqual(measurement["sceneReadToBeforeWriteGU"], (1, 0, 0))
        self.assertEqual(measurement["preStepTargetMinusSceneReadGU"], (3, 0, 0))
        self.assertEqual(measurement["solverTargetChangeGU"], (0, 1, 0))
        self.assertEqual(measurement["writtenMinusSolverTargetGU"], (0, 0, 1))

    def test_absolute_ceiling_includes_boundary(self):
        self.assertTrue(score_right_control({"stockWriteDistanceGU": .01})["absoluteRightGateMet"])

    def test_refuses_nonfinite_coordinates(self):
        origin = (0., 0., 0.)
        with self.assertRaisesRegex(ValueError, "finite observed XYZ"):
            decompose(
                scene_read=origin, scene_before_write=origin, target_before_step=origin,
                target_after_step=(float("nan"), 0., 0.), scene_after_write=origin,
                scene_after_update=origin,
            )
