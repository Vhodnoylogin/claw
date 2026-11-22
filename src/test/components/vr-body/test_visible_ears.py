"""Controls for the normalized, bilateral ear-skin selection."""
import unittest

import numpy as np

from stage_visible_ears import ear_faces


class VisibleEarSelectionTests(unittest.TestCase):
    def setUp(self):
        self.faces = np.array([[0, 2, 3], [1, 3, 4], [2, 3, 4]])
        self.weights = np.array([[.6, 0, 0, 0, .4], [0, 0, .3, 0, .3],
                                 [.3, 0, 0, 0, .4], [0, 0, 0, 0, 1], [0, 0, 0, .4, .6]])

    def test_both_ears_preserve_the_unselected_head(self):
        left, right = ear_faces(self.faces, self.weights, [0, 1, 2, 3])
        np.testing.assert_array_equal(left, [True, False, False])
        np.testing.assert_array_equal(right, [False, True, False])

    def test_cross_ear_face_is_rejected(self):
        self.faces[0, 1] = 1
        with self.assertRaisesRegex(ValueError, 'distinct ears'):
            ear_faces(self.faces, self.weights, [0, 1, 2, 3])

    def test_zero_skin_weight_is_rejected(self):
        self.weights[0] = 0
        with self.assertRaisesRegex(ValueError, 'skin weight sums'):
            ear_faces(self.faces, self.weights, [0, 1, 2, 3])
