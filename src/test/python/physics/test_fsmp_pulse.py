"""Pulse residual discrimination and evidence/lifecycle negatives; no game IO."""
import copy
import importlib.util
import math
from pathlib import Path
import sys
import unittest

from test_fsmp_probe import fixture as observer_fixture, compose, transform

INTEGRATION = Path(__file__).resolve().parents[1] / "integration"
sys.path.insert(0, str(INTEGRATION))
try:
    import fsmp_pulse as pulse
finally:
    sys.path.remove(str(INTEGRATION))


def fixture(sex="female", missing=(), periods=None, holds=None):
    """Independent forward-transform simulation of a damped zero-return response."""
    template = observer_fixture(sex, effect=False)["baseline"]
    reference = template["refs"][0]["identity"]["form"]
    document = {"reference": reference, "sex": sex, "protocol": pulse.protocol(),
                "stimulus": "xml-anchor-pulse", "receipts": {}, "pulses": {},
                "anchorOriginals": {anchor: {"key": "CLAW.FSMPProbe.synthetic-owned-run", "keysBefore": []}
                                    for anchor in pulse.families(sex)}}
    sample, time = 0, 1_000_000_000

    def observe(delta=.1, moved=None, phase=None, index=0, nodes=()):
        nonlocal sample, time
        sample += 1
        time += round(delta*1e9)
        raw = copy.deepcopy(template)
        raw.update(sampleId=sample, producerMonotonicNs=time)
        by_name = {row["name"]: row for row in raw["nodes"]}
        if moved:
            by_name[moved]["world"] = compose(by_name[moved]["world"], transform(pulse.offset()))
            by_name[moved]["local"] = compose(by_name[moved]["local"], transform(pulse.offset()))
        for node in nodes:
            if phase != "stopped" and node not in missing:
                # World-only translation with a finite decaying impulse. The
                # local animation and now-zero kinematic anchor remain fixed.
                value = .04*math.exp(-index/5)*math.cos(.8*index)
                by_name[node]["world"] = compose(by_name[node]["world"], transform([0., value, 0.]))
        return raw

    def transition(action, previous):
        values = [previous]*len(pulse.probe.drivers(sex))
        document["receipts"][action] = {"previous": values[:], "before": observe(), "after": observe(),
            "nativeResult": {"called": True, "returnedType": "bool[]", "returned": values[:]}}

    def commands(anchor, displacement):
        args = [{"form": reference}, False, sex == "female", anchor]
        return [{"script": "NiOverride", "function": function, "args": values,
                 "nativeResult": {"called": True, "returned": None, "returnedType": "none"}}
                for function, values in (("AddNodeTransformPosition", args + [document["anchorOriginals"][anchor]["key"], displacement]),
                                         ("UpdateNodeTransform", args))]

    document["baseline"] = observe()
    transition("first-off", True)
    transition("reenable", False)
    document["stimulusBaseline"] = observe()
    for phase in pulse.probe.PHASES:
        if phase == "stopped":
            transition("second-off", True)
        elif phase == "restarted":
            transition("restore", False)
        document["pulses"][phase] = {}
        for anchor, nodes in pulse.families(sex).items():
            document["pulses"][phase][anchor] = {
                "beforePulse": observe(), "moved": observe(moved=anchor),
                "returned": observe((holds or {}).get(phase, .2)),
                "samples": [observe((periods or {}).get(phase, .1), phase=phase, index=i, nodes=nodes) for i in range(25)],
                "commands": {"moved": commands(anchor, pulse.offset()), "returned": commands(anchor, [0., 0., 0.])}}
    return document


def first(document, phase="active"):
    return next(iter(document["pulses"][phase].values()))


def node(raw, name):
    return next(row for row in raw["nodes"] if row["name"] == name)


class FsmpPulseTests(unittest.TestCase):
    def test_all_requested_drivers_require_zero_return_contrast_including_translation_only_p1(self):
        for sex, count in (("male", 9), ("female", 11)):
            result = pulse.score(fixture(sex))
            self.assertEqual(result["status"], "sampled-pulse-contrast-observed")
            self.assertEqual(len(result["selectiveChannels"]), count)
            self.assertFalse(result["missingDrivers"])
            self.assertTrue(all(row["channel"] == "translation" for row in result["selectiveChannels"]))
            self.assertFalse(result["solverQualified"])
            self.assertFalse(result["contactQualified"])
            self.assertFalse(result["physicsPhaseObserved"])

    def test_one_absent_p1_stays_unconfirmed_despite_other_ten_responses(self):
        result = pulse.score(fixture(missing=("NPC R Breast P1",)))
        self.assertEqual(result["status"], "unconfirmed")
        self.assertEqual(result["missingDrivers"], ["NPC R Breast P1"])

    def test_common_anchor_driver_movement_after_return_is_rejected(self):
        document = fixture()
        raw = first(document)["samples"][0]
        anchor, drivers = next(iter(pulse.families("female").items()))
        for name in (anchor, *drivers):
            current = node(raw, name)
            current["world"] = compose(current["world"], transform([.01, 0., 0.]))
        with self.assertRaisesRegex(ValueError, "anchor did not return or drifted"):
            pulse.score(document)

    def test_anchor_not_returned_before_sampling_is_rejected(self):
        document = fixture()
        anchor = next(iter(pulse.families("female")))
        node(first(document)["returned"], anchor)["world"]["translation"][0] += .1
        with self.assertRaisesRegex(ValueError, "displacement missing/wrong"):
            pulse.score(document)

    def test_missing_or_uncertain_anchor_write_completion_is_rejected(self):
        for change in ({"called": False}, {"returnedType": "none"}, {"called": True, "returnedType": "none", "returned": None, "error": "denied"}):
            document = fixture()
            first(document)["commands"]["returned"][1]["nativeResult"] = change
            with self.assertRaisesRegex(ValueError, "write completion"):
                pulse.score(document)

    def test_native_state_result_cannot_be_missing_or_integer_booleans(self):
        for native in ({"called": False, "returnedType": "bool[]", "returned": [True]*11},
                       {"called": True, "returnedType": "bool[]", "returned": [1]*11}):
            document = fixture()
            document["receipts"]["first-off"]["nativeResult"] = native
            with self.assertRaises(ValueError):
                pulse.score(document)

    def test_partial_body_gate_is_not_motion_acceptance(self):
        document = fixture()
        document["receipts"]["first-off"]["previous"][-1] = False
        document["receipts"]["first-off"]["nativeResult"]["returned"][-1] = False
        with self.assertRaisesRegex(ValueError, "binding/state gate"):
            pulse.score(document)

    def test_wrong_write_target_key_or_sex_is_rejected(self):
        for index, value in ((0, {"form": "0x00000014"}), (1, 0), (2, False), (4, "foreign-key")):
            document = fixture()
            first(document)["commands"]["moved"][0]["args"][index] = value
            with self.assertRaisesRegex(ValueError, "write completion/arguments"):
                pulse.score(document)

    def test_dynamic_local_animation_is_not_residual_physics(self):
        document = fixture()
        node(first(document)["samples"][0], pulse.probe.FEMALE[0])["local"]["translation"][0] += .1
        with self.assertRaisesRegex(ValueError, "Local animation"):
            pulse.score(document)

    def test_parent_control_movement_is_rejected(self):
        document = fixture()
        node(first(document)["samples"][0], pulse.probe.CONTROL[1])["world"]["translation"][0] += .1
        with self.assertRaisesRegex(ValueError, "control parent moved"):
            pulse.score(document)

    def test_root_motion_is_rejected(self):
        document = fixture()
        first(document)["samples"][0]["refs"][0]["sceneTransform"]["translation"][0] += .1
        with self.assertRaisesRegex(ValueError, "root moved"):
            pulse.score(document)

    def test_epoch_change_or_replayed_sample_is_rejected(self):
        for field, value in (("sessionId", "different-owner"), ("producerMonotonicNs", 1), ("sampleId", 1)):
            document = fixture()
            first(document)["samples"][0][field] = value
            with self.assertRaises(ValueError):
                pulse.score(document)

    def test_sampling_must_follow_completed_zero_return(self):
        document = fixture()
        first(document)["samples"][0]["producerMonotonicNs"] = first(document)["returned"]["producerMonotonicNs"]
        with self.assertRaisesRegex(ValueError, "nonadvancing"):
            pulse.score(document)

    def test_declared_hold_and_read_cadence_limits_are_enforced(self):
        for holds, periods in (({"active": .05}, None), ({"active": .7}, None),
                               (None, {"active": .03}), (None, {"active": .21})):
            with self.assertRaisesRegex(ValueError, "declared range"):
                pulse.score(fixture(holds=holds, periods=periods))

    def test_incomparable_phase_hold_or_mean_cadence_remains_unconfirmed(self):
        for holds, periods in (({"stopped": .4}, None), (None, {"stopped": .16})):
            result = pulse.score(fixture(holds=holds, periods=periods))
            self.assertFalse(result["excitationTimingComparable"])
            self.assertEqual(result["status"], "unconfirmed")

    def test_protocol_cannot_change_after_observations(self):
        document = fixture()
        document["protocol"]["maxGapSeconds"] = 5.
        with self.assertRaisesRegex(ValueError, "absent or changed"):
            pulse.score(document)

    def test_initial_key_set_cannot_be_foreign_or_unobserved(self):
        for initial in ({"keysBefore": ["foreign-owner"]}, {}):
            document = fixture()
            anchor = next(iter(pulse.families("female")))
            document["anchorOriginals"][anchor] = {"key": "CLAW.FSMPProbe.synthetic-owned-run", **initial}
            with self.assertRaisesRegex(ValueError, "initially empty key sets"):
                pulse.score(document)

    def test_stationary_world_with_returned_anchor_is_unconfirmed(self):
        result = pulse.score(fixture(missing=pulse.probe.FEMALE))
        self.assertEqual(result["status"], "unconfirmed")
        self.assertEqual(len(result["missingDrivers"]), 11)

    def test_constant_post_return_displacement_is_not_read_only_motion(self):
        document = fixture()
        for phase in ("active", "restarted"):
            for group in document["pulses"][phase].values():
                first_nodes = copy.deepcopy(group["samples"][0]["nodes"])
                for raw in group["samples"]:
                    raw["nodes"] = copy.deepcopy(first_nodes)
        result = pulse.score(document)
        self.assertEqual(result["status"], "unconfirmed")
        self.assertEqual(len(result["missingDrivers"]), 11)


if __name__ == "__main__":
    unittest.main()
