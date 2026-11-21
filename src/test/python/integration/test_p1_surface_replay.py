import unittest

import numpy as np

if __package__:
    from .p1_surface_replay import node_matrix, surface_contribution
else:
    from p1_surface_replay import node_matrix, surface_contribution


class SurfaceContributionTests(unittest.TestCase):
    def test_rotation_and_translation_use_the_source_vertex_and_all_weights(self):
        before = node_matrix({"rotation": np.eye(3).ravel(), "translation": [0, 0, 0], "scale": 1})
        after = node_matrix({"rotation": [0, -1, 0, 1, 0, 0, 0, 0, 1],
                             "translation": [0, 0, 2], "scale": 1})
        vertices = np.array([[2, 1, 0], [0, 0, 0]])
        weights = np.array([[.25, .5], [0, 1]])
        raw, normalized = surface_contribution(vertices, weights, weights[:, :1].T, np.stack([after-before]))
        np.testing.assert_allclose(raw, [[-.75, .25, .5], [0, 0, 0]])
        np.testing.assert_allclose(normalized, [[-1., 1/3, 2/3], [0, 0, 0]])

    def test_opposing_changes_from_two_measured_bones_are_added(self):
        moves = np.zeros((2, 4, 4))
        moves[:, 0, 3] = [3, -1]
        raw, normalized = surface_contribution(np.zeros((1, 3)), np.array([[.25, .75]]),
                                               np.array([[.25], [.75]]), moves)
        np.testing.assert_array_equal(raw, [[0, 0, 0]])
        np.testing.assert_array_equal(normalized, raw)
