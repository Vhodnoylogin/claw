"""Prove equality of rest skin triangles and every signed morph field after split.

Unlike equal NIF hashes, this permits a reviewed shape/material/weight-resource
rewrite while directly checking the actual collision surface and dependencies.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np


def signatures(model,sex,nodes,names,matrix):
    rows=[]
    for node in nodes:
        region=model['regions'].get(sex+'/'+node)
        if region is None:continue
        points=np.asarray(region['points']);faces=np.asarray(region['faces'],dtype=int)
        frame=matrix(node);world=(np.column_stack([points,np.ones(len(points))])@frame.T)[:,:3]
        fields=[np.asarray(region['deltas'].get(name,np.zeros_like(points)))@frame[:3,:3].T for name in names]
        for face in faces:
            order=np.lexsort(world[face].T[::-1]);ids=face[order]
            rows.append(np.concatenate([world[ids].reshape(-1)]+[delta[ids].reshape(-1) for delta in fields]))
    rows=np.asarray(rows)
    if not len(rows):raise ValueError('Empty selected contact surface')
    # Quantized neutral coordinates select correspondence only. All comparison
    # values remain the original, unrounded measured coordinates and deltas.
    keys=np.round(rows[:,:9],4);order=np.lexsort(keys.T[::-1])
    return rows[order],keys[order]


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('before','after','pynifly','out'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--tolerance',type=float,default=1e-4)
    args=parser.parse_args(argv)
    before=json.loads(args.before.read_bytes());after=json.loads(args.after.read_bytes())
    if before['schemaVersion']!=3 or after['schemaVersion']!=3:raise ValueError('Current-vector schema3 models required')
    if not 0<args.tolerance<=.001:raise ValueError('Tolerance must be positive and <=.001 game units')
    root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'scripts'));import breast_rig
    spec=importlib.util.spec_from_file_location('fit_capsules',root/'physics/fit-capsules.py')
    fit=importlib.util.module_from_spec(spec);spec.loader.exec_module(fit)
    api,_,_=breast_rig.load_pynifly(args.pynifly)
    skeleton_pins=[next(row for row in model['sourceInputs'] if Path(row['path']).name=='skeleton.nif') for model in (before,after)]
    if skeleton_pins[0]['sha256']!=skeleton_pins[1]['sha256']:raise ValueError('Different skeleton rest-frame bytes')
    skeleton=api.NifFile(skeleton_pins[1]['path']);matrix=lambda node:fit._matrix(skeleton.nodes[node].global_transform)
    names=sorted(set(before['morphs'])|set(after['morphs']));rows=[];accepted=True
    for sex in ('male','female'):
        left,left_keys=signatures(before,sex,fit.NODES,names,matrix);right,right_keys=signatures(after,sex,fit.NODES,names,matrix)
        matched=left.shape==right.shape and np.array_equal(left_keys,right_keys)
        difference=np.max(abs(left-right),axis=0) if matched else None
        maximum=float(difference.max()) if difference is not None else None
        okay=matched and maximum<=args.tolerance;accepted=accepted and okay
        rows.append({'sex':sex,'beforeTriangles':len(left),'afterTriangles':len(right),'correspondenceMatched':matched,
            'maximumRestTriangleCoordinateDifference':float(difference[:9].max()) if difference is not None else None,
            'maximumSignedDeltaCoordinateDifference':{name:float(difference[9+9*i:18+9*i].max()) for i,name in enumerate(names)} if difference is not None else None,
            'accepted':okay})
    report={'schemaVersion':1,'accepted':accepted,'tolerance':args.tolerance,'morphs':names,'sexes':rows,
        'nodeScope':list(fit.NODES),'comparisonWeight':0.,'independentWeightEndpointFieldCompared':False,
        'beforeModelIdentity':before['modelIdentity'],'afterModelIdentity':after['modelIdentity'],
        'beforeSha256':hashlib.sha256(args.before.read_bytes()).hexdigest(),'afterSha256':hashlib.sha256(args.after.read_bytes()).hexdigest(),
        'proof':'At independent actor weight0, each neutral full-LBS ear/tail triangle and every signed TRI field agrees in a shared actual skeleton rest frame; their linear combination therefore agrees for any common morph coefficient vector within numeric tolerance. Changed weight endpoints and female-only P1 are separate explicit model inputs, outside this equivalence claim.',
        'notProven':'Animation, altered bone or actor scales, fur-layer support, game contact, actual provider or event delivery.'}
    out=fit.safe_output(args.out,[args.before,args.after,Path(__file__)]);out.mkdir(parents=True)
    (out/'support-equality.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'accepted':accepted,'out':str(out),'triangles':[r['afterTriangles'] for r in rows]}));return 0 if accepted else 2


if __name__=='__main__':raise SystemExit(main())
