import sys
import os
from pathlib import Path
import struct
import unittest
from types import SimpleNamespace
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import neck_bounds as bounds


class NeckBoundsTests(unittest.TestCase):
    def test_additive_combination_and_independent_weight_are_both_enclosed(self):
        low = np.asarray([[0., 0, 0]])
        high = np.asarray([[0., 0, 3]])
        lo, hi = bounds.local_boxes(low, high, [np.asarray([[2., 0, 0]]), np.asarray([[0., -4, 0]])], np.eye(4))
        np.testing.assert_array_equal(lo, [[0, -4, 0]])
        np.testing.assert_array_equal(hi, [[2, 0, 3]])
        self.assertAlmostEqual(bounds.reach(lo, hi, [0, 0, 0]), np.sqrt(29))

    def test_b_frame_excludes_nonidentity_global_to_skin(self):
        bind = np.eye(4); bind[0, 3] = 2
        lo, hi = bounds.local_boxes([[1., 0, 0]], [[1., 0, 0]], [], bind)
        np.testing.assert_array_equal(lo, [[3, 0, 0]])
        np.testing.assert_array_equal(hi, lo)
        # A separate C translation must not enter a NiSkinData bone sphere.
        frame = np.eye(4); frame[0, 3] = 10
        wrong, _ = bounds.local_boxes([[1., 0, 0]], [[1., 0, 0]], [], bind@frame)
        self.assertEqual(wrong[0, 0], 13)

    def test_outward_float32_never_rounds_radius_inward(self):
        value = 1.00000003
        self.assertLess(float(np.float32(value)), value)
        self.assertGreaterEqual(bounds.outward_float32(value), value)
        self.assertEqual(bounds.outward_float32(2.), 2.)

    def test_complete_tiny_serialized_delta_cannot_be_dropped(self):
        lo, hi = bounds.local_boxes([[1., 0, 0]], [[1., 0, 0]], [np.asarray([[.00005, 0, 0]])], np.eye(4))
        self.assertGreater(bounds.reach(lo, hi, [0, 0, 0]), 1.)

    def test_opaque_diff_rejects_unrelated_byte_center_change_and_shrink(self):
        before = b'opaque-prefix!' + struct.pack('<4f', 1, 2, 3, 4) + b'unknown-controller-alpha-tail'
        row = {'offset': 14, 'oldSphere': [1., 2., 3., 4.], 'newSphere': [1., 2., 3., 5.]}
        after = bounds.patch_spheres(before, [row])
        self.assertTrue(bounds.verify_bytes(before, after, [row])['onlyNewNeckSphereFieldsMayChange'])
        damaged = bytes([after[0]^1])+after[1:]
        with self.assertRaisesRegex(ValueError, 'Opaque'):
            bounds.verify_bytes(before, damaged, [row])
        for sphere in ([1, 2, 3, 3], [2, 2, 3, 5]):
            with self.assertRaises(ValueError):
                bounds.patch_spheres(before, [{**row, 'newSphere': sphere}])

    def test_uninitialized_new_bone_sphere_is_refused(self):
        shape = bytearray(92); struct.pack_into('<I', shape, 88, 1)
        data = bytes(52)+struct.pack('<IB', 1, 1)+bytes(68)+struct.pack('<H', 0)
        container = SimpleNamespace(blocks=[bytes(shape), struct.pack('<I', 2), data],
                                    kind=lambda index: {1: 'BSDismemberSkinInstance', 2: 'NiSkinData'}[index])
        with self.assertRaisesRegex(ValueError, 'uninitialized'):
            bounds.neck_record(container, SimpleNamespace(id=0, bone_names=[bounds.NECK]))


@unittest.skipUnless(os.environ.get('CLAW_VR_NECK_BOUNDS_ROOT') and os.environ.get('CLAW_VR_NECK_BOUNDS_SOURCE'),
                     'Explicit completed new-Neck sphere output and composed source roots required')
class NativeNeckBoundsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(os.environ['CLAW_VR_NECK_BOUNDS_ROOT'])
        cls.source = Path(os.environ['CLAW_VR_NECK_BOUNDS_SOURCE'])
        cls.report = bounds.resource.read_json(cls.root/'neck-bounds-report.json')
        cls.api, _, cls.Trip, _ = bounds.resource.dependencies()

    def test_actual_four_endpoints_change_only_the_28_new_neck_spheres(self):
        for sex in ('female', 'male'):
            for endpoint in (0, 1):
                source = self.source/sex/f'first-person_{endpoint}.nif'
                target = self.root/'resources'/sex/source.name
                ledger = self.report['bodies'][sex+str(endpoint)]['editLedger']
                self.assertEqual(len(ledger), 7)
                bounds.verify_bytes(source.read_bytes(), target.read_bytes(), ledger)
                self.assertEqual(bounds.resource.sha256(target), self.report['resources'][sex+'/'+target.name])
            tri = sex+'bodywerewolf.tri'
            self.assertEqual((self.source/sex/tri).read_bytes(), (self.root/'resources'/sex/tri).read_bytes())

    def test_native_explicit_morph_corner_random_and_weight_samples_are_inside(self):
        # This directly constructs complete raw morphed positions, then applies
        # native B. It does not call the writer's coordinate-box construction.
        rng = np.random.default_rng(20261028)
        for sex in ('female', 'male'):
            original = [self.api.NifFile(str(self.source/sex/f'first-person_{i}.nif')) for i in (0, 1)]
            public = self.Trip.from_filepath(str(self.source/sex/(sex+'bodywerewolf.tri'))).shapes
            fields, _ = bounds.morph_quality.decode_fields((self.source/sex/(sex+'bodywerewolf.tri')).read_bytes(),
                              public, {s.name: len(s.verts) for s in original[0].shapes})
            by_endpoint = [{s.name: s for s in n.shapes} for n in original]
            for endpoint in (0, 1):
                path = self.root/'resources'/sex/f'first-person_{endpoint}.nif'
                actual = self.api.NifFile(str(path)); container = bounds.head_split.Nif(path.read_bytes())
                for shape in actual.shapes:
                    if bounds.NECK not in shape.bone_names:
                        continue
                    ids = np.asarray([i for i, w in shape.bone_weights[bounds.NECK] if w > 0], int)
                    low, high = [np.asarray(sh[shape.name].verts)[ids] for sh in by_endpoint]
                    delta = np.stack([value[ids] for (name, _), value in fields.items() if name == shape.name])
                    coefficients = np.r_[np.zeros((1, len(delta))), np.ones((1, len(delta))),
                                          np.eye(len(delta)), rng.uniform(0, 1, (12, len(delta)))]
                    bind = bounds.rig.matrix(shape.get_shape_skin_to_bone(bounds.NECK))
                    _, _, sphere = bounds.neck_record(container, shape)
                    for values in coefficients:
                        moved = np.einsum('m,mnj->nj', values, delta)
                        for weight in (0., .37, 1.):
                            vertices = low+weight*(high-low)+moved
                            local = vertices@bind[:3, :3].T+bind[:3, 3]
                            self.assertLessEqual(float(np.linalg.norm(local-sphere[:3], axis=1).max()), sphere[3])


if __name__ == '__main__':
    unittest.main()
