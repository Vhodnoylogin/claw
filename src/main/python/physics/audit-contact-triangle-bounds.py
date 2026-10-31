"""Prove a continuous selected-triangle outside-distance bound at saved inputs.

For one fixed capsule, distance to its convex solid is convex. Every point of
an assigned triangle is therefore no farther from that capsule than the largest
distance of its three vertices. Distance to the capsule union is at most that
assigned-capsule distance. This bounds the *whole selected skin surface*, not
just the stored vertex/edge/centroid samples, at each saved coefficient/weight
vector. It does not bound all possible input vectors or capsule protrusion.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


def outside(points,cap):
    a=np.asarray(cap['p1']);direction=np.asarray(cap['p2'])-a;square=float(direction@direction)
    if not np.isfinite(points).all() or not np.isfinite([*a,*direction,cap['radius']]).all() or cap['radius']<=0:raise ValueError('Finite active capsule/support required')
    fraction=np.clip((points-a)@direction/square,0,1) if square>1e-20 else np.zeros(len(points))
    return np.maximum(0.,np.linalg.norm(points-a-fraction[:,None]*direction,axis=1)-cap['radius'])


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--model',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args(argv);script_bytes=Path(__file__).read_bytes();model_bytes=args.model.read_bytes();model=json.loads(model_bytes)
    if model['schemaVersion']!=3:raise ValueError('Current-vector model required')
    out=args.out.resolve()
    if out.exists() or out.suffix!='.json' or out.parent!=args.model.resolve().parent:raise ValueError('Use a new JSON sidecar beside the explicit model')
    for region in model['regions'].values():
        assigned=[index for group in region['triangleGroups'] for index in group]
        if sorted(assigned)!=list(range(len(region['faces']))):raise ValueError('Incomplete/duplicate selected triangle assignment')
        for partition,faces in zip(region['partitions'],region['triangleGroups']):
            if not set(np.asarray(region['faces'])[faces].reshape(-1)).issubset(partition):raise ValueError('Assigned triangle is missing a support vertex')
    rows=[]
    for fixture in model['fixtures']:
        for sex in ('male','female'):
            deformed={}
            for key,region in model['regions'].items():
                if not key.startswith(sex+'/'):continue
                p=np.asarray(region['points'],float).copy()
                if 'weightDeltas' in region:p+=fixture.get('weight',0.)*np.asarray(region['weightDeltas'])
                for name,delta in region['deltas'].items():p+=fixture['values'].get(name,0.)*np.asarray(delta)
                deformed[key]=p
            maximum=0.;witness=None;by_node={}
            for index,(slot,cap) in enumerate(zip(model['slots'],fixture['sexes'][sex]['capsules'],strict=True)):
                if slot.get(sex) is None:continue
                ids=np.asarray(slot[sex]['partitionIndices'],dtype=int);points=deformed[sex+'/'+slot['node']][ids]
                distances=outside(points,cap);i=int(np.argmax(distances))
                by_node[slot['node']]=max(by_node.get(slot['node'],0.),float(distances[i]))
                if distances[i]>maximum:
                    maximum=float(distances[i]);witness={'slot':index,'node':slot['node'],'regionVertex':int(ids[i]),'pointNodeLocal':points[i].tolist()}
            rows.append({'state':fixture['name'],'weight':fixture.get('weight',0.),'sex':sex,
                'maximumNodeLocalTriangleOutsideUpperBound':maximum,'boundByNode':by_node,'worstAssignedVertexWitness':witness})
    report={'schemaVersion':1,'modelIdentity':model['modelIdentity'],'modelSha256':hashlib.sha256(model_bytes).hexdigest(),
        'proof':'Each complete selected triangle is assigned to one convex capsule. Its vertex maximum of positive capsule distance bounds every barycentric triangle point; union distance is no greater. The report maximizes that bound over all assigned triangles at each saved actual input vector.',
        'spaceScope':'Complete selected rest-LBS skin triangles at every listed input vector; includes mixed ownership faces and optional minority P1 skin.',
        'frameLimit':'Bounds use each assigned node local frame. A common-world bound multiplies each node bound by that frame similarity scale; actor or animated bone scale is not recovered here.',
        'toolSha256':hashlib.sha256(script_bytes).hexdigest(),
        'allInputVectorsProven':False,'capsuleProtrusionProven':False,'animatedPoseProven':False,'gameValidated':False,
        'rows':rows,'maximumNodeLocalBound':max(row['maximumNodeLocalTriangleOutsideUpperBound'] for row in rows)}
    if args.model.read_bytes()!=model_bytes:raise ValueError('Model changed during triangle-bound audit')
    if Path(__file__).read_bytes()!=script_bytes:raise ValueError('Audit tool changed during execution')
    out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'statesIncludingSex':len(rows),'maximumNodeLocalBound':report['maximumNodeLocalBound'],'out':str(out)}));return 0


if __name__=='__main__':raise SystemExit(main())
