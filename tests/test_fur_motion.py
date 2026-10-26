"""Motion/packing regressions using independent small examples and NIF readback."""
from pathlib import Path
from types import SimpleNamespace
import copy
import json
import sys
import tempfile
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import fur_motion as fur
import breast_rig as rig


class FurMotionTests(unittest.TestCase):
    def test_fit_clamps_and_refuses_missing_observation(self):
        x = np.asarray([[1., 2., 0.], [0., -1., 3.]])
        self.assertAlmostEqual(fur.fit_scalar(x, .35*x, 0, .8), .35)
        self.assertEqual(fur.fit_scalar(x, 2*x, 0, .8), .8)
        self.assertEqual(fur.fit_scalar(x, -x, 0, .8), 0.)
        for bad in (np.zeros_like(x), np.full_like(x, np.nan)):
            with self.assertRaises(ValueError):
                fur.fit_scalar(bad, x, 0, 1)

    def test_packed_transfer_preserves_sum_and_spine(self):
        for spine, p1 in ((.5, .125), (.0625, .0009765625), (1., 0.)):
            for desired in (0., .000013, .12345, spine+p1, 10.):
                actual = fur.exact_half_pair(spine, p1, desired)
                self.assertEqual(float(actual.sum()), spine+p1)
                self.assertGreater(actual[0], 0.)
                np.testing.assert_array_equal(actual.astype(np.float16).astype(float), actual)
        with self.assertRaises(ValueError):
            fur.exact_half_pair(.1, .2, .3)

    def test_card_preserves_foreign_support_and_four_slot_vertex(self):
        # Spine, two original joints, another original joint, left P1, right P1.
        old = np.asarray([[.5, .25, .125, 0, .125, 0], [.5, .25, .125, .125, 0, 0]])
        result = fur.transfer_card(old, [0, 1], 0, .25, 0, 4, 5)
        self.assertGreater(result[0, 4], old[0, 4])
        np.testing.assert_array_equal(result[:, 1:4], old[:, 1:4])
        np.testing.assert_array_equal(result[1], old[1])
        np.testing.assert_array_equal(result.sum(axis=1), old.sum(axis=1))
        self.assertLessEqual(np.count_nonzero(result, axis=1).max(), 4)
        opposite = old.copy(); opposite[0, 5] = .125
        with self.assertRaises(ValueError):
            fur.transfer_card(opposite, [0, 1], 0, .25, 0, 4, 5)

    def test_transfer_rejects_bad_indices_nan_and_duplicate_vertex(self):
        old = np.asarray([[.75, 0, 0, .25, 0]])
        for ids, root, q in (([0, 0], 0, .3), ([2], 2, .3), ([0], 0, float('nan'))):
            with self.assertRaises(ValueError):
                fur.transfer_card(old, ids, root, q, 0, 3, 4)

    def test_offset_transport_includes_barycentric_covariance(self):
        m = fur.MotionModel.__new__(fur.MotionModel)
        m.names = ['Spine', 'P1']; m.rest = {n: np.eye(4) for n in m.names}
        m.poses = [('rest', {}, 'ordinary'), ('turn', {}, 'p1-left')]
        m.globals = np.repeat(np.eye(4)[None, None], 2, axis=0)
        m.globals = np.repeat(m.globals, 2, axis=1)
        turn = rig.rotation(2, 90)
        m.globals[1, 1] = turn
        m.profile = {'layer': 'fur_belly'}; m.raw = {}
        v = np.asarray([[0., 0., 0.], [2., 0., 0.], [0., 2., 0.]])
        bary = np.asarray([.2, .3, .5]); offset = np.asarray([0., 0., 1.])
        root = bary@v+offset
        m.shapes = {'body': SimpleNamespace(verts=v), 'fur_belly': SimpleNamespace(verts=np.asarray([root]))}
        m.weights = {'body': np.asarray([[1., 0.], [.5, .5], [0., 1.]]), 'fur_belly': np.asarray([[1., 0.]])}
        m.binds = {n: np.repeat(np.eye(4)[None], 2, axis=0) for n in m.shapes}
        layer = SimpleNamespace(binding=SimpleNamespace(faces=np.asarray([[0, 1, 2]]), indices=np.asarray([0]), weights=np.asarray([bary])))
        got = m.target(layer, 0, 0, 0)
        skin_after = sum(bary[i]*((1-m.weights['body'][i, 1])*v[i]+m.weights['body'][i, 1]*(turn[:3, :3]@v[i])) for i in range(3))
        expected = skin_after+offset-root
        np.testing.assert_allclose(got[1], expected, atol=1e-14)
        # Interpolating the weights at one barypoint loses covariance.
        q = bary@m.weights['body'][:, 1]
        naive = (1-q)*(bary@v)+q*(turn[:3, :3]@(bary@v))+offset-root
        self.assertGreater(np.linalg.norm(got[1]-naive), .1)

    def test_profile_rejects_changed_input_or_weakened_tolerance(self):
        p = json.loads((ROOT/'recipes/fur-motion.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp)/'p.json'
            for key, value in (('maximumCardStrainChange', .1), ('layer', 'head'), ('inputs', {}), ('normalizedOrdinaryMaxError', float('nan'))):
                bad = copy.deepcopy(p); bad[key] = value; f.write_text(json.dumps(bad))
                with self.assertRaises(ValueError):
                    fur.load_profile(f)

    def test_actual_readback_rejects_bodytri_and_detached_normal_mismatch(self):
        try:
            api, _, _ = rig.load_pynifly()
        except (ValueError, ImportError, OSError) as exc:
            self.skipTest('Configured PyNifly required: '+str(exc))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'test.nif'
            nf = api.NifFile(); nf.initialize('SKYRIMSE', str(path))
            shape = nf.createShapeFromData('head', [(0., 0., 0.), (1., 0., 0.), (0., 1., 0.)], [(0, 1, 2)], [(0, 0), (1, 0), (0, 1)], [(0, 0, 1)]*3)
            shape.skin(); shape.add_bone('Spine', api.TransformBuf()); shape.setShapeWeights('Spine', [(0, 1.), (1, 1.), (2, 1.)])
            shape.set_partitions([api.SkyPartition(part_id=32, namedict=nf.dict)], [32])
            api.NiStringExtraData.New(nf, name='BODYTRI', string_value='original.tri', parent=shape)
            nf.save(); nf = api.NifFile(str(path)); frozen = fur.snapshot(nf)
            planned = rig.read_weights(nf.shapes[0], ['Spine'])
            data = path.read_bytes()
            self.assertEqual(data.count(b'original.tri'), 1)
            path.write_bytes(data.replace(b'original.tri', b'changed_.tri'))
            with self.assertRaisesRegex(ValueError, 'Node ancestry or transform changed|extras'):
                fur.verify_snapshot(frozen, api.NifFile(str(path)), 'unused', planned, ['Spine'])
            path.write_bytes(data)
            mutated = copy.deepcopy(frozen); mutated['shapes']['head']['normals'][0, 0] = 1.
            with self.assertRaisesRegex(ValueError, 'normals'):
                fur.verify_snapshot(mutated, api.NifFile(str(path)), 'unused', planned, ['Spine'])


if __name__ == '__main__':
    unittest.main()
