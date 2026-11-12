"""Original XML graph rejection and actual native/facade composition checks."""
from pathlib import Path
import argparse
import copy
import importlib.util
import json
import struct
import sys
import unittest
import xml.etree.ElementTree as ET
import numpy as np

REPO = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location('claw_compose_motion',REPO/'src/main/components/adult-anatomy/python/compose_motion.py')
c = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(c)
ARGS = None


class Pure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.anatomy,cls.fsmp = c.modules(); cls.p = cls.anatomy.load_profile()
        cls.motion = cls.fsmp.render_xml(False); cls.neutral = cls.anatomy.render_xml(cls.p)
        cls.drivers = cls.fsmp.common.source.NODES; cls.anchors = ('NPC Head [Head]','Tails')

    def compose(self,motion=None,neutral=None,drivers=None,anchors=None):
        return c.compose_xml(self.motion if motion is None else motion,self.neutral if neutral is None else neutral,
            self.drivers,self.p['drivers'] if drivers is None else drivers,self.anchors,[self.p['anchor']] if anchors is None else anchors)

    def mutation(self,data,change):
        root=ET.fromstring(data); change(root); return ET.tostring(root)

    def test_original_parameters_and_exact_twelve_driver_union(self):
        output=self.compose();root,bones=c.inspect_xml(output,(*self.drivers,*self.p['drivers']),(*self.anchors,self.p['anchor']))
        self.assertEqual(len(bones),15);self.assertEqual(len(root.findall('generic-constraint')),12)
        expected=[c.signature(x) for raw in (self.motion,self.neutral) for x in ET.fromstring(raw)]
        self.assertEqual([c.signature(x) for x in root],expected)

    def test_same_kinematic_anchor_is_deduplicated(self):
        shared=self.mutation(self.neutral,lambda root: [x.set('name','Tails') if x.tag=='bone' and x.get('name')==self.p['anchor']
            else x.set('bodyA','Tails') if x.tag=='generic-constraint' and x.get('bodyA')==self.p['anchor'] else None for x in root])
        combined=self.compose(neutral=shared,anchors=['Tails'])
        self.assertEqual(sum(x.get('name')=='Tails' for x in ET.fromstring(combined).findall('bone')),1)

    def test_dynamic_collision_rejects(self):
        with self.assertRaisesRegex(ValueError,'collision'):
            c.compose_xml(self.motion,self.motion,self.drivers,self.drivers,self.anchors,self.anchors)

    def test_anchor_driver_collision_rejects(self):
        target=self.drivers[0]
        changed=self.mutation(self.neutral,lambda root:[x.set('name',target) if x.tag=='bone' and x.get('name')==self.p['anchor']
            else x.set('bodyA',target) if x.tag=='generic-constraint' and x.get('bodyA')==self.p['anchor'] else None for x in root])
        with self.assertRaisesRegex(ValueError,'collision'):self.compose(neutral=changed,anchors=[target])

    def test_incompatible_shared_anchor_rejects(self):
        root=ET.fromstring(self.neutral);root[0].set('name','Tails');ET.SubElement(root[0],'gravity-factor').text='1'
        root.find('generic-constraint').set('bodyA','Tails')
        with self.assertRaisesRegex(ValueError,'Incompatible'):self.compose(neutral=ET.tostring(root),anchors=['Tails'])

    def test_missing_or_duplicate_bone_rejects(self):
        for change in (lambda root:root.remove(root.find('bone')),lambda root:root.append(copy.deepcopy(root.find('bone')))):
            with self.subTest(change=change),self.assertRaises(ValueError):self.compose(neutral=self.mutation(self.neutral,change))

    def test_missing_duplicate_and_unresolved_constraints_reject(self):
        mutations=[lambda root:root.remove(root.find('generic-constraint')),
            lambda root:root.append(copy.deepcopy(root.find('generic-constraint'))),
            lambda root:root.find('generic-constraint').set('bodyA','foreign-unresolved'),
            lambda root:root.insert(0,root.find('generic-constraint'))]
        for change in mutations:
            with self.subTest(change=change),self.assertRaises(ValueError):self.compose(neutral=self.mutation(self.neutral,change))

    def test_nonfinite_negative_missing_mass_reject(self):
        for value in ('nan','inf','-1',None):
            def change(root):
                bone=root.find('bone');mass=bone.find('mass')
                if value is None:bone.remove(mass)
                else:mass.text=value
            with self.subTest(value=value),self.assertRaises(ValueError):self.compose(neutral=self.mutation(self.neutral,change))

    def test_unknown_collision_and_global_records_reject(self):
        for tag in ('per-vertex-shape','per-triangle-shape','include','default-bone','global'):
            with self.subTest(tag=tag),self.assertRaises(ValueError):
                self.compose(neutral=self.mutation(self.neutral,lambda root:ET.SubElement(root,tag)))

    def test_unknown_duplicate_or_missing_constraint_parameter_reject(self):
        mutations=[lambda root:ET.SubElement(root.find('generic-constraint'),'foreign').__setattr__('text','1'),
            lambda root:root.find('generic-constraint').append(copy.deepcopy(root.find('generic-constraint/linearLowerLimit'))),
            lambda root:root.find('generic-constraint').remove(root.find('generic-constraint/angularStiffness'))]
        for change in mutations:
            with self.subTest(change=change),self.assertRaises(ValueError):self.compose(neutral=self.mutation(self.neutral,change))

    def test_entity_and_malformed_xml_reject(self):
        for bad in (b'<!DOCTYPE system [<!ENTITY a "x">]><system/>',b'<system>',b'<system file="external"/>'):
            with self.subTest(data=bad),self.assertRaises(ValueError):self.compose(neutral=bad)

    def test_female_p1_original_remains_an_independent_eleven_driver_system(self):
        raw=self.fsmp.render_xml(True)
        root,bones=c.inspect_xml(raw,(*self.drivers,*self.fsmp.common.source.BREAST_NODES),
            (*self.anchors,'NPC L PreBreast P1','NPC R PreBreast P1'))
        self.assertEqual(c.digest(raw),c.MOTION_HASHES[True]);self.assertEqual(len(root.findall('generic-constraint')),11)
        self.assertFalse(set(self.p['drivers'])&set(bones))


@unittest.skipUnless(ARGS,'Explicit actual candidate arguments required')
class Actual(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.anatomy,cls.fsmp=c.modules();cls.p=cls.anatomy.load_profile()
        cls.rig,cls.resource,_,cls.api,cls.Patch,cls.Trip,_=cls.anatomy._imports(ARGS.pynifly,ARGS.morphbench)
        cls.source=ARGS.original;cls.target=ARGS.candidate/'candidate';cls.report=json.loads((ARGS.candidate/'build-report.json').read_text())

    def test_only_known_root_hook_block_and_appended_value_string_change(self):
        for name in ('malebodywerewolf_0.nif','malebodywerewolf_1.nif'):
            with self.subTest(name=name):
                old=self.source/c.MESH/name;new=self.target/c.MESH/name
                expected,proof=c.redirect_hook(old.read_bytes(),self.p['xml'],c.XML,self.fsmp.Nif)
                self.assertEqual(new.read_bytes(),expected)
                a,b=[self.fsmp.Nif(x.read_bytes()) for x in (old,new)]
                self.assertEqual(a.blocks[0],b.blocks[0]);self.assertEqual(a.strings,b.strings[:-1])
                self.assertEqual([i for i,x in enumerate(a.blocks) if x!=b.blocks[i]],[proof['hookBlock']])
                self.assertTrue(self.Patch(new).consistent())
                actual=self.api.NifFile(str(new));hook=actual.root.get_extra_data(blockname='NiStringExtraData',name=c.HOOK)
                self.assertEqual(hook.string_data,c.XML)
        expected={c.MESH+'malebodywerewolf_0.nif',c.MESH+'malebodywerewolf_1.nif',c.MESH+'malebodywerewolf.tri',c.XML}
        self.assertEqual(set(self.report['files']),expected)
        self.assertEqual((self.source/c.MESH/'malebodywerewolf.tri').read_bytes(),(self.target/c.MESH/'malebodywerewolf.tri').read_bytes())

    def test_unknown_missing_multiple_shared_or_already_combined_hooks_reject(self):
        raw=(self.source/c.MESH/'malebodywerewolf_0.nif').read_bytes()
        _,proof=c.redirect_hook(raw,self.p['xml'],c.XML,self.fsmp.Nif);hook=proof['hookBlock']
        for case in ('unknown','missing','duplicate','shared','already'):
            nif=self.fsmp.Nif(raw)
            if case in ('unknown','missing'):
                block=bytearray(nif.blocks[hook]);offset=4 if case=='unknown' else 0
                struct.pack_into('<I',block,offset,nif.name('foreign'));nif.blocks[hook]=bytes(block)
            elif case=='duplicate':nif.append('NiStringExtraData',nif.blocks[hook])
            elif case=='shared':
                root=bytearray(nif.blocks[0]);count,=struct.unpack_from('<I',root,4)
                root[8+4*count:8+4*count]=struct.pack('<I',hook);struct.pack_into('<I',root,4,count+1);nif.blocks[0]=bytes(root)
            else:nif.name(c.XML)
            with self.subTest(case=case),self.assertRaises(ValueError):c.redirect_hook(nif.bytes(),self.p['xml'],c.XML,self.fsmp.Nif)

    def test_native_all_driver_skin_support_and_original_fields_exact(self):
        for filename in ('malebodywerewolf_0.nif','malebodywerewolf_1.nif'):
            old,new=[self.api.NifFile(str(path/c.MESH/filename)) for path in (self.source,self.target)]
            support=self.fsmp.common.inspect_body(new,tuple(self.report['combinedDrivers']),filename)
            self.assertEqual(len(support),12)
            self.assertEqual(set(old.nodes),set(new.nodes))
            for a,b in zip(old.shapes,new.shapes):
                self.assertEqual((a.name,a.verts,a.tris,a.uvs,a.normals,a.textures,a.bone_names,a.bone_weights),
                    (b.name,b.verts,b.tris,b.uvs,b.normals,b.textures,b.bone_names,b.bone_weights))
                self.assertTrue(np.array_equal(self.rig.matrix(a.global_to_skin),self.rig.matrix(b.global_to_skin)))
                for bone in a.bone_names:
                    self.assertTrue(np.array_equal(self.rig.matrix(a.get_shape_skin_to_bone(bone)),self.rig.matrix(b.get_shape_skin_to_bone(bone))))
                self.assertEqual(self.resource.bodytri(a),self.resource.bodytri(b))

    def test_actual_morphbench_morphs_and_combined_physics_records(self):
        from morphbench.api import MorphBench
        from morphbench.config import Config
        from presenters.physics_document import parse_document
        cfg=Config(ARGS.report.with_suffix('.settings.json'));cfg.set('pynifly',str(ARGS.pynifly));cfg.set('skeletonFile','')
        proofs={}
        def records(workspace,data):
            document=parse_document('fsmp',data.decode());workspace.physics_replace(document)
            envelope=workspace.physics_envelopes()
            self.assertFalse(envelope['warnings'])
            output={}
            for row in envelope['records']:
                self.assertTrue(row['range_supported'] and row['frame_supported'])
                self.assertTrue(np.isfinite(row['world_origin']).all())
                output[row['body_a'],row['body_b']]={k:row[k] for k in ('body_a','body_b','linear','angular','linear_reference','world_origin','world_axes')}
                output[row['body_a'],row['body_b']]['frameSource']=row['frame']['source']
            return output
        male=self.fsmp.render_xml(False);neutral=self.anatomy.render_xml(self.p);combined=(self.target/c.XML).read_bytes()
        for filename in ('malebodywerewolf_0.nif','malebodywerewolf_1.nif'):
            before,after=MorphBench(cfg),MorphBench(cfg)
            a=before.open(self.source/c.MESH/filename,self.source/c.MESH/'malebodywerewolf.tri',ARGS.skeleton)
            b=after.open(self.target/c.MESH/filename,self.target/c.MESH/'malebodywerewolf.tri',ARGS.skeleton)
            self.assertEqual((a['shapes'],a['vertices'],a['morphs']),(b['shapes'],b['vertices'],b['morphs']))
            self.assertEqual(before.morphs(),after.morphs());self.assertEqual(len(after.morphs()),30)
            for morph in after.morphs():before.set_slider(morph,.5);after.set_slider(morph,.5)
            for shape in after.shapes():self.assertTrue(np.array_equal(before.deformed(shape['name']),after.deformed(shape['name'])))
            originals=records(after,male);originals.update(records(after,neutral));actual=records(after,combined)
            self.assertEqual(len(actual),12);self.assertEqual(actual,originals)
            proofs[filename]={'summary':b,'all30MorphHalfCombinationAllShapeArraysExact':True,'combinedConfiguredRecords':list(actual.values()),
                'allOriginalComponentLimitsAndFramesExact':True,'scope':'Actual facade import/rest-frame nominal ranges; no solver or motion simulation.'}
        self.__class__.facade_proofs=proofs


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','original','skeleton','pynifly','morphbench','report'):parser.add_argument('--'+name,type=Path,required=True)
    ARGS=parser.parse_args()
    if ARGS.report.exists():raise ValueError('Use a new test report path')
    # Discovery skips optional native tests. Explicit CLI arguments enable them.
    Actual.__unittest_skip__=False
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(Pure),unittest.defaultTestLoader.loadTestsFromTestCase(Actual)])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    roots=[REPO.resolve(),ARGS.pynifly.resolve(),ARGS.morphbench.resolve()]
    loaded={}
    for module in tuple(sys.modules.values()):
        filename=getattr(module,'__file__',None)
        if not filename:continue
        path=Path(filename).resolve()
        if path.suffix=='.py' and path.is_file() and any(root==path or root in path.parents for root in roots):
            loaded[str(path)]=c.digest(path.read_bytes())
    ARGS.report.write_text(json.dumps({'passed':result.wasSuccessful(),'testsRun':result.testsRun,'failures':len(result.failures),
        'errors':len(result.errors),'skipped':len(result.skipped),'facade':getattr(Actual,'facade_proofs',{}),
        'loadedSourcePins':loaded,'numpyVersion':np.__version__,
        'scope':'Offline XML/native file/public Physics facade only; no solver, installation or game.'},indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful())
