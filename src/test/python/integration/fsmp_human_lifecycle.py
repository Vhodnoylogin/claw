"""One nonshipping human-origin lifecycle, then combined paused FSMP writeback.

No physics acceptance at unmeasured boundaries; no source/provider writes.
"""
from pathlib import Path
import importlib.util,json,math,os,struct,sys,time,xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[4]
import fsmp_probe as probe
import fsmp_cached_world as cached
_witness_spec=importlib.util.spec_from_file_location("claw_fsmp_witness_snapshot",ROOT/"src/test/cpp/fsmp_step_witness/validate_snapshot.py")
witness=importlib.util.module_from_spec(_witness_spec);_witness_spec.loader.exec_module(witness)
from skyrim_autotest import api_contract,native,platform
require=cached.require
BEAST='0x000CDD84';NORD='0x00013746';PLUGIN='test_CLAW - Physics Probe.esp'
NONCE=13021309;SAVE_TAG='fsmp-human-lifecycle'
SPECS=(
 {'sex':'female','sexNumber':1,'local':0x900,'reference':'0x0D000900','base':'0x000A2C91','weight':50.,'wolfScale':1.,'offset':150.,'dynamic':11,'fixed':4},
 {'sex':'male','sexNumber':0,'local':0x901,'reference':'0x0D000901','base':'0x000A2C90','weight':29.999998092651367,'wolfScale':1.1299999952316284,'offset':-150.,'dynamic':9,'fixed':2})
CONTRACTS={'CLAWFSMPWitness': ('globalFunctions', {'ReadState': (['int'], 'string'), 'BeginWindow': (['int'], 'string')}), 'DynamicHDT': ('globalFunctions', {'QueryCurrentPhysicsFile': (['actor', 'armoraddon', 'bool'], 'string')}), 'ObjectReference': ('memberFunctions', {'Enable': (['bool'], 'none'), 'Disable': (['bool'], 'none'), 'MoveTo': (['objectreference', 'float', 'float', 'float', 'bool'], 'none')}), 'Actor': ('memberFunctions', {'EnableAI': (['bool'], 'none'), 'SetRestrained': (['bool'], 'none'), 'SetHeadTracking': (['bool'], 'none')}), 'Game': ('globalFunctions', {'GetFormFromFile': (['int', 'string'], 'form')}), 'Utility': ('globalFunctions', {'Wait': (['float'], 'none')})}
CONTRACTS['Actor'][1].update(SetRace=(['race'],'none'),UnequipAll=([],'none'))
CONTRACTS['CLAWDistributionNative']=('globalFunctions',{
 'GetStatus':(['actor'],'int'),'GetHumanWeight':(['actor'],'float'),
 'GetMorphFamily':(['actor'],'string'),'GetOwnMorph':(['actor','string'],'float'),
 'GetCoatPattern':(['actor'],'string'),'GetAppliedCoatPattern':(['actor'],'string'),
 'GetCoatPatternStatus':(['actor'],'string'),'Refresh':(['actor'],'bool')})
CONTRACTS['NiOverride']=('globalFunctions',{'GetBodyMorph':(['objectreference','string','string'],'float')})
f32=lambda x:struct.unpack('<f',struct.pack('<f',x))[0]
bits=lambda x:struct.pack('<f',x).hex()
finite=cached.finite
completed=cached.completed

def validate_ref(raw,spec,current_race,*,disabled=False,loaded=True,expectedBaseRace=BEAST):
    """Explicit current/base-race pair; initial ancestry is separate, raw unchanged."""
    require(raw.get('ok') is True and raw.get('quality')=='complete','Incomplete reference observation')
    rows=[r for r in raw.get('refs',[]) if probe.form(r.get('identity',{}).get('form'))==spec['reference']]
    require(len(rows)==1,'Exact owned reference missing/ambiguous')
    r=rows[0];a=r.get('actor',{});i=r.get('identity',{})
    require(r.get('status')=='available' and r.get('deleted') is False and r.get('disabled') is disabled,'Owned availability differs')
    require(probe.form(r.get('baseForm'))==spec['base'] and probe.form(a.get('baseForm'))==spec['base']
        and i.get('sourcePlugin')==PLUGIN and i.get('localFormId')==f"0x{spec['local']:08X}",'Original human base/reference differs')
    require(a.get('status')=='available' and a.get('raceStatus')=='available' and a.get('sex')==spec['sexNumber']
        and probe.form(a.get('race'))==current_race and probe.form(a.get('baseRace'))==expectedBaseRace
        and a.get('weight',{}).get('status')=='available' and a['weight'].get('rawNPCWeight')==spec['weight'],'Declared same-actor sex/baseRace/weight or current race differs')
    require(type(raw.get('loadGeneration')) is int and raw['loadGeneration']>0 and i.get('loadGeneration')==raw['loadGeneration']
        and type(i.get('runtimeHandle')) is int and i['runtimeHandle']>0,'Actual incarnation unavailable')
    require(type(r.get('loaded3D')) is bool and (loaded is None or r['loaded3D'] is loaded),'Expected loaded/unloaded model differs')
    require(finite(r.get('scale')) and r['scale']>0,'Invalid actual actor scale')
    if r['loaded3D']:
        root=r.get('rootIdentity',{})
        require(root.get('firstPerson') is False and type(root.get('sampledRootToken')) is int and root['sampledRootToken']>0,'Missing actual third-person root')
    return r

def wolf_snapshot(raw,spec):
    validate_ref(raw,spec,BEAST,expectedBaseRace=BEAST)
    # A transparent per-actor view of a durably retained two-actor raw sample.
    view={**raw,'refs':[r for r in raw['refs'] if probe.form(r['identity']['form'])==spec['reference']],
          'nodes':[r for r in raw['nodes'] if probe.form(r['form'])==spec['reference']]}
    row=probe.snapshot(view,spec['reference'],spec['sex'])
    scale=spec['wolfScale']
    require(abs(row['guard']['scale']-scale)<=1e-5 and abs(row['root']['scale']-scale)<=1e-5
        and all(abs(n['local']['scale']-1.)<=1e-5 and abs(n['world']['scale']-scale)<=1e-5 for n in row['nodes'].values()),'Sex-matched actual wolf scales differ')
    return row

def race_argument(target):
    require(target in (BEAST,NORD),'Only declared human/wolf Race form permitted')
    return {'form':target}

def matrix_contract(config):
    path=next(r['source'] for r in config['staged_plugins'] if r['destination']=='SKSE/Plugins/CLAW/MorphLinks.xml')
    root=ET.parse(path).getroot();defaults=root.find('Defaults').attrib
    result={}
    for spec in SPECS:
        profile=next(r for r in root.findall('Profile') if r.attrib['id']==defaults[spec['sex']])
        targets=list(dict.fromkeys(r.attrib['target'] for r in profile))[:3]
        require(len(targets)==3,'Three actual staged matrix targets required')
        result[spec['sex']]={'family':profile.attrib['id'],'targets':targets}
    return result

def combined_match(rows,window):
    matches={};tokens=[]
    for spec in SPECS:
        result=cached.paused_match(rows[spec['sex']],window,spec['sex'])
        require(result['status']==f"unique-paused-dynamic{spec['dynamic']}-match",'Sex-specific paused WORLD writeback unavailable')
        matches[spec['sex']]=result;tokens.extend(r['candidates'][0]['token'] for r in result['dynamicBodies'])
    require(len(tokens)==len(set(tokens))==20,'Combined20 dynamic roles not unique/injective')
    return {'matches':matches,'tokens':tokens}

class Case:
    def __init__(self,session,configuration):
        self.s=session;self.start=time.monotonic();self.end=self.start+300.;self.work_end=self.start+250.;self.cleanup=False
        self.dir=session.dir/'human-fsmp-lifecycle';self.dir.mkdir();self.sequence=0
        self.identities={};self.roots={};self.enabled={s['sex']:False for s in SPECS};self.races={s['sex']:NORD for s in SPECS}
        self.raw_tool=session.tool;self.originalCamera=None;self.normal=None
        self.state={'intent':None,'unknownMutation':False,'semanticRacePending':None,'cameraFreezeActive':False,'cameraPhase':'original',
            'startedMonotonic':self.start,'observations':[],'boundaries':{},'rootTransitions':[],
            'scope':'human-origin lifecycle + final paused writeback only','physicsQualified':False,
            'enabled':self.enabled,'currentRaces':self.races,'expectedCurrentAndBaseRaces':self.races,'initialHumanAncestry':{}}
        self.matrix=matrix_contract(configuration)
        self.s.phase('bounded-human-origin-fsmp-lifecycle',300);self.save()
    def save(self):
        with (self.dir/'state.json').open('w',encoding='utf-8') as f:json.dump(self.state,f,indent=2);f.flush();os.fsync(f.fileno())
    def limit(self):return self.end if self.cleanup else self.work_end
    def raw(self,tool,args,cap=6):
        require(time.monotonic()<self.limit(),'Bounded lifecycle deadline before dispatch')
        deadline=min(self.limit(),time.monotonic()+cap)
        result=self.raw_tool(tool,args,timeout=max(.01,deadline-time.monotonic()),deadline=deadline)
        self.sequence+=1;p=self.dir/f'raw-{self.sequence:04}.json'
        p.write_text(json.dumps({'monotonic':time.monotonic(),'tool':tool,'args':args,'result':result},indent=2)+'\n',encoding='utf-8')
        self.state['observations'].append(str(p));self.save();return result
    def query(self,nodes=False):
        args={'kind':'world_observer','refs':[s['reference'] for s in SPECS],'actors':True}
        if nodes:args['nodes']=[{'ref':s['reference'],'name':n,'firstPerson':False} for s in SPECS for n in probe.node_names(s['sex'])]
        return self.raw('inspect',args)
    def guard(self,spec,*,allowRootChange=False,loaded=None):
        raw=self.query();sex=spec['sex'];r=validate_ref(raw,spec,self.races[sex],disabled=not self.enabled[sex],loaded=loaded,expectedBaseRace=self.races[sex])
        identity=r['identity']
        if sex in self.identities:require(identity==self.identities[sex],'Owned incarnation changed without completed load')
        else:self.identities[sex]=identity
        if r['loaded3D']:
            root=r['rootIdentity']
            if sex in self.roots and root!=self.roots[sex]:
                require(allowRootChange,'Owned model changed outside declared transition')
                self.state['rootTransitions'].append({'sex':sex,'old':self.roots[sex],'new':root,'actualSample':raw['sampleId']})
            self.roots[sex]=root
        return raw,r
    def quarantine(self,reason):
        self.state['unknownMutation']=True;self.state['unknownReason']=reason
        self.s.state['ownedFixtureQuarantine']={'references':[s['reference'] for s in SPECS],'reason':reason,'intent':self.state['intent'],'ownedSessionTeardownRequired':True}
        try:self.save()
        except BaseException:pass
    def mutate(self,label,tool,args,receipt,*,spec=None,cap=8):
        require(not self.state['unknownMutation'] and self.state['intent'] is None and self.state['semanticRacePending'] is None,'Unknown/pending mutation interlock')
        require(self.limit()-time.monotonic()>cap,'Insufficient remaining mutation/cleanup budget')
        require(native.identity(self.s.state['game']['pid'])==self.s.state['game'],'Owned game process changed')
        for current in ([spec] if spec else SPECS):self.guard(current)
        require(self.limit()-time.monotonic()>cap,'Guard consumed required mutation/cleanup budget')
        self.state['intent']={'label':label,'tool':tool,'args':args,'monotonic':time.monotonic()}
        try:
            self.save();result=self.raw(tool,args,cap)
            require(receipt(result),'Mutation completion/type unavailable: '+label)
            self.state['intent']=None;self.save();return result
        except BaseException as error:self.quarantine(repr(error));raise
    def pap(self,script,function,args=(),self_ref=None,kind='none',write=False,spec=None):
        packet={'action':'call','script':script,'function':function,'args':list(args),'timeoutMs':6000}
        if self_ref:packet['self']={'form':self_ref}
        value=self.mutate(function,'papyrus',packet,lambda r:completed(r,kind),spec=spec) if write else self.raw('papyrus',packet)
        require(completed(value,kind),'Typed native read unavailable: '+function);return value['returned']
    def claw(self,spec,function,*args,kind='string',write=False):
        return self.pap('CLAWDistributionNative',function,[{'form':spec['reference']},*args],kind=kind,write=write,spec=spec)
    def poll(self,label,read,accept,seconds=12):
        stop=min(self.limit(),time.monotonic()+seconds)
        while True:
            value=read()
            if accept(value):return value
            require(time.monotonic()<stop,'Bounded observation unavailable: '+label);time.sleep(.15)
    def actor_write(self,spec,function,args,*,newRace=None):
        before=None
        if function=='SetRace':
            require(newRace is not None and args==[race_argument(newRace)],'SetRace requires actual typed Race form dictionary')
            before=self.guard(spec,loaded=True)[0]
            require(type(before.get('sampleId')) is int and before['sampleId']>0 and
                type(before.get('producerMonotonicNs')) is int and before['producerMonotonicNs']>0,'Missing pre-setter producer witness')
        value=self.pap('Actor' if function in ('SetRace','UnequipAll','EnableAI','SetRestrained','SetHeadTracking') else 'ObjectReference',
            function,args,self_ref=spec['reference'],write=True,spec=spec)
        if function=='Enable':self.enabled[spec['sex']]=True
        if function=='Disable':self.enabled[spec['sex']]=False
        if function=='SetRace':self.confirm_race(spec,newRace,before)
        return value
    def confirm_race(self,spec,target,before):
        sex=spec['sex'];old=self.races[sex]
        self.state['semanticRacePending']={'sex':sex,'from':old,'to':target,'beforeSample':before['sampleId'],
            'beforeProducerNs':before['producerMonotonicNs'],'nativeVoidAckIsNotSemanticCompletion':True,'observations':[]}
        try:
            self.save()
            def read():
                raw=self.query();matches=[r for r in raw.get('refs',[]) if probe.form(r.get('identity',{}).get('form'))==spec['reference']]
                require(len(matches)==1,'Race readback lost exact reference')
                actual=probe.form(matches[0].get('actor',{}).get('race'))
                actual_base=probe.form(matches[0].get('actor',{}).get('baseRace'))
                require(actual in (old,target) and actual_base in (old,target),'Current/base race changed outside declared transition')
                r=validate_ref(raw,spec,actual,disabled=False,loaded=None,expectedBaseRace=actual_base)
                require(r['identity']==self.identities[sex],'Race readback incarnation changed')
                require(type(raw.get('sampleId')) is int and raw['sampleId']>before['sampleId']
                    and type(raw.get('producerMonotonicNs')) is int and raw['producerMonotonicNs']>before['producerMonotonicNs'],'Race readback not fresh after guarded setter')
                self.state['semanticRacePending']['observations'].append({'sample':raw['sampleId'],'producerNs':raw['producerMonotonicNs'],
                    'actualRace':actual,'actualBaseRace':actual_base,'loaded3D':r['loaded3D'],'root':r.get('rootIdentity')});self.save()
                return actual,r,actual_base
            actual,r,actual_base=self.poll('actual semantic race after typed setter',read,lambda v:v[0]==target and v[2]==target and v[1]['loaded3D'] is True,12)
            # Only this actual observation authorizes the new expected race/root.
            self.races[sex]=actual
            if sex in self.roots and r['rootIdentity']!=self.roots[sex]:
                self.state['rootTransitions'].append({'sex':sex,'old':self.roots[sex],'new':r['rootIdentity'],'reason':'observed declared race transition'})
            self.roots[sex]=r['rootIdentity']
            self.state.setdefault('completedRaceTransitions',[]).append(self.state['semanticRacePending'])
            self.state['semanticRacePending']=None;self.save()
        except BaseException as error:
            self.quarantine('Semantic race completion unavailable after native void ACK: '+repr(error));raise
    def model_ready(self,spec,*,allowRootChange=False):
        def read():return self.guard(spec,allowRootChange=allowRootChange)[1]
        self.poll('loaded model',read,lambda r:r['loaded3D'] is True,20)
        self.guard(spec,loaded=True)
    def resolved(self):
        rows=[]
        for s in SPECS:
            value=self.pap('Game','GetFormFromFile',[s['local'],PLUGIN],kind='form')
            require(type(value) is dict and probe.form(value.get('formId'))==s['reference'],'Actual plugin/local reference resolution differs')
            rows.append({'local':s['local'],'rawReturned':value,'expected':s['reference']})
        return rows
    def status_ready(self,spec,wolf,*,allowRootChange=False):
        wanted=2 if wolf else 5
        self.poll('actual CLAW status',lambda:self.claw(spec,'GetStatus',kind='int'),lambda x:x==wanted,12)
        self.model_ready(spec,allowRootChange=allowRootChange)
    def binding(self,spec):
        value=self.pap('DynamicHDT','QueryCurrentPhysicsFile',[{'form':spec['reference']},{'form':'0x000CDD87'},False],kind='string')
        expected=f"SKSE/Plugins/hdtSkinnedMeshConfigs/CLAW/CLAWMotion{spec['sex'].capitalize()}.xml"
        require(value.replace('\\','/').casefold()==expected.casefold(),'Actual sex-matched registered XML differs')
        return value
    def capture(self,label,wolf,compare=None):
        values={}
        for s in SPECS:
            self.status_ready(s,wolf);self.guard(s,loaded=True)
            weight=self.claw(s,'GetHumanWeight',kind='float');family=self.claw(s,'GetMorphFamily')
            require(bits(weight)==bits(f32(s['weight']/100.)),'Captured human weight differs/polluted by wolf race')
            require(family.casefold()==self.matrix[s['sex']]['family'].casefold(),'Actual staged default morph family differs')
            morphs={}
            for target in self.matrix[s['sex']]['targets']:
                v=self.claw(s,'GetOwnMorph',target,kind='float')
                skee=self.pap('NiOverride','GetBodyMorph',[{'form':s['reference']},target,'CLAW.Distribution'],kind='float')
                require(bits(v)==bits(skee),'Native cache/actual provider own morph disagree')
                if not wolf:require(v==0. and skee==0.,'Human return retained owned wolf morph')
                morphs[target]=v
            if wolf and s['sex']=='male':require(any(abs(v)>.001 for v in morphs.values()),'Declared male matrix nonzero own field unavailable')
            row={'status':2 if wolf else 5,'humanWeight':weight,'family':family,'ownMorphs':morphs,
                'explicitCoat':self.claw(s,'GetCoatPattern'),'appliedCoat':self.claw(s,'GetAppliedCoatPattern'),
                'coatStatusRaw':self.claw(s,'GetCoatPatternStatus'),
                'actualIdentity':self.identities[s['sex']],'actualRoot':self.roots[s['sex']],
                'initialHumanAncestry':self.state['initialHumanAncestry'][s['sex']],
                'expectedCurrentAndBaseRace':self.races[s['sex']],'rawNPCWeight':s['weight']}
            if wolf:row['registeredXml']=self.binding(s)
            if compare:
                previous=compare[s['sex']]
                require(all(bits(v)==bits(previous['ownMorphs'][k]) for k,v in morphs.items()),'Native/provider own fields did not persist')
                require(all(row[k].casefold()==previous[k].casefold() for k in ('family','explicitCoat','appliedCoat')),'Family/coat selection did not persist')
            values[s['sex']]=row
        self.state['boundaries'][label]=values;self.save();return values
    def transition(self,wolf):
        for s in SPECS:self.actor_write(s,'SetRace',[race_argument(BEAST if wolf else NORD)],newRace=BEAST if wolf else NORD)
        for s in SPECS:self.status_ready(s,wolf,allowRootChange=True)
    def snapshot(self):
        raw=self.pap('CLAWFSMPWitness','ReadState',[0],kind='string');v=witness.parse(raw);serial=v['requestSerial']
        require(v['status']=='pending','Witness snapshot not queued')
        return self.poll('witness snapshot',lambda:witness.parse(self.pap('CLAWFSMPWitness','ReadState',[serial],kind='string'),serial),lambda x:x['status']=='ready',6)
    def camera(self):return cached.camera_flags(self.raw('camera',{'action':'get'}))
    def toggle(self):
        return self.mutate('tfc1','console',{'action':'exec','command':'tfc 1','capture':True,'maxLines':200},cached.console_completed)
    def restore_camera(self):
        if not self.state['cameraFreezeActive']:return
        require(not self.state['unknownMutation'] and self.state['intent'] is None,'Unknown freeze cannot be restored by guessing')
        flags=self.camera();current=self.snapshot()['sample']
        if self.state['cameraPhase']!='restore-ack':
            require(flags['freeCam'] is True and flags['freeCamOwned'] is False and flags['orbitOn'] is False and current['mainFreezeTime'] is True,'Owned TFC state changed; no blind toggle')
            self.toggle();self.state['cameraPhase']='restore-ack';flags=self.camera();current=self.snapshot()['sample']
        require(flags==self.originalCamera and current['mainFreezeTime']==self.normal['sample']['mainFreezeTime']
            and current['mainFreezeNextFrame']==self.normal['sample']['mainFreezeNextFrame'],'Acknowledged camera/freeze restore unavailable; no second toggle')
        self.state['cameraFreezeActive']=False;self.state['cameraPhase']='restored';self.save()
    def final_window(self):
        require(self.work_end-time.monotonic()>45,'Full final witness/cleanup budget unavailable before arm')
        modules=native.modules(self.s.state['game']);admission=cached.module_admission(modules)
        (self.dir/'loaded-modules-before-arm.json').write_text(json.dumps({'raw':modules,'verified':admission},indent=2)+'\n')
        before_raw=self.query(True);before={s['sex']:wolf_snapshot(before_raw,s) for s in SPECS}
        self.normal=self.snapshot();main=self.normal['sample'];self.originalCamera=self.camera()
        require(main['mainFreezeTime'] is False and main['mainFreezeNextFrame'] is False and main['uiPaused'] is False
            and main['engineMultiplier']==1. and main['timerPauseCount']==0 and main['worldRootPresent'] is True,'Actual final context paused/offnormal')
        require(not self.originalCamera['freeCam'] and not self.originalCamera['freeCamOwned'] and not self.originalCamera['orbitOn'],'Original camera not normal')
        packet={'action':'call','script':'CLAWFSMPWitness','function':'BeginWindow','args':[NONCE],'timeoutMs':6000}
        marked=self.mutate('first arm after load','papyrus',packet,lambda r:completed(r,'string'))
        stop=min(self.work_end,time.monotonic()+35)
        def arm_value():
            require(completed(marked,'string'),'Malformed first arm receipt')
            value=json.loads(marked['returned'])
            require(type(value) is dict and value.get('nonce')==NONCE and value.get('status') in ('pending','ready'),'Window arm/poll nonce or state differs')
            return value
        v=arm_value()
        while v.get('status')=='pending':
            require(time.monotonic()<stop,'Window arm deadline');time.sleep(.05)
            marked=self.raw('papyrus',packet);v=arm_value()
        require(v.get('status')=='ready' and v.get('nonce')==NONCE,'First window arm refused')
        initial=self.snapshot()
        while initial['sample']['objectWindow']['pairedSteps']<=20:
            require(time.monotonic()<stop,'More than20 initial pairs unavailable');time.sleep(.1);initial=self.snapshot()
        require(initial['sample']['objectWindow']['status']=='collecting','Final window not collecting')
        self.state['cameraFreezeActive']=True;self.state['cameraPhase']='freeze-intent';self.save()
        self.toggle();self.state['cameraPhase']='freeze-ack';time.sleep(.3)
        paused_a=self.snapshot();signature=cached.paused_signature(paused_a)
        world_a=self.query(True);a={s['sex']:wolf_snapshot(world_a,s) for s in SPECS};time.sleep(.2)
        world_b=self.query(True);b={s['sex']:wolf_snapshot(world_b,s) for s in SPECS};paused_b=self.snapshot()
        require(cached.paused_signature(paused_b)==signature and paused_b['sample']['sampledQpc']>paused_a['sample']['sampledQpc'],'Paused steps/cache changed')
        for s in SPECS:
            sex=s['sex'];require(b[sex]['sample']>a[sex]['sample'] and b[sex]['time']-a[sex]['time']>=200_000_000,'Paused producer progression<.2s')
            for row in (a[sex],b[sex]):
                require(row['guard']['identity']==self.identities[sex] and row['guard']['root']==self.roots[sex],'Paused incarnation/root changed')
                require(probe.max_delta(row['position'],before[sex]['position'])<=.025
                    and probe.max_delta(row['angles'],before[sex]['angles'])<=1e-5
                    and probe.max_delta(row['root']['translation'],before[sex]['root']['translation'])<=.025
                    and probe.max_delta(row['root']['rotationRowMajor'],before[sex]['root']['rotationRowMajor'])<=1e-5,'Final actor/root drifted')
        match_a=combined_match(a,paused_b['sample']['objectWindow']);match_b=combined_match(b,paused_b['sample']['objectWindow'])
        require(match_a['tokens']==match_b['tokens'],'Cached object association changed between observations')
        matches={'A':match_a['matches'],'B':match_b['matches']};all_tokens=match_a['tokens']
        paused={'witnessA':paused_a,'witnessB':paused_b,'worldA':world_a,'worldB':world_b,'matches':matches,'tokens':all_tokens}
        (self.dir/'paused-writeback.json').write_text(json.dumps(paused,indent=2)+'\n')
        self.restore_camera();final=self.snapshot()
        while final['sample']['objectWindow']['status']!='complete':
            require(time.monotonic()<stop,'900 paired steps deadline');time.sleep(.5);final=self.snapshot()
        count=len(final['sample']['objectWindow']['objects'])
        require(count==48,'Actual final object catalog differs from declared22 ambient+15female+11male; no unknown systems accepted')
        self.state['result']={'status':'combined-human-lifecycle-paused-writeback-complete','paused':paused,'final':final,'bodyCount':count,
            'dynamicRoles':20,'fixedAnchorsRecorded':6,'lifecycleMeasuredEarlier':False,'physicsQualified':False};self.save()
    def execute(self,scenario,original_execute):
        modules=native.modules(self.s.state['game']);cached.module_admission(modules)
        (self.dir/'loaded-modules.json').write_text(json.dumps(modules,indent=2)+'\n')
        for script,(scope,methods) in CONTRACTS.items():
            d=self.raw('papyrus',{'action':'describe','script':script})
            rows=api_contract.validate_description(script,d,scope,{n:t[0] for n,t in methods.items()})
            require(all(r.get('native') is True and r['returnType'].casefold()==methods[r['function']][1] for r in rows),'Actual API contract differs: '+script)
        original_execute(self.s,scenario)
        self.s.phase('human-origin-fsmp-lifecycle',self.end-time.monotonic())
        self.state['resolvedInitial']=self.resolved()
        for s in SPECS:
            raw,r=self.guard(s,loaded=False)
            self.state['initialHumanAncestry'][s['sex']]={'identity':r['identity'],'baseForm':r['baseForm'],
                'initialCurrentRace':r['actor']['race'],'initialBaseRace':r['actor']['baseRace'],
                'sex':r['actor']['sex'],'rawNPCWeight':r['actor']['weight']['rawNPCWeight'],
                'sampleId':raw['sampleId'],'producerMonotonicNs':raw['producerMonotonicNs'],'loadGeneration':raw['loadGeneration']}
        self.save()
        for s in SPECS:
            self.actor_write(s,'Enable',[False]);self.model_ready(s,allowRootChange=True)
            self.actor_write(s,'MoveTo',[{'form':'0x00000014'},s['offset'],0.,0.,False])
            self.actor_write(s,'EnableAI',[True]);self.actor_write(s,'SetRestrained',[True]);self.actor_write(s,'SetHeadTracking',[False])
            self.actor_write(s,'UnequipAll',[])
            self.model_ready(s,allowRootChange=True)
            self.guard(s,allowRootChange=True,loaded=True);time.sleep(.2);self.guard(s,loaded=True)
        self.capture('initial-human',False)
        self.transition(True);first=self.capture('first-wolf',True)
        for s in SPECS:
            accepted=self.claw(s,'Refresh',kind='bool',write=True);require(accepted is True,'Known Refresh request rejected')
        for s in SPECS:self.status_ready(s,True,allowRootChange=True)
        self.capture('refreshed-wolf',True,first)
        self.transition(False);self.capture('returned-human',False)
        self.transition(True);self.capture('second-wolf',True,first)
        for s in SPECS:
            old=self.roots[s['sex']];self.actor_write(s,'Disable',[False])
            self.poll('disabled and unloaded',lambda:self.guard(s,loaded=None)[1],lambda r:r['loaded3D'] is False,12)
            self.actor_write(s,'Enable',[False]);self.model_ready(s,allowRootChange=True)
            require(self.roots[s['sex']]!=old,'Enable did not establish fresh observed model')
        self.capture('reenabled-wolf',True,first)
        require(self.work_end-time.monotonic()>150,'Full owned save/load+final diagnostic reserve unavailable')
        pre=self.query();before_generation=pre['loadGeneration'];before_witness=self.snapshot()['sample']['loadEpoch']
        base={'scope':'owned-disposable-profile','saveTag':SAVE_TAG}
        save_args={'operation':'input.perform','request':{**base,'action':'save_game'}};platform.validate(save_args)
        saved=self.mutate('owned-save','platform',save_args,lambda r:r.get('save',{}).get('completed') is True and r['save'].get('ownedByAttempt') is True,cap=40)
        load_args={'operation':'input.perform','request':{**base,'action':'load_game'}};platform.validate(load_args)
        loaded=self.mutate('owned-load','platform',load_args,lambda r:all(r.get('lifecycle',{}).get(k) is True for k in ('worldReady','generationChanged','oldReferenceTagsInvalidated')),cap=50)
        self.s.phase('postload-human-origin-fsmp',self.end-time.monotonic())
        self.identities={};self.roots={};self.state['resolvedAfterLoad']=self.resolved()
        after=self.query();require(after['loadGeneration']>before_generation,'Fresh observer load generation did not advance')
        for s in SPECS:self.model_ready(s,allowRootChange=True)
        after_witness=self.snapshot()['sample']['loadEpoch'];require(after_witness>before_witness,'Witness native load epoch did not advance')
        self.state['loadEvidence']={'beforeGeneration':before_generation,'afterGeneration':after['loadGeneration'],
            'beforeWitnessEpoch':before_witness,'afterWitnessEpoch':after_witness,'save':saved,'load':loaded}
        self.capture('loaded-wolf',True,first);self.final_window()

def run(session,scenario,original_execute,*,configuration):
    case=Case(session,configuration);primary=None
    try:case.execute(scenario,original_execute)
    except BaseException as error:
        primary=error;case.state['primaryFailure']=repr(error)
        try:case.save()
        except BaseException:pass
        raise
    finally:
        case.cleanup=True
        try:
            if not case.state['unknownMutation'] and case.state['intent'] is None and case.state['semanticRacePending'] is None:
                case.restore_camera()
                for s in SPECS:
                    if case.enabled[s['sex']]:case.actor_write(s,'Disable',[False])
        except BaseException as error:
            case.state.setdefault('cleanupFailures',[]).append(repr(error));case.quarantine(repr(error))
            if primary is None:raise
        finally:
            case.state['finishedMonotonic']=time.monotonic()
            try:case.save()
            except BaseException:
                if primary is None:raise
