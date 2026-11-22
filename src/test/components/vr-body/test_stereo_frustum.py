import unittest

import numpy as np

from stereo_frustum import clip_frustum


LIMITS = dict(left=-1, right=1, bottom=-1, top=1, near=1, far=4)


class StereoFrustumTests(unittest.TestCase):
    def test_depth_counts_only_actual_frustum_intersections(self):
        triangles = [
            [[-.5, -.5, 2], [.5, -.5, 2.5], [0, .5, 3]],
            [[2, 0, 1], [3, -1, 2], [3, 1, 2]],
            [[0, 0, 5], [1, 0, 5], [0, 1, 5]],
            [[0, 0, -3], [1, 0, -3], [0, 1, -3]],
        ]
        self.assertEqual(clip_frustum(triangles, **LIMITS),
                         dict(intersectingTriangles=1, crossingNearTriangles=0, nearestDepth=2.0))

    def test_clips_surface_even_when_no_vertex_is_in_frustum(self):
        triangles = [
            [[-6, -1, 2], [6, -1, 2], [0, 6, 2]],
            [[1.9, 4, 2], [4, 1.9, 2], [4, 4, 2]],
        ]
        self.assertEqual(clip_frustum(triangles, **LIMITS),
                         dict(intersectingTriangles=1, crossingNearTriangles=0, nearestDepth=2.0))

    def test_near_crossings_are_counted_only_within_side_limits(self):
        triangles = [
            [[0, 0, .5], [.5, -.5, 2], [-.5, .5, 2]],
            [[3, 0, .5], [2, 1, 1.5], [0, 0, 3]],
            [[0, 0, 0], [0, .5, .5], [0, 0, 1]],
        ]
        self.assertEqual(clip_frustum(triangles, **LIMITS),
                         dict(intersectingTriangles=3, crossingNearTriangles=1, nearestDepth=1.0))

    def test_asymmetric_side_slopes(self):
        triangles = [[[-1.5, 0, 2], [-1.5, .25, 2], [-1.25, 0, 2]]]
        asymmetric = LIMITS | dict(left=-.5, right=.1, bottom=-.2, top=.8)
        self.assertEqual(clip_frustum(triangles, **asymmetric),
                         dict(intersectingTriangles=0, crossingNearTriangles=0, nearestDepth=None))

    def test_empty_and_invalid_numeric_inputs(self):
        triangles = np.empty((0, 3, 3))
        self.assertEqual(clip_frustum(triangles, **LIMITS),
                         dict(intersectingTriangles=0, crossingNearTriangles=0, nearestDepth=None))
        for invalid in (np.zeros((3, 3)), np.full((1, 3, 3), np.nan)):
            with self.subTest(shape=invalid.shape), self.assertRaises(ValueError):
                clip_frustum(invalid, **LIMITS)
        for invalid in (dict(near=0), dict(far=1), dict(left=1), dict(top=float('inf'))):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                clip_frustum(triangles, **(LIMITS | invalid))


if __name__ == '__main__':
    unittest.main()
