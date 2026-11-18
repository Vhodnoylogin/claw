"""Portable symbolic response discrimination; no captured game assets or file dependencies."""
from pathlib import Path
import copy,math,struct,sys,unittest
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import fsmp_damping_response_readback as r
from test_fsmp_joint_limit_readback import symbolic_fixture, associate

def bundle(left=0.):
 d=symbolic_fixture(left=left,right=0.)
 for key in ('witnessA','witnessB','finalWitness'):
  d[key]['sample'].update(mainFreezeNextFrame=False,engineMultiplier=1,timerPauseCount=0)
 a=associate(d)
 return {'rawPair':{'matches':a,'worldB':d['worldB'],'witnessB':d['witnessB']},
         'finalWitness':d['finalWitness'],'restLocal':d['restLocal']}


def fixture():
 d=bundle();assoc=copy.deepcopy(d['rawPair']['matches']);assoc=r.baseline(assoc,d['rawPair']['witnessB'])
 final=copy.deepcopy(d['finalWitness']);w=final['sample']['objectWindow'];objects={o['token']:o for o in w['objects']}
 original=copy.deepcopy(d['rawPair']['worldB']);observed=copy.deepcopy(original)
 observed['sampleId']+=1;observed['producerMonotonicNs']+=200_000_000
 inputs={'anchors':{},'pairedStepsAfterSecondKnownUpdate':500,'remainingPairedSteps':400,'atomicInput':False}
 for parent,driver,peak in zip(r.PARENTS,r.DRIVERS,(.08,.012)):
  a,b=objects[assoc['A']['tokens'][parent]],objects[assoc['A']['tokens'][driver]]
  old=copy.deepcopy(a['initialPre']);held=copy.deepcopy(old)
  axis=[old['world'][i*3] for i in range(3)]
  for i in range(3):held['world'][9+i]+=.1*axis[i]
  for stage in ('lastPre','lastPost'):a[stage]=copy.deepcopy(held)
  a['minimumPostWorld']=[min(x,y) for x,y in zip(old['world'],held['world'])]
  a['maximumPostWorld']=[max(x,y) for x,y in zip(old['world'],held['world'])]
  inputs['anchors'][parent]={'anchorPose':held,'actualStep':.1,
   'beforeWorld':r.joint.pose_transform(old),'afterWorld':r.joint.pose_transform(held)}
  node=next(n for n in observed['nodes'] if n['name']==parent);node['world']=r.joint.pose_transform(held)
  for stage in ('lastPre','lastPost'):
   b[stage]=copy.deepcopy(b['initialPre'])
   b[stage]['world']=held['world'][:9]+[held['world'][9+i]+sum(held['world'][i*3+j]*r.pivot(d['restLocal'][driver])[j] for j in range(3)) for i in range(3)]
  restpoint=b['lastPost']['world'];initial=copy.deepcopy(restpoint);maximum=copy.deepcopy(restpoint)
  for i in range(3):initial[9+i]-=.1*axis[i];maximum[9+i]+=peak*axis[i]
  b['minimumPostWorld']=[min(x,y,z) for x,y,z in zip(restpoint,initial,maximum)]
  b['maximumPostWorld']=[max(x,y,z) for x,y,z in zip(restpoint,initial,maximum)]
 assoc['baselineFirstPreQpc']=w['firstPreQpc'];assoc['initialObjectPoses']={str(o['token']):copy.deepcopy(o['initialPre']) for o in w['objects']}
 return d,assoc,inputs,final,original,observed


class Bounds(unittest.TestCase):
 def test_papyrus_float32_storage_matches_value_not_python_double(self):
  actual=struct.unpack('<f',struct.pack('<f',.1))[0]
  self.assertNotEqual(actual,.1)
  self.assertTrue(r.exact_f32_vector([actual,0.,0.],[.1,0.,0.]))
  bits=struct.unpack('<I',struct.pack('<f',actual))[0]
  adjacent=struct.unpack('<f',struct.pack('<I',bits+1))[0]
  self.assertFalse(r.exact_f32_vector([adjacent,0.,0.],[.1,0.,0.]))
 def test_nonfinite_boolean_and_wrong_width_inputs_refused(self):
  for actual in ([float('nan'),0.,0.],[float('inf'),0.,0.],[True,0.,0.],[.1,0.]):
   with self.subTest(actual=actual):self.assertFalse(r.exact_f32_vector(actual,[.1,0.,0.]))
 def test_symbolic_valid_response_is_only_an_enclosure(self):
  d,a,i,f,_,_=fixture();v=r.score(a,i,f,d['restLocal'])
  self.assertIn('extrema-contrast',v['status']);self.assertFalse(v['trajectoryRecovered']);self.assertFalse(v['timeCoverageProven'])
  self.assertFalse(v['atomicInput'])
 def test_both_ignored_edit_identical_responses_fail(self):
  d,a,i,f,_,_=fixture();w=f['sample']['objectWindow'];o={v['token']:v for v in w['objects']}
  left=o[a['A']['tokens'][r.DRIVERS[0]]];right=o[a['A']['tokens'][r.DRIVERS[1]]]
  for key in ('minimumPostWorld','maximumPostWorld'):
   # Transfer only relative envelopes; absolute bilateral anchor positions differ.
   for n in range(12):left[key][n]=left['lastPost']['world'][n]+right[key][n]-right['lastPost']['world'][n]
  with self.assertRaises(ValueError):r.score(a,i,f,d['restLocal'])
 def test_missing_positive_right_response_fails(self):
  d,a,i,f,_,_=fixture();w=f['sample']['objectWindow'];o={v['token']:v for v in w['objects']};b=o[a['A']['tokens'][r.DRIVERS[1]]]
  anchor=i['anchors'][r.PARENTS[1]]['anchorPose'];u=[anchor['world'][j*3] for j in range(3)]
  for k in ('minimumPostWorld','maximumPostWorld'):
   for j in range(3):b[k][9+j]-=.1*u[j]
  # Keep coherent final last pose inside its extrema; this is a frozen detached control.
  for stage in ('lastPre','lastPost'):
   for j in range(3):b[stage]['world'][9+j]-=.1*u[j]
  with self.assertRaisesRegex(ValueError,'independently follow'):r.score(a,i,f,d['restLocal'])
 def test_shifted_linear_stop_is_not_a_quiet_damping_baseline(self):
  d=bundle(left=.05)
  with self.assertRaisesRegex(ValueError,'Unshifted quiet'):r.baseline(d['rawPair']['matches'],d['rawPair']['witnessB'])
 def test_full900_required(self):
  d,a,i,f,_,_=fixture();f['sample']['objectWindow']['status']='collecting';f['sample']['objectWindow']['pairedSteps']=899
  with self.assertRaises(ValueError):r.score(a,i,f,d['restLocal'])
 def test_original_masses_required(self):
  d,a,i,f,_,_=fixture();o=f['sample']['objectWindow']['objects'][a['A']['tokens'][r.DRIVERS[0]]-1]
  for stage in r.joint.STAGES:o[stage]['inverseMass']=10
  with self.assertRaises(ValueError):r.score(a,i,f,d['restLocal'])
 def test_nonce_fork_refused(self):
  d,a,i,f,_,_=fixture();f['sample']['objectWindow']['nonce']+=1
  with self.assertRaises(ValueError):r.score(a,i,f,d['restLocal'])
 def test_drop_refused(self):
  d,a,i,f,_,_=fixture();f['sample']['objectWindow']['callbackDrops']=1
  with self.assertRaises(ValueError):r.score(a,i,f,d['restLocal'])
 def test_unqualified_opening_refused(self):
  d,a,i,f,_,_=fixture();a.pop('responseBaselineValidated')
  with self.assertRaises(ValueError):r.score(a,i,f,d['restLocal'])
 def test_insufficient_post_update_pairs_refused(self):
  d,a,i,f,_,_=fixture();i['pairedStepsAfterSecondKnownUpdate']=661
  with self.assertRaises(ValueError):r.score(a,i,f,d['restLocal'])
 def test_wrong_pivot_cannot_be_silently_raw_world_origin(self):
  anchor={'world':[1,0,0,0,1,0,0,0,1,0,0,0],'inverseMass':0,'flags':2,'rigidBody':True}
  pose=[0,-1,0,1,0,0,0,0,1,-.92,0,0]
  o={'minimumPostWorld':pose,'maximumPostWorld':pose}
  rest={'translation':[0,1,0],'rotationRowMajor':[1,0,0,0,1,0,0,0,1],'scale':1}
  good=r.peak_bounds(o,anchor,rest,epsilon=0)
  rest['translation']=[0,0,0];wrong=r.peak_bounds(o,anchor,rest,epsilon=0)
  self.assertAlmostEqual(good['lower'],.08);self.assertAlmostEqual(wrong['upper'],-.92)
 def test_rotated_joint_axis_cannot_be_raw_world_x(self):
  anchor={'world':[0,-1,0,1,0,0,0,0,1,0,0,0],'inverseMass':0,'flags':2,'rigidBody':True}
  pose=[0,-1,0,1,0,0,0,0,1,-1,.08,0];o={'minimumPostWorld':pose,'maximumPostWorld':pose}
  rest={'translation':[0,1,0],'rotationRowMajor':[1,0,0,0,1,0,0,0,1],'scale':1}
  self.assertAlmostEqual(r.peak_bounds(o,anchor,rest,epsilon=0)['lower'],.08)
  anchor['world'][:9]=[1,0,0,0,1,0,0,0,1]
  self.assertAlmostEqual(r.peak_bounds(o,anchor,rest,epsilon=0)['upper'],0)
 def test_non_cotemporal_coordinate_extrema_never_become_a_peak_pose(self):
  c=math.sqrt(.5);anchor={'world':[c,-c,0,c,c,0,0,0,1,0,0,0],'inverseMass':0,'flags':2,'rigidBody':True}
  rows=[[1,0,0,0,1,0,0,0,1,1,0,0],[1,0,0,0,1,0,0,0,1,0,1,0]]
  rec={'minimumPostWorld':[min(v[k] for v in rows) for k in range(12)],'maximumPostWorld':[max(v[k] for v in rows) for k in range(12)]}
  rest={'translation':[0,0,0],'rotationRowMajor':[1,0,0,0,1,0,0,0,1],'scale':1}
  b=r.peak_bounds(rec,anchor,rest,epsilon=0)
  self.assertAlmostEqual(b['lower'],c);self.assertAlmostEqual(b['upper'],2*c)
  self.assertNotEqual(b['upper'],c)  # upper is a conservative enclosure, never an actual amplitude.
 def test_final_anchor_drift_refused(self):
  d,a,i,f,_,_=fixture();o=f['sample']['objectWindow']['objects'][a['A']['tokens'][r.PARENTS[0]]-1]
  o['lastPost']['world'][9]+=.01;o['maximumPostWorld'][9]+=.01
  with self.assertRaises(ValueError):r.score(a,i,f,d['restLocal'])
 def test_actual_two_held_inputs_and_count_checkpoint(self):
  d,a,i,f,original,observed=fixture();f['sample']['objectWindow']['status']='collecting';f['sample']['objectWindow']['pairedSteps']=660
  v=r.held_inputs(a,f,original,observed)
  self.assertEqual(v['remainingPairedSteps'],240);self.assertFalse(v['atomicInput'])
 def test_held_input_window_already_ended_refused(self):
  d,a,i,f,original,observed=fixture()
  with self.assertRaises(ValueError):r.held_inputs(a,f,original,observed)
 def test_wrong_actual_anchor_step_refused(self):
  d,a,i,f,original,observed=fixture();f['sample']['objectWindow']['status']='collecting';f['sample']['objectWindow']['pairedSteps']=650
  observed['nodes']=copy.deepcopy(original['nodes'])
  with self.assertRaises(ValueError):r.held_inputs(a,f,original,observed)


if __name__=='__main__':unittest.main(verbosity=2)
