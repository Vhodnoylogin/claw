"""Compare affine/current-vector candidates on the same complete skin triangles.

Only offline geometry is measured. Capsule-union volume uses a paired seeded
Monte Carlo experiment, not a sum of overlapping individual capsule volumes.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np
import contact_fit as contact


def union_volumes(left,right,samples=250000):
    all_caps=left+right
    lower=np.min([np.minimum(c['p1'],c['p2'])-c['radius'] for c in all_caps],axis=0)
    upper=np.max([np.maximum(c['p1'],c['p2'])+c['radius'] for c in all_caps],axis=0)
    volume=float(np.prod(upper-lower));points=lower+np.random.default_rng(20261026).random((samples,3))*(upper-lower)
    a=contact.signed_capsules(points,left)<=0;b=contact.signed_capsules(points,right)<=0
    delta=b.astype(float)-a.astype(float)
    return {'method':'paired-seeded-uniform-Monte-Carlo-capsule-union-membership','samples':samples,
        'baseline':float(a.mean()*volume),'current':float(b.mean()*volume),
        'differenceCurrentMinusBaseline':float(delta.mean()*volume),
        'differenceStandardError':float(delta.std(ddof=1)/np.sqrt(samples)*volume),
        'fractionalReduction':float(1-b.sum()/a.sum()) if a.sum() else None,
        'isExtraneousOutsideSkinVolume':False,
        'limit':'Union volume change is actual capsule geometry; it does not classify enclosed skin volume or measure animation.'}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',type=Path,required=True);p.add_argument('--current',type=Path,required=True)
    p.add_argument('--pynifly',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args(argv)
    spec=importlib.util.spec_from_file_location('fit_capsules',Path(__file__).with_name('fit-capsules.py'))
    fit=importlib.util.module_from_spec(spec);spec.loader.exec_module(fit)
    baseline=json.loads(args.baseline.read_bytes());current=json.loads(args.current.read_bytes())
    if baseline['schemaVersion']!=2 or current['schemaVersion']!=3:raise ValueError('Expected explicit affine2 and current3 inputs')
    root=Path(__file__).resolve().parents[4];sys.path.insert(0,str(root / 'src/main/python/build-tools'));import breast_rig
    api,_,_=breast_rig.load_pynifly(args.pynifly)
    skeleton_path=next(Path(pin['path']) for pin in current['sourceInputs'] if Path(pin['path']).name=='skeleton.nif')
    skeleton=api.NifFile(str(skeleton_path))
    geometry_keys={str(skeleton_path.resolve())}
    for pin in current['sourceInputs']:
        path=Path(pin['path'])
        if path.suffix in ('.tri','.nif'):geometry_keys.add(str(path.resolve()))
    pins=lambda d:{str(Path(row['path']).resolve()):row['sha256'] for row in d['sourceInputs'] if str(Path(row['path']).resolve()) in geometry_keys}
    if pins(baseline)!=pins(current):raise ValueError('Candidates use different geometry inputs')
    for key,digest in pins(current).items():
        if hashlib.sha256(Path(key).read_bytes()).hexdigest()!=digest:raise ValueError('Pinned comparison geometry changed')
    out=fit.safe_output(args.out,[args.baseline,args.current,skeleton_path,Path(__file__)])
    rows=[]
    def world_cap(node,cap):
        frame=fit._matrix(skeleton.nodes[node].global_transform)
        return {'p1':(frame@np.r_[cap['p1'],1])[:3].tolist(),'p2':(frame@np.r_[cap['p2'],1])[:3].tolist(),
                'radius':float(cap['radius'])*float(skeleton.nodes[node].global_transform.scale)}
    for fixture in current['fixtures']:
        if fixture['name'] not in ('neutral','all-1'):continue
        for sex in ('male','female'):
            points=[];faces=[];offset=0
            for node in fit.CONTACT_NODES:
                region=current['regions'].get(sex+'/'+node)
                if region is None:continue
                selected={n:fixture['values'].get(n,0.) for n in region['morphs']};local=contact.deform(region,selected,fixture.get('weight',0.))
                frame=fit._matrix(skeleton.nodes[node].global_transform)
                points.extend((np.column_stack([local,np.ones(len(local))])@frame.T)[:,:3])
                faces.extend((np.asarray(region['faces'])+offset).tolist());offset+=len(local)
            old_caps=[world_cap(row['node'],fit.evaluate(row[sex],{n:fixture['values'].get(n,0.) for n in row[sex]['coefficients']})) for row in baseline['slots']]
            new_caps=[world_cap(row['node'],cap) for row,cap in zip(current['slots'],fixture['sexes'][sex]['capsules'],strict=True) if row.get(sex) is not None]
            rows.append({'state':fixture['name'],'weight':fixture.get('weight',0.),'sex':sex,'baseline':contact.surface_metrics(points,faces,old_caps),
                'current':contact.surface_metrics(points,faces,new_caps),'unionVolume':union_volumes(old_caps,new_caps)})
    report={'schemaVersion':1,'baselineSha256':hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
        'currentSha256':hashlib.sha256(args.current.read_bytes()).hexdigest(),'geometryInputs':pins(current),
        'sameMixedBoundarySkinTriangles':True,'measurements':rows,'gameValidated':False,
        'distanceScope':'Finite exposed-union capsule samples to exact nearest skin triangle, skin vertex/edge/centroid samples to capsule union; not a continuous Hausdorff bound or signed extraneous volume.'}
    out.mkdir(parents=True);(out/'contact-fit-comparison.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'out':str(out),'measurements':len(rows)}));return 0


if __name__=='__main__':raise SystemExit(main())
