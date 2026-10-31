"""Current-TRI support, retained rig gates and a composed-motion sphere bound."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[4] / "src/main/python/physics"


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


rig = module("claw_current_tri_rig_tests", "p1_rig.py")
bounds = module("claw_motion_bound_tests", "motion_bounds.py")


class CurrentTriRigTests(unittest.TestCase):
    def profile(self):
        return json.loads((ROOT / "p1-rig-v3.json").read_text(encoding="utf-8-sig"))

    def test_current_field_support_is_bounded_and_anchors_face_stay_fixed(self):
        p = self.profile()
        vertices = np.array([[-8, 30, 96], [8, 30, 96], [10, 50, 96], [10, 30, 96], [10, 30, 80]], float)
        delta = np.array([[0, 1, -3], [0, 2, -6], [0, 2, -6], [0, 2, -6], [0, 2, -6]], float)
        result, report = rig.mobility(vertices, delta, [3], p)
        self.assertGreater(result[0], 0)
        self.assertGreater(result[1], result[0])
        self.assertTrue(np.all(result <= .4))
        np.testing.assert_array_equal(result[2:], 0)
        # Normalization is intrinsic to the exact current field, with no old TRI.
        scaled, _ = rig.mobility(vertices, delta * 2, [3], p)
        np.testing.assert_allclose(result, scaled)
        self.assertFalse(report["legacyModerateTriUsed"])

    def test_profile_cannot_weaken_rig_gates_or_retarget_existing_bones(self):
        rig.validate_profile(self.profile())
        for change in ("threshold", "mobility", "anchor", "bone", "path", "skeleton"):
            p = copy.deepcopy(self.profile())
            if change == "threshold": p["verification"]["normalizedOrdinaryMaxError"] = 999
            if change == "mobility": p["mobility"]["maximum"] = .5
            if change == "anchor": p["collar"]["anchorCountRange"] = [1, 500]
            if change == "bone": p["p1Bones"][0] = "NPC L Breast"
            if change == "path": p["outputRelativeNif"] = "../escape.nif"
            if change == "skeleton": p["inputs"]["skeletonSha256"] = "f" * 64
            with self.subTest(change=change), self.assertRaises(ValueError):
                rig.validate_profile(p)

    def test_noop_or_nonfinite_current_field_is_refused(self):
        for value in (0, float("nan")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                rig.mobility([[8, 30, 96]], [[0, 0, value]], [], self.profile())


class MotionBoundTests(unittest.TestCase):
    def test_five_independently_composed_nominal_joint_perturbations_fit_bound(self):
        random = np.random.default_rng(20261101)
        center = np.array([1., -2., 70.])
        radius = 100.
        pivots = random.uniform(-50, 110, (11, 3))
        extra = bounds.motion_bound_extra(center, radius, pivots)
        for _ in range(200):
            direction = random.normal(size=3)
            before = center + direction / np.linalg.norm(direction) * radius
            after = before.copy()
            for _ in range(5):
                angles = random.uniform(-.0105, .0105, 3)
                cx, cy, cz = np.cos(angles)
                sx, sy, sz = np.sin(angles)
                rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
                ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
                rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
                pivot = pivots[random.integers(len(pivots))]
                after = (rx @ ry @ rz) @ (after - pivot) + pivot + random.uniform(-.5, .5, 3)
            self.assertLessEqual(float(np.linalg.norm(after - before)), extra)

    def test_larger_spheres_have_larger_extra_and_bad_inputs_fail(self):
        pivots = [[0, 0, 0], [10, 20, 30]]
        self.assertGreater(bounds.motion_bound_extra([0, 0, 0], 100, pivots),
                           bounds.motion_bound_extra([0, 0, 0], 10, pivots))
        for radius in (-1, float("inf"), float("nan")):
            with self.subTest(radius=radius), self.assertRaises(ValueError):
                bounds.motion_bound_extra([0, 0, 0], radius, pivots)


if __name__ == "__main__":
    unittest.main()
