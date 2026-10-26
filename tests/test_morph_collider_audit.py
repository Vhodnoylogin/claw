"""Numerical counterexamples for sampled Havok clearance reporting."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

import numpy as np

PATH = Path(__file__).resolve().parents[1] / "scripts/audit-morph-colliders.py"
SPEC = importlib.util.spec_from_file_location("morph_collider_audit", PATH)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class ClearanceTests(unittest.TestCase):
    def test_sphere_degenerate_axis_and_segment_endcaps(self):
        sphere = {"p1": [0, 0, 0], "p2": [0, 0, 0], "radius": 2}
        np.testing.assert_allclose(AUDIT.signed_distances([[0, 0, 0], [3, 0, 0]], [sphere]), [-2, 1])
        cap = {**sphere, "p2": [0, 0, 4]}
        np.testing.assert_allclose(AUDIT.signed_distances([[0, 0, 7], [3, 0, 2]], [cap]), [1, 1])

    def test_union_uses_nearest_capsule_not_mean(self):
        caps = [{"p1": [x, 0, 0], "p2": [x, 0, 0], "radius": 1} for x in [0, 20]]
        self.assertAlmostEqual(AUDIT.signed_distances([[0, 0, 0]], caps)[0], -1)

    def test_hidden_overgrowth_reported_by_depth(self):
        row = AUDIT.metrics([[1, 0, 0], [-1, 0, 0]], [{"p1": [0, 0, 0], "p2": [0, 0, 0], "radius": 100}])
        self.assertEqual(row["outsideFraction"], 0)
        self.assertEqual(row["insideCapsuleProxyP95"], 99)
        self.assertFalse(row["interiorIsUnionBoundaryDistance"])

    def test_overlapping_union_interior_is_explicit_proxy(self):
        caps = [{"p1": [x, 0, 0], "p2": [x, 0, 0], "radius": 1} for x in [-.5, .5]]
        row = AUDIT.metrics([[0, 0, 0]], caps)
        self.assertAlmostEqual(row["insideCapsuleProxyP95"], .5)
        self.assertNotAlmostEqual(row["insideCapsuleProxyP95"], np.sqrt(.75))
        self.assertFalse(row["interiorIsUnionBoundaryDistance"])
        self.assertNotIn("insideDepthP95", row)
        self.assertNotIn("absoluteDistanceP95", row)

    def test_invalid_capsules_refused(self):
        for radius in [0, -1, float("nan")]:
            with self.assertRaises(ValueError):
                AUDIT.signed_distances([[0, 0, 0]], [{"p1": [0, 0, 0], "p2": [0, 0, 0], "radius": radius}])

    def test_sampling_explicitly_includes_singletons_and_mixtures(self):
        states = AUDIT.sample_states(["B", "A"])
        self.assertEqual(states[0]["values"], {})
        self.assertEqual(states[1]["values"], {"A": 1})
        self.assertEqual(states[-2]["values"], {"A": 1, "B": 1})
        self.assertEqual(states[-1], {"name": "return-neutral", "values": {}})

    def test_full_rest_lbs_product_and_morph_delta(self):
        global_to_skin = np.eye(4)
        global_to_skin[0, 3] = -2
        skin_to_bone = np.eye(4)
        skin_to_bone[0, 3] = 4
        rest_node = np.array([[0, -1, 0, 10], [1, 0, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
        matrix = .25 * (rest_node @ skin_to_bone @ global_to_skin) + .75 * np.eye(4)
        np.testing.assert_allclose(AUDIT.apply_lbs(matrix[None], [[3, 2, 1]]), [[4.25, 2.75, 1]])
        np.testing.assert_allclose(AUDIT.apply_lbs(matrix[None], [[4, 2, 1]]), [[5, 3, 1]])

    def test_rounded_public_frame_probes_recover_rotation_and_translation(self):
        true = np.array([[0, -1, 0, 3.1234], [1, 0, 0, -6.7891], [0, 0, 1, 9.8765], [0, 0, 0, 1]])
        def read(endpoint):
            return np.round((true @ np.r_[endpoint, 1])[:3], 3)
        inferred, receipt = AUDIT.infer_frame(read)
        np.testing.assert_allclose(inferred @ [17, -5, 4, 1], true @ [17, -5, 4, 1], atol=.001)
        self.assertLessEqual(receipt["heldoutMaxCoordinateResidual"], .005)

    def test_nonlinear_or_sheared_probe_refused(self):
        with self.assertRaises(ValueError):
            AUDIT.infer_frame(lambda p: [p[0] + .2 * p[1], p[1], p[2]])
        with self.assertRaises(ValueError):
            AUDIT.infer_frame(lambda p: [p[0] + .0001 * p[0] * p[0], p[1], p[2]])

    def test_actual_posed_fit_covers_cylinder_end_rings(self):
        points = [[x, 2 * np.cos(a), 2 * np.sin(a)] for x in [-4, 4] for a in np.linspace(0, 2 * np.pi, 64, endpoint=False)]
        cap = AUDIT.fit_capsule(points, 100)
        self.assertIsNotNone(cap)
        self.assertLessEqual(AUDIT.signed_distances(points, [cap]).max(), 1e-8)

    def test_serialized_bundle_geometry_and_properties_must_survive(self):
        cap = {"p1": [0, 0, 0], "p2": [0, 0, 3], "radius": 2}
        row = {"bone": "Test", "kind": "bhkRigidBody", "physics": {"mass": 5}, "ragdoll": {}, "capsules": [cap, cap]}
        self.assertEqual(AUDIT.verify_serialized([row], [row], [row])["capsules"], 2)
        for replacement in [{**row, "capsules": [cap]}, {**row, "physics": {"mass": 10}},
                            {**row, "capsules": [{**cap, "radius": 3}, cap]}]:
            with self.assertRaises(ValueError):
                AUDIT.verify_serialized([row], [replacement], [row])

    def test_skin_selection_keeps_all_weights_for_lbs_and_records_omissions(self):
        def buf(x=0):
            return SimpleNamespace(rotation=np.eye(3), translation=[x, 0, 0], scale=1)
        root = SimpleNamespace(name="Root", parent=None, global_transform=buf())
        nodes = {"Root": root}
        for name, x in [("A", 10), ("B", -10), ("C", 0)]:
            nodes[name] = SimpleNamespace(name=name, parent=root, global_transform=buf(x))
        shape = SimpleNamespace(name="body", verts=np.zeros((3, 3)), has_global_to_skin=True,
                                global_to_skin=buf(), transform=buf(999),
                                bone_weights={"A": [(0, .6), (1, .4), (2, .4)],
                                              "B": [(0, .4), (1, .6), (2, .35)], "C": [(2, .25)]},
                                get_shape_skin_to_bone=lambda name: buf())
        library = SimpleNamespace(NifFile=lambda path: SimpleNamespace(shapes=[shape]) if path == "body" else SimpleNamespace(nodes=nodes))
        skins, summary = AUDIT.skin_data(library, "body", "skeleton", ["body"], ["Root"])
        np.testing.assert_allclose(AUDIT.apply_lbs(skins["body"]["matrices"], shape.verts), [[2, 0, 0], [-2, 0, 0], [.5, 0, 0]])
        self.assertEqual(summary[0]["selected"], 2)
        self.assertEqual(summary[0]["omitted"]["belowOwnershipThreshold"], 1)
        self.assertEqual(skins["body"]["selected"]["Root"].tolist(), [0, 1])
        shape.has_global_to_skin = False
        with self.assertRaises(ValueError):
            AUDIT.skin_data(library, "body", "skeleton", ["body"], ["Root"])


if __name__ == "__main__":
    unittest.main()
