"""Exercise the capture against the preserved tool ledger format."""

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from run_tail_refit import Capture
from tail_refit_morph import MORPH_SCRIPT, TEST_KEY, UnconfirmedMutation
from test_tail_refit import ACTOR, BASIS, BASE, CELL, HANDLE, MODEL, PID, make_case
from verify_tail_refit import CBPC, EVENTS, NATIVE, NODE, PHASES, POSE, QPC, SLOT_IDS, Subject


class Transport:
    def __init__(self, path):
        self.path = path
        self.now = 1.
        self.phase, self.sample, self.nonce = 0, 0, 9
        self.armed, self.event, self.contact = 0, 0, None
        self.fit_latency = 0.
        self.slots, self.has_key = set(), False
        self.ended = False
        self.pose_opened = None
        self.pose_ended = None
        self.late_attach = False
        manifest, ledger = make_case()
        self.pose_template = json.loads(ledger[manifest["phases"][0]["poseBefore"]]["result"]["returned"])
        self.inspect_template = ledger[manifest["unattached"][0]]["result"]
        self.describe = ledger[manifest["morph"]["describe"]]["result"]
        self.uncertain = False

    def monotonic(self):
        return self.now

    def sleep(self, wait):
        self.now += wait

    def tick(self):
        return round(self.now * QPC)

    def tool(self, name, args, *, timeout, deadline):
        if not 0 < timeout <= deadline - self.now or args.get("timeoutMs", 0) > (deadline - self.now) * 1000:
            raise AssertionError("Request exceeded its remaining observation window")
        self.sleep(.025)
        if name == "inspect":
            self.sample += 1
            result = deepcopy(self.inspect_template)
            result.update(sampleId=self.sample, producerFrame=self.sample * 2, producerMonotonicNs=self.tick() * 100)
            if self.phase == 1 and len(self.slots) == 4 and self.contact is None:
                self.contact = self.tick()
        elif args["action"] == "describe":
            result = self.describe
        else:
            value, kind = self.method(args["script"], args["function"], args["args"])
            result = {"called": True, "returnedType": kind, "returned": value}
            if self.late_attach and args["function"] == "AttachColliderCapsule":
                self.now = deadline + .01
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"kind": "tool", "tool": name, "args": args, "result": result}) + "\n")
        return result

    def method(self, script, method, args):
        if script == EVENTS:
            if method == "GetCaptureState":
                return json.dumps({"schema": "claw-vr-cbpc-events/1", "status": "idle", "generation": 1,
                                   "pid": PID, "loading": False, "sinkRegistered": True}), "string"
            if method == "Arm":
                self.armed = self.tick()
            if method == "Read":
                return json.dumps({
                    "schema": "claw-vr-cbpc-events/1", "observation": "skse_mod_callback",
                    "status": "sealed", "pid": PID, "nonce": self.nonce, "generation": 1,
                    "actorFormId": ACTOR, "baseFormId": BASE, "cellFormId": CELL,
                    "sealedWithoutLocalDrops": True, "dropped": 0, "unattributed": 0, "lastSequence": 1,
                    "qpcFrequency": QPC, "requestedQpc": self.armed, "armedQpc": self.armed, "closedQpc": self.tick(),
                    "events": [{"sequence": 1, "qpc": self.contact, "eventName": "CBPCPlayerCollisionWithMaleEvent",
                                "strArg": NODE, "senderFormId": ACTOR, "numArg": .45}],
                }), "string"
            return True, "bool"
        if script == POSE:
            if method == "BeginNpcTailRefit":
                assert self.pose_opened is None
                self.pose_opened = self.now
                return json.dumps({"status": "pending"}), "string"
            if self.pose_opened is None or self.now >= self.pose_opened + 30.:
                return json.dumps({"status": "refused", "reason": "expired"}), "string"
            if method in ("SampleNpc", "EndNpc"):
                if method == "EndNpc":
                    self.ended = True
                    self.pose_ended = self.now
                return json.dumps({"status": "pending"}), "string"
            if method == "ReadPhysicsSnapshot":
                if self.tick() < self.event:
                    return json.dumps({"status": "pending"}), "string"
                return json.dumps({"schema": "claw-vr-npc-pose/1", "status": "ready", "nonce": self.nonce,
                                   "pid": PID, "qpcFrequency": QPC, "actor": ACTOR, "base": BASE, "loadEpoch": 1,
                                   "runtimeHandle": HANDLE, "rootToken": self.nonce, "snapshotToken": 15 + self.phase,
                                   "eventQpc": self.event}), "string"
            pose = deepcopy(self.pose_template)
            pose.update(nonce=self.nonce, sequence=args[1], status="ended" if self.ended else "ready")
            pose["sample"].update(rootToken=self.nonce, qpcBegin=self.tick() - 2, qpcEnd=self.tick() - 1)
            pose["sample"]["effectiveMorphs"]["CLAWTailLength"] = float(self.has_key)
            return json.dumps(pose), "string"
        if script == NATIVE:
            if method == "GetModelIdentity":
                return MODEL["modelIdentity"], "string"
            if method == "BeginSessionToken":
                return "owned-physics-session", "string"
            if method == "EndSession":
                return "retired-physics-session", "string"
            if method == "RegisterQualifiedActor":
                self.event = self.tick() + round(self.fit_latency * QPC)
            if method == "UnregisterActor":
                return None, "none"
            if method == "ActorCurrent":
                return False, "bool"
            if method == "GetValues":
                return [float(self.has_key)] + [0.] * 30, "float[]"
            if method == "GetWeight":
                return .5, "float"
            if method == "GetCapsule":
                cap = BASIS["capsulesByPhase"][self.phase][SLOT_IDS.index(args[-1])]
                return [*cap["p1"], *cap["p2"], cap["radius"]], "float[]"
            return True, "bool"
        if script == CBPC:
            slot = (args[7] if method == "AttachColliderCapsule" else args[3]) - 0x434C0000
            if method == "AttachColliderCapsule":
                self.slots.add(slot)
                if self.uncertain:
                    raise TimeoutError("unresolved append")
            else:
                self.slots.remove(slot)
            return True, "bool"
        if script != MORPH_SCRIPT:
            raise ValueError("Unexpected script")
        if method == "HasBodyMorph":
            return self.has_key, "bool"
        if method == "GetBodyMorph":
            return float(self.has_key), "float"
        if method != "UpdateModelWeight":
            assert args[1:3] == ["CLAWTailLength", TEST_KEY]
            self.has_key = method == "SetBodyMorph"
            self.phase += 1
            self.event = self.tick() + round(self.fit_latency * QPC)
        return None, "none"


class CaptureTest(unittest.TestCase):
    def test_snapshot_wait_covers_two_native_scan_passes(self):
        with TemporaryDirectory() as root:
            path = Path(root) / "steps.jsonl"
            path.touch()
            tool = Transport(path)
            tool.fit_latency = 4.
            case = Capture(tool.tool, path, Subject(PID, ACTOR, BASE, CELL, 9), MODEL, BASIS,
                           deadline=30., clock=tool)
            manifest, _ = case.run("owned-test-fixture")
            self.assertEqual([phase["token"] for phase in manifest["phases"]], [15, 16, 17])
            self.assertGreater(tool.pose_ended - tool.pose_opened, 12.)
            self.assertLess(tool.pose_ended - tool.pose_opened, 30.)
            self.assertLess(tool.now, 30.)

    def test_near_limit_snapshot_wait_finishes_inside_fixed_hold(self):
        with TemporaryDirectory() as root:
            path = Path(root) / "steps.jsonl"
            path.touch()
            tool = Transport(path)
            tool.fit_latency = 5.8
            case = Capture(tool.tool, path, Subject(PID, ACTOR, BASE, CELL, 9), MODEL, BASIS,
                           deadline=29., clock=tool)
            _, verdict = case.run("owned-test-fixture")
            self.assertEqual(verdict["status"], "qualified-scoped-tail02-refit-evidence")
            self.assertTrue(tool.ended)
            self.assertLess(tool.now, 29.)

    def test_short_controller_window_refuses_before_first_request(self):
        with TemporaryDirectory() as root:
            path = Path(root) / "steps.jsonl"
            path.touch()
            tool = Transport(path)
            case = Capture(tool.tool, path, Subject(PID, ACTOR, BASE, CELL, 9), MODEL, BASIS,
                           deadline=tool.now + 27., clock=tool)
            with self.assertRaisesRegex(ValueError, "fixed controller window"):
                case.run("owned-test-fixture")
            self.assertEqual(path.read_bytes(), b"")

    def test_run_builds_exact_native_index_manifest(self):
        with TemporaryDirectory() as root:
            path = Path(root) / "steps.jsonl"
            path.touch()
            tool = Transport(path)
            case = Capture(tool.tool, path, Subject(PID, ACTOR, BASE, CELL, 9), MODEL, BASIS,
                           deadline=30., clock=tool)
            manifest, verdict = case.run("owned-test-fixture")
            self.assertEqual([verdict["sameNodeCallbacks"][phase] for phase in PHASES], [0, 0, 1, 0, 0])
            self.assertEqual([phase["token"] for phase in manifest["phases"]], [15, 16, 17])
            self.assertFalse(tool.has_key)
            self.assertFalse(tool.slots)
            self.assertTrue(tool.ended)

    def test_unconfirmed_attach_stops_without_replay(self):
        with TemporaryDirectory() as root:
            path = Path(root) / "steps.jsonl"
            path.touch()
            tool = Transport(path)
            tool.uncertain = True
            case = Capture(tool.tool, path, Subject(PID, ACTOR, BASE, CELL, 9), MODEL, BASIS,
                           deadline=30., clock=tool)
            with self.assertRaisesRegex(UnconfirmedMutation, "AttachColliderCapsule"):
                case.run("owned-test-fixture")
            self.assertEqual(case.waiting_on, "AttachColliderCapsule")
            self.assertEqual(tool.slots, {108})

    def test_late_attach_receipt_is_retained_and_never_replayed(self):
        with TemporaryDirectory() as root:
            path = Path(root) / "steps.jsonl"
            path.touch()
            tool = Transport(path)
            tool.late_attach = True
            case = Capture(tool.tool, path, Subject(PID, ACTOR, BASE, CELL, 9), MODEL, BASIS,
                           deadline=30., clock=tool)
            with self.assertRaisesRegex(UnconfirmedMutation, "AttachColliderCapsule"):
                case.run("owned-test-fixture")
            functions = [row["args"].get("function") for row in case.ledger()]
            self.assertEqual(functions.count("AttachColliderCapsule"), 1)
            self.assertNotIn("DetachCollider", functions)
            self.assertFalse(tool.ended)


if __name__ == "__main__":
    unittest.main()
