"""Contract controls for the fixed-controller VR refit evidence reader."""
from copy import deepcopy
import json
import unittest

from verify_tail_refit import (
    CBPC, CHANNEL, CONTACT_NODES, EVENTS, NATIVE, NODE, PHASES, POSE, QPC, SLOT_IDS, verify,
)
from tail_refit_morph import FUNCTIONS, MORPH_SCRIPT, TEST_KEY
from src.test.python.integration.fsmp_probe import OBSERVATION


ACTOR, BASE, CELL, PID, HANDLE = 0xFF000868, 0x0B000800, 0x0A01A5C6, 10420, 1112349
ACTOR_HEX = f"0x{ACTOR:08X}"
ACTOR_ARG = {"form": ACTOR_HEX}
MODEL = {"modelIdentity": "exact-refit-test-model", "morphs": [CHANNEL, *(str(i) for i in range(30))],
         "slots": [{"node": NODE if i in SLOT_IDS else "other", "male": {}}
                   for i in range(128)]}


def shape(x):
    return [{"p1": [x + i * .1, 0., 0.], "p2": [x + i * .1, 0., 1.], "radius": 1.25}
            for i in range(4)]


BASIS = {"model": MODEL["modelIdentity"], "slots": SLOT_IDS, "values": (0., 1., 0.),
         "capsulesByPhase": [shape(0.), shape(6.), shape(0.)]}


def point(x=0., y=0., z=0.):
    return {"rotationRowMajor": [1, 0, 0, 0, 1, 0, 0, 0, 1], "translation": [x, y, z], "scale": 1.}


def make_case():
    ledger, stamps = [], []
    manifest = {"schema": "claw-vr-tail02-refit-reads/2",
                "subject": {"pid": PID, "actor": ACTOR, "base": BASE, "cell": CELL, "generation": 2},
                "phases": [], "capture": {}}

    def record(row):
        ledger.append(row)
        return len(ledger) - 1

    def call(script, name, args, returns, value):
        return record({"tool": "papyrus", "args": {"action": "call", "script": script, "function": name, "args": args},
                       "result": {"called": True, "returnedType": returns, "returned": value}})

    def hold(start):
        def actor(form, base, handle):
            return {"identity": {"form": f"0x{form:08X}", "runtimeHandle": handle, "loadGeneration": 1},
                    "baseForm": f"0x{base:08X}", "cellForm": f"0x{CELL:08X}", "status": "available",
                    "loaded3D": True, "disabled": False, "deleted": False, "sceneTransform": point(),
                    "position": [0, 0, 0]}

        def node(name, pose):
            return {"status": "available", "name": name, "world": pose}

        source = point(6.5, 6., 2.)  # Native source sphere has local offset (0, -6, -2).
        target = actor(ACTOR, BASE, HANDLE)
        boundary = []
        for sample in range(4):
            tick = start + sample * 5_500_000
            stamps.append(tick)
            raw = {"ok": True, "schemaVersion": 1, "observerVersion": "0.2.6", "quality": "complete",
                   "coherence": OBSERVATION, "phase": "skse_main_thread_task", "space": "world",
                   "units": "skyrim_engine_units", "sessionId": f"{PID}-test", "sampleId": len(stamps),
                   "producerFrame": len(stamps) * 10, "producerMonotonicNs": tick * 100, "loadGeneration": 1,
                   "refs": [actor(0x14, 7, 1048576), target],
                   "nodes": [{**node(name, point() if name == NODE else point(.2, -.6)),
                              "form": ACTOR_HEX, "identity": target["identity"],
                              "firstPerson": False} for name in (NODE, "NPC Root [Root]")],
                   "vrPicking": {"status": "available", "phase": "skse_main_thread_task", "space": "world",
                                 "units": "skyrim_engine_units", "nodes": {
                                     "leftWand": node("LeftWandNode", source), "rightWand": node("RightWandNode", point(35)),
                                     "uprightHmd": node("UprightHmdNode", point(40))}}}
            boundary.append(record({"tool": "inspect", "args": {"kind": "world_observer", "action": "snapshot"},
                                    "result": raw}))
        return boundary

    def pose(sequence, tick, value):
        effective = dict.fromkeys(MODEL["morphs"], 0.)
        effective[CHANNEL] = value
        sample = {"actor": ACTOR, "base": BASE, "cell": CELL, "runtimeHandle": HANDLE, "rootToken": 42, "loadEpoch": 1,
                  "qpcBegin": tick, "qpcEnd": tick + 1000, "sex": 0, "weight": 50,
                  "bodyAddon": 0xCDD87, "bodyItem": 0xCDD86, "race": 0xCDD84, "threadID": 11360,
                  "phase": "skse_main_thread_task", "view": "third_person", "effectiveMorphs": effective,
                  "nodes": [{"name": name, "world": point()} for name in sorted(CONTACT_NODES)],
                  "rootWorld": point(), "bodyCloneWorld": point()}
        reply = {"schema": "claw-vr-npc-pose/1", "status": "ready", "nonce": 42, "sequence": sequence,
                 "pid": PID, "qpcFrequency": QPC, "sample": sample}
        return call(POSE, "ReadNpc", [42, sequence], "string", json.dumps(reply))

    scope = [77, 1]
    manifest["modelRead"] = call(NATIVE, "GetModelIdentity", [], "string", MODEL["modelIdentity"])
    morph = manifest["morph"] = {
        "describe": record({"tool": "papyrus", "args": {"action": "describe", "script": MORPH_SCRIPT},
                            "result": {"name": MORPH_SCRIPT, "globalFunctions": [
                                {"name": method, "native": True, "returnType": ret,
                                 "params": [{"type": param} for param in params]}
                                for method, (ret, params) in FUNCTIONS.items()]}}),
    }
    storage_args = [ACTOR_ARG, CHANNEL, TEST_KEY]
    def storage(value):
        return [call(MORPH_SCRIPT, "HasBodyMorph", storage_args, "bool", value != 0.),
                call(MORPH_SCRIPT, "GetBodyMorph", storage_args, "float", value)]

    morph["initial"] = storage(0.)
    capture = manifest["capture"]
    capture["idle"] = call(EVENTS, "GetCaptureState", [], "string", json.dumps({
        "schema": "claw-vr-cbpc-events/1", "status": "idle", "generation": 1,
        "pid": PID, "loading": False, "sinkRegistered": True}))
    capture["arm"] = call(EVENTS, "Arm", [*scope, ACTOR - 0x100000000, CELL], "bool", True)
    manifest["unattached"] = hold(30_000_000)
    for i, value in enumerate((0., 1., 0.)):
        time = (i + 2) * 30_000_000
        native_args = [ACTOR_ARG, 2, 15 + i]
        phase = {"token": 15 + i}
        if i:
            method, args = ("SetBodyMorph", [*storage_args, 1.]) if i == 1 else ("ClearBodyMorph", storage_args)
            morph["apply" if i == 1 else "restore"] = [
                call(MORPH_SCRIPT, method, args, "none", None),
                call(MORPH_SCRIPT, "UpdateModelWeight", [ACTOR_ARG], "none", None), *storage(value),
            ]
        phase["event"] = call(POSE, "ReadPhysicsSnapshot", [42, 14 + i if i else 0], "string", json.dumps({
            "schema": "claw-vr-npc-pose/1", "status": "ready", "nonce": 42,
            "pid": PID, "qpcFrequency": QPC, "actor": ACTOR, "base": BASE, "loadEpoch": 1, "runtimeHandle": HANDLE,
            "rootToken": 42, "snapshotToken": 15 + i, "eventQpc": time - 200_000,
        }))
        phase["begin"] = call(NATIVE, "SnapshotCurrent", native_args, "bool", True)
        phase["values"] = call(NATIVE, "GetValues", native_args, "float[]", [value] + [0.] * 30)
        phase["weight"] = call(NATIVE, "GetWeight", native_args, "float", .5)
        bank = BASIS["capsulesByPhase"][i]
        phase["capsules"] = [call(NATIVE, "GetCapsule", [*native_args, slot], "float[]",
                                 [*cap["p1"], *cap["p2"], cap["radius"]])
                             for slot, cap in zip(SLOT_IDS, bank, strict=True)]
        phase["attach"] = [
            call(CBPC, "AttachColliderCapsule", [ACTOR_ARG, NODE, cap["p1"], cap["radius"], cap["p2"],
                 cap["radius"], 0., 0x434C0000 + slot, True], "bool", True)
            for slot, cap in zip(SLOT_IDS, bank, strict=True)]
        phase["poseBefore"] = pose(2 * i, time - 100_000, value)
        phase["hold"] = hold(time)
        phase["poseAfter"] = pose(2 * i + 1, time + 16_600_000, value)
        phase["end"] = call(NATIVE, "SnapshotCurrent", native_args, "bool", True)
        phase["detach"] = [call(CBPC, "DetachCollider", [ACTOR_ARG, NODE, 1, 0x434C0000 + slot, True], "bool", True)
                           for slot in SLOT_IDS]
        manifest["phases"].append(phase)
    manifest["detached"] = hold(150_000_000)
    capture["seal"] = call(EVENTS, "Seal", scope, "bool", True)
    capture["read"] = call(EVENTS, "Read", scope, "string", json.dumps({
        "schema": "claw-vr-cbpc-events/1", "observation": "skse_mod_callback", "status": "sealed",
        "pid": PID, "nonce": 77, "generation": 1, "actorFormId": ACTOR, "baseFormId": BASE, "cellFormId": CELL,
        "sealedWithoutLocalDrops": True, "dropped": 0, "unattributed": 0, "lastSequence": 1,
        "qpcFrequency": QPC, "requestedQpc": 1_000_000, "armedQpc": 2_000_000, "closedQpc": 180_000_000,
        "events": [{"sequence": 1, "qpc": 95_000_000, "eventName": "CBPCPlayerCollisionWithMaleEvent",
                    "strArg": NODE, "senderFormId": ACTOR, "numArg": .45}]}))
    return deepcopy(manifest), deepcopy(ledger)


class TailRefitTest(unittest.TestCase):
    def test_full_three_state_proof_and_bone_level_event_only(self):
        plan, raw = make_case()
        result = verify(plan, raw, MODEL, BASIS)
        self.assertEqual([result["sameNodeCallbacks"][phase] for phase in PHASES], [0, 0, 1, 0, 0])
        self.assertEqual(result["snapshotTokens"], [15, 16, 17])
        self.assertFalse(result["perSlotCallbackAttribution"])
        self.assertFalse(result["providerShapeInventoryVerified"])

    def test_snapshot_and_native_aggregate_must_both_be_current(self):
        for key, update, message in (("end", False, "did not remain current"),
                                     ("values", [0.] * 31, "effective SKEE vector")):
            with self.subTest(key=key):
                plan, raw = make_case()
                raw[plan["phases"][1][key]]["result"]["returned"] = update
                with self.assertRaisesRegex(ValueError, message):
                    verify(plan, raw, MODEL, BASIS)

    def test_cannot_substitute_an_unrelated_actor_event_or_leave_the_key_set(self):
        plan, raw = make_case()
        result = raw[plan["phases"][1]["event"]]["result"]
        event = json.loads(result["returned"])
        event["actor"] += 1
        result["returned"] = json.dumps(event)
        with self.assertRaisesRegex(ValueError, "actor-bound native refit event"):
            verify(plan, raw, MODEL, BASIS)
        plan, raw = make_case()
        raw[plan["morph"]["restore"][2]]["result"]["returned"] = True
        with self.assertRaisesRegex(ValueError, "morph was not isolated or cleared"):
            verify(plan, raw, MODEL, BASIS)

    def test_exact_current_fit_and_all_four_slots_required(self):
        for key in ("capsules", "detach"):
            with self.subTest(key=key):
                plan, raw = make_case()
                payload = raw[plan["phases"][1][key][-1]]
                if key == "capsules":
                    payload["result"]["returned"][0] += 1.
                    with self.assertRaisesRegex(ValueError, "pinned exact refit bank"):
                        verify(plan, raw, MODEL, BASIS)
                else:
                    payload["result"]["returned"] = False
                    with self.assertRaisesRegex(ValueError, "slot retirement"):
                        verify(plan, raw, MODEL, BASIS)
        plan, raw = make_case()
        plan["phases"][1]["capsules"].pop()
        with self.assertRaisesRegex(ValueError, "all four"):
            verify(plan, raw, MODEL, BASIS)

    def test_actor_root_and_pose_brackets_are_independently_checked(self):
        for key, value, message in (("runtimeHandle", HANDLE + 1, "actor root"),
                                    ("qpcBegin", 60_000_001, "do not bracket")):
            with self.subTest(field=key):
                plan, raw = make_case()
                index = plan["phases"][0]["poseAfter" if key == "runtimeHandle" else "poseBefore"]
                result = raw[index]["result"]
                pose = json.loads(result["returned"])
                pose["sample"][key] = value
                if key == "qpcBegin":
                    pose["sample"]["qpcEnd"] = value + 1000
                result["returned"] = json.dumps(pose)
                with self.assertRaisesRegex(ValueError, message):
                    verify(plan, raw, MODEL, BASIS)

    def test_controller_movement_and_tail_pose_false_positive_refused(self):
        for route, message in (("leftWand", "Controller or owned actor/root moved"),
                               (NODE, "does not discriminate both capsule banks")):
            with self.subTest(route=route):
                plan, raw = make_case()
                frame = raw[plan["phases"][1]["hold"][1]]["result"]
                node = frame["vrPicking"]["nodes"][route] if route == "leftWand" else frame["nodes"][0]
                node["world"]["translation"][0] += 3.
                with self.assertRaisesRegex(ValueError, message):
                    verify(plan, raw, MODEL, BASIS)

    def test_missing_or_out_of_phase_callback_cannot_qualify(self):
        for qpc in (None, 65_000_000, 152_000_000):
            with self.subTest(qpc=qpc):
                plan, raw = make_case()
                result = raw[plan["capture"]["read"]]["result"]
                window = json.loads(result["returned"])
                if qpc is None:
                    window.update(events=[], lastSequence=0)
                else:
                    window["events"][0]["qpc"] = qpc
                result["returned"] = json.dumps(window)
                with self.assertRaisesRegex(ValueError, "Same-node callbacks do not distinguish"):
                    verify(plan, raw, MODEL, BASIS)


if __name__ == "__main__":
    unittest.main()
