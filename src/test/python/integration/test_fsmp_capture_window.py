import unittest

if __package__:
    from .fsmp_capture_window import bracket_capture, bracket_trace_capture, observe_pose_span
    from .fsmp_phase_comparison import P1_ROLES
else:
    from fsmp_capture_window import bracket_capture, bracket_trace_capture, observe_pose_span
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


class NativeTraceCaptureTests(unittest.TestCase):
    def setUp(self):
        self.rows = []
        for index, x in enumerate((0, .1, .1, .1, 0), 1):
            pose = [1., 0., 0., 0., 1., 0., 0., 0., 1., 0., 0., 0.]
            self.rows.append({"pair": index, "preQpc": 10 * index, "postQpc": 10 * index + 5,
                              **{phase: [{"world": pose.copy()} for _ in P1_ROLES] for phase in ("pre", "post")}})
            self.rows[-1]["pre"][1]["world"][9] = x
            self.rows[-1]["post"][1]["world"][9] = x

    def bracket(self, start, stop):
        return bracket_trace_capture(self.rows, P1_ROLES, start, stop,
                                     translation_limit=.005, rotation_limit=.004)

    def test_selects_the_stable_hold_inside_a_moving_trace(self):
        value = self.bracket(27, 38)
        self.assertTrue(value["sampledPoseStable"])
        self.assertEqual((value["firstPair"], value["lastPair"]), (2, 4))

    def test_picks_up_motion_on_the_enclosing_pairs(self):
        value = self.bracket(23, 38)
        self.assertFalse(value["sampledPoseStable"])
        self.assertEqual(value["failedRoles"], [P1_ROLES[1]])

    def test_refuses_missing_or_unenclosed_pairs(self):
        with self.assertRaisesRegex(ValueError, "complete capture interval"):
            self.bracket(14, 38)
        self.rows[2]["pair"] += 1
        with self.assertRaisesRegex(ValueError, "contiguous"):
            self.bracket(27, 38)
