"""Enclose only the three new anatomy bone spheres, with existing VR bound math.

Serialized TRI fields are independent additive coefficients in [0,1]. Motion is
the declared nominal joint-limit cube; no provider enforcement is asserted.
"""
import math
import struct
import numpy as np
import neck_bounds as bounds
import morph_quality


def records(container, shape, reader):
    raw=container.blocks[shape.id];extra,=struct.unpack_from('<I',raw,4)
    skin,=struct.unpack_from('<I',raw,88+4*extra);data,=struct.unpack_from('<I',container.blocks[skin])
    if container.kind(skin)!='NiSkinInstance' or container.kind(data)!='NiSkinData':
        raise ValueError('Expected declared neutral NiSkinInstance/NiSkinData')
    r=reader(container.blocks[data]);r.take(52);count,present=r.unpack('<IB')
    if count!=len(shape.bone_names) or present!=1:raise ValueError('Invalid anatomy skin palette')
    result={}
    for name in shape.bone_names:
        offset=r.pos+52;r.take(52);sphere=np.asarray(r.unpack('<4f'))
        count,=r.unpack('<H');r.take(count*6)
        if not np.isfinite(sphere).all() or sphere[3]<=0:raise ValueError('Invalid new bone sphere')
        result[name]=(data,offset,sphere)
    r.done();return result


def motion_padding(lower_world,upper_world,bone,rest,parents,p):
    """Triangle bound for leaf-to-anchor composition of nominal rigid joints.

    Each Euler axis is bounded by a; rotation distance <=2*sin(3a/2)*radius.
    Axis translations have norm <=sqrt(3)*l. Prior child displacement expands
    the next parent lever arm; common rigid anchor motion cancels.
    """
    theta=min(math.pi,3*p['motion']['angularLimitRadians'])
    factor=2*math.sin(theta/2);translation=math.sqrt(3)*p['motion']['linearLimit']
    displacement=0.;chain=[];name=bone
    while name in p['drivers']:
        lever=bounds.reach(lower_world,upper_world,rest[name][:3,3])
        displacement+=factor*(lever+displacement)+translation
        chain.append(name);name=parents[name]
    return displacement,chain


def expand(path,tri,skeleton,p,rig,api,Trip,NifPatch,fsmp):
    import head_split
    before=path.read_bytes();container=fsmp.Nif(before);table=NifPatch(path)
    nif=api.NifFile(str(path));skel=api.NifFile(str(skeleton))
    shape=next(s for s in nif.shapes if s.name==p['shape'])
    public=Trip.from_filepath(str(tri)).shapes
    fields,decoder=morph_quality.decode_fields(tri.read_bytes(),public,{s.name:len(s.verts) for s in nif.shapes})
    all_fields=[v for (name,_),v in fields.items() if name==p['shape']]
    rest={n:rig.matrix(x.global_transform) for n,x in skel.nodes.items()}
    parents={n:x.parent.name if x.parent else None for n,x in skel.nodes.items()}
    ledger=[];proof={};boxes={}
    for name,(block,relative,old) in records(container,shape,head_split.Reader).items():
        if name not in p['drivers']:continue
        ids=np.asarray([i for i,w in shape.bone_weights[name] if w>0],int)
        bind=rig.matrix(shape.get_shape_skin_to_bone(name));v=np.asarray(shape.verts)[ids]
        local=v@bind[:3,:3].T+bind[:3,3]
        rest_reach=float(np.linalg.norm(local-old[:3],axis=1).max())
        if abs(rest_reach-old[3])>1e-4:raise ValueError('Native rest sphere is not in the serialized B/raw-vertex frame')
        complete=[f[ids] for f in all_fields]
        lower,upper=bounds.local_boxes(v,v,complete,bind)
        world_lower,world_upper=bounds.local_boxes(v,v,complete,rest[name]@bind)
        padding,chain=motion_padding(world_lower,world_upper,name,rest,parents,p)
        # Convert a world displacement to this frozen rest B frame conservatively.
        padding*=float(np.linalg.norm(np.linalg.inv(rest[name])[:3,:3],ord=2))
        required=bounds.reach(lower,upper,old[:3])+padding
        radius=bounds.outward_float32(max(float(old[3]),required*bounds.MARGIN+bounds.ABSOLUTE_MARGIN))
        new=[*old[:3].tolist(),radius]
        ledger.append({'offset':table.offsets[block]+relative,'oldSphere':old.tolist(),'newSphere':new,'bone':name})
        boxes[name]=(lower,upper,padding)
        proof[name]={'before':old.tolist(),'after':new,'positiveSupport':len(ids),'completeAnatomyFields':len(complete),
            'restReach':rest_reach,'morphCubeReach':bounds.reach(lower,upper,old[:3]),'nominalMotionPadding':padding,
            'nominalDynamicChainLeafToAnchor':chain,'requiredReachWithMotion':required,'clearance':radius-required}
    if set(proof)!=set(p['drivers']):raise ValueError('Missing new bone sphere coverage')
    after=bounds.patch_spheres(before,ledger)
    if len(after)!=len(before):raise ValueError('Sphere patch changed file layout')
    allowed={row['offset']+j for row in ledger for j in range(12,16)}
    if any(a!=b for i,(a,b) in enumerate(zip(before,after)) if i not in allowed):
        raise ValueError('Bytes changed outside three new radius fields')
    path.write_bytes(after)
    actual=api.NifFile(str(path));stored=records(fsmp.Nif(after),next(s for s in actual.shapes if s.name==p['shape']),head_split.Reader)
    for name,(lower,upper,padding) in boxes.items():
        sphere=stored[name][2]
        if sphere.tolist()!=proof[name]['after']:raise ValueError('Sphere float32 readback differs')
        for bits in np.ndindex(2,2,2):
            corners=np.where(np.asarray(bits)[None,:],upper,lower)
            if np.linalg.norm(corners-sphere[:3],axis=1).max()+padding>sphere[3]:
                raise ValueError('Full morph box plus nominal-motion envelope escapes actual sphere')
    return {'spheres':proof,'decoder':decoder,'onlyThreeNewRadiusFieldsChanged':True,'centersAndOldPelvisSphereExact':True,
        'allMorphCubeAndMotionCornersContained':True,'frame':'serialized B/raw-vertex frame; C excluded',
        'scope':'Independent current serialized anatomy TRI coefficients0..1, identical low/high endpoints, and declared nominal joint limits. Frozen rest-frame motion padding is conservative; no solver-overshoot or engine-culling acceptance.'}
