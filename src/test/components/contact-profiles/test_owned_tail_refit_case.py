"""Exercise the admitted-session binding without opening a game or manager."""

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from owned_tail_refit_case import bind_capture
from run_tail_refit import Capture
from tail_refit_morph import UnconfirmedMutation
from test_tail_refit import ACTOR_HEX, BASIS, BASE, HANDLE, MODEL, PID


class OwnedCaptureTest(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.tag = "claw-tail-refit"
        self.base = f"0x{BASE:08X}"
        self.incarnation = {"sessionId": f"{PID}-test", "loadGeneration": 1, "runtimeHandle": HANDLE}
        self.entry = {
            "status": "created", "reference": ACTOR_HEX, "createdReference": ACTOR_HEX, "base": self.base,
            "creationId": "12345678" + "9" * 24, "incarnation": self.incarnation,
            "creationWitness": {"forcePersist": False},
            "actor": {"sex": "male", "race": "0x000CDD84", "weight": 50, "loaded3D": True},
        }
        self.row = {key: self.entry[key] for key in ("base", "reference", "creationId", "incarnation")}
        self.row.update(kind="interactive-fixture-created", tag=self.tag)
        self.session = SimpleNamespace(dir=Path(directory.name), tool=Mock(), state={
            "id": "exact-vr-attempt", "game": {"pid": PID, "birth": 1024, "path": "D:/SkyrimVR.exe"},
            "configuration": {"game_edition": "vr"}, "gameplayBootstrap": {"completed": True},
            "testProfile": "disposable", "ownedWorldGeneration": 1,
            "interactiveActorFixtures": {self.tag: self.entry},
        })
        self.ledger = self.session.dir / "steps.jsonl"
        self.ledger.write_text(json.dumps(self.row) + "\n", encoding="utf-8")
        self.alive = Mock(return_value=True)
        self.require_fixture = Mock(return_value=self.entry)
        modules = patch.dict(sys.modules, {
            "skyrim_autotest": SimpleNamespace(native=SimpleNamespace(alive=self.alive)),
            "skyrim_autotest.fixture_actors": SimpleNamespace(require_fixture=self.require_fixture),
        })
        modules.start()
        self.addCleanup(modules.stop)
        files = patch.object(Capture, "from_files", side_effect=self.make_capture)
        files.start()
        self.addCleanup(files.stop)

    def make_capture(self, call, path, subject, _profile, _basis, *, deadline):
        return Capture(call, path, subject, MODEL, BASIS, deadline=deadline)

    def bind(self):
        return bind_capture(self.session, tag=self.tag, resolved_base=self.base,
                            profile_path=Path("profile.json"), basis_path=Path("basis.json"), deadline=95.)

    def test_uses_executor_creation_binding_before_transport(self):
        capture = self.bind()
        self.require_fixture.assert_called_once_with(self.session, {"reference": ACTOR_HEX, "base": self.base})
        self.assertEqual(capture.owner, (f"{PID}-test", 1, HANDLE))
        self.assertEqual(capture.manifest["fixtureCreation"]["index"], 0)
        self.session.tool.assert_not_called()

    def test_rejects_archived_or_reused_dynamic_reference(self):
        self.entry["creationWitness"]["forcePersist"] = True
        with self.assertRaisesRegex(ValueError, "nonpersistent"):
            self.bind()
        self.session.tool.assert_not_called()

    def test_rejects_changed_creation_log(self):
        self.row["incarnation"] = {**self.incarnation, "runtimeHandle": 1}
        self.ledger.write_text(json.dumps(self.row) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "creation identity differs"):
            self.bind()
        self.session.tool.assert_not_called()

    def test_refuses_driver_action_after_process_or_world_replacement(self):
        capture = self.bind()
        self.session.state["game"]["birth"] += 1
        with self.assertRaises(UnconfirmedMutation):
            capture.call("driver", {"action": "status"})
        self.session.tool.assert_not_called()


if __name__ == "__main__":
    unittest.main()
