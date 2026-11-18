"""Bounded robust scalar fits must protect every supplied sample."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np

spec = importlib.util.spec_from_file_location("claw_attachment_fit_tests",
    Path(__file__).resolve().parents[4] / "src/main/python/physics/attachment_fit.py")
fit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fit)


class AttachmentFitTests(unittest.TestCase):
    def assert_samples_safe(self, r, d, result, tolerance):
        before = np.linalg.norm(r, axis=-1)
        after = np.linalg.norm(np.asarray(r) + result["shift"] * np.asarray(d), axis=-1)
        self.assertTrue(np.all(after - before <= tolerance))
        self.assertLessEqual(result["squared_residual_after"], result["squared_residual_before"])

    def test_single_training_win_is_blocked_by_an_opposed_heldout_sample(self):
        training = fit.fit_shift([[1., 0, 0]], [[-1., 0, 0]], [-2, 2], 0)
        self.assertEqual(training["shift"], 1)
        both = fit.fit_shift([[1., 0, 0], [1., 0, 0]], [[-1., 0, 0], [1., 0, 0]], [-2, 2], 0)
        self.assertEqual(both["feasible_interval"], [0, 0])
        self.assertEqual(both["shift"], 0)
        self.assertEqual(both["status"], "no_op")

    def test_constrained_full_set_optimum_and_limiting_sample_are_reported(self):
        # Unconstrained optimum is 1.75; sample one restricts the interval to [0,1].
        r = np.array([[3., 0, 0], [.5, 0, 0]])
        d = np.array([[-1., 0, 0], [-1., 0, 0]])
        result = fit.fit_shift(r, d, [-5, 5], 0)
        self.assertEqual(result["feasible_interval"], [0, 1])
        self.assertEqual(result["upper_sample"], 1)
        self.assertEqual(result["shift"], 1)
        self.assert_samples_safe(r, d, result, 0)

    def test_interior_least_squares_optimum_removes_consistent_residuals(self):
        r = np.array([[2., 0], [4., 0]])
        d = np.array([[-1., 0], [-2., 0]])
        result = fit.fit_shift(r, d, [-3, 3], 0)
        self.assertEqual(result["shift"], 2)
        self.assertEqual(result["squared_residual_after"], 0)
        self.assert_samples_safe(r, d, result, 0)

    def test_objective_weights_do_not_disable_a_samples_constraint(self):
        result = fit.fit_shift([[1., 0], [1., 0]], [[-1., 0], [1., 0]], [-2, 2], 0,
                               objective_weights=[1, 0])
        self.assertEqual(result["shift"], 0)
        self.assertEqual(result["feasible_interval"], [0, 0])

    def test_huge_zero_weight_control_does_not_erase_the_objective_response(self):
        r = np.array([[1., 0], [1e200, 0]])
        d = np.array([[-1., 0], [0., 0]])
        result = fit.fit_shift(r, d, [-2, 2], 0, objective_weights=[1, 0])
        self.assertEqual(result["shift"], 1)
        self.assertEqual(result["squared_residual_after"], 0)
        np.testing.assert_array_equal(r[1] + result["shift"] * d[1], r[1])

    def test_tiny_response_over_large_finite_bounds_is_not_an_unconstrained_noop(self):
        r, d = np.array([[1., 0]]), np.array([[1e-200, 0]])
        result = fit.fit_shift(r, d, [-1e200, 1e200], 0)
        self.assertEqual(result["feasible_interval"], [-1e200, 0])
        self.assertEqual(result["shift"], -1e200)
        self.assertEqual(result["squared_residual_after"], 0)
        self.assert_samples_safe(r, d, result, 0)

    def test_unsupported_effective_response_ranges_are_rejected_explicitly(self):
        for response, bounds in (([[1e200, 0]], [-1e200, 1e200]),
                                  ([[1e-200, 0]], [-1e-200, 1e-200]),
                                  ([[1e-200, 0]], [-1, 1])):
            with self.subTest(response=response, bounds=bounds), self.assertRaises(ValueError):
                fit.fit_shift([[1., 0]], response, bounds, 0)
        with self.assertRaises(ValueError):
            fit.fit_shift([[1e-200, 0]], [[-1e-200, 0]], [-2, 2], 0)

    def test_both_conventions_and_multistate_axes_remain_explicit_samples(self):
        r = np.array([[[1., 0], [.8, 0]], [[.9, 0], [.7, 0]]])
        d = -np.ones_like(r)
        d[..., 1] = 0
        tolerance = np.array([[0., 0.], [0., 0.]])
        result = fit.fit_shift(r, d, [-.25, .25], tolerance)
        self.assertEqual(result["sample_count"], 4)
        self.assertEqual(result["shift"], .25)
        self.assert_samples_safe(r, d, result, tolerance)

    def test_zero_tiny_response_zero_bounds_and_zero_objective_are_noops(self):
        for response, bounds, weights in (([[0., 0]], [-1, 1], None),
                                           ([[1e-200, 0]], [-1, 1], None),
                                           ([[-1., 0]], [0, 0], None),
                                           ([[-1., 0]], [-1, 1], [0])):
            with self.subTest(response=response, bounds=bounds, weights=weights):
                result = fit.fit_shift([[1., 0]], response, bounds, objective_weights=weights)
                self.assertEqual(result["shift"], 0)
                self.assertEqual(result["status"], "no_op")

    def test_zero_residual_can_restrict_shift_with_its_own_tolerance(self):
        result = fit.fit_shift([[1., 0], [0., 0]], [[-1., 0], [3., 0]], [-2, 2], [1e-8, 1e-8])
        self.assertAlmostEqual(result["feasible_interval"][1], 1e-8 / 3, places=20)
        self.assertGreater(result["shift"], 0)
        self.assert_samples_safe(np.array([[1., 0], [0., 0]]), np.array([[-1., 0], [3., 0]]), result, [1e-8, 1e-8])

    def test_cancellation_retains_the_tiny_near_root_and_large_coefficients(self):
        # The naive positive root rounds to zero; stable product form keeps it.
        result = fit.fit_shift([[1e8, 0]], [[1., 0]], [-1, 1], 1e-8)
        self.assertGreater(result["feasible_interval"][1], 0)
        self.assertAlmostEqual(result["feasible_interval"][1], 1e-8, places=20)
        large = fit.fit_shift([[1e100, 0]], [[-1e100, 0]], [-2, 2], 0)
        self.assertEqual(large["shift"], 1)
        self.assertEqual(large["squared_residual_after"], 0)

    def test_random_returned_shifts_pass_direct_sample_verification(self):
        rng = np.random.default_rng(20261118)
        for _ in range(40):
            r = rng.normal(size=(2, 8, 3))
            d = -r * rng.uniform(.2, 2, size=(2, 8, 1)) + rng.normal(0, .1, r.shape)
            tolerance = rng.uniform(0, 1e-8, size=(2, 8))
            result = fit.fit_shift(r, d, [-.4, .4], tolerance)
            self.assert_samples_safe(r, d, result, tolerance)
            self.assertLessEqual(result["feasible_interval"][0], result["shift"])
            self.assertLessEqual(result["shift"], result["feasible_interval"][1])

    def test_invalid_nonfinite_shapes_bounds_and_tolerances_are_refused(self):
        cases = [([], [], [-1, 1], 0), ([[1, 0]], [[1]], [-1, 1], 0),
                 ([[float("nan"), 0]], [[1, 0]], [-1, 1], 0),
                 ([[1, 0]], [[float("inf"), 0]], [-1, 1], 0),
                 ([[1, 0]], [[1, 0]], [1, 2], 0), ([[1, 0]], [[1, 0]], [1, -1], 0),
                 ([[1, 0]], [[1, 0]], [-float("inf"), 1], 0),
                 ([[1, 0]], [[1, 0]], [-1, 1], -1), ([[1, 0]], [[1, 0]], [-1, 1], float("nan")),
                 ([[1, 0]], [[1, 0]], [-1, 1], [1, 2]), ([[True, False]], [[1, 0]], [-1, 1], 0)]
        for args in cases:
            with self.subTest(args=args), self.assertRaises(ValueError):
                fit.fit_shift(*args)
        for weights in ([-1], [float("inf")], [1, 2]):
            with self.subTest(weights=weights), self.assertRaises(ValueError):
                fit.fit_shift([[1, 0]], [[1, 0]], [-1, 1], objective_weights=weights)


if __name__ == "__main__":
    unittest.main()
