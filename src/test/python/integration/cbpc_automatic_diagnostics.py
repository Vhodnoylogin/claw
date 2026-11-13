"""Known-returned semantic checks; never a Session.tool replacement.

No alternate engine task, node write or provider-state API. Only the retained
current-process logger and copied actual world observations are used.
"""
from pathlib import Path
import hashlib,json,time
import fsmp_probe as scene
from skyrim_autotest.collection import snapshot_log
from skyrim_autotest import native
LOG=Path('C:/Users/radim/Documents/My Games/Skyrim Special Edition/SKSE/CBPC-Collision.log')
LIMIT=64*1024*1024
import cbpc_nominal as nominal

def fresh_log_before_launch(session):
    # Same exact original snapshot/owned-empty/current-file recipe as the
    # previously reviewed preflight; only executed after later machine/game GO.
    scene.require(not any(p['name'].casefold() in ('skyrimse.exe','skyrimvr.exe','modorganizer.exe') for p in native.processes()),'No game/manager may own provider log before cold preparation')
    scene.require(any(Path(p).resolve()==LOG.resolve() for p in session.state['configuration']['extra_files']),'Provider log absent from Session restoration scope')
    scene.require('cbpcLogFreshness' not in session.state,'No cold-log preparation replay')
    session.snapshot(LOG)
    rows=[r for r in session.state['snapshots'] if Path(r['path']).resolve()==LOG.resolve()]
    scene.require(len(rows)==1,'Unique durable original provider-log snapshot required')
    original=rows[0]
    if original['exists']:scene.require(hashlib.sha256(Path(original['backup']).read_bytes()).hexdigest()==original['sha256'],'Provider-log original backup changed')
    state={'originalSnapshot':original.copy(),'intent':'empty-before-cold-owned-launch','beforeMonotonic':time.monotonic()}
    session.state['cbpcLogFreshness']=state;session.save()
    session.write(LOG,b'')
    scene.require(LOG.is_file() and LOG.read_bytes()==b'','Fresh provider log must be empty before launch')
    st=LOG.stat();state.update(emptyVerified=True,emptyVerifiedMonotonic=time.monotonic(),fileIdentity={'device':st.st_dev,'inode':st.st_ino})
    session.save();(session.dir/'cbpc-log-freshness.json').write_text(json.dumps(state,indent=2),encoding='utf8')

ledger=nominal.provider_ledger

def first_transform_binding(session,subject,directory):
    """One fresh-process log prefix before Refresh/load/any provider control.

    Constructor/update records establish this narrow diagnostic gate, never
    selective response, loaded-node inventory or animation qualification.
    """
    fresh=session.state.get('cbpcLogFreshness',{})
    scene.require(fresh.get('emptyVerified') is True,'Fresh cold-process log admission required')
    scene.require(LOG.is_file() and LOG.stat().st_size<LIMIT,'Bounded fresh provider log required')
    receipt=snapshot_log(LOG,directory/'first-wolf-provider.log')
    scene.require(receipt['fileIdentity']==fresh['fileIdentity'],'First-transform provider log identity changed')
    data=(directory/'first-wolf-provider.log').read_bytes()
    rows=ledger(data,scene.drivers(subject['sex']),subject)
    result={'scope':'first-transform constructor/update diagnostics only; response unobserved',
            'subject':subject.copy(),'receipt':receipt,'ledger':rows,
            'allDeclaredNodes':all(r['insertions']>=1 and r['updates']>=1 for r in rows.values()),
            'providerControlsBeforeThisPrefix':[],'runtimeQualified':False}
    (directory/'first-wolf-provider.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    scene.require(result['allDeclaredNodes'],'Automatic first-transform constructor/update binding not observed; no repair Start/Reload')
    return result

def world_follow(raw,baseline,wanted,reference='0x0D000900',sex='female'):
    row=scene.snapshot(raw,reference,sex)
    scene.require(row['guard']==baseline['guard'],'Actual actor/root/source/incarnation changed')
    scene.reference_excitation(row,baseline,wanted)
    delta=[a-b for a,b in zip(row['position'],baseline['position'])]
    root=[a-b for a,b in zip(row['root']['translation'],baseline['root']['translation'])]
    anchors={name:[a-b for a,b in zip(row['nodes'][name]['world']['translation'],baseline['nodes'][name]['world']['translation'])]
        for name in dict.fromkeys(scene.anchors(sex).values())}
    evidence={'sampleId':raw['sampleId'],'producerMonotonicNs':raw['producerMonotonicNs'],'wanted':wanted,
        'actualReferenceDelta':delta,'actualRootDelta':root,'actualAnchorWorldDeltas':anchors}
    scene.require(scene.max_delta(row['angles'],baseline['angles'])<=1e-5 and scene.max_delta(row['root']['rotationRowMajor'],baseline['root']['rotationRowMajor'])<=1e-5 and abs(row['root']['scale']-baseline['root']['scale'])<=1e-5,'Unexpected actor/root rotation/scale')
    scene.require(all(scene.max_delta(v,delta)<=.025 for v in anchors.values()),'Actual anchor WORLD displacement does not follow whole-actor input')
    return evidence

class Diagnostics:
    def __init__(self,session,reference,sex,admitted,*,deadline,subject):
        scene.require(subject==nominal.human_subject(reference,sex,subject["providerActorName"]),"Changed human-origin logging scope")
        self.subject=subject.copy()
        self.session,self.reference,self.sex,self.deadline=session,reference,sex,deadline
        self.nodes=tuple(scene.anchors(sex));self.baseline=scene.snapshot(admitted,reference,sex)
        self.directory=session.dir/'graphless-feasibility';self.directory.mkdir(exist_ok=False)
        fresh=session.state.get('cbpcLogFreshness',{})
        scene.require(fresh.get('emptyVerified') is True and fresh.get('emptyVerifiedMonotonic',float('inf'))<time.monotonic(),'Fresh empty-before-owned-launch log proof required')
        target=session.state.get('game')
        scene.require(target and any(r['role']=='game' and r['identity']==target for r in session.state.get('owned',[])) and native.alive(target),'Exact owned live game required')
        self.previous=None;self.starts={};self.firstIdentity=None
        self.state={'status':'pending','scope':'graphless AI-on feasibility, not contact fit','ownedGame':target.copy(),'logFreshness':fresh.copy(),
            'prefixes':{},'worldChecks':[],'completedPhases':[],'semanticFailures':[],'bindingInventoryObserved':False,
            'stagedDevbenchSha256':'39a85b56b0b11d286cdbd7020438284b317450ac12018ef696e924be10932573',
            'restoredDevbenchSha256':'fbea59e68875309996609a03f27980fd63b71a363cf06534ca4a2129cfc58992'}
        self.persist()
    def persist(self):(self.directory/'state.json').write_text(json.dumps(self.state,indent=2),encoding='utf8')
    def prefix(self,label):
        scene.require(time.monotonic()<self.deadline,'Bounded graphless diagnostics deadline')
        scene.require(LOG.is_file() and LOG.stat().st_size<LIMIT,'Bounded current-process provider log required')
        target=self.directory/(label+'.log');receipt=snapshot_log(LOG,target);data=target.read_bytes()
        scene.require(time.monotonic()<self.deadline,'Provider prefix completed after deadline')
        identity=receipt['fileIdentity']
        if self.previous is not None:scene.require(data.startswith(self.previous) and identity==self.firstIdentity,'Current provider strict prefix/file identity continuity lost')
        else:
            fresh=self.state['logFreshness']['fileIdentity']
            scene.require(identity==fresh,'Provider log replaced after owned-empty admission')
            self.firstIdentity=identity
        self.previous=data
        row={'receipt':receipt,'ledger':ledger(data,self.nodes,self.subject),'bytes':len(data),'observedMonotonic':time.monotonic()}
        self.state['prefixes'][label]=row;self.persist();return row
    def phase_settled(self,phase):
        try:
            row=self.prefix(phase+'-start');self.starts[phase]=row
            scene.require(all(v['insertions']>=1 and v['updates']>=1 for v in row['ledger'].values()),'Current-process declared-node constructor/update diagnostics missing')
        except BaseException as error:
            self.state['semanticFailures'].append({'phase':phase,'where':'known-settled-phase','error':str(error)});self.persist();raise
    def world_follow(self,raw,baseline,wanted):
        # Persist actual raw sample first even when the known numeric gate fails.
        try:
            row=world_follow(raw,baseline,wanted,self.reference,self.sex)
            self.state['worldChecks'].append(row);self.persist()
        except BaseException as error:
            self.state['semanticFailures'].append({'where':'known-returned-world','sampleId':raw.get('sampleId'),'producerMonotonicNs':raw.get('producerMonotonicNs'),'wanted':wanted,'error':str(error),'raw':raw});self.persist();raise
    def phase_complete(self,phase):
        try:
            row=self.prefix(phase+'-end')
            if phase in ('active','restarted'):
                scene.require(all(row['ledger'][n]['updates']>self.starts[phase]['ledger'][n]['updates'] for n in self.nodes),'Provider updates did not continue for all declared current-process nodes')
            self.state['completedPhases'].append(phase)
            if self.state['completedPhases']==['active','stopped','restarted'] and len(self.state['worldChecks'])==75:self.state['status']='all-three-windows-provider-updates-and-world-follow-observed'
            self.persist()
        except BaseException as error:
            self.state['semanticFailures'].append({'phase':phase,'where':'known-completed-phase','error':str(error)});self.persist();raise
