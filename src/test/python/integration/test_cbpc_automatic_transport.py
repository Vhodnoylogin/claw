"""Actual callback boundary tests with a synthetic Session, never a game.

Set CLAW_AUTOTEST_SOURCE to the explicitly selected executor package root.
This prepared integration category intentionally has no ambient/tool fallback.
"""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.environ["CLAW_AUTOTEST_SOURCE"])
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "physics"))
from test_cbpc_automatic import automatic_fixture, nominal, f32, PINS
import cbpc_automatic_owned_case as case
import cbpc_automatic_diagnostics as diagnostics
import cbpc_human_lifecycle as lifecycle


class Clock:
    def __init__(self): self.now = 10.
    def __call__(self): return self.now
    def sleep(self, seconds): self.now += seconds


class Session:
    def __init__(self, directory, sex="female", *, human=False, uncertain=None, binding_failure=False):
        self.dir, self.sex = Path(directory), sex
        self.doc, self.subject = automatic_fixture(sex)
        self.sample = self.doc["baseline"]
        self.reference = self.subject["reference"]
        self.clock, self.calls, self.phase_name = Clock(), [], ""
        self.phase_deadline = float("inf")
        self.state = {"configuration": {"game_edition": "se"}, "checks": []}
        self.position = self.sample["refs"][0]["position"][:]
        self.enabled, self.human = not human, human
        self.uncertain, self.binding_failure = uncertain, binding_failure
        self.on = {n: True for n in nominal.scene.drivers(sex)}
        self.generation, self.handle, self.token, self.sample_id = 2, 8, 10, 10
        self.tree = {n: p[0] for n, p in nominal.hierarchy.parent_paths(sex).items()}
        self.tree.update({f"CME TailBone{i:02}": f"TailBone{i:02}" for i in range(1, 5)})
        self.tree.update({"NPC Head [Head]": "NPC Spine2 [Spn2]", "Tails": "NPC Pelvis [Pelv]",
                          "NPC L PreBreast P1": "NPC Spine2 [Spn2]", "NPC R PreBreast P1": "NPC Spine2 [Spn2]"})
    def save(self): pass
    def phase(self, name, seconds):
        self.phase_name = name
        self.phase_deadline = self.clock() + seconds
    def observe(self, query):
        raw = copy.deepcopy(self.sample)
        self.clock.now += .01
        self.sample_id += 1
        raw.update(sampleId=self.sample_id, producerMonotonicNs=round(self.clock.now * 1e9), loadGeneration=self.generation)
        ref = raw["refs"][0]
        ref["identity"].update(runtimeHandle=self.handle, loadGeneration=self.generation)
        ref["rootIdentity"]["sampledRootToken"] = self.token if self.enabled else None
        if self.uncertain == "root-loss" and "active-position-0-after" in self.phase_name:
            ref["rootIdentity"]["sampledRootToken"] += 1
        ref.update(disabled=not self.enabled, loaded3D=self.enabled, position=self.position[:])
        ref["actor"]["race"] = self.subject["originalRace"] if self.human else self.subject["currentRace"]
        ref["actor"]["baseRace"] = ref["actor"]["race"]
        scale = 1. if self.human else f32(self.subject["expectedUniformScale"])
        if self.uncertain == "scale-mismatch": scale = f32(1.05)
        ref["scale"] = ref["sceneTransform"]["scale"] = scale
        ref["sceneTransform"]["translation"] = self.position[:]
        point = re.search(r"(?:active|stopped|restarted)-position-(\d+)-", self.phase_name)
        local = {name: [0., 0., 0.] for name in nominal.scene.node_names(self.sex)}
        if point:
            for name in self.on:
                local[name][0] = f32(.2 * math.sin(int(point[1]) * .71)) if self.on[name] else 0.
        world = {}
        def locate(name):
            if name not in world:
                parent = self.tree.get(name)
                origin = locate(parent) if parent else self.position
                world[name] = [f32(a + scale * b) for a, b in zip(origin, local[name])]
            return world[name]
        rows = {n["name"]: n for n in raw["nodes"]}
        names = [n["name"] for n in query.get("nodes", [])]
        raw["nodes"] = []
        for name in names:
            row = copy.deepcopy(rows.get(name, next(iter(rows.values()))))
            row.update(name=name, identity=copy.deepcopy(ref["identity"]), rootIdentity=copy.deepcopy(ref["rootIdentity"]))
            if name in ("missing-a", "missing-b"):
                row.update(status="unavailable", reason="Node not found")
            elif name in local:
                row["local"]["translation"] = local[name]
                row["world"]["translation"] = locate(name)
                row["world"]["scale"] = scale
            raw["nodes"].append(row)
        return raw
    def tool(self, tool, args, **kwargs):
        self.calls.append((tool, copy.deepcopy(args)))
        if tool == "inspect": return self.observe(args)
        if tool == "platform":
            action = args["request"]["action"]
            if self.uncertain == action:
                self.generation += 1
                raise TimeoutError("synthetic unknown load completion")
            if action == "save_game": return {"save": {"completed": True, "ownedByAttempt": True}}
            if self.uncertain == "slow-load":
                self.clock.now += 13.
                if self.clock() > self.phase_deadline:
                    raise TimeoutError("synthetic guardian expired while valid owned helper continued")
            self.generation += 1; self.handle += 1; self.token += 1
            return {"lifecycle": {"worldReady": True, "pidChanged": False, "generationChanged": True, "oldReferenceTagsInvalidated": True}}
        if args.get("action") == "describe":
            script = args["script"]
            scope, methods = (lifecycle.CONTRACTS[script] if script in lifecycle.CONTRACTS else case.CONTRACTS[script])
            merged = dict(methods)
            if script in case.CONTRACTS: merged.update(case.CONTRACTS[script][1])
            return {"name": script, scope: [{"name": n, "native": True, "params": [{"name": "p" + str(i), "type": t} for i, t in enumerate(p)], "returnType": r}
                            for n, (p, r) in merged.items()]}
        script, function, values = args["script"], args["function"], args.get("args", [])
        if function == self.uncertain: raise TimeoutError("synthetic unknown native completion")
        value, returned = None, "none"
        if script == "CBPCPluginScript": self.on[values[1]] = function == "StartPhysics"
        elif function == "SetPosition": self.position = values[:]
        elif function == "Enable": self.enabled = True
        elif function == "Disable": self.enabled = False
        elif function == "SetRace":
            assert isinstance(values[0], dict) and set(values[0]) == {"form"}, "Typed race form is mandatory"
            if self.uncertain != "race-no-effect":
                self.human = values[0]["form"] == self.subject["originalRace"]
                self.token += 1
        elif function == "GetFormFromFile": value, returned = {"formId": self.reference}, "form"
        elif function == "GetDisplayName": value, returned = self.subject["providerActorName"], "string"
        elif function == "GetAppearanceStatus": value, returned = "human colours captured", "string"
        elif function == "GetStatus": value, returned = (5 if self.human else 2), "int"
        elif function == "GetLastError": value, returned = "", "string"
        elif function == "GetCoatPattern": value, returned = "installed-base", "string"
        elif function == "Refresh": value, returned = True, "bool"
        self.clock.now += .01
        return {"called": True, "returnedType": returned, "returned": value}


def stock_and_pins(session):
    expected = {"query": {"kind": "world_observer", "refs": [session.reference], "actors": True,
                          "nodes": [{"ref": session.reference, "name": n, "firstPerson": False}
                                    for n in (*nominal.scene.node_names(session.sex), "missing-a", "missing-b")]},
                "protectedNames": list(nominal.scene.node_names(session.sex)), "writeTargets": ["missing-a", "missing-b"],
                "requiredProbeNames": list(nominal.scene.node_names(session.sex)), "missingAnyMeansEarlyReturn": ["missing-a"],
                "sourceParentPaths": {}}
    path = session.dir / "stock-graph-expected.json"
    path.write_text(json.dumps(expected), encoding="utf-8")
    modules = {"cbpc_probe.py": case.controls, "cbpc_pulse.py": nominal.hierarchy, "cbpc_nominal.py": nominal,
               "fsmp_probe.py": nominal.scene, "fsmp_pulse.py": case.fsmp_pulse}
    pins = {"helperSources": {n: {"sha256": hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()} for n, m in modules.items()},
            "stockConfigurationAndRoleProof": [{"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}],
            "xp32Sha256": nominal.hierarchy.XP32_SHA256}
    return expected, pins


class Observer:
    def __init__(self, session): self.session, self.completed = session, []
    def phase_settled(self, phase):
        if phase == "active":
            assert not [a for t, a in self.session.calls if t == "papyrus" and a.get("action") == "call" and a.get("script") == "CBPCPluginScript"]
    def world_follow(self, raw, baseline, wanted):
        diagnostics.world_follow(raw, baseline, wanted, self.session.reference, self.session.sex)
    def phase_complete(self, phase): self.completed.append(phase)


class AutomaticTransportTests(unittest.TestCase):
    def collect(self, session):
        graph, pins = stock_and_pins(session)
        query = nominal.controls.prepare(session.reference, session.sex)["query"]
        evidence = copy.deepcopy(session.doc["humanLifecycle"])
        evidence["phaseWitnesses"]["post-load"] = session.observe(query)
        admitted = session.observe(query)
        return case.run(session, session.reference, session.sex, admitted=admitted,
            subject_pins=pins, stock_expected=graph, human_origin=session.subject, declared_protocol=nominal.automatic_protocol(),
            human_lifecycle=evidence,
            known_observer=Observer(session), sleep=session.clock.sleep, clock=session.clock, monotonic=session.clock)
    def test_actual_collector_both_sexes_has_no_initial_start_and_75_points(self):
        for sex in ("female", "male"):
            with tempfile.TemporaryDirectory() as folder:
                s = Session(folder, sex)
                self.collect(s)
                calls = [a for t, a in s.calls if t == "papyrus" and a.get("action") == "call"]
                provider = [a["function"] for a in calls if a["script"] == "CBPCPluginScript"]
                n = len(s.on)
                self.assertEqual(provider, ["StopPhysics"] * n + ["StartPhysics"] * n)
                self.assertEqual(sum(a["function"] == "SetPosition" for a in calls), 76)
                self.assertEqual(sum(a["function"] == "Disable" for a in calls), 1)
    def test_unknown_first_stop_blocks_all_further_custom_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            s = Session(folder, uncertain="StopPhysics")
            with self.assertRaises(TimeoutError): self.collect(s)
            calls = [a for t, a in s.calls if t == "papyrus" and a.get("action") == "call"]
            self.assertEqual(sum(a["function"] == "SetPosition" for a in calls), 25)
            self.assertFalse(any(a["function"] in ("Disable", "StartPhysics") for a in calls))
    def test_known_numeric_scale_failure_disposes_without_provider_calls(self):
        with tempfile.TemporaryDirectory() as folder:
            s = Session(folder, uncertain="scale-mismatch")
            with self.assertRaisesRegex(ValueError, "scale differs"): self.collect(s)
            calls = [a for t, a in s.calls if t == "papyrus" and a.get("action") == "call"]
            self.assertEqual(sum(a["function"] == "Disable" for a in calls), 1)
            self.assertFalse(any(a["script"] == "CBPCPluginScript" for a in calls))
    def test_unknown_root_change_blocks_cleanup_and_provider_controls(self):
        with tempfile.TemporaryDirectory() as folder:
            s = Session(folder, uncertain="root-loss")
            with self.assertRaisesRegex(ValueError, "continuity lost"): self.collect(s)
            calls = [a for t, a in s.calls if t == "papyrus" and a.get("action") == "call"]
            self.assertEqual(sum(a["function"] == "SetPosition" for a in calls), 1)
            self.assertFalse(any(a["function"] == "Disable" or a["script"] == "CBPCPluginScript" for a in calls))
    def test_actual_lifecycle_is_typed_persistent_and_reacquires_load_epoch(self):
        for sex in ("female", "male"):
            with tempfile.TemporaryDirectory() as folder:
                s = Session(folder, sex, human=True)
                def bound(subject, output):
                    self.assertFalse(s.human)
                    self.assertEqual(sum(a.get("function") == "SetRace" for t, a in s.calls), 1)
                    return {"allDeclaredNodes": True, "synthetic": True}
                subject, admitted, state = lifecycle.run(s, s.reference, sex, position=s.position, end=s.clock()+100,
                    first_binding_witness=bound, monotonic=s.clock, sleep=s.clock.sleep)
                self.assertTrue(state["completed"])
                self.assertGreater(admitted["loadGeneration"], 1)
                self.assertEqual(subject, s.subject)
                self.assertEqual([r["label"] for r in state["writes"]], ["place-disabled", "enable-human", "restrain-human", "unequip-owned-outfit", "enable-human-ai", "first-wolf", "refresh",
                    "human-return", "second-wolf", "node-update", "owned-save", "owned-load", "head-tracking-off"])
    def test_known_binding_failure_disposes_but_unknown_race_or_load_never_does(self):
        for failure in ("binding", "SetRace", "load_game"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as folder:
                s = Session(folder, human=True, uncertain=None if failure == "binding" else failure)
                def bound(subject, output):
                    if failure == "binding": raise ValueError("synthetic missing automatic binding")
                    return {"allDeclaredNodes": True}
                with self.assertRaises((ValueError, TimeoutError)):
                    lifecycle.run(s, s.reference, s.sex, position=s.position, end=s.clock()+100,
                        first_binding_witness=bound, monotonic=s.clock, sleep=s.clock.sleep)
                calls = [a for t, a in s.calls if t == "papyrus" and a.get("action") == "call"]
                self.assertEqual(sum(a["function"] == "Disable" for a in calls), int(failure == "binding"))
                self.assertFalse(any(a["script"] == "CBPCPluginScript" for a in calls))
    def test_void_ack_without_race_change_never_advances_or_replays(self):
        with tempfile.TemporaryDirectory() as folder:
            s = Session(folder, human=True, uncertain="race-no-effect")
            with self.assertRaisesRegex(ValueError, "transition not resolved"):
                lifecycle.run(s, s.reference, s.sex, position=s.position, end=s.clock()+12,
                    first_binding_witness=lambda *args: self.fail("No binding claim before actual race change"),
                    monotonic=s.clock, sleep=s.clock.sleep)
            state = json.loads((s.dir/"cbpc-human-lifecycle/state.json").read_text())
            self.assertEqual(state["expectedRace"], s.subject["originalRace"])
            calls = [a for t, a in s.calls if t == "papyrus" and a.get("action") == "call"]
            self.assertEqual(sum(a["function"] == "SetRace" for a in calls), 1)
            self.assertFalse(any(a["function"] in ("Disable", "Refresh") or a["script"] == "CBPCPluginScript" for a in calls))
    def test_owned_load_longer_than_12_seconds_has_matching_guardian_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            s = Session(folder, human=True, uncertain="slow-load")
            _, _, state = lifecycle.run(s, s.reference, s.sex, position=s.position, end=s.clock()+100,
                first_binding_witness=lambda *args: {"allDeclaredNodes": True},
                monotonic=s.clock, sleep=s.clock.sleep)
            self.assertTrue(state["completed"])
            self.assertFalse(state["unknown"])


if __name__ == "__main__": unittest.main()
