from pathlib import Path
import copy,json,unittest,os,sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,os.environ.get("CLAW_PHOTO_HELPER_ROOT",str(HERE)))
import photo_pose
FIXTURES=Path(os.environ.get('CLAW_PHOTO_FIXTURE_ROOT',str(HERE.parents[1]/'resources/photo_comparison')))

class FinalPoseTests(unittest.TestCase):
 def setUp(self):
  self.fixture=json.loads((FIXTURES/'actual13E-prepark-final-negative.json').read_text())
  self.protocol=json.loads((FIXTURES/'protocol.json').read_text());self.a=self.fixture['final'];self.b=copy.deepcopy(self.a)
  # Synthetic stationary second observation of actual final coordinates, solely
  # for pure boundary tests. No claim that a second game sample existed in13E.
  self.b['sampleId']+=1;self.b['producerMonotonicNs']+=200000000
 def admit(self,a=None,b=None,span=.2):
  photo_pose.admit_final_baseline(a or self.a,b or self.b,self.fixture['specs'],self.protocol['positions'],180,self.protocol,span)
 def test_actual_prepark_foot_delta_remains_a_strict_negative(self):
  with self.assertRaisesRegex(ValueError,'skeleton pose changed'):self.admit(self.fixture['prepark'],self.fixture['final'],15.)
  photo_pose.same_actor_root_scale(self.fixture['prepark'],self.fixture['final'],self.protocol['alignment'])
 def test_stationary_final_sample_shape_is_accepted(self):self.admit()
 def test_final_bone_drift_is_not_waived(self):
  self.b['nodes'][0]['world']['translation'][0]+=.02
  with self.assertRaisesRegex(ValueError,'skeleton pose changed'):self.admit()
 def test_whole_root_world_drift_is_not_subtracted_away(self):
  for r in self.b['refs']:
   r['sceneTransform']['translation'][0]+=.03;r['position'][0]+=.03
  for n in self.b['nodes']:n['world']['translation'][0]+=.03
  with self.assertRaisesRegex(ValueError,'skeleton pose changed'):self.admit()
 def test_root_and_reference_scale_identity_remain_strict(self):
  for field in ('reference','root'):
   b=copy.deepcopy(self.b)
   if field=='reference':b['refs'][0]['scale']+=.001
   else:b['refs'][0]['sceneTransform']['scale']+=.001
   with self.subTest(field=field),self.assertRaisesRegex(ValueError,'scale changed'):self.admit(b=b)
 def test_reused_sample_clock_or_short_wallspan_refuses(self):
  for field in ('sampleId','producerMonotonicNs'):
   b=copy.deepcopy(self.b);b[field]=self.a[field]
   with self.subTest(field=field),self.assertRaisesRegex(ValueError,'advancing samples'):self.admit(b=b)
  with self.assertRaisesRegex(ValueError,'wall span'):self.admit(span=.199)
  b=copy.deepcopy(self.b);b['producerMonotonicNs']=self.a['producerMonotonicNs']+199999999
  with self.assertRaisesRegex(ValueError,'advancing samples'):self.admit(b=b)
 def test_root_token_or_observer_session_change_refuses(self):
  b=copy.deepcopy(self.b);b['refs'][0]['rootIdentity']['sampledRootToken']+=1
  with self.assertRaisesRegex(ValueError,'root identity'):self.admit(b=b)
  b=copy.deepcopy(self.b);b['sessionId']+='-changed'
  with self.assertRaisesRegex(ValueError,'session/load'):self.admit(b=b)

if __name__=='__main__':unittest.main()
