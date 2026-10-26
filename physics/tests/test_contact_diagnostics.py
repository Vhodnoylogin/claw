from pathlib import Path
import sys
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import contact_diagnostics as diagnostics

class ContactDiagnosticsTests(unittest.TestCase):
    def test_aabb_pruning_matches_unpruned_face_point_distance_and_oriented_normal(self):
        rng=np.random.default_rng(20261026);triangles=rng.normal(size=(300,3,3))*4
        triangles[0]=[[0,0,0],[4,0,0],[0,4,0]]
        triangles[1]=[[0,4,0],[4,0,0],[0,0,0]] # Opposite normal, exact tie.
        points=np.concatenate([[[1,1,1e-8]],rng.normal(size=(30,3))*5])
        fast=diagnostics.nearest(points,triangles,prune=True);full=diagnostics.nearest(points,triangles,prune=False)
        self.assertTrue(np.array_equal(fast[2],full[2]))
        self.assertTrue(np.allclose(fast[0],full[0],atol=1e-12,rtol=0))
        self.assertTrue(np.allclose(fast[1],full[1],atol=1e-12,rtol=0))
        self.assertEqual(fast[2][0],0)
        normal=lambda indices:np.cross(triangles[indices,1]-triangles[indices,0],triangles[indices,2]-triangles[indices,0])
        self.assertTrue(np.array_equal(normal(fast[2]),normal(full[2])))
        self.assertTrue(np.allclose(np.sum((points-fast[1])*normal(fast[2]),axis=1),np.sum((points-full[1])*normal(full[2]),axis=1),atol=1e-12,rtol=0))

    def test_nearest_triangle_witness_interior_edge_and_degenerate(self):
        points=[[1,1,2],[3,3,0],[-1,-1,0]];triangles=[[[0,0,0],[4,0,0],[0,4,0]]]
        distance,nearest,indices=diagnostics.nearest(points,triangles)
        self.assertTrue(np.allclose(distance,[2,np.sqrt(2),np.sqrt(2)]))
        self.assertTrue(np.allclose(nearest,[[1,1,0],[2,2,0],[0,0,0]]))
        self.assertEqual(indices.tolist(),[0,0,0])

    def test_full_signed_distributions_explicitly_limit_oriented_open_skin_sign(self):
        p=[[-4,-4,0],[4,-4,0],[0,4,0]];f=[[0,1,2]]
        cap={'p1':[0,0,1],'p2':[0,0,1],'radius':.5}
        result=diagnostics.signed_witnesses(p,f,[cap])
        self.assertGreater(result['capsuleToSkinOrientedNearestFace']['min'],0.)
        self.assertEqual(len(result['capsuleWorstWitnesses']),5)
        self.assertIn('not closed-solid',result['capsuleToSkinOrientedSignLimit'])
        self.assertIn('proxy',result['skinSignedFieldLimit'])

if __name__=='__main__':unittest.main()
