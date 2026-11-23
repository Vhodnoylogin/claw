import copy
from dataclasses import replace
import unittest

if __package__:
    from .cbpc_event_readback import Audience, score, score_player, score_se
else:
    from cbpc_event_readback import Audience, score, score_player, score_se


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
        self.assertNotIn("preAppendCallbacks", result)

    def test_named_ear_capsule_requires_matching_callbacks_and_optional_preappend_silence(self):
        ear = "NPC EarL [EarL]Bone01"
        audience = replace(self.audience, bone=ear)
        holds = {"unattachedNear": (100, 110), **self.holds}
        snap = copy.deepcopy(self.snapshot)
        for event in snap["events"]:
            event["strArg"] = ear
        result = score(snap, audience, holds, .3, 10)
        self.assertEqual(result["status"], "qualified-emission-contrast")
        self.assertEqual(result["preAppendCallbacks"], 0)
        self.assertNotIn("unattachedNear", result["qualifiedHeldEventCounts"])
        for bone in ("NPC EarL [EarL]Bone02", "NPC EarR [EarR]Bone01", "earl"):
            with self.subTest(bone=bone), self.assertRaisesRegex(ValueError, "actor, event or group"):
                score(snap, replace(audience, bone=bone), holds, .3, 10)

    def test_preappend_hold_rejects_emission_and_invalid_producer_interval(self):
        hold = {"unattachedNear": (100, 110), **self.holds}
        events = [self.event(sequence, qpc) for sequence, qpc in enumerate((100, 125, 165), 1)]
        for edge in (100, 110):
            with self.subTest(edge=edge), self.assertRaisesRegex(ValueError, "pre-append hold"):
                events[0]["qpc"] = edge
                score({**self.snapshot, "events": events, "lastSequence": 3}, self.audience, hold, .3, 10)
        for interval in ((99, 110), (100, 109), (110, 120)):
            with self.subTest(interval=interval), self.assertRaisesRegex(ValueError, "overlap, are too short"):
                score(self.snapshot, self.audience, {**hold, "unattachedNear": interval}, .3, 10)

    def test_se_slot46_intake_requires_exact_producer_and_both_silence_controls(self):
        audience = replace(self.audience, bone="TailBone03")
        holds = {"unattachedNear": (100, 110), **self.holds}
        transport = {"schema": "claw-se-cbpc-events/1", "runtime": "SkyrimSE-1.7.104"}
        snap = {**self.snapshot, **transport,
                "events": [{**event, "strArg": audience.bone} for event in self.snapshot["events"]]}
        ready = {**transport, "status": "idle", "sinkRegistered": True, "loading": False,
                 "pid": audience.pid, "generation": audience.generation}
        result = score_se(snap, ready, audience, holds, .3, 10)
        self.assertEqual(result["status"], "qualified-emission-contrast")
        self.assertEqual(result["preAppendCallbacks"], 0)
        self.assertEqual(result["qualifiedHeldEventCounts"], {"nearBefore": 1, "far": 0, "nearAfter": 1, "nearDetached": 0})
        self.assertFalse(result["solverPairCoverageQualified"])
        self.assertFalse(result["havokContactQualified"])
        with self.assertRaisesRegex(ValueError, "unsupported"):
            score(snap, audience, holds, .3, 10)
        with self.assertRaisesRegex(ValueError, "unsupported"):
            score_se(self.snapshot, ready, audience, holds, .3, 10)
        with self.assertRaisesRegex(ValueError, "producer receipt"):
            score_se({**snap, "runtime": None}, ready, audience, holds, .3, 10)
        for change in ({"schema": "claw-vr-cbpc-events/1"}, {"runtime": "SkyrimSE-1.6.1170"},
                       {"pid": str(audience.pid)}, {"generation": audience.generation + 1},
                       {"sinkRegistered": False}, {"loading": True}, {"status": "pending"}):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "producer receipt"):
                score_se(snap, {**ready, **change}, audience, holds, .3, 10)
        for phase in ("unattachedNear", "nearDetached"):
            with self.subTest(phase=phase), self.assertRaisesRegex(ValueError, "requires pre-append and detached"):
                score_se(snap, ready, audience, {name: hold for name, hold in holds.items() if name != phase}, .3, 10)

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

    def test_player_self_contact_requires_same_body32_at_seal_and_qualified_silence(self):
        audience = replace(self.audience, actor=0x14, base=7, bone="TailBone02")
        holds = {"unattachedNear": (100, 110), **self.holds}
        fixture = (0x0B000801, 0x0B000800)
        schema = "claw-vr-cbpc-player-events/1"
        body = {"item": fixture[0], "addon": fixture[1], "runtimeHandle": 80, "female": False, "checkedAtSeal": True}
        snapshot = {**self.snapshot, "schema": schema, "actorFormId": audience.actor, "baseFormId": audience.base,
                    "body32": body, "events": [{**event, "strArg": audience.bone, "senderFormId": audience.actor}
                                               for event in self.snapshot["events"]]}
        ready = {"schema": schema, "status": "idle", "pid": audience.pid, "generation": audience.generation,
                 "sinkRegistered": True, "loading": False}

        def score_case(data=snapshot, windows=holds):
            return score_player(data, ready, audience, windows, body32=fixture, runtime_handle=80, minimum_hold_ticks=10)

        result = score_case()
        self.assertEqual(result["status"], "qualified-emission-contrast")
        self.assertFalse(result["solverPairCoverageQualified"])
        self.assertEqual(score_case({**snapshot, "events": [], "lastSequence": 0})["status"], "insufficient-emission-contrast")
        for name, value in (("checkedAtSeal", False), ("runtimeHandle", 81), ("item", fixture[0] + 1), ("female", True)):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "remain current"):
                score_case({**snapshot, "body32": {**body, name: value}})
        with self.assertRaisesRegex(ValueError, "requires matching"):
            score_case(windows=self.holds)

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
