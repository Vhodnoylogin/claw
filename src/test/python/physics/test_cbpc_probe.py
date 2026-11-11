"""Synthetic discrimination for CBPC void receipts and local-written motion."""
import copy
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integration"))
try:
    import cbpc_probe as probe
finally:
    sys.path.pop(0)

scene = probe.scene
IDENTITY = [1., 0., 0., 0., 1., 0., 0., 0., 1.]
YAW90 = [0., -1., 0., 1., 0., 0., 0., 0., 1.]


def transform(xyz=(0., 0., 0.), rotation=IDENTITY, scale=1.):
    return {"translation": list(xyz), "rotationRowMajor": list(rotation), "scale": scale}


def compose(parent, child):
    # Independent forward fixture; production uses the inverse transform.
    p, c = parent["rotationRowMajor"], child["rotationRowMajor"]
    return transform([parent["translation"][i] + parent["scale"] * sum(p[3*i+j]*child["translation"][j] for j in range(3))
                      for i in range(3)],
                     [sum(p[3*i+k]*c[3*k+j] for k in range(3)) for i in range(3) for j in range(3)],
                     parent["scale"]*child["scale"])


def fixture(sex="female", effect=True):
    reference = "0xFF001234"
    plan = probe.prepare(reference, sex)
    identity = {"form": reference, "runtimeHandle": 12, "loadGeneration": 7}
    root_id = {"firstPerson": False, "sampledRootToken": 9,
               "identityBasis": "sampled_pointer_and_handle_changes_no_object_retention"}
    index = 0

    def snapshot(offset=(0., 0., 0.), response=.013):
        nonlocal index
        index += 1
        root = transform([100., 200., 0.], YAW90, 2.)
        row = {"schemaVersion": 1, "observerVersion": "synthetic-test-only", "ok": True, "quality": "complete",
               "sessionId": "synthetic-cbpc", "loadGeneration": 7, "sampleId": index,
               "producerMonotonicNs": 1_000_000_000 + round(index*probe.PERIOD*1e9),
               "phase": "skse_main_thread_task", "units": "skyrim_engine_units", "space": "world",
               "coherence": copy.deepcopy(scene.OBSERVATION), "producerFrame": None,
               "refs": [{"identity": identity, "rootIdentity": root_id, "baseForm": "0x000A2C90",
                         "status": "available", "loaded3D": True, "deleted": False, "disabled": False,
                         "position": [100., 200., 0.], "anglesRadians": [0., 0., math.pi/2],
                         "scale": 2., "sceneTransform": root,
                         "actor": {"status": "available", "raceStatus": "available", "sex": int(sex == "female"),
                                   "baseForm": "0x000A2C90", "race": "0x000CDD84", "baseRace": "0x000CDD84",
                                   "weight": {"status": "available", "rawNPCWeight": 50., "normalizedNPCWeight": .5}}}],
               "nodes": []}
        for name in scene.node_names(sex):
            anchor_rest = compose(root, transform([3., 4., 5.], YAW90, .5))
            anchor = compose(anchor_rest, transform(offset))
            local = transform([2., response, 0.])
            if name in scene.drivers(sex):
                world = compose(anchor, local)
            elif name in scene.anchors(sex).values():
                local, world = transform(offset), anchor
            else:
                local, world = transform(), anchor_rest
            row["nodes"].append({"form": reference, "identity": identity, "rootIdentity": root_id,
                                 "status": "available", "firstPerson": False, "name": name,
                                 "world": world, "local": local})
        return copy.deepcopy(row)

    document = {"schemaVersion": 1, "reference": reference, "sex": sex,
                "declaredPointPeriodSeconds": probe.PERIOD, "baseline": snapshot(), "receipts": {}, "windows": {}}

    def transition(action):
        document["receipts"][action] = [{"request": request, "before": snapshot(),
                                          "nativeResult": {"called": True, "returnedType": "none", "returned": None},
                                          "after": snapshot()} for request in plan["calls"][action]]

    transition("start")
    document["stimulusBaseline"] = snapshot()
    document["anchorCalibration"] = {"moved": snapshot([.25, 0., 0.]), "reset": snapshot()}
    for phase, action in zip(scene.PHASES, (None, "stop", "restart")):
        if action:
            transition(action)
        # A stopped solver may hold any constant displacement. The score uses
        # within-window variation, not zero/rest equality.
        document["windows"][phase] = [snapshot(offset, .013 + (.02*math.sin(i) if effect and phase != "stopped" else 0.))
                                           for i, offset in enumerate(plan["offsets"])]
    return document


def node(row, name):
    return next(n for n in row["nodes"] if n["name"] == name)


class CbpcProbeTests(unittest.TestCase):
    def test_local_written_contrast_and_nonzero_stopped_pose_are_accepted(self):
        for sex, count in (("male", 9), ("female", 11)):
            result = probe.score(fixture(sex))
            self.assertEqual(result["status"], "sampled-selective-contrast-observed")
            self.assertEqual(len(result["selectiveChannels"]), count)
            self.assertEqual(result["bindingState"], "unknown")
            self.assertFalse(result["solverQualified"])
            self.assertFalse(result["physicsPhaseObserved"])
            self.assertGreater(result["channels"][scene.drivers(sex)[0]]["local"]["translation"]["active"], .005)

    def test_inherited_anchor_movement_without_relative_response_is_unconfirmed(self):
        result = probe.score(fixture(effect=False))
        self.assertEqual(result["status"], "unconfirmed")
        self.assertEqual(result["selectiveChannels"], [])

    def test_only_actual_selective_rotation_channel_is_reported(self):
        document = fixture(effect=False)
        target = "NPC L Breast P1"
        for phase in ("active", "restarted"):
            for i, row in enumerate(document["windows"][phase]):
                angle = .002*math.sin(i)
                c, s = math.cos(angle), math.sin(angle)
                dynamic = node(row, target)
                dynamic["local"]["rotationRowMajor"] = [c, -s, 0., s, c, 0., 0., 0., 1.]
                dynamic["world"] = compose(node(row, "NPC L PreBreast P1")["world"], dynamic["local"])
        result = probe.score(document)
        self.assertEqual(result["status"], "sampled-selective-contrast-observed")
        self.assertEqual(result["selectiveChannels"], [{"node": target, "channel": "rotationRowMajor"}])

    def test_off_or_missing_restart_response_does_not_pass(self):
        for phase in ("active", "restarted"):
            document, neutral = fixture(), fixture(effect=False)
            for row, source in zip(document["windows"][phase], neutral["windows"][phase]):
                row["nodes"] = source["nodes"]
            self.assertEqual(probe.score(document)["status"], "unconfirmed")
        document = fixture()
        for row, source in zip(document["windows"]["stopped"], document["windows"]["active"]):
            row["nodes"] = copy.deepcopy(source["nodes"])
        self.assertEqual(probe.score(document)["status"], "unconfirmed")

    def test_cme_and_parent_animation_controls_are_required(self):
        for name, space in (("CME TailBone02", "local"), ("NPC Spine2 [Spn2]", "local"), ("NPC Root [Root]", "world")):
            document = fixture()
            node(document["windows"]["active"][5], name)[space]["translation"][1] += .02
            result = probe.score(document)
            self.assertFalse(result["unaffectedControlsQuiet"])
            self.assertEqual(result["status"], "unconfirmed")

    def test_native_none_is_not_a_bool_or_binding_receipt(self):
        for result in ({"called": True, "returnedType": "bool", "returned": True},
                       {"called": False, "returnedType": "none", "returned": None},
                       {"called": True, "returnedType": "none"},
                       {"called": True, "returnedType": "none", "returned": None, "error": "timeout"}):
            document = fixture()
            document["receipts"]["stop"][0]["nativeResult"] = result
            with self.subTest(result=result), self.assertRaises(ValueError):
                probe.score(document)

    def test_all_exact_node_calls_and_functions_are_required(self):
        for failure in ("missing", "alias", "function", "actor", "duplicate"):
            document = fixture()
            receipts = document["receipts"]["stop"]
            if failure == "missing":
                receipts.pop()
            elif failure == "alias":
                receipts[0]["request"]["args"][1] = "CLAW_EarL"
            elif failure == "function":
                receipts[0]["request"]["function"] = "ReloadConfig"
            elif failure == "actor":
                receipts[0]["request"]["args"][0]["form"] = "0xFF009999"
            else:
                receipts[1]["request"] = copy.deepcopy(receipts[0]["request"])
            with self.subTest(failure=failure), self.assertRaises(ValueError):
                probe.score(document)

    def test_identity_epoch_root_and_raw_completeness_fail_closed(self):
        for failure in ("actor", "root", "session", "epoch", "base", "weight", "node", "quality", "sex"):
            document = fixture()
            row = document["windows"]["active"][5]
            ref = row["refs"][0]
            if failure == "actor":
                ref["identity"]["form"] = "0xFF009999"
            elif failure == "root":
                ref["rootIdentity"]["sampledRootToken"] += 1
            elif failure == "session":
                row["sessionId"] = "another-session"
            elif failure == "epoch":
                row["loadGeneration"] += 1
            elif failure == "base":
                ref["baseForm"] = ref["actor"]["baseForm"] = "0x000A2C91"
            elif failure == "weight":
                ref["actor"]["weight"]["rawNPCWeight"] += 1
            elif failure == "node":
                row["nodes"].pop()
            elif failure == "quality":
                row["quality"] = "partial"
            else:
                ref["actor"]["sex"] = 0
            with self.subTest(failure=failure), self.assertRaises(ValueError):
                probe.score(document)

    def test_calibration_and_every_anchor_need_actual_world_motion(self):
        for phase in ("calibration", "window"):
            document = fixture()
            row = document["anchorCalibration"]["moved"] if phase == "calibration" else document["windows"]["active"][5]
            anchor = "NPC L PreBreast P1"
            node(row, anchor)["world"] = copy.deepcopy(node(document["stimulusBaseline"], anchor)["world"])
            with self.subTest(phase=phase), self.assertRaises(ValueError):
                probe.score(document)

    def test_cadence_must_match_predeclared_frequency(self):
        document = fixture()
        document["declaredPointPeriodSeconds"] = 1.2
        with self.assertRaises(ValueError):
            probe.score(document)
        document = fixture()
        document["windows"]["active"][5]["producerMonotonicNs"] += 200_000_000
        with self.assertRaises(ValueError):
            probe.score(document)

    def test_incomparable_windows_do_not_pass_even_inside_individual_jitter(self):
        document = fixture()
        # The stopped window runs at 0.99 s and active at 0.71 s. Each is within
        # absolute declared jitter, but their stimulus frequencies differ.
        shift = 0
        for phase, interval in (("active", -.14), ("stopped", .14), ("restarted", 0.)):
            for i, row in enumerate(document["windows"][phase]):
                row["producerMonotonicNs"] += shift + round(i*interval*1e9)
            shift += round(24*interval*1e9)
            next_action = "stop" if phase == "active" else "restart" if phase == "stopped" else None
            if next_action:
                for receipt in document["receipts"][next_action]:
                    for side in ("before", "after"):
                        receipt[side]["producerMonotonicNs"] += shift
        result = probe.score(document)
        self.assertFalse(result["excitationTimingComparable"])
        self.assertEqual(result["status"], "unconfirmed")

    def test_nonadvancing_sample_and_receipt_order_are_rejected(self):
        for kind in ("sampleId", "producerMonotonicNs"):
            document = fixture()
            document["receipts"]["restart"][0]["after"][kind] = document["baseline"][kind]
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                probe.score(document)

    def test_root_node_scale_or_rotated_anchor_are_rejected(self):
        for failure in ("root", "scale", "anchor"):
            document = fixture()
            row = document["windows"]["active"][5]
            if failure == "root":
                row["refs"][0]["sceneTransform"]["translation"][0] += .5
            elif failure == "scale":
                row["nodes"][0]["local"]["scale"] *= 1.01
            else:
                node(row, "Tails")["world"]["rotationRowMajor"] = IDENTITY[:]
            with self.subTest(failure=failure), self.assertRaises(ValueError):
                probe.score(document)

    def test_sex_specific_inventory_and_no_previous_state_claim(self):
        for sex, count in (("male", 9), ("female", 11)):
            plan = probe.prepare("0xff001234", sex)
            self.assertEqual(len(plan["calls"]["start"]), count)
            self.assertEqual(plan["calls"]["start"], plan["calls"]["restart"])
            self.assertEqual(plan["bindingState"], "unknown")
            self.assertFalse(plan["runtimeQualified"])
        with self.assertRaises(ValueError):
            probe.prepare("0x14", "female")


if __name__ == "__main__":
    unittest.main()
