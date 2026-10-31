"""Actual-bind collar/fur distances and local orientation diagnostics for composition."""
from pathlib import Path
import json
import numpy as np
import breast_rig as rig
import surface_collar as surface
from collar_weights import triangle_distances,stat
from body_weight import Projector
from composed_vr import pose_bank

ROOT=Path(__file__).resolve().parents[4]


class Model:
    def __init__(self,low,high,skeleton,raw):
        self.shapes={s.name:s for s in low.shapes};self.high={s.name:np.asarray(s.verts,float) for s in high.shapes}
        self.vertices={n:np.asarray(s.verts,float) for n,s in self.shapes.items()};self.raw=raw;self.cache={}
        self.names=sorted({n for s in low.shapes for n in s.bone_weights});self.index={n:i for i,n in enumerate(self.names)}
        self.rest,self.parents,self.poses,self.global_dicts=pose_bank(skeleton)
        self.globals=np.asarray([[p[n] for n in self.names] for p in self.global_dicts])
        self.W={n:rig.read_weights(s,self.names) for n,s in self.shapes.items()};self.effective={}
        for n,s in self.shapes.items():
            bind=np.zeros((len(self.names),4,4))
            for bone in s.bone_weights:bind[self.index[bone]]=rig.matrix(s.get_shape_skin_to_bone(bone))@rig.matrix(s.global_to_skin)
            self.effective[n]=np.einsum('pbij,bjk->pbik',self.globals,bind)
        self.groups={'ordinary':[i for i,p in enumerate(self.poses) if p[2]=='ordinary'],
                     'heldout':[i for i,p in enumerate(self.poses) if p[2]=='heldout'],
                     'pureP1':[i for i,p in enumerate(self.poses) if p[2].startswith('p1-')],
                     'combinedP1':[i for i,p in enumerate(self.poses) if p[2]=='combined-p1'],
                     'headExamples':[i for i,p in enumerate(self.poses) if i>=151 and p[2]!='visibility-operation-example'],
                     'visibilityExample':[i for i,p in enumerate(self.poses) if p[2]=='visibility-operation-example']}
    def positions(self,name,ids,weight,state,normalized):
        ids=np.asarray(ids,int);v=self.vertices[name][ids]+weight*(self.high[name][ids]-self.vertices[name][ids])
        for morph,value in state.items():
            key=(name,morph)
            if key not in self.cache:self.cache[key]=rig.dense_morph(self.raw,name,morph,len(self.vertices[name]))
            v+=value*self.cache[key][ids]
        W=self.W[name][ids];W=W/W.sum(1)[:,None] if normalized else W
        output=np.zeros((len(self.poses),len(ids),3));h=np.c_[v,np.ones(len(v))]
        for j in np.flatnonzero(np.any(W,axis=0)):
            output+=np.einsum('pij,nj->pni',self.effective[name][:,j,:3],h)*W[None,:,j,None]
        return output
    def skin(self,faces,weight,state,normalized):
        faces=np.asarray(faces,int);body_n=len(self.vertices['body']);all_=faces.ravel();out=np.zeros((len(self.poses),len(all_),3))
        for name,mask,ids in [('body',all_<body_n,all_[all_<body_n]),('head',all_>=body_n,all_[all_>=body_n]-body_n)]:
            if len(ids):out[:,mask]=self.positions(name,ids,weight,state,normalized)
        return out.reshape(len(self.poses),len(faces),3,3)
    def skin_weights(self,faces,bary):
        body_n=len(self.vertices['body']);values=[]
        for face in faces:
            weights=[]
            for sid in face:
                name,i=('body',int(sid)) if sid<body_n else ('head',int(sid-body_n));w=self.W[name][i];weights.append(w/w.sum())
            values.append(weights)
        return np.einsum('nkb,nk->nb',np.asarray(values),bary)
    def target(self,root,triangles,bary,weights):
        attach=np.einsum('pnkj,nk->pnj',triangles,bary);offset=root[0]-attach[0];transport=np.zeros_like(attach)
        for j in np.flatnonzero(np.any(weights,axis=0)):
            rotation=self.globals[:,j,:3,:3]@np.linalg.inv(self.rest[self.names[j]][:3,:3])
            transport+=np.einsum('pij,nj->pni',rotation,offset)*weights[None,:,j,None]
        return attach+transport


def binding_metrics(model,name,ids,faces,bary,weight,state,normalized):
    root=model.positions(name,ids,weight,state,normalized);triangles=model.skin(faces,weight,state,normalized)
    target=model.target(root,triangles,bary,model.skin_weights(faces,bary));distance,signed=triangle_distances(root,triangles)
    _,expected_signed=triangle_distances(target,triangles)
    arrays={'transportedRootError':np.linalg.norm(root-target,axis=-1),'absoluteTriangleDistance':distance,
            'triangleDistanceChange':abs(distance-distance[:1]),'absoluteNormalGap':abs(signed),
            'normalGapChange':abs(signed-signed[:1]),'outsideSignedGap':np.maximum(signed,0),
            'interiorSignedDepth':np.maximum(-signed,0)}
    out={k:{g:stat(v[indices]) for g,indices in model.groups.items()} for k,v in arrays.items()}
    out['restTriangleDistance']=stat(distance[0]);out['restSignedNormalGap']=stat(abs(signed[0]))
    out['restSideCounts']={'outside':int((signed[0]>1e-5).sum()),'interior':int((signed[0]<-1e-5).sum()),'nearSurface':int((abs(signed[0])<=1e-5).sum())}
    out['transportedErrorByRestSide']={side:{g:stat(arrays['transportedRootError'][indices][:,mask]) for g,indices in model.groups.items()}
        for side,mask in [('outside',signed[0]>1e-5),('interior',signed[0]<-1e-5)]}
    worst={}
    for group,indices in model.groups.items():
        values=arrays['transportedRootError'][indices];p,n=np.unravel_index(int(np.argmax(values)),values.shape)
        worst[group]={'rootVertex':int(ids[n]),'pose':model.poses[indices[p]][0],'residual':float(values[p,n]),
            'signedGap':float(signed[indices[p],n]),'expectedSignedGap':float(expected_signed[indices[p],n]),'triangleDistance':float(distance[indices[p],n])}
    out['worstTransportedRoot']=worst
    unexpected=(signed*expected_signed<0)&(abs(expected_signed)>1e-5)&(abs(distance-abs(signed))<1e-5)
    out['oppositeExpectedSideWithProjectionInsideFrozenTriangle']={g:int(unexpected[indices].sum()) for g,indices in model.groups.items()}
    return out


def local_orientation(model,name,triangle_ids,weight,state,normalized):
    faces=np.asarray(model.shapes[name].tris,int)[triangle_ids];ids,inverse=np.unique(faces,return_inverse=True)
    positions=model.positions(name,ids,weight,state,normalized)[:,inverse.reshape(-1,3)]
    cross=np.cross(positions[:,:,1]-positions[:,:,0],positions[:,:,2]-positions[:,:,0]);area=np.linalg.norm(cross,axis=-1)/2
    neutral=model.positions(name,ids,weight,{},normalized)[0,inverse.reshape(-1,3)]
    normal=np.cross(neutral[:,1]-neutral[:,0],neutral[:,2]-neutral[:,0]);rest_area=np.linalg.norm(normal,axis=1)/2
    W=model.W[name][faces];W=W/W.sum(2)[:,:,None];W=W.mean(1);reference=np.zeros_like(cross)
    for j in np.flatnonzero(np.any(W,axis=0)):
        rotation=model.globals[:,j,:3,:3]@np.linalg.inv(model.rest[model.names[j]][:3,:3])
        transport=np.linalg.pinv(rotation).transpose(0,2,1)
        reference+=np.einsum('pij,nj->pni',transport,normal)*W[None,:,j,None]
    dot=np.einsum('pnj,pnj->pn',cross,reference);valid=rest_area>1e-10
    return {g:{'minimumArea':float(area[indices][:,valid].min()),'minimumOwnNeutralAreaRatio':float((area[indices][:,valid]/rest_area[valid]).min()),
               'negativeTransportedNormalDotCount':int((dot[indices][:,valid]<0).sum()),
               'areaBelow1eMinus8Count':int((area[indices][:,valid]<1e-8).sum())} for g,indices in model.groups.items()}


def build(low,high,tri,skeleton,output,baseline=None,pynifly=None):
    low,high,tri,skeleton=[Path(p).resolve(strict=True) for p in (low,high,tri,skeleton)]
    files=[low,high,tri,skeleton,Path(__file__),ROOT / 'src/main/python/build-tools/audit-composed-geometry.py',ROOT / 'src/main/python/build-tools/composed_vr.py',ROOT / 'src/main/python/build-tools/body_weight.py',
           ROOT / 'src/main/python/build-tools/breast_rig.py',ROOT / 'src/main/python/build-tools/surface_collar.py',ROOT / 'src/main/python/build-tools/collar_weights.py',ROOT / 'src/main/resources/recipes/breast-rig-collar.json']
    if baseline is not None:baseline=Path(baseline).resolve(strict=True);files.append(baseline)
    frozen={str(p):rig.sha256(p) for p in files};out=rig.safe_output(output,files);api,Trip,_=rig.load_pynifly(pynifly)
    n0=api.NifFile(str(low));n1=api.NifFile(str(high));skel=api.NifFile(str(skeleton));raw=Trip.from_filepath(str(tri)).shapes
    model=Model(n0,n1,skel,raw);models={'candidate':model}
    if baseline is not None:models['baseline-same-neutral-geometry']=Model(api.NifFile(str(baseline)),n1,skel,raw)
    rp=json.loads((ROOT / 'src/main/resources/recipes/breast-rig-collar.json').read_text());s=model.shapes
    body_v=np.asarray(s['body'].verts);head_v=np.asarray(s['head'].verts);skin=np.r_[body_v,head_v]
    faces=np.r_[s['body'].tris,np.asarray(s['head'].tris)+len(body_v)];project=Projector(skin,faces)
    collar_rule=dict(rp['collar']);collar_rule['anchorCountRange']=[1,500]
    collar=surface.Collar(body_v,s['body'].tris,head_v,s['head'].tris,collar_rule,Projector(body_v,s['body'].tris))
    bindings={'skin-collar':('head',collar.anchors,np.asarray(s['body'].tris)[collar.binding.indices],collar.binding.weights)}
    binding_report={}
    for rule in rp['layers']:
        name=rule['shape'];layer=surface.Layer(s[name].verts,s[name].tris,skin,faces,rule,project);groups=np.flatnonzero(layer.weights>0)
        ids=[int(g[np.all(np.asarray(s[name].verts)[g]==point,axis=1)][0]) for g,point in zip(layer.groups,layer.binding.points)]
        bindings[name]=(name,np.asarray(ids)[groups],layer.binding.faces[layer.binding.indices[groups]],layer.binding.weights[groups])
        binding_report[name]={'selectedGroups':groups.tolist(),'rootIds':np.asarray(ids)[groups].tolist(),'frozenLayerWeights':layer.weights[groups].tolist()}
    states={'neutral':{},'breast-half':{'CLAWTorsoBreastSize':.5},'breast-full':{'CLAWTorsoBreastSize':1.},
            'girth-quarter':{'CLAWTorsoGirth':.25},'girth-half':{'CLAWTorsoGirth':.5},'girth-full':{'CLAWTorsoGirth':1.},
            'breast-full-girth-quarter':{'CLAWTorsoBreastSize':1.,'CLAWTorsoGirth':.25},
            'head-size-full':{'CLAWHeadSize':1.},'head-size-breast-full':{'CLAWHeadSize':1.,'CLAWTorsoBreastSize':1.}}
    out.mkdir();report={'status':'building','inputsAndExecutedSha256':frozen,'bindings':binding_report,'models':{},
        'scope':'Actual LBS, actual deformed frozen triangles, transported rest offsets, raw and normalized conventions. Surface distances are distinct from target residuals. Finite states and declared poses only; local plane-side/orientation indicators do not certify global self-intersection freedom, coverage, camera clearance or appearance.'}
    try:
        roi={}
        breast=rig.dense_morph(raw,'head','CLAWTorsoBreastSize',len(head_v));active=np.any(breast!=0,axis=1)
        roi['head']=np.flatnonzero(np.any(active[np.asarray(s['head'].tris)],axis=1))
        if not len(roi['head']):
            active=(head_v[:,2]<108)&(head_v[:,1]<46)
            roi['head']=np.flatnonzero(np.any(active[np.asarray(s['head'].tris)],axis=1))
        roi['body']=np.unique(collar.binding.indices)
        for label,current in models.items():
            rows={}
            for weight in ((0.,.3,1.) if label=='candidate' else (0.,)):
                weight_rows={}
                for state_name,state in states.items():
                    state_rows={}
                    for normalized in (False,True):
                        mode='normalized' if normalized else 'rawPacked'
                        state_rows[mode]={name:binding_metrics(current,*binding,weight,state,normalized) for name,binding in bindings.items()}
                        state_rows[mode]['orientation']={name:local_orientation(current,name,ids,weight,state,normalized) for name,ids in roi.items()}
                    weight_rows[state_name]=state_rows
                rows[str(weight)]=weight_rows;print('GEOMETRY_AUDIT|'+label+'|weight'+str(weight),flush=True)
            report['models'][label]=rows
        if any(rig.sha256(p)!=h for p,h in frozen.items()):raise ValueError('Geometry audit source/input changed')
        report['status']='completed-offline-actual-gap-and-orientation-measurements-runtime-visual-pending'
    except Exception:
        report['status']='FAILED-incomplete-audit';raise
    finally:(out/'geometry-audit.json').write_text(json.dumps(report,indent=2))
    return out/'geometry-audit.json'
