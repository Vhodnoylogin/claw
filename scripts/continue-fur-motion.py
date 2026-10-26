"""Continue the pinned canonical collar/P1/belly composition into other fur layers.

This is an explicit new experiment using the same unweakened numeric gates as
fur_motion. It does not change that earlier builder's frozen input contract.
"""
from pathlib import Path
import argparse
import json
import shutil
import numpy as np
import breast_rig as rig
import fur_motion as fur
import surface_collar as surface
from collar_weights import write_active_weights

ROOT=Path(__file__).resolve().parents[1]


def build(body,tri,skeleton,profile_file,output,pynifly=None):
    inputs=[Path(p).resolve(strict=True) for p in (body,tri,skeleton,profile_file)]
    body,tri,skeleton,profile_file=inputs
    profile=json.loads(profile_file.read_text())
    if profile!=json.loads((ROOT/'recipes/fur-motion-continuation.json').read_text()):raise ValueError('Unreviewed continuation profile')
    for path,key in ((body,'bodyNifSha256'),(tri,'triSha256'),(skeleton,'skeletonSha256')):
        if rig.sha256(path)!=profile['inputs'][key]:raise ValueError('Pinned input changed: '+key)
    out=rig.safe_output(output,inputs);api,Trip,dependency=rig.load_pynifly(pynifly)
    files=inputs+[Path(__file__),ROOT/'recipes/breast-rig-collar.json',ROOT/'recipes/breast-rig.json',
                  ROOT/'recipes/fur-motion-continuation.json',ROOT/'scripts/fur_motion.py',ROOT/'scripts/breast_rig.py',
                  ROOT/'scripts/surface_collar.py',ROOT/'scripts/collar_weights.py',ROOT/'scripts/locate.py']
    files += [*sorted((dependency/'pyn').glob('*.py')),*sorted((dependency/'tri').glob('*.py')),dependency/'NiflyDLL.dll']
    frozen_hash={str(p):rig.sha256(p) for p in files}
    rp=rig.load_profile(ROOT/'recipes/breast-rig-collar.json');raw=Trip.from_filepath(str(tri)).shapes
    source=api.NifFile(str(body));skel=api.NifFile(str(skeleton));report={'status':'building-unverified-do-not-install','inputsAndExecutedSha256':frozen_hash,'layers':{}}
    out.mkdir();(out/'NOT_INSTALLABLE.txt').write_text('Offline existing-XP32 skin/fur experiment; animation, visual, driver and game acceptance pending. No skeleton output.\n')
    current=body
    try:
        for name in profile['layers']:
            p={k:v for k,v in profile.items() if k not in ('layers',)};p['layer']=name
            source=api.NifFile(str(current));snapshot=fur.snapshot(source)
            if len(source.nodes)!=91:raise ValueError('Expected the 91-node existing-XP32 composition')
            model=fur.MotionModel(source,skel,raw,p,rp);s=model.shapes
            skin=np.r_[s['body'].verts,s['head'].verts];faces=np.r_[s['body'].tris,np.asarray(s['head'].tris)+len(s['body'].verts)]
            rule=next(x for x in rp['layers'] if x['shape']==name)
            layer=surface.Layer(s[name].verts,s[name].tris,skin,faces,rule,rig.SurfaceProjector(skin,faces))
            try:planned,active,rows=fur.plan_motion(model,layer)
            except ValueError as exc:
                if str(exc)!='No card improved within declared budgets; no-op candidate rejected':raise
                report['layers'][name]={'status':'unchanged-no-card-improved-within-existing-gates'};continue
            folder=out/name;folder.mkdir();target=folder/'femalebodywerewolf.nif'
            write_active_weights(s[name],planned,active,model.names);source.filepath=str(target);source.save()
            shutil.copyfile(tri,target.with_suffix('.tri'));actual=api.NifFile(str(target))
            fur.verify_snapshot(snapshot,actual,name,planned,model.names)
            if rig.sha256(target.with_suffix('.tri'))!=profile['inputs']['triSha256']:raise ValueError('TRI changed')
            report['layers'][name]={'status':'verified-offline-improved-full-cards','changedVertexCount':len(active),
                'changedVertices':active.tolist(),'groups':rows,'nifSha256':rig.sha256(target),
                'frozenBindings':[{'group':i,'vertices':ids.tolist(),'rootPoint':layer.binding.points[i].tolist(),
                    'skinVertices':layer.binding.faces[layer.binding.indices[i]].tolist(),'barycentric':layer.binding.weights[i].tolist(),
                    'weight':float(layer.weights[i])} for i,ids in enumerate(layer.groups)]}
            current=target
        if current==body:raise ValueError('Continuation changed no layer')
        final=out/'meshes/actors/werewolfbeast/character assets';final.mkdir(parents=True)
        target=final/'femalebodywerewolf_0.nif';shutil.copyfile(current,target)
        shutil.copyfile(current,final/'femalebodywerewolf_1.nif');shutil.copyfile(tri,final/'femalebodywerewolf.tri')
        if any(rig.sha256(p)!=value for p,value in frozen_hash.items()):raise ValueError('Input/source/dependency changed')
        report.update(status='verified-offline-extended-fur-candidate-runtime-appearance-pending',nif=str(target),
            nifSha256=rig.sha256(target),triSha256=profile['inputs']['triSha256'],
            acceptance='Same 151 poses, BreastSize0/.5/1, raw and normalized P1-root/ordinary/strain gates as the earlier belly fit; only the named whole full-weight cards may change. No strengthened claim for combined morphs, visible coverage, normal gap, animation or physics.')
    except Exception:
        report['status']='FAILED-unverified-do-not-install';raise
    finally:(out/'report.json').write_text(json.dumps(report,indent=2))
    return out/'report.json'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('body','tri','skeleton','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--profile',type=Path,default=ROOT/'recipes/fur-motion-continuation.json');p.add_argument('--pynifly',type=Path)
    a=p.parse_args()
    try:print(build(a.body,a.tri,a.skeleton,a.profile,a.out,a.pynifly))
    except (ValueError,RuntimeError,OSError) as exc:p.exit(1,'Fur continuation rejected: '+str(exc)+'\n')

if __name__=='__main__':main()
