"""Bridge failure-path regressions; engine/provider execution is separate."""
from pathlib import Path
import hashlib
import importlib.util
import json
import unittest

ROOT = (Path(__file__).resolve().parents[4] / 'src/main/python/physics')
spec = importlib.util.spec_from_file_location('claw_auto_build', ROOT/'build.py')
build = importlib.util.module_from_spec(spec); spec.loader.exec_module(build)

def model():
    node = build.NODES[0]
    result = {'schemaVersion':3, 'frame':'node-local-game-units', 'domain':[0,1],
              'evaluator':'deform-actual-normalized-rest-LBS-support-then-PCA-refit-v1', 'morphs':['CLAWHeadEarSize'],
              'slots':[{'node':node, 'male':{'partitionIndices':[0,1]}, 'female':{'partitionIndices':[0,1]}}],
              'regions':{sex+'/'+node:{'points':[[0,0,0],[0,1,0]],'deltas':{}} for sex in ('male','female')}}
    canonical = json.dumps({k:result[k] for k in ('evaluator','morphs','regions','slots')}, sort_keys=True,separators=(',',':')).encode()
    result['modelIdentity'] = 'CLAW.Physics.CurrentVector.' + hashlib.sha256(canonical).hexdigest()
    return result

class AutomaticObserverTests(unittest.TestCase):
    def test_female_p1_slots_keep_indices_without_a_fabricated_male_capsule(self):
        fit = model(); node = build.BREAST_NODES[0]
        fit['slots'].append({'node':node,'sexMask':'female','male':None,'female':{'partitionIndices':[0,1]}})
        fit['regions']['female/'+node] = {'points':[[0,0,0],[0,1,0]],'deltas':{}}
        canonical = json.dumps({k:fit[k] for k in ('evaluator','morphs','regions','slots')},sort_keys=True,separators=(',',':')).encode()
        fit['modelIdentity'] = 'CLAW.Physics.CurrentVector.'+hashlib.sha256(canonical).hexdigest()
        build.validate_fitted_model(fit)
        self.assertEqual(build.expected_capsule_count_for_sex(fit,'male'),1)
        self.assertEqual(build.expected_capsule_count_for_sex(fit,'female'),2)
        data = build.render_data(json.loads((ROOT/'recipe.json').read_text()),json.loads((ROOT/'capsules.json').read_text()),fit)
        self.assertIn('If !female && (slot == 1)',data)
        self.assertIn('Return 1129054208 + slot',data)

    def test_current_vector_identity_pins_support_data_and_cannot_fall_back_to_affine(self):
        fit = model(); build.validate_fitted_model(fit)
        recipe = json.loads((ROOT/'recipe.json').read_text()); capsules = json.loads((ROOT/'capsules.json').read_text())
        data = build.render_data(recipe,capsules,fit)
        self.assertIn('Bool Function NativeFitRequired() Global\n  Return True',data)
        self.assertIn(fit['modelIdentity'],data)
        self.assertIn('Return None\nEndFunction',data)
        self.assertIn('Return -1.0\nEndFunction',data)
        fit['regions']['male/'+build.NODES[0]]['points'][0][0] = 1
        with self.assertRaisesRegex(ValueError,'identity differs'): build.validate_fitted_model(fit)

    def test_native_cleanup_keeps_identity_check_during_snapshot_invalidation(self):
        actor = (ROOT/'papyrus/CLAWPhysicsActor.psc').read_text()
        cleanup = actor.split('Bool Function CleanupContextCurrent',1)[1].split('EndFunction',1)[0]
        self.assertIn('_nativeOwner && !CLAWPhysicsNative.ActorCurrent(target)',cleanup)
        generation = actor.split('Function MarkModelGenerationChanged()',1)[1].split('EndFunction',1)[0]
        self.assertNotIn('_nativeOwner = False',generation)
        self.assertIn('_nativeSnapshot = False',generation)
        sync = actor.split('Int Function SynchronizeObservedMorphs(',1)[1].split('EndFunction',1)[0]
        self.assertIn('CLAWPhysicsData.NativeFitRequired() && !nativeSnapshot',sync)

    def test_native_observer_reads_provider_aggregate_and_never_papyrus_key_sum(self):
        plugin = (ROOT.parents[3]/'src/main/cpp/src/Plugin.cpp').read_text()
        observe = plugin.split('void observePhysics(RE::Actor* actor, bool retryPose) {',1)[1].split('bool readback(',1)[0]
        self.assertIn('morphs->GetBodyMorphs',observe)
        self.assertIn('morphs->ApplyBodyMorphs(skeeReference(actor), false)',observe)
        self.assertNotIn('morphs->GetMorph(',observe)
        self.assertIn('binding.pointer != actor',observe)
        host = (ROOT/'papyrus/CLAWPhysicsHost.psc').read_text()
        self.assertIn('ElseIf outcome == 6',host)
        self.assertIn('If outcome == 4\n      If kind == "pose"',host)
        self.assertIn('AcknowledgePoseSnapshot(target, generation, token, helper.UsedPoseDelta(token))',host)
        self.assertIn('Else\n        CLAWPhysicsNative.AcknowledgeSnapshot(target, generation, token)',host)
        self.assertIn('Function OnPhysicsCandidate(',host)
        self.assertIn('helper.GetTrackedActor() == None && helper.GetAcceptedLedgerCount() == 0',host)
        self.assertIn('physicsPopulationBlocked',plugin)
        self.assertNotIn('SetWeight(',plugin)
        self.assertIn('binding.observation.publishedWeight != job.weight',plugin)

    def test_pose_retry_is_separate_from_capture_and_rechecks_observation(self):
        plugin = (ROOT.parents[3]/'src/main/cpp/src/Plugin.cpp').read_text()
        scan = plugin.split('void queuePhysicsPoseScan() {', 1)[1].split('void queueActor(', 1)[0]
        self.assertIn('visitOne(deliveryCursor, true);', scan)
        self.assertIn('visitOne(captureCursor, false);', scan)
        self.assertIn('retry ? binding.delivered || !binding.poseBaseSnapshot : !binding.delivered', scan)
        self.assertIn('if (retry) observePhysics(actor.get(), true);', scan)
        self.assertIn('(retryPose || !binding.poseBaseSnapshot)', plugin)

    def test_expired_pose_fit_does_not_replace_acknowledged_capsules(self):
        plugin = (ROOT.parents[3]/'src/main/cpp/src/Plugin.cpp').read_text()
        result = plugin.split('void startPhysicsWorker() {', 1)[1].split('void queuePhysicsFit(', 1)[0]
        expires = result.index('now() - job.pose->captured > maxQueuedPoseAge)) return;')
        self.assertLess(result.index('binding.fitPending = false;'), expires)
        self.assertLess(expires, result.index('binding.capsules[slot] = capsules[i];'))
        self.assertLess(expires, result.index('publishPhysics(actor, binding, job.poseBaseSnapshot'))

    def test_pose_trace_is_staged_before_dispatched_and_consumed_at_first_current_ack(self):
        plugin = (ROOT.parents[3]/'src/main/cpp/src/Plugin.cpp').read_text()
        publish = plugin.split('void publishPhysics(', 1)[1].split('RE::NiAVObject* physicsActorRoot', 1)[0]
        self.assertLess(publish.index('binding.snapshot = nextPhysicsSnapshot++'), publish.index('binding.poseReceipt.emplace'))
        self.assertLess(publish.index('binding.poseReceipt.emplace'), publish.index('signalPhysicsSnapshot'))
        ack = plugin.split('void acknowledgePhysicsSnapshot(', 1)[1].split('void physicsAcknowledge(', 1)[0]
        self.assertLess(ack.index('if (!physicsSnapshot('), ack.index('if (binding.delivered'))
        self.assertLess(ack.index('if (binding.delivered'), ack.index('std::exchange(binding.poseReceipt'))
        self.assertIn('poseDelta.has_value() || !binding.poseBaseSnapshot', ack)

    def test_manual_intent_blocks_offer_and_claim_then_task_repeats_revocation(self):
        plugin = (ROOT.parents[3]/'src/main/cpp/src/Plugin.cpp').read_text()
        offer = plugin.split('void offerSourceBootstrap(RE::Actor* actor) {',1)[1].split('void publishPhysics(',1)[0]
        self.assertIn('if (pendingActorRequest(actor)) return;',offer)
        cached = plugin.split('State* sourceCandidateCached(',1)[1].split('bool enableOBodySourcePopulation(',1)[0]
        self.assertIn('sourcePolicyAllows(state, actor)',cached)
        queued = plugin.split('tasks->AddTask([id, owner = std::move(owner)',1)[1].split('if (operation == Operation::assign) {',1)[0]
        self.assertLess(queued.index('stateFor(target, true, false)'), queued.index('revokeSourceBootstrap(*state)'))
        self.assertIn('state->adoptedDefault = false',queued)
        saved = plugin.split('void save(SKSE::SerializationInterface*',1)[1].split('void revert(',1)[0]
        self.assertNotIn('sourceToken',saved)
        self.assertNotIn('adoptedDefault',saved)

    def test_source_bootstrap_requires_actual_public_readiness_and_internal_generation(self):
        plugin = (ROOT.parents[3]/'src/main/cpp/src/Plugin.cpp').read_text()
        ready = plugin.split('bool sourceProviderReady()',1)[1].split('std::map<RE::FormID',1)[0]
        self.assertIn('obodyApiReady.load()',ready)
        self.assertIn('obodyStockGenerationEpoch.load() == obodyProviderEpoch.load()',ready)
        self.assertIn('payload.responsiblePluginInterface == nullptr',plugin)
        self.assertIn('request.readinessEventListener = &obodyReadiness',plugin)
        self.assertIn('morphs->HasBodyMorphName',plugin)
        self.assertNotIn('SetDistributionKey(',plugin)

if __name__ == '__main__': unittest.main()
