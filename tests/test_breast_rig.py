"""Meaningful small numeric/IO-contract checks; no game or live mod dependency."""
import importlib.util, json, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import breast_rig as rig
import surface_collar as surface
import unittest, tempfile

class BreastRigTests(unittest.TestCase):

    def setUp(self):
        self.profile = rig.load_profile(ROOT / 'recipes/breast-rig.json')
        self.temp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp.cleanup()

    def test_projector_matches_brute_surface(self):
        profile = self.profile
        tmp_path = Path(self.temp.name)
        v = np.array([[0, 0, 0], [2, 0, 0], [0, 2, 0], [5, 5, 2], [8, 5, 2], [5, 8, 2]], float)
        t = np.array([[0, 1, 2], [3, 4, 5]])
        fast = rig.SurfaceProjector(v, t)
        for p in [[0.2, 0.2, 1], [6, 6, 3], [3, 3, 0.5], [-1, -1, 0]]:
            q, i, d = fast(p)
            qb, ib, db = surface.closest_surface(np.asarray(p), v, t)
            np.testing.assert_allclose(q, qb)
            assert np.isclose(d, db)
            assert i == ib

    def test_reconstruct_known_composite_and_fixed_roots(self):
        profile = self.profile
        tmp_path = Path(self.temp.name)
        v = np.array([[-8, 28, 97], [8, 28, 97], [8, 46, 97], [8, 28, 89]], float)
        b = profile['shapeBasis']
        low = rig.smooth((b['lowerTop'] - v[:, 2]) / b['lowerWidth'])
        direction = np.column_stack([np.sign(v[:, 0]) * b['massLateral'], b['massForward'] + b['projectionForward'] * low, -(b['projectionDown'] + b['sagDown']) * low])
        mask = np.array([0, 0.7, 0, 0.2])
        mobile, r = rig.reconstruct_mobility(v, direction * mask[:, None], [0], profile)
        assert mobile[0] == mobile[2] == mobile[3] == 0
        assert mobile[1] > 0
        assert r['basisResidual']['max'] < 1e-12
        bad = direction * mask[:, None]
        bad[1, 0] += 1
        with self.assertRaisesRegex(ValueError, 'basis'):
            rig.reconstruct_mobility(v, bad, [0], profile)

    def test_capacity_guard_is_welded_and_smooth(self):
        profile = self.profile
        tmp_path = Path(self.temp.name)
        v = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [2, 0, 0], [2, 1, 0], [0, 0, 0]], float)
        t = np.array([[0, 1, 2], [1, 3, 4], [1, 4, 2], [5, 1, 2]])
        W = np.zeros((len(v), 6))
        W[:, 0] = 1
        W[0, :4] = 0.25
        f = rig.capacity_fade(v, t, W, 2)
        assert f[0] == f[5] == 0
        assert np.isclose(f[1], 0.5)
        assert f[3] == 1
        with self.assertRaises(ValueError):
            rig.capacity_fade(v, t, W, 0)

    def test_transfer_preserves_other_support_and_spine_ancestor_lbs(self):
        profile = self.profile
        tmp_path = Path(self.temp.name)
        W = np.array([[0.5, 0.3, 0.2, 0, 0, 0], [0.4, 0.3, 0.2, 0.1, 0, 0]])
        v = np.array([[-8, 28, 97], [8, 28, 97]], float)
        result, q = rig.transfer_spine2(W, [0.3, 0.3], [1, 0], 0, 4, 5, v)
        np.testing.assert_allclose(result[:, 1:4], W[:, 1:4], atol=1e-15, rtol=0)
        assert q[0] > 0
        assert q[1] == 0
        assert (result > 0).sum(axis=1).max() == 4
        np.testing.assert_allclose(result.sum(axis=1), 1)
        matrices = np.repeat(np.eye(4)[None, None], 6, axis=1)
        matrices[0, 0] = rig.rotation(0, 15)
        matrices[0, 4] = matrices[0, 0]
        matrices[0, 5] = matrices[0, 0]
        np.testing.assert_allclose(rig.lbs(v, result, matrices), rig.lbs(v, W, matrices), atol=1e-12)

    def test_raw_packed_metric_does_not_hide_sum_bias(self):
        profile = self.profile
        tmp_path = Path(self.temp.name)
        v = np.array([[0, 0, 100]], float)
        W = np.array([[0.9996]])
        M = np.eye(4)[None, None]
        assert np.isclose(np.linalg.norm(rig.lbs(v, W, M) - rig.lbs(v, W, M, True)), 0.04)

    def test_transfer_rejects_nonfinite_and_empty_source_weights(self):
        v=np.array([[-8,28,97]],float)
        for W in [np.zeros((1,6)),np.array([[float('nan'),0,0,0,0,0]]),np.array([[-1,2,0,0,0,0]])]:
            with self.assertRaises(ValueError):rig.transfer_spine2(W,[.2],[1],0,4,5,v)

    def test_independent_opposite_and_combined_p1_poses(self):
        profile = self.profile
        tmp_path = Path(self.temp.name)
        left, right = profile['p1Bones']
        poses = rig.pose_definitions([left, right], 3, 20261025)
        groups = {g: [e for n, e, k in poses if k == g] for g in ['p1-left', 'p1-right', 'p1-same', 'p1-opposite', 'combined-p1']}
        assert len(poses) == 151
        assert all((left in e and right not in e for e in groups['p1-left']))
        assert all((right in e and left not in e for e in groups['p1-right']))
        for e in groups['p1-opposite']:
            np.testing.assert_allclose(e[left] @ e[right], np.eye(4), atol=1e-14)
        assert len(groups['combined-p1']) == 12

    def test_profile_rejects_unknown_nonfinite_duplicate_fields(self):
        profile = self.profile
        tmp_path = Path(self.temp.name)
        p = tmp_path / 'profile.json'
        profile['mobility']['maximum'] = float('nan')
        p.write_text(json.dumps(profile))
        with self.assertRaises(ValueError):
            rig.load_profile(p)

    def test_profile_cannot_rename_pinned_bodytri_output(self):
        p=Path(self.temp.name)/'profile.json';data=self.profile
        data['outputRelativeNif']='meshes/renamed.nif';p.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'BODYTRI'):rig.load_profile(p)
        p.write_text('{"schemaVersion":1,"schemaVersion":1}')
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            rig.load_profile(p)

    def test_new_external_output_only(self):
        profile = self.profile
        tmp_path = Path(self.temp.name)
        source = tmp_path / 'source'
        source.mkdir()
        inp = source / 'input.nif'
        inp.touch()
        repo = tmp_path / 'repo'
        repo.mkdir()
        live = tmp_path / 'live'
        live.mkdir()
        for output in [source / 'candidate', repo / 'candidate', live / 'candidate', tmp_path / 'mods/candidate', source]:
            with self.assertRaises(ValueError):
                rig.safe_output(output, [inp], repo=repo, live_roots=[live])
        assert rig.safe_output(tmp_path / 'fresh', [inp], repo=repo, live_roots=[live]) == tmp_path / 'fresh'

    def test_rest_frame_compensation_preserves_transfer_term(self):
        profile = self.profile
        tmp_path = Path(self.temp.name)
        spine = np.eye(4)
        spine[:3, 3] = [0, -0.283, 100]
        p1 = spine.copy()
        p1[:3, 3] += [-9, 22, -4]
        oldbind = np.linalg.inv(spine) @ np.diag([1, 1, 1, 1])
        oldbind[1, 3] -= 0.283
        newbind = np.linalg.inv(p1) @ spine @ oldbind
        ancestor = rig.rotation(2, 15)
        np.testing.assert_allclose(ancestor @ p1 @ newbind, ancestor @ spine @ oldbind, atol=1e-12)

    def test_actual_nif_half_roundtrip_rejects_empty_or_unilateral_head_p1(self):
        try:
            api,_,_=rig.load_pynifly()
        except (ValueError,ImportError,OSError) as exc:
            self.skipTest('Configured PyNifly required for packed-NIF regression: '+str(exc))
        bones=['NPC Spine2 [Spn2]',*self.profile['p1Bones']]
        vertices=[(-1.,0.,0.),(1.,0.,0.),(0.,1.,0.)]
        for label,left,right,accepted in [('half-erased',5.52e-16,5.52e-16,False),
                                          ('one-side',.125,5.52e-16,False),
                                          ('bilateral',.125,.125,True)]:
            with self.subTest(case=label):
                path=Path(self.temp.name)/(label+'.nif')
                nif=api.NifFile();nif.initialize('SKYRIMSE',str(path))
                shape=nif.createShapeFromData('head',vertices,[(0,1,2)],[(0,0),(1,0),(0,1)],[(0,0,1)]*3)
                shape.skin()
                for name in bones:shape.add_bone(name,api.TransformBuf())
                shape.setShapeWeights(bones[0],[(0,1-left),(1,1-right),(2,1.)])
                shape.setShapeWeights(bones[1],[(0,left)])
                shape.setShapeWeights(bones[2],[(1,right)])
                shape.set_partitions([api.SkyPartition(part_id=32,namedict=nif.dict)],[32])
                nif.save()
                actual=api.NifFile(str(path)).shapes[0]
                packed=rig.read_weights(actual,bones)
                if label=='half-erased':
                    self.assertEqual(float(packed[:,1:].max()),0.)
                if accepted:
                    result=rig.require_serialized_head_mobility(packed,bones,actual.verts,bones[1:])
                    self.assertEqual([x['storedMobileVertices']for x in result.values()],[1,1])
                else:
                    with self.assertRaisesRegex(ValueError,'no-op rig rejected'):
                        rig.require_serialized_head_mobility(packed,bones,actual.verts,bones[1:])
if __name__ == '__main__':
    unittest.main()
