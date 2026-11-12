"""Opt-in neutral anatomy skin/FSMP candidate; never installs or changes a skeleton.

The existing original procedural shape is reused without reauthoring any vertex,
UV, material or morph. Distal extended-chain nodes and state controls are absent.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import xml.etree.ElementTree as ET
import numpy as np

REPO = Path(__file__).resolve().parents[5]
COMPONENT = Path(__file__).resolve().parents[1]
PROFILE = COMPONENT / 'resources/neutral-rig.json'
TOOLS = REPO / 'src/main/python/build-tools'
VR = REPO / 'src/main/python/vr'
PHYSICS = REPO / 'src/main/python/physics'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_profile(path=PROFILE):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value: raise ValueError('Duplicate profile field: '+key)
            value[key] = item
        return value
    p = json.loads(Path(path).read_text(), object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite profile')))
    expected = json.loads(PROFILE.read_text())
    if p != expected: raise ValueError('Only the pinned neutral anatomy profile is supported')
    return p


def plan_weights(vertices, p):
    v = np.asarray(vertices, dtype=float)
    if v.shape != (p['vertices'], 3) or not np.isfinite(v).all():
        raise ValueError('Unexpected/nonfinite procedural anatomy vertices')
    nt, nb = p['tubeVertices'], p['ballVerticesEach']
    if nt+2*nb != len(v): raise ValueError('Procedural component spans disagree')
    names = [p['root'], *p['drivers']]
    result = np.zeros((len(v),len(names)))
    t = p['tube']; width = t['mobileFromY']-t['anchoredThroughY']
    if width <= 0 or not 0 < t['maximum'] <= .5 or not 0 < p['ballsMaximum'] <= .5:
        raise ValueError('Invalid neutral attachment weights')
    result[:nt,1] = np.clip((v[:nt,1]-t['anchoredThroughY'])/width,0,1)*t['maximum']
    for index in range(2):
        rows = slice(nt+index*nb, nt+(index+1)*nb)
        if not np.all(v[rows,0] < 0 if index == 0 else v[rows,0] > 0):
            raise ValueError('Procedural bilateral anatomy order changed')
        result[rows,2+index] = p['ballsMaximum']
    result[:,0] = 1-result[:,1:].sum(axis=1)
    if (result < 0).any() or not np.allclose(result.sum(axis=1),1):
        raise ValueError('Invalid normalized anatomy weights')
    return names,result


def render_xml(p):
    """Original bounded motion-only XML; parser vocabulary reused from CLAW FSMP adapter."""
    m = p['motion']
    if any(not math.isfinite(x) or x <= 0 for x in m.values()): raise ValueError('Invalid motion parameter')
    root = ET.Element('system')
    root.append(ET.Comment(' Original neutral CLAW anatomy; no collisions or sexual-state controller. '))
    ET.SubElement(ET.SubElement(root,'bone',name=p['anchor']),'mass').text='0'
    for name in p['drivers']:
        bone = ET.SubElement(root,'bone',name=name)
        ET.SubElement(bone,'mass').text=str(m['mass'])
        ET.SubElement(bone,'inertia',x='.1',y='.1',z='.1')
        for key,value in [('linearDamping',m['damping']),('angularDamping',m['damping']),('gravity-factor',0),('wind-factor',0)]:
            ET.SubElement(bone,key).text=str(value)
        parent = p['anchor'] if name == p['drivers'][0] else p['drivers'][0]
        joint = ET.SubElement(root,'generic-constraint',bodyA=parent,bodyB=name)
        frame=ET.SubElement(joint,'frameInB')
        ET.SubElement(frame,'basis',x='0',y='0',z='0',w='1')
        ET.SubElement(frame,'origin',x='0',y='0',z='0')
        ET.SubElement(joint,'useLinearReferenceFrameA').text='false'
        for key,value in [('linearLowerLimit',-m['linearLimit']),('linearUpperLimit',m['linearLimit']),
            ('angularLowerLimit',-m['angularLimitRadians']),('angularUpperLimit',m['angularLimitRadians']),
            ('linearStiffness',1),('angularStiffness',.5),('linearDamping',m['damping']),
            ('angularDamping',m['damping']),('linearEquilibrium',0),('angularEquilibrium',0)]:
            ET.SubElement(joint,key,x=str(value),y=str(value),z=str(value))
    ET.indent(root)
    return ET.tostring(root,encoding='utf-8',xml_declaration=True)+b'\n'


def _imports(pynifly, morphbench):
    sys.path.insert(0,str(Path(__file__).parent))
    for path in (TOOLS,VR,PHYSICS): sys.path.insert(0,str(path))
    import breast_rig as rig
    import body_resource as resource
    import fsmp_motion as fsmp
    api, NifPatch, TripFile, deps = resource.dependencies(pynifly,morphbench)
    return rig,resource,fsmp,api,NifPatch,TripFile,deps


def write_rig(body, skeleton, target, p, rig, api):
    original = api.NifFile(str(body)); nif = api.NifFile(str(body)); skel = api.NifFile(str(skeleton))
    shape = next(s for s in nif.shapes if s.name == p['shape'])
    old = next(s for s in original.shapes if s.name == p['shape'])
    if old.bone_names != [p['root']] or any(w != 1 for _,w in old.bone_weights[p['root']]):
        raise ValueError('Expected original pelvis-only neutral skin')
    rest = {name:rig.matrix(node.global_transform) for name,node in skel.nodes.items()}
    added = set()
    def add(name):
        if name in nif.nodes: return
        if name not in p['requiredNodes']: raise ValueError('Unplanned skeleton ancestry: '+name)
        parent = skel.nodes[name].parent.name
        add(parent)
        frame = np.linalg.inv(rig.matrix(nif.nodes[parent].global_transform))@rest[name]
        nif.add_node(name,rig._transform_buffer(api,frame),parent=parent);added.add(name)
    for name in p['requiredNodes']: add(name)
    if added != set(p['requiredNodes']): raise ValueError('Expected exactly the declared missing ancestry')
    names, weights = plan_weights(old.verts,p)
    pelvis_bind = old.get_shape_skin_to_bone(p['root']).copy()
    for name in p['drivers']:
        shape.add_bone(name,rig._transform_buffer(api,rest[name]),skel.nodes[name].parent.name)
    shape.set_skin_to_bone_xform(p['root'],pelvis_bind)
    for name in p['drivers']:
        bind = np.linalg.inv(rest[name])@rest[p['root']]@rig.matrix(pelvis_bind)
        shape.set_skin_to_bone_xform(name,rig._transform_buffer(api,bind))
    for j,name in enumerate(names):
        shape.setShapeWeights(name,[(int(i),float(weights[i,j])) for i in np.flatnonzero(weights[:,j])])
    shape.set_partitions(old.partitions,old.partition_tris)
    nif.filepath = str(target);nif.save()
    return names,weights


def skin_block_ids(nif, shape):
    raw = nif.blocks[shape.id];extra, = struct.unpack_from('<I',raw,4)
    instance, = struct.unpack_from('<I',raw,88+4*extra)
    data,partition = struct.unpack_from('<II',nif.blocks[instance])
    if nif.kind(instance) not in ('NiSkinInstance','BSDismemberSkinInstance') or [nif.kind(x) for x in (data,partition)] != ['NiSkinData','NiSkinPartition']:
        raise ValueError('Unexpected source anatomy skin format')
    return instance,data,partition


def compose_skin(body,scratch,p,api,fsmp):
    """Transplant only native-authored skin/new nodes into the original container.

    Native saving changes block/string numbering, so those indices are mapped
    explicitly; none of its unrelated rewritten blocks enter the candidate.
    """
    a,b=[api.NifFile(str(path)) for path in (body,scratch)]
    original,result,generated=[fsmp.Nif(Path(path).read_bytes()) for path in (body,body,scratch)]
    index={node.id:a.nodes[name].id for name,node in b.nodes.items() if name in a.nodes}
    for j,name in enumerate(p['requiredNodes']): index[b.nodes[name].id]=len(original.blocks)+j
    for name in p['requiredNodes']:
        node=b.nodes[name];raw=bytearray(generated.blocks[node.id])
        if generated.kind(node.id)!='NiNode' or struct.unpack_from('<I',raw,4)[0]:
            raise ValueError('Only plain new NiNodes without extra data supported')
        count,=struct.unpack_from('<I',raw,72)
        if len(raw)!=80+4*count or struct.unpack_from('<I',raw,len(raw)-4)[0]:
            raise ValueError('Unexpected new node children/effects')
        if struct.unpack_from('<I',raw,8)[0]!=0xffffffff or struct.unpack_from('<I',raw,68)[0]!=0xffffffff:
            raise ValueError('New node cannot own controllers or collision objects')
        struct.pack_into('<I',raw,0,result.name(name))
        for j in range(count):
            child,=struct.unpack_from('<I',raw,76+4*j)
            if child not in index:raise ValueError('Unknown new-node reference')
            struct.pack_into('<I',raw,76+4*j,index[child])
        if result.append('NiNode',raw)!=index[node.id]:raise ValueError('Append-only node ID plan failed')
    parent=a.nodes[p['root']].id;raw=bytearray(original.blocks[parent]);extra,=struct.unpack_from('<I',raw,4)
    off=72+4*extra;count,=struct.unpack_from('<I',raw,off);end=off+4+4*count
    if len(raw)!=end+4 or struct.unpack_from('<I',raw,end)[0]:raise ValueError('Unexpected pelvis children/effects')
    struct.pack_into('<I',raw,off,count+1)
    raw[end:end]=struct.pack('<I',index[b.nodes[p['requiredNodes'][0]].id]);result.blocks[parent]=bytes(raw)
    oldshape=next(x for x in a.shapes if x.name==p['shape']);newshape=next(x for x in b.shapes if x.name==p['shape'])
    oldi,oldd,oldp=skin_block_ids(original,oldshape);newi,newd,newp=skin_block_ids(generated,newshape)
    if original.kind(oldi)!='NiSkinInstance':raise ValueError('Only actual pinned NiSkinInstance source supported')
    oldroot,=struct.unpack_from('<I',original.blocks[oldi],8)
    data,part,root,count=struct.unpack_from('<4I',generated.blocks[newi])
    if (data,part)!=(newd,newp) or index.get(root)!=oldroot or count!=1+len(p['drivers']):
        raise ValueError('Unexpected generated skin reference graph')
    bones=struct.unpack_from('<'+str(count)+'I',generated.blocks[newi],16)
    result.blocks[oldi]=struct.pack('<4I',oldd,oldp,oldroot,count)+struct.pack('<'+str(count)+'I',*(index[x] for x in bones))
    result.blocks[oldd]=generated.blocks[newd];result.blocks[oldp]=generated.blocks[newp]
    allowed={parent,oldi,oldd,oldp}
    if any(x!=result.blocks[i] for i,x in enumerate(original.blocks) if i not in allowed):
        raise ValueError('Composition changed an unrelated original block')
    return result.bytes(),{'modifiedOriginalBlocks':sorted(allowed),'appendedNodes':p['requiredNodes'],
        'originalStringIndicesPreserved':True,'originalOtherBlocksExact':len(original.blocks)-len(allowed)}


def verify_body(body,target,skeleton,p,names,planned,rig,api,NifPatch,fsmp):
    a,b,skel = [api.NifFile(str(x)) for x in (body,target,skeleton)]
    source_shapes={s.name:s for s in a.shapes};result_shapes={s.name:s for s in b.shapes}
    if source_shapes.keys()!=result_shapes.keys(): raise ValueError('Shape list changed')
    if set(b.nodes)-set(a.nodes)!=set(p['requiredNodes']): raise ValueError('Node set differs from declared ancestry')
    for name,node in a.nodes.items():
        if np.max(abs(rig.matrix(node.global_transform)-rig.matrix(b.nodes[name].global_transform))) != 0:
            raise ValueError('Original node frame changed: '+name)
    rest={n:rig.matrix(x.global_transform) for n,x in skel.nodes.items()}
    for name in p['requiredNodes']:
        node=b.nodes[name]
        if node.parent.name != skel.nodes[name].parent.name or np.max(abs(rig.matrix(node.global_transform)-rest[name])) > p['nodeTolerance']:
            raise ValueError('Skeleton bind ancestry/frame mismatch: '+name)
    changed = []
    for name,old in source_shapes.items():
        new=result_shapes[name]
        if (old.verts,old.tris,old.uvs,old.normals,old.textures)!=(new.verts,new.tris,new.uvs,new.normals,new.textures):
            raise ValueError('Unplanned geometry/material/UV change: '+name)
        if [(x.name,x.string_data) for x in old.extra_data('NiStringExtraData')] != [(x.name,x.string_data) for x in new.extra_data('NiStringExtraData')]:
            raise ValueError('Shape extra data changed: '+name)
        if name != p['shape']:
            if old.bone_weights != new.bone_weights: raise ValueError('Unplanned skin change: '+name)
            for bone in old.bone_names:
                if np.max(abs(rig.matrix(old.get_shape_skin_to_bone(bone))-rig.matrix(new.get_shape_skin_to_bone(bone)))) != 0:
                    raise ValueError('Unplanned bind change: '+name)
        else: changed.append(name)
    original=fsmp.Nif(Path(body).read_bytes());result=fsmp.Nif(Path(target).read_bytes())
    allowed=set(skin_block_ids(original,source_shapes[p['shape']]))|{a.nodes[p['root']].id,0}
    # Composed skin/new nodes and the root hook cannot rewrite unrelated blocks.
    unexpected=[i for i,x in enumerate(original.blocks) if i not in allowed and x != result.blocks[i]]
    if unexpected: raise ValueError('Unrelated original NIF blocks changed: '+str(unexpected[:12]))
    shape=result_shapes[p['shape']];old=source_shapes[p['shape']]
    W=rig.read_weights(shape,names);sum_error=float(abs(W.sum(axis=1)-1).max())
    if sum_error>p['weightTolerance'] or (W>0).sum(axis=1).max()>4 or np.max(abs(W/W.sum(axis=1)[:,None]-planned))>p['weightTolerance']:
        raise ValueError('Serialized skin weights differ from bounded plan')
    expected=rest[p['root']]@rig.matrix(old.get_shape_skin_to_bone(p['root']))@rig.matrix(old.global_to_skin)
    errors={name:float(abs(rest[name]@rig.matrix(shape.get_shape_skin_to_bone(name))@rig.matrix(shape.global_to_skin)-expected).max()) for name in names}
    if max(errors.values())>p['nodeTolerance']:raise ValueError('Rest skin frame does not reproduce original attachment')
    pose_checks={};parent={n:x.parent.name if x.parent else None for n,x in skel.nodes.items()}
    binds=np.asarray([rig.matrix(shape.get_shape_skin_to_bone(name))@rig.matrix(shape.global_to_skin) for name in names])
    rest_matrices=np.asarray([[rest[name]@binds[j] for j,name in enumerate(names)]])
    rest_vertices=rig.lbs(shape.verts,W,rest_matrices,normalize=True)[0]
    # Existing hierarchical LBS helper propagates WWD2 to its bilateral children.
    # These are synthetic bounded poses, not FSMP or live-motion acceptance.
    for j,name in enumerate(names[1:],1):
        angle=p['motion']['angularLimitRadians'];c,s=math.cos(angle),math.sin(angle)
        local=np.eye(4);local[:3,:3]=[[c,-s,0],[s,c,0],[0,0,1]];local[0,3]=p['motion']['linearLimit']
        globals_=rig.posed_globals(rest,parent,names,[(name,{name:local},'neutral')])
        moved=rig.lbs(shape.verts,W,globals_@binds[None,:,:,:],normalize=True)[0]
        displacement=np.linalg.norm(moved-rest_vertices,axis=1)
        anchor=(planned[:,1:].sum(axis=1)==0)
        if not np.isfinite(displacement).all() or displacement.max()<=0 or displacement.max()>1 or np.any(displacement[anchor]>1e-10):
            raise ValueError('Synthetic neutral motion violates finite/attachment bound')
        pose_checks[name]={'maxDisplacement':float(displacement.max()),'changedVertices':int((displacement>1e-8).sum()),'fixedAttachmentVertices':int(anchor.sum())}
    patch=NifPatch(target)
    if not patch.consistent():raise ValueError('Morphbench NIF block reader rejected output')
    for shape in b.shapes:
        center,radius=patch.read_bounds(shape.id)
        if not all(math.isfinite(x) for x in [*center,radius]) or radius<=0:raise ValueError('Unreadable shape bounds')
    hook=b.root.get_extra_data(blockname='NiStringExtraData',name=fsmp.HOOK)
    if hook is None or hook.string_data != p['xml']:raise ValueError('Actual FSMP root binding missing')
    return {'shape':changed,'otherShapesExact':len(a.shapes)-1,'originalUnrelatedBlocksExact':len(original.blocks)-len(allowed),'nodeAncestryMatches':p['requiredNodes'],'weightSumError':sum_error,'maxInfluences':int((W>0).sum(axis=1).max()),'restProductErrors':errors,'syntheticPoses':pose_checks,'syntheticMethod':'Existing hierarchical posed_globals/LBS; normalized packed-weight interpretation; not an FSMP simulation.','morphbenchBlockRead':True,'materialPaths':result_shapes[p['shape']].textures}


def build(body_root,skeleton,out,pynifly,morphbench,profile=PROFILE):
    p=load_profile(profile);body_root=Path(body_root).resolve();skeleton=Path(skeleton).resolve()
    rig,resource,fsmp,api,NifPatch,TripFile,deps=_imports(pynifly,morphbench)
    sources=[Path(__file__),Path(__file__).with_name('skin_bounds.py'),Path(profile),REPO/'src/main/python/build-tools/build-genitals.py',REPO/'src/main/resources/recipes/genitals.json',TOOLS/'breast_rig.py',TOOLS/'head_split.py',PHYSICS/'fsmp_motion.py',VR/'body_resource.py',VR/'neck_bounds.py',TOOLS/'morph_quality.py',TOOLS/'tri_patch.py']
    pins={str(path):sha(path) for path in sources}
    inputs={name:skeleton if name=='skeleton.nif' else body_root/name for name in p['inputs']}
    for name,path in inputs.items():
        if sha(path)!=p['inputs'][name]:raise ValueError('Input does not match current0.10 source: '+name)
    out=resource.safe_output(out,[*inputs.values(),*sources])
    for name,path in inputs.items():
        if name.endswith('.nif') and name!='skeleton.nif':fsmp.bind_nif(path.read_bytes(),p['xml']) # refuses existing physics before output
    out.mkdir(parents=True);(out/'FAILED-unverified-do-not-install').write_text('Unverified offline candidate.\n')
    package=out/'candidate';mesh=package/'Meshes/Actors/WerewolfBeast/Character Assets';mesh.mkdir(parents=True)
    tri=inputs['malebodywerewolf.tri'];(mesh/tri.name).write_bytes(tri.read_bytes())
    xml=package/p['xml'];xml.parent.mkdir(parents=True);xml.write_bytes(render_xml(p))
    reports={}
    scratch=out/'scratch';scratch.mkdir()
    for name in ('malebodywerewolf_0.nif','malebodywerewolf_1.nif'):
        path=mesh/name
        native=scratch/name
        names,planned=write_rig(inputs[name],skeleton,native,p,rig,api)
        composed,ledger=compose_skin(inputs[name],native,p,api,fsmp)
        data,hook=fsmp.bind_nif(composed,p['xml']);path.write_bytes(data)
        import skin_bounds
        bound_proof=skin_bounds.expand(path,tri,skeleton,p,rig,api,TripFile,NifPatch,fsmp)
        reports[name]=verify_body(inputs[name],path,skeleton,p,names,planned,rig,api,NifPatch,fsmp)
        reports[name]['composition']=ledger
        reports[name]['newBoneBounds']=bound_proof
        f=api.NifFile(str(path));trip=TripFile()
        from morphbench.file_visibility import read_file_visibility
        anatomy=next(s for s in f.shapes if s.name==p['shape'])
        reports[name]['fileVisibility']=read_file_visibility(f,api,100000)[anatomy.id]
        reports[name]['neutralGeometry']={'vertices':len(anatomy.verts),'triangles':len(anatomy.tris),
            'bounds':[np.asarray(anatomy.verts).min(0).tolist(),np.asarray(anatomy.verts).max(0).tolist()],
            'scope':'Actual unchanged neutral geometry and file flags; external body-occlusion proxy is separate from rendered/game visibility.'}
        with (mesh/tri.name).open('rb') as stream:
            if trip.read(stream)!=0 or not trip.is_valid:raise ValueError('Unreadable matching body TRI')
        shapes={s.name:s for s in f.shapes}
        for sn,entries in trip.shapes.items():
            if sn not in shapes:raise ValueError('TRI refers to missing shape')
            for key,deltas in entries.items():
                for i,delta in deltas:
                    if not 0<=i<len(shapes[sn].verts) or not all(math.isfinite(x) for x in delta):raise ValueError('Incompatible TRI')
        reports[name]['existingMorphs']=sorted({m for rows in trip.shapes.values() for m in rows})
    assert sha(mesh/tri.name)==p['inputs'][tri.name]
    for path,digest in {**pins,**deps}.items():
        if sha(path)!=digest:raise ValueError('Dependency/source changed during build')
    for name,path in inputs.items():
        if sha(path)!=p['inputs'][name]:raise ValueError('Original resource changed during build')
    files={str(x.relative_to(package)).replace('\\','/'):{'bytes':x.stat().st_size,'sha256':sha(x)} for x in package.rglob('*') if x.is_file()}
    report={'status':'offline-neutral-candidate; NOT game/physics accepted','profile':p,'sources':pins,'dependencies':deps,'inputPaths':{n:str(x) for n,x in inputs.items()},'bodies':reports,'files':files,'integrationGate':'Standalone unhooked current male NIFs only. Refuses existing FSMP hook. Composition with CLAW ear/tail/P1 XML, provider conflict audit and final optional packaging require explicit separate integration.','limits':['No new geometry, texture, skeleton, TRI delta, adult state controller, DLL or matrix changes.','Synthetic affine skin witnesses do not establish FSMP live motion, collision safety or visual quality.','Neutral/retracted existing shape only; distal WWD3..9 not driven.','No install, game, release or publication.']}
    (out/'build-report.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'FAILED-unverified-do-not-install').unlink()
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('body-root','skeleton','out','pynifly','morphbench'):parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args()
    try:
        r=build(a.body_root,a.skeleton,a.out,a.pynifly,a.morphbench);print(json.dumps({'status':r['status'],'files':len(r['files'])}))
    except (OSError,ValueError,RuntimeError,KeyError,StopIteration) as error:
        print('CLAW neutral anatomy: '+str(error),file=sys.stderr);raise SystemExit(2)
