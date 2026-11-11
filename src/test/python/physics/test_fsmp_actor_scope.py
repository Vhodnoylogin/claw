"""Explicit player scope and independent evidence segments, without a game."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

from test_fsmp_owned_case import Session
from test_fsmp_pulse import fixture

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integration"))
try:
    import fsmp_owned_case as case
    import fsmp_probe as scene
    import fsmp_pulse as pulse
finally:
    sys.path.pop(0)


def replace_reference(value, original, replacement):
    if isinstance(value, dict):
        return {key: replace_reference(item, original, replacement) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_reference(item, original, replacement) for item in value]
    return replacement if value == original else value


def player(value):
    result = replace_reference(value, "0xFF001234", "0x00000014")

    def metadata(item):
        if isinstance(item, dict):
            identity = item.get("identity", {})
            if identity.get("form") == "0x00000014":
                identity.update(sourcePlugin="Skyrim.esm", localFormId="0x00000014")
            for row in item.get("refs", []):
                row["baseForm"] = row["actor"]["baseForm"] = "0x00000007"
                row["actor"]["baseRace"] = "0x00013746"
            for child in item.values():
                metadata(child)
        elif isinstance(item, list):
            for child in item:
                metadata(child)

    metadata(result)
    return result


class PlayerScopeTests(unittest.TestCase):
    def test_default_form_and_snapshot_still_refuse_the_player(self):
        raw = player(fixture())["baseline"]
        with self.assertRaisesRegex(ValueError, "never the player"):
            scene.form("0x14")
        with self.assertRaisesRegex(ValueError, "never the player"):
            scene.snapshot(raw, "0x00000014", "female")
        result = scene.snapshot(raw, "0x00000014", "female", actor_role="owned-player")
        self.assertEqual(result["guard"]["identity"]["form"], "0x00000014")

    def test_owned_player_pulse_score_retains_the_same_eleven_driver_gate(self):
        document = player(fixture())
        document["actorRole"] = "owned-player"
        result = pulse.score(document)
        self.assertEqual(result["status"], "sampled-pulse-contrast-observed")
        self.assertEqual(len({row["node"] for row in result["selectiveChannels"]}), 11)

    def test_missing_opt_in_wrong_reference_and_epoch_change_fail_closed(self):
        for kind in ("missing-role", "wrong-reference", "changed-epoch"):
            with self.subTest(kind=kind):
                document = player(fixture())
                document["actorRole"] = "owned-player"
                if kind == "missing-role":
                    document.pop("actorRole")
                elif kind == "wrong-reference":
                    document["reference"] = "0xFF001234"
                else:
                    document["pulses"]["active"]["Tails"]["samples"][0]["loadGeneration"] += 1
                with self.assertRaises(ValueError):
                    pulse.score(document)

    def test_default_callback_wrong_role_and_nonpulse_player_never_dispatch(self):
        cases = (("0x14", {}), ("0xFF001234", {"actor_role": "owned-player"}),
                 ("0x14", {"actor_role": "owned-player", "stimulus": "reference"}))
        for reference, settings in cases:
            with self.subTest(settings=settings), tempfile.TemporaryDirectory() as directory:
                session = Session(directory, sex="female")
                with self.assertRaises(ValueError):
                    case.run(session, reference, "female", **settings)
                self.assertEqual(session.calls, [])

    def test_explicit_player_callback_never_disposes_or_repositions_the_player(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session(directory, sex="female")
            session.sample = player(session.sample)
            result = case.run(session, "0x14", "female", actor_role="owned-player",
                              stimulus="xml-anchor-pulse", segment="wolf-initial", sleep=lambda _: None)
            # The synthetic scene has no solver response: collecting is not a pass.
            self.assertEqual(result["status"], "unconfirmed")
            self.assertFalse(any(args.get("function") in ("Disable", "SetPosition") for _, args in session.calls))
            state = json.loads((Path(directory)/"fsmp-probe/wolf-initial/state.json").read_bytes())
            self.assertEqual(state["actorRole"], "owned-player")
            self.assertEqual(state["segment"], "wolf-initial")
            self.assertEqual(session.state["fsmpProbe"]["directory"], str(Path(directory)/"fsmp-probe/wolf-initial"))

    def test_disposal_hard_refuses_player_before_any_native_call(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session(directory, sex="female")
            with self.assertRaisesRegex(ValueError, "never the player"):
                case.dispose_fixture(session, "0x14", "female", player(session.sample))
            self.assertEqual(session.calls, [])


class SegmentTests(unittest.TestCase):
    def test_npc_disposal_uses_the_declared_segment_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session(directory)
            (Path(directory)/"fsmp-probe/first").mkdir(parents=True)
            result = case.dispose_fixture(session, "0xFF001234", "male", session.sample, segment="first")
            self.assertTrue(result["verifiedDisabledAndCrosshairReleased"])
            self.assertTrue((Path(directory)/"fsmp-probe/first/fixture-disposal.json").is_file())
            self.assertFalse((Path(directory)/"fsmp-probe/fixture-disposal.json").exists())

    def test_invalid_segment_cannot_create_files_or_dispatch(self):
        for segment in ("", "../outside", "a/b", "a\\b", "C:\\escape", "A", "a"*49, 1):
            with self.subTest(segment=segment), tempfile.TemporaryDirectory() as directory:
                session = Session(directory)
                with self.assertRaisesRegex(ValueError, "segment identifier"):
                    case.run(session, "0xFF001234", "male", segment=segment)
                self.assertEqual(session.calls, [])
                self.assertEqual(list(Path(directory).iterdir()), [])

    def test_existing_segment_is_not_overwritten_or_reentered(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session(directory)
            case.run(session, "0xFF001234", "male", segment="first", sleep=lambda _: None)
            state = Path(directory)/"fsmp-probe/first/state.json"
            original, count = state.read_bytes(), len(session.calls)
            with self.assertRaises(FileExistsError):
                case.run(session, "0xFF001234", "male", segment="first", sleep=lambda _: None)
            self.assertEqual(len(session.calls), count)
            self.assertEqual(state.read_bytes(), original)

    def test_fresh_actor_callback_keeps_the_previous_segment_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Session(directory)
            case.run(first, "0xFF001234", "male", segment="first", sleep=lambda _: None)
            original = (Path(directory)/"fsmp-probe/first/state.json").read_bytes()
            second = Session(directory)
            second.sample = replace_reference(second.sample, "0xFF001234", "0xFF001235")
            case.run(second, "0xFF001235", "male", segment="second", sleep=lambda _: None)
            self.assertEqual((Path(directory)/"fsmp-probe/first/state.json").read_bytes(), original)
            state = json.loads((Path(directory)/"fsmp-probe/second/state.json").read_bytes())
            self.assertEqual(state["reference"], "0xFF001235")

    def test_same_graph_empty_container_is_not_waived_for_a_new_segment(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session(directory)
            case.run(session, "0xFF001234", "male", stimulus="xml-anchor-pulse",
                     segment="first", sleep=lambda _: None)
            count = len(session.calls)
            with self.assertRaisesRegex(ValueError, "external transform keys"):
                case.run(session, "0xFF001234", "male", stimulus="xml-anchor-pulse",
                         segment="second", sleep=lambda _: None)
            self.assertFalse(any(args.get("function") == "AddNodeTransformPosition"
                                 for _, args in session.calls[count:]))


if __name__ == "__main__":
    unittest.main()
