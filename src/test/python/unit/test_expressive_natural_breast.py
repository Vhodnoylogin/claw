"""Natural breast growth is a female-only, bounded public field contract."""
import json
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[4]/'src/main/python/build-tools'))
import expressive_body as body


class NaturalBreastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recipe = json.loads((body.ROOT/'src/main/resources/recipes/expressive-body-v3.json').read_text())
        cls.rule = cls.recipe['parameters']['femaleBreast']

    def test_growth_spreads_and_settles_instead_of_sharpening_apex(self):
        # Chest lobe, lower lobe and projecting apex all retain outward mass.
        points = np.array([[9., 26., 101.], [9., 26., 94.], [9., 38., 101.]])
        delta = body.breast_field(points, self.rule)
        self.assertTrue(np.all(delta[:, 0] > 0))
        self.assertTrue(np.all(delta[:, 1] > 0))
        self.assertTrue(np.all(-delta[:, 2] > delta[:, 1]))
        self.assertGreater(-delta[1, 2], -delta[0, 2])
        self.assertLess(delta[2, 1], delta[0, 1])

    def test_midline_is_continuous_and_left_right_growth_is_symmetric(self):
        right = np.array([[9., 30., 99.], [20., 26., 102.], [1e-8, 30., 99.]])
        left = right * [-1, 1, 1]
        np.testing.assert_allclose(body.breast_field(right, self.rule)*[-1, 1, 1],
                                   body.breast_field(left, self.rule), atol=1e-12)
        self.assertLess(abs(body.breast_field(right, self.rule)[-1, 0]), 1e-12)

    def test_face_back_feet_and_support_boundaries_are_fixed(self):
        points = np.array([[0., 65., 120.], [9., -5., 99.], [9., 26., 0.],
                           [9., 26., 82.], [30., 26., 99.], [9., 48., 99.]])
        np.testing.assert_array_equal(body.breast_field(points, self.rule), np.zeros_like(points))

    def test_existing_recipes_and_male_inventory_keep_breast_protected(self):
        self.assertNotIn(body.BREAST, body.authored_names(self.recipe, 'male'))
        self.assertIn(body.BREAST, body.authored_names(self.recipe, 'female'))
        for version in ('v1', 'v2'):
            recipe = json.loads((body.ROOT/f'src/main/resources/recipes/expressive-body-{version}.json').read_text())
            self.assertNotIn(body.BREAST, body.authored_names(recipe, 'female'))

    def test_invalid_dimensions_are_rejected(self):
        for key, value in [('down', float('nan')), ('lobeWidth', 0), ('forward', True),
                           ('apexForwardFraction', 1.1)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                body.breast_field(np.array([[9., 30., 99.]]), {**self.rule, key: value})

    def test_muzzle_mask_protects_breast_and_neck_and_keeps_full_forward_jaw(self):
        rule = self.recipe['parameters']['headIsolation']
        points = np.array([[9., 30., 99.], [0., 44., 115.], [0., 50., 115.],
                           [0., 56., 110.], [0., 72., 115.]])
        support = body.muzzle_support(points, rule)
        np.testing.assert_array_equal(support[:2], [0, 0])
        self.assertGreater(support[2], 0)
        self.assertLess(support[2], 1)
        np.testing.assert_array_equal(support[3:], [1, 1])
        # UV splits and matching skin/mouth coordinates get the same support.
        self.assertEqual(body.muzzle_support(np.repeat(points[2:3], 2, axis=0), rule)[0], support[2])


if __name__ == '__main__':
    unittest.main()
