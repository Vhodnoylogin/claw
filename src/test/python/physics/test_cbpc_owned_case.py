"""Owned CBPC transport tests with independent hierarchical scene/void controls."""
import copy
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

from test_cbpc_pulse import fixture, compose, transform

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integration"))
try:
    import cbpc_owned_case as case
finally:
    sys.path.pop(0)


class Session:
    def __init__(self, directory, sex="female", uncertain=None, fail_head_restore=False):
        self.dir = Path(directory)
        self.state = {"id": "synthetic-cbpc-owned", "checks": []}
        self.sex, self.uncertain, self.fail_head_restore = sex, uncertain, fail_head_restore
        self.sample = fixture(sex)["baseline"]
        self.original = {row["name"]: copy.deepcopy(row) for row in self.sample["nodes"]}
        self.parents = {name: path[0] for name, path in case.probe.parent_paths(sex).items()}
        self.parents.update({f"CME TailBone{i:02}": f"TailBone{i:02}" for i in range(1, 5)})
        self.on = {name: True for name in case.scene.drivers(sex)}
        self.keys, self.offsets, self.calls, self.counts = {}, {}, [], {}
        self.phase_name = ""
        self.mutation_journals = []

    def save(self):
        pass

    def phase(self, name, *args):
        self.phase_name = name

    def observe(self):
        self.sample["sampleId"] += 1
        self.sample["producerMonotonicNs"] += 100_000_000
        rows = {row["name"]: row for row in self.sample["nodes"]}
        family, point = None, 0
        if "-pulse-sample-" in self.phase_name:
            family, point = self.phase_name.split("-pulse-sample-", 1)[1].rsplit("-", 1)
            point = int(point)
        groups = case.pulse.families(self.sex)
        for name in self.on:
            response = (.04*math.exp(-point/5)*math.cos(.8*point)
                        if family and name in groups[family] and self.on[name] else 0.)
            rows[name]["local"] = transform([2., .013 + response, 0.])
        cache = {}

        def world(name):
            if name not in cache:
                if name in groups:
                    cache[name] = compose(self.original[name]["world"], transform(self.offsets.get(name, [0., 0., 0.])))
                elif name in self.parents:
                    cache[name] = compose(world(self.parents[name]), rows[name]["local"])
                else:
                    cache[name] = copy.deepcopy(self.original[name]["world"])
            return cache[name]
        for name in rows:
            rows[name]["world"] = world(name)
        return copy.deepcopy(self.sample)

    def tool(self, tool, args, **kwargs):
        self.calls.append((tool, copy.deepcopy(args)))
        if tool == "inspect":
            return self.observe()
        function, script, values = args["function"], args["script"], args.get("args", [])
        mutating = function.startswith(("StartPhysics", "StopPhysics", "AddNode", "RemoveNode", "UpdateNode", "SetNode"))
        if mutating:
            journal = json.loads((self.dir/"cbpc-probe/journal.json").read_bytes())
            intent = journal["intent"]
            request = intent.get("request", intent)
            assert request["function"] == function and request["args"] == values
            self.mutation_journals.append(copy.deepcopy(intent))
        result = None
        if script == "CBPCPluginScript":
            self.on[values[1]] = function == "StartPhysics"
            self.counts[function] = self.counts.get(function, 0) + 1
            if self.uncertain == (function, self.counts[function]):
                raise TimeoutError("synthetic unknown provider completion after possible effect")
        elif script == "NiOverride":
            name = values[3]
            key = values[4] if len(values) > 4 else None
            data = self.keys.setdefault(name, {})
            if function == "GetNodeTransformKeys":
                result = list(data)
            elif function == "HasNodeTransformPosition":
                result = key in data  # Actual provider retains an empty container.
            elif function == "AddNodeTransformPosition":
                data[key] = values[5][:]
            elif function == "GetNodeTransformPosition":
                result = (data[key] or [0., 0., 0.])[:]
            elif function == "RemoveNodeTransformPosition":
                result = data.get(key) is not None
                if key in data:
                    data[key] = None
            elif function == "UpdateNodeTransform":
                offset = next((value for value in data.values() if value is not None), [0., 0., 0.])
                self.offsets[name] = offset[:]
                row = next(row for row in self.sample["nodes"] if row["name"] == name)
                row["local"] = compose(self.original[name]["local"], transform(offset))
        elif script == "NetImmerse":
            name, value = values[1:3]
            row = next(row for row in self.sample["nodes"] if row["name"] == name)
            channel = {"SetNodeLocalPosition": "translation", "SetNodeLocalRotationMatrix": "rotationRowMajor", "SetNodeScale": "scale"}[function]
            result = None if channel == "scale" else True
            if self.fail_head_restore and name == "NPC Head [Head]" and channel == "rotationRowMajor":
                result = False
            else:
                row["local"][channel] = copy.deepcopy(value)
        elif function == "Disable":
            self.sample["refs"][0]["disabled"] = True
            self.sample["refs"][0]["loaded3D"] = False
        elif function == "GetCurrentCrosshairRef":
            result = None if self.sample["refs"][0]["disabled"] else {"formId": "0xFF001234"}
        return {"called": True, "returnedType": "bool" if type(result) is bool else "none", "returned": result}


class OwnedCbpcPulseTests(unittest.TestCase):
    def controls(self, session):
        return [args for _, args in session.calls if args.get("script") == "CBPCPluginScript"]

    def test_exact_all_nodes_void_controls_and_unknown_state_are_preserved(self):
        for sex, count in (("male", 9), ("female", 11)):
            with self.subTest(sex=sex), tempfile.TemporaryDirectory() as directory:
                session = Session(directory, sex)
                result = case.run(session, "0xFF001234", sex, sleep=lambda _: None)
                self.assertEqual(result["status"], "sampled-pulse-contrast-observed")
                expected = case.probe.prepare("0xFF001234", sex)["calls"]
                self.assertEqual(self.controls(session), [row for stage in ("start", "stop", "restart") for row in expected[stage]])
                self.assertEqual(len(result["selectiveChannels"]), count)
                self.assertEqual(result["bindingState"], "unknown")
                self.assertFalse(result["runtimeQualified"])
                state = json.loads((Path(directory)/"cbpc-probe/state.json").read_bytes())
                cleanup = json.loads((Path(directory)/"cbpc-probe/cleanup.json").read_bytes())
                self.assertEqual(state["providerOriginalState"], "unknown")
                self.assertFalse(cleanup["providerRestorationClaimed"])
                self.assertEqual(cleanup["providerCleanupCalls"], [])
                self.assertFalse(cleanup["errors"])
                self.assertTrue(session.mutation_journals)
                self.assertTrue(all(value is None for keys in session.keys.values() for value in keys.values()))

    def test_unknown_initial_start_is_not_replayed_or_compensated(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session(directory, uncertain=("StartPhysics", 1))
            with self.assertRaises(TimeoutError):
                case.run(session, "0xFF001234", "female", sleep=lambda _: None)
            self.assertEqual(len(self.controls(session)), 1)
            self.assertFalse(session.keys)
            self.assertTrue(session.state["cbpcProbe"]["uncertain"])
            state = json.loads((Path(directory)/"cbpc-probe/state.json").read_bytes())
            self.assertEqual(state["uncertainProviderCall"]["request"]["function"], "StartPhysics")

    def test_nonvoid_or_missing_provider_return_never_reaches_excitation(self):
        for native in ({"called": True, "returnedType": "bool", "returned": True},
                       {"called": True, "returnedType": "none"},
                       {"called": False, "returnedType": "none", "returned": None}):
            class WrongCompletion(Session):
                def tool(self, tool, args, **kwargs):
                    result = super().tool(tool, args, **kwargs)
                    return native if args.get("script") == "CBPCPluginScript" else result
            with self.subTest(native=native), tempfile.TemporaryDirectory() as directory:
                session = WrongCompletion(directory)
                with self.assertRaisesRegex(ValueError, "native completion"):
                    case.run(session, "0xFF001234", "female", sleep=lambda _: None)
                self.assertEqual(len(self.controls(session)), 1)
                self.assertFalse(session.keys)
                self.assertTrue(session.state["cbpcProbe"]["uncertain"])

    def test_unknown_stop_or_restart_does_not_replay_and_still_cleans_owned_anchors(self):
        for failure, calls in ((("StopPhysics", 1), 12), (("StartPhysics", 12), 23)):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                session = Session(directory, uncertain=failure)
                with self.assertRaises(TimeoutError):
                    case.run(session, "0xFF001234", "female", sleep=lambda _: None)
                self.assertEqual(len(self.controls(session)), calls)
                self.assertTrue(session.state["cbpcProbe"]["uncertain"])
                state = json.loads((Path(directory)/"cbpc-probe/state.json").read_bytes())
                self.assertEqual(state["uncertainProviderCall"]["request"]["function"], failure[0])
                cleanup = json.loads((Path(directory)/"cbpc-probe/cleanup.json").read_bytes())
                self.assertFalse(cleanup["errors"])
                self.assertEqual(cleanup["providerCleanupCalls"], [])
                self.assertTrue(all(value is None for keys in session.keys.values() for value in keys.values()))

    def test_human_base_and_current_race_rejected_before_any_mutation(self):
        for key in ("race", "baseRace"):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                session = Session(directory)
                session.sample["refs"][0]["actor"][key] = "0x00013749"
                with self.assertRaisesRegex(ValueError, "born-beast"):
                    case.run(session, "0xFF001234", "female", sleep=lambda _: None)
                self.assertFalse(self.controls(session))
                self.assertFalse(session.mutation_journals)

    def test_cleanup_does_not_skip_other_anchors_or_hide_primary_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session(directory, uncertain=("StopPhysics", 1), fail_head_restore=True)
            with self.assertRaisesRegex(ValueError, "primary: synthetic unknown provider completion"):
                case.run(session, "0xFF001234", "female", sleep=lambda _: None)
            cleanup = json.loads((Path(directory)/"cbpc-probe/cleanup.json").read_bytes())
            self.assertIn("error", cleanup["anchors"]["NPC Head [Head]"])
            for name in ("Tails", "NPC L PreBreast P1", "NPC R PreBreast P1"):
                self.assertTrue(cleanup["anchors"][name]["ownPositionComponentAbsent"])
            self.assertEqual(len(self.controls(session)), 12)

    def test_only_kinematic_anchors_are_mutated_and_p1_uses_declared_small_offset(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session(directory)
            case.run(session, "0xFF001234", "female", sleep=lambda _: None)
            names = set(case.pulse.families("female"))
            for _, args in session.calls:
                if args.get("script") == "NiOverride":
                    self.assertIn(args["args"][3], names)
                    self.assertEqual(args["args"][1:3], [False, True])
                    if args["function"] == "AddNodeTransformPosition" and "PreBreast" in args["args"][3]:
                        self.assertLessEqual(abs(args["args"][-1][0]), .1)
                elif args.get("script") == "NetImmerse":
                    self.assertIn(args["args"][1], names)
            self.assertFalse(any(args.get("function") in ("ReloadConfig", "TogglePhysics", "Disable") for _, args in session.calls))

    def test_disposal_only_disables_guarded_fixture_and_does_not_restore_provider_state(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/"cbpc-probe").mkdir()
            session = Session(directory)
            admitted, provider = copy.deepcopy(session.sample), dict(session.on)
            result = case.dispose_fixture(session, "0xFF001234", "female", admitted)
            self.assertTrue(result["verifiedDisabledAndCrosshairReleased"])
            self.assertTrue((Path(directory)/"cbpc-probe/fixture-disposal.json").is_file())
            self.assertEqual(session.on, provider)
            self.assertFalse(self.controls(session))
            disables = [args for _, args in session.calls if args.get("function") == "Disable"]
            self.assertEqual(len(disables), 1)
            self.assertEqual(disables[0]["args"], [False])


if __name__ == "__main__":
    unittest.main()
