import unittest
from math import hypot

import numpy as np

from prepare_tail_refit_waypoint import MIN_MARGIN, calibration, envelope_distance, waypoint


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

    def test_radial_travel_budget_filters_candidates_without_changing_stock_bound(self):
        resting, active = self.bank(0.), self.bank(10.)
        args = (self.origin, [self.frame], [resting, active, resting], 70. * np.eye(3), 70.)
        unlimited = waypoint(*args)
        restricted = waypoint(*args, max_travel=.12)
        self.assertGreater(unlimited["waypoint"]["controllerTravelMetres"], .12)
        self.assertLessEqual(restricted["waypoint"]["controllerTravelMetres"], .12)
        self.assertGreaterEqual(restricted["waypoint"]["morphedOverlapGu"], MIN_MARGIN)
        self.assertEqual(restricted["stockEnvelopeMarginUpperGu"], unlimited["stockEnvelopeMarginUpperGu"])
        self.assertIsNone(waypoint(*args, max_travel=.01)["waypoint"])

    def test_distance_to_joint_envelope_covers_disk_rim_and_ball(self):
        points = np.array([[.6, .8, 0.], [0., 2., 0.], [2., 1., 0.], [2., -.5, 0.], [0., -.5, 0.]])
        expected = [0., 1., hypot(.4, 1.2), hypot(1.1, 1.2), 1.1]
        np.testing.assert_allclose(envelope_distance(points, 1., .6), expected, atol=1e-12)
        np.testing.assert_allclose(envelope_distance(points, None, .6), [0., 0., 0., 1.1, 1.1], atol=1e-12)
        np.testing.assert_allclose(envelope_distance(points[:2], 1., -1.), [0., 1.], atol=1e-12)
        np.testing.assert_allclose(envelope_distance(points[1:3], 1., 1.), [1., 2.], atol=1e-12)
        self.assertTrue(np.isinf(envelope_distance(points, 1., 1.01)).all())

    def test_joint_constraints_select_only_feasible_grid_points(self):
        resting, active = self.bank(0.), self.bank(10.)
        args = (self.origin, [self.frame], [resting, active, resting], 70. * np.eye(3), 70.)
        legacy = waypoint(*args, max_travel=.12)
        report = waypoint(*args, max_travel=.12, min_height=1.31)
        selected = report["waypoint"]
        self.assertLessEqual(selected["controllerTravelMetres"], .12)
        self.assertGreaterEqual(selected["leftTranslationMetres"][1], 1.31)
        self.assertGreaterEqual(report["constrainedGridBestMarginGu"], MIN_MARGIN)
        self.assertGreaterEqual(report["constrainedEnvelopeMarginUpperGu"], report["constrainedGridBestMarginGu"])
        self.assertEqual(report["stockEnvelopeMarginUpperGu"], legacy["stockEnvelopeMarginUpperGu"])
        impossible = waypoint(*args, max_travel=.12, min_height=1.33)
        self.assertIsNone(impossible["waypoint"])
        self.assertIsNone(impossible["constrainedGridBestMarginGu"])
        self.assertEqual(impossible["constrainedEnvelopeMarginUpperGu"], 0.)

    def test_height_uses_tracking_y_rather_than_world_y(self):
        resting, active = self.bank(0.), self.bank(10.)
        turned = 70. * np.array([[1., 0., 0.], [0., 0., 1.], [0., -1., 0.]])
        args = (self.origin, [self.frame], [resting, active, resting], turned, 70.)
        self.assertIsNotNone(waypoint(*args, max_travel=.3)["waypoint"])
        constrained = waypoint(*args, max_travel=.3, min_height=1.255)
        self.assertIsNone(constrained["waypoint"])
        self.assertLess(constrained["constrainedEnvelopeMarginUpperGu"], MIN_MARGIN)
        with self.assertRaisesRegex(ValueError, "height must be positive and finite"):
            waypoint(*args, min_height=float("nan"))

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
