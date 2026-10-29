"""Lossless, offline anatomical partitioning of the reviewed SSE CLAW meshes.

The narrow binary adapter preserves packed vertices, shaders and binds rather
than round-tripping them through a DCC. Public PyNifly is the independent reader.
Only the reviewed one-partition SSE shapes can be split. No weights are edited.
"""
from __future__ import annotations
from pathlib import Path
import hashlib
import json
import struct
import numpy as np
import breast_rig as rig
import vr_head

ROOT = Path(__file__).resolve().parents[1]
SUFFIX = '_CLAWHead'


class Reader:
    def __init__(self, data): self.data, self.pos = bytes(data), 0
    def take(self, n):
        if n < 0 or self.pos+n > len(self.data): raise ValueError('Truncated binary input')
        a = self.data[self.pos:self.pos+n]; self.pos += n; return a
    def unpack(self, fmt): return struct.unpack(fmt, self.take(struct.calcsize(fmt)))
    def done(self):
        if self.pos != len(self.data): raise ValueError('Unsupported binary trailing data')


def encode(fmt, *args): return struct.pack(fmt, *args)


class Nif:
    """SSE 20.2.0.7/user12/BS100 block container; existing block IDs never move."""
    def __init__(self, data):
        r = Reader(data); end = data.index(b'\n')+1; r.take(end)
        version, endian, user = r.unpack('<IBI')
        if (version, endian, user) != (0x14020007, 1, 12): raise ValueError('Only reviewed little-endian SSE supported')
        self.count_offset = r.pos; count, bs = r.unpack('<II')
        if bs != 100: raise ValueError('Only SSE BS100 supported')
        for _ in range(3): r.take(r.unpack('<B')[0])
        self.prefix = data[:r.pos]
        types, = r.unpack('<H'); self.type_names = [r.take(r.unpack('<I')[0]).decode('ascii') for _ in range(types)]
        self.kinds = list(r.unpack('<'+str(count)+'H')); sizes = r.unpack('<'+str(count)+'I')
        strings, self.maxlen = r.unpack('<II')
        self.strings = [r.take(r.unpack('<I')[0]) for _ in range(strings)]
        groups, = r.unpack('<I')
        if groups: raise ValueError('Grouped NIF unsupported')
        self.blocks = [r.take(n) for n in sizes]
        self.footer = r.take(len(data)-r.pos)
        if self.footer != encode('<II', 1, 0): raise ValueError('Expected one Scene Root')
    def kind(self, i): return self.type_names[self.kinds[i]]
    def append(self, kind, data):
        i = len(self.blocks); self.blocks.append(bytes(data)); self.kinds.append(self.type_names.index(kind)); return i
    def name(self, text):
        value = text.encode('utf-8')
        if value not in self.strings: self.strings.append(value)
        return self.strings.index(value)
    def bytes(self):
        prefix = bytearray(self.prefix); struct.pack_into('<I', prefix, self.count_offset, len(self.blocks))
        return (bytes(prefix)+encode('<H', len(self.type_names))
                +b''.join(encode('<I',len(x.encode('ascii')))+x.encode('ascii') for x in self.type_names)
                +encode('<'+str(len(self.kinds))+'H', *self.kinds)
                +encode('<'+str(len(self.blocks))+'I', *map(len,self.blocks))
                +encode('<II',len(self.strings),max(map(len,self.strings),default=0))
                +b''.join(encode('<I',len(x))+x for x in self.strings)+encode('<I',0)
                +b''.join(self.blocks)+self.footer)


class Partition:
    def __init__(self, data):
        r = Reader(data); count, size, self.stride, self.desc = r.unpack('<IIIQ')
        if count != 1 or self.stride != 40 or size % self.stride: raise ValueError('Expected one reviewed 40-byte SSE partition')
        self.vertices = np.frombuffer(r.take(size), np.uint8).reshape(-1,self.stride).copy()
        nv, nt, nb, ns, nw = r.unpack('<5H')
        if nv != len(self.vertices) or ns or nw != 4: raise ValueError('Unsupported partition layout')
        self.bones = r.take(nb*2)
        if r.unpack('<B')[0] != 1: raise ValueError('Expected vertex map')
        mapping = np.frombuffer(r.take(nv*2),'<u2')
        if not np.array_equal(mapping,np.arange(nv)): raise ValueError('Expected identity partition vertex map')
        if r.unpack('<B')[0] != 1: raise ValueError('Expected stored partition weights')
        self.weights = np.frombuffer(r.take(nv*16),np.uint8).reshape(nv,16).copy()
        if r.unpack('<B')[0] != 1: raise ValueError('Expected triangles')
        self.triangles = np.frombuffer(r.take(nt*6),'<u2').reshape(nt,3).copy()
        if r.unpack('<B')[0] != 1: raise ValueError('Expected packed partition bone indices')
        self.indices = np.frombuffer(r.take(nv*4),np.uint8).reshape(nv,4).copy()
        self.tail = r.take(10)  # LOD, global VB, vertex descriptor
        duplicate = np.frombuffer(r.take(nt*6),'<u2').reshape(nt,3)
        if not np.array_equal(duplicate,self.triangles): raise ValueError('Partition triangle copies disagree')
        r.done()
    def subset(self, ids, triangle_ids):
        ids = np.asarray(ids,int); triangle_ids = np.asarray(triangle_ids,int)
        remap = np.full(len(self.vertices),-1,int); remap[ids] = np.arange(len(ids))
        triangles = remap[self.triangles[triangle_ids]]
        if triangles.min() < 0 or len(ids)>65535 or len(triangles)>65535: raise ValueError('Invalid subset map')
        tris = np.asarray(triangles,'<u2').tobytes(); nv,nt = len(ids),len(triangles)
        return (encode('<IIIQ',1,nv*self.stride,self.stride,self.desc)+self.vertices[ids].tobytes()
                +encode('<5H',nv,nt,len(self.bones)//2,0,4)+self.bones+b'\1'
                +np.arange(nv,dtype='<u2').tobytes()+b'\1'+self.weights[ids].tobytes()+b'\1'+tris
                +b'\1'+self.indices[ids].tobytes()+self.tail+tris)


def subset_skin_data(data, ids):
    r = Reader(data); frame = r.take(52); nb,has = r.unpack('<IB')
    if has != 1: raise ValueError('Expected NiSkinData vertex weights')
    remap = {int(old):new for new,old in enumerate(ids)}; output = [frame,encode('<IB',nb,has)]
    for _ in range(nb):
        fixed = r.take(68); count, = r.unpack('<H'); weights = []
        for _ in range(count):
            vertex, = r.unpack('<H'); weight = r.take(4)
            if vertex in remap: weights.append(encode('<H',remap[vertex])+weight)
        output.extend([fixed,encode('<H',len(weights)),b''.join(weights)])
    r.done(); return b''.join(output)


def components(faces, count):
    parent = np.arange(count)
    def root(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for a,b,c in faces:
        p = root(int(a)); parent[root(int(b))] = p; parent[root(int(c))] = p
    return np.asarray([root(i) for i in range(count)])


def classify(vertices, faces, head_mass, threshold, cards=False):
    """Skin follows majority ownership; fur cards stay whole to preserve coverage."""
    if cards:
        groups = components(faces,len(vertices)); flags = {}
        for group in np.unique(groups):
            ids = np.flatnonzero(groups==group); flags[int(group)] = bool(head_mass[ids].mean()>=threshold)
        return np.asarray([flags[int(groups[t[0]])] for t in faces])
    return head_mass[faces].mean(axis=1)>=threshold


def mapping(faces, selected, count):
    torso_tris = np.flatnonzero(~selected); head_tris = np.flatnonzero(selected)
    torso = np.unique(faces[torso_tris]); head = np.unique(faces[head_tris])
    unused = np.setdiff1d(np.arange(count),np.unique(faces)); torso = np.union1d(torso,unused)
    return {'torsoVertices':torso,'headVertices':head,'torsoTriangles':torso_tris,'headTriangles':head_tris,
            'seamVertices':np.intersect1d(torso,head)}


def option(vertices, faces, mass, selected, breast):
    m = mapping(faces,selected,len(vertices)); seam = m['seamVertices']; tri = vertices[faces]
    area = np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)/2
    edges = {}
    for i,t in enumerate(faces):
        for a,b in ((t[0],t[1]),(t[1],t[2]),(t[2],t[0])):
            edges.setdefault(tuple(sorted((int(a),int(b)))),[]).append(bool(selected[i]))
    boundary = [e for e, sides in edges.items() if any(sides) and not all(sides)]
    length = sum(float(np.linalg.norm(vertices[a]-vertices[b])) for a,b in boundary)
    return {'headTriangles':int(selected.sum()),'torsoTriangles':int((~selected).sum()),
            'seamVertexCount':len(seam),'seamEdgeLength':length,
            'seamBounds':[vertices[seam].min(0).tolist(),vertices[seam].max(0).tolist()] if len(seam) else None,
            'areaWeightedOwnershipError':float(np.sum(area*np.abs(selected-mass[faces].mean(1)))),
            'breastSupportVerticesInHead':int(np.any(breast[m['headVertices']]!=0,axis=1).sum())}


def plan(nif, raw, head_names, profile):
    result, comparisons = {}, {}
    for shape in nif.shapes:
        if shape.name.endswith(SUFFIX): raise ValueError('Already split input')
        vertices=np.asarray(shape.verts);faces=np.asarray(shape.tris,int); names=list(shape.bone_weights)
        weights=rig.read_weights(shape,names); cols=[i for i,n in enumerate(names) if n in head_names]
        mass=weights[:,cols].sum(1)/weights.sum(1)
        cards=shape.name.startswith('fur_') or shape.name.endswith('Blend')
        breast=rig.dense_morph(raw,shape.name,'CLAWTorsoBreastSize',len(vertices))
        selected=classify(vertices,faces,mass,profile['threshold'],cards)
        comparisons[shape.name]={str(t):option(vertices,faces,mass,classify(vertices,faces,mass,t,cards),breast)
                                 for t in profile['comparedThresholds']}
        m=mapping(faces,selected,len(vertices))
        if comparisons[shape.name][str(profile['threshold'])]['breastSupportVerticesInHead']:
            raise ValueError('Chosen boundary removes breast support: '+shape.name)
        result[shape.name]={'mapping':m,'action':'head' if selected.all() else 'torso' if not selected.any() else 'split',
                            'sourceBlock':shape.id,'cards':cards}
    if result['head']['action']!='split': raise ValueError('Mixed head was not split')
    return result,comparisons


def clone_shape_shader(nif, shape, sphere):
    """Give the generated shape its own mutable engine shader/pass state.

    Texture sets and alpha remain shared, unchanged data. Controllers and extra
    data can contain owner references and need a separate graph-copy contract.
    """
    source,=struct.unpack_from('<I',shape,sphere+20)
    if source>=len(nif.blocks) or nif.kind(source)!='BSLightingShaderProperty':
        raise ValueError('Expected reviewed lighting shader property')
    block=nif.blocks[source]
    # SSE BS100: shader type, NiObjectNET name, extra count, controller.
    if len(block)<16:
        raise ValueError('Truncated lighting shader property')
    extras,controller=struct.unpack_from('<Ii',block,8)
    if extras or controller!=-1:
        raise ValueError('Shader controllers/extra data need an ownership copy contract')
    clone=nif.append('BSLightingShaderProperty',block)
    struct.pack_into('<I',shape,sphere+20,clone)
    return source,clone


def split_nif(data, plan_, names):
    nif=Nif(data); added=[]; changed=[]; appended=[]; shader_clones=[]
    for name,p in plan_.items():
        if p['action']!='split': continue
        bid=p['sourceBlock']; shape=bytearray(nif.blocks[bid]);extra,=struct.unpack_from('<I',shape,4)
        sphere=72+4*extra; skinid,=struct.unpack_from('<I',shape,sphere+16)
        if nif.kind(bid)!='BSTriShape' or len(shape)!=120+4*extra or nif.kind(skinid)!='BSDismemberSkinInstance':
            raise ValueError('Unsupported shape/skin layout: '+name)
        instance=bytearray(nif.blocks[skinid]);dataid,partid=struct.unpack_from('<II',instance)
        if nif.kind(dataid)!='NiSkinData' or nif.kind(partid)!='NiSkinPartition':raise ValueError('Unexpected skin references')
        partition=Partition(nif.blocks[partid]);source_data=nif.blocks[dataid]
        m=p['mapping']; newpart=partition.subset(m['headVertices'],m['headTriangles'])
        newdata=subset_skin_data(source_data,m['headVertices'])
        # Keep material values, texture/alpha and bone references, but never make
        # independently morphed shapes share a mutable shader/pass-list owner.
        newshape=bytearray(shape)
        shader_source,shader_clone=clone_shape_shader(nif,newshape,sphere)
        appended.append(shader_clone)
        shader_clones.append({'source':shader_source,'clone':shader_clone,'shape':name+SUFFIX})
        nsid=len(nif.blocks);ndid=nsid+1;npid=nsid+2;nbid=nsid+3
        newinstance=bytearray(instance);struct.pack_into('<II',newinstance,0,ndid,npid)
        struct.pack_into('<I',newshape,0,nif.name(name+SUFFIX));struct.pack_into('<I',newshape,sphere+16,nsid)
        for kind,value in [('BSDismemberSkinInstance',newinstance),('NiSkinData',newdata),('NiSkinPartition',newpart),('BSTriShape',newshape)]:
            appended.append(nif.append(kind,value))
        nif.blocks[dataid]=subset_skin_data(source_data,m['torsoVertices'])
        nif.blocks[partid]=partition.subset(m['torsoVertices'],m['torsoTriangles'])
        changed.extend([dataid,partid]); added.append(nbid)
    root=bytearray(nif.blocks[0]); extra,=struct.unpack_from('<I',root,4);offset=72+4*extra
    count,=struct.unpack_from('<I',root,offset);end=offset+4+count*4
    if len(root)!=end+4 or struct.unpack_from('<I',root,end)[0]:raise ValueError('Unexpected Scene Root children/effects')
    struct.pack_into('<I',root,offset,count+len(added));root[end:end]=encode('<'+str(len(added))+'I',*added)
    nif.blocks[0]=bytes(root); changed.append(0)
    # Every untouched original block must remain exactly byte-identical.
    old=Nif(data)
    if any(a!=b for i,(a,b) in enumerate(zip(old.blocks,nif.blocks)) if i not in changed):raise ValueError('Unrelated block changed')
    return nif.bytes(),{'modifiedOriginalBlocks':changed,'appendedBlocks':appended,
                       'shaderPropertyClones':shader_clones,'byteExactUntouchedBlocks':len(old.blocks)-len(changed)}


def split_trip(data, plan_):
    r=Reader(data);magic=r.take(4)
    if magic not in (b'PIRT',b'\0IRT'):raise ValueError('Not TRIP')
    count,=r.unpack('<H'); records=[]; names=set()
    def name():
        value=r.take(r.unpack('<B')[0])
        if not value:raise ValueError('Empty TRIP name')
        return value
    def packname(n):
        if len(n)>255:raise ValueError('TRIP name too long')
        return encode('<B',len(n))+n
    for _ in range(count):
        shape=name(); decoded=shape.decode('iso-8859-15')
        if decoded in names or decoded not in plan_:raise ValueError('Ambiguous/unknown TRI shape')
        names.add(decoded);nm,=r.unpack('<H');morphs=[]
        for _ in range(nm):
            morph=name();scale=r.take(4);n,=r.unpack('<H');pairs=[]
            for _ in range(n):
                vertex,=r.unpack('<H');pairs.append((vertex,r.take(6)))
            if len({i for i,_ in pairs})!=len(pairs):raise ValueError('Duplicate TRI vertex')
            morphs.append((morph,scale,pairs))
        p=plan_[decoded]
        choices=[(shape,None)] if p['action']!='split' else [(shape,p['mapping']['torsoVertices']),(shape+SUFFIX.encode(),p['mapping']['headVertices'])]
        for newname,ids in choices:
            remap=None if ids is None else {int(old):new for new,old in enumerate(ids)};output=[]
            for morph,scale,pairs in morphs:
                values=[encode('<H',i if remap is None else remap[i])+packed for i,packed in pairs if remap is None or i in remap]
                if values:output.append(packname(morph)+scale+encode('<H',len(values))+b''.join(values))
            if output:records.append(packname(newname)+encode('<H',len(output))+b''.join(output))
    r.done(); return magic+encode('<H',len(records))+b''.join(records)


def pose_equivalence(before,after,raw_before,raw_after,plan_,skeleton):
    """Execute all ten imposed head states on actual serialized geometry/binds."""
    rest={n:rig.matrix(x.global_transform) for n,x in skeleton.nodes.items()}
    parents={n:x.parent.name if x.parent else None for n,x in skeleton.nodes.items()}
    bank=vr_head.pose_bank(rest,parents);poses=[vr_head.impose(rest,parents,x) for _,x,_ in bank]
    new={s.name:s for s in after.shapes};rows={};maximum=0.;seam_max=0.
    states=[('neutral',{}),('breast-half',{'CLAWTorsoBreastSize':.5}),('breast-full',{'CLAWTorsoBreastSize':1.}),
            ('girth-half',{'CLAWTorsoGirth':.5}),('girth-full',{'CLAWTorsoGirth':1.}),
            ('girth-breast-half',{'CLAWTorsoBreastSize':.5,'CLAWTorsoGirth':.5})]
    for b in before.shapes:
        p=plan_[b.name]
        if p['action']!='split':continue
        names=list(b.bone_weights);globals_=np.asarray([[pose[n] for n in names] for pose in poses])
        def evaluate(shape,raw,coefficients):
            v=np.asarray(shape.verts,float).copy()
            for morph,value in coefficients.items():v+=value*rig.dense_morph(raw,shape.name,morph,len(v))
            binds=np.asarray([rig.matrix(shape.get_shape_skin_to_bone(n))@rig.matrix(shape.global_to_skin) for n in names])
            effective=np.einsum('pbij,bjk->pbik',globals_,binds)
            weights=rig.read_weights(shape,names)
            return [rig.lbs(v,weights,effective,normalize) for normalize in (False,True)]
        m=p['mapping'];seam=m['seamVertices'];row={}
        for label,coefficients in states:
            old=evaluate(b,raw_before,coefficients);parts=[];error=0.
            for dest,key in [(b.name,'torsoVertices'),(b.name+SUFFIX,'headVertices')]:
                ids=m[key];actual=evaluate(new[dest],raw_after,coefficients);parts.append((ids,actual))
                error=max(error,*[float(np.linalg.norm(x-y[:,ids],axis=-1).max()) for x,y in zip(actual,old)])
            seam_error=0.
            if len(seam):
                a=np.searchsorted(parts[0][0],seam);c=np.searchsorted(parts[1][0],seam)
                seam_error=max(float(np.linalg.norm(x[:,a]-y[:,c],axis=-1).max()) for x,y in zip(parts[0][1],parts[1][1]))
            row[label]={'allVertexExteriorMaxError':error,'duplicatedSeamMaxDistance':seam_error}
            maximum=max(maximum,error);seam_max=max(seam_max,seam_error)
        rows[b.name]=row
    if maximum!=0. or seam_max!=0.:raise ValueError('Serialized split diverges in controlled head poses/morphs')
    return {'maximumExteriorError':maximum,'maximumDuplicatedSeamGap':seam_max,'modes':['rawPacked','normalized'],
            'poses':[{'name':n,'kind':k,'localReplacements':{n:m.tolist() for n,m in e.items()}} for n,e,k in bank],
            'states':rows,'scope':'Equivalence with source, including its existing head/breast susceptibility; this does not qualify hiding the Head bone or camera clearance.'}


def verify(api, Trip, source, target, source_tri, target_tri, plan_,skeleton=None):
    before=api.NifFile(str(source));after=api.NifFile(str(target));old={s.name:s for s in before.shapes};new={s.name:s for s in after.shapes}
    expected=set(old)|{n+SUFFIX for n,p in plan_.items() if p['action']=='split'}
    if set(new)!=expected:raise ValueError('Serialized shape inventory mismatch')
    source_blocks=Nif(Path(source).read_bytes());target_blocks=Nif(Path(target).read_bytes())
    shader_ownership={};generated_shader_ids=set()
    for name,p in plan_.items():
        if p['action']!='split':continue
        def shader_id(blocks,shape):
            data=blocks.blocks[shape.id];extra=struct.unpack_from('<I',data,4)[0]
            return struct.unpack_from('<I',data,92+4*extra)[0]
        original=shader_id(source_blocks,old[name])
        torso=shader_id(target_blocks,new[name]);head=shader_id(target_blocks,new[name+SUFFIX])
        if torso!=original or head<len(source_blocks.blocks) or head in generated_shader_ids:
            raise ValueError('Split shapes share mutable shader property state: '+name)
        if target_blocks.kind(head)!='BSLightingShaderProperty' or target_blocks.blocks[head]!=source_blocks.blocks[original]:
            raise ValueError('Cloned shader property values changed: '+name)
        generated_shader_ids.add(head)
        shader_ownership[name]={'torsoShaderBlock':torso,'headShaderBlock':head,'distinctOwners':True,'byteExactProperty':True}
    raw_before=Trip.from_filepath(str(source_tri)).shapes;raw_after=Trip.from_filepath(str(target_tri)).shapes
    if {k for x in raw_before.values() for k in x}!={k for x in raw_after.values() for k in x}:raise ValueError('Public morph union changed')
    checks={};tri_pairs=0
    for name,p in plan_.items():
        b=old[name];m=p['mapping'];names=list(b.bone_weights);bw=rig.read_weights(b,names)
        choices=[(name,np.arange(len(b.verts)),np.arange(len(b.tris)))] if p['action']!='split' else [(name,m['torsoVertices'],m['torsoTriangles']),(name+SUFFIX,m['headVertices'],m['headTriangles'])]
        for dest,ids,tids in choices:
            a=new[dest];remap=np.full(len(b.verts),-1,int);remap[ids]=np.arange(len(ids))
            for field in ('verts','uvs','normals','colors'):
                bv=np.asarray(getattr(b,field));av=np.asarray(getattr(a,field));expected_value=bv[ids] if len(bv) else bv
                if not np.array_equal(av,expected_value):raise ValueError('Serialized '+field+' changed: '+dest)
            if not np.array_equal(np.asarray(a.tris),remap[np.asarray(b.tris)[tids]]):raise ValueError('Triangle map failed: '+dest)
            if not np.array_equal(np.asarray(a.uvs)[np.asarray(a.tris)],np.asarray(b.uvs)[np.asarray(b.tris)[tids]]):raise ValueError('Per-triangle UV/material correspondence changed: '+dest)
            if not np.array_equal(rig.read_weights(a,names),bw[ids]):raise ValueError('Packed weights changed: '+dest)
            if not a.has_global_to_skin or not np.array_equal(rig.matrix(a.global_to_skin),rig.matrix(b.global_to_skin)):raise ValueError('Skin frame changed')
            for bone in b.bone_weights:
                if not np.array_equal(rig.matrix(a.get_shape_skin_to_bone(bone)),rig.matrix(b.get_shape_skin_to_bone(bone))):raise ValueError('Skin bind changed')
            if (a.shader_block_name,bytes(a.shader.properties),a.textures)!=(b.shader_block_name,bytes(b.shader.properties),b.textures):raise ValueError('Material changed')
            if (bytes(a.alpha_property.properties) if a.alpha_property else None)!=(bytes(b.alpha_property.properties) if b.alpha_property else None):raise ValueError('Alpha changed')
            if [(x.id,x.flags) for x in a.partitions]!=[(x.id,x.flags) for x in b.partitions] or len(a.partition_tris)!=len(tids):raise ValueError('Partitions changed')
            if [(x.name,x.string_data) for x in a.extra_data()]!=[(x.name,x.string_data) for x in b.extra_data()]:raise ValueError('BODYTRI/extra data changed')
            for morph,pairs in raw_before.get(name,{}).items():
                expected_pairs={int(remap[i]):value for i,value in pairs if remap[i]>=0};actual_pairs=dict(raw_after.get(dest,{}).get(morph,[]))
                if expected_pairs!=actual_pairs:raise ValueError('TRI correspondence changed: '+dest+'/'+morph)
                tri_pairs+=len(actual_pairs)
            checks[dest]={'vertices':len(ids),'triangles':len(tids),'exactPackedWeights':True,'exactMaterialsBindsUvNormals':True,
                          'perTriangleOriginalMaterialAndUvPreserved':True,'originalTexturePaths':dict(a.textures)}
    # Original skeleton graph/transforms, including scales, remain unchanged.
    for name,node in before.nodes.items():
        if name not in after.nodes:raise ValueError('Node disappeared')
        other=after.nodes[name]
        if (node.parent.name if node.parent else None)!=(other.parent.name if other.parent else None):raise ValueError('Node parent changed')
        if not np.array_equal(rig.matrix(node.transform),rig.matrix(other.transform)):raise ValueError('Node transform changed')
    result={'shapes':checks,'mappedSparseTriPairs':tri_pairs,'publicMorphCount':len({k for x in raw_after.values() for k in x}),
            'shaderPropertyOwnership':shader_ownership}
    if skeleton is not None:result['controlledHeadPoses']=pose_equivalence(before,after,raw_before,raw_after,plan_,skeleton)
    return result


def build(body_root,skeleton,profile_file,output,pynifly=None):
    profile=json.loads(Path(profile_file).read_text()); body_root=Path(body_root);skeleton=Path(skeleton)
    if profile!=json.loads((ROOT/'recipes/head-split.json').read_text()):raise ValueError('Unreviewed split profile')
    files=[Path(profile_file),skeleton]+[body_root/e[k] for e in profile['bodies'].values() for k in ('nif','tri')]+[body_root/e['nif'].replace('_0.nif','_1.nif') for e in profile['bodies'].values()]
    inputs={str(x.resolve()):rig.sha256(x) for x in files}
    if rig.sha256(skeleton)!=profile['skeletonSha256']:raise ValueError('XP32 input changed')
    for e in profile['bodies'].values():
        for k in ('nif','tri'):
            if rig.sha256(body_root/e[k])!=e[k+'Sha256']:raise ValueError('Pinned '+k+' changed')
        if rig.sha256(body_root/e['nif'].replace('_0.nif','_1.nif'))!=e['nifSha256']:raise ValueError('Weight endpoints differ')
    out=rig.safe_output(output,files);api,Trip,dependency=rig.load_pynifly(pynifly)
    skel=api.NifFile(str(skeleton));parents={n:x.parent.name if x.parent else None for n,x in skel.nodes.items()};head_names=vr_head.descendants(parents,vr_head.HEAD)
    source={str(p):rig.sha256(p) for p in [Path(__file__),ROOT/'scripts/split-vr-body.py',ROOT/'scripts/breast_rig.py',ROOT/'scripts/vr_head.py',ROOT/'recipes/head-split.json']}
    deps={str(p):rig.sha256(p) for p in [dependency/'NiflyDLL.dll',dependency/'pyn/pynifly.py',dependency/'tri/tripfile.py']}
    prepared={}
    for sex,e in profile['bodies'].items():
        nif=api.NifFile(str(body_root/e['nif']));raw=Trip.from_filepath(str(body_root/e['tri'])).shapes
        planned,comparisons=plan(nif,raw,head_names,profile)
        data,audit=split_nif((body_root/e['nif']).read_bytes(),planned,{})
        tri=split_trip((body_root/e['tri']).read_bytes(),planned)
        prepared[sex]=(planned,comparisons,data,tri,audit)
    out.mkdir(parents=False)
    (out/'NOT_INSTALLABLE.txt').write_text('Offline anatomical split trial. Both pieces visible. Runtime shape visibility, camera clearance and game acceptance remain pending. No skeleton output.\n')
    report={'status':'offline-anatomical-split-readback-pending','inputs':inputs,'sourceSha256':source,'dependencySha256':deps,'bodies':{},'selection':profile['selectionRationale']}
    try:
        for sex,e in profile['bodies'].items():
            planned,comparisons,data,tri,audit=prepared[sex];folder=out/sex/'meshes/actors/werewolfbeast/character assets';folder.mkdir(parents=True)
            nifpath=folder/e['nif'];tripath=folder/e['tri'];nifpath.write_bytes(data);tripath.write_bytes(tri)
            verified=verify(api,Trip,body_root/e['nif'],nifpath,body_root/e['tri'],tripath,planned,skel)
            highpath=folder/e['nif'].replace('_0.nif','_1.nif');highpath.write_bytes(data)
            serialized={n:{'action':p['action'],'sourceBlock':p['sourceBlock'],'wholeFurCards':p['cards'],**{k:v.tolist() for k,v in p['mapping'].items()}} for n,p in planned.items()}
            (out/(sex+'-index-map.json')).write_text(json.dumps(serialized,separators=(',',':')))
            report['bodies'][sex]={'nifSha256':rig.sha256(nifpath),'triSha256':rig.sha256(tripath),'nif':str(nifpath),'tri':str(tripath),'options':comparisons,'binaryAudit':audit,'readback':verified,
                'headVisibilityShapes':[n if p['action']=='head' else n+SUFFIX for n,p in planned.items() if p['action']!='torso']}
        if any(rig.sha256(p)!=h for p,h in {**inputs,**source,**deps}.items()):raise ValueError('Input/source/dependency changed during build')
        report['status']='verified-offline-split-both-pieces-visible-runtime-pending'
    except Exception:
        report['status']='FAILED-unverified-do-not-install';raise
    finally:(out/'head-split-report.json').write_text(json.dumps(report,indent=2))
    return out/'head-split-report.json'
