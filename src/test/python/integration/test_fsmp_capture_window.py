import unittest

if __package__:
    from .fsmp_capture_window import bracket_capture, observe_pose_span
    from .fsmp_phase_comparison import P1_ROLES
else:
    from fsmp_capture_window import bracket_capture, observe_pose_span
    from fsmp_phase_comparison import P1_ROLES


def fixture():
    pose = [1., 0., 0., 0., 1., 0., 0., 0., 1., 0., 0., 0.]
    tokens = dict(zip(P1_ROLES, range(1, 5), strict=True))
    window = {"schemaVersion": 4, "status": "complete", "coherent": True, "awaitingPost": False,
              "callbackDrops": 0, "failureCode": 0, "firstPreQpc": 10, "lastPostQpc": 100,
              "pairedSteps": 900, "pairedStepLimit": 900, "minimumPairedHostTimeStep": .017, "objectCount": 4,
              "objects": [{"token": token, "initialPre": {"world": pose.copy()}, "lastPost": {"world": pose.copy()},
                           "minimumPostWorld": pose.copy(), "maximumPostWorld": pose.copy()} for token in tokens.values()]}
    return window, tokens


class NativeCaptureWindowTests(unittest.TestCase):
    def test_capture_requires_its_complete_interval_in_advancing_window(self):
        observed = observe_pose_span(*fixture())
        limits = {"translation_limit": .002, "rotation_limit": .00001}
        self.assertTrue(bracket_capture(observed, 25, 80, **limits)["sampledPoseStable"])
        for start, end in ((9, 80), (11, 100), (20, 20)):
            with self.subTest(start=start, end=end), self.assertRaisesRegex(ValueError, "complete screenshot request"):
                bracket_capture(observed, start, end, **limits)

    def test_native_extrema_catch_a_moving_pose_with_identical_endpoints(self):
        window, tokens = fixture()
        window["objects"][1]["maximumPostWorld"][9] = .05
        window["objects"][3]["initialPre"]["world"][2] = -.01
        observed = observe_pose_span(window, tokens)
        verdict = bracket_capture(observed, 25, 80, translation_limit=.002, rotation_limit=.00001)
        self.assertFalse(verdict["sampledPoseStable"])
        self.assertEqual(verdict["failedRoles"], [P1_ROLES[1], P1_ROLES[3]])

    def test_no_window_when_pairs_were_lost_or_role_is_unassociated(self):
        window, tokens = fixture()
        for key, value in (("pairedSteps", 899), ("callbackDrops", 1), ("minimumPairedHostTimeStep", 0)):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "lossless"):
                observe_pose_span(dict(window, **{key: value}), tokens)
        with self.assertRaisesRegex(ValueError, "four distinct"):
            observe_pose_span(window, dict.fromkeys(tokens, 1))
