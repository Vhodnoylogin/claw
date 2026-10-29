import json
import struct
import sys
import unittest
import tempfile
from pathlib import Path
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import head_split as h
import tri_patch


class SplitTests(unittest.TestCase):
    def test_generated_shader_owner_is_distinct_with_exact_values(self):
        # Two geometry owners must not alias the runtime shader/pass-list state.
        nif=object.__new__(h.Nif)
        nif.type_names=['BSLightingShaderProperty'];nif.kinds=[0]
        block=struct.pack('<II Ii',0,0xFFFFFFFF,0,-1)+bytes(range(84))
        nif.blocks=[block]
        torso=bytearray(120);struct.pack_into('<I',torso,92,0)
        head=bytearray(torso)
        source,clone=h.clone_shape_shader(nif,head,72)
        self.assertEqual(source,0)
        self.assertNotEqual(clone,source)
        self.assertEqual(struct.unpack_from('<I',torso,92)[0],source)
        self.assertEqual(struct.unpack_from('<I',head,92)[0],clone)
        self.assertEqual(nif.blocks[clone],block)
        changed=bytearray(nif.blocks[clone]);changed[16]^=1;nif.blocks[clone]=bytes(changed)
        self.assertEqual(nif.blocks[source],block)

    def test_shader_owner_rejects_unreviewed_reference_graph(self):
        for extras,controller in [(1,-1),(0,2)]:
            nif=object.__new__(h.Nif)
            nif.type_names=['BSLightingShaderProperty'];nif.kinds=[0]
            nif.blocks=[struct.pack('<II Ii',0,0xFFFFFFFF,extras,controller)+bytes(84)]
            shape=bytearray(120);struct.pack_into('<I',shape,92,0)
            with self.assertRaisesRegex(ValueError,'ownership copy contract'):
                h.clone_shape_shader(nif,shape,72)
            self.assertEqual(len(nif.blocks),1)

    def test_majority_ownership_follows_slanted_neck(self):
        v=np.array([[0,0,0],[1,0,0],[0,1,0],[1,1,0]],float);t=np.array([[0,1,2],[1,2,3]])
        result=h.classify(v,t,np.array([0,.4,.4,1]),.5)
        self.assertEqual(result.tolist(),[False,True])

    def test_fur_cards_are_never_cut(self):
        v=np.zeros((4,3));t=np.array([[0,1,2],[1,2,3]])
        result=h.classify(v,t,np.array([0,0,1,1]),.5,True)
        self.assertTrue(result.all())

    def test_shared_seam_is_duplicated_and_orphans_retained(self):
        t=np.array([[0,1,2],[1,2,3]])
        m=h.mapping(t,np.array([False,True]),5)
        self.assertEqual(m['seamVertices'].tolist(),[1,2])
        self.assertEqual(m['torsoVertices'].tolist(),[0,1,2,4])
        self.assertEqual(m['headVertices'].tolist(),[1,2,3])
        self.assertEqual(sorted(np.r_[m['torsoTriangles'],m['headTriangles']].tolist()),[0,1])

    def test_trip_quantization_and_duplicate_seam_correspondence(self):
        data=(b'PIRT'+struct.pack('<H',1)+b'\4head'+struct.pack('<H',1)+b'\1G'+struct.pack('<fH',.0123,3)
              +struct.pack('<H3hH3hH3h',0,1,2,3,1,4,5,6,3,7,8,9))
        p={'head':{'action':'split','mapping':{'torsoVertices':np.array([0,1,2]),'headVertices':np.array([1,2,3])}}}
        output=tri_patch.offsets(h.split_trip(data,p));source=tri_patch.offsets(data)
        self.assertEqual(output[('head','G',1)].packed,source[('head','G',1)].packed)
        self.assertEqual(output[('head_CLAWHead','G',0)].packed,source[('head','G',1)].packed)
        self.assertEqual(output[('head_CLAWHead','G',2)].packed,(7,8,9))
        self.assertEqual(output[('head_CLAWHead','G',2)].scale,source[('head','G',3)].scale)

    def test_rejects_truncated_and_trailing_trip(self):
        for data in (b'PIRT\1',b'PIRT\0\0x'):
            with self.assertRaises(ValueError):h.split_trip(data,{})

    def test_skin_weight_rows_and_binds_are_exact(self):
        prefix=bytes(range(52))+struct.pack('<IB',1,1);fixed=bytes(range(68))
        data=prefix+fixed+struct.pack('<H',3)+struct.pack('<HfHfHf',0,.3,1,.4,4,.9)
        output=h.subset_skin_data(data,[1,4])
        self.assertEqual(output,prefix+fixed+struct.pack('<H',2)+struct.pack('<HfHf',0,.4,1,.9))

    def test_rejects_non_sse_container(self):
        with self.assertRaises(ValueError):h.Nif(b'Gamebryo\n'+bytes(25))

    def test_actual_serialized_candidate(self):
        import os
        root=os.environ.get('CLAW_HEAD_SPLIT_NATIVE')
        if not root:self.skipTest('Set CLAW_HEAD_SPLIT_NATIVE to the completed external candidate')
        root=Path(root);r=json.loads((root/'head-split-report.json').read_text())
        self.assertEqual(r['status'],'verified-offline-split-both-pieces-visible-runtime-pending')
        for sex,body in r['bodies'].items():
            self.assertEqual(h.rig.sha256(body['nif']),body['nifSha256'])
            self.assertEqual(h.rig.sha256(body['tri']),body['triSha256'])
            self.assertEqual(body['options']['head']['0.5']['breastSupportVerticesInHead'],0)
            poses=body['readback']['controlledHeadPoses']
            self.assertEqual(len(poses['poses']),10)
            self.assertEqual(poses['maximumExteriorError'],0.)
            self.assertEqual(poses['maximumDuplicatedSeamGap'],0.)
            owners=body['readback']['shaderPropertyOwnership']
            self.assertTrue(owners)
            self.assertTrue(all(x['distinctOwners'] and x['byteExactProperty'] for x in owners.values()))
            self.assertEqual(len({x['headShaderBlock'] for x in owners.values()}),len(owners))

    def test_native_rejects_independent_tri_and_bind_corruption(self):
        import os
        root=os.environ.get('CLAW_HEAD_SPLIT_NATIVE')
        if not root:self.skipTest('Set CLAW_HEAD_SPLIT_NATIVE to the completed external candidate')
        root=Path(root);report=json.loads((root/'head-split-report.json').read_text());body=report['bodies']['female']
        sources={Path(p).name:Path(p) for p in report['inputs']}
        source=sources['femalebodywerewolf_0.nif'];source_tri=sources['femalebodywerewolf.tri']
        skeleton=sources['skeleton.nif'];profile=json.loads((h.ROOT/'recipes/head-split.json').read_text())
        api,Trip,_=h.rig.load_pynifly(None);skel=api.NifFile(str(skeleton))
        parents={n:x.parent.name if x.parent else None for n,x in skel.nodes.items()}
        planned,_=h.plan(api.NifFile(str(source)),Trip.from_filepath(str(source_tri)).shapes,h.vr_head.descendants(parents,h.vr_head.HEAD),profile)
        with tempfile.TemporaryDirectory(dir=root) as temp:
            tri=Path(temp)/'corrupt.tri';data=bytearray(Path(body['tri']).read_bytes());record=next(iter(tri_patch.offsets(data).values()))
            value=struct.unpack_from('<h',data,record.position)[0];struct.pack_into('<h',data,record.position,value+1 if value<32767 else value-1);tri.write_bytes(data)
            with self.assertRaisesRegex(ValueError,'TRI correspondence'):
                h.verify(api,Trip,source,Path(body['nif']),source_tri,tri,planned)
            nif=Path(temp)/'corrupt.nif';container=h.Nif(Path(body['nif']).read_bytes())
            shape=container.blocks[planned['head']['sourceBlock']];extra=struct.unpack_from('<I',shape,4)[0]
            skin=struct.unpack_from('<I',shape,88+4*extra)[0];data_id=struct.unpack_from('<I',container.blocks[skin])[0]
            block=bytearray(container.blocks[data_id]);value=struct.unpack_from('<f',block,36)[0];struct.pack_into('<f',block,36,value+.25)
            container.blocks[data_id]=bytes(block);nif.write_bytes(container.bytes())
            with self.assertRaisesRegex(ValueError,'Skin frame'):
                h.verify(api,Trip,source,nif,source_tri,Path(body['tri']),planned)

    def test_head_derived_torso_keeps_head_texture_and_triangle_uvs(self):
        import os
        root=os.environ.get('CLAW_HEAD_SPLIT_NATIVE')
        if not root:self.skipTest('Set CLAW_HEAD_SPLIT_NATIVE to the completed external candidate')
        root=Path(root);report=json.loads((root/'head-split-report.json').read_text());body=report['bodies']['female']
        source=next(Path(p) for p in report['inputs'] if Path(p).name=='femalebodywerewolf_0.nif')
        api,_,_=h.rig.load_pynifly(None);before={s.name:s for s in api.NifFile(str(source)).shapes};after={s.name:s for s in api.NifFile(body['nif']).shapes}
        index=json.loads((root/'female-index-map.json').read_text())['head']
        self.assertNotEqual(before['head'].textures,before['body'].textures)
        for name,key in [('head','torsoTriangles'),('head_CLAWHead','headTriangles')]:
            self.assertEqual(after[name].textures,before['head'].textures)
            self.assertEqual(bytes(after[name].shader.properties),bytes(before['head'].shader.properties))
            actual=np.asarray(after[name].uvs)[np.asarray(after[name].tris)]
            expected=np.asarray(before['head'].uvs)[np.asarray(before['head'].tris)[index[key]]]
            np.testing.assert_array_equal(actual,expected)

    def test_native_rejects_shared_shader_owner_even_with_equal_material(self):
        import os
        root=os.environ.get('CLAW_HEAD_SPLIT_NATIVE')
        if not root:self.skipTest('Set CLAW_HEAD_SPLIT_NATIVE to the completed external candidate')
        root=Path(root);report=json.loads((root/'head-split-report.json').read_text());body=report['bodies']['female']
        sources={Path(p).name:Path(p) for p in report['inputs']}
        source=sources['femalebodywerewolf_0.nif'];source_tri=sources['femalebodywerewolf.tri']
        api,Trip,_=h.rig.load_pynifly(None);skel=api.NifFile(str(sources['skeleton.nif']))
        parents={n:x.parent.name if x.parent else None for n,x in skel.nodes.items()}
        planned,_=h.plan(api.NifFile(str(source)),Trip.from_filepath(str(source_tri)).shapes,
                         h.vr_head.descendants(parents,h.vr_head.HEAD),json.loads((h.ROOT/'recipes/head-split.json').read_text()))
        parsed=api.NifFile(body['nif']);shapes={s.name:s.id for s in parsed.shapes}
        container=h.Nif(Path(body['nif']).read_bytes())
        torso=container.blocks[shapes['head']];extra=struct.unpack_from('<I',torso,4)[0]
        shader=struct.unpack_from('<I',torso,92+4*extra)[0]
        head=bytearray(container.blocks[shapes['head_CLAWHead']]);extra=struct.unpack_from('<I',head,4)[0]
        struct.pack_into('<I',head,92+4*extra,shader)
        container.blocks[shapes['head_CLAWHead']]=bytes(head)
        with tempfile.TemporaryDirectory(dir=root) as temp:
            corrupt=Path(temp)/'shared-shader.nif';corrupt.write_bytes(container.bytes())
            with self.assertRaisesRegex(ValueError,'share mutable shader property'):
                h.verify(api,Trip,source,corrupt,source_tri,Path(body['tri']),planned)


if __name__=='__main__':unittest.main()
