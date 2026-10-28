"""Qualify final split weight endpoints against a fitted physical triangle model.

Re-read every actual final skin point, normalized bind and absolute TRI field.
Preserve fixed physical triangle partitions only when both endpoint surfaces and
every signed field match. A mismatch never copies acceptance or fit results.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import types
import numpy as np


def capture_inputs(paths):
    return {Path(path).resolve():Path(path).read_bytes() for path in paths}


def revalidate_inputs(snapshots):
    for path,data in snapshots.items():
        if path.read_bytes()!=data:raise ValueError('Input changed during final geometry qualification: '+str(path))


def captured_json(path,snapshots):
    return json.loads(snapshots[Path(path).resolve()])


def captured_module(name,path,snapshots):
    """Execute exactly the helper bytes whose digest is retained, not a reread."""
    path=Path(path).resolve();module=types.ModuleType(name);module.__file__=str(path)
    module.__package__=name.rpartition('.')[0];sys.modules[name]=module
    exec(compile(snapshots[path],str(path),'exec'),module.__dict__)
    return module


def extract(fit,api,skeleton,nif0,nif1,records,shapes,nodes):
    meshes=[api.NifFile(str(path)) for path in (nif0,nif1)];chunks={node:[] for node in nodes}
    for name in shapes:
        for mesh in meshes:
            if name not in mesh.shape_dict:raise ValueError('Final selected shape missing: '+name)
        pair=[fit.triangle_regions(mesh.shape_dict[name],skeleton,records,nodes) for mesh in meshes]
        if set(pair[0])!=set(pair[1]):raise ValueError('Final weight endpoint ownership differs')
        for node,first in pair[0].items():
            second=pair[1][node]
            for key in ('vertices','fullRegionTriangles','restLBSMatricesSha256'):
                if first[2][key]!=second[2][key]:raise ValueError('Final endpoint topology or normalized skin matrices differ')
            if set(first[1])!=set(second[1]) or any(not np.array_equal(first[1][n],second[1][n]) for n in first[1]):
                raise ValueError('Final endpoint changes absolute TRI field')
            chunks[node].append((first,second[0]-first[0]))
    result={}
    for node,rows in chunks.items():
        if not rows:continue
        names=sorted({name for (row,_weight) in rows for name in row[1]})
        points=np.concatenate([row[0] for row,_ in rows]);weight=np.concatenate([w for _,w in rows])
        deltas={n:np.concatenate([row[1].get(n,np.zeros_like(row[0])) for row,_ in rows]) for n in names}
        faces=[];references=[];offset=0
        for (p,_,source),_weight in rows:
            faces.extend((np.asarray(source['fullRegionTriangles'])+offset).tolist());offset+=len(p)
            references.extend({'shape':source['shape'],'triangle':index} for index in source['sourceTriangleIndices'])
        result[node]={'points':points,'weightDeltas':weight,'deltas':deltas,'faces':np.asarray(faces,dtype=int),'faceReferences':references}
    return result


def face_signature(region,names):
    p=np.asarray(region['points']);f=np.asarray(region['faces'],dtype=int)
    fields=[p,np.asarray(region.get('weightDeltas',np.zeros_like(p)))]+[np.asarray(region['deltas'].get(n,np.zeros_like(p))) for n in names]
    return np.concatenate([field[f][:,:,None,:] for field in fields],axis=2)


def match_region(before,after,names,tolerance):
    # Signature order: vertex, field(P0,P1-P0,each TRI), XYZ. Correspondence uses
    # coarse unordered P0 locations; all accepted comparisons use unrounded data.
    left=face_signature(before,names);right=face_signature(after,names)
    if len(left)!=len(right):raise ValueError('Selected final skin triangle count changed')
    lower=right[:, :, 0, :].min(axis=1);upper=right[:, :, 0, :].max(axis=1)
    candidates=[];mapping=[];maximum=np.zeros((2+len(names),3))
    cyclic=((0,1,2),(1,2,0),(2,0,1))
    for index,row in enumerate(left):
        # An AABB comparison is only a necessary spatial prefilter. It cannot
        # lose a valid match at a rounded-key boundary, including duplicates.
        nearby=np.flatnonzero((abs(lower-row[:,0,:].min(axis=0)).max(axis=1)<=tolerance)&
                              (abs(upper-row[:,0,:].max(axis=0)).max(axis=1)<=tolerance))
        choices=[]
        for candidate in nearby:
            for permutation in cyclic:
                difference=abs(row-right[candidate,list(permutation)])
                error=float(difference.max())
                if error<=tolerance:choices.append((error,int(candidate),permutation,difference))
        if not choices:raise ValueError('No oriented full-field match within tolerance at source triangle '+str(index))
        candidates.append(sorted(choices,key=lambda value:(value[0],value[1],value[2])))
    # A one-to-one matching, rather than greedy nearest assignment, handles
    # coincident faces with different endpoint/TRI fields and ambiguous matches.
    owner={};chosen={}
    def assign(index,seen):
        for choice in candidates[index]:
            target=choice[1]
            if target in seen:continue
            seen.add(target)
            if target not in owner or assign(owner[target],seen):
                owner[target]=index;chosen[index]=choice;return True
        return False
    for index in sorted(range(len(left)),key=lambda i:(len(candidates[i]),i)):
        if not assign(index,set()):raise ValueError('No bijective oriented full-field triangle matching within tolerance')
    for index in range(len(left)):
        error,candidate,permutation,difference=chosen[index];maximum=np.maximum(maximum,difference.max(axis=0))
        mapping.append({'sourceTriangle':index,'finalTriangle':candidate,'finalReference':after['faceReferences'][candidate],
            'cyclicVertexPermutation':list(permutation),'maximumCoordinateOrFieldDifference':error})
    combination_bound=float(sum(field.max() for field in maximum))
    return mapping,{'triangles':len(left),'maximumRestCoordinateDifference':float(maximum[0].max()),
        'maximumIndependentWeightDeltaDifference':float(maximum[1].max()),
        'maximumAbsoluteTRIDeltaDifference':{n:float(maximum[i+2].max()) for i,n in enumerate(names)},
        'maximumCombinedCoordinateErrorBoundOverUnitInputBox':combination_bound,
        'maximumCombinedEuclideanErrorBoundOverUnitInputBox':float(np.sqrt(3)*combination_bound),
        'sameOrientedTrianglesAndFields':True}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    for sex in ('male','female'):
        for suffix in ('nif','nif-1','tri'):parser.add_argument('--'+sex+'-'+suffix,type=Path,required=True)
    parser.add_argument('--skeleton',type=Path,required=True);parser.add_argument('--pynifly',type=Path,required=True)
    parser.add_argument('--skin-shapes',default='body,head,head_CLAWHead');parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--tolerance',type=float,default=1e-4);args=parser.parse_args(argv)
    if not 0<args.tolerance<=.001:raise ValueError('Explicit equivalence tolerance must be <=.001')
    root=Path(__file__).resolve().parents[1];addon=args.pynifly.resolve()
    geometry=[getattr(args,sex+'_'+suffix) for sex in ('male','female') for suffix in ('nif','nif_1','tri')]+[args.skeleton]
    inputs=[args.source,args.source.parent/'physics-fit-model.h',args.source.parent/'physics-fit-fixtures.h',Path(__file__),root/'physics/fit-capsules.py',root/'physics/contact_fit.py',root/'physics/current_model.py',root/'scripts/tri_patch.py',root/'distribution/include/claw/PhysicsFit.h',*geometry,
            addon/'NiflyDLL.dll',*sorted((addon/'pyn').glob('*.py'))]
    # Capture once, before parsing the model or executing any selected helper.
    snapshots=capture_inputs(inputs);source=captured_json(args.source,snapshots)
    if source['schemaVersion']!=3 or not source.get('weightDependent'):raise ValueError('A complete independent-weight schema3 source model is required')
    sys.path[:0]=[str(root/'scripts'),str(root/'physics'),str(addon)]
    captured_module('contact_fit',root/'physics/contact_fit.py',snapshots)
    tri_patch=captured_module('tri_patch',root/'scripts/tri_patch.py',snapshots)
    fit=captured_module('claw_captured_fit_rebase',root/'physics/fit-capsules.py',snapshots)
    if fit._settings_module.SOURCE_BYTES != snapshots[(root/'physics/current_model.py').resolve()]:
        raise ValueError('Evaluator settings differ from their captured source bytes')
    from pyn import pynifly,niflydll
    if Path(pynifly.__file__).resolve()!=addon/'pyn/pynifly.py' or Path(niflydll.nifly_path).resolve()!=addon/'NiflyDLL.dll':
        raise ValueError('Loaded PyNifly interface/DLL differs from the explicitly captured dependency')
    pynifly.NifFile.Load(str(addon/'NiflyDLL.dll'));api=pynifly;out=fit.safe_output(args.out,inputs)
    old_skeleton=next(pin for pin in source['sourceInputs'] if Path(pin['path']).name=='skeleton.nif')
    if hashlib.sha256(snapshots[args.skeleton.resolve()]).hexdigest()!=old_skeleton['sha256']:raise ValueError('Final skeleton rest frames differ')
    skeleton=api.NifFile(str(args.skeleton));mapping={};summaries=[];names=source['morphs']
    for sex in ('male','female'):
        nodes=fit.NODES+(fit.P1_NODES if sex=='female' and source.get('femaleP1Contacts') else ())
        records=tri_patch.offsets(snapshots[getattr(args,sex+'_tri').resolve()])
        actual=extract(fit,api,skeleton,getattr(args,sex+'_nif'),getattr(args,sex+'_nif_1'),records,args.skin_shapes.split(','),nodes)
        expected={key.split('/',1)[1]:value for key,value in source['regions'].items() if key.startswith(sex+'/')}
        if set(actual)!=set(expected):raise ValueError('Final selected region set changed')
        if any(set(region['deltas'])-set(names) for region in actual.values()):raise ValueError('Final geometry introduced an unmodeled TRI dependency')
        for node,region in expected.items():
            matches,summary=match_region(region,actual[node],names,args.tolerance)
            mapping[sex+'/'+node]=matches;summaries.append({'sex':sex,'node':node,**summary})
    revalidate_inputs(snapshots)
    equality={'schemaVersion':1,'accepted':True,'tolerance':args.tolerance,'sourceModelIdentity':source['modelIdentity'],
        'sourceModelSha256':hashlib.sha256(snapshots[args.source.resolve()]).hexdigest(),'summaries':summaries,'mapping':mapping,
        'proof':'Every oriented physical source triangle matches an actual final triangle at P0, its independent P1-P0 field, and every absolute signed TRI field. Per-field differences and their conservative sum over the full unit coefficient/weight box are recorded. Fixed physical partitions are retained only after this actual input comparison. Numeric optimizer outputs can still be sensitive near ties; actual native fixtures remain a separate required check. No geometry mismatch is refitted or hidden.',
        'limit':'This is rest-skin input equivalence, not animation, actor/bone-scale, provider or game acceptance.'}
    out.mkdir(parents=True);marker=out/'FAILED-unverified-do-not-install';marker.write_text('Final input qualification incomplete. Do not install.\n',encoding='utf-8')
    proof=out/'geometry-input-equality.json';proof.write_text(json.dumps(equality,indent=2)+'\n',encoding='utf-8')
    result=copy.deepcopy(source);result['priorSourceInputs']=result['sourceInputs']
    result['sourceInputs']=[{'path':str(path),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for path,data in snapshots.items()]
    result['coveredShapes']=args.skin_shapes.split(',')
    result['ownership']='Ear/tail: complete faces touching a >=0.5 dominant target vertex. Female P1: complete faces touching actual positive side-matched minority P1 skin support. Every retained vertex uses all normalized skin weights.'
    result['excluded']='Fur/blend layers, skin outside explicit ear/tail and optional female P1 selection, animation/pose/actor or bone scale, actual provider/contact and Havok.'
    result['expectedCapsuleCounts']={sex:sum(slot.get(sex) is not None for slot in result['slots']) for sex in ('male','female')}
    result['finalInputQualification']={'accepted':True,'mappingFile':proof.name,'mappingSha256':hashlib.sha256(proof.read_bytes()).hexdigest(),
        'fixedPartitionProvenance':'regions[].sources retain original physical-partition references in priorSourceInputs; mapping links every triangle to actual final shape/index.',
        'numericCapsuleFixturesPreserved':True,'runtimeQualified':False,'gameValidated':False}
    fit.write_cpp_model(result,out/'physics-fit-model.h');fit.write_cpp_fixtures(result,out/'physics-fit-fixtures.h')
    for filename in ('physics-fit-model.h','physics-fit-fixtures.h'):
        emitted=(out/filename).read_bytes();original=(args.source.parent/filename).resolve()
        if emitted!=snapshots[original]:raise ValueError('Final fixed numeric model/fixture header changed after input-only qualification: '+filename)
        result['finalInputQualification'][filename+'Sha256']=hashlib.sha256(emitted).hexdigest()
    result['finalInputQualification']['nativeModelAndFixturesByteIdenticalToQualifiedPreview']=True
    result['finalInputQualification']['modelAndOwnHelpersConsumedFromCapturedBytes']=True
    revalidate_inputs(snapshots)
    (out/'fitted-capsules.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    revalidate_inputs(snapshots);marker.unlink()
    print(json.dumps({'accepted':True,'regions':len(summaries),'triangles':sum(s['triangles'] for s in summaries),'out':str(out),'modelIdentity':result['modelIdentity']}));return 0


if __name__=='__main__':raise SystemExit(main())
