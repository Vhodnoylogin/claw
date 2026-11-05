"""Safety contracts in actual PSC source; no Papyrus/CBPC event execution claimed.

These checks guard the failure paths that compilation alone cannot establish.
They deliberately inspect the shipped source instead of a Python lifecycle copy.
Engine event delivery, stack scheduling and native results still need game tests.
"""
from pathlib import Path
import re
import unittest

ROOT = (Path(__file__).resolve().parents[4] / 'src/main/python/physics') / "papyrus"


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
        recheck = sync.rindex("If failed || !AttachmentContextCurrent(target, synchronizationGeneration, node)", 0, append)
        for read in ("CBPCPluginScript.DetachCollider(", "CLAWPhysicsData.Point(slot, female, False)",
                     "CLAWPhysicsData.Point(slot, female, True)", "CLAWPhysicsData.Radius(slot, female)"):
            self.assertLess(sync.index(read), recheck)
        self.assertRegex(sync[recheck:append], r"^If failed \|\| !AttachmentContextCurrent\(target, synchronizationGeneration, node\)\s+failed = True\s+Else\s+$")
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

    def test_every_native_retirement_passes_the_required_session_explicitly(self):
        # The Papyrus API's empty default cannot retire any native binding: the
        # C++ boundary rejects it before erasing even an inactive/empty binding.
        native = source("CLAWPhysicsNative.psc")
        self.assertIn('String expectedSession = ""', native)
        plugin = (ROOT.parents[2] / "cpp/src/Plugin.cpp").read_text()
        unregister = plugin.split("void physicsUnregister(", 1)[1].split("bool physicsActorCurrent", 1)[0]
        self.assertLess(unregister.index("!physicsSessionMatches(expectedSession.c_str())"),
                        unregister.index("physicsBindings.erase(found)"))
        calls = re.findall(r"CLAWPhysicsNative\.UnregisterActor\(([^\n]+)\)", self.host)
        self.assertEqual(len(calls), 2)
        for call in calls:
            self.assertEqual(len(call.split(",")), 3, call)
            self.assertEqual(call.split(",")[-1].strip(), "expectedRuntime")

    def test_alias_retirement_keeps_captured_owner_until_empty_ledger_and_same_session(self):
        remember = body(self.host, "RememberNativeRetirement")
        self.assertLess(remember.index("If _retirementPending[index]"),
                        remember.index("Actor previousNativeActor = helper.GetQualifiedActor()"))
        for field in ("_retirementActors[index] = previousNativeActor",
                      "_retirementRuntime[index] = expectedRuntime",
                      "_retirementPending[index] = True"):
            self.assertIn(field, remember)
        withdraw = body(self.host, "DisableAutomaticForRuntime")
        capture = withdraw.index("RememberNativeRetirement(index, helper, expectedRuntime)")
        self.assertLess(capture, withdraw.index("_automatic[index] = False"))
        self.assertIn("Bool nativeOwner = _retirementPending[index]", withdraw)
        self.assertIn("Actor target = _retirementActors[index]", withdraw)
        self.assertIn("expectedRuntime = _retirementRuntime[index]", withdraw)

        retirement = body(self.host, "CompleteNativeRetirement")
        call = retirement.index("UnregisterActor(previousNativeActor, False, expectedRuntime)")
        self.assertIn("Actor previousNativeActor = _retirementActors[index]", retirement[:call])
        self.assertIn("String expectedRuntime = _retirementRuntime[index]", retirement[:call])
        self.assertIn("helper.GetAcceptedLedgerCount() > 0", retirement[:call])
        for fragment in (retirement[:call], retirement[call:]):
            self.assertIn("!RuntimeCurrent(expectedRuntime)", fragment)
            self.assertIn("Return False", fragment)
        self.assertLess(call, retirement.index("_retirementPending[index] = False"))

        for name in ("AssignInternal", "ReleaseInternal"):
            with self.subTest(function=name):
                code = body(self.host, name)
                withdraw = code.index("DisableAutomaticForRuntime(index, expectedRuntime)")
                cleanup = code.index("helper.Cleanup()")
                complete = code.index("If !CompleteNativeRetirement(index, helper)")
                clear = code.index("helper.Clear()")
                self.assertLess(code.index("String expectedRuntime = _runtimeSession"), withdraw)
                self.assertIn("expectedRuntime = _retirementRuntime[index]", code[:withdraw])
                self.assertLess(withdraw, cleanup)
                self.assertLess(code.index("cleanup == 8 || helper.GetAcceptedLedgerCount() > 0"), complete)
                self.assertLess(complete, code.index("Revoke(helper)"))
                self.assertLess(complete, clear)
                self.assertRegex(code[complete:clear], r"If !CompleteNativeRetirement\(index, helper\)\s+Return Fail\(-6,")
                self.assertNotRegex(code, r"GetSessionToken\(|BeginSessionToken\(|AcknowledgeProviderReset\(")

    def test_cleanup_cleared_owner_cannot_bypass_pending_retirement_on_retry_or_regrant(self):
        # Cleanup clears _nativeOwner after the last accepted capsule is removed.
        # The Host must therefore retain its OWN exact actor/session across calls.
        cleanup = body(self.actor, "CleanupInternal")
        self.assertIn("_nativeOwner = False", cleanup)
        remember = body(self.host, "RememberNativeRetirement")
        gate = re.search(r"If _retirementPending\[index\] \|\| .*?\s+Return\s+EndIf", remember)
        self.assertIsNotNone(gate)
        self.assertLess(gate.end(), remember.index("_retirementActors[index] ="))
        # Only the guarded successful request path may clear persistent context.
        self.assertEqual(self.host.count("_retirementPending[index] = False"), 1)
        complete = body(self.host, "CompleteNativeRetirement")
        self.assertNotIn("HasNativeOwner", complete)
        self.assertNotIn("_automatic[index]", complete)
        self.assertNotIn("_runtimeSession", complete)
        register = body(self.host, "RegisterAutomatic")
        self.assertIn("If _retirementPending[index] ||", register)
        enable = body(self.host, "EnableAutomaticInternal")
        self.assertLess(enable.index("CompleteNativeRetirement(index, helper)"),
                        enable.index("helper.QualifyForActor("))
        for name, mutation in (("QualifyInternal", "helper.QualifyForActor("),
                               ("PulseInternal", "helper.Synchronize()"),
                               ("PulseMorphsInternal", "helper.SynchronizeMorphs(")):
            code = body(self.host, name)
            self.assertLess(code.index("If _retirementPending[index]"), code.index(mutation))
        self.assertIn("_retirementPending[slot] ||", body(self.host, "HasRememberedCapsules"))
        self.assertIn("_retirementActors[slot] == target", body(self.host, "ActorInOtherSlot"))
        # Session notifications and automatic-array migrations do not erase or
        # replace a pending token, even when a fresh integration session begins.
        for name in ("NotifySessionChanged", "EnableIntegration", "EnsureAutomaticArrays"):
            self.assertNotRegex(body(self.host, name), r"_retirement(?:Pending|Actors|Runtime).*=")

    def test_empty_suspend_retires_with_explicit_end_token_without_trapping_old_integration(self):
        notification = body(self.host, "NotifySessionChanged")
        self.assertIn("retirementRuntime = CLAWPhysicsNative.EndSession(previousRuntime)", notification)
        self.assertIn("DisableAutomaticForRuntime(slot, retirementRuntime)", notification)
        withdrawal = body(self.host, "DisableAutomaticForRuntime")
        self.assertRegex(withdrawal, r"If helper.GetAcceptedLedgerCount\(\) > 0\s+CLAWPhysicsNative.UnregisterActor\(target, True, expectedRuntime\)\s+Else\s+CompleteNativeRetirement\(index, helper\)\s+EndIf")
        completion = body(self.host, "CompleteNativeRetirement")
        # The stored EndSession return token may be current while the Host still
        # caches the former integration token. That normal empty path must work.
        self.assertNotIn("_runtimeSession", completion)
        self.assertEqual(completion.count("!RuntimeCurrent(expectedRuntime)"), 3)
        self.assertIn("String expectedRuntime = _retirementRuntime[index]", completion)
        # An already-pending A token is never replaced with new EndSession B.
        remember = body(self.host, "RememberNativeRetirement")
        self.assertLess(remember.index("If _retirementPending[index]"),
                        remember.index("_retirementRuntime[index] = expectedRuntime"))

    def test_completed_empty_withdrawal_clears_superseded_helper_owner_before_pending_context(self):
        completion = body(self.host, "CompleteNativeRetirement")
        request = completion.index("UnregisterActor(previousNativeActor, False, expectedRuntime)")
        local_clear = completion.index("If !helper.ClearRetiredNativeObservation(previousNativeActor)")
        forget = completion.index("_retirementPending[index] = False")
        self.assertLess(request, local_clear)
        self.assertLess(local_clear, forget)
        for fragment in (completion[request:local_clear], completion[local_clear:forget]):
            self.assertIn("If !RuntimeCurrent(expectedRuntime)", fragment)
            self.assertIn("Return False", fragment)
        self.assertRegex(completion[local_clear:forget], r"If !helper.ClearRetiredNativeObservation\(previousNativeActor\)\s+Return False\s+EndIf")
        # Compose the actual source branches: empty Suspend completes this call;
        # Remember's ONLY owner sources on a following Release/Suspend are the
        # now-false Host automatic flag and the cleared helper native owner.
        withdraw = body(self.host, "DisableAutomaticForRuntime")
        self.assertLess(withdraw.index("_automatic[index] = False"),
                        withdraw.index("CompleteNativeRetirement(index, helper)"))
        remember = body(self.host, "RememberNativeRetirement")
        self.assertRegex(remember, r"If _retirementPending\[index\] \|\| \(!_automatic\[index\] && !helper.HasNativeOwner\(\)\)\s+Return")
        clear = body(self.actor, "ClearRetiredNativeObservation")
        self.assertLess(clear.index("_nativeOwner = False"), clear.index("Return True"))
        self.assertIn("Return _nativeOwner", body(self.actor, "HasNativeOwner"))
        self.assertNotRegex(body(self.actor, "MarkModelGenerationChanged") + body(self.host, "Revoke"),
                            r"_nativeOwner\s*=\s*True")

    def test_local_observation_retirement_is_idempotent_serialized_and_not_provider_acknowledgment(self):
        clear = body(self.actor, "ClearRetiredNativeObservation")
        self.assertRegex(clear, r"If _busy\s+Return False\s+EndIf\s+_busy = True")
        self.assertIn("Actor previousOwner = _qualifiedActor", clear)
        self.assertRegex(clear, r"If previousOwner == None\s+previousOwner = GetActorReference\(\)\s+EndIf")
        self.assertRegex(clear, r"If previousActor == None \|\| previousOwner != previousActor \|\| GetAcceptedLedgerCount\(\) > 0\s+_busy = False\s+Return False\s+EndIf")
        guard = clear[:clear.index("_nativeOwner = False")]
        self.assertNotIn("If !_nativeOwner", guard)
        self.assertNotIn("If _nativeOwner", guard)
        self.assertNotIn("_tracked", clear)
        for assignment in ("_nativeOwner = False", "_nativeSnapshot = False", "_nativeToken = 0", "_nativeWeight = -1.0"):
            self.assertIn(assignment, clear)
        self.assertRegex(clear, r"_busy = False\s+Return True\s*$")
        self.assertNotRegex(clear, r"(?:ProviderQualified|ExclusiveIndexRange|StaticPoseAccepted|_qualifiedActor|_qualifiedGeneration|_modelGeneration|_accepted|_tracked)\s*=")
        self.assertNotRegex(clear, r"CLAWPhysicsNative\.|CBPCPluginScript\.|AcknowledgeProviderReset|SetStatus\(")

    def test_retirement_array_migration_never_rebuilds_partially_saved_context(self):
        arrays = body(self.host, "EnsureRetirementArrays")
        self.assertRegex(arrays, r"If _retirementPending == None && _retirementActors == None && _retirementRuntime == None")
        self.assertEqual(arrays.count("new "), 3)
        self.assertIn("_retirementPending.Length == 16", arrays)
        self.assertLess(body(self.host, "Initialize").index("EnsureRetirementArrays()"),
                        body(self.host, "Initialize").index("If _slots != None"))

if __name__ == "__main__":
    unittest.main()
