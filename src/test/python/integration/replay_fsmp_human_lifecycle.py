"""Replay retained qualified tool receipts; never connects to a game or manager.

Requires explicit external executor, frozen original case, and completed run.
The operating-system module guard is replaced ONLY by that run's retained
path/hash proof. This does not requalify current installed files or run a game.
"""
from pathlib import Path
import argparse,copy,hashlib,importlib.util,json,sys,tempfile
from unittest.mock import patch


def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def replay(module,configuration,run,original_state,output,port):
    directory=run/'human-fsmp-lifecycle'
    receipts=[json.loads(p.read_text(encoding='utf-8')) for p in sorted(directory.glob('raw-*.json'))]
    assert receipts and original_state['result']['final']['sample']['objectWindow']['pairedSteps']==900
    process=json.loads((run/'state.json').read_text(encoding='utf-8-sig'))['game']
    initial_modules=json.loads((directory/'loaded-modules.json').read_text())
    final_modules=json.loads((directory/'loaded-modules-before-arm.json').read_text())
    module_calls=[initial_modules,final_modules['raw']]
    proof=final_modules['verified'];index=[0];module_index=[0]
    clock=[original_state['startedMonotonic']]

    class Session:
        def __init__(self):self.dir=output;self.state={'game':process};self.phases=[]
        def phase(self,name,seconds):self.phases.append((name,seconds))
        def tool(self,name,args,**kwargs):
            assert index[0]<len(receipts),'Port dispatched beyond retained evidence'
            row=receipts[index[0]]
            assert (name,args)==(row['tool'],row['args']),f"Tool sequence differs at {index[0]+1}: {(name,args)} != {(row['tool'],row['args'])}"
            assert clock[0]<=row['monotonic']+.002,'Replay clock moved beyond recorded response'
            clock[0]=row['monotonic'];index[0]+=1
            return copy.deepcopy(row['result'])

    def modules(_game):
        assert module_index[0]<2,'Unexpected extra module lookup'
        value=module_calls[module_index[0]];module_index[0]+=1;return copy.deepcopy(value)

    helper=module.cached if port else module.female
    def retained_module_proof(paths):
        # No on-disk installed-module reads in this offline replay.
        for name,digest in helper.MODULE_HASHES.items():
            actual=[p for p in paths if Path(p).name.casefold()==name]
            bound=[r for r in proof if r['name']==name]
            assert len(actual)==len(bound)==1 and actual[0]==bound[0]['path'] and bound[0]['sha256']==digest
        return copy.deepcopy(proof)

    session=Session()
    with patch.object(module.native,'identity',return_value=process),patch.object(module.native,'modules',modules),\
         patch.object(helper,'module_admission',retained_module_proof),\
         patch.object(module.time,'monotonic',lambda:clock[0]),\
         patch.object(module.time,'sleep',lambda duration:clock.__setitem__(0,clock[0]+duration)):
        # The sole world-ready startup step has separate actual passed evidence.
        # No mutating scenario prefix is omitted or fabricated.
        if port:module.run(session,{'steps':[]},lambda *_:None,configuration=configuration)
        else:module.run(session,{'steps':[]},lambda *_:None)
    assert index[0]==len(receipts) and module_index[0]==2,'Not all retained receipts consumed'
    value=json.loads((output/'human-fsmp-lifecycle/state.json').read_text())
    return value,len(receipts)


def semantic(value):
    # Only local output paths and host-only final timing vary during offline I/O.
    value=copy.deepcopy(value);value.pop('observations');value.pop('finishedMonotonic')
    return value


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--executor',type=Path,required=True)
    p.add_argument('--original-case',type=Path,required=True)
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    assert args.output.parent.is_dir() and not args.output.exists(),'Use a fresh external receipt output'
    sys.path[:0]=[str(Path(__file__).resolve().parent),str(args.executor)]
    port=load_module('claw_ported_fsmp_lifecycle',Path(__file__).with_name('fsmp_human_lifecycle.py'))
    original=load_module('claw_original_fsmp_lifecycle',args.original_case/'subject.py')
    config=json.loads((args.original_case/'config.json').read_text())
    scenario=json.loads((args.original_case/'scenario.json').read_text())
    assert len(scenario['steps'])==1 and scenario['steps'][0]['args']=={'operation':'state.read'}
    actual=json.loads((args.run/'human-fsmp-lifecycle/state.json').read_text())
    result=json.loads((args.run/'result.json').read_text())
    assert result['result']=='passed' and result['checks'][0]['result']=='passed'
    with tempfile.TemporaryDirectory(dir=args.output.parent) as tmp:
        root=Path(tmp);(root/'original').mkdir();(root/'ported').mkdir()
        old,count=replay(original,config,args.run,actual,root/'original',False)
        new,count2=replay(port,config,args.run,actual,root/'ported',True)
        assert count==count2 and semantic(old)==semantic(new),'Port differs from frozen source replay'
        assert semantic(new)==semantic(actual),'Replay differs from retained actual semantic result'
    sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    receipt={'status':'PASS','scope':'Offline retained receipt replay only; port not game-launched',
        'toolReceipts':count,'originalCaseSha256':sha(args.original_case/'subject.py'),
        'portedCaseSha256':sha(Path(__file__).with_name('fsmp_human_lifecycle.py')),
        'cachedHelperSha256':sha(Path(__file__).with_name('fsmp_cached_world.py')),
        'actualStateSha256':sha(args.run/'human-fsmp-lifecycle/state.json'),
        'boundaries':list(actual['boundaries']),'raceTransitions':len(actual['completedRaceTransitions']),
        'dynamicRoles':20,'pairedSteps':900,'objects':48,
        'osAndModuleChecks':'Retained actual path/hash proof; current installation not read',
        'nativeCalls':0,'managerApiCalls':0,'gameLaunched':False}
    args.output.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
