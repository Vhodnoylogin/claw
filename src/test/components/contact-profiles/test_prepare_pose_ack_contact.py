"""Geometry controls for same-pose ACK contact planning."""
from copy import deepcopy
import json
import unittest

from prepare_pose_ack_contact import contrast, prepare
from test_pose_ack import ACTOR, GENERATION, PROFILE, lines, receipt


NODE = "TailBone02"
OLD_CLEAR = "oldClearNewOverlap"
OLD_OVERLAP = "oldOverlapNewClear"


def sphere(x, radius=.5):
    return [x, 0., 0., x, 0., 0., radius]


def capsule(packet, slot):
    return next(item for item in packet["capsules"] if item["slot"] == slot)


class PoseAckContactTests(unittest.TestCase):
    def setUp(self):
        self.full = receipt(40, 100)
        self.delta = receipt(44, 200, previous=40, application="delta")
        capsule(self.full, 2)["geometry"] = sphere(0.)
        capsule(self.delta, 2)["geometry"] = sphere(6.)

    def plan(self, *packets, profile=PROFILE, node=NODE):
        return prepare(lines(*packets), profile, actor=ACTOR, generation=GENERATION,
                       token=self.delta["token"], node=node, hand_radius=1.)

    def test_same_pose_contact_contrast_in_both_directions(self):
        report = self.plan(self.full, self.delta)
        self.assertEqual((report["previousToken"], report["token"], report["slots"]), (40, 44, [2]))
        self.assertFalse(report["controllerReachChecked"])
        self.assertFalse(report["contactVerified"])
        for direction, destination in ((OLD_CLEAR, [4., 14., 3.]), (OLD_OVERLAP, [4., 2., 3.])):
            with self.subTest(direction=direction):
                witness = report[direction]
                self.assertIs(witness["meetsRequestedMargin"], True)
                self.assertEqual(witness["sphereCenterRootRelativeGu"], destination)
                self.assertAlmostEqual(witness["separationGu"], 10.)
                self.assertAlmostEqual(witness["overlapGu"], 2.)
        json.dumps(report, allow_nan=False)

    def test_prior_root_relative_translation_has_no_effect(self):
        translated = deepcopy(self.full)
        bone = translated["bones"][0]
        bone["world"][3] = 500.
        bone["worldToBone"][7] = 250.
        self.assertEqual(self.plan(translated, self.delta), self.plan(self.full, self.delta))

    def test_unchanged_same_node_capsule_blocks_false_overlap_contrast(self):
        profile, full = deepcopy(PROFILE), deepcopy(self.full)
        profile["slots"][3]["node"] = NODE
        capsule(full, 3)["node"] = NODE
        capsule(full, 3)["geometry"] = sphere(6.)
        report = self.plan(full, self.delta, profile=profile)
        self.assertEqual(report["slots"], [2, 3])
        self.assertFalse(report[OLD_CLEAR]["meetsRequestedMargin"])
        self.assertLess(report[OLD_CLEAR]["marginUpperBoundGu"], report["requiredMarginGu"])
        self.assertTrue(report[OLD_OVERLAP]["meetsRequestedMargin"])

    def test_upper_bound_rules_out_requested_margin_after_small_displacement(self):
        capsule(self.delta, 2)["geometry"] = sphere(.25)
        report = self.plan(self.full, self.delta)
        for direction in (OLD_CLEAR, OLD_OVERLAP):
            with self.subTest(direction=direction):
                witness = report[direction]
                self.assertFalse(witness["meetsRequestedMargin"])
                self.assertAlmostEqual(witness["marginUpperBoundGu"], .25)
                self.assertLessEqual(witness["bestSampledMarginGu"], witness["marginUpperBoundGu"])
                self.assertLess(witness["marginUpperBoundGu"], report["requiredMarginGu"])

    def test_full_fallback_and_unchanged_node_are_inadmissible(self):
        fallback = receipt(44, 200, previous=40, application="full")
        capsule(fallback, 2)["geometry"] = sphere(6.)
        with self.assertRaisesRegex(ValueError, "Host delta path"):
            self.plan(self.full, fallback)
        with self.assertRaisesRegex(ValueError, "no changed slot"):
            self.plan(self.full, self.delta, node="TailBone03")

    def test_nonuniform_current_attachment_scale_is_refused(self):
        bone = self.delta["bones"][0]
        bone["world"][10] = 3.
        bone["worldToBone"][10] = 1. / 3.
        bone["worldToBone"][11] = -1.
        with self.assertRaisesRegex(ValueError, "uniform scale"):
            self.plan(self.full, self.delta)

    def test_reachable_search_can_choose_a_different_qualifying_point(self):
        clear = [{"p1": [0., 0., 0.], "p2": [0., 0., 0.], "radius": 1.}]
        overlap = [{"p1": [6., 0., 0.], "p2": [6., 0., 0.], "radius": 1.}]
        unrestricted = contrast(clear, overlap, .25)
        limited = contrast(clear, overlap, .25, lambda points: points[:, 0] <= 5.5)
        self.assertTrue(limited["meetsRequestedMargin"])
        self.assertEqual(limited["sphereCenterRootRelativeGu"], [5.5, 0., 0.])
        self.assertLess(limited["bestSampledMarginGu"], unrestricted["bestSampledMarginGu"])
        self.assertEqual(limited["marginUpperBoundGu"], unrestricted["marginUpperBoundGu"])
        empty = contrast(clear, overlap, .25, lambda points: points[:, 0] < 0.)
        self.assertFalse(empty["meetsRequestedMargin"])
        self.assertIsNone(empty["sphereCenterRootRelativeGu"])


if __name__ == "__main__":
    unittest.main()
