"""Offline controls for selecting sampled EarR reach without physics calls."""

from copy import deepcopy
from dataclasses import replace
import unittest

from cbpc_vr_reach import EAR, PoseWindow, select_window


IDENTITY = {"pid": 12, "nonce": 4, "loadEpoch": 2, "actor": 0xFF000899, "base": 0x0B000800,
            "handle": 31, "cell": 0x0A01A5C6, "addon": 0xCDD87, "rootToken": 4}
ROTATION = [1, 0, 0, 0, 1, 0, 0, 0, 1]
ARGUMENTS = {"expected_identity": IDENTITY, "qpc_frequency": 1000,
             "capsule": {"p1": [-2., 0., 0.], "p2": [2., 0., 0.], "radius": 1.},
             "wand": {"local": [1., 0., 0.], "radius": 1.},
             "minimum_hold_ticks": 75, "minimum_calibration_ticks": 75, "maximum_gap_ticks": 26}


def pose(x, y=0):
    return {"rotationRowMajor": ROTATION.copy(), "translation": [x, y, 0], "scale": 1.}


def window(start, sequence, left_values, ear_values=None):
    ears = [0] * len(left_values) if ear_values is None else ear_values
    rows = []
    for index, (left, ear) in enumerate(zip(left_values, ears, strict=True)):
        begin = start + index * 25
        rows.append({"qpcBegin": begin, "qpcEnd": begin + 1, "phaseSequence": sequence + index,
                     "actorRootWorld": pose(0), "rightWandWorld": pose(50), "uprightHmdWorld": pose(40),
                     "leftWandWorld": pose(left), "earWorld": pose(ear)})
    return PoseWindow(IDENTITY.copy(), EAR, 1000, (rows[0]["qpcBegin"], rows[-1]["qpcEnd"]), rows)


class ReachTests(unittest.TestCase):
    def setUp(self):
        self.target = window(100, 1, [-10] * 6)
        self.near = window(350, 10, [1.5, 1.6, 1.5, 1.6, 1.7])
        self.far = window(550, 20, [9.0, 9.0, 9.1, 9.1, 9.2])

    def test_uses_measured_calibration_extrema_and_inward_clock_bounds(self):
        result = select_window(self.target, self.near, self.far, **ARGUMENTS)
        self.assertEqual(result["qpc"], (101, 225))
        self.assertEqual(result["phaseSequence"], (1, 6))
        self.assertEqual(result["nearCalibrationQpc"], (351, 450))
        self.assertEqual(result["farCalibrationQpc"], (551, 650))
        self.assertAlmostEqual(result["maximumNearSignedGap"], -1.3)
        self.assertAlmostEqual(result["minimumFarSignedGap"], 6.0)
        self.assertFalse(result["providerContactMeasured"])
        self.assertEqual(result["observation"], "sampled_nominal_capsule_reach")
        self.assertEqual((result["identity"], result["role"], result["qpcFrequency"]), (IDENTITY, EAR, 1000))

    def test_single_sample_of_the_wrong_geometry_splits_reach_window(self):
        target = window(100, 1, [-10] * 11, [0] * 5 + [-2] + [0] * 5)
        near = window(500, 20, [1.5] * 5)
        far = window(700, 30, [9.0] * 5)
        result = select_window(target, near, far, **ARGUMENTS)
        self.assertEqual(result["phaseSequence"], (7, 11))
        self.assertEqual(result["qpc"], (251, 350))
        self.assertIsNone(select_window(target, near, far, **{**ARGUMENTS, "minimum_hold_ticks": 100}))

    def test_near_calibration_extrema_can_refuse_an_apparently_valid_reach(self):
        near = window(350, 10, [1.95, 2.0, 2.15, 2.23, 2.28])
        self.assertIsNone(select_window(self.target, near, self.far, **ARGUMENTS))

    def test_refuses_missing_alias_or_ambiguous_calibrations(self):
        ambiguous = window(550, 20, [1.6] * 5)
        for options, reason in (
            ((self.near, None), "Missing or foreign"),
            ((self.near, self.near), "independently measured"),
            ((self.near, ambiguous), "calibration is ambiguous"),
            ((replace(self.near, role="TailBone01"), self.far), "Missing or foreign"),
            ((replace(self.near, identity={**IDENTITY, "handle": 32}), self.far), "Missing or foreign"),
            ((self.near, replace(self.far, qpc_frequency=99)), "Missing or foreign"),
        ):
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                select_window(self.target, *options, **ARGUMENTS)

    def test_rejects_callback_gap_qpc_gap_and_unobserved_bounds(self):
        for field, value, reason in (
            ("phaseSequence", 4, "cadence gap"),
            ("qpcBegin", 154, "cadence gap"),
            ("qpcEnd", 176, "cadence gap"),
        ):
            rows = deepcopy(self.target.rows)
            rows[2][field] = value
            if field == "qpcBegin":
                rows[2]["qpcEnd"] = value + 1
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, reason):
                select_window(replace(self.target, rows=rows), self.near, self.far, **ARGUMENTS)
        with self.assertRaisesRegex(ValueError, "measured boundaries"):
            select_window(replace(self.target, bounds=(99, 226)), self.near, self.far, **ARGUMENTS)

    def test_rejects_tracking_or_root_drift_and_short_calibration(self):
        for name in ("rightWandWorld", "uprightHmdWorld", "actorRootWorld"):
            rows = deepcopy(self.far.rows)
            rows[2][name]["translation"][1] = .36
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "scene controls"):
                select_window(self.target, self.near, replace(self.far, rows=rows), **ARGUMENTS)
        with self.assertRaisesRegex(ValueError, "moved during calibration"):
            select_window(self.target, window(350, 10, [1.5, 1.5, 1.86, 1.5, 1.5]), self.far, **ARGUMENTS)
        with self.assertRaisesRegex(ValueError, "calibration window is too short"):
            select_window(self.target, window(350, 10, [1.5] * 4), self.far, **ARGUMENTS)


if __name__ == "__main__":
    unittest.main()
