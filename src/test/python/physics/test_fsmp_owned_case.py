"""Case orchestration negatives; synthetic Session, no game or transport."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_fsmp_probe import fixture, compose, transform

INTEGRATION = Path(__file__).resolve().parents[1] / "integration"
sys.path.insert(0, str(INTEGRATION))
try:
    import fsmp_owned_case as case
finally:
    sys.path.remove(str(INTEGRATION))


class Session:
    def __init__(self, directory, previous=None, timeout=False, frozen_anchors=False, world_response=False,
                 fail_head_restore=False, sex="male"):
        self.dir = Path(directory)
        self.state = {"checks": [], "id": "synthetic-owned-run"}
        self.sex = sex
        self.sample = fixture(sex, effect=False)["baseline"]
        self.calls = []
        self.previous = [True]*len(case.probe.drivers(sex)) if previous is None else previous
        self.timeout = timeout
        self.frozen_anchors = frozen_anchors
        self.world_response = world_response
        self.fail_head_restore = fail_head_restore
        self.anchor_keys = {}
        self.current_phase = None
        self.inspect_keys = []
        self.original_nodes = {n["name"]: copy.deepcopy(n) for n in self.sample["nodes"]}

    def save(self):
        pass

    def phase(self, *args):
        self.current_phase = args[0]

    def tool(self, tool, args, **kwargs):
        result = self._tool(tool, args, **kwargs)
        if tool == "papyrus":
            result.setdefault("called", True)
            result.setdefault("returnedType", "bool[]" if args.get("function") == "TogglePhysics" else
                              "bool" if type(result.get("returned")) is bool else "none")
        return result

    def _tool(self, tool, args, **kwargs):
        self.calls.append((tool, copy.deepcopy(args)))
        if tool == "inspect":
            self.inspect_keys.append((self.current_phase, copy.deepcopy(self.anchor_keys)))
            self.sample["sampleId"] += 1
            self.sample["producerMonotonicNs"] += 100_000_000
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
                return {"returned": (self.anchor_keys[name][key] or [0.,0.,0.])[:]}
            elif function == "RemoveNodeTransformPosition":
                values = self.anchor_keys.setdefault(name, {})
                existed = values.get(key) is not None
                if key in values:
                    values[key] = None  # Actual SKEE retains the empty key container.
                return {"returned": existed}
            elif function == "UpdateNodeTransform" and not self.frozen_anchors:
                offset = next((v for v in self.anchor_keys.get(name, {}).values() if v is not None), [0.,0.,0.])
                anchor_world = self.original_nodes[name]["world"]
                moved = compose(anchor_world, transform(offset))
                for row in self.sample["nodes"]:
                    if row["name"] == name:
                        row["world"] = moved
                        row["local"] = compose(self.original_nodes[name]["local"], transform(offset))
                    elif case.probe.anchors(self.sex).get(row["name"]) == name or (
                            name == "Tails" and row["name"] in case.probe.INTERMEDIATES):
                        rest = case.probe.relative(self.original_nodes[row["name"]]["world"], anchor_world)
                        if self.world_response and row["name"] in case.probe.drivers(self.sex) and all(self.previous):
                            rest["translation"][1] += .03*offset[0]
                        row["world"] = compose(moved, rest)
            return {"returned": None}
        if args.get("script") == "NetImmerse":
            name, value = args["args"][1:3]
            if self.fail_head_restore and name == "NPC Head [Head]" and args["function"] == "SetNodeLocalRotationMatrix":
                return {"returned": False}
            row = next(row for row in self.sample["nodes"] if row["name"] == name)
            channel = {"SetNodeLocalPosition": "translation", "SetNodeLocalRotationMatrix": "rotationRowMajor", "SetNodeScale": "scale"}[args["function"]]
            row["local"][channel] = copy.deepcopy(value)
            return {"returned": None if channel == "scale" else True}
        if args.get("function") == "Disable":
            self.sample["refs"][0]["disabled"] = True
            self.sample["refs"][0]["loaded3D"] = False
            return {"called": True, "returned": None, "returnedType": "none"}
        if args.get("function") == "GetCurrentCrosshairRef":
            return {"called": True, "returned": None if self.sample["refs"][0]["disabled"] else {"formId": "0xFF001234"}}
        if args.get("function") == "TogglePhysics":
            if self.timeout:
                raise TimeoutError("synthetic unknown native return")
            names, on = args["args"][1:]
            indices = [case.probe.drivers(self.sex).index(name) for name in names]
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
            result = case.run(session, "0xFF001234", "male", stimulus="xml-anchors", sleep=lambda _: None)
            self.assertEqual(result["status"], "unconfirmed")
            self.assertTrue(result["anchorExcitationQualified"])
            self.assertEqual(session.previous, [True]*9)
            self.assertTrue(all(v is None for values in session.anchor_keys.values() for v in values.values()))
            cleanup = json.loads((Path(directory)/"fsmp-probe/cleanup.json").read_bytes())
            self.assertTrue(all(row["hasKeyContainerAfterRemoval"] for row in cleanup["anchors"].values()))
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
                case.run(session, "0xFF001234", "male", stimulus="xml-anchors", sleep=lambda _: None)
            state = json.loads((Path(directory)/"fsmp-probe/state.json").read_bytes())
            self.assertEqual(state["windows"], {})
            self.assertTrue(all(v is None for values in session.anchor_keys.values() for v in values.values()))

    def test_direct_anchor_world_response_is_discriminated_without_local_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session(directory, world_response=True)
            result = case.run(session, "0xFF001234", "male", stimulus="xml-anchors", sleep=lambda _: None)
            self.assertEqual(result["status"], "sampled-selective-contrast-observed")
            self.assertTrue(result["localAnimationQuiet"])
            self.assertTrue(result["controlParentsQuiet"])
            self.assertFalse(result["solverQualified"])

    def test_one_anchor_cleanup_error_does_not_skip_the_other_or_hide_primary(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session(directory, frozen_anchors=True, fail_head_restore=True)
            with self.assertRaisesRegex(ValueError, "primary: Mass-zero anchor world displacement"):
                case.run(session, "0xFF001234", "male", stimulus="xml-anchors", sleep=lambda _: None)
            cleanup = json.loads((Path(directory)/"fsmp-probe/cleanup.json").read_bytes())
            self.assertIn("error", cleanup["anchors"]["NPC Head [Head]"])
            self.assertTrue(cleanup["anchors"]["Tails"]["ownPositionComponentAbsent"])
            self.assertTrue(all(v is None for values in session.anchor_keys.values() for v in values.values()))

    def test_female_trial_qualifies_eleven_and_only_writes_four_kinematic_anchors(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session(directory, world_response=True, sex="female")
            result = case.run(session, "0xFF001234", "female", stimulus="xml-anchors", sleep=lambda _: None)
            self.assertEqual(result["status"], "sampled-selective-contrast-observed")
            self.assertEqual(len(result["selectiveChannels"]), 11)
            self.assertEqual(session.previous, [True]*11)
            expected = {"NPC Head [Head]", "Tails", "NPC L PreBreast P1", "NPC R PreBreast P1"}
            written = set()
            for tool, args in session.calls:
                if args.get("script") == "NiOverride":
                    self.assertEqual(args["args"][1:3], [False, True])
                    written.add(args["args"][3])
                elif args.get("script") == "NetImmerse":
                    self.assertFalse(args["args"][-1])
                    written.add(args["args"][1])
            self.assertEqual(written, expected)
            cleanup = json.loads((Path(directory)/"fsmp-probe/cleanup.json").read_bytes())
            self.assertEqual(set(cleanup["anchors"]), expected)
            self.assertFalse(cleanup["errors"])
            self.assertTrue(all(row["ownPositionComponentAbsent"] for row in cleanup["anchors"].values()))

    def test_female_missing_p1_binding_never_excites_and_restores_only_known_ten(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session(directory, previous=[True]*10 + [False], sex="female")
            with self.assertRaisesRegex(ValueError, "dynamic-body gate"):
                case.run(session, "0xFF001234", "female", stimulus="xml-anchors", sleep=lambda _: None)
            self.assertFalse(any(args.get("script") == "NiOverride" for _, args in session.calls))
            toggles = [args for _, args in session.calls if args.get("function") == "TogglePhysics"]
            self.assertEqual(toggles[1]["args"][1], list(case.probe.FEMALE[:10]))
            self.assertEqual(session.previous, [True]*10 + [False])

    def test_fixture_disposal_requires_disabled_readback_and_null_crosshair(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/"fsmp-probe").mkdir()
            session = Session(directory, sex="female")
            admitted = copy.deepcopy(session.sample)
            result = case.dispose_fixture(session, "0xFF001234", "female", admitted)
            self.assertTrue(result["verifiedDisabledAndCrosshairReleased"])
            self.assertEqual(len([args for _, args in session.calls if args.get("function") == "Disable"]), 1)
            self.assertTrue(result["observations"][-1]["world"]["refs"][0]["disabled"])
            self.assertIsNone(result["observations"][-1]["crosshair"]["returned"])

    def test_fixture_disposal_refuses_changed_actor_before_any_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/"fsmp-probe").mkdir()
            session = Session(directory, sex="female")
            admitted = copy.deepcopy(session.sample)
            session.sample["refs"][0]["actor"]["weight"]["rawNPCWeight"] = 51.
            with self.assertRaisesRegex(ValueError, "changed before disposal"):
                case.dispose_fixture(session, "0xFF001234", "female", admitted)
            self.assertFalse(any(args.get("function") == "Disable" for _, args in session.calls))

    def test_fixture_disposal_does_not_treat_missing_crosshair_value_as_null(self):
        class MissingValue(Session):
            def tool(self, tool, args, **kwargs):
                result = super().tool(tool, args, **kwargs)
                return {"called": True} if args.get("function") == "GetCurrentCrosshairRef" else result
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/"fsmp-probe").mkdir()
            session = MissingValue(directory, sex="female")
            with self.assertRaisesRegex(ValueError, "Crosshair readback value unavailable"):
                case.dispose_fixture(session, "0xFF001234", "female", copy.deepcopy(session.sample))
            self.assertEqual(len([args for _, args in session.calls if args.get("function") == "Disable"]), 1)

    def test_fixture_disposal_rejects_error_null_and_missing_null_type(self):
        for invalid in ({"called": True, "returnedType": "none", "returned": None, "error": "unavailable"},
                        {"called": True, "returned": None}):
            class InvalidNull(Session):
                def tool(self, tool, args, **kwargs):
                    result = super().tool(tool, args, **kwargs)
                    return invalid if args.get("function") == "GetCurrentCrosshairRef" else result
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as directory:
                (Path(directory)/"fsmp-probe").mkdir()
                session = InvalidNull(directory, sex="female")
                with self.assertRaisesRegex(ValueError, "Crosshair"):
                    case.dispose_fixture(session, "0xFF001234", "female", copy.deepcopy(session.sample))
                self.assertEqual(len([args for _, args in session.calls if args.get("function") == "Disable"]), 1)

    def test_fixture_disposal_waits_for_non_null_reference_to_release(self):
        class DelayedNull(Session):
            crosshairs = 0
            def tool(self, tool, args, **kwargs):
                result = super().tool(tool, args, **kwargs)
                if args.get("function") == "GetCurrentCrosshairRef":
                    self.crosshairs += 1
                    if self.crosshairs == 1:
                        return {"called": True, "returnedType": "objectreference", "returned": {"formId": "0xFF001234"}}
                return result
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/"fsmp-probe").mkdir()
            session = DelayedNull(directory, sex="female")
            result = case.dispose_fixture(session, "0xFF001234", "female", copy.deepcopy(session.sample), sleep=lambda _: None)
            self.assertTrue(result["verifiedDisabledAndCrosshairReleased"])
            self.assertEqual(len(result["observations"]), 2)
            self.assertEqual(len([args for _, args in session.calls if args.get("function") == "Disable"]), 1)

    def test_pulse_uncertain_wait_does_not_reach_motion_or_replay_wait(self):
        class UnknownWait(Session):
            waits = 0
            def tool(self, tool, args, **kwargs):
                result = super().tool(tool, args, **kwargs)
                if args.get("script") == "Utility" and args.get("function") == "Wait":
                    self.waits += 1
                    if self.waits == 1:
                        return {"called": False, "returnedType": "none", "returned": None}
                return result
        with tempfile.TemporaryDirectory() as directory:
            session = UnknownWait(directory)
            with self.assertRaisesRegex(ValueError, "settle completion uncertain"):
                case.run(session, "0xFF001234", "male", stimulus="xml-anchor-pulse", sleep=lambda _: None)
            state = json.loads((Path(directory)/"fsmp-probe/state.json").read_bytes())
            self.assertEqual(state["pulses"], {})
            self.assertTrue(all(v is None for keys in session.anchor_keys.values() for v in keys.values()))
            prime = [args for _, args in session.calls if args.get("function") == "Wait" and args.get("args") == [2.]]
            self.assertEqual(len(prime), 1)

    def test_fixture_disposal_requires_bounded_deadline_and_fresh_precondition(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/"fsmp-probe").mkdir()
            session = Session(directory, sex="female")
            admitted = copy.deepcopy(session.sample)
            for invalid in (float("inf"), float("nan"), 0, 16, True):
                with self.assertRaisesRegex(ValueError, "finite 1..15"):
                    case.dispose_fixture(session, "0xFF001234", "female", admitted, maximum_seconds=invalid)
            self.assertEqual(session.calls, [])
            with patch.object(session, "tool", return_value=admitted):
                with self.assertRaisesRegex(ValueError, "precondition was replayed"):
                    case.dispose_fixture(session, "0xFF001234", "female", admitted)

    def test_fixture_disposal_does_not_accept_uncertain_disable_despite_effect(self):
        class UncertainDisable(Session):
            def tool(self, tool, args, **kwargs):
                result = super().tool(tool, args, **kwargs)
                if args.get("function") == "Disable":
                    result["called"] = False
                return result
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/"fsmp-probe").mkdir()
            session = UncertainDisable(directory, sex="female")
            with self.assertRaisesRegex(ValueError, "completion uncertain; do not replay"):
                case.dispose_fixture(session, "0xFF001234", "female", copy.deepcopy(session.sample))
            self.assertTrue(session.sample["refs"][0]["disabled"])
            self.assertEqual(len([args for _, args in session.calls if args.get("function") == "Disable"]), 1)
            self.assertFalse(any(args.get("function") == "GetCurrentCrosshairRef" for _, args in session.calls))

    def test_pulse_samples_only_after_each_family_has_returned_to_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session(directory, sex="female")
            result = case.run(session, "0xFF001234", "female", stimulus="xml-anchor-pulse", sleep=lambda _: None)
            self.assertEqual(result["status"], "unconfirmed")
            self.assertEqual(len(result["missingDrivers"]), 11)
            samples = [keys for phase, keys in session.inspect_keys if "-pulse-sample-" in phase]
            self.assertEqual(len(samples), 3*4*25)
            self.assertTrue(all(value == [0., 0., 0.] for keys in samples for values in keys.values() for value in values.values()))
            self.assertTrue(all(v is None for values in session.anchor_keys.values() for v in values.values()))
            state = json.loads((Path(directory)/"fsmp-probe/state.json").read_bytes())
            self.assertEqual(state["windows"], {})
            self.assertEqual(len(state["pulses"]["active"]), 4)

    def test_late_read_cannot_compress_the_following_sample_gap(self):
        def dispatches(schedule):
            now, last, result = 0., None, []
            for index in range(25):
                now = max(now, schedule(index, last))
                result.append(now)
                now += .008  # Read completion precedes evidence persistence.
                last = now
                # A slow journal write leaves little time to the next slot.
                now += .166 if index == 1 else .006
            return result
        old = dispatches(lambda index, last: index*.1)
        fixed = dispatches(lambda index, last: case.next_sample_time(0., index, .1, .04, last))
        self.assertLess(min(b-a for a, b in zip(old, old[1:])), .04)
        self.assertGreaterEqual(min(b-a for a, b in zip(fixed, fixed[1:])), .04)
        self.assertLessEqual(max(b-a for a, b in zip(fixed, fixed[1:])), .2)
        self.assertAlmostEqual(fixed[-1], 2.4)

    def test_pulse_uncertain_body_receipt_is_not_replayed_or_excited(self):
        class UncertainBody(Session):
            def tool(self, tool, args, **kwargs):
                result = super().tool(tool, args, **kwargs)
                if args.get("function") == "TogglePhysics":
                    result["called"] = False
                return result
        with tempfile.TemporaryDirectory() as directory:
            session = UncertainBody(directory, sex="female")
            with self.assertRaisesRegex(ValueError, "body-state completion uncertain"):
                case.run(session, "0xFF001234", "female", stimulus="xml-anchor-pulse", sleep=lambda _: None)
            self.assertEqual(len([args for _, args in session.calls if args.get("function") == "TogglePhysics"]), 1)
            self.assertFalse(any(args.get("script") == "NiOverride" for _, args in session.calls))

    def test_pulse_uncertain_anchor_write_never_reaches_sampling(self):
        class UncertainWrite(Session):
            def tool(self, tool, args, **kwargs):
                result = super().tool(tool, args, **kwargs)
                if args.get("function") == "AddNodeTransformPosition":
                    result["called"] = False
                return result
        with tempfile.TemporaryDirectory() as directory:
            session = UncertainWrite(directory, sex="female")
            with self.assertRaisesRegex(ValueError, "pulse write completion uncertain"):
                case.run(session, "0xFF001234", "female", stimulus="xml-anchor-pulse", sleep=lambda _: None)
            self.assertFalse(any("-pulse-sample-" in phase for phase, _ in session.inspect_keys))
            self.assertTrue(all(v is None for values in session.anchor_keys.values() for v in values.values()))


if __name__ == "__main__":
    unittest.main()
