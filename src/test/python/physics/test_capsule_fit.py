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

PATH=(Path(__file__).resolve().parents[4] / 'src/main/python/physics')/"fit-capsules.py"
SPEC=importlib.util.spec_from_file_location("claw_capsule_fit",PATH)
fit=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(fit)


def cylinder():
    angles=np.linspace(0,2*np.pi,32,endpoint=False)
    return np.asarray([[2*np.cos(a),2*np.sin(a),z] for z in np.linspace(-5,5,8) for a in angles])


class CapsuleFitTests(unittest.TestCase):
    def test_declared_attachment_uses_actual_names_and_ancestry_not_bracket_guess(self):
        root=SimpleNamespace(name='Root',parent=None)
        alias=SimpleNamespace(name='NPC L UpperArm [RUar]',parent=root)
        canonical=SimpleNamespace(name='NPC L UpperArm [LUar]',parent=alias)
        twist=SimpleNamespace(name='Twist',parent=canonical)
        skeleton=SimpleNamespace(nodes={node.name:node for node in (root,alias,canonical,twist)})
        recipe=[{'node':alias.name,'count':2,'sexMask':'both'}]
        measured=fit.measured_support_regions(recipe,skeleton)
        self.assertEqual(measured,[dict(recipe[0],ancestry=[alias.name,'Root'])])
        self.assertEqual(fit.nearest_region_bone('Twist',skeleton,(alias.name,)),alias.name)
        with self.assertRaisesRegex(ValueError,'no selected coarse ancestor'):
            fit.nearest_region_bone(alias.name,skeleton,(canonical.name,))
        with self.assertRaisesRegex(ValueError,'missing from XP32'):
            fit.measured_support_regions([dict(recipe[0],node='Missing')],skeleton)
        root.parent=twist
        with self.assertRaisesRegex(ValueError,'Cycle'):
            fit.measured_support_regions(recipe,skeleton)

    def test_whole_body_keeps_full_seam_faces_and_only_actual_claw_fields(self):
        def transform():return SimpleNamespace(rotation=np.eye(3),scale=1.,translation=[0,0,0])
        root=SimpleNamespace(name='Root',parent=None,global_transform=transform())
        hand=SimpleNamespace(name='Hand',parent=root,global_transform=transform())
        digit=SimpleNamespace(name='Finger',parent=hand,global_transform=transform())
        other=SimpleNamespace(name='Other',parent=root,global_transform=transform())
        shape=SimpleNamespace(name='claws',verts=[[0,0,0],[1,0,0],[0,1,0],[1,1,0]],tris=[[0,1,2],[1,2,3]],
            global_to_skin=transform(),bone_weights={'Finger':[(0,.49),(1,.1),(2,.1),(3,.1)],
                'Other':[(0,.51),(1,.9),(2,.9),(3,.9)]},get_shape_skin_to_bone=lambda _:transform())
        skeleton=SimpleNamespace(nodes={node.name:node for node in (root,hand,digit,other)})
        records={('claws','CLAWArmClawLong',2):SimpleNamespace(packed=[2,0,0],scale=.5),
                 ('claws','CLAWZero',1):SimpleNamespace(packed=[0,0,0],scale=1.)}
        # No vertex is directly bound to either selected ancestor: the old
        # regional threshold selects nothing, although every face deforms.
        self.assertEqual(fit.triangle_regions(shape,skeleton,records,('Hand','Root')), {})
        rows=fit.triangle_regions(shape,skeleton,records,('Hand','Root'),whole_body=True)
        points,fields,source=rows['Root']
        self.assertEqual(source['sourceTriangleIndices'],[0,1])
        self.assertEqual(source['vertices'],[0,1,2,3])
        self.assertEqual(source['fullRegionTriangles'],shape.tris)
        self.assertEqual(source['boundaryTrianglesExcluded'],0)
        self.assertEqual(source['skinBoneRegionAncestry'],{'Finger':'Hand','Other':'Root'})
        self.assertEqual(set(fields),{'CLAWArmClawLong'})
        np.testing.assert_array_equal(fields['CLAWArmClawLong'],[[0,0,0],[0,0,0],[1,0,0],[0,0,0]])
        with self.assertRaisesRegex(ValueError,'no selected coarse ancestor'):
            fit.triangle_regions(shape,skeleton,records,('Hand',),whole_body=True)

    def test_whole_body_preserves_positive_minority_p1_priority(self):
        def transform(x=0):return SimpleNamespace(rotation=np.eye(3),scale=1.,translation=[x,0,0])
        root=SimpleNamespace(name='Torso',parent=None,global_transform=transform())
        name=fit.P1_NODES[0];p1=SimpleNamespace(name=name,parent=root,global_transform=transform(2))
        shape=SimpleNamespace(name='body',verts=[[1,0,0],[2,0,0],[1,1,0]],tris=[[0,1,2]],global_to_skin=transform(),
            bone_weights={name:[(0,.03),(1,.03),(2,.03)],'Torso':[(0,.97),(1,.97),(2,.97)]},get_shape_skin_to_bone=lambda _:transform())
        skeleton=SimpleNamespace(nodes={name:p1,'Torso':root})
        rows=fit.triangle_regions(shape,skeleton,{},('Torso',name),whole_body=True)
        self.assertEqual(set(rows),{name})
        self.assertEqual(rows[name][2]['sourceTriangleIndices'],[0])

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

    def test_declared_partition_override_uses_arbitrary_node_and_sex_mask(self):
        node='Measured Limb [New]'
        rows=[{'node':node,'count':2,'sexMask':'both'},
              {'node':'Measured Chest','count':1,'sexMask':'female'}]
        selected={'male/'+node:'strips-0','female/'+node:'compact-extreme',
                  'female/Measured Chest':'strips-2'}
        self.assertEqual(fit.partition_overrides(selected,rows),selected)
        self.assertIsNot(fit.partition_overrides(selected,rows),selected)
        for key in ('male/Measured Chest','female/Undeclared','other/'+node):
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'exact sex/node'):
                fit.partition_overrides({key:'compact'},rows)
        # Explicit declarations do not widen the historical default path.
        with self.assertRaisesRegex(ValueError,'exact sex/node'):
            fit.partition_overrides({'male/'+node:'compact'})

    def test_declared_partition_override_validates_the_support_declaration(self):
        row={'node':'Measured Limb','count':1,'sexMask':'both'}
        for invalid in ([row,row],[dict(row,count=True)],[dict(row,sexMask='male')]):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                fit.partition_overrides({},invalid)

    def test_coarse_recipe_override_is_validated_after_profile_and_regions(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);recipe=root/'recipe.json';nif=root/'input.nif'
            nif.write_bytes(b'fixture')
            recipe.write_text(json.dumps({'schemaVersion':1,'weightDomain':[0.,1.],'morphDomain':[0.,1.],
                'supportProfile':fit._settings_module.COARSE_PROFILE,
                'supportRegions':[{'node':'Measured Limb','count':1,'sexMask':'both'}],
                'partitionOverrides':{'male/Measured Limb':'strips-0'}}))
            argv=['--current-vector','--contact-recipe',str(recipe),'--out',str(root/'out'),'--skeleton',str(nif)]
            for sex in ('male','female'):
                for suffix in ('nif','tri'):argv.extend(['--'+sex+'-'+suffix,str(nif)])
            errors=io.StringIO()
            with patch.dict(sys.modules,{'breast_rig':SimpleNamespace(), 'tri_patch':SimpleNamespace()}):
                with patch.object(sys.modules['breast_rig'],'load_pynifly',create=True,
                                  side_effect=ValueError('stopped after valid recipe')) as admit,redirect_stderr(errors):
                    self.assertEqual(fit.main(argv),2)
            admit.assert_called_once()
            self.assertIn('stopped after valid recipe',errors.getvalue())
            self.assertNotIn('exact sex/node',errors.getvalue())
            self.assertFalse((root/'out').exists())

    def test_declared_override_still_requires_actual_generated_region(self):
        node='Measured Limb';unused='Measured Empty'
        root=SimpleNamespace(name=node,parent=None)
        skeleton=SimpleNamespace(nodes={node:root,unused:SimpleNamespace(name=unused,parent=root)})
        points=np.asarray([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]])
        faces=[[0,1,2]]
        selected={node:(points,{}, {'vertices':[0,1,2],'fullRegionTriangles':faces,
            'sourceTriangleIndices':[0],'restLBSMatricesSha256':'a'*64})}
        args=SimpleNamespace(support_profile=fit._settings_module.COARSE_PROFILE,
            support_regions=[{'node':name,'count':1,'sexMask':'both'} for name in (node,unused)],
            current_counts=None,contact_passes=0,solid_tail=False,
            partition_overrides={'female/'+unused:'compact-extreme'},
            male_nif=Path('male.nif'),female_nif=Path('female.nif'),male_nif_1=None,female_nif_1=None,
            skeleton=Path('skeleton.nif'),skin_shapes='skin',tail_axis='pca',partition_method='compact',
            fixture_set='compact',signed_diagnostics=False,require_distinct_weight_endpoints=False)
        mesh=SimpleNamespace(shape_dict={'skin':SimpleNamespace(tris=faces)})
        api=SimpleNamespace(NifFile=lambda _:mesh)
        contact=SimpleNamespace(partitions=lambda *args:([list(range(3))],[[0]]))
        with (patch.object(fit,'triangle_regions',return_value=selected),
              patch.dict(sys.modules,{'contact_fit':contact})):
            with self.assertRaisesRegex(ValueError,'without actual selected support'):
                fit.build_current(args,api,{'male':{},'female':{}},skeleton,
                                  {args.skeleton.resolve():b'fixture'},Path('unused'))

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
