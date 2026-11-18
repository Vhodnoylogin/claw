"""Optional reviewed uniform-scale replay; portable symbols remain separate.

Raw game data stays external. An explicit missing/changed selection fails;
without selection the actual class reports a visible skip unless REQUIRED=1.
"""
from pathlib import Path
import copy
import hashlib
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import fsmp_uniform_scale_readback as scale
from test_fsmp_joint_limit_readback import compose,transform

EVIDENCE_ENV='CLAW_FSMP_UNIFORM_SCALE_READBACK_EVIDENCE'
REQUIRED_ENV='CLAW_FSMP_UNIFORM_SCALE_READBACK_REQUIRED'
ARCHIVED_EVIDENCE_SHA256='81fd284e7e1fe54bf030c80831061f10f5852f63effaa8c15ea345c977818fb8'


def read_selected_actual():
    selected=os.environ.get(EVIDENCE_ENV)
    if not selected:
        if os.environ.get(REQUIRED_ENV)=='1':
            raise AssertionError('Required actual uniform-scale evidence missing: set '+EVIDENCE_ENV)
        raise unittest.SkipTest('Optional actual uniform-scale proof not selected; set '+EVIDENCE_ENV)
    payload=Path(selected).expanduser().resolve(strict=True).read_bytes()
    if hashlib.sha256(payload).hexdigest()!=ARCHIVED_EVIDENCE_SHA256:
        raise AssertionError('Explicit actual uniform-scale proof hash differs; new evidence requires review')
    actual=json.loads(payload)
    if actual.get('schema')!='claw-actual-uniform-scale-replay/1' or not {
            'rawPair','finalWitness','restLocal','reference','base','sourceRun','initialUnitObservation','measurementLease'}<=set(actual):
        raise AssertionError('Complete reviewed actual uniform-scale bundle required')
    if not {'worldA','worldB','witnessA','witnessB','matches','limitResult'}<=set(actual['rawPair']):
        raise AssertionError('Complete actual uniform-scale paused pair required')
    return actual


def prepared(actual):
    return {**actual['rawPair'],**{k:actual[k] for k in ('finalWitness','restLocal','reference','base')}}


def associate(value):
    # These are retained actual getter observations, not the requested1.1 literal.
    return scale.pair(value['worldA'],value['worldB'],value['witnessA'],value['witnessB'],
        reference=value['reference'],base=value['base'],rest_local=value['restLocal'],
        getter_a=value['matches']['A']['scaleContext']['getter'],getter_b=value['matches']['B']['scaleContext']['getter'])


def score(value):return scale.score_case(associate(value),value['finalWitness'],value['restLocal'])


def set_joint_translation(value,driver,xyz,*,stages=scale.STAGES,final_only=False):
    """Independent forward corruption using the shared fixture's compose helper.

    Scale the rest pivot, keep proper bases, update min/max and raw paused node
    positions so a wrong joint value reaches the intended functional gate.
    """
    tokens=value['matches']['A']['tokens'];parent=scale.PARENTS[scale.DRIVERS.index(driver)]
    observed=value['matches']['A']['scaleContext']['roles'][driver]['world']
    rest=copy.deepcopy(value['restLocal'][driver]);rest['translation']=[observed*x for x in rest['translation']]
    for name in (('finalWitness',) if final_only else ('witnessA','witnessB','finalWitness')):
        objects={o['token']:o for o in value[name]['sample']['objectWindow']['objects']};obj=objects[tokens[driver]]
        for stage in stages:
            pose=objects[tokens[parent]][stage]['world']
            frame=compose(compose(transform(pose[9:],pose[:9]),transform(xyz)),rest)
            obj[stage]['world']=frame['rotationRowMajor']+frame['translation']
        poses=[obj[stage]['world'] for stage in scale.STAGES]
        obj['minimumPostWorld']=[min(p[i] for p in poses) for i in range(12)]
        obj['maximumPostWorld']=[max(p[i] for p in poses) for i in range(12)]
        if name in ('witnessA','witnessB'):
            raw=value['worldA' if name=='witnessA' else 'worldB'];pose=obj['lastPost']['world']
            node=next(n for n in raw['nodes'] if n['name']==driver)
            node['world']=transform(pose[9:],pose[:9],observed)


class ExplicitActualUniformScaleReadback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.actual=read_selected_actual()

    def test_actual_paused_and_completed900_replay(self):
        value=prepared(self.actual);before=copy.deepcopy(value)
        with patch.object(scale.cached,'module_admission',side_effect=AssertionError('Historical module admission must not run')):
            associated=associate(value)
            self.assertEqual(associated,self.actual['rawPair']['matches'])
            self.assertEqual(scale.score_limit(associated),self.actual['rawPair']['limitResult'])
            result=scale.score_case(associated,value['finalWitness'],value['restLocal'])
        self.assertEqual(value,before);self.assertEqual(result['status'],'uniform-scale-mass-and-linear-limit-correspondence-observed')
        self.assertEqual(value['finalWitness']['sample']['objectWindow']['pairedSteps'],900)
        self.assertEqual(len(set(associated['A']['tokens'].values())),4)
        for stage in scale.STAGES:
            for index,driver in enumerate(scale.DRIVERS):
                row=result['completed900Coordinates'][stage][driver]
                self.assertAlmostEqual(row['qWorld'][0],.05*row['observedWorldScale'] if index==0 else 0.,delta=scale.WORLD_TOLERANCE)
                self.assertAlmostEqual(row['actualInverseMass'],20/row['observedWorldScale']**3,delta=scale.MASS_TOLERANCE)

    def test_retained_observations_reconstruct_measurement_lease(self):
        actual=self.actual;unit=actual['initialUnitObservation'];lease=actual['measurementLease'];a,b=lease['observations'][-2:]
        initial=unit['parsedFresh']
        self.assertAlmostEqual(unit['getter'],1.,delta=scale.SCALE_TOLERANCE)
        parsed_a=scale.probe.snapshot(a['raw'],actual['reference'],'female');parsed_b=scale.probe.snapshot(b['raw'],actual['reference'],'female')
        # ACK was checked by the accepted callback; this pure replay checks its retained observation barrier.
        rebuilt=scale.establish_measurement(initial,parsed_a,a['getter'],parsed_b,b['getter'],acknowledged=True)
        self.assertEqual(rebuilt,{'guard':lease['guard'],'scaleContext':lease['scaleContext']})
        with self.assertRaisesRegex(ValueError,'ACK'):
            scale.establish_measurement(initial,parsed_a,a['getter'],parsed_b,b['getter'],acknowledged=False)

    def test_actual_unscaled_mass_refused(self):
        value=prepared(copy.deepcopy(self.actual));token=value['matches']['A']['tokens'][scale.DRIVERS[0]]
        for name in ('witnessA','witnessB','finalWitness'):
            obj=next(o for o in value[name]['sample']['objectWindow']['objects'] if o['token']==token)
            for stage in scale.STAGES:obj[stage]['inverseMass']=20.
        with self.assertRaisesRegex(ValueError,'inverse mass'):score(value)

    def test_actual_unscaled_lower_limit_refused(self):
        value=prepared(copy.deepcopy(self.actual));set_joint_translation(value,scale.DRIVERS[0],(.05,0.,0.))
        with self.assertRaisesRegex(ValueError,'Scaled positive'):score(value)

    def test_actual_right_drift_inside_endpoint_gate_refused(self):
        value=prepared(copy.deepcopy(self.actual))
        set_joint_translation(value,scale.DRIVERS[1],(-.0014,0.,0.),stages=('initialPre',),final_only=True)
        set_joint_translation(value,scale.DRIVERS[1],(.0014,0.,0.),stages=('lastPre','lastPost'),final_only=True)
        with self.assertRaisesRegex(ValueError,'Bilateral scaled window was not settled'):score(value)

    def test_actual_wrong_base_scale_root_and_stale_samples_refused(self):
        for kind in ('base','worldScale','getter','root','sample','pid','nonce'):
            value=prepared(copy.deepcopy(self.actual))
            if kind=='base':value['base']='0x0D000803'
            elif kind=='worldScale':next(n for n in value['worldB']['nodes'] if n['name']==scale.DRIVERS[0])['world']['scale']=1.05
            elif kind=='getter':value['matches']['B']['scaleContext']['getter']=1.
            elif kind=='root':value['worldB']['refs'][0]['rootIdentity']['sampledRootToken']+=1
            elif kind=='sample':value['worldB']['sampleId']=value['worldA']['sampleId']
            elif kind=='pid':value['witnessB']['pid']+=1
            else:value['finalWitness']['sample']['objectWindow']['nonce']+=1
            with self.subTest(kind=kind),self.assertRaises(ValueError):score(value)


class ExplicitUniformScaleSelectionContract(unittest.TestCase):
    def test_unset_optional_skips_and_required_unset_fails(self):
        for required,error in (('',unittest.SkipTest),('1',AssertionError)):
            with self.subTest(required=required),patch.dict(os.environ,{EVIDENCE_ENV:'',REQUIRED_ENV:required}),self.assertRaises(error):
                read_selected_actual()

    def test_selected_missing_or_wrong_digest_fails(self):
        repo=Path(__file__).resolve().parents[4];target=(repo/'target/test-inputs/fsmp-uniform-scale').resolve()
        self.assertTrue(target.is_relative_to((repo/'target').resolve()));target.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='selection-',dir=target) as directory:
            path=Path(directory).resolve();self.assertTrue(path.is_relative_to(target));missing=path/'missing.json'
            with patch.dict(os.environ,{EVIDENCE_ENV:str(missing)}),self.assertRaises(FileNotFoundError):read_selected_actual()
            damaged=path/'damaged.json';damaged.write_text('{}',encoding='utf-8')
            with patch.dict(os.environ,{EVIDENCE_ENV:str(damaged)}),self.assertRaisesRegex(AssertionError,'hash differs'):read_selected_actual()


if __name__=='__main__':unittest.main()
