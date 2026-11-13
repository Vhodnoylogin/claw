"""Pure reader for the single native witness JSON contract; no tools/files/game."""
import json,math

def integer(value,low=0):return type(value) is int and value>=low
def number(value):return type(value) in (int,float) and math.isfinite(value)
def parse(text,serial=None):
    def pairs(items):
        out={}
        for key,value in items:
            if key in out:raise ValueError('Duplicate JSON field')
            out[key]=value
        return out
    value=json.loads(text,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    if (value.get('schema')!='claw-fsmp-step-witness/2' or value.get('status') not in ('pending','ready')
        or not integer(value.get('requestSerial'),1) or not integer(value.get('pid'),1)
        or not integer(value.get('qpcFrequency'),1) or value.get('provider',{}).get('status')!='ready'
        or value['provider'].get('interfaceVersion')!=[2,0,0] or value['provider'].get('bulletVersion')!=[3,24,0]
        or value['provider'].get('bulletObjectsDereferenced') is not True
        or value['provider'].get('compiledBulletHeaderVersion')!=325
        or value['provider'].get('btUseSseInApi') is not True or value['provider'].get('btScalarBytes')!=4
        or value['provider'].get('bulletVersionDeclarationIsHardcoded') is not True
        or value['provider'].get('objectLayoutPdbGuid')!='FA13003A-6397-4D63-833B-71BE3CFFE2C2'
        or value['provider'].get('objectLayoutPdbSha256')!='1fcd447240416f1f40a4ddb0cdad3e2a16c0028d690a2a86b7bea8ed89b5006f'):raise ValueError('Witness admission refused/malformed')
    for version in ('interfaceVersion','bulletVersion'):
        if not all(type(v) is int for v in value['provider'][version]):raise ValueError('Version integers required')
    if serial is not None and value['requestSerial']!=serial:raise ValueError('Request serial changed')
    if value['status']=='pending':return value
    s=value.get('sample',{})
    if (s.get('phase')!='skse_main_thread_task' or s.get('physicsPhase')!='not_synchronized'
        or not integer(s.get('loadEpoch'),1) or not integer(s.get('sampledQpc'),1)
        or not integer(s.get('sampledThreadId'),1) or not integer(s.get('mainThreadIdRaw'))):raise ValueError('Snapshot phase/identity unavailable')
    for field in ('mainFreezeTime','mainFreezeNextFrame','mainGameActive','uiPaused','worldRootPresent','worldCameraPresent'):
        if type(s.get(field)) is not bool:raise ValueError('Native Boolean unavailable')
    if not integer(s.get('timerPauseCount')):raise ValueError('Timer pause count unavailable')
    for field in ('timerRealDelta','timerDelta','engineMultiplier'):
        if not number(s.get(field)):raise ValueError('Native finite timer unavailable')
    for side in ('pre','post'):
        e=s.get(side,{})
        if (e.get('coherent') is not True or not all(integer(e.get(k)) for k in ('count','lastQpc','lastThreadId','invalidEvents','droppedEvents'))
            or e['invalidEvents'] or e['droppedEvents'] or not number(e.get('lastTimeStep'))):raise ValueError('Counter sample is incoherent/invalid/dropped')
        if e['count'] and (e['lastTimeStep']<=0 or not e['lastQpc'] or not e['lastThreadId']):raise ValueError('Completed event lacks positive time/thread witness')
    validate_window(s.get('objectWindow'),s['loadEpoch'])
    return value

def pose(value):
    if not isinstance(value,dict) or set(value)!= {'world','rigidBody','inverseMass','flags'}:raise ValueError('Pose schema unavailable')
    world=value['world']
    if not isinstance(world,list) or len(world)!=12 or not all(number(v) for v in world):raise ValueError('Finite 3x3 basis + xyz required')
    if type(value['rigidBody']) is not bool or not number(value['inverseMass']) or value['inverseMass']<0 or not integer(value['flags']):raise ValueError('Mass/flags unavailable')
    return value

def validate_window(w,epoch,nonce=None):
    if not isinstance(w,dict) or w.get('status') not in ('idle','armed','collecting','complete'):raise ValueError('Window refused/incoherent/unavailable')
    if (w.get('coherent') is not True or w.get('objectCapacity')!=128 or w.get('pairedStepLimit')!=900
        or not integer(w.get('nonce')) or not integer(w.get('loadEpoch'))
        or w.get('callbackDrops')!=0 or type(w.get('callbackDrops')) is not int
        or w.get('failureCode')!=0 or type(w.get('failureCode')) is not int
        or not integer(w.get('pairedSteps')) or not 0<=w['pairedSteps']<=900
        or not integer(w.get('objectCount')) or not 0<=w['objectCount']<=128
        or type(w.get('awaitingPost')) is not bool):raise ValueError('Window bounds/failure unavailable')
    if nonce is not None and w['nonce']!=nonce:raise ValueError('Window nonce changed')
    if w['status']=='idle':
        if w['nonce'] or w['objectCount'] or w['pairedSteps']:raise ValueError('Malformed idle window')
    elif not w['nonce'] or w['loadEpoch']!=epoch:raise ValueError('Window load/nonce mismatch')
    rows=w.get('objects')
    if not isinstance(rows,list) or len(rows)!=w['objectCount']:raise ValueError('Object catalog size changed')
    if w['status']=='complete' and (w['pairedSteps']!=900 or w['awaitingPost']):raise ValueError('Incomplete terminal window')
    if w['status'] in ('collecting','complete'):
        if not rows or not integer(w.get('firstPreQpc'),1) or not integer(w.get('lastPreQpc'),1):raise ValueError('Started window lacks producer witness')
    if w['pairedSteps']:
        if (not integer(w.get('lastPostQpc'),1) or not integer(w.get('lastPostThreadId'),1)
            or not integer(w.get('lastPreThreadId'),1) or not number(w.get('lastTimeStep')) or w['lastTimeStep']<=0):raise ValueError('Window pair timing unavailable')
        # An in-flight pre may be newer than lastPost; complete pairs cannot.
        if not w['awaitingPost'] and w['lastPostQpc']<=w['lastPreQpc']:raise ValueError('Reversed pair time')
    for i,row in enumerate(rows):
        if row.get('token')!=i+1 or type(row.get('token')) is not int:raise ValueError('Opaque catalog token invalid')
        initial=pose(row.get('initialPre'));pose(row.get('lastPre'))
        if not number(row.get('maximumPairedDifference')) or row['maximumPairedDifference']<0:raise ValueError('Paired delta unavailable')
        if not integer(row.get('firstNonzeroStep')) or row['firstNonzeroStep']>w['pairedSteps']:raise ValueError('First delta step invalid')
        if w['pairedSteps']:
            last=pose(row.get('lastPost'))
            for key in ('rigidBody','inverseMass','flags'):
                if last[key]!=initial[key]:raise ValueError('Catalog metadata changed')
            lo,hi=row.get('minimumPostWorld'),row.get('maximumPostWorld')
            if not isinstance(lo,list) or not isinstance(hi,list) or len(lo)!=12 or len(hi)!=12 or not all(number(v) for v in lo+hi):raise ValueError('Finite world extrema required')
            if any(not a<=b<=c for a,b,c in zip(lo,last['world'],hi)):raise ValueError('World extrema do not contain last pose')
        if row['firstNonzeroStep']:
            if not integer(row.get('firstNonzeroPreQpc'),1) or not integer(row.get('firstNonzeroPostQpc'),1) or row['firstNonzeroPostQpc']<=row['firstNonzeroPreQpc']:raise ValueError('First pair QPC unavailable')
            pair=row.get('firstNonzeroPair')
            if not isinstance(pair,dict):raise ValueError('Missing first pair')
            a,b=pose(pair.get('pre')),pose(pair.get('post'))
            if a['world']==b['world']:raise ValueError('Nonzero pair has zero delta')
        elif row.get('firstNonzeroPair') is not None:raise ValueError('Unexpected first pair')
    return w

def compare(first,second):
    if first['status']!='ready' or second['status']!='ready':raise ValueError('Two ready snapshots required')
    a,b=first['sample'],second['sample']
    if (first['pid']!=second['pid'] or first['qpcFrequency']!=second['qpcFrequency']
        or a['loadEpoch']!=b['loadEpoch'] or b['sampledQpc']<=a['sampledQpc']
        or first['requestSerial']==second['requestSerial']):raise ValueError('Cross-process/load or reused/reversed snapshot')
    growth={name:b[name]['count']-a[name]['count'] for name in ('pre','post')}
    if any(v<0 for v in growth.values()):raise ValueError('Counter regressed')
    return {'preStepDelta':growth['pre'],'postStepDelta':growth['post'],
        'providerCompletedStepsObserved':growth['post']>0,
        'seconds':(b['sampledQpc']-a['sampledQpc'])/first['qpcFrequency'],
        'targetActorOrMotionQualified':False}
