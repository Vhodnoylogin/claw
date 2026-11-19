import copy,json,unittest
import validate_snapshot as v

def fixture(serial=1,count=0,qpc=100):
 e={'count':count,'lastQpc':qpc if count else 0,'lastThreadId':7 if count else 0,
    'lastTimeStep':.01 if count else 0.,'coherent':True,'invalidEvents':0,'droppedEvents':0}
 return {'schema':'claw-fsmp-step-witness/2','status':'ready','requestSerial':serial,'pid':17,'qpcFrequency':100,
  'provider':{'status':'ready','interfaceVersion':[2,0,0],'bulletVersion':[3,24,0],'bulletObjectsDereferenced':True,
   'compiledBulletHeaderVersion':325,'btUseSseInApi':True,'btScalarBytes':4,'bulletVersionDeclarationIsHardcoded':True,
   'objectLayoutPdbGuid':'FA13003A-6397-4D63-833B-71BE3CFFE2C2','objectLayoutPdbSha256':'1fcd447240416f1f40a4ddb0cdad3e2a16c0028d690a2a86b7bea8ed89b5006f'},
  'sample':{'phase':'skse_main_thread_task','physicsPhase':'not_synchronized','loadEpoch':2,
   'sampledQpc':qpc,'sampledThreadId':1,'mainThreadIdRaw':1,'mainFreezeTime':False,
   'mainFreezeNextFrame':False,'mainGameActive':True,'uiPaused':False,'worldRootPresent':True,
   'worldCameraPresent':True,'timerPauseCount':0,'timerRealDelta':.01,'timerDelta':.01,
   'engineMultiplier':1.,'pre':copy.deepcopy(e),'post':copy.deepcopy(e),
   'objectWindow':{'status':'idle','coherent':True,'objectCapacity':128,'pairedStepLimit':900,'nonce':0,'loadEpoch':0,
    'callbackDrops':0,'failureCode':0,'pairedSteps':0,'objectCount':0,'awaitingPost':False,'objects':[]}}}
def window():
 a={'world':[1.,0,0,0,1.,0,0,0,1.,5.,6.,7.],'rigidBody':True,'inverseMass':20.,'flags':0}
 b=copy.deepcopy(a);b['world'][9]+=.01
 return {'status':'complete','nonce':71,'loadEpoch':2,'coherent':True,'objectCapacity':128,'pairedStepLimit':900,
  'objectCount':1,'pairedSteps':900,'failureCode':0,'callbackDrops':0,'firstPreQpc':1,'lastPreQpc':2999,'lastPostQpc':3000,
  'lastPreThreadId':7,'lastPostThreadId':7,'lastTimeStep':.016,'awaitingPost':False,
  'objects':[{'token':1,'initialPre':a,'lastPre':a,'lastPost':b,'minimumPostWorld':a['world'],
   'maximumPostWorld':b['world'],'maximumPairedDifference':.01,'firstNonzeroStep':1,'firstNonzeroPreQpc':1,'firstNonzeroPostQpc':2,'firstNonzeroPair':{'pre':a,'post':b}}]}

def v3_window():
 w=window();w.update(schemaVersion=3,minimumPairedHostTimeStep=.016,summedPairedHostTimeStep=.016*900,
                     timeStepStatisticsScope=v.HOST_DT_SCOPE)
 for row in w['objects']:
  for p in [row['initialPre'],row['lastPre'],row['lastPost'],row['firstNonzeroPair']['pre'],row['firstNonzeroPair']['post']]:
   p.update(linearVelocity=[0.,-1.,0.],angularVelocity=[-.25,0.,0.],inverseLocalInertia=[10.,0.,10.])
 return w

def v4_window():
 w=v3_window();w['schemaVersion']=4
 second=copy.deepcopy(w['objects'][0]);second['token']=2;w['objects'].append(second);w['objectCount']=2
 p={'lowerLimit':[-1.,-1.,-1.,0.,0.,0.],'upperLimit':[1.,1.,1.,0.,0.,0.],
    'springEnabled':[True,True,True,False,False,False],'stiffness':[50.,50.,50.,0.,0.,0.],
    'damping':[0.,.4,.4,0.,0.,0.],'stopERP':[.2]*6,'stiffnessLimited':[True]*6,'dampingLimited':[True]*6}
 w['incidentConstraints']={'status':'observed','scope':v.CONSTRAINT_SCOPE,'axisOrder':v.CONSTRAINT_AXES,
    'perBodyReferenceLimit':64,'uniqueConstraintCapacity':256,'constraintCount':1,'failureCode':0,
    'constraints':[{'token':1,'bodyAToken':1,'bodyBToken':2,'type':12,'enabled':True,'status':'spring2','spring2':p}]}
 return w

class V4Tests(unittest.TestCase):
 def test_vr_uses_v4_windows_and_has_no_se_pause_authority(self):
  def vr(serial,count,time):
   value=fixture(serial,count,time);value['schema']=v.VR_SCHEMA
   sample=value['sample']
   for field in v.ENGINE_FIELDS:del sample[field]
   sample.update(engineStateAvailable=False,objectWindow=v4_window())
   return value
  a,b=vr(1,0,100),vr(2,41,250)
  self.assertEqual(v.compare(v.parse(json.dumps(a)),v.parse(json.dumps(b)))['postStepDelta'],41)
  for field,value in (('engineStateAvailable',True),('engineStateAvailable',0),('mainFreezeTime',False),
                      ('objectWindow',v3_window())):
   changed=copy.deepcopy(b);changed['sample'][field]=value
   with self.subTest(field=field,value=value),self.assertRaises(ValueError):v.parse(json.dumps(changed))
  with self.assertRaises(ValueError):v.compare(v.parse(json.dumps(a)),v.parse(json.dumps(fixture(2,41,250))))
 def test_full_six_axis_readout_and_legacy_versions(self):
  w=v4_window();self.assertIs(v.validate_window(w,2),w)
  d=fixture();d['schema']='claw-fsmp-step-witness/4';d['sample']['objectWindow']=w
  self.assertEqual(v.parse(json.dumps(d))['sample']['objectWindow']['incidentConstraints'],w['incidentConstraints'])
  v.validate_window(v3_window(),2);v.validate_window(window(),2)
 def test_unsupported_type_is_explicit_and_does_not_erase_supported_edge(self):
  w=v4_window();c=w['incidentConstraints'];edge=copy.deepcopy(c['constraints'][0])
  edge.update(token=2,type=11,status='unsupported_type',spring2=None)
  c.update(status='unsupported',constraintCount=2);c['constraints'].append(edge)
  v.validate_window(w,2)
  self.assertEqual(c['constraints'][0]['spring2']['damping'][0],0.)
  edge['spring2']={}
  with self.assertRaises(ValueError):v.validate_window(w,2)
 def test_empty_initial_catalog_and_not_started_have_distinct_status(self):
  w=v4_window();c=w['incidentConstraints'];c.update(constraintCount=0,constraints=[]);v.validate_window(w,2)
  w.update(status='armed',pairedSteps=0,objectCount=0,objects=[],awaitingPost=False,
     minimumPairedHostTimeStep=None,summedPairedHostTimeStep=0.)
  c['status']='not_started';v.validate_window(w,2)
  c['status']='observed'
  with self.assertRaises(ValueError):v.validate_window(w,2)
 def test_missing_or_unversioned_joint_evidence_refused(self):
  for version in (None,2,3):
   w=v4_window()
   if version is None:del w['schemaVersion']
   else:w['schemaVersion']=version
   with self.subTest(version=version),self.assertRaises(ValueError):v.validate_window(w,2)
  w=v4_window();del w['incidentConstraints']
  with self.assertRaises(ValueError):v.validate_window(w,2)
 def test_endpoints_type_support_flags_bounds_and_pointer_leaks_refused(self):
  for field,value in [('bodyAToken',0),('bodyBToken',3),('bodyAToken',True),('type',True),
     ('type',11),('status','unsupported_type'),('enabled',1),('key',12345)]:
   w=v4_window();w['incidentConstraints']['constraints'][0][field]=value
   with self.subTest(field=field,value=value),self.assertRaises(ValueError):v.validate_window(w,2)
  for field,value in [('status','refused'),('constraintCount',257),('perBodyReferenceLimit',65),
      ('uniqueConstraintCapacity',True),('failureCode',1),('scope','latest approximate state')]:
   w=v4_window();w['incidentConstraints'][field]=value
   with self.subTest(field=field),self.assertRaises(ValueError):v.validate_window(w,2)
  w=v4_window();w['objects'][1]['initialPre']['rigidBody']=False
  for key in v.DYNAMICS_FIELDS:w['objects'][1]['initialPre'][key]=None
  with self.assertRaises(ValueError):v.validate_window(w,2)
 def test_parameters_are_exact_finite_six_axis_arrays_and_bool_flags(self):
  for field,value in [('lowerLimit',[0]*5),('upperLimit',[0]*7),('stiffness',[float('inf')]*6),
     ('damping',[False]*6),('stopERP',None),('springEnabled',[1]*6),('stiffnessLimited',[None]*6),
     ('dampingLimited',[False]*5),('key',[0]*6)]:
   w=v4_window();w['incidentConstraints']['constraints'][0]['spring2'][field]=value
   with self.subTest(field=field),self.assertRaises(ValueError):v.validate_window(w,2)

class V3Tests(unittest.TestCase):
 def test_explicit_v3_parse_and_direct_window_keep_exact_dynamics(self):
  w=v3_window();self.assertIs(v.validate_window(w,2,71),w)
  d=fixture();d['schema']='claw-fsmp-step-witness/3';d['sample']['objectWindow']=w
  self.assertEqual(v.parse(json.dumps(d))['sample']['objectWindow'],w)
  self.assertEqual(w['objects'][0]['firstNonzeroPair']['post']['inverseLocalInertia'],[10.,0.,10.])
 def test_zero_rigid_dynamics_are_available_and_valid(self):
  w=v3_window()
  for p in [w['objects'][0]['initialPre'],w['objects'][0]['lastPre'],w['objects'][0]['lastPost']]:
   for key in v.DYNAMICS_FIELDS:p[key]=[0.,0.,0.]
  v.validate_window(w,2)
 def test_nonrigid_requires_explicit_null_not_fabricated_zero(self):
  w=v3_window();r=w['objects'][0]
  for p in [r['initialPre'],r['lastPre'],r['lastPost'],r['firstNonzeroPair']['pre'],r['firstNonzeroPair']['post']]:
   p['rigidBody']=False;p['inverseMass']=0.
   for key in v.DYNAMICS_FIELDS:p[key]=None
  v.validate_window(w,2)
  r['lastPost']['linearVelocity']=[0.,0.,0.]
  with self.assertRaises(ValueError):v.validate_window(w,2)
 def test_bad_rigid_vectors_and_negative_inertia_refused(self):
  for field,value in [('linearVelocity',None),('linearVelocity',[False,0,0]),('angularVelocity',[0,0]),
      ('angularVelocity',[0,float('inf'),0]),('inverseLocalInertia',[10,-1,10])]:
   w=v3_window();w['objects'][0]['lastPost'][field]=value
   with self.subTest(field=field,value=value),self.assertRaises(ValueError):v.validate_window(w,2)
 def test_initial_and_first_pair_dynamics_are_not_optional(self):
  for stage in ('initialPre','lastPre','firstNonzeroPair'):
   w=v3_window();p=w['objects'][0][stage]
   if stage=='firstNonzeroPair':p=p['post']
   del p['angularVelocity']
   with self.subTest(stage=stage),self.assertRaises(ValueError):v.validate_window(w,2)
 def test_no_schema_inference_or_cross_schema_comparison(self):
  for version in (None,2,True,4):
   w=v3_window()
   if version is None:del w['schemaVersion']
   else:w['schemaVersion']=version
   with self.subTest(version=version),self.assertRaises(ValueError):v.validate_window(w,2)
  d=fixture();d['sample']['objectWindow']=v3_window()
  with self.assertRaises(ValueError):v.parse(json.dumps(d))
  d=fixture(2,20,300);d['schema']='claw-fsmp-step-witness/3';w=copy.deepcopy(d['sample']['objectWindow'])
  w.update(schemaVersion=3,minimumPairedHostTimeStep=None,summedPairedHostTimeStep=0.,timeStepStatisticsScope=v.HOST_DT_SCOPE)
  d['sample']['objectWindow']=w
  with self.assertRaises(ValueError):v.compare(v.parse(json.dumps(fixture())),v.parse(json.dumps(d)))
 def test_host_pair_statistics_bounds_and_scope(self):
  for key,value in [('minimumPairedHostTimeStep',None),('minimumPairedHostTimeStep',0),
     ('summedPairedHostTimeStep',float('nan')),('summedPairedHostTimeStep',.1),
     ('timeStepStatisticsScope','Bullet substeps')]:
   w=v3_window();w[key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):v.validate_window(w,2)
 def test_completed_statistics_contain_last_pair_but_pending_pre_is_excluded(self):
  w=v3_window();w.update(minimumPairedHostTimeStep=.05,summedPairedHostTimeStep=45.)
  with self.assertRaises(ValueError):v.validate_window(w,2)
  w=v3_window();w.update(lastTimeStep=15.)
  with self.assertRaises(ValueError):v.validate_window(w,2)
  w=v3_window();w.update(status='collecting',awaitingPost=True,lastPreQpc=3001,lastTimeStep=.001)
  v.validate_window(w,2)
 def test_idle_and_pending_pre_do_not_require_or_count_unpaired_dt(self):
  w=fixture()['sample']['objectWindow'];w.update(schemaVersion=3,minimumPairedHostTimeStep=None,
       summedPairedHostTimeStep=0.,timeStepStatisticsScope=v.HOST_DT_SCOPE);v.validate_window(w,2)
  w['summedPairedHostTimeStep']=.016
  with self.assertRaises(ValueError):v.validate_window(w,2)
  w=v3_window();w.update(status='collecting',awaitingPost=True,lastPreQpc=3001,lastTimeStep=.001)
  v.validate_window(w,2) # The in-flight host step is not yet part of completed statistics.
class Tests(unittest.TestCase):
 def test_zero_is_valid_unqualified_and_positive_growth_is_only_global_steps(self):
  a=v.parse(json.dumps(fixture()),1);b=v.parse(json.dumps(fixture(2,20,300)),2)
  self.assertEqual(v.compare(a,b),{'preStepDelta':20,'postStepDelta':20,'providerCompletedStepsObserved':True,'seconds':2.,'targetActorOrMotionQualified':False})
  b=v.parse(json.dumps(fixture(2,0,300)),2);self.assertFalse(v.compare(a,b)['providerCompletedStepsObserved'])
 def test_bad_types_versions_clock_serial_and_duplicate_json_refuse(self):
  for field,val in [('pid',True),('requestSerial',1.0),('qpcFrequency',0),('status','refused')]:
   d=fixture();d[field]=val
   with self.subTest(field=field),self.assertRaises(ValueError):v.parse(json.dumps(d),1)
  d=fixture();d['provider']['interfaceVersion']=[1,0,0]
  with self.assertRaises(ValueError):v.parse(json.dumps(d),1)
  with self.assertRaises(ValueError):v.parse(json.dumps(fixture()),2)
  with self.assertRaises(ValueError):v.parse('{"schema":1,"schema":2}')
 def test_incoherent_invalid_dropped_and_cross_epoch_refuse(self):
  for field,val in [('coherent',False),('invalidEvents',1),('droppedEvents',1),('lastTimeStep',0)]:
   d=fixture(count=1);d['sample']['post'][field]=val
   with self.subTest(field=field),self.assertRaises(ValueError):v.parse(json.dumps(d))
  a=v.parse(json.dumps(fixture()));b=fixture(2,20,300);b['sample']['loadEpoch']=3
  with self.assertRaises(ValueError):v.compare(a,v.parse(json.dumps(b)))
 def test_complete_window_and_no_external_pointer_identity(self):
  w=window();self.assertIs(v.validate_window(w,2,71),w)
  d=fixture();d['sample']['objectWindow']=w;v.parse(json.dumps(d))
  self.assertEqual(set(w['objects'][0]['initialPre']),{'world','rigidBody','inverseMass','flags'})
 def test_window_overflow_epoch_drop_and_incomplete_refuse(self):
  for key,value in [('objectCount',129),('pairedSteps',899),('nonce',72),('loadEpoch',3),('callbackDrops',1),('failureCode',3),('coherent',False)]:
   w=window();w[key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):v.validate_window(w,2,71)
 def test_world_and_first_delta_mutants_refuse(self):
  for change in ('nonfinite','wrongshape','badtoken','zeroFirstPair','badExtrema','pointerLeak'):
   w=window();r=w['objects'][0]
   if change=='nonfinite':r['lastPost']['world'][2]=float('nan')
   elif change=='wrongshape':r['lastPre']['world'].pop()
   elif change=='badtoken':r['token']=1.0
   elif change=='zeroFirstPair':r['firstNonzeroPair']['post']=r['firstNonzeroPair']['pre']
   elif change=='badExtrema':r['minimumPostWorld'][9]=100.
   else:r['initialPre']['key']=12345678
   with self.subTest(change=change),self.assertRaises(ValueError):v.validate_window(w,2,71)
if __name__=='__main__':unittest.main(verbosity=2)
