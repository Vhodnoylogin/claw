import importlib.util
from pathlib import Path
import unittest
import numpy as np

PATH=Path(__file__).resolve().parents[1]/'scripts/morph_calibration.py'
SPEC=importlib.util.spec_from_file_location('morph_calibration',PATH)
cal=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(cal)


class CalibrationTests(unittest.TestCase):
    def test_split_duplicates_do_not_reweight_geometry_or_merge_different_bindings(self):
        points=np.zeros((5,3));bones={'B':np.array([1,1,1,1,.5])}
        deltas={'M':np.zeros((5,3))};deltas['M'][3,0]=.1
        keep=cal.unique_physical_samples(points,bones,deltas,[0,0,1,0,0])
        np.testing.assert_array_equal(keep,[0,2,3,4])

    def test_projection_is_linear_and_preserves_signed_shrink(self):
        p=np.asarray([[x,y,z] for x in (-2,2) for y in (-1,1) for z in range(8)],float)
        f=cal.feature(p,np.ones(len(p),bool),'width')
        self.assertAlmostEqual(cal.response(p*[-.2,0,0],[f])[0],-.2)
        a=p*[.2,0,0];b=p*[0,.3,0]
        np.testing.assert_allclose(cal.response(.3*a+.7*b,[f]),.3*cal.response(a,[f])+.7*cal.response(b,[f]))

    def test_one_human_source_can_drive_several_distinct_wolf_regions(self):
        matrix=np.asarray([[.4,0],[0,.2]])
        gains,error=cal.signed_fit(matrix,[.2,.1])
        np.testing.assert_allclose(gains,[.5,.5],atol=1e-8)
        self.assertLess(error,.051) # negative anatomy has no opposed target.

    def test_opposed_geometry_uses_opposed_human_signs(self):
        gains,error=cal.signed_fit([[1,-1]],[.4])
        self.assertLess(error,1e-12)
        np.testing.assert_allclose(gains,[.4,-.4],atol=1e-8)

    def test_source_name_does_not_choose_gain_sign(self):
        gains,_=cal.signed_fit([[1]],[-.6])
        self.assertAlmostEqual(gains[0],-.6)

    def test_source_cancellation_occurs_before_clamp(self):
        rules=[{'source':name,'target':'Girth','gain':.5} for name in ['A','B']]
        self.assertEqual(cal.compose(rules,{'A':2,'B':-2}),{'Girth':0})
        self.assertEqual(cal.compose(rules,{'A':1,'B':0}),{'Girth':.5})

    def test_degenerate_geometry_refused(self):
        with self.assertRaises(ValueError):cal.feature(np.zeros((16,3)),np.ones(16,bool),'width')
        with self.assertRaises(ValueError):cal.signed_fit(np.zeros((1,9)),[1])


if __name__=='__main__':unittest.main()
