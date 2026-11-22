from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src/main/python/physics"))
from contact_fit import triangle_distance
from peer_contact_geometry import plan, provider_faces


class ContactAimTests(unittest.TestCase):
    def setUp(self):
        self.points = np.array([(0, 0, 0), (.0625, 0, 0), (0, .0625, 0), (0, 0, .0625)])
        self.vertices = np.array([(0., 0., 0.), (4., 0., 0.), (0., 4., 0.)])
        self.faces = np.array([(0, 1, 2)])
        self.weights = np.ones((3, 1))
        self.exposed = np.ones(3, dtype=bool)

    def aim(self):
        return plan(self.vertices, self.faces, self.exposed, self.weights, self.points, 1.,
                    lambda point: point[2] > 0, triangle_distance)[1][0]

    def test_rotation_bound_and_global_far_clearance(self):
        trial = self.aim()
        self.assertEqual(trial["face"], 0)
        self.assertGreater(trial["projectionMargin"], 1.)
        self.assertGreater(trial["planeMargin"], .6)
        self.assertAlmostEqual(trial["farClearance"], 1.)
        self.vertices = np.vstack((self.vertices, self.vertices + (0, 0, 2.0625)))
        self.faces = np.array([(0, 1, 2), (3, 4, 5)])
        self.weights = np.ones((6, 1))
        self.exposed = np.array([True] * 3 + [False] * 3)
        self.assertIsNone(self.aim())

    def test_rejects_a_probe_that_cannot_stay_inside_the_face(self):
        self.vertices /= 30
        self.assertIsNone(self.aim())

    def test_retained_membership_uses_a_strict_per_corner_threshold(self):
        faces = np.array([(0, 1, 2), (1, 2, 3)])
        weights = np.array([[np.finfo(np.float32).eps], [0.], [0.], [.5]])
        self.assertEqual(provider_faces(faces, weights).tolist(), [1])


if __name__ == "__main__":
    unittest.main()
