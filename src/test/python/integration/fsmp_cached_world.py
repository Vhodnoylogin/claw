"""Pure cached-WORLD guards for the qualified nonshipping FSMP diagnostic.

No transport, engine actions, solver writes or phase assumptions live here.
"""
from pathlib import Path
import math
import fsmp_probe as probe

MODULE_HASHES={
 'hdtsmp64.dll':'5290e2a8c3ddc4c13fecfd08234ff455f50c6a9ca42dcd381cde158631446672',
 'clawfsmpwitness.dll':'adfd1e34bb544a384a23c800065a7b76c4c7062b8e841b5526431f9f1c35d294',
 'clawdistribution.dll':'ccf7718d90f99ebc176b4231566fa6cc1cbbb117741de6e1babe267ab508503b',
 'devbench.dll':'39a85b56b0b11d286cdbd7020438284b317450ac12018ef696e924be10932573',
 'skyrimworldobserver.dll':'7e81410b2b446f6606715e3f4b0f00466a1eac655d4b1789c32a77aaf5260c0a'}

def require(ok,message):
    if not ok:raise ValueError(message)

def module_admission(modules):
    import hashlib
    names={Path(p).name.casefold() for p in modules}
    require(not names&{'cbp.dll','livingphysique.dll','modelswapper.dll','clawnativeleftp1test.dll'},'Competing loaded module')
    rows=[]
    for name,digest in MODULE_HASHES.items():
        paths=[Path(p) for p in modules if Path(p).name.casefold()==name]
        require(len(paths)==1 and paths[0].is_absolute() and paths[0].is_file(),'Exact loaded module path unavailable: '+name)
        actual=hashlib.sha256(paths[0].read_bytes()).hexdigest()
        require(actual==digest,'Actual loaded module bytes differ: '+name)
        rows.append({'name':name,'path':str(paths[0]),'resolvedPath':str(paths[0].resolve()),'sha256':actual})
    return rows

def _base_completed(raw,kind):
    return (isinstance(raw,dict) and raw.get('called') is True and not raw.get('error') and not raw.get('isError')
        and str(raw.get('returnedType','')).casefold()==kind and 'returned' in raw
        and (raw['returned'] is None if kind=='none' else type(raw['returned']) is str if kind=='string' else True))

def finite(x):return type(x) in (int,float) and math.isfinite(x)

def completed(raw,kind):
    if not _base_completed(raw,kind):return False
    value=raw['returned']
    return (kind not in ('int','bool','float') or
        (kind=='int' and type(value) is int) or (kind=='bool' and type(value) is bool) or
        (kind=='float' and finite(value)))

def console_completed(raw):
    return (type(raw) is dict and raw.get('completed') is True and raw.get('queued') is False
        and raw.get('capturing') is True and raw.get('command')=='tfc 1' and not raw.get('error') and not raw.get('isError'))

def camera_flags(raw):
    require(type(raw) is dict and type(raw.get('freeCam')) is bool and type(raw.get('freeCamOwned')) is bool
        and type(raw.get('stateId')) is int and type(raw.get('pov')) is str
        and type(raw.get('orbit')) is dict and type(raw['orbit'].get('on')) is bool,'Actual camera flags unavailable')
    return {'freeCam':raw['freeCam'],'freeCamOwned':raw['freeCamOwned'],'stateId':raw['stateId'],'pov':raw['pov'],'orbitOn':raw['orbit']['on']}

def paused_signature(value):
    s=value['sample'];w=s['objectWindow']
    require(s['mainFreezeTime'] is True and s['uiPaused'] is False and w['status']=='collecting'
        and w['coherent'] is True and w['awaitingPost'] is False and w['pairedSteps']>20,'Paused coherent in-progress window unavailable')
    return {'loadEpoch':s['loadEpoch'],'pre':s['pre'],'post':s['post'],'lastPostQpc':w['lastPostQpc'],
        'pairedSteps':w['pairedSteps'],'objects':[(o['token'],o['lastPost']) for o in w['objects']]}

def paused_match(row,window,sex):
    require(sex in ("female","male"),"Explicit female/male role required")
    matches=[]
    for name in probe.drivers(sex):
        expected=row['nodes'][name]['world'];candidates=[]
        for o in window['objects']:
            p=o['lastPost'];world=p['world']
            if p['rigidBody'] is True and p['inverseMass']>0 and not p['flags']&3:
                xyz=probe.max_delta(world[9:],expected['translation']);rot=probe.max_delta(world[:9],expected['rotationRowMajor'])
                if xyz<=.002 and rot<=1e-5:candidates.append({'token':o['token'],'xyzMaxError':xyz,'rotationMaxError':rot})
        matches.append({'node':name,'candidates':candidates})
    tokens=[r['candidates'][0]['token'] for r in matches if len(r['candidates'])==1]
    return {'status':f'unique-paused-dynamic{len(probe.drivers(sex))}-match' if len(tokens)==len(probe.drivers(sex)) and len(set(tokens))==len(probe.drivers(sex)) else 'unavailable',
        'dynamicBodies':matches,'fixedAnchors':{n:row['nodes'][n]['world'] for n in dict.fromkeys(probe.anchors(sex).values())},
        'kinematicExactMatchRequired':False,'translationTolerance':.002,'rotationTolerance':1e-5,
        'centerOfMass':'identity from exact XML/default source','normalMotionQualified':False,'physicsAcceptance':False}
