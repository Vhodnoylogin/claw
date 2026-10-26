"""Safety contracts in actual PSC source; no Papyrus/CBPC event execution claimed.

These checks guard the failure paths that compilation alone cannot establish.
They deliberately inspect the shipped source instead of a Python lifecycle copy.
Engine event delivery, stack scheduling and native results still need game tests.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1] / "papyrus"


def source(name):
    # Semicolons inside a PSC string are not comments.
    return "\n".join(re.match(r'((?:"[^"\\]*(?:\\.[^"\\]*)*"|[^";])*)', line)[1]
                     for line in (ROOT / name).read_text().splitlines())


def body(text, name, kind="Function"):
    match = re.search(r"(?im)^.*\b" + kind + r"\s+" + name + r"\([^\n]*\)[ \t]*(?:Global[ \t]*)?$", text)
    if not match:
        raise AssertionError("Missing " + name)
    return re.split(r"(?im)^End" + kind + r"\s*$", text[match.end():], maxsplit=1)[0]


class LifecycleSourceContracts(unittest.TestCase):
    def setUp(self):
        self.actor = source("CLAWPhysicsActor.psc")
        self.host = source("CLAWPhysicsHost.psc")

    def test_retarget_and_release_refuse_busy_or_pending_cleanup_before_alias_write(self):
        for name in ("AssignInternal", "ReleaseInternal"):
            with self.subTest(name=name):
                code = body(self.host, name)
                gate = re.search(r"If cleanup == 8 \|\| helper.GetAcceptedLedgerCount\(\) > 0\s+Return Fail\(-3,[^\n]+\)\s+EndIf", code)
                self.assertIsNotNone(gate)
                self.assertLess(code.index("helper.Cleanup()"), gate.start())
                self.assertGreater(code.index("helper.Clear()"), gate.end())
                if name == "AssignInternal":
                    self.assertGreater(code.index("helper.ForceRefTo(target)"), code.index("helper.Clear()"))

    def test_failed_clear_blocks_force_and_force_requires_observed_actor(self):
        code = body(self.host, "AssignInternal")
        refusal = re.search(r"If helper.GetReference\(\) != None\s+Return Fail\(-4,[^\n]+\)\s+EndIf", code)
        self.assertIsNotNone(refusal)
        self.assertLess(refusal.end(), code.index("helper.ForceRefTo(target)"))
        self.assertRegex(code, r"If helper.GetActorReference\(\) != target\s+Return Fail\(-4,")

    def test_pending_former_actor_reserves_actor_across_other_slots(self):
        duplicate = body(self.host, "ActorInOtherSlot")
        self.assertIn("GetActorReference() == target || _slots[slot].GetTrackedActor() == target", duplicate)
        for name in ("AssignInternal", "QualifyInternal", "PulseInternal"):
            self.assertIn("ActorInOtherSlot(", body(self.host, name))

    def test_native_false_detach_does_not_clear_accepted_ledger(self):
        cleanup = body(self.actor, "CleanupInternal")
        self.assertRegex(cleanup, r"If removed\s+_accepted\[slot\] = False\s+EndIf")
        self.assertEqual(cleanup.count("_accepted[slot] = False"), 1)
        self.assertIn("If GetAcceptedLedgerCount() > 0", cleanup)
        self.assertIn("Return SetStatus(6,", cleanup)

    def test_each_cleanup_native_mutation_rechecks_captured_actor_authority_and_generation(self):
        context = body(self.actor, "CleanupContextCurrent")
        for requirement in ("_tracked == target", "ProviderQualified", "ExclusiveIndexRange", "_modelGeneration == generation"):
            self.assertIn(requirement, context)
        self.assertNotIn("GetActorReference", context)  # old alias actor still needs its own cleanup
        cleanup = body(self.actor, "CleanupInternal")
        self.assertLess(cleanup.index("Actor cleanupActor = _tracked"), cleanup.index("While slot < CLAWPhysicsData.SlotCount()"))
        self.assertLess(cleanup.index("Int cleanupGeneration = _modelGeneration"), cleanup.index("While slot < CLAWPhysicsData.SlotCount()"))
        call = "Bool removed = CBPCPluginScript.DetachCollider(cleanupActor, node, 1, colliderIndex, True)"
        self.assertIn(call, cleanup)
        # No data/native query may be inserted between the final guard and detach.
        guard = r"If !CleanupContextCurrent\(cleanupActor, cleanupGeneration\)\s+Return SetStatus\(6,[^\n]+\)\s+EndIf"
        self.assertRegex(cleanup, guard + r"\s+" + re.escape(call))
        # A revocation during the native call must retain this slot even on true.
        self.assertRegex(cleanup, re.escape(call) + r"\s+" + guard + r"\s+If removed\s+_accepted\[slot\] = False")

    def test_append_rechecks_after_preclean_and_data_reads_including_alias_identity(self):
        context = body(self.actor, "AttachmentContextCurrent")
        for requirement in ("!IsCurrentBeast(target)", "!target.Is3DLoaded()", "!NetImmerse.HasNode(target, node, False)",
                            "GetActorReference() != target", "_tracked == target", "_modelGeneration == generation", "AttachmentQualified(target)"):
            self.assertIn(requirement, context)
        sync = body(self.actor, "SynchronizeInternal")
        append = sync.index("Bool accepted = CBPCPluginScript.AttachColliderCapsule(")
        recheck = sync.rindex("If !AttachmentContextCurrent(target, synchronizationGeneration, node)", 0, append)
        for read in ("CBPCPluginScript.DetachCollider(", "CLAWPhysicsData.Point(slot, female, False)",
                     "CLAWPhysicsData.Point(slot, female, True)", "CLAWPhysicsData.Radius(slot, female)"):
            self.assertLess(sync.index(read), recheck)
        self.assertRegex(sync[recheck:append], r"^If !AttachmentContextCurrent\(target, synchronizationGeneration, node\)\s+failed = True\s+Else\s+$")
        self.assertNotIn("CLAWPhysicsData.", sync[append:sync.index("_accepted[slot] = accepted", append)])

    def test_accepted_append_is_recorded_before_changed_context_rollback(self):
        sync = body(self.actor, "SynchronizeInternal")
        append = sync.index("Bool accepted = CBPCPluginScript.AttachColliderCapsule(")
        remember = sync.index("_accepted[slot] = accepted", append)
        rollback = sync.index("If failed\n    CleanupInternal()", remember)
        self.assertLess(remember, rollback)
        self.assertIn("GetActorReference() != target", sync[remember:rollback])
        self.assertIn("_modelGeneration != synchronizationGeneration", sync[remember:rollback])
        self.assertRegex(sync[rollback:], r"If GetAcceptedLedgerCount\(\) > 0\s+Return SetStatus\(6,")

    def test_model_events_expire_pose_but_preserve_cleanup_ledger(self):
        mark = body(self.actor, "MarkModelGenerationChanged")
        self.assertIn("_modelGeneration += 1", mark)
        self.assertIn("StaticPoseAccepted = False", mark)
        self.assertIn("_generationUnknown = True", mark)
        self.assertNotRegex(mark, r"_accepted\[[^\]]+\]\s*=")
        self.assertNotIn("_tracked = None", mark)
        for name in ("OnLoad", "OnUnload", "OnRaceSwitchComplete"):
            self.assertEqual(body(self.actor, name, "Event").strip(), "MarkModelGenerationChanged()")

    def test_session_load_revokes_native_authority_without_dropping_ledger_or_retry(self):
        revoke = body(self.host, "Revoke")
        self.assertIn("MarkModelGenerationChanged()", revoke)
        self.assertIn("ProviderQualified = False", revoke)
        self.assertIn("ExclusiveIndexRange = False", revoke)
        self.assertLess(revoke.index("ProviderQualified = False"), revoke.index("MarkModelGenerationChanged()"))
        self.assertLess(revoke.index("ExclusiveIndexRange = False"), revoke.index("MarkModelGenerationChanged()"))
        session = body(self.host, "NotifySessionChanged")
        self.assertIn("Revoke(_slots[slot])", session)
        self.assertNotIn("_busy", session)
        self.assertNotRegex(session + revoke, r"Cleanup\(|Clear\(|AcknowledgeProviderReset\(|Synchronize\(")
        relay = source("CLAWPhysicsLoadRelay.psc")
        self.assertIn("host.NotifySessionChanged()", body(relay, "OnPlayerLoadGame", "Event"))

    def test_qualification_binds_evidence_actor_and_generation_not_public_bools_alone(self):
        qualify = body(self.actor, "QualifyForActor")
        for requirement in ("_busy", 'evidence == ""', "expectedActor != GetActorReference()", "expectedGeneration != _modelGeneration"):
            self.assertIn(requirement, qualify)
        self.assertLess(qualify.index("Return False"), qualify.index("ProviderQualified = provider"))
        qualified = body(self.actor, "AttachmentQualified")
        self.assertIn("_qualifiedActor == target", qualified)
        self.assertIn("_qualifiedGeneration == _modelGeneration", qualified)
        self.assertIn("StaticPoseAccepted", qualified)
        sync = body(self.actor, "SynchronizeInternal")
        self.assertIn("!AttachmentQualified(target)", sync)
        self.assertGreaterEqual(sync.count("!AttachmentContextCurrent(target, synchronizationGeneration, node)"), 2)

    def test_unknown_generation_with_ledger_blocks_duplicate_append(self):
        sync = body(self.actor, "SynchronizeInternal")
        gate = re.search(r"If _generationUnknown && GetAcceptedLedgerCount\(\) > 0\s+Return SetStatus\(6,[^\n]+\)\s+EndIf", sync)
        self.assertIsNotNone(gate)
        self.assertLess(gate.end(), sync.index("CBPCPluginScript.AttachColliderCapsule("))

    def test_reset_requires_external_assertion_exact_actor_and_requalified_native_ownership(self):
        reset = body(self.actor, "AcknowledgeProviderReset")
        guard = reset[:reset.index("EnsureLedger()")]
        for requirement in ("_busy", "!ProviderQualified", "!ExclusiveIndexRange", "!previousContainersDiscarded", "previousActor != _tracked"):
            self.assertIn(requirement, guard)
        self.assertIn("Return False", guard)
        host_reset = body(self.host, "AcknowledgeReset")
        self.assertIn('resetEvidence == ""', host_reset)
        self.assertIn("_lastResetEvidence = resetEvidence", host_reset)
        self.assertNotIn("DetachCollider", host_reset)

    def test_host_is_finite_explicit_and_serialized(self):
        init = body(self.host, "Initialize")
        self.assertIn("ActorSlots.Length > 16", init)
        self.assertIn("GetOwningQuest() != Self", init)
        self.assertIn("ActorSlots[other] == ActorSlots[slot]", init)
        self.assertNotRegex(self.host, r"RegisterFor.*Update|Event OnUpdate|Find.*Actor|AttachCollider|StopPhysics|StartPhysics|ReloadConfig")
        for name in ("Assign", "Release", "Qualify", "Pulse"):
            code = body(self.host, name)
            self.assertRegex(code, r"If _busy\s+Return -8\s+EndIf")
            self.assertLess(code.index("_busy = True"), code.index(name + "Internal("))
            self.assertGreater(code.index("_busy = False"), code.index(name + "Internal("))

    def test_opt_in_is_session_scoped_and_never_qualifies_the_provider(self):
        self.assertIn("Bool Property IntegrationOptIn = False Auto", self.host)
        enabled = body(self.host, "IntegrationEnabled")
        self.assertIn("_enabledGeneration == _sessionGeneration", enabled)
        enable = body(self.host, "EnableIntegration")
        for condition in ('evidence == ""', "expectedSessionGeneration != _sessionGeneration", "!IsRunning()"):
            self.assertIn(condition, enable)
        self.assertNotRegex(enable, r"ProviderQualified|ExclusiveIndexRange|StaticPoseAccepted|Synchronize\(")
        for name in ("AssignInternal", "QualifyInternal", "PulseInternal"):
            self.assertRegex(body(self.host, name), r"^\s*If !IntegrationEnabled\(\)\s+Return Fail\(-6,")
        session = body(self.host, "NotifySessionChanged")
        self.assertLess(session.index("IntegrationOptIn = False"), session.index("Revoke(_slots[slot])"))
        self.assertIn("_sessionGeneration += 1", session)
        self.assertNotIn("IntegrationEnabled()", body(self.host, "ReleaseInternal"))

    def test_coordinator_start_is_explicit_and_register_qualify_pulse_remain_separate(self):
        control = source("CLAWPhysicsControl.psc")
        lookup = body(control, "GetHost")
        self.assertIn('Game.GetFormFromFile(0x000800, "CLAW - Physics.esp")', lookup)
        self.assertNotIn("Start()", lookup)
        begin = body(control, "BeginSession")
        self.assertLess(begin.index('!optIn || evidence == ""'), begin.index("host.Start()"))
        self.assertLess(begin.index("host.HasRememberedCapsules()"), begin.index("host.Start()"))
        self.assertNotRegex(begin, r"Assign\(|Qualify\(|Pulse\(|Synchronize\(")
        for function, call in (("RegisterActor", "host.Assign(slot, target)"), ("QualifyActor", "host.Qualify("),
                               ("PulseActor", "host.Pulse(slot, expectedActor)")):
            self.assertIn(call, body(control, function))
        self.assertNotRegex(control, r"Find.*Actor|RegisterFor.*Update|Stop\(|Reset\(|AttachCollider")


if __name__ == "__main__":
    unittest.main()
