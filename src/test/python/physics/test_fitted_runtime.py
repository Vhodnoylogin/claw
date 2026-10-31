"""Fitted capsule input and actor lifecycle regressions; no engine calls."""
from pathlib import Path
import copy
import importlib.util
import json
import tempfile
import unittest
from unittest.mock import patch
import re

ROOT=(Path(__file__).resolve().parents[4] / 'src/main/python/physics')
spec=importlib.util.spec_from_file_location('claw_fitted_build',ROOT/'build.py')
build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)

def fixture(bundle=False):
    row={'base':{'p1':[0,0,0],'p2':[0,2,0],'radius':2.0},
         'coefficients':{'CLAWHeadEarSize':{'p1':[0,0,0],'p2':[0,1,0],'radius':-0.5}}}
    model={'schemaVersion':2 if bundle else 1,'frame':'node-local-game-units','domain':[0,1],
           'morphs':['CLAWHeadEarSize']}
    if bundle:
        model['slots']=[{'node':node,'male':copy.deepcopy(row),'female':copy.deepcopy(row)}
                        for node in build.NODES if node!='TailBone04']
        model['slots'].insert(1,copy.deepcopy(model['slots'][0]))
    else:
        for sex in ('male','female'):
            model[sex]={node:copy.deepcopy(row) if node!='TailBone04' else None for node in build.NODES}
    return model

def function(source,name):
    m=re.search(r'(?m)^.*\bFunction '+name+r'\([^\n]*\)[^\n]*\n',source)
    assert m,name
    return source[m.end():].split('EndFunction',1)[0]

class FittedRuntimeTests(unittest.TestCase):
    def test_bundle_repeated_nodes_keep_separate_stable_indices_and_slotcount(self):
        model=fixture(True);build.validate_fitted_model(model)
        self.assertEqual(build.capsule_slot_count(model),9)
        self.assertEqual(build.expected_capsule_count(model),9)
        self.assertEqual(build.data_nodes(model)[:2],(build.NODES[0],)*2)
        recipe=json.loads((ROOT/'recipe.json').read_bytes());capsules=json.loads((ROOT/'capsules.json').read_bytes())
        data=build.render_data(recipe,capsules,model)
        self.assertIn('Return 9',function(data,'SlotCount'))
        self.assertIn('Return 1129054208 + slot',function(data,'ColliderIndex'))
        self.assertNotIn('slot != 7',function(data,'HasCapsule'))
        self.assertEqual(function(data,'Node').count('Return "'+build.NODES[0]+'"'),2)

    def test_fitted_shrink_coefficient_and_exact_radius_are_not_halved_or_clamped(self):
        model=fixture();build.validate_fitted_model(model)
        recipe=json.loads((ROOT/'recipe.json').read_bytes());capsules=json.loads((ROOT/'capsules.json').read_bytes())
        data=build.render_data(recipe,capsules,model)
        self.assertIn('Return 2.000000',function(data,'Radius'))
        self.assertIn('result += -0.500000000 * values[0]',function(data,'RadiusForMorphs'))
        self.assertIn('result[1] += 1.000000000 * values[0]',function(data,'PointForMorphs'))
        valid=function(data,'MorphValuesValidCopy')
        self.assertIn('!(values[index] >= 0.0 && values[index] <= 1.0)',valid)
        self.assertNotIn('Clamp',valid)

    def test_invalid_fit_domain_layout_and_internal_radius_refused(self):
        for change in ('range','nonfinite','zero-radius','wrongnode','onesex','duplicate-name','too-many'):
            with self.subTest(change=change):
                model=fixture(True)
                if change=='range':model['domain']=[-1,1]
                if change=='nonfinite':model['slots'][0]['male']['base']['p1'][0]=float('nan')
                if change=='zero-radius':model['slots'][0]['male']['coefficients']['CLAWHeadEarSize']['radius']=-3
                if change=='wrongnode':model['slots'][0]['node']='NPC Root [Root]'
                if change=='onesex':model['slots'][0]['female']=None
                if change=='duplicate-name':model['morphs']*=2
                if change=='too-many':model['slots']*=4
                with self.assertRaises(ValueError):build.validate_fitted_model(model)

    def test_consumed_fit_mutation_cannot_get_success_receipt(self):
        recipe=json.loads((ROOT/'recipe.json').read_bytes());capsules=json.loads((ROOT/'capsules.json').read_bytes())
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'fit.json';path.write_text(json.dumps(fixture()))
            fitted=build.fitted_model(path)
            original=build.render_motion
            def change(recipe):
                rendered=original(recipe);path.write_text(json.dumps(fixture())+' ');return rendered
            with patch.object(build,'render_motion',side_effect=change),self.assertRaisesRegex(ValueError,'changed after consumption'):
                build.build(root/'out',recipe,capsules,fitted=fitted)
            self.assertTrue((root/'out/FAILED-unverified-do-not-install').exists())
            self.assertFalse((root/'out/claw-physics-source.json').exists())

    def test_actor_refresh_cleans_old_indices_before_reappend_and_same_values_skip(self):
        actor=(ROOT/'papyrus/CLAWPhysicsActor.psc').read_text()
        sync=function(actor,'SynchronizeInternal')
        self.assertIn('GetAcceptedLedgerCount() == CLAWPhysicsData.ExpectedCapsuleCountForSex(female) && !_morphRefresh',sync)
        self.assertLess(sync.index('If GetAcceptedLedgerCount() > 0\n    CleanupInternal()'),sync.index('AttachColliderCapsule('))
        self.assertGreater(sync.index('_morphRefresh = False'),sync.index('If failed'))
        pulse=function(actor,'SynchronizeMorphs')
        self.assertLess(pulse.index('Int snapshotGeneration'),pulse.index('prepared[index] = values[index]'))
        self.assertIn('snapshotGeneration != _modelGeneration',pulse)
        self.assertIn('_morphValues = prepared',pulse)
        self.assertIn('_morphRefresh = _morphRefresh || changed',pulse)
        self.assertNotIn('AttachColliderCapsule',pulse)
        self.assertIn('_morphValuesQualified = False',function(actor,'MarkModelGenerationChanged'))

    def test_model_changes_cannot_hide_saved_slots_or_detach_new_layout(self):
        actor=(ROOT/'papyrus/CLAWPhysicsActor.psc').read_text()
        self.assertIn('While slot < _accepted.Length',function(actor,'GetAcceptedLedgerCount'))
        self.assertNotIn('EnsureLedger()',function(actor,'GetAcceptedLedgerCount'))
        cleanup=function(actor,'CleanupInternal')
        self.assertLess(cleanup.index('_acceptedModel != CLAWPhysicsData.ModelIdentity()'),cleanup.index('DetachCollider('))
        sync=function(actor,'SynchronizeInternal')
        self.assertLess(sync.index('_acceptedModel != CLAWPhysicsData.ModelIdentity()'),sync.index('AttachColliderCapsule('))
        migrate=sync[sync.index('If _accepted.Length < CLAWPhysicsData.SlotCount()'):sync.index('_tracked = target')]
        self.assertLess(migrate.index('If GetAcceptedLedgerCount() > 0'),migrate.index('_accepted = new Bool[128]'))
        self.assertIn('Return SetStatus(6,',migrate)

if __name__=='__main__':unittest.main()
