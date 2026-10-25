"""Numeric/adapter failure contracts; no game, installed files or fake pose oracle."""
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import collar_weights as collar


class CollarWeights(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads((ROOT / 'recipes/collar-weights.json').read_text(encoding='utf-8'))

    def test_pinned_profile_and_numeric_rejections(self):
        collar.validate_profile(self.profile)
        cases = [('collar', 'width', True), ('collar', 'solverTolerance', float('nan')),
                 ('fitting', 'maxInfluences', 5), ('poses', 'seed', False)]
        for group, key, value in cases:
            bad = copy.deepcopy(self.profile)
            bad[group][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                collar.validate_profile(bad)
        for mutate in (lambda p: p['anchors'][0].update(head=True),
                       lambda p: p['anchors'][0].update(barycentric=[.5, .5, .5]),
                       lambda p: p['anchors'][1].update(head=p['anchors'][0]['head']),
                       lambda p: p.update(relativeNifPath='../escape.nif'),
                       lambda p: p['poses']['ordinaryControls'][0].update(bone='NPC L Breast P1')):
            bad = copy.deepcopy(self.profile)
            mutate(bad)
            with self.assertRaises(ValueError):
                collar.validate_profile(bad)

    def test_exact_input_hashes_fail_before_parsing_or_writing(self):
        with tempfile.TemporaryDirectory(prefix='claw-collar-inputs-') as folder:
            paths = [Path(folder) / n for n in ('body.nif', 'body.tri', 'skeleton.nif')]
            for i, p in enumerate(paths):
                p.write_bytes(bytes([i]))
            with self.assertRaisesRegex(ValueError, 'nifSha256'):
                collar.validate_inputs(*paths, self.profile)
            profile = copy.deepcopy(self.profile)
            for p, key in zip(paths, ('nifSha256', 'triSha256', 'skeletonSha256')):
                profile['pins'][key] = collar.sha256(p)
            self.assertEqual(collar.validate_inputs(*paths, profile), [p.resolve() for p in paths])
            paths[1].write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'triSha256'):
                collar.validate_inputs(*paths, profile)

    def test_mvp_cannot_rename_embedded_bodytri_destination(self):
        for relative in ('meshes/elsewhere/renamed.nif', 'meshes/actors/werewolfbeast/character assets/other.nif'):
            bad = copy.deepcopy(self.profile)
            bad['relativeNifPath'] = relative
            with self.subTest(relative=relative), self.assertRaisesRegex(ValueError, 'BODYTRI'):
                collar.validate_profile(bad)

    def test_readback_uses_detached_prewrite_bind_snapshot(self):
        # Plain public-API carriers, not opaque Nifly handle copies. Mutating the
        # live writer object and readback alike must not redefine the baseline.
        bone = 'NPC Spine2 [Spn2]'
        def transform():
            return SimpleNamespace(rotation=np.eye(3), translation=[0., 0., 0.], scale=1.)
        def carrier():
            node = SimpleNamespace(name=bone, parent=None, global_transform=transform())
            shapes = []
            for name, z in (('body', 0.), ('head', .2)):
                shape = SimpleNamespace(name=name, verts=[[0., 0., z], [1., 0., z], [0., 1., z]],
                    tris=[[0, 1, 2]], uvs=[[0., 0.], [1., 0.], [0., 1.]],
                    bone_names=[bone], bone_ids=[0], bone_weights={bone: [(0, 1.), (1, 1.), (2, 1.)]},
                    global_to_skin=transform(), bind=transform())
                shape.get_shape_skin_to_bone = lambda name, obj=shape: obj.bind
                shapes.append(shape)
            return SimpleNamespace(nodes={bone: node}, shapes=shapes)
        profile = copy.deepcopy(self.profile)
        profile['pins']['nodeCount'] = 1
        profile['anchors'] = [{'head': 0, 'bodyTriangle': 0, 'barycentric': [1., 0., 0.]}]
        profile['poses']['ordinaryControls'] = [{'bone': bone, 'degrees': 15}]
        profile['poses']['heldoutCount'] = 1
        live, result = carrier(), carrier()
        model = collar.Model(live, carrier(), profile)
        planned, active = model.weights['head'].copy(), np.array([0])
        collar.verify_readback(model, result, planned, active)
        live.shapes[1].bind.translation[0] += .25
        result.shapes[1].bind.translation[0] += .25
        with self.assertRaisesRegex(ValueError, 'skin bind'):
            collar.verify_readback(model, result, planned, active)
        self.assertEqual(model.original_shapes['head']['binds'][bone][0, 3], 0.)
        with self.assertRaises(ValueError):
            model.original_shapes['head']['binds'][bone][0, 3] = .25

    def test_new_external_directory_only(self):
        with tempfile.TemporaryDirectory(prefix='claw-collar-output-') as folder:
            parent = Path(folder)
            self.assertEqual(collar.guard_output(parent / 'new'), (parent / 'new').resolve())
            with self.assertRaisesRegex(ValueError, 'new'):
                collar.guard_output(parent)
            for name in ('Data', 'mods', 'Overwrite'):
                root = parent / name
                root.mkdir()
                with self.assertRaisesRegex(ValueError, 'external staging'):
                    collar.guard_output(root / 'new')
            with self.assertRaisesRegex(ValueError, 'source/live'):
                collar.guard_output(ROOT / 'new-collar-test-output')
            with self.assertRaisesRegex(ValueError, 'contain an input'):
                collar.guard_output(parent / 'new', [parent / 'new' / 'body.nif'])

    def test_normalize_is_explicit_and_does_not_mutate_packed_input(self):
        packed = np.array([[.25, .749755859375]])
        saved = packed.copy()
        result = collar.normalize(packed)
        self.assertEqual(result.sum(), 1.)
        np.testing.assert_array_equal(packed, saved)
        for bad in (np.zeros((1, 2)), np.array([[1., -1.]]), np.array([[float('nan'), 1.]])):
            with self.assertRaises(ValueError):
                collar.normalize(bad)

    def test_sparse_fit_keeps_four_slot_simplex_and_exposes_unrepresentable_five(self):
        points = np.zeros((6, 5, 3))
        for i in range(5):
            points[i + 1, i, 0] = 1.
        reference = np.full(5, .2)
        target = np.einsum('pbj,b->pj', points, reference)
        fitted = collar.sparse_fit(points, target, reference, self.profile['fitting'])
        self.assertLessEqual((fitted > 0).sum(), 4)
        self.assertGreaterEqual(fitted.min(), 0)
        self.assertAlmostEqual(fitted.sum(), 1.)
        self.assertGreater(np.linalg.norm(np.einsum('pbj,b->pj', points, fitted) - target), .19)
        wanted = np.array([.3, .7, 0, 0, 0])
        target = np.einsum('pbj,b->pj', points, wanted)
        fitted = collar.sparse_fit(points, target, reference, self.profile['fitting'])
        np.testing.assert_allclose(np.einsum('pbj,b->pj', points, fitted), target, atol=1e-10)
        with self.assertRaises(ValueError):
            collar.sparse_fit(points, target, np.zeros(5), self.profile['fitting'])

    def test_half_packing_exact_sum_without_adding_support(self):
        for target in (np.array([.3728749, .222064, .0985152, .3065459, 0]),
                       np.array([1e-6, .6819016, .1172223, .2008751, 0]), np.array([1., 0, 0])):
            target = target / target.sum()
            result = collar.exact_half_weights(target)
            self.assertEqual(result.sum(), 1.)
            np.testing.assert_array_equal(result.astype(np.float16).astype(float), result)
            self.assertEqual(result[-1], 0)
            self.assertLess(abs(result - target).max(), .001)
        for bad in (np.full(5, .2), np.array([float('nan'), 1]), np.zeros(2)):
            with self.assertRaises(ValueError):
                collar.exact_half_weights(bad)

    def test_two_unit_band_preserves_outer_weights_and_interpolates_nonnegative(self):
        vertices = np.asarray([[x, y, 0.] for y in range(5) for x in range(5)])
        faces = []
        for y in range(4):
            for x in range(4):
                i = y * 5 + x
                faces.extend([[i, i + 1, i + 5], [i + 1, i + 6, i + 5]])
        old = np.tile([1., 0], (25, 1))
        seeds = np.tile([0., 1], (5, 1))
        result, active, distance, _ = collar.blend_band(vertices, np.asarray(faces), np.arange(5), seeds, old, self.profile['collar'])
        np.testing.assert_array_equal(result[:5], seeds)
        np.testing.assert_array_equal(result[vertices[:, 1] >= 2], old[vertices[:, 1] >= 2])
        np.testing.assert_allclose(result.sum(axis=1), 1., atol=1e-10)
        self.assertGreaterEqual(result.min(), 0.)
        self.assertTrue((distance[active] < 2).all())

    def test_public_per_bone_adapter_clears_stale_slots_and_preserves_outside(self):
        names = list('abcde')
        initial = np.array([[.4, .3, .2, .1, 0], [.5, .5, 0, 0, 0]])
        class PackedShape:
            def __init__(self):
                self.weights = initial.copy()
                self.bone_weights = {n: [] for n in names}
                self.calls = []
            def setShapeWeights(self, bone, pairs):
                self.calls.append((bone, pairs))
                j = names.index(bone)
                for i, value in pairs:
                    # The real public setter retains unmentioned old slots. A
                    # new fifth slot cannot be assumed to evict the right one.
                    if value == 0 or self.weights[i, j] > 0 or (self.weights[i] > 0).sum() < 4:
                        self.weights[i, j] = value
        shape = PackedShape()
        wanted = initial.copy()
        wanted[0] = [.4, .3, .2, 0, .1]
        collar.write_active_weights(shape, wanted, np.array([0]), names)
        np.testing.assert_array_equal(shape.weights, wanted)
        self.assertTrue(all(value == 0 for _, pairs in shape.calls[:5] for _, value in pairs))
        shape = PackedShape()
        shape.bone_weights.pop('e')
        with self.assertRaisesRegex(ValueError, 'cannot add'):
            collar.write_active_weights(shape, wanted, np.array([0]), names)
        self.assertEqual(shape.calls, [])

    def test_direct_weight_interpolation_has_covariance_residual(self):
        # Two source vertices have opposite bone ownership. Applying averaged
        # weights at their midpoint differs from averaging their posed positions.
        vertices = np.array([[0., 0, 0, 1], [2., 0, 0, 1]])
        transforms = np.array([np.eye(4), collar.rotation(2, 90)])
        posed = np.array([(transforms[i] @ vertices[i])[:3] for i in range(2)])
        midpoint = vertices.mean(axis=0)
        interpolated = .5 * sum((t @ midpoint)[:3] for t in transforms)
        self.assertGreater(np.linalg.norm(interpolated - posed.mean(axis=0)), .7)

    def test_rotation_is_not_a_gap_and_triangle_distance_uses_posed_normal(self):
        triangle = np.array([[[[0., 0, 0], [1, 0, 0], [0, 1, 0]]]])
        point = np.array([[[.25, .25, .2]]])
        distance, signed = collar.triangle_distances(point, triangle)
        self.assertAlmostEqual(distance.item(), .2)
        self.assertAlmostEqual(signed.item(), .2)
        r = collar.rotation(1, 90)[:3, :3]
        moved = point @ r.T
        d2, s2 = collar.triangle_distances(moved, triangle @ r.T)
        np.testing.assert_allclose(d2, distance)
        np.testing.assert_allclose(s2, signed)
        self.assertGreater(np.linalg.norm(moved - point), .3)

    def test_training_and_unseen_pose_corpus_is_deterministic_and_separate(self):
        poses, count = collar.pose_definitions(self.profile)
        other, _ = collar.pose_definitions(self.profile)
        self.assertEqual(count, 79)
        self.assertEqual(len(poses), 115)
        self.assertEqual(poses[count][0], 'heldout-combined-0')
        for (_, a), (_, b) in zip(poses, other):
            self.assertEqual(set(a), set(b))
            for name in a:
                np.testing.assert_array_equal(a[name], b[name])


if __name__ == '__main__':
    unittest.main()
