"""Read-only check that the local weight repair adds no fur/blend path defects."""
from pathlib import Path
import argparse,importlib.util,json
import numpy as np
import breast_rig as rig
from geometry_audit import Model


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('prior-composition','composition','skeleton','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();before=json.loads(a.prior_composition.read_text());after=json.loads(a.composition.read_text())
    old=before['bodies']['male'];new=after['bodies']['male'];raw_tri=next(Path(s) for s,h in before['inputsAndExecutedSha256'].items() if h==before['profile']['inputs']['maleTriSha256'])
    sources=[a.prior_composition,a.composition,a.skeleton,raw_tri,Path(old['boundedSource']),Path(old['boundedHighSource']),Path(new['boundedHighSource']),Path(__file__)]
    frozen={str(x):rig.sha256(x) for x in sources};api,Trip,_=rig.load_pynifly(None);low=api.NifFile(old['boundedSource']);high0=api.NifFile(old['boundedHighSource']);high1=api.NifFile(new['boundedHighSource'])
    skel=api.NifFile(str(a.skeleton));raw=Trip.from_filepath(str(raw_tri)).shapes;m0=Model(low,high0,skel,raw);m1=Model(low,high1,skel,raw)
    path=Path(__file__).with_name('check-weight-pose-path.py');spec=importlib.util.spec_from_file_location('guard_layer_critical',path);check=importlib.util.module_from_spec(spec);spec.loader.exec_module(check)
    report={'status':'building','inputs':frozen,'layers':{}}
    for name in m0.shapes:
        if not(name.startswith('fur_') or name.endswith('Blend')):continue
        changed=np.any(m0.high[name]!=m1.high[name],axis=1);faces=np.asarray(m0.shapes[name].tris,int);face_ids=np.flatnonzero(np.any(changed[faces],axis=1))
        if not len(face_ids):continue
        used,inverse=np.unique(faces[face_ids],return_inverse=True);local=inverse.reshape(-1,3);rows={}
        for mode in (False,True):
            lo=m0.positions(name,used,0.,{},mode);old_hi=m0.positions(name,used,1.,{},mode);new_hi=m1.positions(name,used,1.,{},mode);cases=[]
            for i,pose in enumerate(m0.poses[:151]):
                b=check.critical(lo[i,local],old_hi[i,local]);c=check.critical(lo[i,local],new_hi[i,local])
                turns=sorted(set(c['negativeOwnPose0NormalDotTriangles'])-set(b['negativeOwnPose0NormalDotTriangles']))
                collapse=sorted(set(c['continuousAreaCollapseTriangles'])-set(b['continuousAreaCollapseTriangles']))
                cases.append({'pose':pose[0],'newNormalTurns':face_ids[turns].tolist(),'newAreaCollapses':face_ids[collapse].tolist(),
                    'priorNormalTurnCount':len(b['negativeOwnPose0NormalDotTriangles']),'guardedNormalTurnCount':len(c['negativeOwnPose0NormalDotTriangles'])})
            rows['normalized' if mode else 'rawPacked']=cases
        report['layers'][name]={'changedVertices':int(changed.sum()),'affectedTriangles':len(face_ids),'checks':rows}
    added=sum(len(c[k]) for layer in report['layers'].values() for rows in layer['checks'].values() for c in rows for k in ('newNormalTurns','newAreaCollapses'))
    if any(rig.sha256(s)!=h for s,h in frozen.items()):raise ValueError('Layer-check input changed')
    report.update(status='passed-no-new-affected-layer-continuous-weight-defects' if not added else 'FAILED-new-affected-layer-weight-defects',addedDefectInstances=added)
    a.out.write_text(json.dumps(report,indent=2));print(a.out);return 0 if not added else 1

if __name__=='__main__':raise SystemExit(main())
