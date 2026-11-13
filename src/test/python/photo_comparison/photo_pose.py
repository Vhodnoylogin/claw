"""Packet-local raw custody and unchanged strict pose checks after translation."""
import copy,json,os,time
import capture_guards

def persist(directory,args,raw):
 entry={'atMonotonic':time.monotonic(),'args':args,'raw':raw}
 with (directory/'photo-pose-samples.jsonl').open('a',encoding='utf8') as stream:
  stream.write(json.dumps(entry,separators=(',',':'),allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())

def validate(raw,specs,positions,heading,protocol):
 unavailable=[{'form':r.get('form') or r.get('identity',{}).get('form'),'name':r.get('name'),
               'status':r.get('status'),'reason':r.get('reason')} for r in raw.get('refs',[])+raw.get('nodes',[])
              if r.get('status')!='available']
 capture_guards.require(not unavailable,'Native pose member unavailable: '+json.dumps(unavailable,separators=(',',':')))
 return capture_guards.validate_sample(raw,specs,positions,heading,protocol)

def select(raw,references):
 refs={r.casefold() for r in references}
 return {**raw,'refs':[r for r in raw['refs'] if r['identity']['form'].casefold() in refs],
         'nodes':[r for r in raw['nodes'] if r['form'].casefold() in refs]}

def same_actor_root_scale(baseline,current,alignment):
 capture_guards.require(type(baseline.get('sessionId')) is str and bool(baseline['sessionId']) and
    type(baseline.get('loadGeneration')) is int and baseline['loadGeneration']>0 and
    baseline['sessionId']==current.get('sessionId') and baseline['loadGeneration']==current.get('loadGeneration'),
                        'Final pose observer session/load generation changed')
 before={r['identity']['form']:r for r in baseline['refs']}
 after={r['identity']['form']:r for r in current['refs']}
 capture_guards.require(before.keys()==after.keys(),'Final pose actor catalogue changed')
 for ref,a in before.items():
  b=after[ref]
  capture_guards.require(a['identity']==b['identity'] and a['rootIdentity']==b['rootIdentity'],
                         'Final pose actor/root identity changed')
  capture_guards.require(a['scale']==b['scale'] and a['sceneTransform']['scale']==b['sceneTransform']['scale'],
                         'Final pose actor/root scale changed')
  capture_guards.require(max(abs(x-y) for x,y in zip(a['sceneTransform']['rotationRowMajor'],b['sceneTransform']['rotationRowMajor']))<=alignment['rootRotationTolerance'],
                         'Final pose root rotation changed')

def final_stable(baseline,current,alignment):
 same_actor_root_scale(baseline,current,alignment)
 # Same final placement: all original absolute local/world pose tolerances apply.
 capture_guards.compare_bracket(baseline,current,alignment)

def admit_final_baseline(first,second,specs,positions,heading,protocol,wall_span):
 validate(first,specs,positions,heading,protocol);validate(second,specs,positions,heading,protocol)
 capture_guards.require(type(first.get('sampleId')) is int and first['sampleId']>0 and type(second.get('sampleId')) is int and
    second['sampleId']>first['sampleId'] and type(first.get('producerMonotonicNs')) is int and
    first['producerMonotonicNs']>0 and type(second.get('producerMonotonicNs')) is int and
    second['producerMonotonicNs']-first['producerMonotonicNs']>=round(protocol['sampleSpanSeconds']*1000000000) and
    wall_span>=protocol['sampleSpanSeconds'],'Final placement lacks two advancing samples and required wall span')
 final_stable(first,second,protocol['alignment'])

def compare_repositioned(baseline,current,alignment):
 # Translation is explicitly authored/read back at the two fixed photo anchors.
 # Compare unchanged locals and world pose relative to each actual root. This
 # does not alter the source evidence, any image, or any numeric tolerance.
 def root_relative(raw):
  out=copy.deepcopy(raw)
  roots={r['identity']['form'].casefold():r['sceneTransform']['translation'] for r in out['refs']}
  for node in out['nodes']:
   root=roots[node['form'].casefold()]
   node['world']['translation']=[v-r for v,r in zip(node['world']['translation'],root)]
  return out
 capture_guards.compare_bracket(root_relative(baseline),root_relative(current),alignment)
