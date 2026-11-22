"""Exercise the admitted full Host capture against the original ledger contract."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from run_pose_contact import PoseContactCapture
from tail_refit_morph import UnconfirmedMutation
from test_pose_ack import GENERATION, MORPH, PROFILE, lines, receipt
from test_tail_refit import ACTOR, ACTOR_ARG, BASE, CELL, HANDLE, NODE, PID, make_case
from test_verify_pose_contact_window import TOKEN, set_tail
from verify_pose_contact_window import CONTROL
from verify_tail_refit import EVENTS, NATIVE, POSE, QPC, Subject


NONCE = 77
CAPTURE_GENERATION = 5
EVIDENCE = "admitted fixture and owned provider scope"
FAR = (16., 0., 0.)
ACTIVE_SLOTS = sum(slot["sexMask"] in ("male", "both") for slot in PROFILE["slots"])


class AdmittedExecutor:
    def __init__(self, directory):
        self.path = directory / "steps.jsonl"
        self.ack_log = directory / "CLAWDistribution.log"
        self.profile = directory / "fitted-capsules.json"
        self.ack_log.write_text("", encoding="utf-8")
        self.profile.write_text(json.dumps(PROFILE), encoding="utf-8")
        self.append({"kind": "admitted-executor-setup"})
        case, rows = make_case()
        self.scene = rows[case["unattached"][0]]["result"]
        self.pose = json.loads(rows[case["phases"][0]["poseBefore"]]["result"]["returned"])
        self.now, self.frame, self.position_frame = 1., 0, 0
        self.moves, self.mutations, self.callbacks = [], [], []
        self.arm_state = "idle"
        self.requested = self.armed = self.closed = None
        self.attached = self.ended = False
        self.active_pose = 0
        self.current_center = FAR
        self.timeout_on = self.unconfirmed_move = None
        self.partial_delta = False

    def append(self, row):
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row) + "\n")

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds

    def tick(self):
        return round(self.now * QPC)

    def position(self, phase, point, *, deadline):
        if phase == "far" and point is not None or phase == "near" and point is None:
            raise AssertionError("Unexpected guarded driver request")
        self.current_center = FAR if phase == "far" else tuple(point)
        self.position_frame = 0
        self.moves.append((phase, self.current_center))
        self.append({"kind": "driver", "action": "publish", "phase": phase, "deadline": deadline})
        return self.unconfirmed_move != phase

    def observe(self):
        self.frame += 1
        self.position_frame += 1
        result = deepcopy(self.scene)
        result.update(sampleId=self.frame, producerFrame=self.frame * 2,
                      producerMonotonicNs=self.tick() * 100, durationUs=100)
        left = result["vrPicking"]["nodes"]["leftWand"]["world"]
        x, y, z = self.current_center
        left["translation"] = [x, y + 6., z + 2.]
        if self.attached and self.current_center != FAR and self.position_frame == 2:
            self.callbacks.append({"sequence": len(self.callbacks) + 1, "qpc": self.tick(),
                                   "eventName": "CBPCPlayerCollisionWithMaleEvent", "strArg": NODE,
                                   "senderFormId": ACTOR, "numArg": .45})
        return result

    def flush_acks(self):
        start = self.tick() // 10 - 50
        full = receipt(40, start)
        delta = receipt(TOKEN, start + 20, previous=40, application="delta")
        full["weight"] = delta["weight"] = .5
        set_tail(full, 0.)
        set_tail(delta, 6.)
        prefix, initial, update = lines(full, delta)
        if self.partial_delta:
            update = update[:-2]
        self.ack_log.write_bytes((prefix + initial + update).encode("utf-8"))
        self.pose["sample"]["effectiveMorphs"] = {MORPH: delta["morphs"][0]["value"]}

    def event_call(self, method, args):
        state = self.arm_state
        if method == "GetCaptureState":
            if state == "pending":
                self.armed = self.tick()
                self.arm_state = "armed"
            return json.dumps({"schema": "claw-vr-cbpc-events/1", "status": state,
                               "generation": CAPTURE_GENERATION, "pid": PID,
                               "loading": False, "sinkRegistered": True}), "string"
        if method == "Arm":
            if args != [NONCE, CAPTURE_GENERATION, ACTOR - 2**32, CELL] or state != "idle":
                raise AssertionError("Unexpected CBPC arm")
            self.requested = self.tick()
            self.arm_state = "pending"
        elif method == "Seal":
            if args != [NONCE, CAPTURE_GENERATION] or state != "armed" or self.attached:
                raise AssertionError("Unexpected CBPC seal")
            self.closed = self.tick()
            self.arm_state = "sealed"
        elif method == "Read":
            if args != [NONCE, CAPTURE_GENERATION] or state != "sealed":
                raise AssertionError("Unexpected CBPC read")
            return json.dumps({"schema": "claw-vr-cbpc-events/1", "observation": "skse_mod_callback",
                               "status": state, "pid": PID, "nonce": NONCE, "generation": CAPTURE_GENERATION,
                               "actorFormId": ACTOR, "baseFormId": BASE, "cellFormId": CELL,
                               "sealedWithoutLocalDrops": True, "dropped": 0, "unattributed": 0,
                               "lastSequence": len(self.callbacks), "qpcFrequency": QPC,
                               "requestedQpc": self.requested, "armedQpc": self.armed, "closedQpc": self.closed,
                               "events": self.callbacks}), "string"
        else:
            raise AssertionError(method)
        return True, "bool"

    def pose_call(self, method, args):
        if method == "BeginNpcContact":
            if args != [NONCE, ACTOR - 2**32, BASE, HANDLE, CELL, 0xCDD87, PROFILE["morphs"]]:
                raise AssertionError("Unexpected actor pose lease")
        elif method == "SampleNpc":
            if args != [NONCE, self.active_pose + 1]:
                raise AssertionError("Pose sample sequence was not advanced")
            self.active_pose += 1
        elif method == "EndNpc":
            self.ended = True
        elif method == "ReadNpc":
            if args != [NONCE, self.active_pose]:
                raise AssertionError("Pose read did not match the active sample")
            pose = deepcopy(self.pose)
            pose.update(nonce=NONCE, sequence=self.active_pose, status="ended" if self.ended else "ready")
            pose["sample"].update(rootToken=NONCE, qpcBegin=self.tick() - 1000, qpcEnd=self.tick() - 1)
            return json.dumps(pose), "string"
        else:
            raise AssertionError(method)
        return json.dumps({"status": "pending"}), "string"

    def papyrus(self, script, method, args):
        read = {"GetCaptureState", "Read", "ReadNpc", "GetModelIdentity", "SnapshotCurrent",
                "ActorCurrent", "GetGeneration", "GetLedgerCount"}
        if method not in read:
            self.mutations.append((script, method))
        if script == EVENTS:
            return self.event_call(method, args)
        if script == POSE:
            return self.pose_call(method, args)
        if script == NATIVE:
            if method == "SnapshotCurrent":
                return self.attached and args == [ACTOR_ARG, GENERATION, TOKEN], "bool"
            if method == "ActorCurrent":
                return self.attached, "bool"
            if method == "GetModelIdentity":
                return PROFILE["modelIdentity"], "string"
        if script != CONTROL:
            raise AssertionError((script, method, args))
        if method == "BeginSession":
            return args == [True, EVIDENCE], "bool"
        if method == "GetGeneration":
            return GENERATION, "int"
        if method == "RegisterActor" and args == [0, ACTOR_ARG]:
            return 0, "int"
        if method == "EnableAutomaticActor" and args == [0, ACTOR_ARG, EVIDENCE, True, True, True]:
            self.attached = True
            self.flush_acks()
            return 0, "int"
        if method == "ReleaseActor" and args == [0]:
            self.attached = False
            return 0, "int"
        if method == "GetLedgerCount" and args == [0]:
            return ACTIVE_SLOTS if self.attached else 0, "int"
        raise AssertionError((script, method, args))

    def tool(self, name, args, *, timeout, deadline):
        if not 0 < timeout <= 2.6 or self.monotonic() >= deadline:
            raise AssertionError("Executor call left the admitted window")
        self.sleep(.025)
        if name == "inspect":
            result = self.observe()
        elif name == "papyrus":
            value, kind = self.papyrus(args["script"], args["function"], args["args"])
            if args["function"] == self.timeout_on:
                self.append({"kind": "unconfirmed-tool", "tool": name, "args": args})
                raise TimeoutError("Native completion was not delivered")
            result = {"called": True, "returnedType": kind, "returned": value}
        else:
            raise AssertionError(name)
        self.append({"kind": "tool", "tool": name, "args": args, "result": result})
        return result

    def capture(self):
        return PoseContactCapture(self.tool, self.path, self.ack_log, Subject(PID, ACTOR, BASE, CELL, 0),
                                  self.profile, self.position, deadline=28., clock=self)


class RunPoseContactTest(unittest.TestCase):
    def test_real_verifier_accepts_full_sequence_and_owned_ledger(self):
        with TemporaryDirectory() as root:
            executor = AdmittedExecutor(Path(root))
            manifest, raw, verdict = executor.capture().run(NODE, NONCE, EVIDENCE)

            self.assertEqual(verdict["status"], "qualified-emission-contrast")
            self.assertEqual(verdict["preAppendPosition"], "unattachedFar")
            self.assertEqual(verdict["qualifiedHeldEventCounts"],
                             {"nearBefore": 1, "far": 0, "nearAfter": 1, "nearDetached": 0})
            self.assertEqual(verdict["preAppendCallbacks"], 0)
            self.assertEqual((manifest["subject"]["generation"], verdict["token"], verdict["previousToken"]),
                             (GENERATION, TOKEN, 40))
            self.assertEqual(manifest["sha256"], {key: sha256(data).hexdigest() for key, data in raw.items()})
            self.assertEqual([phase for phase, _ in executor.moves], ["far", "near", "far", "near"])
            self.assertEqual(executor.moves[1], executor.moves[3])
            self.assertEqual(executor.active_pose, 6)
            self.assertTrue(executor.ended)
            self.assertFalse(executor.attached)
            self.assertEqual(executor.arm_state, "sealed")

    def test_unknown_enable_completion_preserves_partial_state_without_replay(self):
        with TemporaryDirectory() as root:
            executor = AdmittedExecutor(Path(root))
            executor.timeout_on = "EnableAutomaticActor"
            capture = executor.capture()
            with self.assertRaisesRegex(UnconfirmedMutation, "EnableAutomaticActor"):
                capture.run(NODE, NONCE, EVIDENCE)

            self.assertEqual(capture.waiting_on, "EnableAutomaticActor")
            self.assertEqual(executor.mutations.count((CONTROL, "EnableAutomaticActor")), 1)
            self.assertEqual(executor.mutations[-1], (CONTROL, "EnableAutomaticActor"))
            self.assertTrue(executor.attached)
            self.assertEqual(executor.moves, [("far", FAR)])

    def test_unflushed_delta_cannot_drive_near_or_release(self):
        with TemporaryDirectory() as root:
            executor = AdmittedExecutor(Path(root))
            executor.partial_delta = True
            with self.assertRaisesRegex(ValueError, "yielded no current pose delta"):
                executor.capture().run(NODE, NONCE, EVIDENCE)

            self.assertFalse(executor.ack_log.read_bytes().endswith(b"\n"))
            self.assertEqual(executor.mutations[-1], (CONTROL, "EnableAutomaticActor"))
            self.assertEqual(executor.moves, [("far", FAR)])

    def test_unconfirmed_guarded_position_issues_near_only_once(self):
        with TemporaryDirectory() as root:
            executor = AdmittedExecutor(Path(root))
            executor.unconfirmed_move = "near"
            capture = executor.capture()
            with self.assertRaisesRegex(ValueError, "Controller move was not confirmed"):
                capture.run(NODE, NONCE, EVIDENCE)

            self.assertEqual([phase for phase, _ in executor.moves], ["far", "near"])
            self.assertEqual(capture.waiting_on, "controller:near")
            self.assertEqual(executor.mutations[-1], (CONTROL, "EnableAutomaticActor"))


if __name__ == "__main__":
    unittest.main()
