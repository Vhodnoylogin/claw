"""Synthetic algorithm tests only; none is actual CBPC/game evidence."""
import copy
import math
import os
from pathlib import Path
import struct
import sys
import unittest

HERE=Path(__file__).resolve().parents[4]
REFERENCE=Path(os.environ.get('CLAW_NOMINAL_REFERENCE_ROOT',str(HERE)))
sys.path.insert(0,str(REFERENCE/'src/test/python/integration'))
sys.path.insert(0,str(HERE/'src/test/python/integration'))
import cbpc_nominal as nominal

I=[1.,0.,0.,0.,1.,0.,0.,0.,1.]
REF='0x0D000900'
PINS={'synthetic':'unit-fixture-not-provider-evidence'}
def f32(x):return struct.unpack('<f',struct.pack('<f',x))[0]
def tx(position):return {'translation':list(map(f32,position)),'rotationRowMajor':I[:],'scale':1.}


def fixture(*,noise_off=0.,weak_node=None,off_pose=0.):
    sex='female';names=nominal.scene.node_names(sex)
    parents={n:p[0] for n,p in nominal.hierarchy.parent_paths(sex).items()}
    tree={'NPC Head [Head]':'NPC Spine2 [Spn2]','Tails':'NPC Pelvis [Pelv]',
          'NPC L PreBreast P1':'NPC Spine2 [Spn2]','NPC R PreBreast P1':'NPC Spine2 [Spn2]'}
    tree.update(parents)
    for i in range(1,5):tree[f'CME TailBone{i:02}']=f'TailBone{i:02}'
    identity={'form':REF,'loadGeneration':1,'runtimeHandle':8}
    root={'firstPerson':False,'identityBasis':'sampled_pointer_and_handle_changes_no_object_retention','sampledRootToken':1}
    sample=0;now=0
    def raw(position,amplitude=0.,index=0,dt=.02,pose=0.):
        nonlocal sample,now
        sample+=1;now+=round(dt*1e9)
        local={name:[0.,0.,0.] for name in names}
        for name in parents:
            a=0. if name==weak_node else amplitude
            local[name]=[f32(pose+a*math.sin(index*.71)),0.,0.]
        world={}
        def locate(name):
            if name not in world:
                parent=tree.get(name)
                origin=locate(parent) if parent else position
                world[name]=[f32(a+b) for a,b in zip(origin,local[name])]
            return world[name]
        rows=[{'form':REF,'name':name,'firstPerson':False,'status':'available',
               'identity':copy.deepcopy(identity),'rootIdentity':copy.deepcopy(root),
               'local':tx(local[name]),'world':tx(locate(name))} for name in names]
        actor={'status':'available','raceStatus':'available','sex':1,'baseForm':'0x0D000800',
               'race':'0x000CDD84','baseRace':'0x000CDD84','weight':{'status':'available','rawNPCWeight':50}}
        ref={'status':'available','loaded3D':True,'deleted':False,'disabled':False,
             'identity':copy.deepcopy(identity),'rootIdentity':copy.deepcopy(root),'actor':actor,
             'baseForm':'0x0D000800','scale':1.,'position':list(map(f32,position)),
             'anglesRadians':[0.,0.,0.],'sceneTransform':tx(position)}
        return {'ok':True,'quality':'complete','schemaVersion':1,'phase':'skse_main_thread_task',
                'units':'skyrim_engine_units','space':'world','coherence':copy.deepcopy(nominal.scene.OBSERVATION),
                'sessionId':'synthetic-only','loadGeneration':1,'sampleId':sample,'producerMonotonicNs':now,
                'observerVersion':'synthetic','refs':[ref],'nodes':rows}
    origin=[0.,0.,7000.]
    d={'schemaVersion':1,'protocol':nominal.protocol(),'subjectPins':PINS.copy(),
       'skeletonSha256':nominal.hierarchy.XP32_SHA256,'reference':REF,'sex':sex,
       'expectedParents':parents,'baseline':raw(origin),'setupReceipts':[],'receipts':{},'positionReceipts':{},'windows':{}}
    for function in ('EnableAI','SetRestrained'):
        request={'action':'call','script':'Actor','function':function,'self':{'form':REF},'args':[True],'timeoutMs':8000}
        d['setupReceipts'].append({'request':request,'nativeResult':{'called':True,'returnedType':'none','returned':None}})
    plan=nominal.controls.prepare(REF,sex)
    for phase,action in zip(nominal.PHASES,('start','stop','restart')):
        d['receipts'][action]=[{'request':request,'nativeResult':{'called':True,'returnedType':'none','returned':None},
                                'before':raw(origin),'after':raw(origin)} for request in plan['calls'][action]]
        amplitude=noise_off if phase=='stopped' else .2
        d['windows'][phase]=[];d['positionReceipts'][phase]=[]
        for i,pos in enumerate(nominal.trajectory(origin)):
            before=raw(pos)
            after=raw(pos,amplitude,i,2. if i==0 else .83,off_pose if phase=='stopped' else 0.)
            d['windows'][phase].append(after)
            d['positionReceipts'][phase].append({'request':{'action':'call','script':'ObjectReference','function':'SetPosition',
                'self':{'form':REF},'args':pos,'timeoutMs':8000},'nativeResult':{'called':True,'returnedType':'none','returned':None},
                'before':before,'after':after})
    done={"called":True,"returnedType":"none","returned":None}
    disabled=raw(origin);disabled["refs"][0]["disabled"]=True;disabled["refs"][0]["loaded3D"]=False
    # Build chronological cleanup rows separately from the phase samples.
    before=raw(origin);after=raw(origin);dispose_before=raw(origin);disabled=raw(origin)
    disabled["refs"][0]["disabled"]=True;disabled["refs"][0]["loaded3D"]=False
    d["cleanup"]={"providerState":"unknown","providerRestorationClaimed":False,
        "restoreReference":{"request":{"action":"call","script":"ObjectReference","function":"SetPosition",
            "self":{"form":REF},"args":origin,"timeoutMs":8000},"nativeResult":done.copy(),"before":before,"after":after},
        "disposeFixture":{"request":{"action":"call","script":"ObjectReference","function":"Disable",
            "self":{"form":REF},"args":[False],"timeoutMs":8000},"nativeResult":done.copy(),"before":dispose_before,"after":disabled}}
    return d


class NominalTests(unittest.TestCase):
    def test_all_eleven_positive_and_limit_labels(self):
        r=nominal.score(fixture(),PINS)
        self.assertEqual(r['status'],'sampled-provider-selective-motion')
        self.assertEqual(len(r['channels']),11)
        self.assertFalse(r['actualParentIdentityObserved'])
        self.assertFalse(r['runtimeQualified'])

    def test_missing_one_driver_is_not_all_driver_success(self):
        r=nominal.score(fixture(weak_node='TailBone04'),PINS)
        self.assertIn('TailBone04',r['missingDrivers'])
        self.assertEqual(r['status'],'unconfirmed')

    def test_off_driver_motion_fails_selective_response(self):
        r=nominal.score(fixture(noise_off=.1),PINS)
        self.assertEqual(len(r['missingDrivers']),11)

    def test_constant_stopped_pose_offset_is_not_motion(self):
        result=nominal.score(fixture(off_pose=.3),PINS)
        self.assertEqual(result['status'],'sampled-provider-selective-motion')

    def test_replayed_epoch_cadence_and_source_changes_reject(self):
        changes=[lambda d:d['windows']['stopped'][5].update(loadGeneration=2),
                 lambda d:d['windows']['active'][5].update(producerMonotonicNs=d['windows']['active'][4]['producerMonotonicNs']),
                 lambda d:d['windows']['active'][5].update(producerMonotonicNs=d['windows']['active'][5]['producerMonotonicNs']+300000000),
                 lambda d:d['subjectPins'].update(synthetic='changed')]
        for change in changes:
            d=fixture();change(d)
            with self.subTest(change=change),self.assertRaises(ValueError):nominal.score(d,PINS)

    def test_duplicate_name_and_expected_hierarchy_change_reject(self):
        d=fixture();d['windows']['active'][0]['nodes'][1]['name']=d['windows']['active'][0]['nodes'][0]['name']
        with self.assertRaises(ValueError):nominal.score(d,PINS)
        d=fixture();d['expectedParents']['TailBone03']='Tails'
        with self.assertRaises(ValueError):nominal.score(d,PINS)

    def test_stale_world_cannot_pass_local_motion(self):
        d=fixture()
        first=d['windows']['active'][0]['nodes'][0]['world']
        for row in d['windows']['active']:row['nodes'][0]['world']=copy.deepcopy(first)
        with self.assertRaisesRegex(ValueError,'composition inconsistent'):nominal.score(d,PINS)

    def test_inherited_only_motion_is_not_response(self):
        d=fixture()
        for phase in nominal.PHASES:
            for row in d['windows'][phase]:
                for node in row['nodes']:
                    node['local']=tx([0.,0.,0.]);node['world']=tx(row['refs'][0]['position'])
        r=nominal.score(d,PINS)
        self.assertEqual(len(r['missingDrivers']),11)

    def test_independent_local_control_and_bad_trajectory_reject(self):
        d=fixture();next(n for n in d['windows']['active'][5]['nodes'] if n['name']=='CME TailBone01')['local']['translation'][0]=.1
        with self.assertRaises(ValueError):nominal.score(d,PINS)
        d=fixture();d['windows']['active'][5]['refs'][0]['position'][0]+=1
        with self.assertRaises(ValueError):nominal.score(d,PINS)

    def test_incomparable_excitation_rejects_not_normalizes(self):
        d=fixture()
        # Add real expected-parent/root-consistent animation input on Head in one
        # phase. All its descendant world transforms move with it.
        names=set(nominal.scene.MALE[:4])|{'NPC Head [Head]'}
        for i,row in enumerate(d['windows']['active']):
            offset=.5*math.sin(i*.5)
            for node in row['nodes']:
                if node['name'] in names:node['world']['translation'][1]=f32(node['world']['translation'][1]+offset)
                if node['name']=='NPC Head [Head]':node['local']['translation'][1]=f32(node['local']['translation'][1]+offset)
        with self.assertRaisesRegex(ValueError,'Incomparable actual kinematic'):nominal.score(d,PINS)

    def test_aggregate_deadline_rejects(self):
        d=fixture();d['cleanup']['disposeFixture']['after']['producerMonotonicNs']=d['baseline']['producerMonotonicNs']+161000000000
        with self.assertRaisesRegex(ValueError,'deadline exceeded'):nominal.score(d,PINS)

    def test_missing_settle_rejects(self):
        d=fixture();d['windows']['active'][0]['producerMonotonicNs']-=1500000000
        with self.assertRaisesRegex(ValueError,'settle not observed'):nominal.score(d,PINS)

    def test_uncertain_native_receipt_rejects(self):
        d=fixture();d['receipts']['stop'][2]['nativeResult'].pop('returned')
        with self.assertRaises(ValueError):nominal.score(d,PINS)

    def test_missing_wrong_or_uncertain_position_packet_rejects(self):
        for change in (lambda d:d.pop('positionReceipts'),
                       lambda d:d['positionReceipts']['active'][2]['request'].update(function='MoveTo'),
                       lambda d:d['positionReceipts']['active'][2]['nativeResult'].pop('returned'),
                       lambda d:d['positionReceipts']['active'][2]['nativeResult'].update(isError=True)):
            d=fixture();change(d)
            with self.subTest(change=change),self.assertRaises((ValueError,KeyError)):nominal.score(d,PINS)

    def test_failed_provider_setup_and_cleanup_envelopes_reject(self):
        for select in (lambda d:d['receipts']['stop'][2], lambda d:d['setupReceipts'][0],
                       lambda d:d['cleanup']['restoreReference'], lambda d:d['cleanup']['disposeFixture']):
            d=fixture();select(d)['nativeResult']['isError']=True
            with self.subTest(select=select),self.assertRaisesRegex(ValueError,'Uncertain/non-void native completion'):
                nominal.score(d,PINS)

    def test_cleanup_or_provider_restore_claim_cannot_be_omitted(self):
        for change in (lambda d:d.pop('cleanup'),
                       lambda d:d['cleanup']['disposeFixture']['after']['refs'][0].update(disabled=False),
                       lambda d:d['cleanup'].update(providerRestorationClaimed=True)):
            d=fixture();change(d)
            with self.subTest(change=change),self.assertRaises((ValueError,KeyError)):nominal.score(d,PINS)

    def test_world_precision_floor_scales_with_coordinate_magnitude(self):
        a=tx([0.,0.,7000.]);b=tx([0.,0.,7001.])
        self.assertGreater(nominal.relative_floor(a,b,'translation'),1e-4)
        self.assertGreaterEqual(nominal.local_floor(tx([0.,0.,0.]),'translation'),1e-4)
        self.assertAlmostEqual(nominal.ulp32(7000.),2**-11)

if __name__=='__main__':unittest.main()
