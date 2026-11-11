"""Run the production sampler against independent transport and timer clocks."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_fsmp_owned_case import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integration"))
try:
    import fsmp_probe as scene
    import owned_anchors as anchors
finally:
    sys.path.pop(0)


class SamplingClockTests(unittest.TestCase):
    def collect(self, roundtrip):
        with tempfile.TemporaryDirectory() as directory:
            session = Session(directory)
            clock = [13.003]
            observed = {}
            state = {"pulses": {}}

            def observe(name):
                # Independent transport takes time, even with no explicit sleep.
                clock[0] += roundtrip
                session.phase(name)
                value = session.tool("inspect", {})
                if "-pulse-sample-" in name:
                    family = name.split("-pulse-sample-", 1)[1].rsplit("-", 1)[0]
                    observed.setdefault(family, []).append(clock[0])
                return value

            def sleep(seconds):
                self.assertGreaterEqual(seconds, 0)
                clock[0] += seconds

            owned = anchors.OwnedAnchors("0xFF001234", "male", "CLAW.FSMPProbe.clock", state,
                observe=observe,
                receipt=lambda name, script, function, args: session.tool("papyrus", {
                    "script": script, "function": function, "args": copy.deepcopy(args)}),
                wait=lambda *args: None, persist=lambda: None)
            owned.capture()
            owned.apply([0., 0., 0.])
            baseline = scene.snapshot(observe("baseline"), "0xFF001234", "male")
            spec = {"holdSeconds": .12, "samples": 25,
                    "samplePeriodSeconds": .1, "minGapSeconds": .04}
            # Coarse lifecycle time must not schedule samples or be subtracted
            # from QPC. This catches an accidental mixed-clock regression.
            with patch.object(anchors.time, "monotonic", side_effect=AssertionError("coarse clock used")):
                owned.collect_phase("active", spec, baseline, sleep=sleep, clock=lambda: clock[0])
            self.assertEqual(set(observed), set(owned.names))
            return observed

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
