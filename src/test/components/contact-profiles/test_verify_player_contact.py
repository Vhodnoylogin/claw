"""Synthetic controls for joining an equipped-player contact ledger."""

from copy import deepcopy
import json
import unittest

from verify_player_contact import (ACTOR, ARM_NODES, CBPC, CLOCK, EVENTS, EVENT_SCHEMA, PHASES, QPC,
                                   SCHEMA, TOPOLOGY, TOPOLOGY_SCHEMA, Subject, decode, verify)
from player_contact_custody import ISOLATED_ABSENCES, MODULES, PLUGINS, verify_backing, verify_vfs
from retarget_player_contact import plan, retarget
from test_cbpc_vr_geometry import CELL, PID, pose, sample
from test_dispatch_markers import FIXTURE, capture, mark, origin


def case(*, female=False, arm="tail"):
    ledger = []
    node = ARM_NODES[arm]
    handle, nonce, generation = 0x14, 11, 2
    item, addon = FIXTURE
    manifest = {"schema": SCHEMA, "clock": CLOCK, "pid": PID, "cell": CELL, "sex": "Female" if female else "Male",
                "arm": arm, "association": 0, "capture": {"nonce": nonce, "generation": generation},
                "topology": {}, "holds": {}, "attach": [], "detach": []}
    shape = {"p1": [0., 0., 0.], "p2": [0., 0., 1.], "radius": 1.5}
    profile = {"fixtures": [{"name": "neutral", "weight": 0., "values": {},
                             "sexes": {sex: {"capsules": [shape] * 112} for sex in ("male", "female")}}]}

    def add(row):
        ledger.append(deepcopy(row))
        return len(ledger) - 1

    def call(script, method, args, kind, value):
        return add({"tool": "papyrus", "args": {"action": "call", "script": script, "function": method, "args": args},
                    "result": {"called": True, "returnedType": kind, "returned": value}})

    def topology(name, number, qpc):
        raw = dict(capture(TOPOLOGY_SCHEMA), nonce=number, pid=PID)
        body = raw["sample"]
        body.update(sex=int(female), weight=0., cell=CELL, runtimeHandle=handle, qpcBegin=qpc, qpcEnd=qpc + 50,
                    playerBody32Fixture={"item": item, "addon": addon})
        model = "W_F" if female else "W_M"
        world = body["views"]["thirdPerson"]
        world["active"][0].update(item=item, addon=addon, modelPath=origin(model))
        world["buffered"] = []
        body["body32Markers"][1]["clone"] = 0
        mark(body, 0, model)
        mark(body, 1, classification="unloaded")
        request = call(TOPOLOGY, "CaptureDispatch", [number], "string", json.dumps(dict(raw, status="pending")))
        read = call(TOPOLOGY, "Read", [number], "string", json.dumps(raw))
        manifest["topology"][name] = {"nonce": number, "request": request, "capture": read}

    def hold(name, group):
        indices = []
        for i in range(3):
            raw = sample(3 * group + i + 1, (1 + 3 * group) * 10**9 + i * 800_000_000, 3 if name == "far" else 10)
            player = raw["refs"][0]
            raw["refs"] = [player]
            root = {"name": "NPC Root [Root]", "identity": player["identity"], "form": ACTOR["form"],
                    "status": "available", "firstPerson": False, "world": pose([0, 0, 0])}
            target = {**root, "name": node, "world": pose([14, 0, 9])}
            raw.update(nodes=[root, target], durationUs=100)
            indices.append(add({"tool": "inspect", "args": {"kind": "world_observer", "action": "snapshot", "refs": [ACTOR["form"]],
                                                            "nodes": [{"ref": ACTOR["form"], "name": current["name"], "firstPerson": False}
                                                                      for current in raw["nodes"]]}, "result": raw}))
        manifest["holds"][name] = indices

    add({"kind": "private-vr-bridge-observation"})
    manifest["fixtureReads"] = {key: call("Game", "GetFormFromFile", [form & 0xFFFFFF, "test_CLAW - VR Player Body32.esp"],
                                          "form", {"formId": f"0x{form:08X}"})
                                for key, form in (("item", item), ("addon", addon))}
    cap = manifest["capture"]
    idle = {"schema": EVENT_SCHEMA, "pid": PID, "generation": generation, "status": "idle", "sinkRegistered": True, "loading": False}
    cap["idle"] = call(EVENTS, "GetCaptureState", [], "string", json.dumps(idle))
    cap["arm"] = call(EVENTS, "Arm", [nonce, generation, 0x14, CELL], "bool", True)
    cap["armed"] = call(EVENTS, "GetCaptureState", [], "string", json.dumps(dict(idle, status="armed")))
    topology("before", 1, 1_000_000)
    hold("unattachedNear", 0)
    slots = range(108, 112) if arm == "tail" else range(88, 92)
    manifest["attach"] = [call(CBPC, "AttachColliderCapsule", [ACTOR, node, shape["p1"], 1.5, shape["p2"], 1.5, 0.,
                                                              0x434C0000 + slot, True], "bool", True) for slot in slots]
    topology("attached", 2, 30_000_000)
    for group, name in enumerate(PHASES[1:4], 1):
        hold(name, group)
    manifest["detach"] = [call(CBPC, "DetachCollider", [ACTOR, node, 1, 0x434C0000 + slot, True], "bool", True) for slot in slots]
    topology("detached", 3, 120_000_000)
    hold("nearDetached", 4)
    topology("after", 4, 155_000_000)
    cap["seal"] = call(EVENTS, "Seal", [nonce, generation], "bool", True)
    window = {"schema": EVENT_SCHEMA, "pid": PID, "generation": generation, "nonce": nonce, "status": "sealed",
              "qpcFrequency": QPC, "requestedQpc": 10, "armedQpc": 100, "closedQpc": 170_000_000, "actorFormId": 0x14,
              "baseFormId": 7, "cellFormId": CELL, "observation": "skse_mod_callback", "lastSequence": 2, "dropped": 0,
              "unattributed": 0, "sealedWithoutLocalDrops": True, "body32": {"runtimeHandle": handle, "female": female,
                                                                             "item": item, "addon": addon, "checkedAtSeal": True},
              "events": [{"sequence": i, "qpc": tick, "eventName": f"CBPCPlayerCollisionWith{manifest['sex']}Event",
                          "senderFormId": 0x14, "strArg": node, "numArg": .325}
                         for i, tick in enumerate((50_000_000, 110_000_000), 1)]}
    cap["read"] = call(EVENTS, "Read", [nonce, generation], "string", json.dumps(window))
    return manifest, ledger, profile


class PlayerContactTests(unittest.TestCase):
    def test_retarget_preserves_measured_wand_basis_and_converts_sphere_center_to_wand_origin(self):
        frame = {"left": pose([8, 7, 20], 2.), "source": [20., 7., 16.], "targetPose": pose([10, 5, 30], 1.5)}
        anchors = {"near": {"handFromTargetBoneGu": [0., 0., 0.]}, "far": {"handFromTargetBoneGu": [7., 0., 0.]}}
        result = retarget(frame, anchors, [[0., 0., 0., 0., 0., 1., 1.5]])
        self.assertEqual(result["near"]["sphereCenterGu"], [10., 5., 30.])
        self.assertEqual(result["near"]["leftWand"], pose([-2., 5., 34.], 2.))
        self.assertEqual(result["near"]["sphereRadiusGu"], 6.)
        self.assertEqual(result["far"]["signedGapGu"], 2.25)
        anchors["far"]["handFromTargetBoneGu"] = [5., 0., 0.]
        with self.assertRaisesRegex(ValueError, "far cue has insufficient"):
            retarget(frame, anchors, [[0., 0., 0., 0., 0., 1., 1.5]])

    def test_retarget_requires_the_adjacent_equipped_weight_zero_player(self):
        run, rows, _ = case(female=True, arm="tail")
        node = ARM_NODES["tail"]
        config = {"arms": {"tail": {"node": node, "slots": [108], "capsules": {"female": [{"geometry": [0., 0., 0., 0., 0., 1., 1.5]}]}}}}
        anchors = {"targetNode": node, "sourceSlotIndices": [108], "near": {"handFromTargetBoneGu": [0., 0., 0.]},
                   "far": {"handFromTargetBoneGu": [7., 0., 0.]}}
        cues = {"results": {"female": {"arms": {"tail": anchors}}}}
        frame = rows[run["holds"]["unattachedNear"][0]]
        native = decode(rows[run["topology"]["before"]["capture"]]["result"]["returned"])
        subject = Subject(PID, 0x14, 7, CELL, 0)
        actual = plan(frame, native, FIXTURE, subject, config, cues, "tail", "female")
        self.assertEqual(actual["targets"]["near"]["sphereCenterGu"], [14., 0., 9.])
        for key, value in (("weight", 1.), ("runtimeHandle", 21)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                wrong = deepcopy(native)
                wrong["sample"][key] = value
                plan(frame, wrong, FIXTURE, subject, config, cues, "tail", "female")

    def test_scoped_clearance_and_contact_for_both_arms(self):
        for female, arm in ((True, "tail"), (False, "left-ear")):
            with self.subTest(arm=arm):
                result = verify(*case(female=female, arm=arm))
                self.assertEqual(result["status"], "qualified-emission-contrast")
                self.assertEqual(result["qualifiedHeldEventCounts"], {"nearBefore": 1, "far": 0, "nearAfter": 1, "nearDetached": 0})
                self.assertEqual(result["preAppendCallbacks"], 0)
                self.assertEqual(result["signedGapRangesGu"]["nearBefore"], [-2., -2.])
                self.assertFalse(result["perSlotCallbackAttribution"])

    def test_refuses_wrong_capsule_and_earlier_measurement_at_current_slot(self):
        for key, field, value in (("attach", "args", [ACTOR, "TailBone02", [], 1., [], 1., 0., 1, True]),
                                  ("detach", "return", False), ("nearBefore", "producerMonotonicNs", 2_900_000_000),
                                  ("nearAfter", "request", [])):
            with self.subTest(key=key):
                manifest, steps, profile = case()
                if key in ("attach", "detach"):
                    row = steps[manifest[key][0]]
                    if field == "args":
                        row["args"]["args"] = value
                    else:
                        row["result"]["returned"] = value
                else:
                    row = steps[manifest["holds"][key][0]]
                    if field == "request":
                        row["args"]["refs"] = value
                    else:
                        row["result"][field] = value
                with self.assertRaises(ValueError):
                    verify(manifest, steps, profile)

    def test_callback_during_far_or_first_sample_does_not_qualify(self):
        for tick in (40_000_010, 80_000_000):
            with self.subTest(tick=tick):
                manifest, steps, model = case()
                row = steps[manifest["capture"]["read"]]["result"]
                window = decode(row["returned"])
                window["events"][0]["qpc"] = tick
                row["returned"] = json.dumps(window)
                self.assertEqual(verify(manifest, steps, model)["status"], "insufficient-emission-contrast")


def custody_case():
    files = {PLUGINS.casefold() + name: digest for name, digest in MODULES.items()}
    config = PLUGINS.casefold() + "cbpccollisionconfig.txt"
    files[config] = "a" * 64
    game = {"pid": PID, "birth": 10_000, "path": r"D:\SkyrimVR\SkyrimVR.exe"}
    context = {"serverBootId": "boot", "instanceId": "instance", "mo2Pid": 77, "batch": True,
               "profilesPath": r"D:\isolated\profiles"}
    before = {**context, "profile": "test-arm", "profilePath": r"D:\isolated\profiles\test-arm", "bridgeMutation": {"active": False}}
    rows, resources, selections = [], [], []
    for i, (path, digest) in enumerate(files.items(), 1):
        real = "D:\\isolated\\" + path.replace("/", "\\")
        row = {"path": path, "status": "verified", "winner": "Owned", "origins": ["Owned"], "archive": None, "real": real,
               "sha256": digest}
        rows.append(row)
        resources.append({"virtual": path, "actual": deepcopy(row), "pin": {"path": real, "bytes": 4096, "sha256": digest}})
        if path.endswith(".dll"):
            name, base = path.split("/")[-1], i * 4096
            module = {"pid": PID, "name": name, "base": base, "hModule": base}
            location = {"ntPath": "\\Device\\" + name, "physicalPath": "\\\\?\\" + real}
            mapped = {"ntPath": location["ntPath"], "allocationBase": base, "baseAddress": base, "state": 0x1000, "type": 0x1000000}
            pin = {"sha256": digest, "bytes": 4096}
            selections.append({"name": name, "module": module, "mappedBefore": mapped, "mappedAfterRead": mapped, "mappedFinal": mapped,
                               "openedBacking": location, "finalBacking": location, "pinBefore": pin, "pinFinal": pin})
    rows.extend({"path": path, "status": "not-found", "origins": [], "real": None} for path in ISOLATED_ABSENCES)
    state = {"gameEdition": "vr", "game": game, "testProfileName": "test-arm", "privateVrPoststageVfs": {
        "context": context, "observedBeforeStartup08FinalGate": True,
        "batch": {"profile": "test-arm", "complete": True, "count": len(rows), "files": rows,
                                      "snapshot": {"mappingRechecked": True, "state": "no-observed-divergence",
                                                   "observations": {"before": before, "after": deepcopy(before)}}}, "resources": resources,
        "negatives": {"configInventory": {"path": "SKSE/Plugins", "filter": "CBP*.txt", "files": [resources[-1]["pin"]["path"]]}}}}
    association = {"kind": "private-vr-bridge-observation", "location": "devbench-and-game-associated", "observation": {
        "game": deepcopy(game), "result": {"gameIdentityMatched": True}, "serverBootId": "boot", "mo2": {"pid": 77}}}
    backing = {"schema": "loaded-module-backing/2", "status": "observed", "qualified": True, "expectedProcess": deepcopy(game),
               "lastProcessIdentity": deepcopy(game), "inventoryBeforeComplete": True, "inventoryAfterComplete": True,
               "selected": selections, "inventoryBefore": [row["module"] for row in selections],
               "inventoryAfter": [row["module"] for row in selections]}
    return state, association, backing, files, {"cbpccollisionconfig.txt"}


class PlayerContactCustodyTests(unittest.TestCase):
    def test_exact_vfs_and_mapped_modules(self):
        state, association, backing, files, inventory = custody_case()
        for row in state["privateVrPoststageVfs"]["resources"]:
            row["pin"]["path"] = row["pin"]["path"].upper()
        profile, game, resources = verify_vfs(state, association, files, inventory, PID)
        self.assertEqual(profile, "test-arm")
        verify_backing(backing, game, resources)
        backing["inventoryAfter"].append({"name": "hdtSMP64.dll"})
        with self.assertRaisesRegex(ValueError, "cannot share"):
            verify_backing(backing, game, resources)

    def test_vfs_winner_inventory_and_same_process_are_required(self):
        for change in (lambda state: state["privateVrPoststageVfs"]["batch"]["files"][-1].update(status="verified"),
                       lambda state: state["privateVrPoststageVfs"]["resources"][0]["pin"].update(sha256="x"),
                       lambda state: state["privateVrPoststageVfs"]["negatives"]["configInventory"]["files"].append("extra.txt"),
                       lambda state: state["game"].update(birth=10_001)):
            with self.subTest(change=change), self.assertRaises(ValueError):
                state, association, _, files, inventory = custody_case()
                change(state)
                verify_vfs(state, association, files, inventory, PID)

    def test_correct_loaded_hash_at_unproven_or_foreign_path_is_refused(self):
        state, association, backing, files, inventory = custody_case()
        _, game, resources = verify_vfs(state, association, files, inventory, PID)
        backing["selected"][0]["finalBacking"]["physicalPath"] = r"D:\other\cbp.dll"
        with self.assertRaisesRegex(ValueError, "backing changed"):
            verify_backing(backing, game, resources)
