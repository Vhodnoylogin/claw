import unittest

import numpy as np

from prepare_tail_refit_waypoint import MIN_MARGIN, calibration, waypoint


def pose(xyz):
    return {"translation": xyz, "rotationRowMajor": [1., 0., 0., 0., 1., 0., 0., 0., 1.], "scale": 1.}


class TailWaypointTest(unittest.TestCase):
    def setUp(self):
        self.origin = {"source": [0., 0., 0.], "left": pose([0., 0., 0.]),
                       "controls": {"head": pose([-75., 0., 0.]), "right": pose([0., -90., 0.])}}
        self.frame = {**self.origin, "targetPose": pose([0., 0., 0.])}

    @staticmethod
    def bank(displacement):
        return [{"p1": [x, displacement, 0.], "p2": [x, displacement, 1.], "radius": 1.}
                for x in (-1., 0., 1., 2.)]

    def test_sweep_admits_point_distinguishing_complete_banks(self):
        resting, active = self.bank(0.), self.bank(10.)
        report = waypoint(self.origin, [self.frame], [resting, active, resting], 70. * np.eye(3), 70.)
        selected = report["waypoint"]
        self.assertTrue(selected["insideStockEnvelope"])
        self.assertGreaterEqual(selected["neutralSeparationGu"], MIN_MARGIN)
        self.assertGreaterEqual(selected["morphedOverlapGu"], MIN_MARGIN)
        self.assertGreaterEqual(report["stockEnvelopeMarginUpperGu"], min(
            selected["neutralSeparationGu"], selected["morphedOverlapGu"]))

    def test_no_single_stationary_point_if_animated_support_boxes_separate(self):
        resting, active = self.bank(0.), self.bank(10.)
        shifted = {**self.frame, "targetPose": pose([30., 0., 0.])}
        report = waypoint(self.origin, [self.frame, shifted], [resting, active, resting], 70. * np.eye(3), 70.)
        self.assertEqual(report, {"testedCenters": 0, "stockEnvelopeMarginUpperGu": 0., "waypoint": None})

    def test_near_rigid_axis_swap_without_original_movement_match_refuses(self):
        columns = (70. * np.eye(3)).tolist()
        policy = {"columnsGuPerMetre": columns, "nearMetres": [-.30, 1.1, -.35]}
        publication = {"status": "acknowledged", "frame": {"left": {
            "matrix": [1., 0., 0., -.30, 0., 1., 0., 1.1, 0., 0., 1., -.35]}}}
        moved = {"source": [0., -7., 0.]}
        matrix, minimum = calibration(self.origin, moved, policy, publication)
        self.assertTrue(np.array_equal(matrix, 70. * np.eye(3)))
        self.assertEqual(minimum, 70.)
        policy["columnsGuPerMetre"] = [columns[0], columns[2], columns[1]]
        with self.assertRaisesRegex(ValueError, "does not validate"):
            calibration(self.origin, moved, policy, publication)


if __name__ == "__main__":
    unittest.main()
