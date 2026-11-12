"""Run the production sampler against independent transport and timer clocks."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_fsmp_owned_case import Session
from test_fsmp_pulse import fixture as pulse_fixture, pulse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integration"))
try:
    import fsmp_probe as scene
    import owned_anchors as anchors
finally:
    sys.path.pop(0)


class SamplingClockTests(unittest.TestCase):
    def collect(self, roundtrip, *, checkpoint_cost=0., failure=None, details=False):
        with tempfile.TemporaryDirectory() as directory:
            session = Session(directory)
            clock = [13.003]
            observed = {}
            state = {"pulses": {}}
            trace, holds = [], []
            moved, returned, checkpointed = {}, {}, set()
            collecting = False

            def observe(name):
                if collecting:
                    trace.append(("observe", name))
                    for family, row in state["pulses"]["active"].items():
                        if (name == "anchor-AddNodeTransformPosition-" + family + "-guard"
                                and "moved" in row and "returned" not in row):
                            returned[family] = clock[0]
                # Independent transport takes time, even with no explicit sleep.
                clock[0] += roundtrip
                session.phase(name)
                value = session.tool("inspect", {})
                if "-pulse-moved-" in name:
                    family = name.split("-pulse-moved-", 1)[1]
                    moved[family] = clock[0]
                    if failure == "validation":
                        node = next(row for row in value["nodes"] if row["name"] == family)
                        node["world"]["translation"][0] += .01
                if "-pulse-sample-" in name:
                    family = name.split("-pulse-sample-", 1)[1].rsplit("-", 1)[0]
                    observed.setdefault(family, []).append(clock[0])
                return value

            def sleep(seconds):
                self.assertGreaterEqual(seconds, 0)
                if any("moved" in row and "returned" not in row for row in state["pulses"].get("active", {}).values()):
                    holds.append(seconds)
                clock[0] += seconds

            def receipt(name, script, function, args):
                if collecting:
                    trace.append(("native", script, function, copy.deepcopy(args)))
                    if failure == "return" and function == "AddNodeTransformPosition" and args[-1] == [0., 0., 0.]:
                        raise TimeoutError("synthetic zero-return deadline")
                return session.tool("papyrus", {"script": script, "function": function, "args": copy.deepcopy(args)})

            def persist():
                if not collecting:
                    return
                intent = state.get("intent")
                trace.append(("persist", intent.get("function") if intent else None,
                              bool(intent and "nativeResult" in intent)))
                for family, row in state["pulses"]["active"].items():
                    if "moved" in row and family not in checkpointed:
                        checkpointed.add(family)
                        clock[0] += checkpoint_cost
                        if failure == "checkpoint":
                            raise OSError("synthetic moved checkpoint failure")

            owned = anchors.OwnedAnchors("0xFF001234", "male", "CLAW.FSMPProbe.clock", state,
                observe=observe,
                receipt=receipt, wait=lambda *args: None, persist=persist)
            owned.capture()
            owned.apply([0., 0., 0.])
            baseline = scene.snapshot(observe("baseline"), "0xFF001234", "male")
            spec = {"holdSeconds": .12, "samples": 25,
                    "samplePeriodSeconds": .1, "minGapSeconds": .04}
            collecting = True
            error = None
            # Coarse lifecycle time must not schedule samples or be subtracted
            # from QPC. This catches an accidental mixed-clock regression.
            with patch.object(anchors.time, "monotonic", side_effect=AssertionError("coarse clock used")):
                try:
                    owned.collect_phase("active", spec, baseline, sleep=sleep, clock=lambda: clock[0])
                except BaseException as caught:
                    if failure is None:
                        raise
                    error = caught
            if details:
                return {"observed": observed, "trace": trace, "moved": moved, "returned": returned,
                        "holds": holds, "state": state, "error": error}
            self.assertEqual(set(observed), set(owned.names))
            return observed

    def test_checkpoint_cost_consumes_wait_without_changing_actions_or_samples(self):
        baseline = self.collect(0., details=True)
        for cost in (.02, .12, .155):
            with self.subTest(checkpoint_seconds=cost):
                result = self.collect(0., checkpoint_cost=cost, details=True)
                self.assertEqual(result["trace"], baseline["trace"])
                self.assertEqual(set(result["observed"]), set(result["moved"]))
                for family, at in result["moved"].items():
                    self.assertAlmostEqual(result["returned"][family] - at, max(.12, cost), places=10)
                    self.assertEqual(len(result["observed"][family]), 25)
                for seconds in result["holds"]:
                    self.assertAlmostEqual(seconds, max(0., .12 - cost), places=10)

    def test_every_native_write_keeps_intent_reply_and_clear_checkpoints(self):
        trace = self.collect(0., details=True)["trace"]
        for index, event in enumerate(trace):
            if event[0] == "native" and event[2] in ("AddNodeTransformPosition", "UpdateNodeTransform"):
                self.assertEqual(trace[index - 1], ("persist", event[2], False))
                self.assertEqual(trace[index + 1], ("persist", event[2], True))
                self.assertEqual(trace[index + 2], ("persist", None, False))

    def test_validation_checkpoint_and_return_exceptions_propagate_before_sampling(self):
        for failure, error, message in (("validation", ValueError, "displacement missing/wrong"),
                                        ("checkpoint", OSError, "moved checkpoint failure"),
                                        ("return", TimeoutError, "zero-return deadline")):
            with self.subTest(boundary=failure):
                result = self.collect(0., failure=failure, details=True)
                self.assertIsInstance(result["error"], error)
                self.assertIn(message, str(result["error"]))
                self.assertEqual(result["observed"], {})
                native = [event for event in result["trace"] if event[0] == "native"]
                if failure == "return":
                    self.assertEqual(native[-1][2], "AddNodeTransformPosition")
                    self.assertEqual(native[-1][3][-1], [0., 0., 0.])
                    self.assertTrue(result["state"]["quarantined"])
                else:
                    self.assertTrue(all(event[3][-1] != [0., 0., 0.] for event in native if event[2] == "AddNodeTransformPosition"))

    def test_slow_checkpoint_does_not_rebase_or_relax_producer_hold_gates(self):
        protocol = copy.deepcopy(pulse.protocol())
        result = self.collect(0., checkpoint_cost=.7, details=True)
        self.assertTrue(all(seconds == 0. for seconds in result["holds"]))
        for family, at in result["moved"].items():
            self.assertAlmostEqual(result["returned"][family] - at, .7, places=10)
        with self.assertRaisesRegex(ValueError, "hold duration outside declared range"):
            pulse.score(pulse_fixture(holds={phase: .7 for phase in pulse.probe.PHASES}))
        incomparable = pulse.score(pulse_fixture(holds={"active": .2, "stopped": .4, "restarted": .2}))
        self.assertFalse(incomparable["excitationTimingComparable"])
        self.assertEqual(incomparable["status"], "unconfirmed")
        self.assertEqual(pulse.score(pulse_fixture(holds={phase: .5 for phase in pulse.probe.PHASES}))["status"],
                         "sampled-pulse-contrast-observed")
        self.assertEqual(pulse.protocol(), protocol)

    def test_qpc_sampling_keeps_fractional_cadence_without_coarse_clock(self):
        for values in self.collect(.013).values():
            self.assertEqual(len(values), 25)
            for before, after in zip(values, values[1:]):
                self.assertAlmostEqual(after - before, .1, places=10)

    def test_transport_overrun_never_creates_catch_up_burst(self):
        for values in self.collect(.15).values():
            self.assertEqual(len(values), 25)
            for before, after in zip(values, values[1:]):
                self.assertGreaterEqual(after - before + 1e-12, .19)


if __name__ == "__main__":
    unittest.main()
