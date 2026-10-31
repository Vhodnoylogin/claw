"""Compose one pinned skin/fur carrier, public MorphBench bounds and exact split.

MorphBench's public open/bounds/attach/bounds_write interface owns sphere fitting
and writing. Our only additional analysis is actual-bind LBS and a conservative
per-vertex coordinate-box union of the declared additive morph/pose envelope.
"""
from pathlib import Path
import itertools
import json
import shutil
import sys
import numpy as np
import breast_rig as rig
import head_split as split
import vr_head

ROOT=Path(__file__).resolve().parents[4]


def sphere_only(before,after):
    """Independent reconstruction: no byte outside actual shape spheres may differ."""
    a=split.Nif(before);b=split.Nif(after)
    if a.prefix!=b.prefix or a.kinds!=b.kinds or a.strings!=b.strings or len(a.blocks)!=len(b.blocks):raise ValueError('Bounds changed NIF container')
    reconstructed=split.Nif(before);fields=[]
    for i,(old,new) in enumerate(zip(a.blocks,b.blocks)):
        if a.kind(i)=='BSTriShape':
            extra=int.from_bytes(old[4:8],'little');offset=72+4*extra
            if old[:offset]!=new[:offset] or old[offset+16:]!=new[offset+16:]:raise ValueError('Bounds changed protected shape bytes')
            value=bytearray(old);value[offset:offset+16]=new[offset:offset+16];reconstructed.blocks[i]=bytes(value);fields.append(i)
        elif old!=new:raise ValueError('Bounds changed a nonshape block')
    if reconstructed.bytes()!=after:raise ValueError('Bounds byte reconstruction failed')
    return {'only16ByteSphereFieldsMayChange':True,'shapeBlocks':fields,
            'changedByteCount':sum(x!=y for x,y in zip(before,after))}


def pose_bank(skeleton):
    rest={n:rig.matrix(x.global_transform) for n,x in skeleton.nodes.items()}
    parents={n:x.parent.name if x.parent else None for n,x in skeleton.nodes.items()}
    definitions=rig.pose_definitions(['NPC L Breast P1','NPC R Breast P1'],3.,20261025)
    ordinary=rig.posed_globals(rest,parents,list(rest),definitions)
    globals_=[{n:ordinary[i,j] for j,n in enumerate(rest)} for i in range(len(definitions))]
    extra=vr_head.pose_bank(rest,parents)[1:]
    for label,edits,kind in extra:
        globals_.append(vr_head.impose(rest,parents,edits));definitions.append((label,edits,kind))
    return rest,parents,definitions,globals_


def posed_boxes(shape,raw,globals_,endpoint=None):
    """All additive0..1 morphs at every declared pose, raw and normalized LBS.

    For each fixed pose LBS is affine in the morph coefficients. Summing each
    transformed offset's coordinate minima/maxima therefore encloses all corners,
    even for vertices above the exhaustive MorphBench corner cap. Taking a union
    across poses/modes remains conservative; no continuous animation is claimed.
    """
    vertices=np.asarray(shape.verts,float);names=list(shape.bone_weights);weights=rig.read_weights(shape,names)
    binds=np.asarray([rig.matrix(shape.get_shape_skin_to_bone(n))@rig.matrix(shape.global_to_skin) for n in names])
    morphs={name:rig.dense_morph(raw,shape.name,name,len(vertices)) for name in raw.get(shape.name,{})}
    if endpoint is not None:morphs['__CLAWBaseWeightEndpoint']=np.asarray(endpoint,float)-vertices
    delta=np.stack(list(morphs.values()),axis=1) if morphs else np.zeros((len(vertices),0,3))
    lower=np.full_like(vertices,np.inf);upper=np.full_like(vertices,-np.inf);rest_error={}
    for normalize in (False,True):
        W=weights/weights.sum(1)[:,None] if normalize else weights
        for i,pose in enumerate(globals_):
            products=np.asarray([pose[n] for n in names])@binds
            matrix=np.einsum('nb,bij->nij',W,products)
            base=np.einsum('nij,nj->ni',matrix[:,:3,:3],vertices)+matrix[:,:3,3]
            if i==0:rest_error['normalized' if normalize else 'rawPacked']=float(np.linalg.norm(base-vertices,axis=1).max())
            if len(morphs):
                moved=np.einsum('nij,nmj->nmi',matrix[:,:3,:3],delta)
                lo=base+np.minimum(moved,0).sum(1);hi=base+np.maximum(moved,0).sum(1)
            else:lo=hi=base
            lower=np.minimum(lower,lo);upper=np.maximum(upper,hi)
    return lower,upper,{'publicMorphs':list(morphs),'restLbsDifferenceFromStoredVertices':rest_error}


def bound_carrier(api,Trip,source,endpoint,tri,skeleton,out,mb_directory,profile):
    """Use public MorphBench for additive bounds, then a conservative posed hull."""
    sys.path.insert(0,str(mb_directory))
    from morphbench.api import MorphBench
    from morphbench.config import Config
    from morphbench.model import Shape,BodyModel
    from morphbench.morphs import MorphSet,Morph
    from morphbench.bounds import Sphere
    from scipy.spatial import ConvexHull
    out.mkdir();cfg=Config(out/'morphbench.json');cfg.set('language','en');cfg.set('sliderRange',[0.,1.])
    cfg.set('boundsCornerCap',12);cfg.set('boundsMargin',1.01);cfg.set('boundsTolerance',0.)
    bench=MorphBench(cfg);bench.open(source,tri=tri,skeleton='')
    before=bench.bounds();native=api.NifFile(str(source));end={s.name:s for s in api.NifFile(str(endpoint)).shapes}
    analysis={};morphs={};public=bench.morphs()
    for shape in native.shapes:
        high=end[shape.name]
        if shape.tris!=high.tris or shape.uvs!=high.uvs or shape.bone_weights!=high.bone_weights:raise ValueError('Weight endpoint topology/UV/weights differ')
        sh=Shape(shape.name,np.asarray(shape.verts,np.float32),np.asarray(shape.tris,np.int32),np.asarray(shape.normals,np.float32),np.asarray(shape.uvs,np.float32),{})
        sh.bound=Sphere(list(shape.properties.boundingSphereCenter),float(shape.properties.boundingSphereRadius));sh.block=shape.id;analysis[shape.name]=sh
        values={}
        for name in public:
            field=bench.morph_deltas(shape.name,name)
            if field is not None:values[name]=Morph(name,shape.name,field['indices'],field['offsets'])
        delta=np.asarray(high.verts,np.float32)-np.asarray(shape.verts,np.float32);ids=np.flatnonzero(np.any(delta!=0,axis=1))
        values['__CLAWBaseWeightEndpoint']=Morph('__CLAWBaseWeightEndpoint',shape.name,ids,delta[ids]);morphs[shape.name]=values
    bench.attach(BodyModel(source,analysis),MorphSet(tri,'TRIP',morphs))
    static=out/'additive.nif';receipt=bench.bounds_write(static,margin=1.01)
    static_audit=sphere_only(source.read_bytes(),static.read_bytes());bench.open(static,tri=tri,skeleton='');static_rows=bench.bounds()
    if not all(x['ok'] for x in static_rows):raise ValueError('Public additive bounds readback failed')
    nif=api.NifFile(str(static));raw=Trip.from_filepath(str(tri)).shapes;skel=api.NifFile(str(skeleton))
    _,_,definitions,globals_=pose_bank(skel);analysis_shapes={};boxes={};pose_rows={}
    for shape in nif.shapes:
        lower,upper,detail=posed_boxes(shape,raw,globals_,end[shape.name].verts);boxes[shape.name]=(lower,upper)
        # A convex hull of all per-vertex box corners covers every declared pose
        # and additive coefficient. Hull reduction changes no enclosing extent.
        corners=np.concatenate([np.where(np.asarray(bits)[None,:],upper,lower) for bits in itertools.product((0,1),repeat=3)])
        corners=np.unique(corners,axis=0)
        hull=ConvexHull(corners);cloud=corners[hull.vertices].astype(np.float32)
        sh=Shape(shape.name,cloud,np.zeros((0,3),np.int32),None,None,{})
        sh.bound=Sphere(list(shape.properties.boundingSphereCenter),float(shape.properties.boundingSphereRadius));sh.block=shape.id
        analysis_shapes[shape.name]=sh;pose_rows[shape.name]={**detail,'cornerPoints':len(corners),'hullPoints':len(cloud)}
        np.savez_compressed(out/(shape.name+'-pose-boxes.npz'),lower=lower,upper=upper)
        print('POSE_BOUNDS|'+shape.name+'|'+str(len(cloud))+' hull vertices',flush=True)
    # Public attach is explicitly provided for caller-built analysis models.
    # Only the original NIF sphere blocks are written; the synthetic hull mesh is
    # never serialized or substituted for the actual carrier geometry.
    posed=MorphBench(cfg);posed.attach(BodyModel(static,analysis_shapes),MorphSet(tri,'TRIP',{}))
    pose_before=posed.bounds();bounded=out/'additive-and-poses.nif';pose_receipt=posed.bounds_write(bounded,margin=1.01)
    pose_audit=sphere_only(static.read_bytes(),bounded.read_bytes());actual=api.NifFile(str(bounded))
    for shape in actual.shapes:
        centre=np.asarray(shape.properties.boundingSphereCenter,float);radius=float(shape.properties.boundingSphereRadius)
        lo,hi=boxes[shape.name];reach=float(np.linalg.norm(np.maximum(abs(lo-centre),abs(hi-centre)),axis=1).max())
        if reach>radius+1e-4:raise ValueError('Independent posed additive box escapes serialized bound: '+shape.name)
        pose_rows[shape.name].update(serializedCentre=centre.tolist(),serializedRadius=radius,independentBoxReach=reach,
                                     clearance=radius-reach,allDeclaredPoseMorphBoxesCovered=True)
    bench.open(bounded,tri=tri,skeleton='');after=bench.bounds()
    if not all(x['ok'] for x in after):raise ValueError('Final public additive bound check failed')
    # The same convex pose/weight envelope is written through the facade to the
    # actual high endpoint. Geometry, TRI and skin bytes remain independent.
    high_shapes={}
    for shape in api.NifFile(str(endpoint)).shapes:
        sh=Shape(shape.name,analysis_shapes[shape.name].verts,np.zeros((0,3),np.int32),None,None,{})
        sh.bound=Sphere(list(shape.properties.boundingSphereCenter),float(shape.properties.boundingSphereRadius));sh.block=shape.id;high_shapes[shape.name]=sh
    high_bench=MorphBench(cfg);high_bench.attach(BodyModel(endpoint,high_shapes),MorphSet(tri,'TRIP',{}))
    high_bounded=out/'additive-and-poses_1.nif';high_receipt=high_bench.bounds_write(high_bounded,margin=1.01)
    high_audit=sphere_only(endpoint.read_bytes(),high_bounded.read_bytes());bench.open(high_bounded,tri=tri,skeleton='');high_rows=bench.bounds()
    if not all(x['ok'] for x in high_rows):raise ValueError('High endpoint public additive bounds failed')
    for shape in api.NifFile(str(high_bounded)).shapes:
        centre=np.asarray(shape.properties.boundingSphereCenter,float);radius=float(shape.properties.boundingSphereRadius);lo,hi=boxes[shape.name]
        if float(np.linalg.norm(np.maximum(abs(lo-centre),abs(hi-centre)),axis=1).max())>radius+1e-4:raise ValueError('High endpoint misses combined pose/weight envelope')
    report={'staticBefore':before,'staticReceipt':receipt,'staticReadback':static_rows,'staticByteAudit':static_audit,
            'poseBefore':pose_before,'poseReceipt':pose_receipt,'poseByteAudit':pose_audit,'poseReadback':pose_rows,
            'publicStaticReadbackAfterPoseWrite':after,'highEndpointReceipt':high_receipt,'highEndpointByteAudit':high_audit,'highEndpointPublicReadback':high_rows,
            'poses':[{'name':n,'group':g,'localEdits':{k:m.tolist() for k,m in e.items()}} for n,e,g in definitions],
            'scope':'All public morphs independently additive0..1 plus independent neutral weight0..1; 151 ordinary/held-out/P1 poses plus9 declared Head examples; raw and normalized LBS. Conservative per-vertex coordinate boxes then exact convex hull. Finite declared poses only; no continuous animation, tracked camera, engine culling or physics coverage claim.'}
    (out/'bounds-report.json').write_text(json.dumps(report,indent=2));return bounded,high_bounded,report


def build(female,female_tri,male,male_tri,skeleton,profile_file,output,mb_directory,pynifly=None):
    inputs=[Path(x).resolve(strict=True) for x in (female,female_tri,male,male_tri,skeleton,profile_file)]
    female,female_tri,male,male_tri,skeleton,profile_file=inputs;mb_directory=Path(mb_directory).resolve(strict=True)
    profile=json.loads(profile_file.read_text());template=json.loads((ROOT / 'src/main/resources/recipes/composed-vr.json').read_text())
    if profile!=template or profile['threshold']!=.5:raise ValueError('Unreviewed composition profile')
    female_high=female.with_name(female.name.replace('_0.nif','_1.nif'));male_high=male.with_name(male.name.replace('_0.nif','_1.nif'));inputs += [female_high,male_high]
    for path,key in ((female,'femaleNifSha256'),(female_high,'femaleHighNifSha256'),(female_tri,'femaleTriSha256'),(male,'maleNifSha256'),(male_high,'maleHighNifSha256'),(male_tri,'maleTriSha256'),(skeleton,'skeletonSha256')):
        if rig.sha256(path)!=profile['inputs'][key]:raise ValueError('Composed input pin changed: '+key)
    out=rig.safe_output(output,inputs);api,Trip,dependency=rig.load_pynifly(pynifly)
    files=inputs+[Path(__file__),ROOT / 'src/main/python/build-tools/compose-vr-body.py',ROOT / 'src/main/python/build-tools/head_split.py',ROOT / 'src/main/python/build-tools/breast_rig.py',ROOT / 'src/main/python/build-tools/vr_head.py']
    files += list((mb_directory/'morphbench').glob('*.py'))+[*sorted((dependency/'pyn').glob('*.py')),*sorted((dependency/'tri').glob('*.py')),dependency/'NiflyDLL.dll']
    frozen={str(p):rig.sha256(p) for p in files};skel=api.NifFile(str(skeleton));parents={n:x.parent.name if x.parent else None for n,x in skel.nodes.items()}
    head_names=vr_head.descendants(parents,vr_head.HEAD);out.mkdir()
    report={'status':'building-unverified-do-not-install','inputsAndExecutedSha256':frozen,'profile':profile,'bodies':{}}
    (out/'OFFLINE_CANDIDATE.txt').write_text('Composed anatomical body resources. No live install or skeleton replacement. Runtime routing, selective head visibility, camera, animation, contact-driver and appearance acceptance remain pending.\n')
    try:
        for sex,source,endpoint,tri in [('female',female,female_high,female_tri),('male',male,male_high,male_tri)]:
            bounded,bounded_high,bounds_report=bound_carrier(api,Trip,source,endpoint,tri,skeleton,out/(sex+'-bounds'),mb_directory,profile)
            nif=api.NifFile(str(bounded));raw=Trip.from_filepath(str(tri)).shapes
            planned,comparisons=split.plan(nif,raw,head_names,profile)
            data,audit=split.split_nif(bounded.read_bytes(),planned,{})
            morph=split.split_trip(tri.read_bytes(),planned);folder=out/'meshes/actors/werewolfbeast/character assets';folder.mkdir(parents=True,exist_ok=True)
            target=folder/(sex+'bodywerewolf_0.nif');target.write_bytes(data);target_tri=folder/(sex+'bodywerewolf.tri');target_tri.write_bytes(morph)
            readback=split.verify(api,Trip,bounded,target,tri,target_tri,planned,skel)
            high_data,high_audit=split.split_nif(bounded_high.read_bytes(),planned,{})
            target_high=folder/(sex+'bodywerewolf_1.nif');target_high.write_bytes(high_data)
            high_readback=split.verify(api,Trip,bounded_high,target_high,tri,target_tri,planned,skel)
            if data==high_data:raise ValueError('Composed endpoints are not distinct')
            mapping={n:{'action':p['action'],'sourceBlock':p['sourceBlock'],'wholeFurCards':p['cards'],**{k:v.tolist() for k,v in p['mapping'].items()}} for n,p in planned.items()}
            (out/(sex+'-index-map.json')).write_text(json.dumps(mapping,separators=(',',':')))
            report['bodies'][sex]={'nif':str(target),'tri':str(target_tri),'nifSha256':rig.sha256(target),'triSha256':rig.sha256(target_tri),
                'highNif':str(target_high),'highNifSha256':rig.sha256(target_high),'boundedSource':str(bounded),'boundedSourceSha256':rig.sha256(bounded),
                'boundedHighSource':str(bounded_high),'boundedHighSourceSha256':rig.sha256(bounded_high),'boundsReport':str(out/(sex+'-bounds/bounds-report.json')),
                'options':comparisons,'binaryAudit':audit,'readback':readback,'highBinaryAudit':high_audit,'highReadback':high_readback,
                'headVisibilityShapes':[n if p['action']=='head' else n+split.SUFFIX for n,p in planned.items() if p['action']!='torso'],
                'contactSkinShapeSelector':['body','head','head_CLAWHead']}
        if any(rig.sha256(p)!=h for p,h in frozen.items()):raise ValueError('Composition input/source/dependency changed')
        report['status']='verified-offline-composed-body-resources-runtime-and-appearance-pending'
    except Exception:
        report['status']='FAILED-unverified-do-not-install';raise
    finally:(out/'composed-vr-report.json').write_text(json.dumps(report,indent=2))
    return out/'composed-vr-report.json'
