"""Synthetic controls for the pure native SE anchor-response scorer."""

import copy
from pathlib import Path
import sys
import unittest

if __package__:
    # The retained joint helper also loads legacy sibling modules by name.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from .fsmp_se_anchor_response import DRIVERS, PARENTS, evaluate
else:
    from fsmp_se_anchor_response import DRIVERS, PARENTS, evaluate


ROTATION = [0., -1., 0., 1., 0., 0., 0., 0., 1.]
IDENTITY = [1., 0., 0., 0., 1., 0., 0., 0., 1.]
ROLES = (DRIVERS[1], PARENTS[0], PARENTS[1], DRIVERS[0])
SPANS = {"quiet": (100, 340), "held": (600, 840), "returned": (1100, 1340)}
REST = {role: {"translation": [0., 1., 0.], "rotationRowMajor": IDENTITY, "scale": 1.}
        for role in DRIVERS}


def fixture_pose(anchor_shift, driver_shift, right_shift=0, fixed_offset=.10):
    """In a rotated world basis, local X moves in WORLD +Y."""
    result = {}
    for index, (anchor, driver) in enumerate(zip(PARENTS, DRIVERS, strict=True)):
        kinematic_shift = anchor_shift if index == 0 else right_shift
        dynamic_shift = fixed_offset + driver_shift if index == 0 else right_shift
        anchor_y = 1600. + 19. * index
        result[anchor] = {"world": ROTATION + [2048., anchor_y + kinematic_shift, 7000.],
                          "rigidBody": True, "inverseMass": 0, "flags": 2}
        result[driver] = {"world": ROTATION + [2047., anchor_y + dynamic_shift, 7000.],
                          "rigidBody": True, "inverseMass": 20, "flags": 0}
    return [result[key] for key in ROLES]


def trial():
    quiet = fixture_pose(0., 0.)
    held = fixture_pose(.01, .01)
    return [
        {"pair": i, "preQpc": i * 100 + 10, "postQpc": i * 100 + 20,
         "pre": copy.deepcopy(pre), "post": copy.deepcopy(post), "hostTimeStep": 1 / 60}
        for i, (pre, post) in enumerate([
            (quiet, quiet), (quiet, quiet), (quiet, quiet),
            (quiet, fixture_pose(.01, 0.)), (fixture_pose(.01, .004), held),
            (held, held), (held, held), (held, held),
            (held, fixture_pose(0., .009)), (fixture_pose(0., .008), fixture_pose(0., .003)),
            (quiet, quiet), (quiet, quiet), (quiet, quiet),
        ], start=1)
    ]


class AnchorResponseTests(unittest.TestCase):
    def evaluate(self, rows=None, spans=SPANS, delta=.01):
        return evaluate(trial() if rows is None else rows, ROLES, spans, rest=REST, anchor_delta=delta)

    def test_selects_complete_pairs_and_reports_measured_release(self):
        result = self.evaluate()
        self.assertTrue(result["qualified"], result["checks"])
        self.assertEqual(result["measures"]["commandedWorldAnchorDeltaGU"], [0., .01, 0.])
        self.assertAlmostEqual(result["measures"]["leftHeldSignedTravelGU"], .01)
        self.assertAlmostEqual(result["measures"]["float32TranslationFloorGU"], 2**-10)
        self.assertAlmostEqual(result["phases"]["held"]["leftJointXRangeGU"][0], .10)
        self.assertEqual(result["phases"]["held"]["pairCount"], 3)
        self.assertEqual(result["phases"]["held"]["qpcSpanTicks"], 210)
        self.assertAlmostEqual(result["phases"]["held"]["hostTimeStepSumSeconds"], 3 / 60)
        release = result["releaseTransient"]
        self.assertTrue(release["available"])
        self.assertEqual(release["pairCount"], 2)
        self.assertAlmostEqual(release["largestObservedAbsLeftJointXDeviationGU"], .009)
        self.assertAlmostEqual(release["largestObservedWithinPairAbsLeftJointXDeltaGU"], .009)

    def test_cuts_partial_pair_and_refuses_insufficient_phase_coverage(self):
        result = self.evaluate(spans={**SPANS, "held": (611, 840)})
        self.assertFalse(result["qualified"])
        self.assertFalse(result["checks"]["completePhaseCoverage"])
        self.assertEqual(result["phases"]["held"]["firstPair"], 7)

    def test_wrong_world_direction_fails_held_input(self):
        result = self.evaluate(delta=-.01)
        self.assertFalse(result["qualified"])
        self.assertFalse(result["checks"]["commandedAnchorHeldAndReturned"])
        self.assertFalse(result["checks"]["leftMovedInCommandedDirection"])

    def test_held_anchor_without_dynamic_body_shift_is_refused(self):
        rows = trial()
        for row in rows[5:8]:
            row["pre"] = row["post"] = fixture_pose(.01, 0.)
        result = self.evaluate(rows)
        self.assertTrue(result["checks"]["commandedAnchorHeldAndReturned"])
        self.assertFalse(result["checks"]["leftMovedInCommandedDirection"])
        self.assertFalse(result["qualified"])

    def test_unchanged_rig_never_qualifies_tiny_command_within_error(self):
        rows = trial()
        for row in rows[5:8]:
            row["pre"] = row["post"] = fixture_pose(0., .01)
        result = self.evaluate(rows, delta=.0001)
        self.assertTrue(result["checks"]["leftMovedInCommandedDirection"])
        self.assertFalse(result["checks"]["commandedAnchorHeldAndReturned"])

    def test_right_motion_between_phases_is_refused(self):
        rows = trial()
        rows[8]["post"] = fixture_pose(0., .009, right_shift=.013)
        result = self.evaluate(rows)
        self.assertFalse(result["checks"]["independentRightControl"])
        self.assertGreater(result["measures"]["rightSpanUpperGU"], .010)
        self.assertFalse(result["qualified"])

    def test_left_driver_must_return_with_known_anchor(self):
        rows = trial()
        for row in rows[-3:]:
            row["pre"] = row["post"] = fixture_pose(0., .007)
        result = self.evaluate(rows)
        self.assertTrue(result["checks"]["commandedAnchorHeldAndReturned"])
        self.assertFalse(result["checks"]["leftReturned"])
        self.assertFalse(result["checks"]["nominalLeftRest"])

    def test_noise_floor_blocks_small_signed_travel(self):
        rows = trial()
        rows[1]["post"] = fixture_pose(0., -.003)
        result = self.evaluate(rows)
        self.assertGreater(result["measures"]["effectiveSignalFloorGU"], .01)
        self.assertFalse(result["checks"]["leftMovedInCommandedDirection"])

    def test_undercovered_release_is_optional(self):
        rows = trial()
        for row in rows[8:10]:
            row["pre"] = row["post"] = fixture_pose(.01, .01)
        result = self.evaluate(rows, spans={**SPANS, "held": (600, 1050), "returned": (1050, 1340)})
        self.assertTrue(result["qualified"])
        self.assertFalse(result["releaseTransient"]["available"])

    def test_clock_and_role_validation_fail_closed(self):
        rows = trial()
        rows[8]["preQpc"] = rows[7]["postQpc"]
        with self.assertRaisesRegex(ValueError, "contiguous advancing"):
            self.evaluate(rows)
        rows = trial()
        rows[1]["post"][ROLES.index(DRIVERS[0])]["inverseMass"] = 10
        with self.assertRaisesRegex(ValueError, "0.05-mass"):
            self.evaluate(rows)

    def test_joint_rest_uses_rotated_pivot_and_rejects_wrong_nominal(self):
        rows = trial()
        for row in rows[:3] + rows[-3:]:
            row["pre"] = row["post"] = fixture_pose(0., 0., fixed_offset=.08)
        result = self.evaluate(rows)
        self.assertAlmostEqual(result["phases"]["quiet"]["leftJointXRangeGU"][0], .08)
        self.assertFalse(result["checks"]["nominalLeftRest"])


if __name__ == "__main__":
    unittest.main()
