"""Motion discrimination, real-world inverse transforms and binding negatives."""
import copy
import importlib.util
import math
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "integration/fsmp_probe.py"
SPEC = importlib.util.spec_from_file_location("fsmp_probe", PATH)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)

IDENTITY = [1., 0., 0., 0., 1., 0., 0., 0., 1.]
YAW90 = [0., -1., 0., 1., 0., 0., 0., 0., 1.]


def transform(xyz=None, rotation=None, scale=1.):
    return {"translation": list(xyz or [0., 0., 0.]),
            "rotationRowMajor": list(rotation or IDENTITY), "scale": scale}


def compose(parent, child):
    # Independent forward transform fixture, not the production inverse.
    pr, cr = parent["rotationRowMajor"], child["rotationRowMajor"]
    xyz = child["translation"]
    return transform([parent["translation"][i] + parent["scale"]*sum(pr[3*i+j]*xyz[j] for j in range(3))
                      for i in range(3)],
                     [sum(pr[3*i+k]*cr[3*k+j] for k in range(3)) for i in range(3) for j in range(3)],
                     parent["scale"]*child["scale"])


def fixture(sex="female", effect=True):
    reference = "0xFF001234"
    identity = {"form": reference, "runtimeHandle": 12, "loadGeneration": 7}
    root_id = {"firstPerson": False, "sampledRootToken": 9,
               "identityBasis": "sampled_pointer_and_handle_changes_no_object_retention"}
    plan = probe.prepare(reference, sex, [100., 200., 0.])
    index = 0

    def snapshot(position, phase="stopped", step=0):
        nonlocal index
        index += 1
        root = transform(position, YAW90, 2.)
        row = {"schemaVersion": 1, "observerVersion": "0.3.1-se104-candidate", "ok": True, "quality": "complete",
               "sessionId": "synthetic-observer", "loadGeneration": 7, "sampleId": index,
               "producerMonotonicNs": 1_000_000_000 + index*200_000_000,
               "phase": "skse_main_thread_task", "units": "skyrim_engine_units", "space": "world",
               "coherence": copy.deepcopy(probe.OBSERVATION), "producerFrame": None,
               "refs": [{"identity": identity, "rootIdentity": root_id, "baseForm": "0x000A2C90",
                         "status": "available", "loaded3D": True, "deleted": False, "disabled": False,
                         "position": position, "anglesRadians": [0., 0., math.pi/2], "scale": 2., "sceneTransform": root,
                         "actor": {"status": "available", "raceStatus": "available", "sex": int(sex == "female"),
                                   "baseForm": "0x000A2C90", "race": "0x000CDD84", "baseRace": "0x000CDD84",
                                   "weight": {"status": "available", "rawNPCWeight": 50., "normalizedNPCWeight": .5}}}],
               "nodes": []}
        for name in probe.node_names(sex):
            # Common translating/rotating/scaled anchor. A genuine world-only
            # solver offset leaves local animation exactly unchanged.
            anchor = compose(root, transform([3., 4., 5.], YAW90, .5))
            local = transform([2., 0., 0.]) if name in probe.drivers(sex) else transform()
            offset = transform([2., .02*math.sin(step) if effect and phase != "stopped" else 0., 0.])
            world = compose(anchor, offset) if name in probe.drivers(sex) else anchor
            row["nodes"].append({"form": reference, "identity": identity, "rootIdentity": root_id,
                                 "status": "available", "firstPerson": False, "name": name,
                                 "world": world, "local": local})
        return copy.deepcopy(row)

    baseline = snapshot(plan["origin"])
    n = len(probe.drivers(sex))
    receipts, windows = {}, {}

    def receipt(action, state):
        receipts[action] = {"previous": [state]*n, "before": snapshot(plan["origin"]), "after": snapshot(plan["origin"])}

    receipt("first-off", True)
    receipt("reenable", False)
    for phase in probe.PHASES:
        if phase == "stopped":
            receipt("second-off", True)
        elif phase == "restarted":
            receipt("restore", False)
        windows[phase] = [snapshot(item["expectedPosition"], phase, step)
                          for step, item in enumerate(plan["windows"][phase])]
    return {"reference": reference, "sex": sex, "baseline": baseline, "windows": windows,
            "receipts": receipts}


class FsmpProbeTests(unittest.TestCase):
    def test_inverse_rotated_scaled_anchor(self):
        parent = transform([7., 11., 13.], YAW90, 2.)
        child = transform([3., -5., 2.], YAW90, .5)
        actual = probe.relative(compose(parent, child), parent)
        for key in ("translation", "rotationRowMajor"):
            for x, y in zip(actual[key], child[key]):
                self.assertAlmostEqual(x, y)
        self.assertEqual(actual["scale"], child["scale"])

    def test_dynamic_anchor_rotation_and_scale_do_not_create_relative_motion(self):
        child = transform([3., -5., 2.], YAW90, .5)
        for angle, scale in ((0., 1.), (.4, 2.), (-.8, .25)):
            c, s = math.cos(angle), math.sin(angle)
            parent = transform([7., angle*10, 13.], [c, -s, 0., s, c, 0., 0., 0., 1.], scale)
            actual = probe.relative(compose(parent, child), parent)
            for key in ("translation", "rotationRowMajor"):
                for x, y in zip(actual[key], child[key]):
                    self.assertAlmostEqual(x, y)

    def test_rotation_and_translation_inherited_from_anchor_are_not_physics(self):
        document = fixture(effect=False)
        # Entire actor and all anchors may move in world. Relative motion must
        # still be zero even with nonidentity rotation and nonunit scale.
        result = probe.score(document)
        self.assertEqual(result["status"], "unconfirmed")
        self.assertEqual(result["selectiveChannels"], [])

    def test_world_only_response_survives_constant_local_channels(self):
        for sex in ("male", "female"):
            result = probe.score(fixture(sex))
            self.assertEqual(result["status"], "sampled-selective-contrast-observed")
            self.assertTrue(result["localAnimationQuiet"])
            self.assertTrue(result["anchorsRootRelativeQuiet"])
            self.assertEqual(len(result["selectiveChannels"]), 9 if sex == "male" else 11)
            self.assertFalse(result["solverQualified"])
            self.assertFalse(result["physicsPhaseObserved"])

    def test_animation_only_response_is_unconfirmed(self):
        document = fixture()
        document["windows"]["active"][5]["nodes"][0]["local"]["translation"][0] += .02
        self.assertFalse(probe.score(document)["localAnimationQuiet"])
        self.assertEqual(probe.score(document)["status"], "unconfirmed")

    def test_moving_anchor_cannot_supply_selective_evidence(self):
        document = fixture()
        anchor = next(row for row in document["windows"]["active"][5]["nodes"] if row["name"] == "Tails")
        anchor["world"]["translation"][0] += .02
        self.assertFalse(probe.score(document)["anchorsRootRelativeQuiet"])
        self.assertEqual(probe.score(document)["status"], "unconfirmed")

    def test_binding_missing_kinematic_false_and_malformed_returns_block(self):
        for replacement in ([False]*11, [True]*10, [1]*11, None):
            document = fixture()
            document["receipts"]["first-off"]["previous"] = replacement
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                probe.score(document)

    def test_each_previous_state_transition_is_required(self):
        for action in ("reenable", "second-off", "restore"):
            document = fixture()
            document["receipts"][action]["previous"][0] = not document["receipts"][action]["previous"][0]
            with self.subTest(action=action), self.assertRaises(ValueError):
                probe.score(document)

    def test_root_change_missing_parent_stale_sample_and_bad_excitation_block(self):
        for failure in ("root", "parent", "sample", "position", "rotation", "scale", "unmoved-root"):
            document = fixture()
            row = document["windows"]["active"][5]
            if failure == "root":
                row["refs"][0]["rootIdentity"]["sampledRootToken"] += 1
            elif failure == "parent":
                row["nodes"] = [n for n in row["nodes"] if n["name"] != "Tails"]
            elif failure == "sample":
                row["sampleId"] = 1
            elif failure == "position":
                row["refs"][0]["position"][0] += 1.
            elif failure == "rotation":
                row["nodes"][0]["world"]["rotationRowMajor"] = [1.]*9
            elif failure == "scale":
                row["nodes"][0]["world"]["scale"] *= 1.02
            else:
                row["refs"][0]["sceneTransform"]["translation"][0] = 100.
            with self.subTest(failure=failure), self.assertRaises(ValueError):
                probe.score(document)

    def test_observation_without_advancing_time_does_not_count(self):
        document = fixture()
        document["windows"]["active"][1]["producerMonotonicNs"] = document["windows"]["active"][0]["producerMonotonicNs"]
        with self.assertRaises(ValueError):
            probe.score(document)

    def test_different_excitation_frequency_is_not_attributed_to_solver(self):
        document = fixture()
        # Slow stopped window, shift restart to retain monotonic continuity.
        for i, row in enumerate(document["windows"]["stopped"]):
            row["producerMonotonicNs"] += i*100_000_000
        for row in document["windows"]["restarted"]:
            row["producerMonotonicNs"] += 2_400_000_000
        for side in ("before", "after"):
            document["receipts"]["restore"][side]["producerMonotonicNs"] += 2_400_000_000
        result = probe.score(document)
        self.assertFalse(result["excitationTimingComparable"])
        self.assertEqual(result["status"], "unconfirmed")

    def test_receipt_wrong_actor_root_or_order_does_not_qualify_binding(self):
        for failure in ("actor", "root", "order"):
            document = fixture()
            row = document["receipts"]["second-off"]["after"]
            if failure == "actor":
                row["refs"][0]["identity"]["form"] = "0xFF009999"
            elif failure == "root":
                row["refs"][0]["rootIdentity"]["sampledRootToken"] += 1
            else:
                row["sampleId"] = document["receipts"]["reenable"]["after"]["sampleId"]
            with self.subTest(failure=failure), self.assertRaises(ValueError):
                probe.score(document)

    def test_cme_animation_between_tail_drivers_is_not_solver_evidence(self):
        document = fixture()
        intermediate = next(row for row in document["windows"]["active"][5]["nodes"]
                            if row["name"] == "CME TailBone02")
        intermediate["local"]["translation"][1] += .01
        result = probe.score(document)
        self.assertFalse(result["localAnimationQuiet"])
        self.assertEqual(result["status"], "unconfirmed")

    def test_generated_packets_select_sex_specific_xml_names_and_float_positions(self):
        for sex in ("male", "female"):
            plan = probe.prepare("0xff001234", sex, [100, 200, 300])
            self.assertEqual(len(plan["togglePackets"]["first-off"]["args"]["args"][1]), 9 if sex == "male" else 11)
            self.assertEqual(plan["windows"]["active"], plan["windows"]["stopped"])
            self.assertEqual(plan["windows"]["active"], plan["windows"]["restarted"])
            for row in plan["windows"]["active"]:
                self.assertTrue(all(type(v) is float for v in row["steps"][0]["args"]["args"]))
            self.assertEqual(plan["windows"]["active"][-1]["expectedPosition"], plan["origin"])
        with self.assertRaises(ValueError):
            probe.prepare("0x14", "male", [0., 0., 0.])


if __name__ == "__main__":
    unittest.main()
