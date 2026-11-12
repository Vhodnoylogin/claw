"""Failure-boundary counterexamples; synthetic transport, no game or metric change."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_fsmp_owned_case import Session, case


class FsmpLifecycleSafetyTests(unittest.TestCase):
    def run_failure(self, session, error=ValueError, stimulus="xml-anchor-pulse", **kwargs):
        with self.assertRaises(error) as raised:
            case.run(session, "0xFF001234", session.sex, stimulus=stimulus,
                     sleep=lambda _: None, **kwargs)
        self.assertTrue(session.state["ownedFixtureQuarantine"])
        calls = copy.deepcopy(session.calls)
        result = case.dispose_fixture(session, "0xFF001234", session.sex,
                                      copy.deepcopy(session.sample))
        self.assertTrue(result["skipped"])
        self.assertFalse(result["verifiedDisabledAndCrosshairReleased"])
        self.assertEqual(session.calls, calls)  # Even an unconditional outer finally cannot dispatch.
        return raised.exception

    def test_interrupt_during_native_toggle_preserves_interrupt_and_forbids_cleanup(self):
        class Interrupted(Session):
            def tool(self, tool, args, **kwargs):
                result = super().tool(tool, args, **kwargs)
                if args.get("function") == "TogglePhysics":
                    raise KeyboardInterrupt("interrupted after native side effect")
                return result
        with tempfile.TemporaryDirectory() as directory:
            session = Interrupted(directory)
            error = self.run_failure(session, KeyboardInterrupt)
            self.assertIn("after native side effect", str(error))
            self.assertEqual(session.calls[-1][1]["function"], "TogglePhysics")
            self.assertEqual(session.previous, [False]*9)

    def test_baseexception_during_anchor_add_does_not_remove_or_restore_any_anchor(self):
        class Interrupted(Session):
            def tool(self, tool, args, **kwargs):
                result = super().tool(tool, args, **kwargs)
                if args.get("function") == "AddNodeTransformPosition":
                    raise SystemExit("unknown anchor completion")
                return result
        with tempfile.TemporaryDirectory() as directory:
            session = Interrupted(directory, sex="female")
            self.run_failure(session, SystemExit)
            self.assertEqual(session.calls[-1][1]["function"], "AddNodeTransformPosition")
            self.assertTrue(any(v is not None for rows in session.anchor_keys.values() for v in rows.values()))

    def test_error_envelopes_keep_raw_reply_and_stop_all_later_tools(self):
        for function, stimulus in (("TogglePhysics", "xml-anchor-pulse"),
                                   ("AddNodeTransformPosition", "xml-anchor-pulse"),
                                   ("Wait", "xml-anchor-pulse"), ("SetPosition", "reference")):
            class ErrorReply(Session):
                def tool(self, tool, args, **kwargs):
                    result = super().tool(tool, args, **kwargs)
                    if args.get("function") == function:
                        result["isError"] = True
                    return result
            with self.subTest(function=function), tempfile.TemporaryDirectory() as directory:
                session = ErrorReply(directory)
                self.run_failure(session, stimulus=stimulus)
                self.assertEqual(session.calls[-1][1]["function"], function)
                journal = json.loads((Path(directory)/"fsmp-probe/journal.json").read_text())
                self.assertTrue(journal["intent"]["nativeResult"]["isError"])

    def test_intent_persistence_failure_never_dispatches_native_mutation(self):
        class FailedJournal(Session):
            def save(self):
                if self.state.get("fsmpProbe", {}).get("intent"):
                    raise OSError("intent persistence unavailable")
        with tempfile.TemporaryDirectory() as directory:
            session = FailedJournal(directory)
            error = self.run_failure(session, OSError)
            self.assertEqual(str(error), "intent persistence unavailable")
            self.assertFalse(any(tool == "papyrus" for tool, _ in session.calls))

    def test_raw_receipt_persistence_failure_retains_reply_and_interlocks_before_retry(self):
        class FailedJournal(Session):
            def save(self):
                intent = self.state.get("fsmpProbe", {}).get("intent")
                if intent and "nativeResult" in intent:
                    raise OSError("raw receipt persistence unavailable")
        with tempfile.TemporaryDirectory() as directory:
            session = FailedJournal(directory)
            self.run_failure(session, OSError)
            self.assertEqual(session.calls[-1][1]["function"], "TogglePhysics")
            marker = session.state["ownedFixtureQuarantine"]
            self.assertEqual(marker["intent"]["nativeResult"]["returned"], [True]*9)

    def test_cleared_intent_persistence_failure_does_not_authorize_next_tool(self):
        class FailedClear(Session):
            saw_reply = False
            def save(self):
                intent = self.state.get("fsmpProbe", {}).get("intent")
                if intent and "nativeResult" in intent:
                    self.saw_reply = True
                elif self.saw_reply and not intent:
                    raise OSError("completed receipt clear not durable")
        with tempfile.TemporaryDirectory() as directory:
            session = FailedClear(directory)
            self.run_failure(session, OSError)
            self.assertEqual(session.calls[-1][1]["function"], "TogglePhysics")
            state = json.loads((Path(directory)/"fsmp-probe/state.json").read_text())
            self.assertEqual(state["lastCompletedMutation"]["nativeResult"]["returned"], [True]*9)

    def test_cancellation_after_native_return_persists_known_reply_before_quarantine(self):
        class CancelAfterReturn(Session):
            cancel = False
            def tool(self, tool, args, **kwargs):
                result = super().tool(tool, args, **kwargs)
                if args.get("function") == "TogglePhysics":
                    self.cancel = True
                return result
        with tempfile.TemporaryDirectory() as directory:
            session = CancelAfterReturn(directory)
            self.run_failure(session, RuntimeError, cancelled=lambda: session.cancel)
            self.assertEqual(session.calls[-1][1]["function"], "TogglePhysics")
            state = json.loads((Path(directory)/"fsmp-probe/state.json").read_text())
            self.assertEqual(state["lastCompletedMutation"]["nativeResult"]["returned"], [True]*9)

    def test_preexisting_quarantine_refuses_new_segment_without_any_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session(directory)
            session.state["ownedFixtureQuarantine"] = {"reason": "prior unknown completion"}
            with self.assertRaisesRegex(ValueError, "quarantined"):
                case.run(session, "0xFF001234", "male", segment="after-load")
            self.assertEqual(session.calls, [])

    def test_existing_foreign_or_empty_key_is_still_rejected_without_adoption(self):
        for key, value in (("foreign", [1., 0., 0.]), ("CLAW.FSMPProbe.older-segment", None)):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                session = Session(directory)
                session.anchor_keys["NPC Head [Head]"] = {key: value}
                with self.assertRaisesRegex(ValueError, "Fresh anchor has external transform keys"):
                    case.run(session, "0xFF001234", "male", stimulus="xml-anchor-pulse", sleep=lambda _: None)
                self.assertFalse(any(args.get("function") == "AddNodeTransformPosition" for _, args in session.calls))
                self.assertEqual(session.anchor_keys["NPC Head [Head]"], {key: value})

    def test_disposal_error_receipt_or_interrupt_quarantines_second_disposal(self):
        for failure in ("isError", "interrupt"):
            class FailedDisable(Session):
                def tool(self, tool, args, **kwargs):
                    result = super().tool(tool, args, **kwargs)
                    if args.get("function") == "Disable":
                        if failure == "interrupt":
                            raise KeyboardInterrupt("Disable return lost")
                        result["isError"] = True
                    return result
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                session = FailedDisable(directory)
                (Path(directory)/"fsmp-probe").mkdir()
                admitted = copy.deepcopy(session.sample)
                with self.assertRaises(KeyboardInterrupt if failure == "interrupt" else ValueError):
                    case.dispose_fixture(session, "0xFF001234", "male", admitted)
                self.assertEqual(session.calls[-1][1]["function"], "Disable")
                before = copy.deepcopy(session.calls)
                self.assertTrue(case.dispose_fixture(session, "0xFF001234", "male", admitted)["skipped"])
                self.assertEqual(session.calls, before)

    def test_unknown_cleanup_result_stops_other_anchors_and_preserves_primary_error(self):
        class LostCleanup(Session):
            def tool(self, tool, args, **kwargs):
                result = super().tool(tool, args, **kwargs)
                if args.get("function") == "RemoveNodeTransformPosition":
                    result["isError"] = True
                return result
        with tempfile.TemporaryDirectory() as directory:
            session = LostCleanup(directory, frozen_anchors=True)
            error = self.run_failure(session, stimulus="xml-anchors")
            self.assertIn("Mass-zero anchor world displacement", str(error))
            self.assertTrue(any("FSMP cleanup:" in note for note in error.__notes__))
            self.assertEqual(session.calls[-1][1]["function"], "RemoveNodeTransformPosition")

    def test_anchor_raw_persistence_failure_blocks_update_and_every_cleanup_tool(self):
        class FailedAnchorJournal(Session):
            def save(self):
                intent = self.state.get("fsmpProbe", {}).get("intent")
                if intent and intent.get("action") == "anchor" and "nativeResult" in intent:
                    raise OSError("anchor receipt not durable")
        with tempfile.TemporaryDirectory() as directory:
            session = FailedAnchorJournal(directory)
            self.run_failure(session, OSError)
            self.assertEqual(session.calls[-1][1]["function"], "AddNodeTransformPosition")
            self.assertTrue(session.state["ownedFixtureQuarantine"]["intent"]["nativeResult"]["called"])

    def test_unavailable_anchor_read_quarantines_before_any_anchor_write(self):
        class LostRead(Session):
            def tool(self, tool, args, **kwargs):
                result = super().tool(tool, args, **kwargs)
                if args.get("function") == "GetNodeTransformKeys":
                    result["called"] = False
                return result
        with tempfile.TemporaryDirectory() as directory:
            session = LostRead(directory)
            self.run_failure(session)
            self.assertEqual(session.calls[-1][1]["function"], "GetNodeTransformKeys")

    def test_cancelled_disposal_performs_no_tools_and_interlocks_outer_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session(directory)
            (Path(directory)/"fsmp-probe").mkdir()
            admitted = copy.deepcopy(session.sample)
            with self.assertRaisesRegex(RuntimeError, "cancelled"):
                case.dispose_fixture(session, "0xFF001234", "male", admitted, cancelled=lambda: True)
            self.assertEqual(session.calls, [])
            self.assertTrue(case.dispose_fixture(session, "0xFF001234", "male", admitted)["skipped"])

    def test_interrupt_in_cleanup_is_preserved_when_there_is_no_primary_failure(self):
        class CleanupInterrupted(Session):
            def tool(self, tool, args, **kwargs):
                result = super().tool(tool, args, **kwargs)
                if args.get("function") == "SetPosition" and self.current_phase == "fsmp: cleanup-position":
                    raise KeyboardInterrupt("cleanup position completion lost")
                return result
        with tempfile.TemporaryDirectory() as directory:
            session = CleanupInterrupted(directory)
            error = self.run_failure(session, KeyboardInterrupt, stimulus="reference")
            self.assertEqual(str(error), "cleanup position completion lost")
            self.assertEqual(session.calls[-1][1]["function"], "SetPosition")

    def test_disposal_raw_receipt_write_failure_blocks_disabled_and_crosshair_reads(self):
        original = Path.write_text
        def fail_receipt(path, data, *args, **kwargs):
            if path.name == "fixture-disposal.json" and '"receipt"' in data:
                raise OSError("Disable receipt not durable")
            return original(path, data, *args, **kwargs)
        with tempfile.TemporaryDirectory() as directory:
            session = Session(directory)
            (Path(directory)/"fsmp-probe").mkdir()
            with patch.object(Path, "write_text", fail_receipt):
                with self.assertRaisesRegex(OSError, "Disable receipt not durable"):
                    case.dispose_fixture(session, "0xFF001234", "male", copy.deepcopy(session.sample))
            self.assertTrue(session.state["ownedFixtureQuarantine"])
            self.assertEqual(session.calls[-1][1]["function"], "Disable")


    def test_fresh_nested_disposal_evidence_exists_before_pre_pulse_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            parent=Path(directory)/"fsmp-probe"/"after-model"
            class FreshSegment(Session):
                def phase(self,*args):
                    self_parent=Path(directory)/"fsmp-probe"/"after-model"
                    self.assert_directory_ready=self_parent.is_dir()
                    super().phase(*args)
                def tool(self,tool,args,**kwargs):
                    if not parent.is_dir():raise AssertionError("Transport before disposal evidence parent")
                    return super().tool(tool,args,**kwargs)
            session=FreshSegment(directory)
            self.assertFalse(parent.exists())
            result=case.dispose_fixture(session,"0xFF001234","male",copy.deepcopy(session.sample),segment="after-model")
            self.assertTrue(session.assert_directory_ready)
            self.assertTrue(result["verifiedDisabledAndCrosshairReleased"])
            self.assertEqual(len(result["observations"]),1)
            self.assertEqual(sum(args.get("function")=="Disable" for _,args in session.calls),1)
            self.assertTrue((parent/"fixture-disposal.json").is_file())
            self.assertFalse(any(args.get("function")=="TogglePhysics" for _,args in session.calls))

    def test_disposal_mkdir_failure_quarantines_before_any_transport_or_retry(self):
        for failure in (OSError("disposal directory denied"),KeyboardInterrupt("disposal directory interrupted")):
            with self.subTest(failure=type(failure).__name__),tempfile.TemporaryDirectory() as directory:
                session=Session(directory);admitted=copy.deepcopy(session.sample)
                with patch.object(Path,"mkdir",side_effect=failure) as mkdir:
                    with self.assertRaises(type(failure)) as raised:
                        case.dispose_fixture(session,"0xFF001234","male",admitted,segment="after-load")
                    self.assertIs(raised.exception,failure)
                    self.assertEqual(mkdir.call_count,1)
                    self.assertEqual(session.calls,[])
                    self.assertTrue(session.state["ownedFixtureQuarantine"]["ownedSessionTeardownRequired"])
                    self.assertIsNone(session.state["ownedFixtureQuarantine"]["intent"])
                    result=case.dispose_fixture(session,"0xFF001234","male",admitted,segment="after-load")
                    self.assertTrue(result["skipped"])
                    self.assertEqual(mkdir.call_count,1)
                self.assertEqual(list(Path(directory).iterdir()),[])

    def test_disposal_player_invalid_and_quarantined_refusal_has_zero_filesystem(self):
        for reference in ("0x14","0x00000014","not-a-form","0x0"):
            with self.subTest(reference=reference),tempfile.TemporaryDirectory() as directory:
                session=Session(directory)
                with patch.object(Path,"mkdir") as mkdir,patch.object(Path,"write_text") as write:
                    with self.assertRaises(ValueError):
                        case.dispose_fixture(session,reference,"male",copy.deepcopy(session.sample),segment="after-model")
                    mkdir.assert_not_called();write.assert_not_called()
                self.assertEqual(session.calls,[]);self.assertEqual(list(Path(directory).iterdir()),[])
        with tempfile.TemporaryDirectory() as directory:
            session=Session(directory);session.state["ownedFixtureQuarantine"]={"reason":"earlier unknown"}
            with patch.object(Path,"mkdir") as mkdir,patch.object(Path,"write_text") as write:
                self.assertTrue(case.dispose_fixture(session,"0xFF001234","male",None,segment="after-load")["skipped"])
                mkdir.assert_not_called();write.assert_not_called()
            self.assertEqual(session.calls,[]);self.assertEqual(list(Path(directory).iterdir()),[])



if __name__ == "__main__":
    unittest.main()
