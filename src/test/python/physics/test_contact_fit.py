"""Numeric regressions for actual current-state surface fitting; no engine."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np

SPEC=importlib.util.spec_from_file_location('contact_fit',(Path(__file__).resolve().parents[4] / 'src/main/python/physics')/'contact_fit.py')
contact=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(contact)


class ContactFitTests(unittest.TestCase):
    def test_explicit_extreme_seed_keeps_complete_faces_and_stable_tie_order(self):
        points=np.asarray([[x,y,0.] for x in (-4.,-3.,0.,3.,4.) for y in (0.,1.,2.)])
        faces=np.asarray([[3*i,3*i+1,3*i+2] for i in range(5)])
        historical=contact.partitions(points,faces,2)
        self.assertEqual(historical,contact.partitions(points,faces,2,'compact'))
        first=contact.partitions(points,faces,2,'compact-extreme')
        self.assertEqual(first,contact.partitions(points,faces,2,'compact-extreme'))
        self.assertEqual(sorted(index for group in first[1] for index in group),list(range(len(faces))))
        for vertices,group in zip(*first):
            self.assertEqual(vertices,np.unique(faces[group]).tolist())
        # Equal farthest ends use the first stable face index, so this symmetric
        # fixture retains the historical left-first capsule order.
        self.assertEqual(first,historical)
        # Reorder a unique farthest face: the geometric result follows that
        # extreme, and triangle references still address the supplied storage.
        points[12:,0]=8.
        groups,triangles=contact.partitions(points,faces,2,'compact-extreme')
        self.assertIn(4,triangles[0])
        self.assertEqual(sorted(i for row in triangles for i in row),list(range(5)))

    def test_near_sphere_surface_has_stable_axis_parameterization(self):
        sphere={'p1':[0.,0.,0.],'p2':[0.,0.,0.],'radius':2.}
        almost={'p1':[0.,0.,0.],'p2':[1e-14,-1e-14,0.],'radius':2.}
        self.assertTrue(np.allclose(contact.objective_surface(sphere),contact.objective_surface(almost),atol=1e-12,rtol=0))

    def test_near_equal_direction_components_keep_ordered_surface_frame(self):
        first={'p1':[0.,0.,0.],'p2':[1.,-1.,1.],'radius':2.}
        second={'p1':[0.,0.,0.],'p2':[1.-2e-15,-1.,1.+1e-15],'radius':2.}
        self.assertTrue(np.allclose(contact.objective_surface(first),contact.objective_surface(second),atol=1e-12,rtol=0))

    def test_prescribed_direction_is_refused_by_contact_optimization(self):
        model={'points':[[0,0,0],[1,0,0],[0,1,0]],'morphs':[],'deltas':{},'partitions':[[0,1,2]],
            'faces':[[0,1,2]],'triangleGroups':[[0]],'axisHints':[[1,0,0]],'contactPasses':3}
        with self.assertRaisesRegex(ValueError,'Prescribed-axis'):contact.evaluate(model,{})

    def test_independent_weight_interpolates_points_without_scaling_absolute_tri(self):
        model={'morphs':['x'],'points':[[0,0,0],[0,0,2]],'weightDeltas':[[2,0,0],[2,0,2]],
               'deltas':{'x':[[0,3,0],[0,3,0]]},'partitions':[[0,1]]}
        self.assertTrue(np.array_equal(contact.deform(model,{'x':1},0),[[0,3,0],[0,3,2]]))
        self.assertTrue(np.array_equal(contact.deform(model,{'x':1},.5),[[1,3,0],[1,3,3]]))
        self.assertTrue(np.array_equal(contact.deform(model,{'x':1},1),[[2,3,0],[2,3,4]]))
        for weight in [True,-.01,1.01,float('nan'),'1']:
            with self.subTest(weight=weight),self.assertRaises(ValueError):contact.deform(model,{},weight)

    def test_symmetric_contact_objective_improves_flat_patch_without_hiding_undercoverage(self):
        points=np.array([[-2,-1,0],[-2,1,0],[2,-1,0],[2,1,0]],float);faces=[[0,1,2],[1,2,3]]
        before=contact.surface_metrics(points,faces,[contact.capsule(points)])
        cap=contact.contact_capsule(points,faces,passes=3)
        after=contact.surface_metrics(points,faces,[cap])
        self.assertLess(after['capsuleToSkinP95'],before['capsuleToSkinP95'])
        self.assertGreater(after['skinOutsideFraction'],0.)
        self.assertLess(after['skinOutsideMaxSampled'],.8)
        self.assertLess(max(after['skinOutsideMaxSampled'],after['capsuleToSkinMaxSampled']),
                        max(before['skinOutsideMaxSampled'],before['capsuleToSkinMaxSampled']))

    def test_exact_triangle_interior_edge_and_degenerate_distance(self):
        triangle=[[[0,0,0],[4,0,0],[0,4,0]]]
        # A nearest-vertex approximation would report sqrt(6), rather than 2.
        self.assertTrue(np.allclose(contact.triangle_distance([[1,1,2],[3,3,0],[-2,-2,0]],triangle),[2,np.sqrt(2),np.sqrt(8)]))
        self.assertTrue(np.allclose(contact.triangle_distance([[1,2,0]],[[[0,0,0],[2,0,0],[2,0,0]]]),[2]))

    def test_current_fit_contract_covers_full_triangles_in_grow_shrink_and_mix(self):
        p=np.asarray([[x,y,z] for x in [-2,2] for y in [-1,1] for z in [-5,5]],float)
        faces=[[0,1,3],[0,3,2],[4,6,7],[4,7,5],[0,4,5],[0,5,1]]
        groups,triangles=contact.partitions(p,faces,3)
        model={'points':p.tolist(),'morphs':['grow','shrink','turn'],
            'deltas':{'grow':(p*np.array([.4,.3,.2])).tolist(),
                      'shrink':(p*np.array([-.3,-.2,-.4])).tolist(),
                      'turn':np.column_stack([p[:,2]*.3,np.zeros(len(p)),-p[:,0]*.3]).tolist()},'partitions':groups}
        neutral=contact.evaluate(model,{})
        for a,b,c in np.random.default_rng(16).random((30,3)):
            values={'grow':a,'shrink':b,'turn':c};moved=contact.deform(model,values);caps=contact.evaluate(model,values)
            for ids,cap in zip(triangles,caps):
                for weights in [[1,0,0],[.2,.3,.5],[.1,.8,.1]]:
                    sample=np.asarray([weights@moved[np.asarray(faces)[i]] for i in ids])
                    self.assertLessEqual(contact.signed_capsules(sample,[cap]).max(),1e-9)
        self.assertEqual(neutral,contact.evaluate(model,{}))
        shrink=contact.evaluate(model,{'shrink':1})
        self.assertLess(sum(c['radius'] for c in shrink),sum(c['radius'] for c in neutral))
        self.assertEqual(sorted(i for group in triangles for i in group),list(range(len(faces))))

    def test_current_fit_refuses_unknown_nonfinite_out_of_domain_boolean(self):
        model={'morphs':['x'],'points':[[0,0,0],[0,0,2]],'deltas':{},'partitions':[[0,1]]}
        for values in [{'y':0},{'x':True},{'x':float('inf')},{'x':-.01},{'x':1.01}]:
            with self.subTest(values=values),self.assertRaises(ValueError):contact.evaluate(model,values)

    def test_exposed_union_metric_removes_hidden_surface_samples(self):
        points=np.array([[-4,-4,-4],[4,-4,-4],[0,4,-4],[0,0,4]])
        faces=[[0,1,2],[0,1,3],[1,2,3],[2,0,3]]
        outer={'p1':[0,0,0],'p2':[0,0,0],'radius':2.}
        inner={'p1':[0,0,0],'p2':[0,0,0],'radius':1.}
        one=contact.surface_metrics(points,faces,[outer]);two=contact.surface_metrics(points,faces,[outer,inner])
        self.assertEqual(one['capsuleSurfaceSamples'],two['capsuleSurfaceSamples'])
        self.assertEqual(one['capsuleToSkinP95'],two['capsuleToSkinP95'])
        self.assertTrue(two['exactNearestTriangleDistance'])
        self.assertTrue(two['finiteSamplingNotHausdorffProof'])


if __name__=='__main__':unittest.main()
