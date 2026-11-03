"""Actual Host/native authority wiring contracts; no game/provider simulation."""
from pathlib import Path
import re
import unittest
ROOT = Path(__file__).resolve().parents[4]
HOST = (ROOT / "src/main/python/physics/papyrus/CLAWPhysicsHost.psc").read_text()
CONTROL = (ROOT / "src/main/python/physics/papyrus/CLAWPhysicsControl.psc").read_text()
PLUGIN = (ROOT / "src/main/cpp/src/Plugin.cpp").read_text()

def body(source, name):
    return re.search(r"(?im)^.*?Function " + name + r"\([^\n]*\)[^\n]*\n(.*?)^EndFunction", source, re.S | re.M).group(1)

class PhysicsAuthorityContracts(unittest.TestCase):
    def test_only_explicit_enable_selects_qualified_and_population_selects_initial(self):
        explicit = body(HOST, "EnableAutomatic")
        candidate = body(HOST, "OnPhysicsCandidate")
        cached = body(HOST, "ProcessAutomatic")
        self.assertIn("expectedRuntime, False)", explicit)
        self.assertIn("expectedRuntime, True)", candidate)
        self.assertNotIn("RegisterQualifiedActor", cached + candidate)
        self.assertNotIn("EnableAutomaticInternal", cached)
        dispatch = body(HOST, "RegisterAutomatic")
        self.assertLess(dispatch.index("If initialPopulation"), dispatch.index("ElseIf qualified"))
        for api in ("RegisterInitialActor", "RegisterQualifiedActor", "RegisterActor"):
            self.assertRegex(dispatch, api + r"\([^\n]+expectedRuntime\)")
    def test_new_grant_requires_retired_old_ledger_before_requalification(self):
        enable = body(HOST, "EnableAutomaticInternal")
        ledger = enable.index('Return Fail(-5, "Retire the exact previous capsule ledger')
        self.assertLess(ledger, enable.index("helper.QualifyForActor"))
        self.assertLess(ledger, enable.index("RegisterAutomatic"))
        self.assertNotIn("AcknowledgeProviderReset", enable)
    def test_cached_events_are_current_wakeups_and_old_snapshot_cannot_clean_new(self):
        cached = body(HOST, "ProcessAutomatic")
        self.assertLess(cached.index("ConditionCurrent(target, kind, expectedRuntime)"), cached.index("helper.MarkModelGenerationChanged"))
        self.assertLess(cached.index('ConditionCurrent(target, "renew", expectedRuntime)'), cached.index("helper.Cleanup()"))
        condition = PLUGIN.split("bool physicsConditionCurrent(", 1)[1].split("bool physicsSnapshotCurrent", 1)[0]
        self.assertIn('if (kind == "renew") return found->second.condition == "waiting"', condition)
        self.assertIn("if (authority.pending()) return false", condition)
    def test_native_registration_ticket_is_captured_before_task_and_rechecked(self):
        register = PLUGIN.split("bool registerPhysics(", 1)[1].split("bool physicsRegister(", 1)[0]
        self.assertLess(register.index("physicsAuthority.admit"), register.index("tasks->AddTask"))
        self.assertLess(register.index("old->second.ready = false"), register.index("tasks->AddTask"))
        self.assertIn("observePhysicsContext(target, state)", register)
        self.assertIn("physicsAuthority.commit(ticket, physicsOwner(state), pending->second)", register)
        self.assertGreaterEqual(register.count("physicsSessionMatches("), 2)
        unregister = PLUGIN.split("void physicsUnregister(", 1)[1].split("bool physicsActorCurrent", 1)[0]
        self.assertIn("physicsAuthority.suspend()", unregister)
        self.assertNotIn("states.erase", unregister)
        self.assertIn("state.physicsAuthority.engaged()) continue", PLUGIN)
    def test_process_world_and_same_world_session_proof_are_fixed_at_first_boundary(self):
        begin = body(CONTROL, "BeginSession")
        self.assertLess(begin.index("BeginSessionToken()"), begin.index("GetHost()"))
        self.assertIn("NotifySessionChanged(expectedRuntime)", begin)
        self.assertIn("evidence, expectedRuntime)", begin)
        notify = body(HOST, "NotifySessionChanged")
        self.assertIn("EndSession(previousRuntime)", notify)
        self.assertIn("DisableAutomaticForRuntime(slot, retirementRuntime)", notify)
        disable = body(HOST, "DisableAutomaticForRuntime")
        self.assertNotIn("_runtimeSession", disable)
        self.assertIn("expectedRuntime)", disable)
        rotate = PLUGIN.split("std::string rotatePhysicsSession(", 1)[1].split("bool physicsSetPopulation", 1)[0]
        self.assertIn("physicsSessionAuthorized = authorize", rotate)
        self.assertIn("physicsSessionMatches(expectedSession.c_str()) ? rotatePhysicsSession(false)", rotate)
        register = PLUGIN.split("bool registerPhysics(", 1)[1].split("bool physicsRegister(", 1)[0]
        self.assertEqual(register.count("!physicsSessionAuthorized || !physicsSessionMatches("), 2)
        self.assertIn('std::to_string(physicsSessionWorld) + "/" + std::to_string(physicsSessionRevision)', PLUGIN)
        self.assertIn("physicsProcessNonce", PLUGIN)
        self.assertIn("physicsSessionWorld != epoch", PLUGIN)
        self.assertIn("if (authorize) physicsSessionWorld = epoch.load()", rotate)
    def test_cleanup_and_publication_use_separate_native_authority(self):
        cleanup = PLUGIN.split("bool physicsActorCurrent(", 1)[1].split("const PhysicsBinding* physicsSnapshot", 1)[0]
        snapshot = PLUGIN.split("const PhysicsBinding* physicsSnapshot", 1)[1].split("bool physicsConditionCurrent", 1)[0]
        self.assertIn("cleanupAllowed", cleanup)
        self.assertNotIn("renewable", cleanup)
        self.assertIn("publishable", snapshot)
        self.assertIn("physicsRoots.size() >= 16", PLUGIN)

if __name__ == "__main__": unittest.main()
