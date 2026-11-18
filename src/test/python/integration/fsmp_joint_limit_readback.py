"""Pure one-lower-limit functional checker. No transport, clocks or mutations.
The caller owns fresh actor/process/module/fixture and morph-state admission.
"""
import math
from pathlib import Path
import importlib.util

if __package__:
    from . import fsmp_probe as probe, fsmp_cached_world as cached
else:
    import fsmp_probe as probe
    import fsmp_cached_world as cached

# One maintained native witness validator; do not fork its parsing contract.
_validator = Path(__file__).resolve().parents[4] / "src/test/cpp/fsmp_step_witness/validate_snapshot.py"
_spec = importlib.util.spec_from_file_location("claw_fsmp_joint_limit_witness_snapshot", _validator)
witness = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(witness)

PARENTS=('NPC L PreBreast P1','NPC R PreBreast P1')
DRIVERS=('NPC L Breast P1','NPC R Breast P1')
STAGES=('initialPre','lastPre','lastPost')
TRANSLATION_MATCH=.002
ROTATION_MATCH=1e-5
JOINT_TOLERANCE=.005
LOWER_LEFT=.05
UPPER_LEFT=.15


def require(ok,message):
    if not ok:raise ValueError(message)


def unit(t):
    value=probe.transform(t)
    require(abs(value['scale']-1.)<=1e-5,'Actual unit frame required')
    return value


def pose_transform(pose):
    world=probe.numbers(pose['world'],12)
    return unit({'rotationRowMajor':world[:9],'translation':world[9:],'scale':1.})


def joint_frame(anchor,driver,rest_local):
    """inv(A_world) * B_world * inv(B_local_rest), unit exact-COM frameInA.
    Uses the pinned direct A->B hierarchy; raw origins omit the pivot lever arm.
    """
    anchor,driver,rest=unit(anchor),unit(driver),unit(rest_local)
    rel=probe.relative(driver,anchor)
    r,s=rel['rotationRowMajor'],rest['rotationRowMajor']
    rot=[sum(r[i*3+k]*s[j*3+k] for k in range(3)) for i in range(3) for j in range(3)]
    xyz=[rel['translation'][i]-sum(rot[i*3+j]*rest['translation'][j] for j in range(3)) for i in range(3)]
    return {'rotationRowMajor':rot,'translation':xyz,'scale':1.}


def _map_one(row,window,rest,expected_inverse_mass):
    require(set(rest)==set(DRIVERS),'Exact bilateral rest frames required')
    require(set(expected_inverse_mass)==set(DRIVERS),'Exact bilateral mass expectation required')
    dynamic=cached.paused_match(row,window,'female')
    require(dynamic['status']=='unique-paused-dynamic11-match','Full dynamic11 association unavailable')
    objects={o['token']:o for o in window['objects']}
    mapping={}
    for parent,driver in zip(PARENTS,DRIVERS):
        d=next(r for r in dynamic['dynamicBodies'] if r['node']==driver)
        token=d['candidates'][0]['token'];mapping[driver]=token
        expected=expected_inverse_mass[driver]
        require(type(expected) in (int,float) and expected in (10.,20.),'Explicit retained/original P1 mass expectation required')
        require(all(objects[token][stage]['rigidBody'] is True and objects[token][stage]['inverseMass']==expected and
                    objects[token][stage]['flags']&3==0 for stage in STAGES),'Actual P1 mass/flags differ')
        actual=row['nodes'][parent]['world'];candidates=[]
        for o in window['objects']:
            p=o['lastPost']
            if p['rigidBody'] is True and p['inverseMass']==0 and p['flags']&3==2:
                if probe.max_delta(p['world'][9:],actual['translation'])<=TRANSLATION_MATCH and probe.max_delta(p['world'][:9],actual['rotationRowMajor'])<=ROTATION_MATCH:
                    candidates.append(o['token'])
        require(len(candidates)==1,'Unique positive kinematic-parent association unavailable')
        mapping[parent]=candidates[0]
        require(probe.max_delta(row['nodes'][driver]['local']['translation'],unit(rest[driver])['translation'])<=TRANSLATION_MATCH and
                probe.max_delta(row['nodes'][driver]['local']['rotationRowMajor'],rest[driver]['rotationRowMajor'])<=ROTATION_MATCH,
                'Actual driver local differs from frozen direct-parent rest frame')
        require(all(objects[candidates[0]][stage]['rigidBody'] is True and objects[candidates[0]][stage]['inverseMass']==0 and
                    objects[candidates[0]][stage]['flags']&3==2 for stage in STAGES),'Kinematic parent metadata changed')
    require(len(set(mapping.values()))==4,'Four-role association is not injective')
    coordinates={stage:{driver:joint_frame(pose_transform(objects[mapping[parent]][stage]),pose_transform(objects[mapping[driver]][stage]),rest[driver])['translation']
                        for parent,driver in zip(PARENTS,DRIVERS)} for stage in STAGES}
    return {'tokens':mapping,'jointCoordinates':coordinates,'dynamic11':dynamic}


def pair(world_a,world_b,native_a,native_b,*,reference,base,rest_local,expected_inverse_mass):
    require(cached.paused_signature(native_a)==cached.paused_signature(native_b),'Pause/window state changed')
    require(native_a['pid']==native_b['pid'] and native_a['qpcFrequency']==native_b['qpcFrequency'] and
            native_b['sample']['sampledQpc']>native_a['sample']['sampledQpc'] and native_a['requestSerial']!=native_b['requestSerial'],
            'Native process/clock/request progression unavailable')
    rows=[];results=[]
    for raw,native in ((world_a,native_a),(world_b,native_b)):
        require(native['status']=='ready','Ready native sample required')
        witness.validate_window(native['sample']['objectWindow'],native['sample']['loadEpoch'])
        row=probe.snapshot(raw,reference,'female');actor=row['guard']['actor']
        require(actor['baseForm']==base and actor['race']==actor['baseRace']=='0x000CDD84','Owned base/wolf identity differs')
        require(abs(row['guard']['scale']-1.)<=1e-5 and abs(row['root']['scale']-1.)<=1e-5 and
                all(abs(n[s]['scale']-1.)<=1e-5 for n in row['nodes'].values() for s in ('local','world')),'Actual unit actor/root/local/WORLD scales required')
        rows.append(row);results.append(_map_one(row,native['sample']['objectWindow'],rest_local,expected_inverse_mass))
    require(rows[0]['guard']==rows[1]['guard'] and rows[1]['sample']>rows[0]['sample'] and rows[1]['time']-rows[0]['time']>=200_000_000,
            'Actor/root identity or producer progression differs')
    require(results[0]['tokens']==results[1]['tokens'],'Run-local role tokens changed')
    # Native pause is the actual shared-physics-pose boundary; only main-task
    # bracketing observations progress. It does not claim advancing paused steps.
    return {'status':'paused-four-role-joint-frame-associated','reference':reference,'base':base,
            'pid':native_a['pid'],'loadEpoch':native_a['sample']['loadEpoch'],'nonce':native_a['sample']['objectWindow']['nonce'],
            'pairedStepsAtPause':native_a['sample']['objectWindow']['pairedSteps'],'expectedInverseMass':expected_inverse_mass,
            'A':results[0],'B':results[1]}


def score_limit(associated):
    """Frozen prospective gate. Never accepts the old .10/.05 mass capture."""
    require(associated['expectedInverseMass']==dict.fromkeys(DRIVERS,20.),'Prospective case requires original .05/.05 masses')
    for mark in ('A','B'):
        for stage,coords in associated[mark]['jointCoordinates'].items():
            left,right=coords[DRIVERS[0]],coords[DRIVERS[1]]
            require(abs(left[0]-LOWER_LEFT)<=JOINT_TOLERANCE,'Left positive lower-limit rest correspondence absent')
            require(abs(right[0])<=JOINT_TOLERANCE,'Unchanged right P1 rest control moved')
            require(all(abs(v)<=.15+JOINT_TOLERANCE for xyz in (left,right) for v in xyz[1:]),'Unchanged joint y/z interval exceeded')
    # Settled native initial and current poses, not two copies of a paused pose.
    for driver in DRIVERS:
        before=associated['A']['jointCoordinates']['initialPre'][driver]
        after=associated['A']['jointCoordinates']['lastPost'][driver]
        require(probe.max_delta(before,after)<=JOINT_TOLERANCE,'Window was not settled before pause')
    return {'status':'left-positive-lower-limit-functional-correspondence-observed','leftTarget':LOWER_LEFT,
            'leftUpperUnchanged':UPPER_LEFT,'jointTolerance':JOINT_TOLERANCE,'associated':associated,
            'scope':'One original-mass unit-scale rest-constraint outcome; no exact live limit getter or general solver calibration'}


def score_case(associated,final_native,rest_local):
    result=score_limit(associated)
    require(final_native['status']=='ready' and final_native['pid']==associated['pid'],'Final native process differs')
    sample=final_native['sample'];window=sample['objectWindow']
    witness.validate_window(window,sample['loadEpoch'])
    require(sample['loadEpoch']==associated['loadEpoch'] and window['nonce']==associated['nonce'] and
            window['status']=='complete' and window['pairedSteps']==900 and window['pairedSteps']>associated['pairedStepsAtPause'],
            'Same final complete900-pair window required')
    require(sample['mainFreezeTime'] is False and sample['uiPaused'] is False,'Original normal clock must be restored before completion')
    objects={o['token']:o for o in window['objects']};tokens=associated['A']['tokens'];coords={}
    for stage in STAGES:
        coords[stage]={}
        for parent,driver in zip(PARENTS,DRIVERS):
            p,d=objects[tokens[parent]][stage],objects[tokens[driver]][stage]
            require(p['inverseMass']==0 and p['flags']&3==2 and d['inverseMass']==20 and d['flags']&3==0,'Final original-mass/kinematic metadata differs')
            coords[stage][driver]=joint_frame(pose_transform(p),pose_transform(d),rest_local[driver])['translation']
        require(abs(coords[stage][DRIVERS[0]][0]-LOWER_LEFT)<=JOINT_TOLERANCE and abs(coords[stage][DRIVERS[1]][0])<=JOINT_TOLERANCE,
                'Completed-window joint correspondence differs')
        require(all(abs(v)<=.15+JOINT_TOLERANCE for xyz in coords[stage].values() for v in xyz[1:]),'Completed-window y/z interval exceeded')
    for driver in DRIVERS:
        require(probe.max_delta(coords['initialPre'][driver],coords['lastPost'][driver])<=JOINT_TOLERANCE,'Completed-window rest displacement did not stay settled: '+driver)
    result['completed900JointCoordinates']=coords
    return result
