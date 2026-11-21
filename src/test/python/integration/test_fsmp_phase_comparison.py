import copy
import unittest

if __package__:
    from .fsmp_phase_comparison import P1_ROLES, PHASES, ROLES, compare, observe_passive_admission
    from .fsmp_phase_observation import observe_window, summarize_replay
else:
    from fsmp_phase_comparison import P1_ROLES, PHASES, ROLES, compare, observe_passive_admission
    from fsmp_phase_observation import observe_window, summarize_replay


def window(*, active=False, left=.008, right=.006):
    incoming = dict.fromkeys(ROLES, (0., 0., 0.))
    written = dict(incoming, leftP1=(left, 0., 0.), rightP1=(right, 0., 0.))
    entry = 50 if active else 10
    return {
        "scope": ("run", "provider", "actor", "role-binding"),
        "forceApplied": active,
        "incomingParentLocal": {role: (role + "-parent", role + "-local") for role in ROLES},
        "solverSteps": (.016, .012),
        "phaseQpc": {phase: entry + 5 * index for index, phase in enumerate(PHASES)},
        "worldByPhase": dict(zip(PHASES, (incoming.copy(), incoming.copy(), written, incoming.copy()))),
    }


class PhaseComparisonTests(unittest.TestCase):
    def test_passive_provider_baseline_checks_absolute_solver_components(self):
        def role(name, anchor):
            return {"name": name, "flags": 2 if anchor else 0, "inverseMass": 0. if anchor else 20.,
                    "engineScale": 1., "pre": [0.] * 12, "post": [0.] * 12}

        rows = [{} for _ in range(11)] + [role(name, i % 2 == 0) for i, name in enumerate(P1_ROLES)]
        rows[-1]["post"][-3:] = [.006, .006, .006]
        self.assertTrue(observe_passive_admission(rows)["stationary"])
        rows[-1]["post"][-3:] = [-.009765625, 0., 0.]
        verdict = observe_passive_admission(rows)
        self.assertFalse(verdict["stationary"])
        self.assertEqual(verdict["failedRoles"], [P1_ROLES[-1]])
        rows[-1]["inverseMass"] = 10.
        with self.assertRaisesRegex(ValueError, "different rig type, mass or scale"):
            observe_passive_admission(rows)

    def test_left_response_can_disappear_before_outer_return(self):
        result = compare(window(), window(active=True, left=.048))
        self.assertAlmostEqual(result["phases"]["afterStockWrite"]["activeMinusPassiveGU"]["left"][0], .04)
        self.assertEqual(result["phases"]["afterOuterUpdate"]["activeMinusPassiveGU"]["left"], (0., 0., 0.))

    def test_individual_window_retains_motion_when_pair_timing_differs(self):
        quiet, pulse = window(left=0., right=0.), window(active=True, left=.055, right=0.)
        pulse["worldByPhase"]["afterOuterUpdate"]["leftP1"] = (.055, 0., 0.)
        pulse["solverSteps"] = (.016, .013)
        with self.assertRaisesRegex(ValueError, "same two observed positive solver step durations"):
            compare(quiet, pulse)
        replay = {"observedWindows": [quiet, pulse], "initialMatch": {}, "renderedMotionMeasured": False,
                  "comparisonUnavailable": "Mismatched solver steps"}
        observed_replay = summarize_replay(replay)
        self.assertEqual(observed_replay["comparisonUnavailable"], "Mismatched solver steps")
        self.assertFalse(observed_replay["renderedMotionMeasured"])
        self.assertNotEqual(observed_replay["passiveSolverStepsS"], observed_replay["activeSolverStepsS"])
        for observed, left in ((observed_replay["passive"], 0.), (observed_replay["active"], .055)):
            self.assertEqual(observed["rightStockControl"], {
                "absoluteRightStockWriteGU": 0., "absoluteRightLimitGU": .01, "absoluteRightGateMet": True,
            })
            for phase in PHASES[2:]:
                self.assertEqual(observed["phases"][phase]["left"]["relativeDeltaGU"], (left, 0., 0.))
            self.assertNotIn("activeMinusPassiveGU", observed["phases"]["afterOuterUpdate"])
        with self.assertRaisesRegex(ValueError, "same scope"):
            summarize_replay(dict(replay, observedWindows=[pulse, quiet]))

    def test_absolute_gate_is_independent_of_passive_subtraction(self):
        result = compare(window(right=.011), window(active=True, right=.011))
        self.assertEqual(result["phases"]["afterStockWrite"]["activeMinusPassiveGU"]["right"], (0., 0., 0.))
        self.assertFalse(result["rightStockControls"]["passive"]["absoluteRightGateMet"])
        self.assertFalse(result["rightStockControls"]["active"]["absoluteRightGateMet"])
        self.assertTrue(compare(window(), window(active=True, right=.01))[
            "rightStockControls"]["active"]["absoluteRightGateMet"])

    def test_mismatched_owner_input_or_duration_cannot_be_scored(self):
        for key, changed in (
            ("scope", ("second-run", "provider", "actor", "role-binding")),
            ("forceApplied", False),
            ("incomingParentLocal", dict.fromkeys(ROLES, ("other-parent", "other-local"))),
            ("solverSteps", (.016, .016)),
        ):
            with self.subTest(key=key), self.assertRaises(ValueError):
                compare(window(), dict(window(active=True), **{key: changed}))
        for steps in ((), (.016,), (.016, True), (.016, float("inf"))):
            with self.subTest(steps=steps), self.assertRaisesRegex(ValueError, "solver step durations"):
                compare(dict(window(), solverSteps=steps), dict(window(active=True), solverSteps=steps))

    def test_unmatched_or_incomplete_outer_update_cannot_be_scored(self):
        pulse = window(active=True)
        missing = copy.deepcopy(pulse)
        del missing["worldByPhase"]["afterOuterUpdate"]
        with self.assertRaisesRegex(ValueError, "boundary must have a pose"):
            compare(window(), missing)
        missing = copy.deepcopy(pulse)
        missing["phaseQpc"]["outerEntry"] = 20
        with self.assertRaisesRegex(ValueError, "passive window must finish"):
            compare(window(), missing)
        pulse["worldByPhase"]["outerEntry"]["rightP1"] = (.01, 0., 0.)
        with self.assertRaisesRegex(ValueError, "Incoming world poses"):
            compare(window(), pulse)

    def test_anchor_motion_cannot_pass_stock_control(self):
        quiet, pulse = window(), window(active=True)
        pulse["worldByPhase"]["afterStockWrite"]["rightAnchor"] = (.01, 0., 0.)
        with self.assertRaisesRegex(ValueError, "anchor trajectories"):
            compare(quiet, pulse)
        quiet["worldByPhase"]["afterStockWrite"]["rightAnchor"] = (.01, 0., 0.)
        with self.assertRaisesRegex(ValueError, "stationary anchors"):
            compare(quiet, pulse)
        self.assertIsNone(observe_window(quiet)["rightStockControl"])
