"""Independent neutral weight endpoints calibrated from actual human geometry.

V(w,c) = V0 + w*(V1-V0) + sum(c[m]*TRI[m]). Actor weight never multiplies
the already-applied named morph coefficients. Existing skin/binds/UV/TRI survive.
"""
from pathlib import Path
import heapq
import importlib.util
import itertools
import json
import shutil
import struct
import numpy as np
from scipy.optimize import lsq_linear
import breast_rig as rig
import head_split
import surface_collar as surface
import morph_calibration as calibration

ROOT=Path(__file__).resolve().parents[1]


def interpolate(low,high,weight,morphs=None,coefficients=None):
    if not np.isfinite(weight) or not 0<=weight<=1:raise ValueError('Weight must be normalized0..1')
    low=np.asarray(low,float);high=np.asarray(high,float)
    if low.shape!=high.shape or low.ndim!=2 or low.shape[1]!=3:raise ValueError('Endpoint arrays differ')
    result=low+weight*(high-low)
    for name,value in (coefficients or {}).items():result+=float(value)*np.asarray((morphs or {})[name],float)
    if not np.isfinite(result).all():raise ValueError('Nonfinite composed geometry')
    return result


class Projector:
    """Exact triangle-AABB BVH; public closest_surface supplies leaf geometry."""
    def __init__(self,vertices,faces):
        self.vertices=surface.positions(vertices);self.faces=surface.triangles(faces,len(vertices));points=self.vertices[self.faces]
        self.lo=points.min(1);self.hi=points.max(1);self.centres=(self.lo+self.hi)/2;self.nodes=[]
        def build(ids):
            index=len(self.nodes);lo=self.lo[ids].min(0);hi=self.hi[ids].max(0);self.nodes.append(None)
            if len(ids)<=24:self.nodes[index]=(lo,hi,ids,None,None)
            else:
                axis=int(np.ptp(self.centres[ids],axis=0).argmax());order=ids[np.argsort(self.centres[ids,axis],kind='stable')];mid=len(ids)//2
                left=build(order[:mid]);right=build(order[mid:]);self.nodes[index]=(lo,hi,None,left,right)
            return index
        build(np.arange(len(self.faces)))
    @staticmethod
    def bound(point,lo,hi):return float(np.sum(np.maximum(np.maximum(lo-point,point-hi),0)**2))
    def __call__(self,point):
        point=np.asarray(point,float);queue=[(0.,0)];best=(np.inf,None,None)
        while queue:
            bound,index=heapq.heappop(queue)
            if bound>best[0]*best[0]+1e-12:break
            lo,hi,ids,left,right=self.nodes[index]
            if ids is not None:
                hit,j,distance=surface.closest_surface(point,self.vertices,self.faces[ids])
                if distance<best[0]:best=(distance,hit,int(ids[j]))
            else:
                for child in (left,right):
                    a,b,_,_,_=self.nodes[child];lower=self.bound(point,a,b)
                    if lower<=best[0]*best[0]+1e-12:heapq.heappush(queue,(lower,child))
        return best[1],best[2],best[0]


def calibration_module():
    path=ROOT/'scripts/calibrate-morph-links.py';spec=importlib.util.spec_from_file_location('claw_weight_calibration_fields',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def regional_basis(vertices,bones,features,breast_delta):
    """Smooth anatomical soft-tissue fields measured by the calibration facade.

    Broad named morphs cannot independently reproduce a human endpoint which
    changes only forearms/calves. Bone-region radial fields supply those missing
    independent directions without compensating with unrelated torso morphs.
    """
    import re
    v=np.asarray(vertices,float);count=len(v);result={}
    def bone(pattern):return sum((x for n,x in bones.items() if re.search(pattern,n,re.I)),np.zeros(count))
    def soft(value):return rig.smooth(np.asarray(value)/.25)
    spine=bone('Spine');selected=spine>=.25;lo,hi=np.quantile(v[selected,2],[.02,.98]);z=(v[:,2]-lo)/(hi-lo)
    def window(low,high):return rig.smooth((z-(low-.08))/.08)*rig.smooth(((high+.08)-z)/.08)
    for region,pattern in [('upperarm','UpperArm|Upperarm'),('forearm','Forearm'),('thigh','Thigh'),('calf','Calf')]:
        field=np.zeros_like(v)
        for side in ('L','R'):
            key=region+'.'+side
            if key not in features:continue
            mask=bone(r'NPC '+side+r' .*('+pattern+r')');ids=features[key]['indices'];cloud=v[ids];centre=cloud.mean(0)
            _,_,axes=np.linalg.svd(cloud-centre,full_matrices=False);axis=axes[0];relative=v-centre
            radial=relative-(relative@axis)[:,None]*axis;field+=radial*soft(mask)[:,None]
        result[region+'.radial']=field
    for region,mask in [('waist',soft(spine)*window(.12,.45)),('thorax',soft(spine)*window(.48,.95))]:
        for axis,dimension in [('width',0),('depth',1)]:
            key=region+'.'+axis
            if key not in features:continue
            ids=features[key]['indices'];centre=v[ids,dimension].mean();field=np.zeros_like(v);field[:,dimension]=(v[:,dimension]-centre)*mask
            result[key]=field
    if 'hip.width' in features:
        field=np.zeros_like(v);centre=v[features['hip.width']['indices'],0].mean();field[:,0]=(v[:,0]-centre)*soft(bone('Pelv|Butt'));result['hip.width']=field
    if 'belly.front' in features:
        ids=features['belly.front']['indices'];scale=features['belly.front']['scale'];threshold=np.min(v[ids,1])
        field=np.zeros_like(v);field[:,1]=scale*soft(spine)*window(.12,.45)*rig.smooth((v[:,1]-threshold+scale*.2)/(scale*.2))
        result['belly.front']=field
    if 'breast.width' in features:
        support=np.linalg.norm(breast_delta,axis=1);support=rig.smooth(support/max(float(support.max()),1e-30))
        ids=features['breast.width']['indices'];field=np.zeros_like(v);field[:,0]=(v[:,0]-v[ids,0].mean())*support;result['breast.width']=field
        field=np.zeros_like(v);field[:,1]=features['breast.front']['scale']*support;result['breast.front']=field
    return result


def fit_field(api,Trip,human0,human1,wolf,wolf_tri,sex,profile):
    module=calibration_module();h0=api.NifFile(str(human0));h1=api.NifFile(str(human1));nif=api.NifFile(str(wolf))
    human_shape=profile['humanShapes'][sex];hv,hb,_=module.mesh(h0,[human_shape]);end,_,_=module.mesh(h1,[human_shape])
    if hv.shape!=end.shape:raise ValueError('Human weight endpoint topology differs')
    a=next(s for s in h0.shapes if s.name==human_shape);b=next(s for s in h1.shapes if s.name==human_shape)
    if a.tris!=b.tris or a.uvs!=b.uvs:raise ValueError('Human endpoint indices/UV differ')
    wv,wb,offsets=module.mesh(nif,['body','head']);raw=Trip.from_filepath(str(wolf_tri)).shapes;s={x.name:x for x in nif.shapes}
    collar_rule=json.loads((ROOT/'recipes/breast-rig-collar.json').read_text())['collar'];collar_rule=dict(collar_rule)
    collar_rule['anchorCountRange']=[1,500]
    collar=surface.Collar(s['body'].verts,s['body'].tris,s['head'].verts,s['head'].tris,collar_rule,Projector(s['body'].verts,s['body'].tris))
    breast=np.concatenate([rig.dense_morph(raw,name,'CLAWTorsoBreastSize',len(s[name].verts)) for name in ['body','head']])
    hf=module.fields(hv,hb);wf=module.fields(wv,wb,np.linalg.norm(breast,axis=1)>1e-5 if sex=='female' else np.zeros(len(wv),bool))
    feature_names=sorted(set(hf)&set(wf));hfields=[hf[n] for n in feature_names];wfields=[wf[n] for n in feature_names]
    anatomical=regional_basis(wv,wb,wf,breast);fields={};skin_fields=[];basis=[]
    for name,combined in anatomical.items():
        field={n:np.zeros((len(shape.verts),3)) for n,shape in s.items()}
        for n,(start,count) in offsets.items():field[n]=combined[start:start+count].copy()
        field['head']=collar.reconcile(field['body'],field['head'])
        fields[name]=field;skin_fields.append(np.concatenate([field[n] for n in ['body','head']]));basis.append(name)
    target=calibration.response(end-hv,hfields);matrix=np.column_stack([calibration.response(d,wfields) for d in skin_fields])
    # The same frozen regional projections as human morph calibration, now on
    # an actual endpoint delta. Signed bounded coefficients form a neutral base
    # field; they are never sent as named SKEE morph coefficients.
    regularizer=profile['regularizer'];A=np.r_[matrix,np.eye(len(basis))*np.sqrt(regularizer)];y=np.r_[target,np.zeros(len(basis))]
    answer=lsq_linear(A,y,bounds=(-profile['maximumBasisMagnitude'],profile['maximumBasisMagnitude']),tol=1e-12,max_iter=2000)
    if not answer.success:raise ValueError('Human endpoint calibration failed')
    coefficients=answer.x;mass={name:sum((coefficients[j]*fields[field][name] for j,field in enumerate(basis)),np.zeros((len(shape.verts),3))) for name,shape in s.items()}
    # Whole cards follow the frozen skin root displacement. Blend patches follow
    # per vertex. This is geometric neutral-weight inheritance, not a P1 driver.
    skin=np.r_[s['body'].verts,s['head'].verts];faces=np.r_[s['body'].tris,np.asarray(s['head'].tris)+len(s['body'].verts)]
    skin_mass=np.r_[mass['body'],mass['head']];projector=Projector(skin,faces);layer_report={}
    for name,shape in s.items():
        if not (name.startswith('fur_') or name.endswith('Blend')):continue
        v=np.asarray(shape.verts);rule={'mode':'vertices' if name=='ChestBlend' else 'cards',
            'bounds':[(v.min(0)-1).tolist(),(v.max(0)+1).tolist()],'fade':[.01,.01,.01],
            'distanceFade':[1000000.,1000001.],'weldDecimals':5}
        layer=surface.Layer(v,shape.tris,skin,faces,rule,projector);translation=layer.binding.evaluate(skin_mass);field=np.zeros_like(v)
        for ids,value in zip(layer.groups,translation):field[ids]=value
        mass[name]=field;layer_report[name]={'groups':len(layer.groups),'maxMovement':float(np.linalg.norm(field,axis=1).max()),
            'staticRootOffsetDeltaMax':float(np.max(np.linalg.norm(translation-layer.binding.evaluate(skin_mass),axis=1)))}
    prediction=matrix@coefficients
    if np.linalg.norm(prediction-target)>=np.linalg.norm(target)-1e-12:raise ValueError('Endpoint field does not improve the zero-weight baseline')
    if max(np.linalg.norm(v,axis=1).max() for v in mass.values())<.0001:raise ValueError('Human endpoint projection produced a packed no-op')
    report={'features':feature_names,'humanEndpointFeatureDelta':target.tolist(),'wolfEndpointFeatureDelta':prediction.tolist(),
        'basisCoefficients':dict(zip(basis,coefficients.tolist())),'zeroResidual':float(np.linalg.norm(target)),
        'fittedResidual':float(np.linalg.norm(prediction-target)),'humanMaxDisplacement':float(np.linalg.norm(end-hv,axis=1).max()),
        'collarAnchors':collar.anchors.tolist(),'collarOffsetChangeMax':float(np.linalg.norm(mass['head'][collar.anchors]-collar.binding.evaluate(mass['body']),axis=1).max()),
        'layers':layer_report,'formula':'V(w,c)=V0+w*(V1-V0)+sum(c[m]*TRI[m]); neutral-base field calibrated from actual human_1-human_0. Named coefficients and TRI offsets are independent of weight.',
        'method':'Same frozen anatomical signed regional projections as calibrate-morph-links.py; bounded least squares, whole-card/per-vertex root inheritance and frozen collar constraints. This is geometry calibration, not appearance acceptance.'}
    return nif,raw,mass,report


def transport_frames(vertices,faces,delta,rows):
    """Transport authored normal/tangent frames with a local deformation Jacobian."""
    v=np.asarray(vertices,float);d=np.asarray(delta,float);t=np.asarray(faces,int)
    edges=np.unique(np.sort(np.r_[t[:,[0,1]],t[:,[1,2]],t[:,[2,0]]],axis=1),axis=0)
    E=np.zeros((len(v),3,3));D=np.zeros_like(E)
    for side in (0,1):
        a=edges[:,side];b=edges[:,1-side];x=v[b]-v[a];y=d[b]-d[a]
        np.add.at(E,a,x[:,:,None]*x[:,None,:]);np.add.at(D,a,y[:,:,None]*x[:,None,:])
    gradient=D@np.linalg.pinv(E,rcond=1e-8);F=np.eye(3)+gradient;active=np.linalg.norm(gradient,axis=(1,2))>1e-10
    result=rows.copy();ids=np.flatnonzero(active)
    if not len(ids):return result
    normal=rows[ids,20:23].astype(float)/127.5-1;tangent=rows[ids,24:27].astype(float)/127.5-1
    bitangent=np.column_stack([np.frombuffer(rows.tobytes(),'<f4').reshape(len(rows),10)[ids,3],rows[ids,23].astype(float)/127.5-1,rows[ids,27].astype(float)/127.5-1])
    normal=np.einsum('nij,nj->ni',np.linalg.pinv(F[ids]).transpose(0,2,1),normal);normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-30)
    tangent=np.einsum('nij,nj->ni',F[ids],tangent);tangent-=normal*np.sum(tangent*normal,axis=1)[:,None];tangent/=np.maximum(np.linalg.norm(tangent,axis=1)[:,None],1e-30)
    handed=np.sign(np.sum(np.cross(normal,tangent)*bitangent,axis=1));handed[handed==0]=1
    bitangent=np.cross(normal,tangent)*handed[:,None]
    pack=lambda x:np.clip(np.rint((x+1)*127.5),0,255).astype(np.uint8)
    result[ids,20:23]=pack(normal);result[ids,24:27]=pack(tangent);result[ids,23]=pack(bitangent[:,1]);result[ids,27]=pack(bitangent[:,2])
    for i,value in zip(ids,bitangent[:,0]):result[i,12:16]=np.frombuffer(struct.pack('<f',float(value)),np.uint8)
    return result


def move_nif(data,nif,mass):
    container=head_split.Nif(data);changed=[]
    for shape in nif.shapes:
        delta=mass[shape.name];new=np.asarray(np.asarray(shape.verts,float)+delta,dtype='<f4')
        if not np.any(delta):continue
        block=container.blocks[shape.id];extra=struct.unpack_from('<I',block,4)[0];skinid=struct.unpack_from('<I',block,88+4*extra)[0]
        dataid,partid=struct.unpack_from('<II',container.blocks[skinid]);partition=container.blocks[partid]
        count,size,stride,desc=struct.unpack_from('<IIIQ',partition)
        if stride!=40 or size//stride!=len(new):raise ValueError('Unexpected packed SSE vertex layout')
        rows=np.frombuffer(partition[20:20+size],np.uint8).reshape(-1,40).copy();result=transport_frames(shape.verts,shape.tris,delta,rows)
        result[:,:12]=new.view(np.uint8).reshape(-1,12)
        # UV bytes, skin-weight halves and palette indices remain exact.
        if not np.array_equal(rows[:,16:20],result[:,16:20]) or not np.array_equal(rows[:,28:40],result[:,28:40]):raise ValueError('Endpoint changed UV/skin data')
        container.blocks[partid]=partition[:20]+result.tobytes()+partition[20+size:];changed.append(partid)
    return container.bytes(),changed


def area_path(vertices,faces,delta):
    """Continuous triangle-area minima for every neutral weight0..1 segment."""
    v=np.asarray(vertices,float);t=np.asarray(faces,int);d=np.asarray(delta,float)
    e=v[t[:,1]]-v[t[:,0]];f=v[t[:,2]]-v[t[:,0]];a=d[t[:,1]]-d[t[:,0]];b=d[t[:,2]]-d[t[:,0]]
    c0=np.cross(e,f);c1=np.cross(a,f)+np.cross(e,b);c2=np.cross(a,b)
    before=np.linalg.norm(c0,axis=1);minimum=before.copy();at=np.zeros(len(t))
    coefficients=np.stack([np.sum(c0*c0,1),2*np.sum(c0*c1,1),np.sum(c1*c1,1)+2*np.sum(c0*c2,1),2*np.sum(c1*c2,1),np.sum(c2*c2,1)],axis=1)
    for i,co in enumerate(coefficients):
        derivative=np.array([4*co[4],3*co[3],2*co[2],co[1]])
        roots=np.roots(np.trim_zeros(derivative,'f')) if np.any(derivative) else []
        values=[0.,1.]+[float(x.real) for x in roots if abs(x.imag)<1e-8 and 0<x.real<1]
        norm=[np.linalg.norm(c0[i]+x*c1[i]+x*x*c2[i]) for x in values];j=int(np.argmin(norm));minimum[i]=norm[j];at[i]=values[j]
    ratio=minimum/np.maximum(before,1e-30);valid=before>1e-10
    if np.any(minimum[valid]<1e-9):raise ValueError('Weight interpolation creates a degenerate triangle')
    full=c0+c1+c2;reversed_=np.einsum('ij,ij->i',c0,full)<0
    return {'continuousMinArea':float(minimum[valid].min()/2),'minimumOwnRestAreaRatio':float(ratio[valid].min()),
            'normalReversalCount':int(reversed_.sum()),'worstTriangle':int(np.where(valid)[0][np.argmin(ratio[valid])]),
            'worstWeight':float(at[np.where(valid)[0][np.argmin(ratio[valid])]])}


def build(female,female_tri,male,male_tri,human_root,profile_file,output,pynifly=None):
    profile_file=Path(profile_file).resolve(strict=True);p=json.loads(profile_file.read_text())
    if p!=json.loads((ROOT/'recipes/body-weight.json').read_text()):raise ValueError('Unreviewed body weight profile')
    human_root=Path(human_root).resolve(strict=True);sources={'female':(Path(female).resolve(strict=True),Path(female_tri).resolve(strict=True)),
             'male':(Path(male).resolve(strict=True),Path(male_tri).resolve(strict=True))}
    inputs=[profile_file]
    for sex,(body,tri) in sources.items():
        for path,key in ((body,'nifSha256'),(tri,'triSha256')):
            if rig.sha256(path)!=p['bodies'][sex][key]:raise ValueError('Pinned wolf input changed: '+sex+'/'+key)
        inputs.extend([body,tri])
        for i in (0,1):
            path=human_root/(sex+'body_'+str(i)+'.nif')
            if rig.sha256(path)!=p['humanInputs'][sex][i]:raise ValueError('Human endpoint pin changed')
            inputs.append(path)
    out=rig.safe_output(output,inputs);api,Trip,dependency=rig.load_pynifly(pynifly)
    files=inputs+[Path(__file__),ROOT/'scripts/build-body-weight.py',ROOT/'scripts/calibrate-morph-links.py',ROOT/'scripts/morph_calibration.py',
                  ROOT/'scripts/head_split.py',ROOT/'scripts/surface_collar.py',ROOT/'scripts/breast_rig.py',ROOT/'recipes/breast-rig-collar.json']
    files += [*sorted((dependency/'pyn').glob('*.py')),*sorted((dependency/'tri').glob('*.py')),dependency/'NiflyDLL.dll']
    frozen={str(x):rig.sha256(x) for x in files};out.mkdir();report={'status':'building-unverified-do-not-install','inputsAndExecutedSha256':frozen,'bodies':{}}
    try:
        for sex,(body,tri) in sources.items():
            print('BODY_WEIGHT|calibrating '+sex,flush=True)
            nif,raw,mass,cal=fit_field(api,Trip,human_root/(sex+'body_0.nif'),human_root/(sex+'body_1.nif'),body,tri,sex,p)
            data,changed=move_nif(body.read_bytes(),nif,mass);folder=out/'meshes/actors/werewolfbeast/character assets';folder.mkdir(parents=True,exist_ok=True)
            low=folder/(sex+'bodywerewolf_0.nif');high=folder/(sex+'bodywerewolf_1.nif');low.write_bytes(body.read_bytes());high.write_bytes(data)
            shutil.copyfile(tri,folder/(sex+'bodywerewolf.tri'));actual=api.NifFile(str(high));a={x.name:x for x in actual.shapes};checks={}
            for shape in nif.shapes:
                other=a[shape.name];expected=np.asarray(np.asarray(shape.verts,float)+mass[shape.name],np.float32)
                if not np.array_equal(np.asarray(other.verts,np.float32),expected):raise ValueError('Endpoint position readback failed')
                if other.tris!=shape.tris or other.uvs!=shape.uvs or other.bone_weights!=shape.bone_weights:raise ValueError('Endpoint topology/UV/weights changed')
                if not np.array_equal(rig.matrix(shape.global_to_skin),rig.matrix(other.global_to_skin)):raise ValueError('Endpoint skin frame changed')
                for bone in shape.bone_weights:
                    if not np.array_equal(rig.matrix(shape.get_shape_skin_to_bone(bone)),rig.matrix(other.get_shape_skin_to_bone(bone))):raise ValueError('Endpoint bind changed')
                checks[shape.name]={'movedVertices':int(np.any(mass[shape.name]!=0,axis=1).sum()),'maxDisplacement':float(np.linalg.norm(mass[shape.name],axis=1).max()),
                    'neutralWeightPath':area_path(shape.verts,shape.tris,mass[shape.name])}
            if low.read_bytes()==high.read_bytes():raise ValueError('Distinct endpoints collapsed to identical bytes')
            report['bodies'][sex]={'low':str(low),'high':str(high),'lowSha256':rig.sha256(low),'highSha256':rig.sha256(high),
                'triSha256':rig.sha256(tri),'calibration':cal,'readback':checks,'changedPartitionBlocks':changed}
            print('BODY_WEIGHT|verified '+sex+' distinct endpoints',flush=True)
        if any(rig.sha256(path)!=value for path,value in frozen.items()):raise ValueError('Endpoint input/source/dependency changed')
        report['status']='verified-offline-distinct-neutral-weight-endpoints-runtime-and-appearance-pending'
    except Exception:
        report['status']='FAILED-unverified-do-not-install';raise
    finally:(out/'body-weight-report.json').write_text(json.dumps(report,indent=2))
    return out/'body-weight-report.json'
