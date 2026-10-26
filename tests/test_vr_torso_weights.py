"""Independent numeric and admission checks for the optional VR torso experiment."""
from pathlib import Path
import copy
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import vr_torso_weights as vr


class PackedTransferTests(unittest.TestCase):
    def test_removes_head_motion_and_preserves_other_joint_exactly(self):
        weights = np.asarray([[.5, .25, .25], [.75, 0, .25]])
        got = vr.transfer_head(weights, [1, 0], 0, [1])
        np.testing.assert_array_equal(got, [[.75, 0, .25], [.75, 0, .25]])
        # Head translation20: the first vertex's former5-unit excursion is gone.
        self.assertEqual(float(weights[0, 1]*20), 5.)
        self.assertEqual(float(got[0, 1]*20), 0.)

    def test_exact_sum_retains_unrepresentable_pair_residual(self):
        weights = np.asarray([[.7, .1, .2]], dtype=np.float16).astype(float)
        got = vr.transfer_head(weights, [1], 0, [1])
        np.testing.assert_array_equal(got.sum(axis=1), weights.sum(axis=1))
        np.testing.assert_array_equal(got[:, 2], weights[:, 2])
        self.assertGreater(got[0, 1], 0)  # Exact packed zero cannot represent this pair sum.
        self.assertLess(got[0, 1], weights[0, 1])

    def test_head_and_jaw_removal_keeps_four_slots_without_palette_pruning(self):
        weights = np.asarray([[.5, .25, .125, .125], [0, .5, .25, .25]])
        got = vr.transfer_head(weights, [1, 1], 0, [1, 2])
        np.testing.assert_array_equal(got, [[.875, 0, 0, .125], [.75, 0, 0, .25]])
        np.testing.assert_array_equal(got[:, 3], weights[:, 3])
        self.assertLessEqual(int(np.count_nonzero(got, axis=1).max()), 4)

    def test_zero_field_is_byte_value_noop_and_invalid_field_refused(self):
        weights = np.asarray([[.75, .25]])
        np.testing.assert_array_equal(vr.transfer_head(weights, [0], 0, [1]), weights)
        for field in ([float('nan')], [-.01], [1.01]):
            with self.assertRaises(ValueError):
                vr.transfer_head(weights, field, 0, [1])


class RegionAndFrameTests(unittest.TestCase):
    def test_geodesic_band_does_not_jump_to_nearby_disconnected_surface(self):
        vertices = np.asarray([[0, 0, 0], [1, 0, 0], [0, 1, 0],
                               [0, 0, .01], [1, 0, .01], [0, 1, .01]])
        triangles = np.asarray([[0, 1, 2], [3, 4, 5]])
        got = vr.band_field(vertices, triangles, [0], 2., 5, [2])
        self.assertEqual(got[0], 1.)
        self.assertAlmostEqual(got[1], .5)
        self.assertEqual(got[2], 0.)
        np.testing.assert_array_equal(got[3:], 0.)

    def test_lbs_retains_actual_scale_frame_and_distinct_raw_sum(self):
        model = vr.Model.__new__(vr.Model)
        model.globals = np.zeros((2, 2, 4, 4))
        model.weights = {'test': np.asarray([[.5, .25]])}
        model.vertices = {'test': np.asarray([[2., 0, 0]])}
        model.deltas = {'test': np.asarray([[0., 0, 0]])}
        frame = np.eye(4); frame[:3, :3] *= 2; frame[0, 3] = 3
        model.effective = {'test': np.tile(frame, (2, 2, 1, 1))}
        model.effective['test'][1, 1, 0, 3] += 20
        raw = model.evaluate('test', [0], 0, normalized=False)
        normal = model.evaluate('test', [0], 0, normalized=True)
        np.testing.assert_allclose(raw[:, 0, 0], [5.25, 10.25])
        np.testing.assert_allclose(normal[:, 0, 0], [7, 7+20/3])
        corrected = vr.transfer_head(model.weights['test'], [1], 0, [1])
        got = model.evaluate('test', [0], 0, corrected, False)
        np.testing.assert_allclose(got[:, 0, 0], [5.25, 5.25])

    def test_edge_gate_detects_card_deformation_even_with_fixed_root(self):
        old = np.asarray([[[0., 0, 0], [1., 0, 0]]]*2)
        new = old.copy(); new[1, 1, 0] = 1.1
        measured = vr.edge_change(old, new, np.asarray([[0, 1]]))
        self.assertAlmostEqual(float(measured.max()), .1)


class AdmissionTests(unittest.TestCase):
    def fixtures(self):
        scalar = lambda value: {'max': value, 'rms': value/10}
        values = {'coreHideBefore': scalar(2), 'coreHideAfter': scalar(0),
                  'ordinaryChange': scalar(.1), 'pureP1MotionChange': scalar(0)}
        shapes = {'head': {'measurements': {'normalized': values}}}
        joins = {'collar': {'normalized': {'offsetDriftIncrease': scalar(0)}},
                 'layers': {'fur': {'measurements': {'normalized': {
                     'rootTransportResidualBefore': scalar(.1), 'rootTransportResidualAfter': scalar(.11),
                     'pointwiseRootResidualIncrease': scalar(.01),
                     'rootDistanceDriftIncrease': scalar(.001), 'fullCardEdgeChange': scalar(.005)}}}}}
        limits = vr.load_profile(ROOT/'recipes/vr-torso-weights.json')['limits']
        return shapes, joins, limits

    def test_head_hide_success_does_not_override_ordinary_or_fur_failure(self):
        shapes, joins, limits = self.fixtures()
        self.assertFalse(vr.admission(shapes, joins, limits))
        shapes['head']['measurements']['normalized']['ordinaryChange']['max'] = .3
        self.assertIn('head/normalized: ordinary motion change budget', vr.admission(shapes, joins, limits))
        shapes['head']['measurements']['normalized']['ordinaryChange']['max'] = .1
        joins['layers']['fur']['measurements']['normalized']['fullCardEdgeChange']['max'] = .02
        self.assertIn('fur/normalized: full-card strain change', vr.admission(shapes, joins, limits))

    def test_packed_residual_cannot_be_reported_as_isolation(self):
        shapes, joins, limits = self.fixtures()
        shapes['head']['measurements']['normalized']['coreHideAfter']['max'] = .001
        self.assertIn('head/normalized: head-hide isolation', vr.admission(shapes, joins, limits))

    def test_worse_local_join_cannot_hide_behind_a_different_global_maximum(self):
        shapes, joins, limits = self.fixtures()
        row = joins['layers']['fur']['measurements']['normalized']
        row['rootTransportResidualBefore']['max'] = 2.
        row['rootTransportResidualAfter']['max'] = 1.9
        row['pointwiseRootResidualIncrease']['max'] = .03
        self.assertIn('fur/normalized: fur attachment increase', vr.admission(shapes, joins, limits))

    def test_profile_cannot_weaken_limits_or_change_roi(self):
        profile = vr.load_profile(ROOT/'recipes/vr-torso-weights.json')
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'profile.json'
            for mutate in (lambda p: p['limits'].update(ordinaryMaxNormalized=.251),
                           lambda p: p['region'].update(faceMinY=46),
                           lambda p: p['limits'].update(minimumHideReduction=.8)):
                p = copy.deepcopy(profile); mutate(p); path.write_text(json.dumps(p))
                with self.assertRaises(ValueError):
                    vr.load_profile(path)

    def test_readback_refuses_protected_normals_and_unplanned_body_weights(self):
        eye = np.eye(4)
        shape = {'vertices': np.asarray([[0., 0, 0]]), 'triangles': np.asarray([[0, 0, 0]]),
                 'uvs': np.asarray([[0., 0]]), 'frame': eye, 'normals': np.asarray([[0., 0, 1]]),
                 'colors': np.asarray([]), 'transform': eye, 'render': (), 'extras': (), 'partitions': (),
                 'hasFrame': True, 'bones': ('Spine',), 'binds': {'Spine': eye},
                 'weights': {'Spine': ((0, 1.),)}}
        before = {'nodes': {'Root': (None, eye, eye, ())}, 'shapes': {'body': shape}}
        for change in ('normal', 'weight'):
            after = copy.deepcopy(before)
            if change == 'normal':
                after['shapes']['body']['normals'][0] = [0, 1, 0]
            else:
                after['shapes']['body']['weights'] = {'Spine': ((0, .5),)}
            with patch.object(vr, 'snapshot', return_value=after), self.assertRaises(ValueError):
                vr.verify_readback(before, object(), {}, ['Spine'])


if __name__ == '__main__':
    unittest.main()
