"""Exact nearest-triangle witnesses and explicit signed-distance distributions.

The oriented nearest-face sign is a local surface-side diagnostic. An open
selected skin patch does not define a closed solid, so it must never be sold
as a winding-number inside/outside test or signed extraneous volume.
"""
from __future__ import annotations
import numpy as np
import contact_fit as contact


NEAREST_SQUARED_TIE=1e-12


def nearest(points,triangles,chunk=64,prune=True):
    p=np.asarray(points,float).reshape(-1,3);t=np.asarray(triangles,float).reshape(-1,3,3)
    if prune and len(t)>128:
        lower=t.min(axis=1);upper=t.max(axis=1);distances=[];locations=[];indices=[]
        for point in p:
            bound=np.sum(np.maximum(np.maximum(lower-point,point-upper),0.)**2,axis=1)
            first=int(np.argmin(bound));distance,_,_=nearest([point],t[first:first+1],prune=False)
            # Inclusive bound retains all possible nearest/tied witnesses.
            candidates=np.flatnonzero(bound<=float(distance[0]**2)+NEAREST_SQUARED_TIE)
            distance,location,index=nearest([point],t[candidates],prune=False)
            distances.append(distance[0]);locations.append(location[0]);indices.append(int(candidates[index[0]]))
        return np.asarray(distances),np.asarray(locations),np.asarray(indices,dtype=int)
    distances=[];locations=[];indices=[]
    a=t[None,:,0,:];u=t[None,:,1,:]-a;v=t[None,:,2,:]-a
    uu=np.sum(u*u,axis=2);uv=np.sum(u*v,axis=2);vv=np.sum(v*v,axis=2);denominator=uu*vv-uv*uv
    for start in range(0,len(p),chunk):
        q=p[start:start+chunk,None,:];w=q-a;wu=np.sum(w*u,axis=2);wv=np.sum(w*v,axis=2)
        safe=np.where(abs(denominator)>1e-24,denominator,1.)
        b=(wu*vv-wv*uv)/safe;c=(wv*uu-wu*uv)/safe;inside=(abs(denominator)>1e-24)&(b>=0)&(c>=0)&(b+c<=1)
        closest=a+b[:,:,None]*u+c[:,:,None]*v
        square=np.where(inside,np.sum((q-closest)**2,axis=2),np.inf)
        for i,j in ((0,1),(1,2),(2,0)):
            begin=t[None,:,i,:];direction=t[None,:,j,:]-begin;norm=np.sum(direction*direction,axis=2)
            fraction=np.clip(np.sum((q-begin)*direction,axis=2)/np.where(norm>1e-24,norm,1.),0,1)
            candidate=begin+fraction[:,:,None]*direction;trial=np.sum((q-candidate)**2,axis=2);take=trial<square
            closest=np.where(take[:,:,None],candidate,closest);square=np.minimum(square,trial)
        # Original ordering is retained through pruning. Equal/near-equal
        # squared distances choose the lowest original triangle index.
        minimum=square.min(axis=1)
        owner=np.argmax(square<=minimum[:,None]+NEAREST_SQUARED_TIE,axis=1);row=np.arange(len(q));indices.extend(owner.tolist())
        distances.extend(np.sqrt(np.maximum(0,square[row,owner])));locations.extend(closest[row,owner])
    return np.asarray(distances),np.asarray(locations),np.asarray(indices,dtype=int)


def distribution(values):
    d=np.asarray(values,float)
    return {'samples':len(d),'min':float(d.min()),'p05':float(np.quantile(d,.05)),
        'p50':float(np.quantile(d,.5)),'p95':float(np.quantile(d,.95)),'max':float(d.max()),
        'absoluteP95':float(np.quantile(abs(d),.95)),'rms':float(np.sqrt(np.mean(d*d)))}


def signed_witnesses(points,faces,capsules):
    p=np.asarray(points,float);f=np.asarray(faces,dtype=int);triangles=p[f];samples=[];owners=[]
    for i,cap in enumerate(capsules):
        s=contact.capsule_surface(cap);others=capsules[:i]+capsules[i+1:]
        if others:s=s[contact.signed_capsules(s,others)>=-1e-7]
        samples.extend(s);owners.extend([i]*len(s))
    samples=np.asarray(samples);dist,closest,index=nearest(samples,triangles)
    normals=np.cross(triangles[index,1]-triangles[index,0],triangles[index,2]-triangles[index,0])
    length=np.linalg.norm(normals,axis=1);side=np.sum((samples-closest)*normals,axis=1)/np.maximum(length,1e-30)
    oriented=np.where(side>=0,dist,-dist);ambiguous=abs(side)<=1e-8*np.maximum(1.,dist)
    bary=((1.,0.,0.),(0.,1.,0.),(0.,0.,1.),(.5,.5,0.),(.5,0.,.5),(0.,.5,.5),(1/3,)*3)
    skin=np.concatenate([np.einsum('tjk,j->tk',triangles,np.asarray(w)) for w in bary]);field=contact.signed_capsules(skin,capsules)
    capsule_witnesses=[]
    for i in np.argsort(-dist,kind='stable')[:5]:
        capsule_witnesses.append({'point':samples[i].tolist(),'capsuleSlot':owners[i],
            'nearestSkinTriangle':int(index[i]),'nearestSkinPoint':closest[i].tolist(),
            'unsignedDistance':float(dist[i]),'orientedNearestFaceSignedDistance':float(oriented[i]),'signAmbiguous':bool(ambiguous[i])})
    skin_witnesses=[]
    for i in np.argsort(-abs(field),kind='stable')[:5]:
        each=[float(contact.signed_capsules([skin[i]],[cap])[0]) for cap in capsules]
        skin_witnesses.append({'point':skin[i].tolist(),'signedCapsuleField':float(field[i]),'capsuleSlot':int(np.argmin(each))})
    surface={'measured':True,'capsuleSurfaceSamples':len(samples),'skinSurfaceSamples':len(skin),
        'capsuleToSkinP50':float(np.quantile(dist,.5)),'capsuleToSkinP95':float(np.quantile(dist,.95)),
        'capsuleToSkinMaxSampled':float(dist.max()),'skinOutsideFraction':float(np.mean(field>1e-5)),
        'skinOutsideMaxSampled':float(max(0,field.max())),'skinInsideCapsuleProxyP95':float(np.quantile(np.maximum(0,-field),.95)),
        'exactNearestTriangleDistance':True,'exposedUnionSurfaceOnly':True,'finiteSamplingNotHausdorffProof':True}
    surface['nearestTriangleSquaredTieTolerance']=NEAREST_SQUARED_TIE
    return {'surfaceMetrics':surface,'capsuleToSkinOrientedNearestFace':distribution(oriented),
        'capsuleToSkinOrientedSignLimit':'Local nearest oriented triangle; selected skin is open. This is not closed-solid inside/outside, signed Hausdorff distance or outside-skin volume.',
        'orientedSignAmbiguousFraction':float(np.mean(ambiguous)),
        'skinToCapsuleField':distribution(field),
        'skinSignedFieldLimit':'Positive outside distance and capsule-union membership are exact. Negative minimum per-capsule field is an interior proxy, not distance to union boundary.',
        'capsuleWorstWitnesses':capsule_witnesses,'skinWorstAbsoluteWitnesses':skin_witnesses,
        'samplingLimit':'Finite parameter-grid capsule samples and skin vertex/edge/centroid samples, unweighted by area; no unsampled Hausdorff maximum proof.'}
