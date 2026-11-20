import unittest

import fsmp_vr_p1_pulse as pulse


IDENTITY = [1., 0., 0., 0., 1., 0., 0., 0., 1.]
REST = {name: {"translation": [.1, 0., 0.], "rotationRowMajor": IDENTITY, "scale": 1.}
        for name in pulse.joint.DRIVERS}


def trial(left_motion=.024, right_motion=0., after_motion=0., origin=4., advances=True):
    spans, rows = {}, []
    for index, phase in enumerate(pulse.PHASES, 1):
        start = index * 100
        spans[phase] = (start, start + 90)
        left = origin + (pulse.STEP if phase == "held" else 0.)
        driver = origin + .1 + (left_motion if phase == "held" else after_motion if phase == "returned" else 0.)
        right = origin + 2.1 + (right_motion if phase == "held" else 0.)
        poses = [{"world": IDENTITY + [x, 0., 0.]} for x in (left, origin + 2., driver, right)]
        pre = poses if phase != "held" or not advances else [*poses[:2], {"world": IDENTITY + [origin + .1, 0., 0.]}, poses[3]]
        for tick in range(start + 1, start + 80, 8):
            rows.append({"preQpc": tick, "postQpc": tick + 2, "pre": pre, "post": poses})
    return rows, spans


class PulseTests(unittest.TestCase):
    def evaluate(self, frames):
        return pulse.evaluate(*frames, rest=REST, scale=1.)

    def test_known_step_requires_driver_motion_in_both_coordinate_systems(self):
        result = self.evaluate(trial())
        self.assertEqual(result["status"], "sampled-solver-contrast")
        self.assertAlmostEqual(result["samples"]["driverWorldProjectedX"]["left"]["held"]["peak"], .024)
        self.assertAlmostEqual(result["samples"]["jointLocalX"]["left"]["held"]["peak"], .016)
        self.assertEqual(result["matchingHeldPrePostPairs"], 10)
        self.assertFalse(result["renderedMotionQualified"])
        self.assertEqual(self.evaluate(trial(left_motion=0.))["status"], "inconclusive")
        stale = self.evaluate(trial(advances=False))
        self.assertIs(stale["phaseContrastObserved"], True)
        self.assertEqual(stale["matchingHeldPrePostPairs"], 0)
        self.assertEqual(stale["status"], "inconclusive")

    def test_control_and_return_are_independent_requirements(self):
        cases = {"moving control": trial(right_motion=.025), "missing recovery": trial(after_motion=.008),
                 "insufficient precision": trial(origin=131072.)}
        for reason, frames in cases.items():
            with self.subTest(reason=reason):
                self.assertEqual(self.evaluate(frames)["status"], "inconclusive")

    def test_rejects_reused_time_span_and_wrong_anchor(self):
        rows, spans = trial()
        spans["held"] = spans["quiet"]
        with self.assertRaisesRegex(ValueError, "disjoint"):
            self.evaluate((rows, spans))
        rows, spans = trial()
        rows[10]["post"][1]["world"][10] = .1
        with self.assertRaisesRegex(ValueError, "kinematic pose"):
            self.evaluate((rows, spans))
