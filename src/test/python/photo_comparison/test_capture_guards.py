import copy,json,unittest,sys,os
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,os.environ.get('CLAW_PHOTO_HELPER_ROOT',str(HERE)))
import capture_guards as g,photo_pose
from test_support import FIXTURES,temporary

class CaptureGuards(unittest.TestCase):
    def normal(self):return {'requested':1,'effective':1,'owner':'','leased':False,'leaseRemainingMs':0}
    def frozen(self):return {'requested':0,'effective':0,'owner':'owned','leased':True,'leaseRemainingMs':100,'generation':3,'currentGeneration':3,'state':'reached','reached':True,'applied':True}
    def test_foreign_or_offnormal_baseline_refuses(self):
        g.admit_baseline(self.normal())
        for change in [{'leased':True},{'effective':0},{'requested':True},{'leaseRemainingMs':-1}]:
            with self.subTest(change=change),self.assertRaises(ValueError):g.admit_baseline(dict(self.normal(),**change))
    def test_set_requires_exact_known_generation_completion(self):
        g.set_receipt(self.frozen(),0,True)
        for change in [{'currentGeneration':4},{'generation':True},{'reached':False},{'applied':False},{'owner':''}]:
            with self.subTest(change=change),self.assertRaises(ValueError):g.set_receipt(dict(self.frozen(),**change),0,True)
    def test_get_readback_does_not_invent_generation_and_detects_lease_loss(self):
        raw=self.frozen();g.frozen_readback(raw,raw,raw)
        for change in [{'owner':'other'},{'leaseRemainingMs':0},{'leaseRemainingMs':101},{'effective':1}]:
            with self.subTest(change=change),self.assertRaises(ValueError):g.frozen_readback(dict(raw,**change),raw,raw)
    def test_camera_requires_owned_finite_complete_fields(self):
        raw={k:0 for k in g.CAMERA_FIELDS};raw.update(freeCam=True,freeCamOwned=True,freeCamBackend='declared',camAngles=[0,0])
        g.camera_key(raw)
        for change in [{'freeCamOwned':False},{'camX':float('nan')},{'camYaw':True}]:
            with self.subTest(change=change),self.assertRaises(ValueError):g.camera_key(dict(raw,**change))
    def test_ambiguous_or_missing_bones_and_nonfinite_transform_refuse(self):
        f=json.loads((FIXTURES/'actual13E-prepark-final-negative.json').read_bytes());p=json.loads((FIXTURES/'protocol.json').read_bytes())
        for mutate in [lambda r:r['nodes'].pop(),lambda r:r['nodes'][0]['local']['translation'].__setitem__(0,float('nan'))]:
            raw=copy.deepcopy(f['final']);mutate(raw)
            with self.assertRaises(ValueError):photo_pose.validate(raw,f['specs'],p['positions'],180,p)
    def test_raw_unavailable_read_is_persisted_before_refusal(self):
        raw={'refs':[{'status':'unavailable','reason':'explicit unavailable'}],'nodes':[]}
        with temporary() as folder:
            path=Path(folder);photo_pose.persist(path,{'kind':'world_observer'},raw)
            with self.assertRaisesRegex(ValueError,'Native pose member unavailable'):photo_pose.validate(raw,{}, {},0,{})
            self.assertEqual(json.loads((path/'photo-pose-samples.jsonl').read_bytes())['raw'],raw)
