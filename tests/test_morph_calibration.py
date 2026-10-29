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

    def test_native_cap_is_applied_after_shared_sum_and_clamp(self):
        rules=[{'source':name,'target':'Girth','gain':2.4,'cap':.25} for name in ['A','B']]
        self.assertAlmostEqual(cal.compose(rules,{'A':.1})['Girth'],.06)
        self.assertEqual(cal.compose(rules,{'A':2})['Girth'],.25)
        self.assertEqual(cal.compose(rules,{'A':2,'B':-2})['Girth'],0)
        with self.assertRaises(ValueError):
            cal.compose([rules[0],dict(rules[1],cap=.5)],{})

    def test_measured_himbo_and_wolf_waist_shrink_need_same_polarity(self):
        # Serialized installed TRI/NIF measurements: positive source and target
        # both decrease the bone-supported regional lateral width.
        human_width = -0.10086447796210547
        wolf_width = -0.039536675600633314
        gain = cal.gain_with_primary_direction(-3.8354787, human_width, wolf_width)
        self.assertEqual(gain, 3.8354787)
        rules = [{'source':'TorsoWaistSize','target':'WaistNarrow','gain':gain}]
        self.assertAlmostEqual(cal.compose(rules, {'TorsoWaistSize':.2})['WaistNarrow'], .76709574)
        self.assertEqual(cal.compose(rules, {'TorsoWaistSize':-.4})['WaistNarrow'], 0)
        with self.assertRaises(ValueError):
            cal.gain_with_primary_direction(gain, 0, wolf_width)

    def test_finite_recentered_metric_handles_large_field_and_translation(self):
        points=np.asarray([[x,y,z] for x in (-2,-1,1,2) for y in (-1,1) for z in (0,1)],float)
        ids=np.arange(len(points))
        moved=cal.finite_region_dimensions(points,points+[10,20,30],ids,0)
        self.assertAlmostEqual(moved['relative']['mad'],0)
        self.assertAlmostEqual(moved['relative']['full_span'],0)
        scaled=cal.finite_region_dimensions(points,points*[1.5,1,1],ids,0)
        self.assertAlmostEqual(scaled['relative']['mad'],.5)
        self.assertAlmostEqual(scaled['relative']['q05_95_span'],.5)
        reflected=points*[-1,1,1]
        finite=cal.finite_region_dimensions(points,reflected,ids,0)
        self.assertAlmostEqual(finite['relative']['mad'],0)
        linear=cal.response(reflected-points,[cal.feature(points,np.ones(len(points),bool),'width')])[0]
        self.assertAlmostEqual(linear,-2) # A surrogate, not the finite width.

    def test_degenerate_geometry_refused(self):
        with self.assertRaises(ValueError):cal.feature(np.zeros((16,3)),np.ones(16,bool),'width')
        with self.assertRaises(ValueError):cal.signed_fit(np.zeros((1,9)),[1])


if __name__=='__main__':unittest.main()
