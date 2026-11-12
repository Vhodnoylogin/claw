"""Transport fault/packet tests, not simulated CBPC or new game evidence."""
import copy
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[4]
REFERENCE = Path(os.environ.get("CLAW_NOMINAL_REFERENCE_ROOT", str(HERE)))
sys.path[:0] = [str(HERE/"src/test/python/integration"), str(REFERENCE/"src/test/python/integration")]
import cbpc_nominal_owned_case as owned

FIXTURES = HERE/"src/test/resources/physics/cbpc-nominal"
RECORDED = json.loads((FIXTURES/"recorded-observer-snapshot.json").read_bytes())
CONTRACTS = json.loads((FIXTURES/"recorded-native-contracts.json").read_bytes())
STOCK = json.loads((FIXTURES/"stock-graph-expected.json").read_bytes())
REF = RECORDED["refs"][0]["identity"]["form"]
PINS = json.loads((FIXTURES/"declared-subject-pins.json").read_bytes())
for row in PINS["stockConfigurationAndRoleProof"]:
    if Path(row["path"]).name == "stock-graph-expected.json":
        row["path"] = str(FIXTURES/"stock-graph-expected.json")
        # A relocated LF JSON copy is test input, not the original raw artifact.
        row["sha256"] = hashlib.sha256(Path(row["path"]).read_bytes()).hexdigest()
DONE = {"called": True, "returnedType": "none", "returned": None}


class Clock:
    def __init__(self):
        self.now = 0.
        self.cancelled = False
        self.cancel_at = None

    def read(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds
        if self.cancel_at is not None and self.now >= self.cancel_at:
            self.cancelled = True


class Session:
    """Recorded observer shape + deterministic transport only; no physics model."""
    def __init__(self, directory, clock, fault=None):
        self.dir, self.clock, self.fault = Path(directory), clock, fault
        self.state = {"id": "offline-packet-test", "configuration": {"game_edition": "se"}, "checks": []}
        self.calls = []
        self.position = RECORDED["refs"][0]["position"][:]
        self.disabled = False
        self.sample = RECORDED["sampleId"]

    def save(self):
        pass

    def phase(self, *args):
        pass

    def tool(self, tool, args, **kwargs):
        self.calls.append((tool, copy.deepcopy(args), kwargs))
        self.clock.now += .005
        if self.fault is not None:
            value = self.fault(self, tool, args)
            if value is not None:
                return value
        if tool == "inspect":
            raw = copy.deepcopy(RECORDED)
            self.sample += 1
            raw.update(sampleId=self.sample, producerMonotonicNs=RECORDED["producerMonotonicNs"]+int(self.clock.now*1e9))
            original = raw["refs"][0]["position"]
            delta = [a-b for a,b in zip(self.position, original)]
            raw["refs"][0]["position"] = self.position[:]
            for tx in [raw["refs"][0]["sceneTransform"], *(n["world"] for n in raw["nodes"])]:
                tx["translation"] = [a+b for a,b in zip(tx["translation"], delta)]
            raw["refs"][0]["disabled"] = self.disabled
            if self.disabled:
                raw["refs"][0]["loaded3D"] = False
            if "nodes" not in args:
                raw["nodes"] = []
            return raw
        if args["action"] == "describe":
            return copy.deepcopy(CONTRACTS[args["script"]])
        if args["function"] == "SetPosition":
            self.position = args["args"][:]
        if args["function"] == "Disable":
            self.disabled = True
        return DONE.copy()


def mutations(session):
    return [args for tool,args,_ in session.calls if tool == "papyrus" and args.get("action") == "call"
            and args["function"] != "GetCurrentCrosshairRef"]


class TransportTests(unittest.TestCase):
    def execute(self, session, clock, *, declared_protocol=None):
        # Stock-role logic already has its own source/actual-root tests. Only its
        # admission is stubbed here; this suite deliberately tests callback flow.
        with patch.object(owned.role, "qualify", return_value={"testOnly": "admission stub"}), \
             patch.object(owned.nominal, "score", return_value={"status": "sampled-provider-selective-motion",
                 "missingDrivers": [], "runtimeQualified": False, "testOnly": "transport; no physics scoring"}):
            return owned.run(session, REF, "female", admitted=copy.deepcopy(RECORDED),
                subject_pins=PINS, stock_expected=STOCK, sleep=clock.sleep,
                clock=clock.read, monotonic=clock.read, cancelled=lambda: clock.cancelled,
                declared_protocol=declared_protocol)

    def test_recorded_native_contracts_and_changed_signature(self):
        for script, raw in CONTRACTS.items():
            owned.validate_contract(script, raw)
        changed = copy.deepcopy(CONTRACTS["ObjectReference"])
        next(r for r in changed["memberFunctions"] if r["name"] == "SetPosition")["params"][0]["type"] = "int"
        with self.assertRaisesRegex(AssertionError, "parameter mismatch"):
            owned.validate_contract("ObjectReference", changed)

    def test_actual_packets_25_points_24_intervals_and_cleanup_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            clock=Clock(); session=Session(directory, clock)
            self.execute(session, clock)
            calls=mutations(session)
            self.assertEqual([(p["script"],p["function"],p["args"]) for p in calls[:2]],
                             [("Actor","EnableAI",[True]),("Actor","SetRestrained",[True])])
            provider=[p for p in calls if p["script"] == "CBPCPluginScript"]
            plan=owned.controls.prepare(REF,"female")
            self.assertEqual(provider,[r for action in ("start","stop","restart") for r in plan["calls"][action]])
            positions=[p for p in calls if p["function"] == "SetPosition"]
            points=owned.nominal.trajectory(RECORDED["refs"][0]["position"])
            self.assertEqual([p["args"] for p in positions],points*3+[points[0]])
            self.assertTrue(all(type(v) is float for p in positions for v in p["args"]))
            self.assertEqual(sum(p["function"] == "Disable" for p in calls),1)
            self.assertEqual(calls[-1]["args"],[False])
            self.assertFalse(any(p["script"] in ("NiOverride","NetImmerse","DynamicHDT") for p in calls))
            state=json.loads((Path(directory)/"cbpc-nominal/state.json").read_bytes())
            self.assertTrue(state["cleanup"]["crosshairReleasedVerified"])
            self.assertEqual(state["cleanup"]["providerCleanupCalls"],[])
            self.assertTrue(all(len(v)==25 for v in state["positionReceipts"].values()))
            self.assertTrue(all(len(v)-1==24 for v in state["windows"].values()))
            self.assertTrue(all(kw["deadline"] in (128.,160.) for _,_,kw in session.calls))

    def test_unknown_provider_receipt_forbids_next_call_and_cleanup_mutation(self):
        for bad in ({"called":False,"returnedType":"none","returned":None},
                    {"called":True,"returnedType":"none"},
                    {"called":True,"returnedType":"bool","returned":False},
                    {**DONE,"error":"timeout"}, {**DONE,"isError":True}):
            def fault(session, tool, args):
                if args.get("function") == "StartPhysics":
                    return bad.copy()
            with self.subTest(bad=bad),tempfile.TemporaryDirectory() as directory:
                clock=Clock(); session=Session(directory,clock,fault)
                with self.assertRaises(ValueError):self.execute(session,clock)
                self.assertEqual(mutations(session)[-1]["function"],"StartPhysics")
                self.assertEqual(session.calls[-1][1]["function"],"StartPhysics")
                state=json.loads((Path(directory)/"cbpc-nominal/state.json").read_bytes())
                self.assertTrue(state["uncertain"] and state["quarantined"])
                self.assertIsNotNone(state["intent"])

    def test_unknown_position_receipt_and_inflight_interrupt_forbid_restore_disable(self):
        for interrupt in (False,True):
            def fault(session, tool, args):
                if args.get("function") == "SetPosition":
                    if interrupt:raise KeyboardInterrupt("in-flight dispatch")
                    return {"called":True,"returnedType":"none"}
            with self.subTest(interrupt=interrupt),tempfile.TemporaryDirectory() as directory:
                clock=Clock(); session=Session(directory,clock,fault)
                with self.assertRaises((ValueError,KeyboardInterrupt)):self.execute(session,clock)
                self.assertEqual([p["function"] for p in mutations(session)].count("SetPosition"),1)
                self.assertEqual(session.calls[-1][1]["function"],"SetPosition")
                self.assertFalse(any(p["function"] == "Disable" for p in mutations(session)))

    def test_cancel_after_completed_receipt_stops_before_read_or_cleanup(self):
        def fault(session, tool, args):
            if args.get("function") == "StartPhysics":
                session.clock.cancelled=True
                return DONE.copy()
        with tempfile.TemporaryDirectory() as directory:
            clock=Clock(); session=Session(directory,clock,fault)
            with self.assertRaises(owned.Cancelled):self.execute(session,clock)
            self.assertEqual(session.calls[-1][1]["function"],"StartPhysics")
            state=json.loads((Path(directory)/"cbpc-nominal/state.json").read_bytes())
            self.assertTrue(state["cancelled"] and state["quarantined"])
            self.assertFalse(state["uncertain"])
            self.assertIsNone(state["intent"])

    def test_cancel_during_wait_does_not_send_compensating_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            clock=Clock(); clock.cancel_at=3.; session=Session(directory,clock)
            with self.assertRaises(owned.Cancelled):self.execute(session,clock)
            self.assertFalse(any(p["function"] == "Disable" for p in mutations(session)))
            self.assertEqual(len([p for p in mutations(session) if p["script"] == "CBPCPluginScript"]),11)

    def test_unknown_observer_after_completed_position_stops_cleanup(self):
        def fault(session, tool, args):
            if tool == "inspect" and any(p["function"] == "SetPosition" for p in mutations(session)):
                return {"ok":False,"quality":"unavailable"}
        with tempfile.TemporaryDirectory() as directory:
            clock=Clock(); session=Session(directory,clock,fault)
            with self.assertRaises(ValueError):self.execute(session,clock)
            self.assertEqual(len([p for p in mutations(session) if p["function"] == "SetPosition"]),1)
            self.assertFalse(any(p["function"] == "Disable" for p in mutations(session)))

    def test_deadline_preserves_finite_guarded_cleanup_reserve(self):
        jumped=False
        def fault(session, tool, args):
            nonlocal jumped
            if args.get("function") == "SetPosition" and not jumped:
                jumped=True; session.clock.now=128.001
        with tempfile.TemporaryDirectory() as directory:
            clock=Clock(); session=Session(directory,clock,fault)
            with self.assertRaisesRegex(ValueError,"deadline"):self.execute(session,clock)
            self.assertEqual([p["function"] for p in mutations(session)].count("SetPosition"),2)
            self.assertEqual([p["function"] for p in mutations(session)].count("Disable"),1)
            self.assertLess(clock.now,160.)

    def test_nonnull_crosshair_requires_another_read_without_replaying_disable(self):
        reads=0
        def fault(session, tool, args):
            nonlocal reads
            if args.get("function") == "GetCurrentCrosshairRef":
                reads+=1
                if reads == 1:
                    return {"called":True,"returnedType":"ObjectReference","returned":{"form":REF}}
        with tempfile.TemporaryDirectory() as directory:
            clock=Clock(); session=Session(directory,clock,fault)
            self.execute(session,clock)
            self.assertEqual(reads,2)
            self.assertEqual([p["function"] for p in mutations(session)].count("Disable"),1)
            state=json.loads((Path(directory)/"cbpc-nominal/state.json").read_bytes())
            self.assertTrue(state["cleanup"]["crosshairReleasedVerified"])
            self.assertEqual(len(state["cleanup"]["crosshairObservations"]),2)


    def test_asyncio_cancellation_from_sleep_or_read_phase_forbids_all_later_tools(self):
        for location in ("sleep", "phase"):
            with self.subTest(location=location), tempfile.TemporaryDirectory() as directory:
                class InterruptedClock(Clock):
                    fired = False
                    def sleep(self, seconds):
                        if location == "sleep" and not self.fired:
                            self.fired = True
                            self.call_count = len(session.calls)
                            raise asyncio.CancelledError("cancelled nominal settle")
                        super().sleep(seconds)
                class InterruptedSession(Session):
                    def phase(self, *args):
                        if location == "phase" and not clock.fired and args[0] == "cbpc-nominal: start-0-before":
                            clock.fired = True
                            clock.call_count = len(self.calls)
                            raise asyncio.CancelledError("cancelled read phase")
                clock=InterruptedClock(); session=InterruptedSession(directory, clock)
                with self.assertRaises(asyncio.CancelledError): self.execute(session, clock)
                self.assertEqual(len(session.calls), clock.call_count)
                state=json.loads((Path(directory)/"cbpc-nominal/state.json").read_bytes())
                self.assertTrue(state["cancelled"] and state["quarantined"])
                self.assertFalse(any(p["function"] == "Disable" for p in mutations(session)))

    def test_asyncio_cleanup_cancellation_preserves_primary_and_stops_later_tools(self):
        jumped=False
        def fault(session, tool, args):
            nonlocal jumped
            if args.get("function") == "SetPosition" and not jumped:
                jumped=True; session.clock.now=128.001
        class InterruptedClock(Clock):
            def sleep(self, seconds):
                if not jumped:
                    return super().sleep(seconds)
                self.call_count=len(session.calls)
                raise asyncio.CancelledError("cancelled cleanup wait")
        with tempfile.TemporaryDirectory() as directory:
            clock=InterruptedClock(); session=Session(directory,clock,fault)
            with self.assertRaisesRegex(ValueError,"deadline"): self.execute(session,clock)
            self.assertEqual(len(session.calls), clock.call_count)
            state=json.loads((Path(directory)/"cbpc-nominal/state.json").read_bytes())
            self.assertTrue(state["cancelled"] and state["quarantined"])
            self.assertEqual(state["cleanup"]["error"]["type"], "CancelledError")
            self.assertFalse(any(p["function"] == "Disable" for p in mutations(session)))

    def test_intent_raw_receipt_and_completion_persistence_failures_quarantine(self):
        for stage in ("intent", "raw-receipt", "completion"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as directory:
                class FailingSession(Session):
                    fired=False
                    def save(self):
                        current=self.state.get("cbpcNominal", {})
                        intent=current.get("intent")
                        enable_seen=any(p["function"] == "EnableAI" for p in mutations(self))
                        selected=(intent is not None and intent["label"] == "EnableAI" and
                                  ((stage == "intent" and "nativeResult" not in intent) or
                                   (stage == "raw-receipt" and "nativeResult" in intent))) or (
                                  stage == "completion" and intent is None and enable_seen)
                        if selected and not self.fired:
                            self.fired=True; self.call_count=len(self.calls)
                            raise OSError("synthetic " + stage + " persistence failed")
                clock=Clock(); session=FailingSession(directory,clock)
                with self.assertRaisesRegex(OSError, stage): self.execute(session,clock)
                self.assertEqual(len(session.calls), session.call_count)
                state=json.loads((Path(directory)/"cbpc-nominal/state.json").read_bytes())
                self.assertTrue(state["uncertain"] and state["quarantined"])
                self.assertEqual(state["intent"]["label"], "EnableAI")
                self.assertEqual("nativeResult" in state["intent"], stage != "intent")
                self.assertEqual(session.state["checks"], [])

    def test_observation_raw_write_failure_quarantines_before_any_cleanup_tool(self):
        original_write=Path.write_text
        with tempfile.TemporaryDirectory() as directory:
            clock=Clock(); session=Session(directory,clock); failed=[]
            def failing_write(path, *args, **kwargs):
                if path.parent.name == "observations" and "EnableAI-after" in path.name and not failed:
                    failed.append(len(session.calls))
                    raise OSError("synthetic observation raw write failed")
                return original_write(path,*args,**kwargs)
            with patch.object(Path,"write_text",failing_write):
                with self.assertRaisesRegex(OSError,"observation raw"): self.execute(session,clock)
            self.assertEqual(len(session.calls),failed[0])
            state=json.loads((Path(directory)/"cbpc-nominal/state.json").read_bytes())
            self.assertTrue(state["quarantined"])
            self.assertEqual(session.state["checks"], [])

    def test_final_persistence_failure_fails_without_more_tools(self):
        original_write=Path.write_text
        with tempfile.TemporaryDirectory() as directory:
            clock=Clock(); session=Session(directory,clock); failed=[]
            def failing_write(path, *args, **kwargs):
                if path.name == "state.json" and path.parent.name == "cbpc-nominal" and not failed:
                    failed.append(len(session.calls))
                    raise OSError("synthetic final persistence failed")
                return original_write(path,*args,**kwargs)
            with patch.object(Path,"write_text",failing_write):
                with self.assertRaisesRegex(OSError,"final persistence"): self.execute(session,clock)
            self.assertEqual(len(session.calls),failed[0])
            state=json.loads((Path(directory)/"cbpc-nominal/state.json").read_bytes())
            self.assertTrue(state["quarantined"])
            self.assertEqual(state["finalPersistenceError"]["type"],"OSError")
            self.assertEqual(session.state["checks"], [])

    def test_error_persistence_failure_never_replaces_primary_receipt_failure(self):
        def fault(session,tool,args):
            if args.get("function") == "StartPhysics": return {**DONE,"isError":True}
        class FailingErrorSession(Session):
            def save(self):
                if self.state.get("cbpcNominal",{}).get("quarantined"):
                    raise OSError("synthetic error persistence failed")
        with tempfile.TemporaryDirectory() as directory:
            clock=Clock(); session=FailingErrorSession(directory,clock,fault)
            with self.assertRaises(ValueError) as caught: self.execute(session,clock)
            self.assertNotIsInstance(caught.exception,OSError)
            self.assertEqual(session.calls[-1][1]["function"],"StartPhysics")
            state=json.loads((Path(directory)/"cbpc-nominal/state.json").read_bytes())
            self.assertEqual(state["primaryError"]["message"],str(caught.exception))
            self.assertTrue(state["uncertain"] and state["quarantined"])
            self.assertEqual(session.state["checks"], [])


    def test_terminal_check_save_failure_quarantines_and_removes_only_its_check(self):
        class FailingTerminalSession(Session):
            failed=False
            def save(self):
                if not self.failed and any(row.get("name") == owned.nominal.protocol()["id"] for row in self.state["checks"]):
                    self.failed=True
                    self.call_count=len(self.calls)
                    raise OSError("synthetic terminal check save failed")
        with tempfile.TemporaryDirectory() as directory:
            clock=Clock(); session=FailingTerminalSession(directory,clock)
            original={"name":"preexisting-owned-check","result":"observed"}
            session.state["checks"].append(original)
            with self.assertRaisesRegex(OSError,"terminal check save"): self.execute(session,clock)
            self.assertEqual(len(session.calls),session.call_count)
            self.assertEqual(session.state["checks"],[original])
            self.assertIs(session.state["checks"][0],original)
            self.assertTrue(session.state["cbpcNominal"]["quarantined"])
            state=json.loads((Path(directory)/"cbpc-nominal/state.json").read_bytes())
            self.assertTrue(state["quarantined"])
            self.assertEqual(state["terminalError"]["type"],"OSError")


    def test_normal_ai_on_start_precedes_single_ai_off_and_75_actor_positions(self):
        spec=owned.nominal.protocol(ai_disabled=True)
        with tempfile.TemporaryDirectory() as directory:
            clock=Clock();session=Session(directory,clock)
            self.execute(session,clock,declared_protocol=spec)
            state=json.loads((Path(directory)/"cbpc-nominal/state.json").read_bytes())
            self.assertEqual(state["protocol"],spec)
            calls=mutations(session)
            self.assertEqual([r["args"] for r in calls if r["function"]=="EnableAI"],[[True],[False]])
            freeze=next(i for i,r in enumerate(calls) if r["function"]=="EnableAI" and r["args"]==[False])
            self.assertEqual(sum(r["function"]=="StartPhysics" for r in calls[:freeze]),11)
            self.assertFalse(any(r["function"]=="SetPosition" for r in calls[:freeze]))
            self.assertFalse(any(r["script"] in ("NiOverride","NetImmerse","DynamicHDT") for r in calls))
            self.assertEqual(sum(len(rows) for rows in state["positionReceipts"].values()),75)
            x=[r["request"]["args"][0] for r in state["positionReceipts"]["active"]]
            self.assertAlmostEqual(max(x)-min(x),40.)

    def test_unknown_ai_off_quarantines_and_forbids_cleanup_or_any_later_tool(self):
        failure=[]
        def fault(session,tool,args):
            if tool=="papyrus" and args.get("function")=="EnableAI" and args["args"]==[False]:
                failure.append(len(session.calls))
                raise asyncio.CancelledError("synthetic interrupted AI-off completion")
        with tempfile.TemporaryDirectory() as directory:
            clock=Clock();session=Session(directory,clock,fault)
            with self.assertRaises(asyncio.CancelledError):
                self.execute(session,clock,declared_protocol=owned.nominal.protocol(ai_disabled=True))
            self.assertEqual(len(session.calls),failure[0])
            state=json.loads((Path(directory)/"cbpc-nominal/state.json").read_bytes())
            self.assertTrue(state["quarantined"] and state["uncertain"])
            self.assertEqual(state["intent"]["request"]["args"],[False])


if __name__ == "__main__":
    unittest.main()
