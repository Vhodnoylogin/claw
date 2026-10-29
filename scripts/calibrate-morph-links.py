"""Calibrate explicit human body-resource links from actual authored geometry.

Only logical anatomical candidates are compared. Gains are measured from frozen
dimensionless regional projections, never guessed from source slider spelling.
Outputs are new external calibration reports and typed resource-family XML.
"""
from pathlib import Path
import argparse, hashlib, importlib.util, json, re, sys
import xml.etree.ElementTree as ET
import numpy as np
import morph_calibration as cal

ROOT=Path(__file__).resolve().parents[1]
TARGETS={
 'girth':'CLAWTorsoGirth','waist':'CLAWTorsoWaistNarrow','flank':'CLAWTorsoFlankWidth',
 'belly':'CLAWTorsoBellyRound','arm':'CLAWArmGirth','thigh':'CLAWLegThighGirth',
 'calf':'CLAWLegCalfGirth','back':'CLAWTorsoBackWide','chest':'CLAWTorsoChestSize',
 'shoulder':'CLAWTorsoShoulderGirth','breast':'CLAWTorsoBreastSize'}


def pin(path):
 path=Path(path).resolve();data=path.read_bytes()
 return {'path':str(path),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}


def load_module(name,path):
 spec=importlib.util.spec_from_file_location(name,path)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def logical_sources(family):
 if family in ('3BA','CBBE'):
  groups=[
   ('BigTorso ChubbyWaist WideWaistLine'.split(),['girth','flank']),
   ('Waist TummyTuck'.split(),['waist','girth']),
   ('Hips HipUpperWidth HipNarrow_v2 UNPHip_v2'.split(),['flank']),
   ('Belly BigBelly PregnancyBelly BellyFrontUpFat_v2 BellyFrontDownFat_v2 BellySideUpFat_v2 BellySideDownFat_v2 BellyUnder_v2'.split(),['belly','girth']),
   ('Arms ChubbyArms ForearmSize MuscleArms MuscleMoreArms_v2'.split(),['arm','shoulder']),
   ('Thighs SlimThighs LegsThin ChubbyLegs MuscleLegs MuscleMoreLegs_v2 ThighOutsideThicc_v2 ThighInsideThicc_v2 ThighFBThicc_v2'.split(),['thigh','calf']),
   ('CalfSize CalfSmooth CalfFBThicc_v2'.split(),['calf']),
   ('ChestWidth ShoulderWidth Back MuscleBack_v2 BackWing_v2'.split(),['back','chest','shoulder']),
   ('ChestDepth MusclePecs SternumDepth'.split(),['chest']),
   ('Breasts BreastsFantasy BreastsNewSH BreastsNewSHSymmetry BreastsSmall BreastsSmall2 BreastsGone DoubleMelon BreastFlatness BreastFlatness2'.split(),['breast'])]
 else:
  groups=[
   ('BodyMass Chubby Lean Muscle'.split(),['girth','belly','arm','thigh','calf','flank']),
   ('TorsoMass TorsoMassSmooth TorsoLower'.split(),['girth','flank']),
   ('TorsoWaistSize TorsoFlatAbs'.split(),['waist','girth']),
   ('TorsoHip TorsoHipLarge TorsoHipSmooth'.split(),['flank']),
   ('TorsoBelly TorsoBellyChub TorsoBellyLHandles BellyPot BellySmooth BellyRounder PregnancyBelly'.split(),['belly','girth']),
   ('ArmsBiceps ArmsBicepsBack ArmsFore ArmsSide ArmsBrachio'.split(),['arm']),
   ('ArmsShoulders ArmsDelts ArmsDeltsBack ArmsDeltsUpper ArmsDeltsLower ArmsDeltsShape'.split(),['shoulder','arm']),
   ('TorsoWidth TorsoBackSize TorsoShoulderInc TorsoShoulderDec'.split(),['back','chest','shoulder']),
   ('PecsSize PecsMass PecsWidth PecsPush PecsDecrease PecsMinor PecsLower'.split(),['chest']),
   ('LegsSize LegsThigh LegsThinner LegsChubby LegsFemurUpper LegsFemurLower LegsFemurSide LegsFemurBack LegsThighUpperSide LegsVastusMReduction LegsThighInnerSide LegsThighIn LegsThighSmoothCurve'.split(),['thigh','calf']),
   ('LegsCalfSize LegsCalfWidth LegsCalfUpper LegsCalfLower LegsCalfFlatten LegsCalfSideIn LegsCalfOut'.split(),['calf'])]
 return {source:targets for sources,targets in groups for source in sources}


def mesh(nif, names):
 shapes=[shape for shape in nif.shapes if shape.name in names]
 if len(shapes)!=len(names):raise ValueError('Explicit source skin shapes missing')
 vertices=np.concatenate([np.asarray(shape.verts,float) for shape in shapes])
 bones={}
 start=0;offsets={}
 for shape in shapes:
  offsets[shape.name]=(start,len(shape.verts))
  for name,pairs in shape.bone_weights.items():
   weights=bones.setdefault(name,np.zeros(len(vertices)))
   for index,value in pairs:weights[start+index]+=value
  start+=len(shape.verts)
 return vertices,bones,offsets


def weight(bones,pattern,count):
 return sum((value for name,value in bones.items() if re.search(pattern,name,re.I)),np.zeros(count))


def fields(vertices,bones,breast_mask=None):
 count=len(vertices)
 spine=weight(bones,'Spine',count)>=.25
 if spine.sum()<30:raise ValueError('Missing torso anatomical support')
 lo,hi=np.quantile(vertices[spine,2],[.02,.98]);z=(vertices[:,2]-lo)/(hi-lo)
 waist=spine&(z>=.12)&(z<=.45)
 chest=spine&(z>=.48)&(z<=.95)
 breast=(weight(bones,'Breast',count)>=.25) if breast_mask is None else breast_mask
 chest&=~breast
 hip=weight(bones,'Pelv|Butt',count)>=.25
 definitions=[('waist.width',waist,'width'),('waist.depth',waist,'depth'),
  ('belly.front',waist,'front'),('thorax.width',chest,'width'),('thorax.depth',chest,'depth'),
  ('hip.width',hip,'width')]
 for region,pattern in [('upperarm','UpperArm|Upperarm'),('forearm','Forearm'),('thigh','Thigh'),('calf','Calf')]:
  for side in ('L','R'):
   mask=weight(bones,r'NPC '+side+r' .*('+pattern+r')',count)>=.25
   definitions.append((region+'.'+side,mask,'radial'))
 if breast.sum()>=8:
  definitions.extend([('breast.width',breast,'width'),('breast.front',breast,'front')])
 result={}
 for name,mask,kind in definitions:
  if mask.sum()>=8:result[name]=cal.feature(vertices,mask,kind)
 return result


def main():
 ap=argparse.ArgumentParser(description=__doc__)
 for name in ('human-nif','human-osp','wolf-nif','wolf-tri','pynifly','out'):ap.add_argument('--'+name,type=Path,required=True)
 ap.add_argument('--human-shape',required=True);ap.add_argument('--slider-set',required=True)
 ap.add_argument('--family',choices=('3BA','CBBE','HIMBO'),required=True);ap.add_argument('--version',required=True)
 ap.add_argument('--wolf-shapes',default='body,head',help='Explicit physical skin parts; include head_CLAWHead for a split family')
 args=ap.parse_args()
 args.out=args.out.resolve()
 if args.out.exists() or any(part.lower() in ('mods','data','overwrite','downloads') for part in args.out.parts):raise ValueError('New external output required')
 if ROOT==args.out or ROOT in args.out.parents:raise ValueError('Calibration outputs must remain outside source')
 if any((parent/'.git').exists() for parent in (args.out,*args.out.parents)):raise ValueError('Output inside a source checkout')
 for source in (args.human_nif,args.human_osp,args.wolf_nif,args.wolf_tri):
  if source.resolve().parent==args.out or source.resolve().parent in args.out.parents:raise ValueError('Output inside input directory')
 addon=args.pynifly.resolve();sys.path.insert(0,str(addon))
 source_inputs=[Path(__file__),Path(cal.__file__),args.human_nif,args.human_osp,args.wolf_nif,args.wolf_tri,
  addon/'NiflyDLL.dll',addon/'osd/osdfile.py',addon/'tri/tripfile.py',*sorted((addon/'pyn').rglob('*.py'))]
 captured=[pin(path) for path in source_inputs]
 from pyn import pynifly
 pynifly.NifFile.Load(str(addon/'NiflyDLL.dll'))
 osd_module=load_module('claw_source_osd',addon/'osd/osdfile.py')
 trip_module=load_module('claw_source_trip',addon/'tri/tripfile.py')
 osp=ET.parse(args.human_osp).getroot()
 slider_set=next(node for node in osp.findall('SliderSet') if node.attrib['name']==args.slider_set)
 target=next(node.attrib['target'] for node in slider_set.findall('Shape') if node.text==args.human_shape)
 human=pynifly.NifFile(str(args.human_nif));wolf=pynifly.NifFile(str(args.wolf_nif))
 wolf_shapes=args.wolf_shapes.split(',')
 hv,hb,ho=mesh(human,[args.human_shape]);wv,wb,wo=mesh(wolf,wolf_shapes)
 trip=trip_module.TripFile.from_filepath(str(args.wolf_tri))
 def raw_wolf_delta(name):
  d=np.zeros_like(wv)
  for shape,(start,count) in wo.items():
   for index,offset in trip.shapes.get(shape,{}).get(name,[]):d[start+index]=offset
  return d
 raw_wolf_fields={name:raw_wolf_delta(name) for name in TARGETS.values()}
 # Keep exact source-space samples once, even where an anatomical split copied
 # a seam. Distinct bind frames or different responses are never merged.
 frame_classes={};frame_ids=np.zeros(len(wv),dtype=int)
 def transform_key(value):
  return (*map(float,value.translation),*[float(x) for row in value.rotation for x in row],float(value.scale))
 for name,(start,count) in wo.items():
  shape=wolf.shape_dict[name]
  if not shape.has_global_to_skin:raise ValueError('Explicit target skin frame required: '+name)
  key=(transform_key(shape.global_to_skin),tuple((bone,transform_key(shape.get_shape_skin_to_bone(bone))) for bone in sorted(shape.bone_names)))
  frame_ids[start:start+count]=frame_classes.setdefault(key,len(frame_classes))
 raw_sample_count=len(wv)
 keep=cal.unique_physical_samples(wv,wb,raw_wolf_fields,frame_ids)
 wv=wv[keep];wb={name:value[keep] for name,value in wb.items()}
 wolf_fields={name:value[keep] for name,value in raw_wolf_fields.items()}
 def wolf_delta(name):return wolf_fields[name]
 breast_mask=np.linalg.norm(wolf_delta(TARGETS['breast']),axis=1)>1e-5
 osds={};human_deltas={};policy=logical_sources(args.family)
 for slider in slider_set.findall('Slider'):
  name=slider.attrib['name']
  if name not in policy or slider.attrib.get('uv')=='true':continue
  if slider.attrib.get('invert','false')!='false' or slider.attrib.get('clamp','false')!='false' or slider.attrib.get('zap','false')!='false':raise ValueError('Unqualified authored slider flags')
  delta=np.zeros_like(hv)
  for data in slider.findall('Data'):
   if data.attrib.get('target')!=target:continue
   filename=data.text.split('\\')[0];path=args.human_nif.parent/filename
   if path not in osds:
    captured.append(pin(path))
    loaded=osd_module.OSDFile.from_file(path)
    if not loaded.is_valid:raise ValueError('OSD read failed')
    osds[path]=dict(loaded.entries);source_inputs.append(path)
   for index,offset in osds[path][data.attrib['name']]:delta[index]+=offset
  human_deltas[name]=delta
 human_breast=(np.linalg.norm(human_deltas.get('Breasts',np.zeros_like(hv)),axis=1)>1e-5) if args.family!='HIMBO' else np.zeros(len(hv),bool)
 hf=fields(hv,hb,human_breast);wf=fields(wv,wb,breast_mask if args.family!='HIMBO' else np.zeros(len(wv),bool))
 feature_names=sorted(set(hf)&set(wf))
 hfields=[hf[name] for name in feature_names];wfields=[wf[name] for name in feature_names]
 target_names=[name for name in TARGETS if name!='breast' or args.family!='HIMBO']
 wolf_response={name:cal.response(wolf_delta(TARGETS[name]),wfields) for name in target_names}
 sources={name:cal.response(delta,hfields) for name,delta in human_deltas.items()}
 rules=[];comparisons=[]
 for source,human_response in sorted(sources.items()):
  if np.linalg.norm(human_response)<1e-6:continue
  allowed=[name for name in policy[source] if name in wolf_response]
  matrix=np.column_stack([wolf_response[name] for name in allowed])
  gains,error=cal.signed_fit(matrix,human_response)
  single=min(cal.signed_fit(matrix[:,index:index+1],human_response)[1] for index in range(len(allowed)))
  if error>single+1e-9:raise ValueError('Multiple-target solution regressed its single-target baseline')
  direction_guard=None
  if args.family=='HIMBO' and source=='TorsoWaistSize' and 'waist' in allowed:
   # The unconstrained multiregion fit can choose the opposite waist polarity
   # to improve unrelated depth/belly residuals. Keep the independently measured
   # lateral direction; do not refit other gains or invent a neutral offset.
   index=allowed.index('waist');axis=feature_names.index('waist.width')
   before=float(gains[index]);before_error=error
   gains[index]=cal.gain_with_primary_direction(before,human_response[axis],wolf_response['waist'][axis])
   positive=matrix@np.clip(gains,0,1);negative=matrix@np.clip(-gains,0,1)
   error=float(np.sum((positive-human_response)**2)+np.sum((negative+human_response)**2))
   direction_guard={'axis':'waist.width','gainBefore':before,'gainAfter':float(gains[index]),
    'humanResponse':float(human_response[axis]),'wolfResponse':float(wolf_response['waist'][axis]),
    'unconstrainedSignedUnitError':before_error,'policy':'preserve-primary-direction-v1'}
  comparisons.append({'source':source,'humanFeatureResponse':human_response.tolist(),'targets':allowed,'gains':gains.tolist(),
   'signedUnitError':error,'bestSingleTargetError':single,'zeroResponseError':float(2*human_response@human_response),
   'primaryDirectionGuard':direction_guard})
  for name,gain in zip(allowed,gains):
   if abs(gain)>1e-5:rules.append({'source':source,'target':TARGETS[name],'gain':round(float(gain),7),'cap':1})
 if not 1<=len(rules)<=128:raise ValueError('Native family rule budget exceeded: '+str(len(rules)))
 sex='male' if args.family=='HIMBO' else 'female'
 identity='CLAW.'+args.family+'.'+args.version+'.Geometry1'
 root=ET.Element('MorphLinkProfiles',schemaVersion='1')
 profile=ET.SubElement(root,'Profile',id=identity,family=args.family,version=args.version,sex=sex,calibration='regional-signed-projection-v1')
 for rule in rules:ET.SubElement(profile,'Rule',**{key:str(value) for key,value in rule.items()})
 ET.indent(root)
 args.out.mkdir(parents=True)
 (args.out/'MorphLinks.xml').write_text(ET.tostring(root,encoding='unicode')+'\n',encoding='ascii')
 zeros=cal.compose(rules,{})
 if any(zeros.values()):raise ValueError('Neutral mapping has an offset')
 report={'status':'implemented-geometric-calibration-not-game-appearance-acceptance','id':identity,'sex':sex,'family':args.family,
  'version':args.version,'inputs':captured,'features':feature_names,'featureMethod':'Frozen source-space regional signed projection / neutral local dimension. Linear authored geometry; not anatomical volume or rendering.',
  'wolfSkinSampling':{'shapes':wolf_shapes,'rawSamples':raw_sample_count,'uniqueResponseSamples':len(keep),
    'exactDuplicatesRemoved':raw_sample_count-len(keep),'identity':'coordinates + all skin weights + calibrated TRI fields + exact bind-frame class'},
  'baselineRegions':{'human':{name:{k:v for k,v in value.items() if k not in ('indices','directions')} for name,value in hf.items()},
    'wolf':{name:{k:v for k,v in value.items() if k not in ('indices','directions')} for name,value in wf.items()}},
  'wolfResponses':{name:value.tolist() for name,value in wolf_response.items()},'comparisons':comparisons,'rules':rules,
  'formula':'clamp(sum(effectiveHuman[source] * measuredSignedGain),0,1); no actor-weight interpolation, preset pairing or unmeasured traits',
  'limits':['Best among explicit logical target/sign allocations under the stated regional metric; not a universal artistic optimum',
    'No target capable of an opposed deformation means some human directions remain neutral',
    'Multiple sources sum before clamp; arbitrary presets and combined source shapes need actual visual/runtime acceptance',
    'Ears, tail, paws, claws, digitigrade and unrelated anatomy remain neutral without qualified human source fields'],
  'profile':pin(args.out/'MorphLinks.xml')}
 if captured!=[pin(path) for path in source_inputs]:raise ValueError('Calibration input changed')
 (args.out/'calibration.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'id':identity,'rules':len(rules),'sourceFields':len(comparisons),'featureCount':len(feature_names),'out':str(args.out)}))


if __name__=='__main__':main()
