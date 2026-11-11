"""Case orchestration negatives; synthetic Session, no game or transport."""
import copy
import importlib.util
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

from test_fsmp_probe import fixture

INTEGRATION = Path(__file__).resolve().parents[1] / "integration"
sys.path.insert(0, str(INTEGRATION))
try:
    import fsmp_owned_case as case
finally:
    sys.path.remove(str(INTEGRATION))


class Session:
    def __init__(self, directory, previous=None, timeout=False):
        self.dir = Path(directory)
        self.state = {"checks": []}
        self.sample = fixture("male", effect=False)["baseline"]
        self.calls = []
        self.previous = [True]*9 if previous is None else previous
        self.timeout = timeout

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
            for transform in transforms:
                transform["translation"] = [x+y for x,y in zip(transform["translation"], delta)]
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


if __name__ == "__main__":
    unittest.main()
