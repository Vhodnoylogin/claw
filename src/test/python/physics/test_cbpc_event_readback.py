import copy
import unittest

from cbpc_event_readback import Audience, score


class CbpcEventControls(unittest.TestCase):
    def setUp(self):
        self.audience = Audience(123, 27, 2, 0xFF000899, 0x0B000800, 0x0A01A5C6, "Male", "TailBone01")
        self.holds = {"nearBefore": (120, 130), "far": (140, 150), "nearAfter": (160, 170),
                      "nearDetached": (180, 190)}
        self.snapshot = {
            "schema": "claw-vr-cbpc-events/1", "status": "sealed", "pid": 123, "nonce": 27, "generation": 2,
            "actorFormId": 0xFF000899, "baseFormId": 0x0B000800, "cellFormId": 0x0A01A5C6,
            "qpcFrequency": 10000000, "requestedQpc": 99, "armedQpc": 100, "closedQpc": 200,
            "observation": "skse_mod_callback", "lastSequence": 2, "dropped": 0, "unattributed": 0,
            "sealedWithoutLocalDrops": True, "events": [self.event(1, 125), self.event(2, 165)],
        }

    def event(self, sequence, qpc):
        return {"sequence": sequence, "qpc": qpc, "numArg": .325, "eventName": "CBPCPlayerCollisionWithMaleEvent",
                "senderFormId": self.audience.actor, "strArg": "TailBone01"}

    def test_positive_controls_and_silent_holds_only_qualify_callback(self):
        result = score(self.snapshot, self.audience, self.holds, .3, 10)
        self.assertEqual(result["status"], "qualified-emission-contrast")
        self.assertEqual(result["qualifiedHeldEventCounts"], {"nearBefore": 1, "far": 0, "nearAfter": 1, "nearDetached": 0})
        self.assertFalse(result["solverPairCoverageQualified"])
        self.assertFalse(result["havokContactQualified"])

    def test_far_or_detached_emission_refuses_the_contrast(self):
        for tick, index in ((145, 1), (185, 2)):
            with self.subTest(tick=tick):
                snap = copy.deepcopy(self.snapshot)
                snap["events"].insert(index, self.event(0, tick))
                snap["lastSequence"] += 1
                for i, row in enumerate(snap["events"], 1):
                    row["sequence"] = i
                result = score(snap, self.audience, self.holds, .3, 10)
                self.assertEqual(result["status"], "insufficient-emission-contrast")

    def test_zero_events_without_positive_controls_refuses(self):
        snap = {**self.snapshot, "lastSequence": 0, "events": []}
        result = score(snap, self.audience, self.holds, .3, 10)
        self.assertEqual(result["status"], "insufficient-emission-contrast")

    def test_wrong_owner_incomplete_or_dropped_window_rejected(self):
        for change in ({"nonce": 28}, {"generation": 3}, {"status": "changed_world"}, {"dropped": 1},
                       {"unattributed": 1}, {"lastSequence": 3}, {"closedQpc": 185}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                score({**self.snapshot, **change}, self.audience, self.holds, .3, 10)

    def test_wrong_payload_missed_bounds_or_reordered_callback_rejected(self):
        for change in ({"senderFormId": 0xFF000801}, {"strArg": "TailBone02"}, {"numArg": .1},
                       {"numArg": float("nan")}, {"sequence": 7}, {"qpc": 122}, {"qpc": 205}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                snap = copy.deepcopy(self.snapshot)
                snap["events"][1].update(change)
                score(snap, self.audience, self.holds, .3, 10)

    def test_motion_between_holds_does_not_satisfy_either_control(self):
        snap = {**self.snapshot, "events": [self.event(1, 132), self.event(2, 155)]}
        result = score(snap, self.audience, self.holds, .3, 10)
        self.assertEqual(result["status"], "insufficient-emission-contrast")
        self.assertEqual(result["eventsOutsideHolds"], 2)

    def test_short_far_hold_and_clock_expiry_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "too short"):
            score(self.snapshot, self.audience, {**self.holds, "far": (140, 141)}, .3, 10)
        expiry = self.snapshot["requestedQpc"] + 60 * self.snapshot["qpcFrequency"]
        with self.assertRaisesRegex(ValueError, "expiry"):
            score({**self.snapshot, "closedQpc": expiry}, self.audience, self.holds, .3, 10)

    def test_decimal_threshold_uses_the_providers_float32_value(self):
        snap = copy.deepcopy(self.snapshot)
        for row in snap["events"]:
            row["numArg"] = 0.699999988079071
        self.assertEqual(score(snap, self.audience, self.holds, .7, 10)["status"], "qualified-emission-contrast")
