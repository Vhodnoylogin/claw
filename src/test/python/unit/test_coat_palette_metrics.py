# SPDX-FileCopyrightText: 2026 CLAW contributors
from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src/main/python/build-tools"))
import coat_palette_metrics as m


class CoatPaletteMetricsTests(unittest.TestCase):
    def test_fully_transparent_colours_do_not_bias_visible_alpha_weighted_average(self):
        rgba = np.array([[[255, 0, 0, 255], [0, 255, 0, 0]],
                         [[0, 0, 255, 255], [255, 255, 255, 0]]], dtype=np.uint8)
        result = m.sample_rgba(rgba)
        self.assertEqual(result["alphaWeightedLinearMeanRgb"], [.5, 0, .5])
        self.assertEqual(result["visibleSamplePixels"], 2)
        self.assertEqual(result["sampleCoverageAlpha90"], .5)

    def test_partial_alpha_weights_actual_visible_texels(self):
        rgba = np.array([[[255, 0, 0, 255], [0, 0, 255, 85]]], dtype=np.uint8)
        result = m.sample_rgba(rgba)
        np.testing.assert_allclose(result["alphaWeightedLinearMeanRgb"], [.75, 0, .25])

    def test_no_fabricated_rgb_for_fully_transparent_texture(self):
        result = m.sample_rgba(np.zeros((4, 4, 4), dtype=np.uint8))
        self.assertFalse(result["available"])
        self.assertNotIn("alphaWeightedLinearMeanRgb", result)

    def test_sampling_is_bounded_even_for_a_highly_rectangular_texture(self):
        rgba = np.full((1, 1024, 4), 255, dtype=np.uint8)
        result = m.sample_rgba(rgba, 16)
        self.assertLessEqual(result["samplePixels"], 16)
        self.assertEqual(result, m.sample_rgba(rgba, 16))


if __name__ == "__main__":
    unittest.main()
