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
