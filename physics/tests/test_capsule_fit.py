import importlib.util
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import redirect_stderr
import io
import json
import sys
import numpy as np

PATH=Path(__file__).resolve().parents[1]/"fit-capsules.py"
SPEC=importlib.util.spec_from_file_location("claw_capsule_fit",PATH)
fit=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(fit)


def cylinder():
    angles=np.linspace(0,2*np.pi,32,endpoint=False)
    return np.asarray([[2*np.cos(a),2*np.sin(a),z] for z in np.linspace(-5,5,8) for a in angles])


class CapsuleFitTests(unittest.TestCase):
    def test_recipe_change_between_parse_and_snapshot_cannot_attest_other_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);recipe=root/'recipe.json';nif=root/'input.nif';addon=root/'addon';out=root/'out'
            (addon/'pyn').mkdir(parents=True)
            (addon/'NiflyDLL.dll').write_bytes(b'fixture')
            (addon/'pyn/pynifly.py').write_bytes(b'fixture')
            nif.write_bytes(b'fixture')
            parsed=json.dumps({'schemaVersion':1,'weightDomain':[0.,1.],'morphDomain':[0.,1.],
                'partitionOverrides':{'female/NPC EarR [EarR]Bone01':'compact-extreme'}}).encode()
            recipe.write_bytes(parsed)
            def admit(_):
                # PyNifly admission occurs after option parsing and before the
                # source snapshot. Even semantically equal replacement bytes
                # cannot be attributed to the already parsed source document.
                recipe.write_bytes(parsed+b'\n')
                return SimpleNamespace(),None,addon
            argv=['--current-vector','--contact-recipe',str(recipe),'--out',str(out),'--skeleton',str(nif)]
            for sex in ('male','female'):
                for suffix in ('nif','tri'):argv.extend(['--'+sex+'-'+suffix,str(nif)])
            errors=io.StringIO()
            with patch.dict(sys.modules,{'breast_rig':SimpleNamespace(load_pynifly=admit),'tri_patch':SimpleNamespace()}),redirect_stderr(errors):
                result=fit.main(argv)
            self.assertEqual(result,2)
            self.assertIn('Contact recipe changed since its options were parsed',errors.getvalue())
            self.assertFalse(out.exists())

    def test_partition_overrides_are_explicit_sex_node_methods(self):
        selected={'female/NPC EarR [EarR]Bone01':'compact-extreme'}
        self.assertEqual(fit.partition_overrides(selected),selected)
        self.assertIsNot(fit.partition_overrides(selected),selected)
        for value in (None,[],{'female/EarR':'compact-extreme'},
                      {'male/NPC L Breast P1':'compact-extreme'},
                      {'female/NPC EarR [EarR]Bone01':'auto'},
                      {'female/NPC EarR [EarR]Bone01':True}):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'exact sex/node'):
                fit.partition_overrides(value)

    def test_minority_p1_mobility_support_is_not_lost_by_dominant_threshold(self):
        def transform(x=0):return SimpleNamespace(rotation=np.eye(3),scale=1.,translation=[x,0,0])
        node=fit.P1_NODES[0];other='NPC Head [Head]'
        shape=SimpleNamespace(name='head',verts=[[1,0,0],[2,0,0],[1,1,0]],tris=[[0,1,2]],
            global_to_skin=transform(),bone_weights={node:[(0,.3),(1,.3),(2,.3)],other:[(0,.7),(1,.7),(2,.7)]},
            get_shape_skin_to_bone=lambda _:transform())
        skeleton=SimpleNamespace(nodes={node:SimpleNamespace(global_transform=transform(2)),other:SimpleNamespace(global_transform=transform())})
        result=fit.triangle_regions(shape,skeleton,{},nodes=fit.NODES+fit.P1_NODES)
        self.assertEqual(result[node][2]['fullRegionTriangles'],[[0,1,2]])
        self.assertEqual(result[node][2]['selectionRule'],'actual positive side-matched minority P1 skin support')
        self.assertTrue(np.allclose(result[node][0][:,0],[-.4,.6,-.4]))

    def test_mixed_face_retains_all_three_full_lbs_vertices_and_actual_delta(self):
        def transform(z=0):return SimpleNamespace(rotation=np.eye(3),scale=1.,translation=[0,0,z])
        node='TailBone03';other='NPC Head [Head]'
        shape=SimpleNamespace(name='body',verts=[[0,0,0],[1,0,0],[0,1,0],[1,1,0]],
            tris=[[0,1,2],[1,2,3]],global_to_skin=transform(),
            bone_weights={node:[(0,.6),(1,.2),(2,.4)],other:[(0,.4),(1,.8),(2,.6),(3,1.)]},
            get_shape_skin_to_bone=lambda _:transform())
        skeleton=SimpleNamespace(nodes={node:SimpleNamespace(global_transform=transform(10)),other:SimpleNamespace(global_transform=transform())})
        rows=fit.triangle_regions(shape,skeleton,{('body','grow',2):SimpleNamespace(packed=[1,0,0],scale=1.)})
        points,deltas,source=rows[node]
        self.assertEqual(source['vertices'],[0,1,2])
        self.assertEqual(source['fullRegionTriangles'],[[0,1,2]])
        self.assertEqual(source['boundaryTrianglesExcluded'],0)
        self.assertEqual(source['mixedOwnershipTrianglesIncluded'],1)
        self.assertTrue(np.allclose(points[:,2],[-4,-8,-6]))
        self.assertTrue(np.allclose(deltas['grow'],[[0,0,0],[0,0,0],[1,0,0]]))

    def test_encloses_every_vertex_and_survives_two_morph_mixtures(self):
        points=cylinder()
        stretch=points*np.array([.3,.3,.5])
        tilt=np.column_stack([points[:,2]*.35,np.zeros(len(points)),np.zeros(len(points))])
        model=fit.fit(points,{"size":stretch,"tilt":tilt})
        self.assertEqual(model["verification"]["cornerCount"],4)
        for a in np.linspace(0,1,11):
            for b in np.linspace(0,1,11):
                cap=fit.evaluate(model,{"size":float(a),"tilt":float(b)})
                self.assertLessEqual(fit.distance(points+a*stretch+b*tilt,**cap).max(),1e-8)

    def test_shrink_reduces_radius_and_return_to_zero_is_exact(self):
        points=cylinder(); delta=points*np.array([-.4,-.4,-.2])
        model=fit.fit(points,{"shrink":delta})
        low=fit.evaluate(model,{"shrink":0.}); high=fit.evaluate(model,{"shrink":1.})
        self.assertLess(high["radius"],low["radius"]*.7)
        self.assertLess(np.linalg.norm(high["p2"]-high["p1"]),np.linalg.norm(low["p2"]-low["p1"]))
        for key in low: self.assertTrue(np.array_equal(low[key],model["base"][key]))

    def test_all_corner_proof_works_for_signed_affine_size_contributions(self):
        p=cylinder(); grow=p*np.array([.2,.2,.3]); shrink=p*np.array([-.3,-.3,-.2])
        model=fit.fit(p,{"grow":grow,"shrink":shrink})
        self.assertLess(model["coefficients"]["shrink"]["radius"],0.)
        rng=np.random.default_rng(7)
        for a,b in rng.random((100,2)):
            cap=fit.evaluate(model,{"grow":float(a),"shrink":float(b)})
            self.assertLessEqual(fit.distance(p+a*grow+b*shrink,**cap).max(),1e-8)

    def test_rejects_unknown_out_of_domain_and_nonfinite_coefficients(self):
        model=fit.fit(cylinder(),{"size":cylinder()*.2})
        for values in ({"unknown":0.},{"size":-1e-8},{"size":1.00001},{"size":float('nan')},{"size":True}):
            with self.subTest(values=values),self.assertRaises(ValueError): fit.evaluate(model,values)

    def test_rejects_malformed_degenerate_and_excessive_support(self):
        for points,deltas in (([[0,0,0]]*4,{}),([[float('inf'),0,0]]*5,{}),
                              (cylinder(),{"a":np.zeros((4,3))}),
                              (cylinder(),{str(i):cylinder()*.1 for i in range(9)})):
            with self.subTest(n=len(deltas)),self.assertRaises(ValueError): fit.fit(points,deltas)

    def test_neutral_only_model_is_measured_not_fabricated(self):
        p=cylinder(); model=fit.fit(p,{})
        self.assertEqual(model["coefficients"],{})
        self.assertEqual(model["verification"]["cornerCount"],1)
        self.assertLessEqual(fit.distance(p,**fit.evaluate(model,{})).max(),1e-8)

    def test_turning_endpoint_model_encloses_rotating_skin_at_interior_values(self):
        p=cylinder(); turn=np.column_stack([p[:,2]*.7,np.zeros(len(p)),-p[:,0]*.7])
        model=fit.fit(p,{"turn":turn})
        baseline=np.asarray(model["base"]["p2"])-model["base"]["p1"]
        moved=fit.evaluate(model,{"turn":1.})
        self.assertGreater(np.linalg.norm(np.cross(baseline,moved["p2"]-moved["p1"])),1.)
        for v in np.linspace(0,1,21):
            self.assertLessEqual(fit.distance(p+v*turn,**fit.evaluate(model,{"turn":float(v)})).max(),1e-8)

    def test_bundle_assigns_complete_triangles_to_one_capsule_for_all_mixtures(self):
        p=cylinder(); triangles=np.asarray([[i,i+1,i+32] for i in range(31)])
        delta=p*np.array([.3,.1,.2])
        models,_=fit.fit_bundle(p,{"grow":delta},4,triangles)
        assigned=[]
        for model in models:
            assigned.extend(model["triangleIndices"])
            self.assertTrue(set(triangles[model["triangleIndices"]].reshape(-1)).issubset(model["partitionIndices"]))
            for value in [0.,.37,1.]:
                cap=fit.evaluate(model,{"grow":value})
                for face in triangles[model["triangleIndices"]]:
                    for a,b in [(0.,0.),(.2,.3),(.7,.1),(0.,1.)]:
                        point=(p[face]+value*delta[face]).T@np.array([a,b,1-a-b])
                        self.assertLessEqual(fit.distance([point],**cap).max(),1e-8)
        self.assertEqual(sorted(assigned),list(range(len(triangles))))

    def test_bundle_refuses_invalid_counts_and_triangle_indices(self):
        for count,faces in [(0,None),(9,None),(2,[[0,1,9999]])]:
            with self.subTest(count=count),self.assertRaises(ValueError):fit.fit_bundle(cylinder(),{},count,faces)

    def test_output_safety_refuses_existing_source_and_live_destinations(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for target in (root,PATH.parent/"not-allowed",root/"mods"/"candidate",root/"Data"/"candidate"):
                with self.subTest(target=target),self.assertRaises(ValueError): fit.safe_output(target,[PATH])
            self.assertEqual(fit.safe_output(root/"new",[PATH]),(root/"new").resolve())


if __name__=="__main__":unittest.main()
