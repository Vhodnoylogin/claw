"""Independent hierarchical forward fixtures for CBPC own-local pulse response."""
import copy
import math
from pathlib import Path
import sys
import unittest

from test_fsmp_probe import fixture as observer_fixture, compose, transform

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integration"))
try:
    import cbpc_pulse as probe
finally:
    sys.path.pop(0)


def fixture(sex="female", missing=(), periods=None):
    template = observer_fixture(sex, effect=False)["baseline"]
    reference = template["refs"][0]["identity"]["form"]
    plan = probe.prepare(reference, sex)
    groups = probe.pulse.families(sex)
    paths = probe.parent_paths(sex)
    parents = {name: path[0] for name, path in paths.items()}
    parents.update({f"CME TailBone{i:02}": f"TailBone{i:02}" for i in range(1, 5)})
    anchors = {name: compose(template["refs"][0]["sceneTransform"], transform([3. + i*10, 4., 5.]))
               for i, name in enumerate(groups)}
    document = {key: copy.deepcopy(plan[key]) for key in ("schemaVersion", "reference", "sex", "protocol", "stimulus", "skeletonSha256", "parentPaths")}
    document.update(receipts={}, pulses={}, anchorOriginals={anchor: {
        "key": "CLAW.FSMPProbe.synthetic-cbpc-run", "keysBefore": []} for anchor in groups})
    sample, clock = 0, 1_000_000_000

    def observe(delta=.1, moved=None, phase=None, family=None, point=0):
        nonlocal sample, clock
        sample += 1
        clock += round(delta*1e9)
        raw = copy.deepcopy(template)
        raw.update(sampleId=sample, producerMonotonicNs=clock)
        rows = {row["name"]: row for row in raw["nodes"]}
        for name in rows:
            if name in paths:
                response = 0.
                if family and name in groups[family] and phase != "stopped" and name not in missing:
                    response = .04*math.exp(-point/5)*math.cos(.8*point)
                rows[name]["local"] = transform([2., .013 + response, 0.])
            else:
                rows[name]["local"] = transform()
        cache = {}
        def world(name):
            if name not in cache:
                if name in anchors:
                    cache[name] = compose(anchors[name], transform(probe.pulse.offset(name) if name == moved else [0., 0., 0.]))
                    rows[name]["local"] = transform(probe.pulse.offset(name) if name == moved else [0., 0., 0.])
                elif name in parents:
                    cache[name] = compose(world(parents[name]), rows[name]["local"])
                else:
                    cache[name] = copy.deepcopy(rows[name]["world"])
            return cache[name]
        for name in rows:
            rows[name]["world"] = world(name)
        return raw

    def transition(action):
        document["receipts"][action] = []
        for request in plan["calls"][action]:
            document["receipts"][action].append({"request": request, "before": observe(), "after": observe(),
                "nativeResult": {"called": True, "returnedType": "none", "returned": None}})

    def commands(anchor, displacement):
        args = [{"form": reference}, False, sex == "female", anchor]
        return [{"script": "NiOverride", "function": function, "args": values,
                 "nativeResult": {"called": True, "returnedType": "none", "returned": None}}
                for function, values in (("AddNodeTransformPosition", args + [document["anchorOriginals"][anchor]["key"], displacement]),
                                         ("UpdateNodeTransform", args))]

    document["baseline"] = observe()
    transition("start")
    document["stimulusBaseline"] = observe()
    for phase, action in zip(probe.scene.PHASES, (None, "stop", "restart")):
        if action:
            transition(action)
        document["pulses"][phase] = {}
        for anchor in groups:
            document["pulses"][phase][anchor] = {"beforePulse": observe(), "moved": observe(moved=anchor),
                "returned": observe(.2), "commands": {"moved": commands(anchor, probe.pulse.offset(anchor)),
                "returned": commands(anchor, [0., 0., 0.])}, "samples": [
                    observe((periods or {}).get(phase, .1), phase=phase, family=anchor, point=i) for i in range(25)]}
    return document


def node(raw, name):
    return next(row for row in raw["nodes"] if row["name"] == name)


def first(document, phase="active"):
    return next(iter(document["pulses"][phase].values()))


class CbpcPulseTests(unittest.TestCase):
    def test_all_drivers_need_own_local_and_parent_relative_response(self):
        for sex, count in (("male", 9), ("female", 11)):
            result = probe.score(fixture(sex))
            self.assertEqual(result["status"], "sampled-pulse-contrast-observed")
            self.assertEqual(len(result["selectiveChannels"]), count)
            self.assertFalse(result["missingDrivers"])
            self.assertEqual(result["bindingState"], "unknown")
            self.assertFalse(result["runtimeQualified"])
            self.assertFalse(result["solverQualified"])
            self.assertNotIn("restoredPreviousState", result)

    def test_never_bound_child_inheriting_bound_parent_motion_does_not_pass(self):
        document = fixture(missing=("TailBone05",))
        rows = document["pulses"]["active"]["Tails"]["samples"]
        self.assertGreater(probe.scene.spread([node(raw, "TailBone05")["world"]["translation"] for raw in rows]), .01)
        self.assertEqual(probe.scene.spread([node(raw, "TailBone05")["local"]["translation"] for raw in rows]), 0.)
        result = probe.score(document)
        self.assertEqual(result["status"], "unconfirmed")
        self.assertEqual(result["missingDrivers"], ["TailBone05"])

    def test_world_only_writer_is_not_a_cbpc_local_write(self):
        document = fixture()
        for phase in ("active", "restarted"):
            for group in document["pulses"][phase].values():
                for raw in group["samples"]:
                    for name in probe.scene.drivers("female"):
                        node(raw, name)["local"] = transform([2., .013, 0.])
        result = probe.score(document)
        self.assertEqual(len(result["missingDrivers"]), 11)
        self.assertEqual(result["status"], "unconfirmed")

    def test_local_only_without_parent_relative_world_response_does_not_pass(self):
        document = fixture()
        for phase in ("active", "restarted"):
            for group in document["pulses"][phase].values():
                for raw in group["samples"]:
                    for name in probe.scene.drivers("female"):
                        node(raw, name)["world"] = copy.deepcopy(node(group["beforePulse"], name)["world"])
        self.assertEqual(probe.score(document)["status"], "unconfirmed")

    def test_one_missing_p1_cannot_hide_behind_ten_responding_drivers(self):
        result = probe.score(fixture(missing=("NPC L Breast P1",)))
        self.assertEqual(result["missingDrivers"], ["NPC L Breast P1"])
        self.assertEqual(result["status"], "unconfirmed")

    def test_nonzero_frozen_stopped_pose_uses_its_own_before_pulse_baseline(self):
        document = fixture()
        parents = {name: path[0] for name, path in probe.parent_paths("female").items()}
        parents.update({f"CME TailBone{i:02}": f"TailBone{i:02}" for i in range(1, 5)})
        for group in document["pulses"]["stopped"].values():
            for raw in (group["beforePulse"], group["moved"], group["returned"], *group["samples"]):
                rows = {row["name"]: row for row in raw["nodes"]}
                for name in probe.scene.FEMALE:
                    rows[name]["local"] = transform([2., .213, 0.])
                cache = {}
                def world(name):
                    if name not in cache:
                        cache[name] = compose(world(parents[name]), rows[name]["local"]) if name in parents else rows[name]["world"]
                    return cache[name]
                for name in rows:
                    rows[name]["world"] = world(name)
        self.assertEqual(probe.score(document)["status"], "sampled-pulse-contrast-observed")

    def test_stale_immediate_parent_input_does_not_qualify_child(self):
        document = fixture()
        for phase in probe.scene.PHASES:
            group = document["pulses"][phase]["Tails"]
            original = node(group["beforePulse"], "CME TailBone04")["world"]
            for raw in (group["moved"], group["returned"], *group["samples"]):
                node(raw, "CME TailBone04")["world"] = copy.deepcopy(original)
        result = probe.score(document)
        self.assertIn("TailBone05", result["missingDrivers"])
        self.assertEqual(result["status"], "unconfirmed")

    def test_exact_pinned_parent_paths_and_skeleton_are_required(self):
        for failure in ("skeleton", "path", "missing"):
            document = fixture()
            if failure == "skeleton":
                document["skeletonSha256"] = "unverified"
            elif failure == "path":
                document["parentPaths"]["TailBone05"] = ["Tails"]
            else:
                document.pop("parentPaths")
            with self.subTest(failure=failure), self.assertRaisesRegex(ValueError, "Pinned XP32"):
                probe.score(document)

    def test_missing_or_uncertain_node_control_receipts_fail_closed(self):
        for failure in ("missing", "boolean", "unknown", "alias"):
            document = fixture()
            receipt = document["receipts"]["stop"][0]
            if failure == "missing":
                document["receipts"]["stop"].pop()
            elif failure == "boolean":
                receipt["nativeResult"] = {"called": True, "returnedType": "bool", "returned": True}
            elif failure == "unknown":
                receipt["nativeResult"] = {"called": True, "returnedType": "none"}
            else:
                receipt["request"]["args"][1] = "CLAW_Tail"
            with self.subTest(failure=failure), self.assertRaises(ValueError):
                probe.score(document)

    def test_mutation_completion_cannot_be_inferred_from_visible_offset(self):
        document = fixture()
        first(document)["commands"]["moved"][1]["nativeResult"] = {"called": False, "returnedType": "none", "returned": None}
        with self.assertRaisesRegex(ValueError, "write completion"):
            probe.score(document)

    def test_moving_anchor_off_stale_world_confound_is_rejected(self):
        document = fixture()
        for raw in first(document)["samples"]:
            node(raw, "NPC Head [Head]")["world"]["translation"][0] += .05
        with self.assertRaisesRegex(ValueError, "anchor did not return/drifted"):
            probe.score(document)

    def test_independent_local_controls_must_remain_quiet(self):
        for name in ("CME TailBone02", "NPC Spine2 [Spn2]"):
            document = fixture()
            node(first(document)["samples"][0], name)["local"]["translation"][0] += .01
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "Independent CBPC local control"):
                probe.score(document)

    def test_epoch_or_nonadvancing_sample_cannot_be_scored(self):
        for field, value in (("sessionId", "other-game"), ("producerMonotonicNs", 1), ("sampleId", 1)):
            document = fixture()
            first(document)["samples"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                probe.score(document)

    def test_born_beast_race_is_required(self):
        document = fixture()
        document["baseline"]["refs"][0]["actor"]["race"] = "0x00013749"
        with self.assertRaisesRegex(ValueError, "Born-beast"):
            probe.score(document)

    def test_transformed_human_cannot_satisfy_the_born_beast_gate(self):
        document = fixture()
        def set_human_base(value):
            if isinstance(value, dict):
                if "actor" in value:
                    value["actor"]["baseRace"] = "0x00013749"
                for item in value.values():
                    set_human_base(item)
            elif isinstance(value, list):
                for item in value:
                    set_human_base(item)
        set_human_base(document)
        with self.assertRaisesRegex(ValueError, "Born-beast"):
            probe.score(document)

    def test_actual_read_cadence_stays_predeclared(self):
        with self.assertRaisesRegex(ValueError, "cadence/span"):
            probe.score(fixture(periods={"active": .3}))
        result = probe.score(fixture(periods={"stopped": .16}))
        self.assertFalse(result["excitationTimingComparable"])
        self.assertEqual(result["status"], "unconfirmed")

    def test_constant_post_return_pose_is_not_motion(self):
        document = fixture()
        for phase in ("active", "restarted"):
            for group in document["pulses"][phase].values():
                sample = copy.deepcopy(group["samples"][0]["nodes"])
                for raw in group["samples"]:
                    raw["nodes"] = copy.deepcopy(sample)
        self.assertEqual(probe.score(document)["status"], "unconfirmed")

    def test_no_local_response_remains_unknown_not_bound(self):
        result = probe.score(fixture(missing=probe.scene.FEMALE))
        self.assertEqual(result["status"], "unconfirmed")
        self.assertEqual(len(result["missingDrivers"]), 11)
        self.assertEqual(result["bindingState"], "unknown")


if __name__ == "__main__":
    unittest.main()
