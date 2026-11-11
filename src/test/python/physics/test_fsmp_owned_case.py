"""Case orchestration negatives; synthetic Session, no game or transport."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

from test_fsmp_probe import fixture, compose, transform

INTEGRATION = Path(__file__).resolve().parents[1] / "integration"
sys.path.insert(0, str(INTEGRATION))
try:
    import fsmp_owned_case as case
finally:
    sys.path.remove(str(INTEGRATION))


class Session:
    def __init__(self, directory, previous=None, timeout=False, frozen_anchors=False, world_response=False):
        self.dir = Path(directory)
        self.state = {"checks": [], "id": "synthetic-owned-run"}
        self.sample = fixture("male", effect=False)["baseline"]
        self.calls = []
        self.previous = [True]*9 if previous is None else previous
        self.timeout = timeout
        self.frozen_anchors = frozen_anchors
        self.world_response = world_response
        self.anchor_keys = {}
        self.original_nodes = {n["name"]: copy.deepcopy(n) for n in self.sample["nodes"]}

    def save(self):
        pass

    def phase(self, *args):
        pass

    def tool(self, tool, args, **kwargs):
        self.calls.append((tool, copy.deepcopy(args)))
        if tool == "inspect":
            self.sample["sampleId"] += 1
            self.sample["producerMonotonicNs"] += 200_000_000
            return copy.deepcopy(self.sample)
        if args.get("script") == "NiOverride":
            function, values = args["function"], args["args"]
            name = values[3]
            if function == "GetNodeTransformKeys":
                return {"returned": list(self.anchor_keys.get(name, {}))}
            key = values[4] if len(values) > 4 else None
            if function == "HasNodeTransformPosition":
                return {"returned": key in self.anchor_keys.get(name, {})}
            if function == "AddNodeTransformPosition":
                self.anchor_keys.setdefault(name, {})[key] = values[5][:]
            elif function == "GetNodeTransformPosition":
                return {"returned": self.anchor_keys[name][key][:]}
            elif function == "RemoveNodeTransformPosition":
                return {"returned": self.anchor_keys[name].pop(key, None) is not None}
            elif function == "UpdateNodeTransform" and not self.frozen_anchors:
                offset = next(iter(self.anchor_keys.get(name, {}).values()), [0.,0.,0.])
                anchor_world = self.original_nodes[name]["world"]
                moved = compose(anchor_world, transform(offset))
                for row in self.sample["nodes"]:
                    if row["name"] == name:
                        row["world"] = moved
                        row["local"] = compose(self.original_nodes[name]["local"], transform(offset))
                    elif case.probe.anchors("male").get(row["name"]) == name or (
                            name == "Tails" and row["name"] in case.probe.INTERMEDIATES):
                        rest = case.probe.relative(self.original_nodes[row["name"]]["world"], anchor_world)
                        if self.world_response and row["name"] in case.probe.MALE and all(self.previous):
                            rest["translation"][1] += .03*offset[0]
                        row["world"] = compose(moved, rest)
            return {"returned": None}
        if args.get("script") == "NetImmerse":
            name, value = args["args"][1:3]
            row = next(row for row in self.sample["nodes"] if row["name"] == name)
            channel = {"SetNodeLocalPosition": "translation", "SetNodeLocalRotationMatrix": "rotationRowMajor", "SetNodeScale": "scale"}[args["function"]]
            row["local"][channel] = copy.deepcopy(value)
            return {"returned": None if channel == "scale" else True}
        if args.get("function") == "TogglePhysics":
            if self.timeout:
                raise TimeoutError("synthetic unknown native return")
            names, on = args["args"][1:]
            indices = [case.probe.drivers("male").index(name) for name in names]
            previous = [self.previous[index] for index in indices]
            for index in indices:
                self.previous[index] = on
            return {"called": True, "returned": previous}
        if args.get("function") == "SetPosition":
            old = self.sample["refs"][0]["position"]
            delta = [x-y for x,y in zip(args["args"],old)]
            self.sample["refs"][0]["position"] = args["args"][:]
            transforms = [self.sample["refs"][0]["sceneTransform"]] + [row["world"] for row in self.sample["nodes"]]
            for node_transform in transforms:
                node_transform["translation"] = [x+y for x,y in zip(node_transform["translation"], delta)]
        return {"called": True, "returned": None}


class OwnedFsmpCaseTests(unittest.TestCase):
    def test_false_binding_gate_never_excites_or_enables_missing_nodes(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session(directory, previous=[False]*9)
            with self.assertRaisesRegex(ValueError, "dynamic-body gate"):
                case.run(session, "0xFF001234", "male")
            toggles = [args for tool,args in session.calls if args.get("function") == "TogglePhysics"]
            self.assertEqual(len(toggles), 1)
            self.assertFalse(toggles[0]["args"][2])
            positions = [args["args"] for tool,args in session.calls if args.get("function") == "SetPosition"]
            self.assertTrue(all(position == [100., 200., 0.] for position in positions))

    def test_partial_binding_restores_only_originally_dynamic_names(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session(directory, previous=[True] + [False]*8)
            with self.assertRaisesRegex(ValueError, "dynamic-body gate"):
                case.run(session, "0xFF001234", "male")
            toggles = [args for tool,args in session.calls if args.get("function") == "TogglePhysics"]
            self.assertEqual(len(toggles), 2)
            self.assertEqual(toggles[1]["args"][1], [case.probe.MALE[0]])
            self.assertTrue(toggles[1]["args"][2])
            self.assertEqual(session.previous, [True] + [False]*8)

    def test_uncertain_native_return_is_not_replayed_or_blindly_restored(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session(directory, timeout=True)
            with self.assertRaises(TimeoutError):
                case.run(session, "0xFF001234", "male")
            toggles = [args for tool,args in session.calls if args.get("function") == "TogglePhysics"]
            self.assertEqual(len(toggles), 1)
            self.assertTrue(session.state["fsmpProbe"]["uncertain"])

    def test_successful_state_protocol_does_not_claim_physics_from_root_motion(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session(directory)
            result = case.run(session, "0xFF001234", "male")
            self.assertEqual(result["status"], "unconfirmed")
            self.assertFalse(result["solverQualified"])
            self.assertEqual(session.previous, [True]*9)
            self.assertEqual(session.sample["refs"][0]["position"], [100., 200., 0.])

    def test_owned_anchor_keys_are_cleaned_without_writing_dynamic_bones(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session(directory)
            result = case.run(session, "0xFF001234", "male", stimulus="xml-anchors")
            self.assertEqual(result["status"], "unconfirmed")
            self.assertTrue(result["anchorExcitationQualified"])
            self.assertEqual(session.previous, [True]*9)
            self.assertTrue(all(not values for values in session.anchor_keys.values()))
            writes = [args for tool,args in session.calls if args.get("script") in ("NiOverride", "NetImmerse")
                      and args.get("function", "").startswith(("Add", "Remove", "Update", "Set"))]
            self.assertTrue(writes)
            for args in writes:
                node = args["args"][3] if args["script"] == "NiOverride" else args["args"][1]
                self.assertIn(node, ("NPC Head [Head]", "Tails"))

    def test_stored_key_without_real_anchor_movement_stops_early(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session(directory, frozen_anchors=True)
            with self.assertRaisesRegex(ValueError, "anchor world displacement"):
                case.run(session, "0xFF001234", "male", stimulus="xml-anchors")
            state = json.loads((Path(directory)/"fsmp-probe/state.json").read_bytes())
            self.assertEqual(state["windows"], {})
            self.assertTrue(all(not values for values in session.anchor_keys.values()))

    def test_direct_anchor_world_response_is_discriminated_without_local_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session(directory, world_response=True)
            result = case.run(session, "0xFF001234", "male", stimulus="xml-anchors")
            self.assertEqual(result["status"], "sampled-selective-contrast-observed")
            self.assertTrue(result["localAnimationQuiet"])
            self.assertTrue(result["controlParentsQuiet"])
            self.assertFalse(result["solverQualified"])


if __name__ == "__main__":
    unittest.main()
