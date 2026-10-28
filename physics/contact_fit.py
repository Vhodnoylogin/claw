"""Current-vector capsule fitting and actual sampled surface diagnostics.

No NIF, renderer or provider dependencies. Geometry is already in the chosen
node's rest frame. A current-vector fit encloses the supplied full triangles;
it makes no claim about an interval between different fitted vectors.
"""
from __future__ import annotations
import math
import numpy as np


def _first_tied(values,largest=False,epsilon=1e-10):
    values=np.asarray(values,float);extreme=float(values.max() if largest else values.min())
    return int(np.flatnonzero(abs(values-extreme)<=epsilon)[0])


def capsule(points, padding=1e-4, direction=None):
    """Deterministic enclosing PCA capsule, mirrored by PhysicsFit.h.

    Recompute the covariance on the *deformed* support. A box envelope is never
    carried into another state. Radius includes every support point; endpoint
    slack shortens the capsule without excluding any of those points.
    """
    p=np.asarray(points,dtype=float).reshape(-1,3)
    if len(p)<2 or not np.isfinite(p).all() or not 0 < padding <= .01:
        raise ValueError("Invalid current-vector support")
    centre=p.mean(axis=0); relative=p-centre; covariance=relative.T@relative
    if direction is not None:
        axis=np.asarray(direction,dtype=float);length=float(np.linalg.norm(axis))
        if axis.shape!=(3,) or not np.isfinite(axis).all() or length<1e-12:raise ValueError("Invalid capsule direction")
        axis=axis/length
    else:
        diagonal=np.diag(covariance);axis=np.eye(3)[_first_tied(diagonal,True,1e-12*max(1.,float(abs(diagonal).max())))]
        for _ in range(48):
            moved=covariance@axis; length=float(np.linalg.norm(moved))
            if length<1e-20: break
            axis=moved/length
    if axis[_first_tied(abs(axis),True)]<0:axis=-axis
    along=relative@axis; radial=np.linalg.norm(relative-along[:,None]*axis,axis=1)
    radius=float(radial.max())+padding
    slack=np.sqrt(np.maximum(0,radius*radius-radial*radial))
    lower=float(np.min(along+slack)); upper=float(np.max(along-slack))
    if upper<lower:lower=upper=(lower+upper)*.5
    return {"p1":(centre+lower*axis).tolist(),"p2":(centre+upper*axis).tolist(),"radius":radius}


def deform(model, values, weight=0.):
    names=model["morphs"]
    if set(values)-set(names):raise ValueError("Unknown current-vector morph")
    coefficients=np.asarray([values.get(name,0.) for name in names],dtype=float)
    if any(isinstance(v,bool) or not isinstance(v,(int,float,np.integer,np.floating)) for v in values.values()) or not np.isfinite(coefficients).all() or np.any((coefficients<0)|(coefficients>1)):
        raise ValueError("Current-vector morphs must be finite in [0,1]")
    if isinstance(weight,bool) or not isinstance(weight,(int,float,np.integer,np.floating)) or not math.isfinite(weight) or not 0<=weight<=1:
        raise ValueError('Actor weight must be finite in [0,1]')
    points=np.asarray(model["points"],dtype=float).copy()
    if 'weightDeltas' in model:points+=weight*np.asarray(model['weightDeltas'])
    for name,value in zip(names,coefficients):
        if value and name in model["deltas"]:points+=value*np.asarray(model["deltas"][name])
    return points


def evaluate(model,values,weight=0.):
    p=deform(model,values,weight)
    result=[]
    for i,ids in enumerate(model['partitions']):
        direction=None
        if 'axisHints' in model:
            direction=np.asarray(model['axisHints'][i],dtype=float).copy()
            for name,value in values.items():
                if name in model.get('axisDeltas',{}):direction+=value*np.asarray(model['axisDeltas'][name][i])
        local=p[np.asarray(ids,dtype=int)]
        if model.get('contactPasses',0):
            if direction is not None:raise ValueError('Prescribed-axis contact optimization is not a supported family')
            mapping={int(v):j for j,v in enumerate(ids)}
            faces=np.asarray([[mapping[int(v)] for v in model['faces'][face]] for face in model['triangleGroups'][i]],dtype=int)
            result.append(contact_capsule(local,faces,model.get('padding',1e-4),model['contactPasses']))
        else:result.append(capsule(local,model.get('padding',1e-4),direction))
    return result


def objective_surface(cap):
    a=np.asarray(cap['p1']);b=np.asarray(cap['p2']);axis=b-a;length=float(np.linalg.norm(axis))
    axis=axis/length if length>1e-10 else np.array([0.,0.,1.])
    helper=np.eye(3)[_first_tied(abs(axis))];u=np.cross(axis,helper);u/=np.linalg.norm(u);v=np.cross(axis,u)
    ring=np.asarray([math.cos(i*math.pi/4)*u+math.sin(i*math.pi/4)*v for i in range(8)])
    r=cap['radius'];rows=[]
    for f in (0.,.5,1.):rows.extend(a+f*(b-a)+r*ring)
    for end,sign in ((a,-1.),(b,1.)):
        rows.extend(end+r*(ring/math.sqrt(2)+axis*sign/math.sqrt(2)))
        rows.append(end+sign*r*axis)
    return np.asarray(rows)


def contact_capsule(points,faces,padding=1e-4,passes=3):
    """Symmetric sampled minimax/RMS objective, mirrored exactly in C++.

    Complete triangles provide skin vertices/edge/centroid samples and exact
    nearest-triangle references. All seven endpoint/radius parameters can move.
    This deliberately trades explicit measured undercoverage against protrusion
    instead of treating an enclosing convex hull as the contact objective.
    """
    p=np.asarray(points,float);triangles=p[np.asarray(faces,dtype=int)]
    bary=((1.,0.,0.),(0.,1.,0.),(0.,0.,1.),(.5,.5,0.),(.5,0.,.5),(0.,.5,.5),(1/3,)*3)
    skin=np.concatenate([np.einsum('tjk,j->tk',triangles,np.asarray(w)) for w in bary])
    initial=capsule(p,padding);scale=max(initial['radius'],padding*10)
    def from_parameters(x):return {'p1':x[:3].tolist(),'p2':x[3:6].tolist(),'radius':float(x[6])}
    def objective(x):
        if x[6]<padding:return float('inf')
        cap=from_parameters(x);a=abs(signed_capsules(skin,[cap]));b=triangle_distance(objective_surface(cap),triangles)
        return float(max(a.max(),b.max())+.2*math.sqrt((float(a@a)+float(b@b))/(len(a)+len(b))))
    x=np.r_[initial['p1'],initial['p2'],initial['radius']];score=objective(x)
    radial=signed_capsules(skin,[{**initial,'radius':0.}]);candidate=x.copy();candidate[6]=max(padding,float((radial.max()+radial.min())*.5))
    trial=objective(candidate)
    if trial<score-1e-7:x=candidate;score=trial
    for iteration in range(passes):
        step=scale*.3*(.5**iteration)
        for dimension in range(7):
            chosen=x;best=score
            for sign in (-1.,1.):
                candidate=x.copy();candidate[dimension]+=step*sign
                trial=objective(candidate)
                if trial<best-1e-7:chosen=candidate;best=trial
            x=chosen;score=best
    return from_parameters(x)


def signed_capsules(points,capsules):
    p=np.asarray(points,dtype=float).reshape(-1,3); result=np.full(len(p),np.inf)
    for cap in capsules:
        a=np.asarray(cap["p1"]); d=np.asarray(cap["p2"])-a; n=float(d@d)
        t=np.clip((p-a)@d/n,0,1) if n>1e-20 else np.zeros(len(p))
        result=np.minimum(result,np.linalg.norm(p-a-t[:,None]*d,axis=1)-cap["radius"])
    return result


def triangle_distance(points,triangles,chunk=96):
    """Exact unsigned point/closed-triangle distance, including degenerate faces.

    Vertex-only distance is insufficient: nearest points may be in a triangle
    interior or on an edge. Projection is accepted only for valid barycentrics;
    otherwise the minimum of the three exact segment distances is used.
    """
    p=np.asarray(points,dtype=float).reshape(-1,3)
    t=np.asarray(triangles,dtype=float).reshape(-1,3,3)
    if not len(t) or not np.isfinite(p).all() or not np.isfinite(t).all():raise ValueError("Finite triangles required")
    result=np.full(len(p),np.inf)
    for begin in range(0,len(p),chunk):
        q=p[begin:begin+chunk,None,:]; a=t[None,:,0,:]; u=t[None,:,1,:]-a; v=t[None,:,2,:]-a
        w=q-a; uu=np.sum(u*u,axis=2); uv=np.sum(u*v,axis=2); vv=np.sum(v*v,axis=2)
        wu=np.sum(w*u,axis=2); wv=np.sum(w*v,axis=2); denominator=uu*vv-uv*uv
        safe=np.where(abs(denominator)>1e-24,denominator,1.)
        b=(wu*vv-wv*uv)/safe; c=(wv*uu-wu*uv)/safe
        inside=(abs(denominator)>1e-24)&(b>=0)&(c>=0)&(b+c<=1)
        square=np.where(inside,np.sum((w-b[:,:,None]*u-c[:,:,None]*v)**2,axis=2),np.inf)
        for i,j in ((0,1),(1,2),(2,0)):
            start=t[None,:,i,:]; direction=t[None,:,j,:]-start
            norm=np.sum(direction*direction,axis=2); fraction=np.clip(np.sum((q-start)*direction,axis=2)/np.where(norm>1e-24,norm,1.),0,1)
            square=np.minimum(square,np.sum((q-start-fraction[:,:,None]*direction)**2,axis=2))
        result[begin:begin+len(q)]=np.sqrt(np.maximum(0,square.min(axis=1)))
    return result


def capsule_surface(cap,azimuth=16,axial=5,hemisphere=4):
    a=np.asarray(cap["p1"]); b=np.asarray(cap["p2"]); axis=b-a; length=np.linalg.norm(axis)
    axis=axis/length if length>1e-10 else np.array([0.,0.,1.])
    helper=np.eye(3)[_first_tied(abs(axis))]; u=np.cross(axis,helper); u/=np.linalg.norm(u); v=np.cross(axis,u)
    ring=np.asarray([math.cos(t)*u+math.sin(t)*v for t in np.linspace(0,2*math.pi,azimuth,endpoint=False)])
    r=cap["radius"]; rows=[]
    for f in np.linspace(0,1,axial):rows.extend(a+f*(b-a)+r*ring)
    for end,sign in ((a,-1),(b,1)):
        for t in np.linspace(0,math.pi/2,hemisphere+1)[1:]:rows.extend(end+r*(math.cos(t)*ring+sign*math.sin(t)*axis))
    return np.asarray(rows)


def surface_metrics(points,faces,capsules,*,dense=False):
    """Two directional sampled surface distances; all nearest faces are exact.

    Samples hidden in another capsule are removed before capsule->skin
    measurement. This evaluates the exposed capsule union, rather than the
    misleading minimum negative capsule field at skin vertices. Sampling is
    finite and does not certify an unsampled Hausdorff maximum or signed volume.
    """
    p=np.asarray(points,dtype=float); f=np.asarray(faces,dtype=int).reshape(-1,3)
    if not len(f):return {"measured":False,"reason":"No skin triangles"}
    triangles=p[f]; samples=[]
    for i,cap in enumerate(capsules):
        s=capsule_surface(cap,azimuth=32 if dense else 16,axial=9 if dense else 5,hemisphere=8 if dense else 4)
        others=capsules[:i]+capsules[i+1:]
        if others:s=s[signed_capsules(s,others)>=-1e-7]
        samples.extend(s)
    samples=np.asarray(samples).reshape(-1,3)
    if len(triangles)>128:
        from contact_diagnostics import nearest
        outward=nearest(samples,triangles)[0]
    else:outward=triangle_distance(samples,triangles)
    bary=[(1,0,0),(0,1,0),(0,0,1),(.5,.5,0),(.5,0,.5),(0,.5,.5),(1/3,)*3]
    skin=np.concatenate([np.einsum('tjk,j->tk',triangles,np.asarray(weights)) for weights in bary])
    d=signed_capsules(skin,capsules)
    return {"measured":True,"capsuleSurfaceSamples":len(samples),"skinSurfaceSamples":len(skin),
            "capsuleToSkinP50":float(np.quantile(outward,.5)),"capsuleToSkinP95":float(np.quantile(outward,.95)),
            "capsuleToSkinMaxSampled":float(outward.max()),"skinOutsideFraction":float(np.mean(d>1e-5)),
            "skinOutsideMaxSampled":float(max(0,d.max())),"skinInsideCapsuleProxyP95":float(np.quantile(np.maximum(0,-d),.95)),
            "exactNearestTriangleDistance":True,"exposedUnionSurfaceOnly":True,"finiteSamplingNotHausdorffProof":True}


def partitions(points,faces,count,method='compact'):
    """Spatial triangle clusters; every complete supplied triangle is owned once.

    Partitions contain all vertices of their faces. A vertex shared across a
    boundary is intentionally repeated, preserving mixed boundary triangles.
    """
    p=np.asarray(points,dtype=float); faces=np.asarray(faces,dtype=int).reshape(-1,3)
    if count<1 or count>128 or not len(faces):raise ValueError("Triangle groups require 1..128 slots and faces")
    centroids=p[faces].mean(axis=1); count=min(count,len(faces))
    if method.startswith('strips-'):
        direction=int(method.rsplit('-',1)[1])
        _,_,axes=np.linalg.svd(p-p.mean(axis=0),full_matrices=False)
        axis=axes[direction]
        if axis[int(np.argmax(abs(axis)))]<0:axis=-axis
        groups=[ids.tolist() for ids in np.array_split(np.argsort(centroids@axis,kind='stable'),count)]
        return [np.unique(faces[ids].reshape(-1)).tolist() for ids in groups],groups
    if method not in ('compact','compact-extreme'):raise ValueError("Unknown triangle partition method")
    # The historical first-face seed remains the default. The explicit trial
    # starts at the farthest centroid from the centroid mean; np.argmax breaks
    # exact ties by the lowest stable input face index. Face storage is retained.
    first=0 if method=='compact' else int(np.argmax(np.sum((centroids-centroids.mean(axis=0))**2,axis=1)))
    centres=[centroids[first]]
    for _ in range(count-1):
        nearest=np.min(np.sum((centroids[:,None,:]-np.asarray(centres)[None,:,:])**2,axis=2),axis=1)
        centres.append(centroids[int(np.argmax(nearest))])
    centres=np.asarray(centres); previous=None
    for _ in range(64):
        labels=np.argmin(np.sum((centroids[:,None,:]-centres[None,:,:])**2,axis=2),axis=1)
        if previous is not None and np.array_equal(labels,previous):break
        for i in range(count):
            if np.any(labels==i):centres[i]=centroids[labels==i].mean(axis=0)
        previous=labels
    groups=[np.flatnonzero(labels==i).tolist() for i in range(count) if np.any(labels==i)]
    return [np.unique(faces[ids].reshape(-1)).tolist() for ids in groups],groups
