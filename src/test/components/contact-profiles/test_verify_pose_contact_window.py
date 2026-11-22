"""Synthetic raw-ledger controls for the live pose-contact acceptance join."""
from copy import deepcopy
import json
import unittest

from test_pose_ack import GENERATION, MORPH, PROFILE, lines, receipt
from test_tail_refit import ACTOR, ACTOR_ARG, BASE, CELL, HANDLE, NODE, PID, make_case
from verify_pose_contact_window import ACTIVE, CLOCK, CONTROL, NATIVE, PHASES, POSE, verify


TOKEN = 44
DURATION_US = 100


def set_tail(packet, x):
    capsule = next(item for item in packet["capsules"] if item["slot"] == 2)
    capsule["geometry"] = [x, 0., 0., x, 0., 1., 1.]


def read_payload(ledger, index):
    return json.loads(ledger[index]["result"]["returned"])


def write_payload(ledger, index, value):
    ledger[index]["result"]["returned"] = json.dumps(value)


def fixture():
    legacy, raw = make_case()
    full = receipt(40, 4_800_000)
    delta = receipt(TOKEN, 4_900_000, previous=40, application="delta")
    full["weight"] = delta["weight"] = .5
    set_tail(full, 0.)
    set_tail(delta, 6.)

    ledger = []
    plan = {"schema": "claw-vr-pose-contact-reads/1", "clock": CLOCK, "token": TOKEN, "node": NODE,
            "subject": {"pid": PID, "actor": ACTOR, "base": BASE, "cell": CELL, "generation": GENERATION},
            "capture": {}, "holds": {}, "release": {}}

    def record(row):
        ledger.append(deepcopy(row))
        return len(ledger) - 1

    def typed(script, method, args, result_type, value):
        return record({"tool": "papyrus", "args": {"action": "call", "script": script, "function": method, "args": args},
                       "result": {"called": True, "returnedType": result_type, "returned": value}})

    def frames(name, source):
        indices = []
        for number, old in enumerate(source):
            index = record(raw[old])
            indices.append(index)
            payload = ledger[index]["result"]
            payload["durationUs"] = DURATION_US
            if name == "far":
                payload["vrPicking"]["nodes"]["leftWand"]["world"]["translation"][0] = 16.
            if number == 0 and name == "nearBefore":
                record({"kind": "capture-gap-marker"})
        return indices

    def pose(old):
        sample = read_payload(raw, old)
        sample["sample"]["effectiveMorphs"] = {MORPH: delta["morphs"][0]["value"]}
        return typed(POSE, "ReadNpc", [sample["nonce"], sample["sequence"]], "string", json.dumps(sample))

    def current():
        return typed(NATIVE, "SnapshotCurrent", [ACTOR_ARG, GENERATION, TOKEN], "bool", True)

    plan["modelRead"] = typed(NATIVE, "GetModelIdentity", [], "string", PROFILE["modelIdentity"])
    capture = plan["capture"]
    for key in ("idle", "arm"):
        capture[key] = record(raw[legacy["capture"][key]])
    plan["holds"]["unattachedNear"] = {"frames": frames("unattachedNear", legacy["unattached"])}
    enabled = sum(item["sexMask"] in ("male", "both") for item in PROFILE["slots"])
    plan["ledgerCount"] = typed(CONTROL, "GetLedgerCount", [0], "int", enabled)
    for name, old in zip(ACTIVE, legacy["phases"], strict=True):
        plan["holds"][name] = {"currentBefore": current(), "poseBefore": pose(old["poseBefore"]),
                               "frames": frames(name, old["hold"]), "poseAfter": pose(old["poseAfter"]),
                               "currentAfter": current()}
    plan["release"] = {"call": typed(CONTROL, "ReleaseActor", [0], "int", 0),
                       "count": typed(CONTROL, "GetLedgerCount", [0], "int", 0),
                       "actorCurrent": typed(NATIVE, "ActorCurrent", [ACTOR_ARG], "bool", False)}
    plan["holds"]["nearDetached"] = {"frames": frames("nearDetached", legacy["detached"])}
    for key in ("seal", "read"):
        capture[key] = record(raw[legacy["capture"][key]])
    event = read_payload(ledger, capture["read"])
    template = event["events"][0]
    event["events"] = [{**template, "sequence": i, "qpc": tick}
                       for i, tick in enumerate((50_000_000, 65_000_000, 125_000_000), 1)]
    event["lastSequence"] = len(event["events"])
    write_payload(ledger, capture["read"], event)
    return plan, ledger, (full, delta)


class VerifyPoseContactWindowTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.ledger, self.acks = fixture()

    def verify(self, *extra_acks):
        return verify(self.plan, self.ledger, lines(*self.acks, *extra_acks), PROFILE)

    def hold(self, name="nearBefore"):
        return self.plan["holds"][name]

    def frame(self, i, name="nearBefore"):
        return self.ledger[self.hold(name)["frames"][i]]["result"]

    def test_all_five_phases_join_current_geometry_and_callback(self):
        report = self.verify()
        self.assertEqual(report["status"], "qualified-emission-contrast")
        self.assertEqual((report["actor"], report["token"], report["previousToken"], report["slots"]),
                         (ACTOR, TOKEN, 40, [2]))
        self.assertEqual(list(report["holdQpc"]), list(PHASES))
        self.assertEqual(report["holdQpc"]["nearBefore"], (60_001_010, 76_500_000))
        self.assertEqual(report["worldGapRanges"]["nearBefore"],
                         {"oldGapGu": [2.5, 2.5], "newGapGu": [-3.5, -3.5]})
        self.assertEqual(report["preAppendCallbacks"], 0)
        self.assertEqual(report["qualifiedHeldEventCounts"], {"nearBefore": 1, "far": 0, "nearAfter": 1, "nearDetached": 0})
        self.assertEqual(report["eventsOutsideHolds"], 1)
        self.assertFalse(report["providerShapeInventoryVerified"])
        self.assertFalse(report["perSlotCallbackAttribution"])

    def test_currentness_requires_same_token_and_actor_at_both_boundaries(self):
        for boundary, replacement, message in (
            ("currentBefore", {"args": {**self.ledger[self.hold()["currentBefore"]]["args"],
                                         "args": [ACTOR_ARG, GENERATION, TOKEN - 1]}}, "exact typed"),
            ("currentAfter", {"args": {**self.ledger[self.hold()["currentAfter"]]["args"],
                                        "args": [{"form": "0xFF000869"}, GENERATION, TOKEN]}}, "exact typed"),
            ("currentAfter", {"result": {"called": True, "returnedType": "bool", "returned": False}}, "remain current"),
        ):
            with self.subTest(boundary=boundary, replacement=replacement):
                index = self.hold()[boundary]
                original = self.ledger[index]
                self.ledger[index] = {**original, **replacement}
                with self.assertRaisesRegex(ValueError, message):
                    self.verify()
                self.ledger[index] = original

    def test_pre_append_far_allows_live_selection_of_the_near_waypoint(self):
        holds = self.plan["holds"]
        holds["unattachedFar"] = holds.pop("unattachedNear")
        for index, _ in enumerate(holds["unattachedFar"]["frames"]):
            self.frame(index, "unattachedFar")["vrPicking"]["nodes"]["leftWand"]["world"]["translation"][0] = 16.
        report = self.verify()
        self.assertEqual(report["status"], "qualified-emission-contrast")
        self.assertEqual(report["preAppendPosition"], "unattachedFar")
        self.assertEqual(report["preAppendCallbacks"], 0)

    def test_no_definite_ack_before_native_bracket_is_refused(self):
        before = read_payload(self.ledger, self.hold()["poseBefore"])["sample"]
        self.acks[1]["acknowledgedUs"] = before["qpcBegin"] // 10
        with self.assertRaisesRegex(ValueError, "accepted snapshot window"):
            self.verify()

    def test_initial_publication_cannot_overlap_pre_append_samples(self):
        full = receipt(40, 3_500_000)
        full["weight"] = .5
        set_tail(full, 0.)
        self.acks = (full, self.acks[1])
        with self.assertRaisesRegex(ValueError, "Pre-append samples overlap"):
            self.verify()

    def test_new_publication_during_held_token_is_refused(self):
        newer = receipt(45, 6_500_000, previous=TOKEN, application="delta")
        newer["weight"] = .5
        set_tail(newer, 7.)
        with self.assertRaisesRegex(ValueError, "accepted snapshot window"):
            self.verify(newer)

    def test_callbacks_from_wrong_actor_or_group_and_drops_are_refused(self):
        index = self.plan["capture"]["read"]
        for key, value, message in (
            ("senderFormId", ACTOR + 1, "Unexpected actor"),
            ("strArg", "TailBone03", "Unexpected actor"),
            ("dropped", 1, "Dropped or unattributed"),
        ):
            with self.subTest(key=key):
                payload = read_payload(self.ledger, index)
                altered = deepcopy(payload)
                record = altered["events"][1] if key in ("senderFormId", "strArg") else altered
                record[key] = value
                write_payload(self.ledger, index, altered)
                with self.assertRaisesRegex(ValueError, message):
                    self.verify()
                write_payload(self.ledger, index, payload)

    def test_callback_during_first_observer_task_is_not_credited(self):
        index = self.plan["capture"]["read"]
        event = read_payload(self.ledger, index)
        event["events"][1]["qpc"] = 60_001_009  # one tick before inward start
        write_payload(self.ledger, index, event)
        report = self.verify()
        self.assertEqual(report["status"], "insufficient-emission-contrast")
        self.assertEqual(report["qualifiedHeldEventCounts"]["nearBefore"], 0)
        self.assertEqual(report["eventsOutsideHolds"], 2)

    def test_full_observer_tasks_must_fit_the_sealed_capture(self):
        index = self.plan["capture"]["read"]
        original = read_payload(self.ledger, index)
        for field, tick in (("armedQpc", self.frame(0, "unattachedNear")["producerMonotonicNs"] // 100 + 1),
                            ("closedQpc", self.frame(-1, "nearDetached")["producerMonotonicNs"] // 100 + 1)):
            with self.subTest(field=field):
                write_payload(self.ledger, index, {**original, field: tick})
                with self.assertRaisesRegex(ValueError, "outside the sealed capture"):
                    self.verify()

    def test_contact_before_attach_or_after_retirement_cannot_qualify(self):
        index = self.plan["capture"]["read"]
        original = read_payload(self.ledger, index)
        pre_append = deepcopy(original)
        pre_append["events"][0]["qpc"] = 35_000_000
        write_payload(self.ledger, index, pre_append)
        with self.assertRaisesRegex(ValueError, "pre-append hold"):
            self.verify()
        detached = deepcopy(original)
        detached["events"].append({**detached["events"][-1], "qpc": 155_000_000, "sequence": 4})
        detached["lastSequence"] += 1
        write_payload(self.ledger, index, detached)
        self.assertEqual(self.verify()["status"], "insufficient-emission-contrast")

    def test_stale_world_frame_and_changed_effective_morph_are_refused(self):
        frame = self.frame(1)
        original = frame["producerFrame"]
        frame["producerFrame"] = self.frame(0)["producerFrame"]
        with self.assertRaisesRegex(ValueError, "incoherent actor/Observer"):
            self.verify()
        frame["producerFrame"] = original
        index = self.hold()["poseAfter"]
        pose = read_payload(self.ledger, index)
        pose["sample"]["effectiveMorphs"][MORPH] = .5
        write_payload(self.ledger, index, pose)
        with self.assertRaisesRegex(ValueError, "fitted input vector"):
            self.verify()

    def test_reused_index_and_intervening_driver_action_are_refused(self):
        frames = self.hold()["frames"]
        original = frames[1]
        frames[1] = frames[0]
        with self.assertRaisesRegex(ValueError, "Reused, missing or out-of-order"):
            self.verify()
        frames[1] = original
        self.ledger[frames[0] + 1] = {"kind": "driver", "action": "publish"}
        with self.assertRaisesRegex(ValueError, "interrupted the observed hold"):
            self.verify()

    def test_insufficient_observed_dwell_is_refused(self):
        start = self.frame(0)["producerMonotonicNs"]
        for i in range(1, len(self.hold()["frames"])):
            self.frame(i)["producerMonotonicNs"] = start + i * 1_000_000
        with self.assertRaisesRegex(ValueError, "hold is too short"):
            self.verify()

    def test_failed_retirement_is_refused_even_if_detached_is_silent(self):
        for key, returned in (("call", 6), ("count", 1), ("actorCurrent", True)):
            with self.subTest(key=key):
                result = self.ledger[self.plan["release"][key]]["result"]
                original = result["returned"]
                result["returned"] = returned
                with self.assertRaisesRegex(ValueError, "retirement is unproven"):
                    self.verify()
                result["returned"] = original


if __name__ == "__main__":
    unittest.main()
