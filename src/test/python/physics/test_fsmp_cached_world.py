"""Pure negative contracts; these synthetic poses are not game evidence."""
from pathlib import Path
import copy,sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integration'))
import fsmp_cached_world as cached


class CachedWorldTests(unittest.TestCase):
    def test_native_completion_preserves_typed_uncertainty(self):
        for raw,kind in [
            ({'called':True,'returnedType':'none'},'none'),
            ({'called':True,'returnedType':'bool','returned':1},'bool'),
            ({'called':True,'returnedType':'int','returned':True},'int'),
            ({'called':True,'returnedType':'float','returned':float('nan')},'float')]:
            self.assertFalse(cached.completed(raw,kind))
        self.assertTrue(cached.completed({'called':True,'returnedType':'none','returned':None},'none'))

    def test_console_ack_is_separate_from_camera_effect(self):
        raw={'completed':True,'queued':False,'capturing':True,'command':'tfc 1'}
        self.assertTrue(cached.console_completed(raw))
        for key,value in [('completed',False),('queued',True),('capturing',False),('command','tfc')]:
            self.assertFalse(cached.console_completed({**raw,key:value}))
        with self.assertRaises(ValueError):cached.camera_flags({'freeCam':True})

    def test_unique_positive_mass_match_for_both_sexes_and_duplicate_refusal(self):
        for sex,count in [('male',9),('female',11)]:
            names=cached.probe.drivers(sex);row={'nodes':{}};objects=[]
            for i,name in enumerate((*names,*dict.fromkeys(cached.probe.anchors(sex).values()))):
                rotation=[1.,0.,0.,0.,1.,0.,0.,0.,1.];xyz=[i*10.,0.,0.]
                row['nodes'][name]={'world':{'translation':xyz,'rotationRowMajor':rotation}}
                objects.append({'token':i+1,'lastPost':{'world':rotation+xyz,'rigidBody':True,
                    'inverseMass':20. if name in names else 0.,'flags':0 if name in names else 2}})
            match=cached.paused_match(row,{'objects':objects},sex)
            self.assertEqual(match['status'],f'unique-paused-dynamic{count}-match')
            self.assertFalse(match['kinematicExactMatchRequired'])
            objects.append(copy.deepcopy(objects[0]));objects[-1]['token']=99
            self.assertEqual(cached.paused_match(row,{'objects':objects},sex)['status'],'unavailable')

    def test_cached_pose_cannot_pass_wrong_space_or_outside_tolerance(self):
        sex='male';names=cached.probe.drivers(sex);row={'nodes':{}};objects=[]
        for i,name in enumerate((*names,*dict.fromkeys(cached.probe.anchors(sex).values()))):
            rotation=[1.,0.,0.,0.,1.,0.,0.,0.,1.];xyz=[i*10.,0.,0.]
            row['nodes'][name]={'world':{'translation':xyz,'rotationRowMajor':rotation}}
            objects.append({'token':i+1,'lastPost':{'world':rotation+xyz,'rigidBody':True,'inverseMass':20.,'flags':0}})
        objects[0]['lastPost']['world'][9]+=.0021
        self.assertEqual(cached.paused_match(row,{'objects':objects},sex)['status'],'unavailable')
        with self.assertRaises(ValueError):cached.paused_match(row,{'objects':objects},'unknown')


if __name__=='__main__':unittest.main()
