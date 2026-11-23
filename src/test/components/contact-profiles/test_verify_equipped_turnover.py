"""Synthetic controls for the joined topology, ACK and lifecycle verifier."""

from copy import deepcopy
import json
import unittest

from test_pose_ack import PROFILE, lines, receipt
from verify_equipped_turnover import (
    ACTOR, ACTOR_ID, CLOCK, CONTROL, EAR_MORPHS, EAR_POSE, EAR_SCHEMA, FIXTURE_PLUGIN, NATIVE, PHASES, SCHEMA,
    TOPOLOGY, TOPOLOGY_SCHEMA,
    TRANSITIONS, verify,
)
from test_dispatch_markers import FIXTURE, capture, mark, origin


def case(female=False, *, ears=False):
    ledger, acks = [], []
    stock = deepcopy(PROFILE)
    stock["slots"] = [dict(node="TailBone02", sexMask="both")]
    stock["morphs"] = sorted(EAR_MORPHS)
    equipped = {**stock, "modelIdentity": "CLAW.Physics.Equipped.fixture"}

    def call(script, function, args, kind, value, *, target=None):
        index = len(ledger)
        row = {"tool": "papyrus", "args": {"action": "call", "script": script, "function": function, "args": args},
               "result": {"called": True, "returnedType": kind, "returned": value}}
        if target is not None:
            row["args"]["self"] = dict(target)
        ledger.append(row)
        return index

    def detach(binding):
        return {"count": call(CONTROL, "GetLedgerCount", [0], "int", 0),
                "snapshotCurrent": call(NATIVE, "SnapshotCurrent", binding, "bool", False)}

    item, addon = ({"form": f"0x{form:08X}"} for form in FIXTURE)
    fixture_reads = {name: call("Game", "GetFormFromFile", [local, FIXTURE_PLUGIN], "Form", {"formId": form["form"]})
                     for name, local, form in (("item", 0x801, item), ("addon", 0x800, addon))}
    manifest = {"schema": SCHEMA, "clock": CLOCK, "pid": 492, "fixtureReads": fixture_reads,
                "hostModel": call(NATIVE, "GetModelIdentity", [], "String", stock["modelIdentity"]), "phases": {}}
    for n, phase in enumerate(PHASES, 1):
        generation, token, nonce = n * 3, n * 10, n * 2
        binding = [ACTOR, generation, token]
        profile = equipped if phase == "equipped" else stock
        ack = dict(receipt(token, n * 100), actor=ACTOR_ID, generation=generation, registration=n,
                   model=profile["modelIdentity"], female=female, changedSlots=[0],
                   morphs=[{"name": name, "value": .25} for name in profile["morphs"]])
        ack["capsules"] = [dict(ack["capsules"][0], node="TailBone02")]
        acks.append(ack)

        raw = dict(capture(TOPOLOGY_SCHEMA), nonce=nonce)
        sample = raw["sample"]
        sample.update(sex=int(female), weight=40., qpcBegin=n * 1000 + 50, qpcEnd=n * 1000 + 60,
                      playerBody32Fixture=dict(zip(("item", "addon"), FIXTURE, strict=True)))
        world = sample["views"]["thirdPerson"]
        family = "female" if female else "male"
        world["active"][0]["modelPath"] = rf"Actors\WerewolfBeast\Character Assets\{family}bodywerewolf_1.nif"
        if phase == "equipped":
            marker = "W_F" if female else "W_M"
            world["active"][0].update(item=FIXTURE[0], addon=FIXTURE[1], modelPath=origin(marker))
            mark(sample, 0, marker)
            world["buffered"] = []
            sample["body32Markers"][1]["clone"] = 0
            mark(sample, 1, classification="unloaded")
        row = {"nonce": nonce, "token": token,
               "generationRead": call(CONTROL, "GetGeneration", [0], "Int", generation),
               "currentBefore": call(NATIVE, "SnapshotCurrent", binding, "Bool", True),
               "request": call(TOPOLOGY, "CaptureDispatch", [nonce], "String", json.dumps({
                   "schema": TOPOLOGY_SCHEMA, "status": "pending", "pid": 492, "nonce": nonce})),
               "capture": call(TOPOLOGY, "Read", [nonce], "String", json.dumps(raw))}
        if phase == "equipped" and ears:
            ear_nonce = 1
            gate = {"generation": 8, "postPhaseCount": 19, "loading": False, "higgsBuild": 42}
            pending = {"schema": EAR_SCHEMA, "status": "pending", "pid": raw["pid"], "nonce": ear_nonce, "worldGate": gate}
            ear = dict(pending, status="ready", epoch=8, worldGate=dict(gate, postPhaseCount=20),
                       body32={"worldDispatchMarker": marker}, sample={
                           "player": ACTOR_ID, "base": sample["base"], "race": sample["race"], "cell": sample["cell"],
                           "handle": sample["runtimeHandle"], "sex": sample["sex"], "rawWeight": sample["weight"],
                           "biped": dict(world["active"][0], slot=32), "phase": "PostVrikPostHiggs", "phaseSequence": 20,
                           "higgsBuild": 42, "qpcBegin": sample["qpcEnd"] + 20, "qpcEnd": sample["qpcEnd"] + 40,
                           "qpcFrequency": sample["qpcFrequency"], "earEffectiveMorphs": dict.fromkeys(EAR_MORPHS, .25)})
            row["earPose"] = {"nonce": ear_nonce,
                              "request": call(EAR_POSE, "Capture", [ear_nonce], "String", json.dumps(pending)),
                              "capture": call(EAR_POSE, "Read", [ear_nonce], "String", json.dumps(ear))}
        row["currentAfter"] = call(NATIVE, "SnapshotCurrent", binding, "Bool", True)
        row["count"] = call(CONTROL, "GetLedgerCount", [0], "Int", 1)
        if phase in TRANSITIONS:
            row["equipmentAction"] = call("Actor", TRANSITIONS[phase], [item, False, True], "none", None, target=ACTOR)
            row["onModelChange"] = detach(binding)
        row["retirement"] = {"release": call(CONTROL, "ReleaseActor", [0], "Int", 0), **detach(binding),
                             "actorCurrent": call(NATIVE, "ActorCurrent", [ACTOR], "bool", False)}
        manifest["phases"][phase] = row
    return manifest, ledger, acks, stock, equipped


class TurnoverTests(unittest.TestCase):
    def check(self, manifest, ledger, acks, stock, equipped):
        return verify(manifest, ledger, lines(*acks), stock, equipped)

    def test_same_player_fresh_profiles_and_separate_claims(self):
        for female in (False, True):
            with self.subTest(female=female):
                manifest, ledger, acks, stock, equipped = case(female)
                result = self.check(manifest, ledger, acks, stock, equipped)
                self.assertTrue(result["routeTurnoverVerified"])
                self.assertTrue(result["hostLedgerRetirementVerified"])
                self.assertFalse(result["solverGeometryVerified"])
                self.assertFalse(result["controllerContactVerified"])
                self.assertEqual([phase["model"] for phase in result["phases"].values()],
                                 [stock["modelIdentity"], equipped["modelIdentity"], stock["modelIdentity"]])

    def test_same_world_requires_new_registration_and_exact_model(self):
        for field, value in (("registration", 1), ("world", 2), ("model", PROFILE["modelIdentity"])):
            with self.subTest(field=field):
                args = case()
                args[2][1][field] = value
                with self.assertRaises(ValueError):
                    self.check(*args)

    def test_old_token_or_residual_host_ledger_prevents_turnover(self):
        for key, value in (("count", 1), ("snapshotCurrent", True)):
            with self.subTest(key=key):
                args = case()
                index = args[0]["phases"]["equipped"]["onModelChange"][key]
                args[1][index]["result"]["returned"] = value
                with self.assertRaisesRegex(ValueError, "retirement"):
                    self.check(*args)

    def test_refuses_other_equipment_target_and_unproven_release(self):
        args = case()
        stock = args[0]["phases"]["stock"]
        args[1][stock["equipmentAction"]]["args"]["self"] = {"form": "0xFF00085B"}
        with self.assertRaisesRegex(ValueError, "EquipItem"):
            self.check(*args)
        args = case()
        release = args[0]["phases"]["restored"]["retirement"]["release"]
        args[1][release]["result"]["returned"] = -3
        with self.assertRaisesRegex(ValueError, "release failed"):
            self.check(*args)
        args = case()
        actor_current = args[0]["phases"]["restored"]["retirement"]["actorCurrent"]
        args[1][actor_current]["result"]["returned"] = True
        with self.assertRaisesRegex(ValueError, "native cleanup lease"):
            self.check(*args)

    def test_rejects_snapshot_from_before_ack_or_after_load(self):
        for key, value in (("epoch", 8), ("handle", 81), ("clock", 2000)):
            with self.subTest(key=key):
                args = case()
                index = args[0]["phases"]["equipped"]["capture"]
                result = args[1][index]["result"]
                raw = json.loads(result["returned"])
                if key == "epoch":
                    raw[key] = value
                elif key == "handle":
                    raw["sample"]["runtimeHandle"] = value
                else:
                    raw["sample"].update(qpcBegin=value, qpcEnd=value + 10)
                result["returned"] = json.dumps(raw)
                with self.assertRaises(ValueError):
                    self.check(*args)

    def test_rejects_buffered_equipped_body_in_either_phase(self):
        for phase in ("equipped", "restored"):
            with self.subTest(phase=phase):
                args = case()
                index = args[0]["phases"][phase]["capture"]
                result = args[1][index]["result"]
                raw = json.loads(result["returned"])
                sample = raw["sample"]
                sample["views"]["thirdPerson"]["buffered"] = [dict(slot=2, clone=4, item=FIXTURE[0],
                                                                      addon=FIXTURE[1], modelPath=origin("W_M"))]
                sample["body32Markers"][1]["clone"] = 4
                mark(sample, 1, "W_M")
                result["returned"] = json.dumps(raw)
                with self.assertRaises(ValueError):
                    self.check(*args)

    def test_cached_reply_without_matching_queued_capture_is_refused(self):
        args = case()
        request = args[0]["phases"]["stock"]["request"]
        reply = args[1][request]["result"]
        payload = json.loads(reply["returned"])
        reply["returned"] = json.dumps(dict(payload, pid=493))
        with self.assertRaisesRegex(ValueError, "matching CLAWVRModelTopology capture request"):
            self.check(*args)

    def test_links_post_phase_ear_pose_to_the_same_equipped_ack(self):
        for female in (False, True):
            with self.subTest(female=female):
                linked = self.check(*case(female, ears=True))["phases"]["equipped"]["earPose"]
                self.assertEqual(linked, {"nonce": 1, "phase": 20, "qpcBegin": 2080, "qpcEnd": 2100, "token": 20,
                                          "earPoseLinked": True})

    def test_matching_topology_and_ear_pose_cannot_use_an_ack_from_different_weight(self):
        for weight in (37., None):
            with self.subTest(weight=weight):
                args = case(ears=True)
                equipped = args[0]["phases"]["equipped"]
                for index, field in ((equipped["capture"], "weight"), (equipped["earPose"]["capture"], "rawWeight")):
                    reply = args[1][index]["result"]
                    raw = json.loads(reply["returned"])
                    raw["sample"][field] = weight
                    reply["returned"] = json.dumps(raw)
                with self.assertRaisesRegex(ValueError, "actor weight"):
                    self.check(*args)

    def test_rejects_cross_actor_world_route_and_out_of_order_ear_pose(self):
        for field, value in (("handle", 81), ("qpcBegin", 2060), ("phaseSequence", 19), ("qpcFrequency", 1000000),
                             ("qpcEnd", 3001), ("earEffectiveMorphs", dict.fromkeys(EAR_MORPHS, .5))):
            with self.subTest(field=field):
                args = case(ears=True)
                capture = args[0]["phases"]["equipped"]["earPose"]["capture"]
                reply = args[1][capture]["result"]
                raw = json.loads(reply["returned"])
                raw["sample"][field] = value
                reply["returned"] = json.dumps(raw)
                with self.assertRaises(ValueError):
                    self.check(*args)

    def test_retirement_receipts_cannot_be_reused_or_sorted_later(self):
        args = case()
        stock = args[0]["phases"]["stock"]
        stock["onModelChange"]["count"] = stock["retirement"]["count"]
        with self.assertRaisesRegex(ValueError, "out-of-order"):
            self.check(*args)


if __name__ == "__main__":
    unittest.main()
