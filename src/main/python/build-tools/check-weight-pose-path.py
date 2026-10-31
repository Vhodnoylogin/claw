"""Independently check continuous neutral-weight triangle orientation in actual poses."""
from pathlib import Path
import argparse,json
import numpy as np
import breast_rig as rig
from geometry_audit import Model


def critical(a,b):
    e=a[:,1]-a[:,0];f=a[:,2]-a[:,0];d=b-a;u=d[:,1]-d[:,0];v=d[:,2]-d[:,0]
    c0=np.cross(e,f);c1=np.cross(u,f)+np.cross(e,v);c2=np.cross(u,v)
    norm=np.linalg.norm(c0,axis=1);valid=norm>1e-10
    axis=np.argmax(abs(c0)+abs(c1)+abs(c2),axis=1);rows=np.arange(len(a));qa=c2[rows,axis];qb=c1[rows,axis];qc=c0[rows,axis]
    scale=np.maximum(abs(qa)+abs(qb)+abs(qc),1e-30);quadratic=abs(qa)>scale*1e-12
    disc=qb*qb-4*qa*qc;real=disc>=0;sqrt=np.sqrt(np.maximum(disc,0));q=-.5*(qb+np.where(qb>=0,1.,-1.)*sqrt)
    roots=[]
    for numerator,denominator,mask in [(q,qa,quadratic&real),(qc,q,quadratic&real),(-qc,qb,~quadratic)]:
        t=np.divide(numerator,denominator,out=np.full_like(q,np.nan),where=abs(denominator)>1e-30)
        use=mask&(t>0)&(t<1)&valid;cross=c0[use]+t[use,None]*c1[use]+t[use,None]**2*c2[use]
        hit=np.flatnonzero(use)[np.linalg.norm(cross,axis=1)<2e-8];roots.extend(hit.tolist())
    d0=np.sum(c0*c0,1);d1=np.sum(c0*c1,1);d2=np.sum(c0*c2,1)
    t=np.clip(np.divide(-d1,2*d2,out=np.zeros_like(d1),where=d2>1e-30),0,1)
    minimum=np.minimum(d0,np.sum(c0*(c0+c1+c2),1));minimum=np.minimum(minimum,d0+t*d1+t*t*d2)
    return {'continuousAreaCollapseTriangles':sorted(set(roots)),'negativeOwnPose0NormalDotTriangles':np.flatnonzero((minimum<0)&valid).tolist(),
            'minimumEndpointAreaRatio':float(np.min(np.linalg.norm(c0+c1+c2,axis=1)[valid]/norm[valid]))}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('low','high','tri','skeleton','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();api,Trip,_=rig.load_pynifly(None);low=api.NifFile(str(a.low));high=api.NifFile(str(a.high));skel=api.NifFile(str(a.skeleton))
    model=Model(low,high,skel,Trip.from_filepath(str(a.tri)).shapes);report={'inputs':{str(x.resolve()):rig.sha256(x)for x in [a.low,a.high,a.tri,a.skeleton,Path(__file__)]},'states':{}}
    for label,state in [('neutral',{}),('breast-full',{'CLAWTorsoBreastSize':1.})]:
        shapes={}
        for name in ('body','head'):
            ids=np.arange(len(model.vertices[name]));lo=model.positions(name,ids,0.,state,True);hi=model.positions(name,ids,1.,state,True);faces=np.asarray(model.shapes[name].tris,int);rows=[]
            for i,pose in enumerate(model.poses):
                value=critical(lo[i,faces],hi[i,faces]);value.update(pose=pose[0],group=pose[2]);rows.append(value)
            shapes[name]=rows
        report['states'][label]=shapes
    report['status']='completed-continuous-weight-actual-pose-orientation-audit'
    a.out.write_text(json.dumps(report,indent=2));print(a.out)

if __name__=='__main__':main()
