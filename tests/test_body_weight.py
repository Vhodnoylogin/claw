import sys
import unittest
from pathlib import Path
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import body_weight as weight
import surface_collar as surface


class WeightTests(unittest.TestCase):
    def test_weight_and_named_morph_are_independent(self):
        low=np.zeros((2,3));high=np.ones((2,3))*2;delta=np.ones((2,3))*3
        for value in (0.,.3,1.):
            actual=weight.interpolate(low,high,value,{'M':delta},{'M':.7})
            np.testing.assert_allclose(actual,value*2+2.1)
            np.testing.assert_allclose(actual-weight.interpolate(low,high,value),delta*.7)

    def test_thirty_percent_is_not_thirty_percent_morphs(self):
        low=np.array([[1.,2.,3.]]);high=np.array([[3.,4.,5.]])
        np.testing.assert_allclose(weight.interpolate(low,high,.3),[[1.6,2.6,3.6]])
        for value in (-.1,1.1,float('nan')):
            with self.assertRaises(ValueError):weight.interpolate(low,high,value)

    def test_exact_bvh_matches_brute_triangle_projection(self):
        rng=np.random.default_rng(20261026);vertices=rng.normal(size=(120,3));faces=np.arange(120).reshape(-1,3)
        projector=weight.Projector(vertices,faces)
        for point in rng.normal(size=(30,3)):
            a,_,d=projector(point);b,_,e=surface.closest_surface(point,vertices,faces)
            np.testing.assert_allclose(a,b,atol=1e-10);self.assertAlmostEqual(d,e,places=10)

    def test_translation_preserves_authored_tangent_frame_bytes(self):
        vertices=np.array([[0.,0,0],[1.,0,0],[0.,1,0]]);faces=np.array([[0,1,2]])
        rows=np.arange(120,dtype=np.uint8).reshape(3,40)
        result=weight.transport_frames(vertices,faces,np.ones((3,3))*.3,rows)
        np.testing.assert_array_equal(result,rows)

    def test_continuous_weight_path_rejects_midpoint_collapse(self):
        vertices=np.array([[0.,0,0],[1.,0,0],[0.,1,0]]);faces=np.array([[0,1,2]])
        delta=np.array([[0.,0,0],[0.,0,0],[0.,-2,0]])
        with self.assertRaises(ValueError):weight.area_path(vertices,faces,delta)

    def test_continuous_translation_retains_area(self):
        vertices=np.array([[0.,0,0],[1.,0,0],[0.,1,0]]);faces=np.array([[0,1,2]])
        report=weight.area_path(vertices,faces,np.ones((3,3))*.7)
        self.assertEqual(report['minimumOwnRestAreaRatio'],1.)
        self.assertEqual(report['normalReversalCount'],0)

    def test_normal_transport_follows_sheared_geometry_and_keeps_uv_weights(self):
        vertices=np.array([[0.,0,0],[1.,0,0],[0.,1,0]]);faces=np.array([[0,1,2]])
        rows=np.zeros((3,40),np.uint8);rows[:,20:23]=[128,128,255];rows[:,24:27]=[255,128,128]
        rows[:,23]=255;rows[:,27]=128;rows[:,16:20]=[1,2,3,4];rows[:,28:40]=np.arange(12)
        delta=np.array([[0.,0,0],[0.,0,.3],[0.,0,0]])
        actual=weight.transport_frames(vertices,faces,delta,rows);normal=actual[:,20:23].astype(float)/127.5-1
        expected=np.array([-.3,0,1]);expected/=np.linalg.norm(expected)
        np.testing.assert_allclose(normal,np.tile(expected,(3,1)),atol=.01)
        np.testing.assert_array_equal(actual[:,16:20],rows[:,16:20]);np.testing.assert_array_equal(actual[:,28:40],rows[:,28:40])


if __name__=='__main__':unittest.main()
