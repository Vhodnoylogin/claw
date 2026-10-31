"""Opt-in existing-XP32 breast rig: pure numeric core and lazy public PyNifly adapter.

This is post-export tooling, not a runtime driver or an install/package action.
"""
from __future__ import annotations
from pathlib import Path
import hashlib,heapq,importlib.util,json,math,platform,shutil,sys
import numpy as np
import surface_collar as surface

ROOT=Path(__file__).resolve().parents[4]
TOP_KEYS={'schemaVersion','name','status','inputs','spineBone','p1Bones','requiredNodes','publicMorph',
          'shapeBasis','mobility','collar','layers','verification','outputRelativeNif','_note'}

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def smooth(value):
    x=np.clip(np.asarray(value,dtype=float),0,1)
    return x*x*(3-2*x)

def stats(values):
    x=np.asarray(values,dtype=float)
    if not np.isfinite(x).all():raise ValueError('Nonfinite verification result')
    return {'n':int(x.size),'p95':float(np.quantile(x,.95))if x.size else 0.,
            'max':float(x.max())if x.size else 0.}

def load_profile(filename):
    def unique(pairs):
        result={}
        for k,v in pairs:
            if k in result:raise ValueError('Duplicate profile key: '+k)
            result[k]=v
        return result
    p=json.loads(Path(filename).read_text(encoding='utf-8-sig'),object_pairs_hook=unique,
                 parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite profile value')))
    if set(p)!=TOP_KEYS or p['schemaVersion']!=1:raise ValueError('Unknown/incomplete breast rig profile')
    template=json.loads((ROOT / 'src/main/resources/recipes/breast-rig.json').read_text())
    # This first source candidate deliberately has a narrow schema. Numeric tuning
    # is supported within these fields; arbitrary transforms/mappings are not.
    def structure(value,expected):
        if isinstance(expected,dict):
            if not isinstance(value,dict)or set(value)!=set(expected):raise ValueError('Profile object fields changed')
            for k in value:structure(value[k],expected[k])
        elif isinstance(expected,list):
            if not isinstance(value,list)or len(value)!=len(expected):raise ValueError('Profile array size changed')
            for a,b in zip(value,expected):structure(a,b)
        elif isinstance(expected,(int,float)):
            if isinstance(value,bool)or not isinstance(value,(int,float))or not math.isfinite(value):raise ValueError('Invalid profile number')
        elif not isinstance(value,str):raise ValueError('Invalid profile string')
    structure(p,template)
    for k in ['bodyNifSha256','triSha256','skeletonSha256']:
        h=p['inputs'][k]
        if len(h)!=64 or any(c not in '0123456789abcdef'for c in h):raise ValueError('Invalid input hash')
    if p['spineBone']!='NPC Spine2 [Spn2]'or p['p1Bones']!=['NPC L Breast P1','NPC R Breast P1']:
        raise ValueError('Only the existing bilateral XP32 P1/Spine2 contract is supported')
    if p['requiredNodes']!=template['requiredNodes']or p['publicMorph']!='CLAWTorsoBreastSize':raise ValueError('Rig ownership contract changed')
    if p['inputs']['sourceNodeCount']!=85 or p['inputs']['outputNodeCount']!=91 or p['inputs']['anchorCount']!=55:raise ValueError('Raw 85-node / six-node / 55-anchor contract required')
    if [(x['shape'],x['mode'])for x in p['layers']]!=[(x['shape'],x['mode'])for x in template['layers']]or p['collar']['source']!='body'or p['collar']['target']!='head':
        raise ValueError('Layer/collar ownership changed')
    for k in ['lowerWidth']:
        if p['shapeBasis'][k]<=0:raise ValueError('Invalid shape basis width')
    b=p['shapeBasis'];q=p['mobility'];v=p['verification']
    if min(b.values())<0 or b['massForward']<=0:raise ValueError('Invalid reconstruction basis')
    if not 0<q['maximum']<=.4 or min(q[k]for k in ['bottomWidth','topWidth','capacityGuardWidth','minimum'])<=0:
        raise ValueError('Invalid mobility limits')
    if q['minimum']>=q['maximum'] or q['bottomStart']>=q['topEnd']or not 0<=q['weldDecimals']<=8:raise ValueError('Invalid mobility support')
    if not 0<v['p1Degrees']<=3 or min(v[k]for k in ['nodeMatrixTolerance','packedWeightSumTolerance','normalizedOrdinaryMaxError','rawOrdinaryMaxError'])<=0:
        raise ValueError('Invalid verification tolerances')
    rel=Path(p['outputRelativeNif'])
    if rel.is_absolute()or rel.drive or '..'in rel.parts or rel.suffix.lower()!='.nif':raise ValueError('Unsafe relative NIF output')
    if p['outputRelativeNif']!=template['outputRelativeNif']:raise ValueError('Output must retain the pinned BODYTRI-relative filename')
    return p

def safe_output(output,inputs,*,repo=ROOT,live_roots=()):
    out=Path(output).resolve()
    if out.exists():raise ValueError('Output directory already exists')
    blocked=[Path(repo).resolve(),*[Path(p).resolve().parent for p in inputs],*[Path(p).resolve()for p in live_roots]]
    if any(out==p or p in out.parents for p in blocked):raise ValueError('Output is inside a source/live directory')
    if any(p.casefold()in {'mods','mo2','modorganizer','overwrite','skyrim vr','skyrimvr','skyrim special edition'}for p in out.parts):
        raise ValueError('Output points into a live game/mod-manager tree')
    return out

class SurfaceProjector:
    """Exact AABB-pruned nearest triangle; no Blender/scipy dependency.

    A triangle whose AABB is farther than a known surface hit cannot win.
    The final answer uses the existing public closest_surface implementation.
    """
    def __init__(self,vertices,faces):
        self.v=surface.positions(vertices);self.t=surface.triangles(faces,len(self.v))
        points=self.v[self.t];self.lo=points.min(axis=1);self.hi=points.max(axis=1)
    def __call__(self,point):
        point=np.asarray(point,float)
        bound=np.sum(np.maximum(np.maximum(self.lo-point,point-self.hi),0)**2,axis=1)
        first=int(bound.argmin());hit,_,distance=surface.closest_surface(point,self.v,self.t[first:first+1])
        ids=np.flatnonzero(bound<=distance*distance+1e-10)
        hit,index,distance=surface.closest_surface(point,self.v,self.t[ids])
        return hit,int(ids[index]),distance

def reconstruct_mobility(vertices,delta,anchors,profile):
    v=surface.positions(vertices);d=surface.positions(delta)
    if d.shape!=v.shape:raise ValueError('Morph/vertex count mismatch')
    b=profile['shapeBasis'];p=profile['mobility'];low=smooth((b['lowerTop']-v[:,2])/b['lowerWidth'])
    direction=np.column_stack([np.sign(v[:,0])*b['massLateral'],b['massForward']+b['projectionForward']*low,
                               -(b['projectionDown']+b['sagDown'])*low])
    mask=np.maximum(np.sum(d*direction,axis=1)/np.sum(direction*direction,axis=1),0)
    residual=np.linalg.norm(d-mask[:,None]*direction,axis=1)
    if residual.max()>.0003:raise ValueError('TRI does not match the moderate reconstruction basis')
    if mask.max()>1.0001:raise ValueError('Reconstructed scalar exceeds the bounded mask')
    mobile=p['maximum']*mask*smooth((v[:,2]-p['bottomStart'])/p['bottomWidth'])*smooth((p['topEnd']-v[:,2])/p['topWidth'])
    if np.max(abs(d[anchors]))>1e-10 or np.any(d[v[:,1]>=p['faceCutoffY']]):raise ValueError('Breast source moves anchors/face')
    mobile[anchors]=0;mobile[v[:,1]>=p['faceCutoffY']]=0;mobile[mobile<=p['minimum']]=0
    if not np.any(mobile):raise ValueError('Reconstructed mobility is empty')
    return mobile,{'basisResidual':stats(residual),'mask':stats(mask),'mobility':stats(mobile)}

def capacity_fade(vertices,faces,original_weights,width,decimals=5):
    W=np.asarray(original_weights,float)
    if not math.isfinite(width)or width<=0:raise ValueError('Invalid capacity guard width')
    if not np.isfinite(W).all()or W.min()<0 or (W>0).sum(axis=1).max()>4:raise ValueError('Invalid original influence budget')
    first,inverse,graph=surface.welded_graph(vertices,faces,int(decimals))
    distance=np.full(len(first),np.inf);queue=[]
    for i in set(inverse[np.flatnonzero((W>0).sum(axis=1)>=4)].tolist()):
        distance[i]=0.;heapq.heappush(queue,(0.,i))
    while queue:
        d,i=heapq.heappop(queue)
        if d!=distance[i]or d>=width:continue
        for j,length in graph[i]:
            proposed=d+length
            if proposed<distance[j]:distance[j]=proposed;heapq.heappush(queue,(proposed,j))
    return smooth(distance[inverse]/width)

def transfer_spine2(weights,desired,fade,spine,p1_left,p1_right,vertices):
    old=np.asarray(weights,float)
    if old.ndim!=2 or not np.isfinite(old).all()or old.min()<0 or np.any(old.sum(axis=1)<=0):raise ValueError('Invalid source weights')
    old=old/old.sum(axis=1)[:,None]
    desired=np.asarray(desired,float);fade=np.asarray(fade,float)
    if desired.shape!=(len(old),)or fade.shape!=desired.shape or not np.isfinite(desired).all()or np.min(desired)<0 or not np.isfinite(fade).all()or np.min(fade)<0 or np.max(fade)>1:
        raise ValueError('Invalid mobility field')
    if old[:,[p1_left,p1_right]].any():raise ValueError('Source is already weighted to P1')
    w=old[:,spine];q=w*(-np.expm1(-desired/np.maximum(w,1e-30)))*fade
    result=old.copy();result[:,spine]-=q
    side=np.where(np.asarray(vertices)[:,0]<0,p1_left,p1_right);result[np.arange(len(old)),side]+=q
    if result.min()<-1e-12 or abs(result.sum(axis=1)-1).max()>1e-10 or (result>0).sum(axis=1).max()>4:
        raise ValueError('Transfer exceeds normalized nonnegative four-weight budget')
    return result,q

def rotation(axis,degrees):
    a=math.radians(degrees);c,s=math.cos(a),math.sin(a);m=np.eye(4);i,j=[(1,2),(2,0),(0,1)][axis]
    m[i,i]=m[j,j]=c;m[j,i]=s;m[i,j]=-s
    return m

def pose_definitions(p1,degrees,seed):
    controls=[('NPC Spine [Spn0]',12),('NPC Spine1 [Spn1]',12),('NPC Spine2 [Spn2]',15),
      ('NPC L Clavicle [RClv]',15),('NPC R Clavicle [RClv]',15),('NPC Neck [Neck]',15),('NPC Head [Head]',15),
      ('NPC L UpperArm [RUar]',15),('NPC R UpperArm [RUar]',15),('NPC L UpperarmTwist1 [LUt1]',10),
      ('NPC R UpperarmTwist1 [RUt1]',10),('NPC L UpperarmTwist2 [LUt2]',10),('NPC R UpperarmTwist2 [RUt2]',10)]
    poses=[('rest',{},'ordinary')]
    for n,d in controls:
        for axis in range(3):
            for sign in [-1,1]:poses.append((f'{n}:{axis}:{sign*d}',{n:rotation(axis,sign*d)},'ordinary'))
    rng=np.random.default_rng(seed);held=[]
    for i in range(36):
        edits={n:rotation(int(rng.integers(3)),float(rng.uniform(-d,d)))for n,d in controls}
        held.append(edits);poses.append((f'heldout:{i}',edits,'heldout'))
    for mode in ['left','right','same','opposite']:
        for axis in range(3):
            for sign in [-1,1]:
                edits={}
                if mode!='right':edits[p1[0]]=rotation(axis,sign*degrees)
                if mode!='left':edits[p1[1]]=rotation(axis,sign*degrees*(-1 if mode=='opposite'else 1))
                poses.append((f'p1-{mode}:{axis}:{sign*degrees}',edits,'p1-'+mode))
    for i in range(12):
        edits=dict(held[i]);edits[p1[0]]=rotation(i%3,degrees);edits[p1[1]]=rotation((i+1)%3,-degrees)
        poses.append((f'combined-p1:{i}',edits,'combined-p1'))
    return poses

def posed_globals(rest,parent,names,poses):
    local={n:np.linalg.inv(rest[parent[n]])@rest[n]if parent[n]else rest[n]for n in rest};result=[]
    for label,edits,group in poses:
        posed={}
        def visit(n):
            if n not in posed:posed[n]=(visit(parent[n])if parent[n]else np.eye(4))@local[n]@edits.get(n,np.eye(4))
            return posed[n]
        result.append([visit(n)for n in names])
    return np.asarray(result)

def lbs(vertices,weights,matrices,normalize=False):
    """Column-vector LBS, with explicit raw/normalized weight convention."""
    vertices=np.asarray(vertices,float);W=np.asarray(weights,float)
    if normalize:W=W/np.maximum(W.sum(axis=1)[:,None],1e-30)
    h=np.c_[vertices,np.ones(len(vertices))];result=np.zeros((len(matrices),len(vertices),3))
    for b in range(W.shape[1]):
        if np.any(W[:,b]):result+=np.einsum('pjk,nk->pnj',matrices[:,b],h)[...,:3]*W[None,:,b,None]
    return result

def matrix(transform):
    m=np.eye(4);m[:3,:3]=np.asarray(transform.rotation)*float(transform.scale);m[:3,3]=list(transform.translation)
    return m

def load_pynifly(directory=None):
    import locate
    path=Path(directory or locate.local_config(__file__).get('pynifly',''))
    if not (path/'pyn/pynifly.py').is_file():raise ValueError('Configure PyNifly in build.local.json or --pynifly')
    sys.path.insert(0,str(path))
    from pyn import pynifly
    pynifly.NifFile.Load(str(path/'NiflyDLL.dll'))
    spec=importlib.util.spec_from_file_location('claw_rig_trip',path/'tri/tripfile.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return pynifly,module.TripFile,path

def read_weights(shape,names):
    result=np.zeros((len(shape.verts),len(names)));index={n:i for i,n in enumerate(names)}
    for n,pairs in shape.bone_weights.items():
        for i,w in pairs:result[i,index[n]]+=w
    if not np.isfinite(result).all()or result.min()<0 or np.any(result.sum(axis=1)<=0):raise ValueError('Invalid serialized skin weights')
    return result

def require_serialized_head_mobility(weights,names,vertices,p1_bones):
    """A successful bilateral rig must survive actual packed-weight readback.

    A small plan/readback error alone permits a mathematically nonzero field
    which half packing erases. Counts here use stored weights on the proper side.
    """
    weights=np.asarray(weights,float);vertices=surface.positions(vertices);result={}
    for side,bone in enumerate(p1_bones):
        if bone not in names:raise ValueError('Serialized head P1 is empty; no-op rig rejected: '+bone)
        column=weights[:,names.index(bone)]
        selected=(vertices[:,0]<0)if side==0 else(vertices[:,0]>0)
        actual=column[selected]
        count=int((actual>0).sum())
        if count==0:raise ValueError('Serialized head P1 is empty on one side; no-op rig rejected: '+bone)
        result[bone]={'storedMobileVertices':count,'storedMaxWeight':float(actual.max())}
    return result

def dense_morph(raw,name,key,count):
    result=np.zeros((count,3))
    for i,value in raw.get(name,{}).get(key,[]):result[i]=value
    if not np.isfinite(result).all():raise ValueError('Nonfinite TRI delta')
    return result

def _transform_buffer(api,value):
    t=api.TransformBuf();t.store(value[:3,3].tolist(),value[:3,:3].tolist(),[1.,1.,1.]);return t

def _write_rig(api,body,skeleton,p,planned,target):
    nif=api.NifFile(str(body));base=api.NifFile(str(body));skel=api.NifFile(str(skeleton))
    originals=set(base.nodes);rest={n:matrix(x.global_transform)for n,x in skel.nodes.items()};added=set()
    required=set()
    for n in p['p1Bones']:
        while n not in originals:required.add(n);n=skel.nodes[n].parent.name
    if required!=set(p['requiredNodes']):raise ValueError('Required XP32 ancestry differs from profile')
    def add(n):
        if n in originals or n in added:return
        parent=skel.nodes[n].parent.name;add(parent)
        parent_world=matrix(base.nodes[parent].global_transform)if parent in originals else rest[parent]
        nif.add_node(n,_transform_buffer(api,np.linalg.inv(parent_world)@rest[n]),parent=parent);added.add(n)
    for n in sorted(required):add(n)
    original_shapes={s.name:s for s in base.shapes}
    for shape in nif.shapes:
        if shape.name not in planned:continue
        entry=planned[shape.name];original=original_shapes[shape.name]
        oldbind={n:original.get_shape_skin_to_bone(n).copy()for n in original.bone_weights}
        added_bones=[]
        for n in p['p1Bones']:
            if np.any(entry['weights'][:,entry['names'].index(n)]>0):
                shape.add_bone(n,_transform_buffer(api,rest[n]),skel.nodes[n].parent.name);added_bones.append(n)
        for n,t in oldbind.items():shape.set_skin_to_bone_xform(n,t)
        # The complete global-to-skin frame cancels here; retain the exact old
        # Spine2 bind instead of introducing a new identity-rest convention.
        spine_bind=matrix(original.get_shape_skin_to_bone(p['spineBone']))
        for n in added_bones:
            shape.set_skin_to_bone_xform(n,_transform_buffer(api,np.linalg.inv(rest[n])@rest[p['spineBone']]@spine_bind))
        for j,n in enumerate(entry['names']):
            if n in oldbind or n in added_bones:
                shape.setShapeWeights(n,[(int(i),float(entry['weights'][i,j]))for i in np.flatnonzero(entry['weights'][:,j]>0)])
        shape.set_partitions(original.partitions,original.partition_tris)
    nif.filepath=str(target);nif.save()

def verify_candidate(api,body,target,skeleton,tri,raw,p,planned,anchors):
    baseline=api.NifFile(str(body));result=api.NifFile(str(target));skel=api.NifFile(str(skeleton));tol=p['verification']
    if len(result.nodes)!=p['inputs']['outputNodeCount']or set(result.nodes)-set(baseline.nodes)!=set(p['requiredNodes']):raise ValueError('Unexpected output node graph')
    node_error=max(float(abs(matrix(result.nodes[n].global_transform)-matrix(x.global_transform)).max())for n,x in baseline.nodes.items())
    if node_error!=0:raise ValueError('Original node globals changed')
    node_audit={}
    for n in p['requiredNodes']:
        node=result.nodes[n];expected=skel.nodes[n];error=float(abs(matrix(node.global_transform)-matrix(expected.global_transform)).max())
        if node.parent.name!=expected.parent.name or error>tol['nodeMatrixTolerance']:raise ValueError('XP32 node matrix/ancestry mismatch: '+n)
        node_audit[n]={'parent':node.parent.name,'globalMatrixError':error,'localMatrix':matrix(node.transform).tolist(),'donorLocalMatrix':matrix(expected.transform).tolist()}
    names=sorted({n for nf in [baseline,result]for s in nf.shapes for n in s.bone_weights}|set(p['p1Bones']))
    if not set(names)<=set(skel.nodes):raise ValueError('Weighted bone absent from pinned XP32')
    index={n:i for i,n in enumerate(names)};rest={n:matrix(x.global_transform)for n,x in skel.nodes.items()};parent={n:x.parent.name if x.parent else None for n,x in skel.nodes.items()}
    poses=pose_definitions(p['p1Bones'],tol['p1Degrees'],int(tol['seed']));globals_=posed_globals(rest,parent,names,poses)
    groups={group:[i for i,x in enumerate(poses)if x[2]==group]for group in sorted({x[2]for x in poses})}
    pure=[i for i,x in enumerate(poses)if x[2].startswith('p1-')]
    shapes={s.name:s for s in baseline.shapes};checks={};aggregate={}
    for s in result.shapes:
        b=shapes[s.name]
        if s.verts!=b.verts or s.tris!=b.tris or s.uvs!=b.uvs:raise ValueError('Geometry/topology/UV changed: '+s.name)
        A=read_weights(b,names);B=read_weights(s,names)
        if (B>0).sum(axis=1).max()>4 or abs(B.sum(axis=1)-1).max()>tol['packedWeightSumTolerance']:raise ValueError('Invalid packed weight budget/sum: '+s.name)
        old_bind_error=max(float(abs(matrix(s.get_shape_skin_to_bone(n))-matrix(b.get_shape_skin_to_bone(n))).max())for n in b.bone_weights)
        if old_bind_error!=0 or np.max(abs(matrix(s.global_to_skin)-matrix(b.global_to_skin)))!=0:raise ValueError('Original skin bind/frame changed')
        nonspine=[j for j,n in enumerate(names)if n!=p['spineBone']and n not in p['p1Bones']]
        if np.any((A[:,nonspine]>0)&(B[:,nonspine]<=0)):raise ValueError('Serialized export pruned an original non-Spine2 influence')
        original_four=(A>0).sum(axis=1)==4
        if B[original_four][:,[index[n]for n in p['p1Bones']]].any():raise ValueError('Serialized P1 violates the original four-weight capacity guard')
        plan_error=0.
        if s.name in planned:
            entry=planned[s.name];expected=entry['weights'][:,[entry['names'].index(n)for n in names]]
            plan_error=float(abs(B/B.sum(axis=1)[:,None]-expected).max())
            if plan_error>.001:raise ValueError('Serialized weights do not reproduce the numeric plan')
        elif np.any(A!=B):raise ValueError('Weights changed on an unplanned shape')
        p1_bind_error={}
        for n in p['p1Bones']:
            if not np.any(B[:,index[n]]):continue
            actual=rest[n]@matrix(s.get_shape_skin_to_bone(n))@matrix(s.global_to_skin)
            expected=rest[p['spineBone']]@matrix(b.get_shape_skin_to_bone(p['spineBone']))@matrix(b.global_to_skin)
            error=float(abs(actual-expected).max());p1_bind_error[n]=error
            if error>tol['nodeMatrixTolerance']:raise ValueError('Serialized P1/Spine2 bind convention changed')
        union=np.flatnonzero(np.any(A!=B,axis=1))
        r={'verticesEqual':True,'trianglesEqual':True,'uvEqual':True,'changedVertexUnion':union.tolist(),
           'maxInfluences':int((B>0).sum(axis=1).max()),'packedWeightSumError':float(abs(B.sum(axis=1)-1).max()),'oldBindMaxAbsChange':old_bind_error,
           'p1RestProductError':p1_bind_error,'originalNonSpine2InfluencesPruned':0,'poses':{}}
        r['originalFourInfluenceP1Zero']=True;r['serializedPlanNormalizedWeightMaxError']=plan_error
        if s.name=='head':
            r['serializedBilateralHeadMobility']=require_serialized_head_mobility(B,names,s.verts,p['p1Bones'])
            if np.any(B[anchors]!=A[anchors]):raise ValueError('Anchor weights changed')
            v=np.asarray(s.verts);p1=[index[n]for n in p['p1Bones']]
            if B[anchors][:,p1].any()or B[v[:,1]>=p['mobility']['faceCutoffY']][:,p1].any():raise ValueError('P1 moves anchor/face')
            r['fixedAnchorCount']=len(anchors);r['anchorWeightsEqual']=True;r['anchorAndFaceP1Zero']=True
        if not len(union):checks[s.name]=r;continue
        bind={}
        for label,shape in [('baseline',b),('candidate',s)]:
            value=np.zeros((len(names),4,4))
            for n in shape.bone_weights:value[index[n]]=matrix(shape.get_shape_skin_to_bone(n))@matrix(shape.global_to_skin)
            bind[label]=np.einsum('pbjk,bkl->pbjl',globals_,value)
        # Full union of changed packed influences, including exporter-only tiny
        # changes outside the desired mask. Never evaluate only desired P1 owners.
        delta=dense_morph(raw,s.name,p['publicMorph'],len(s.verts))[union];vertices=np.asarray(s.verts)[union]
        for normalize in [False,True]:
            mode='normalized'if normalize else'rawPacked';errors=[];motion=[]
            for coefficient in [0.,.5,1.]:
                points=vertices+coefficient*delta
                old=lbs(points,A[union],bind['baseline'],normalize);new=lbs(points,B[union],bind['candidate'],normalize)
                errors.append(np.linalg.norm(new-old,axis=-1));motion.append(np.linalg.norm(new[pure]-new[:1],axis=-1))
            errors=np.asarray(errors);r['poses'][mode]={g:stats(errors[:,ids])for g,ids in groups.items()}
            r['poses'][mode]['pureP1MotionFromOwnRest']=stats(motion)
            aggregate.setdefault(mode,{}).setdefault('pureP1MotionFromOwnRest',[]).append(np.asarray(motion).ravel())
            for group,ids in groups.items():aggregate.setdefault(mode,{}).setdefault(group,[]).append(errors[:,ids].ravel())
            limit=tol['normalizedOrdinaryMaxError']if normalize else tol['rawOrdinaryMaxError']
            if max(r['poses'][mode][g]['max']for g in ['ordinary','heldout'])>limit:raise ValueError('Ordinary-pose error exceeds declared '+mode+' tolerance')
        checks[s.name]=r
    summary={mode:{group:stats(np.concatenate(values))for group,values in table.items()}for mode,table in aggregate.items()}
    if sha256(target.with_suffix('.tri'))!=sha256(tri):raise ValueError('TRI changed')
    return {'sourceNodeCount':len(baseline.nodes),'outputNodeCount':len(result.nodes),'originalNodeGlobalError':node_error,
            'nodes':node_audit,'shapes':checks,'aggregatePoses':summary,'poseDefinitions':[{'name':n,'group':g,'localRotations':{b:x.tolist()for b,x in edits.items()}}for n,edits,g in poses],
            'poseConvention':'Actual serialized binds and weights; rawPacked does not normalize. normalized is a separate mathematical metric, not a shader claim. States 0/0.5/1 moderate BreastSize. All packed-weight changed vertices included.'}

def build_candidate(body,tri,skeleton,profile_file,output,pynifly_directory=None):
    body,tri,skeleton,profile_file=[Path(p).resolve(strict=True)for p in [body,tri,skeleton,profile_file]]
    inputs_before={str(f):sha256(f)for f in [body,tri,skeleton,profile_file]}
    source_before={str(f.relative_to(ROOT)):sha256(f)for f in [Path(__file__),ROOT / 'src/main/python/build-tools/rig-breast.py']}
    p=load_profile(profile_file)
    for filename,key in [(body,'bodyNifSha256'),(tri,'triSha256'),(skeleton,'skeletonSha256')]:
        if sha256(filename)!=p['inputs'][key]:raise ValueError('Pinned input mismatch: '+key)
    import locate
    config=locate.local_config(__file__);live=[config['mods']]if config.get('mods')else[]
    out=safe_output(output,[body,tri,skeleton,profile_file],live_roots=live)
    api,TripFile,dependency=load_pynifly(pynifly_directory)
    nif=api.NifFile(str(body));skel=api.NifFile(str(skeleton));shapes={s.name:s for s in nif.shapes}
    if len(nif.nodes)!=p['inputs']['sourceNodeCount']:raise ValueError('Expected raw 85-node source')
    raw=TripFile.from_filepath(str(tri)).shapes;public={n for morphs in raw.values()for n in morphs}
    if len(public)!=p['inputs']['publicMorphCount']or not all(n.startswith('CLAW')for n in public):raise ValueError('TRI public morph contract mismatch')
    v={n:np.asarray(s.verts)for n,s in shapes.items()};t={n:np.asarray(s.tris)for n,s in shapes.items()}
    collar=surface.Collar(v['body'],t['body'],v['head'],t['head'],p['collar'],SurfaceProjector(v['body'],t['body']))
    if len(collar.anchors)!=p['inputs']['anchorCount']:raise ValueError('Expected exactly 55 anchors')
    head=dense_morph(raw,'head',p['publicMorph'],len(v['head']))
    if np.any(dense_morph(raw,'body',p['publicMorph'],len(v['body']))):raise ValueError('Expected shape-only BreastSize with fixed body')
    mobile,reconstruction=reconstruct_mobility(v['head'],head,collar.anchors,p)
    mobility={'body':np.zeros(len(v['body'])),'head':mobile}
    skin=np.r_[v['body'],v['head']];faces=np.r_[t['body'],t['head']+len(v['body'])]
    scalar=np.column_stack([np.r_[mobility['body'],mobile],np.zeros(len(skin)),np.zeros(len(skin))]);project=SurfaceProjector(skin,faces)
    layer_info={}
    for rule in p['layers']:
        name=rule['shape'];layer=surface.Layer(v[name],t[name],skin,faces,rule,project)
        mobility[name]=layer.reconcile(np.zeros_like(v[name]),scalar)[:,0]
        layer_info[name]={'groups':len(layer.groups),'fullGroups':int((layer.weights>=1-1e-6).sum()),'fadeGroups':int(((layer.weights>0)&(layer.weights<1-1e-6)).sum())}
    names=sorted({n for s in nif.shapes for n in s.bone_weights}|set(p['p1Bones']));index={n:i for i,n in enumerate(names)};planned={};coverage={}
    for name,desired in mobility.items():
        if name=='body':continue
        original=read_weights(shapes[name],names);fade=capacity_fade(v[name],t[name],original,p['mobility']['capacityGuardWidth'],p['mobility']['weldDecimals'])
        weights,q=transfer_spine2(original,desired,fade,index[p['spineBone']],*[index[n]for n in p['p1Bones']],v[name])
        planned[name]={'weights':weights,'names':names}
        coverage[name]={'desiredMobileVertices':int((desired>p['mobility']['minimum']).sum()),'guardedMobileVertices':int((q>p['mobility']['minimum']).sum()),
            'p1Weights':stats(q),'desiredMobility':stats(desired),'p1Sum':float(q.sum()),'layerBinding':layer_info.get(name)}
    out.mkdir(parents=True,exist_ok=False)
    (out/'status.json').write_text(json.dumps({'status':'building-unverified-do-not-install'}))
    try:
        target=(out/p['outputRelativeNif']).resolve()
        if out not in target.parents:raise ValueError('NIF output escapes staging directory')
        target.parent.mkdir(parents=True,exist_ok=True)
        _write_rig(api,body,skeleton,p,planned,target);shutil.copyfile(tri,target.with_suffix('.tri'))
        verification=verify_candidate(api,body,target,skeleton,tri,raw,p,planned,collar.anchors)
        if any(sha256(f)!=value for f,value in inputs_before.items()):raise ValueError('Input changed during build')
        if any(sha256(ROOT/f)!=value for f,value in source_before.items()):raise ValueError('Builder source changed during build')
        report={'status':'verified-offline-source-candidate-runtime-and-driver-ownership-pending','profile':p['name'],
            'reconstruction':'New scalar mask reconstructed from moderate TRI; not byte-exact local prototype A reproduction.',
            'inputs':inputs_before,'sourceSha256':source_before,
            'dependencies':{'python':platform.python_version(),'numpy':np.__version__,'pyniflyDirectory':str(dependency),
                'sha256':{str(f.relative_to(dependency)):sha256(f)for f in [dependency/'pyn/pynifly.py',dependency/'NiflyDLL.dll']}},
            'outputSha256':{str(f.relative_to(out)):sha256(f)for f in [target,target.with_suffix('.tri')]},
            'reconstructionMetrics':reconstruction,'coverage':coverage,'verification':verification,
            'limits':['Off by default; no install/runtime controller.',
              'Existing human 3BA/CBPC/SMP may already drive P1; effective ownership audit required before game.',
              'Independent layer guards can cause root drift; no fur/skin common-field acceptance.',
              'Preserves existing ordinary joint drift; no seam, animation, renderer, physics or aesthetic acceptance.',
              'Raw and normalized LBS are separate metrics; shader normalization is unknown.',
              'Moderate BreastSize states only; other combined morph extremes excluded.']}
        filename=out/'report.json';filename.write_text(json.dumps(report,indent=2),encoding='utf-8')
        (out/'status.json').write_text(json.dumps({'status':report['status'],'report':'report.json'}));return filename
    except Exception as exc:
        (out/'status.json').write_text(json.dumps({'status':'FAILED-unverified-do-not-install','error':str(exc)}));raise
