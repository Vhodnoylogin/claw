"""Measured-envelope contrast gates; synthetic dimensions, no donor/native API."""
import copy
import math
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[4]/'src/main/python/build-tools'))
import expressive_contrast as contrast


def section(radius, front):
    return {'hullArea': math.pi * radius * radius, 'front': front}


class ExpressiveContrastTests(unittest.TestCase):
    def test_diameter_contrast_uses_actual_envelope_not_slider_coefficients(self):
        sections = {'minimum': section(1, 9), 'neutral': section(2, 9), 'maximum': section(3, 9)}
        self.assertAlmostEqual(contrast.contrast('upperArm', sections), 4)
        self.assertAlmostEqual(contrast.effective_diameter(section(3, 0)), 6)
        sections['maximum']['hullArea'] = float('nan')
        with self.assertRaises(ValueError):
            contrast.contrast('upperArm', sections)

    def test_abdomen_measures_front_change_from_neutral(self):
        sections = {'minimum': section(1, -100), 'neutral': section(2, 4), 'maximum': section(3, 9)}
        self.assertEqual(contrast.contrast('abdomen', sections), 5)
        sections['maximum']['front'] = 4
        with self.assertRaises(ValueError):
            contrast.contrast('abdomen', sections)

    def test_missing_coat_is_not_invented_and_missing_outer_cannot_pass(self):
        reference = {region: {family: {'contrast': None if family == 'coat' else 4.}
                             for family in contrast.FAMILIES} for region in contrast.REGIONS}
        candidate = copy.deepcopy(reference)
        for region in candidate:
            for family in ('skin', 'outer'):
                candidate[region][family]['contrast'] = 5.
        rows = contrast.compare_measures(reference, candidate)
        self.assertTrue(all(row['outer']['passesRequiredRatio'] for row in rows.values()))
        self.assertIsNone(rows['thigh']['coat']['ratio'])
        candidate['thigh']['outer']['contrast'] = None
        self.assertFalse(contrast.compare_measures(reference, candidate)['thigh']['outer']['passesRequiredRatio'])
        candidate['thigh']['outer']['contrast'] = 4.999
        self.assertFalse(contrast.compare_measures(reference, candidate)['thigh']['outer']['passesRequiredRatio'])
        reference['thigh']['outer']['contrast'] = 0
        with self.assertRaises(ValueError):
            contrast.compare_measures(reference, candidate)

    def test_region_masks_separate_right_thigh_from_midline_other_leg_and_front_fur(self):
        points = np.array([[14., 0, 62], [0, 0, 62], [-14, 0, 62], [14, 30, 62]])
        np.testing.assert_array_equal(contrast.region_mask(points, 'thigh'), [True, False, False, False])
        with self.assertRaises(ValueError):
            contrast.region_mask(points, 'unknown')


if __name__ == '__main__':
    unittest.main()
