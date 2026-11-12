"""Focused pure + actual resource/facade checks; no host, renderer or game."""
from pathlib import Path
import argparse
import importlib.util
import json
import sys
import unittest
import xml.etree.ElementTree as ET
import numpy as np

REPO=Path(__file__).resolve().parents[4]
FILE=REPO/'src/main/components/adult-anatomy/python/build.py'
spec=importlib.util.spec_from_file_location('claw_neutral_anatomy',FILE)
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
ARGS=None


class Pure(unittest.TestCase):
    def vertices(self):
        p=builder.load_profile();v=np.zeros((p['vertices'],3));nt=p['tubeVertices'];nb=p['ballVerticesEach']
        v[:nt,1]=np.linspace(-8,6,nt);v[nt:nt+nb,0]=-2;v[nt+nb:,0]=2
        return p,v

    def test_fixed_attachment_and_normalized_skin(self):
        p,v=self.vertices();names,w=builder.plan_weights(v,p)
        self.assertEqual(names,[p['root'],*p['drivers']])
        self.assertTrue(np.array_equal(w.sum(axis=1),np.ones(len(v))))
        self.assertTrue(np.all(w[v[:,1]<=1][:p['tubeVertices'],0]>=.65))
        self.assertTrue(np.all(w[:p['tubeVertices']][v[:p['tubeVertices'],1]<=1,0]==1))
        self.assertLessEqual(int((w>0).sum(axis=1).max()),2)
        self.assertTrue(np.any(w[:,1:]));self.assertTrue(np.isfinite(w).all())

    def test_invalid_vertices_and_bilateral_order_reject(self):
        p,v=self.vertices()
        for bad in (v[:-1],np.full(v.shape,np.nan),v*np.array([-1,1,1])):
            with self.assertRaises(ValueError):builder.plan_weights(bad,p)

    def test_xml_has_only_declared_neutral_bones(self):
        p,_=self.vertices();root=ET.fromstring(builder.render_xml(p))
        bones=root.findall('bone');self.assertEqual([b.get('name') for b in bones],[p['anchor'],*p['drivers']])
        self.assertEqual(bones[0].findtext('mass'),'0')
        self.assertEqual([(j.get('bodyA'),j.get('bodyB')) for j in root.findall('generic-constraint')],
            [(p['anchor'],p['drivers'][0]),(p['drivers'][0],p['drivers'][1]),(p['drivers'][0],p['drivers'][2])])
        self.assertFalse(root.findall('per-vertex-shape')+root.findall('per-triangle-shape'))
        self.assertNotIn('WWD 3',builder.render_xml(p).decode())
        for joint in root.findall('generic-constraint'):
            self.assertEqual(joint.find('frameInB/basis').attrib,dict(x='0',y='0',z='0',w='1'))
            self.assertEqual(joint.find('frameInB/origin').attrib,dict(x='0',y='0',z='0'))
            self.assertEqual(joint.findtext('useLinearReferenceFrameA'),'false')


class Actual(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p=builder.load_profile();cls.root=ARGS.candidate/'candidate';cls.mesh=cls.root/'Meshes/Actors/WerewolfBeast/Character Assets'
        cls.rig,cls.resource,cls.fsmp,cls.api,cls.NifPatch,cls.TripFile,_=builder._imports(ARGS.pynifly,ARGS.morphbench)

    def test_input_and_tri_pins_and_minimal_payload(self):
        expected={'Meshes/Actors/WerewolfBeast/Character Assets/'+n for n in self.p['inputs'] if n!='skeleton.nif'}|{self.p['xml']}
        actual={str(p.relative_to(self.root)).replace('\\','/') for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(actual,expected)
        self.assertEqual(builder.sha(self.mesh/'malebodywerewolf.tri'),self.p['inputs']['malebodywerewolf.tri'])
        for name,digest in self.p['inputs'].items():
            path=ARGS.skeleton if name=='skeleton.nif' else ARGS.body_root/name
            self.assertEqual(builder.sha(path),digest)

    def test_existing_hook_refused_without_changes(self):
        path=self.mesh/'malebodywerewolf_0.nif';raw=path.read_bytes();before=builder.sha(path)
        with self.assertRaisesRegex(ValueError,'already has an FSMP binding'):self.fsmp.bind_nif(raw,self.p['xml'])
        self.assertEqual(builder.sha(path),before)

    def test_only_three_new_sphere_radii_differ_from_frozen03(self):
        import skin_bounds
        import head_split
        for filename in ('malebodywerewolf_0.nif','malebodywerewolf_1.nif'):
            old=ARGS.previous/'candidate/Meshes/Actors/WerewolfBeast/Character Assets'/filename;new=self.mesh/filename
            before,after=old.read_bytes(),new.read_bytes();table=self.NifPatch(old)
            shapes=[next(s for s in self.api.NifFile(str(path)).shapes if s.name==self.p['shape']) for path in (old,new)]
            a,b=[skin_bounds.records(self.fsmp.Nif(raw),s,head_split.Reader) for raw,s in zip((before,after),shapes)]
            ledger=[]
            for name in self.p['drivers']:
                block,offset,sphere=a[name];_,_,expanded=b[name]
                self.assertTrue(np.array_equal(sphere[:3],expanded[:3]));self.assertGreater(expanded[3],sphere[3])
                ledger.append({'offset':table.offsets[block]+offset,'oldSphere':sphere.tolist(),'newSphere':expanded.tolist()})
            self.assertEqual(after,skin_bounds.bounds.patch_spheres(before,ledger))
            self.assertTrue(np.array_equal(a[self.p['root']][2],b[self.p['root']][2]))

    def test_morphbench_actual_public_facade(self):
        from morphbench.api import MorphBench
        from morphbench.config import Config
        from presenters.physics_document import parse_document
        cfg=Config(ARGS.report.with_suffix('.morphbench-settings.json'));cfg.set('pynifly',str(ARGS.pynifly));cfg.set('skeletonFile','')
        proof={}
        for filename in ('malebodywerewolf_0.nif','malebodywerewolf_1.nif'):
            original,current=MorphBench(cfg),MorphBench(cfg)
            before=original.open(ARGS.body_root/filename,ARGS.body_root/'malebodywerewolf.tri',skeleton='')
            after=current.open(self.mesh/filename,self.mesh/'malebodywerewolf.tri',ARGS.skeleton)
            self.assertEqual((before['shapes'],before['vertices'],before['morphs']),(after['shapes'],after['vertices'],after['morphs']))
            self.assertEqual(after['shapes'],16);self.assertEqual(after['morphs'],30)
            self.assertEqual(original.morphs(),current.morphs());self.assertFalse(any('Crotch' in x for x in current.morphs()))
            for morph in current.morphs():
                original.set_slider(morph,.5);current.set_slider(morph,.5)
            for shape in current.shapes():
                name=shape['name'];a=original.deformed(name);b=current.deformed(name)
                self.assertTrue(np.isfinite(b).all());self.assertTrue(np.array_equal(a,b),name)
            self.assertTrue(set(self.p['requiredNodes'])<=set(current.slots_anchors()))
            self.assertIn('genitals',current.visible_shapes())
            document=parse_document('fsmp',(self.root/self.p['xml']).read_text())
            current.physics_replace(document);envelopes=current.physics_envelopes()
            self.assertEqual(len(envelopes['records']),3)
            for record in envelopes['records']:
                self.assertTrue(record['range_supported'] and record['frame_supported'])
                self.assertEqual(record['linear_reference'],'B')
                self.assertEqual(record['frame']['source'],'frameInB')
                self.assertTrue(np.isfinite(record['world_origin']).all())
                for kind,limit in [('linear',self.p['motion']['linearLimit']),('angular',self.p['motion']['angularLimitRadians'])]:
                    self.assertEqual([(x['lower'],x['upper'],x['status']) for x in record[kind]],[(-limit,limit,'limited')]*3)
            proof[filename]={'summary':after,'all30MorphsHalfCombinedPreserved':True,'all16ShapeDeformedArraysExact':True,'actualSkeletonAnchorsPresent':True,'fileVisibleInFacade':True,'physicsImport':envelopes}
        self.__class__.facade_proof=proof


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','previous','body-root','skeleton','pynifly','morphbench','report'):parser.add_argument('--'+name,type=Path,required=True)
    ARGS=parser.parse_args()
    if ARGS.report.exists():raise ValueError('Use a new test report path')
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(Pure),unittest.defaultTestLoader.loadTestsFromTestCase(Actual)])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    ARGS.report.write_text(json.dumps({'passed':result.wasSuccessful(),'testsRun':result.testsRun,'errors':len(result.errors),'failures':len(result.failures),'actualFacade':getattr(Actual,'facade_proof',{}),'scope':'Pure rules + actual native resources/public Morphbench facade; no physics simulation/game/rendering.'},indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful())
