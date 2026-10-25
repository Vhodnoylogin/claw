"""Attachment invariants on synthetic surfaces; no installed/game fixtures."""
import copy
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("surface_collar", ROOT / "scripts/surface_collar.py")
surface = importlib.util.module_from_spec(spec)
spec.loader.exec_module(surface)


def grid():
    vertices = np.asarray([[x, y, 0.] for y in range(5) for x in range(5)], dtype=float)
    faces = []
    for y in range(4):
        for x in range(4):
            i = y * 5 + x
            faces.extend([[i, i + 1, i + 5], [i + 1, i + 6, i + 5]])
    return vertices, np.asarray(faces)


class SurfaceCollar(unittest.TestCase):
    def setUp(self):
        self.source, self.faces = grid()
        self.target = self.source + [0, 0, .2]
        self.rule = {"anchorBounds": [[-.1, -.1, -.1], [4.1, .1, .3]],
                     "anchorMaxDistance": .5, "anchorCountRange": [5, 5],
                     "width": 1.5, "weldDecimals": 5,
                     "maxIterations": 400, "solverTolerance": 1e-10}
        self.collar = surface.Collar(self.source, self.faces, self.target, self.faces, self.rule)

    def test_neutral_attachment_follows_source_and_preserves_offset(self):
        source_delta = np.tile([.1, -.4, .3], (len(self.source), 1))
        corrected = self.collar.reconcile(source_delta, np.zeros_like(self.target))
        metrics = self.collar.metrics(self.source + source_delta, self.target + corrected)
        self.assertLess(metrics["donorOffsetErrorMax"], 1e-10)
        np.testing.assert_array_equal(corrected[self.target[:, 1] >= 1.5], 0)

    def test_lobe_interior_and_original_arrays_are_unchanged(self):
        original = self.target.copy()
        delta = np.zeros_like(self.target)
        delta[22] = [0, 3, -2]
        corrected = self.collar.reconcile(np.tile([0, .3, -.2], (25, 1)), delta)
        np.testing.assert_array_equal(corrected[22], delta[22])
        np.testing.assert_array_equal(self.target, original)
        np.testing.assert_array_equal(delta[22], [0, 3, -2])

    def test_constraints_are_linear_for_combined_morph_coefficients(self):
        a = np.tile([0, .3, .2], (25, 1))
        b = np.tile([-.2, 0, .1], (25, 1))
        zero = np.zeros_like(a)
        combined = self.collar.reconcile(.25 * a + .75 * b, zero)
        separate = .25 * self.collar.reconcile(a, zero) + .75 * self.collar.reconcile(b, zero)
        np.testing.assert_allclose(combined, separate, atol=1e-8)

    def test_uv_split_copies_share_correction_without_topology_weld(self):
        target = np.concatenate([self.target, self.target[[0]]])
        faces = self.faces.copy()
        faces[0, 0] = 25
        rule = copy.deepcopy(self.rule)
        rule["anchorCountRange"] = [5, 6]
        collar = surface.Collar(self.source, self.faces, target, faces, rule)
        corrected = collar.reconcile(np.tile([0, .2, .1], (25, 1)), np.zeros_like(target))
        np.testing.assert_array_equal(corrected[0], corrected[25])
        self.assertEqual(len(corrected), 26)
        self.assertEqual(faces[0, 0], 25)

    def test_invalid_topology_bounds_and_field_are_rejected(self):
        expected = surface.signature(self.source, self.faces)
        surface.validate_geometry(self.source, self.faces, expected, 1e-6)
        with self.assertRaises(ValueError):
            surface.validate_geometry(self.source, self.faces[::-1], expected, 1e-6)
        with self.assertRaises(ValueError):
            surface.validate_geometry(self.source + [0, 0, .1], self.faces, expected, 1e-6)
        with self.assertRaises(ValueError):
            self.collar.reconcile(np.zeros((3, 3)), np.zeros_like(self.target))
        with self.assertRaises(ValueError):
            self.collar.reconcile(np.full_like(self.source, np.nan), np.zeros_like(self.target))

    def test_projected_triangle_anchor_is_not_nearest_vertex(self):
        binding = surface.Bindings([[.25, .25, .2]], self.source, self.faces)
        self.assertAlmostEqual(binding.distances[0], .2)
        np.testing.assert_allclose(binding.evaluate(self.source)[0], [.25, .25, 0])

    def test_card_binding_preserves_card_edge_lengths(self):
        vertices = np.asarray([[.4, .4, .2], [.6, .4, .2], [.4, .6, .2]])
        rule = {"mode": "cards", "weldDecimals": 5,
                "bounds": [[-1, -1, -1], [5, 5, 2]], "fade": [.1, .1, .1],
                "distanceFade": [.5, 1.]}
        layer = surface.Layer(vertices, [[0, 1, 2]], self.source, self.faces, rule)
        source_delta = self.source * [.1, .2, 0] + [0, 0, .3]
        changed = layer.reconcile(np.zeros_like(vertices), source_delta)
        np.testing.assert_allclose(changed[0], changed[1])
        np.testing.assert_allclose(changed[1], changed[2])

    def test_card_fade_retains_original_internal_deformation(self):
        vertices = np.asarray([[.4, .4, .2], [.6, .4, .2], [.4, .6, .2]])
        rule = {"mode": "cards", "weldDecimals": 5,
                "bounds": [[-1, -1, -1], [5, 5, 2]], "fade": [.1, .1, .1],
                "distanceFade": [.5, 1.]}
        layer = surface.Layer(vertices, [[0, 1, 2]], self.source, self.faces, rule)
        layer.weights[:] = .5
        old = np.asarray([[0., 0, 0], [1., 0, 0], [0., 0, 0]])
        changed = layer.reconcile(old, np.zeros_like(self.source))
        np.testing.assert_array_equal(changed[:, 0], [0, .5, 0])

    def test_actual_adapter_clears_existing_key_when_layer_becomes_zero(self):
        # Blender-shaped stubs exercise the real adapter read/write methods;
        # Collar and Layer are the production numeric implementations.
        adapter_spec = importlib.util.spec_from_file_location(
            "morphlib_adapter_regression", ROOT / "scripts/morphlib.py")
        adapter = importlib.util.module_from_spec(adapter_spec)
        with mock.patch.dict(sys.modules, {"mathutils": SimpleNamespace(Vector=np.asarray)}):
            adapter_spec.loader.exec_module(adapter)

        class Identity:
            def to_3x3(self):
                return self

            def inverted(self):
                return self

            def __matmul__(self, value):
                return np.asarray(value)

        class Keys(list):
            def get(self, name):
                return next((key for key in self if key.name == name), None)

            def __contains__(self, item):
                return self.get(item) is not None if isinstance(item, str) else super().__contains__(item)

            def __getitem__(self, item):
                return self.get(item) if isinstance(item, str) else super().__getitem__(item)

        key_name = ">CLAWAdapterRegression"
        def obj(vertices, delta=None, missing=False):
            def key(name, values):
                return SimpleNamespace(name=name, data=[SimpleNamespace(co=p.copy()) for p in values])
            keys = None if missing else SimpleNamespace(key_blocks=Keys([
                key("Basis", vertices), key(key_name, vertices + delta)]))
            result = SimpleNamespace(data=SimpleNamespace(shape_keys=keys), matrix_world=Identity())
            result.shape_key_add = lambda **kw: self.fail("A new all-zero layer key must not be created")
            return result

        source = np.asarray([[0., 0, 0], [1., 0, 0], [0., 1, 0]])
        target = source + [0, 0, .2]
        fur = source * .2 + [.2, .2, .1]
        faces = np.asarray([[0, 1, 2]])
        rule = dict(self.rule, anchorBounds=[[-.1, -.1, -.1], [1.1, 1.1, .3]],
                    anchorCountRange=[3, 3])
        collar = surface.Collar(source, faces, target, faces, rule)
        skin = np.concatenate([source, target])
        skin_faces = np.asarray([[0, 1, 2], [3, 4, 5]])
        layer_rule = {"mode": "cards", "weldDecimals": 5,
                      "bounds": [[-1, -1, -1], [2, 2, 2]],
                      "fade": [.1, .1, .1], "distanceFade": [.5, 1.]}
        layer = surface.Layer(fur, faces, skin, skin_faces, layer_rule)
        session = adapter.SurfaceCollarSession.__new__(adapter.SurfaceCollarSession)
        session.np = np
        session.vertices = {"body": source, "head": target, "fur": fur, "new_fur": fur}
        session.objects = {"body": obj(source, np.zeros_like(source)),
                           "head": obj(target, np.ones_like(target)),
                           "fur": obj(fur, np.asarray([[0., 0, 0], [1., 0, 0], [0., 0, 0]])),
                           "new_fur": obj(fur, missing=True)}
        session.skin_names = ["body", "head"]
        session.collars = [({"source": "body", "target": "head"}, collar)]
        session.layers = [("fur", layer), ("new_fur", layer)]
        session.recipe = {"fieldEpsilon": 1e-8}
        session.report = {"morphs": {}}
        session.log = lambda message: None
        session.reconcile_morphs()
        np.testing.assert_array_equal(session._key_delta("fur", key_name), 0)
        np.testing.assert_array_equal(session._key_delta("head", key_name), 0)
        self.assertIsNone(session.objects["new_fur"].data.shape_keys)


if __name__ == "__main__":
    unittest.main()
