"""Discriminate real attachment drift from rotated donor offsets and morph changes."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location("claw_attachment_audit_tests", ROOT / "src/main/python/physics/attachment_audit.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class AttachmentMeasurements(unittest.TestCase):
    def geometry(self):
        triangle = np.array([[[0., 0, 0], [2., 0, 0], [0., 2, 0]]])
        bary = np.array([[.5, .25, .25]])
        root = np.array([[.5, .5, 2.]])
        rotation = np.array([[1., 0, 0], [0, 0, -1.], [0, 1., 0]])
        rotations = np.array([[np.eye(3)], [rotation]])
        posed_roots = np.array([root, root @ rotation.T])
        posed_triangles = np.array([triangle, triangle @ rotation.T])
        weights = np.ones((1, 3, 1))
        return posed_roots, posed_triangles, bary, weights, rotations, root, triangle

    def test_rigidly_rotated_nonzero_donor_gap_is_not_attachment_drift(self):
        values = audit.measure_binding(*self.geometry())
        np.testing.assert_allclose(values["poseTransportedOffsetDrift"], 0, atol=1e-12)
        np.testing.assert_allclose(values["neutralOffsetResidual"], 0, atol=1e-12)
        np.testing.assert_allclose(values["rootToSkinDistance"], 2)
        np.testing.assert_allclose(values["signedTriangleStandOff"], 2)
        # Subtracting the unrotated rest offset would falsely report a gap defect.
        args = self.geometry()
        self.assertGreater(np.linalg.norm((args[0][1] - args[1][1].mean(axis=1)) - [0, 0, 2]), 2)

    def test_extra_root_translation_is_real_pose_drift(self):
        args = list(self.geometry())
        args[0][1, 0] += [0, 0, .3]
        measured = audit.measure_binding(*args)
        self.assertAlmostEqual(measured["poseTransportedOffsetDrift"][1, 0], .3)
        self.assertAlmostEqual(measured["neutralOffsetResidual"][1, 0], .3)

    def test_static_morph_change_is_not_hidden_inside_current_rest_offset(self):
        args = list(self.geometry())
        # A changed morph moves the root by .4, then its pose rotates coherently.
        args[0][0, 0] += [0, 0, .4]
        args[0][1, 0] += [0, -.4, 0]
        measured = audit.measure_binding(*args)
        np.testing.assert_allclose(measured["staticMorphOffsetChange"], .4)
        np.testing.assert_allclose(measured["poseTransportedOffsetDrift"], 0, atol=1e-12)
        np.testing.assert_allclose(measured["neutralOffsetResidual"], .4)

    def test_transport_normalizes_each_skin_vertex_before_barycentric_blending(self):
        args = list(self.geometry())
        args[3] = np.array([[[2., 0], [0, 1.], [0, 3.]]])
        args[4] = np.repeat(args[4], 2, axis=1)
        measured = audit.measure_binding(*args)
        np.testing.assert_allclose(measured["poseTransportedOffsetDrift"], 0, atol=1e-12)

    def test_raw_and_normalized_lbs_positions_remain_distinct_diagnostics(self):
        _, rig = audit.helpers()
        vertices = np.array([[.5, .5, 2.]])
        matrices = np.array([[np.eye(4)], [np.eye(4)]])
        matrices[1, 0, 0, 3] = 1
        weights = np.array([[.99975]])
        raw = rig.lbs(vertices, weights, matrices, False)
        normalized = rig.lbs(vertices, weights, matrices, True)
        self.assertGreater(float(np.linalg.norm(raw-normalized)), .0001)
        np.testing.assert_allclose(normalized[1] - normalized[0], [[1., 0, 0]])
        np.testing.assert_allclose(raw[1] - raw[0], [[.99975, 0, 0]])

    def test_invalid_bary_weights_nonfinite_and_nonrest_first_pose_fail(self):
        for change in ("bary", "weight", "nan", "first-pose"):
            args = list(self.geometry())
            if change == "bary": args[2][0] = [-1., 1., 1.]
            if change == "weight": args[3][:] = 0
            if change == "nan": args[0][0, 0, 0] = float("nan")
            if change == "first-pose": args[4][0, 0, 0, 0] = 2
            with self.subTest(change=change), self.assertRaises(ValueError):
                audit.measure_binding(*args)

    def test_degenerate_triangle_sign_is_explicitly_unavailable(self):
        args = list(self.geometry())
        args[1][:] = 0
        measured = audit.measure_binding(*args)
        self.assertFalse(measured["signedValid"].any())
        report = audit.summarize(measured, [("rest", {}, "ordinary"), ("turned", {}, "ordinary")])
        signed = report["poseGroups"]["ordinary"]["signedTriangleStandOff"]
        self.assertEqual(signed["degenerateTriangleSamples"], 2)
        self.assertIsNone(signed["max"])
        json.dumps(report, allow_nan=False)

    def test_worst_drift_identifies_the_declared_pose_and_root(self):
        args = list(self.geometry())
        args[0][1, 0, 0] += .7
        report = audit.summarize(audit.measure_binding(*args), [("rest", {}, "ordinary"), ("test-pose", {}, "heldout")])
        worst = report["poseGroups"]["heldout"]["poseTransportedOffsetDrift"]
        self.assertEqual(worst["worstPose"], "test-pose")
        self.assertEqual(worst["worstRootIndex"], 0)
        self.assertAlmostEqual(worst["max"], .7)

    def test_full_and_fade_followers_are_not_conflated(self):
        args = list(self.geometry())
        # Duplicate one root: the fade root has the larger intentional underfollow.
        for i, axis in ((0, 1), (1, 1), (2, 0), (3, 0), (5, 0), (6, 0)):
            args[i] = np.repeat(args[i], 2, axis=axis)
        args[0][1, 0, 0] += .2
        args[0][1, 1, 0] += .9
        report = audit.summarize(audit.measure_binding(*args), [("rest", {}, "ordinary"), ("pose", {}, "ordinary")], [1., .25])
        metric = report["poseGroups"]["ordinary"]["poseTransportedOffsetDrift"]
        self.assertEqual(report["rootClasses"], {"fullWeight": 1, "fadeWeight": 1})
        self.assertAlmostEqual(metric["fullWeightMax"], .2)
        self.assertAlmostEqual(metric["fadeWeightMax"], .9)
        self.assertEqual(metric["worstRegionWeight"], .25)


class StateAndOutputContracts(unittest.TestCase):
    def test_mixed_morphs_compose_before_skinning_and_missing_shape_field_is_zero(self):
        vertices = np.array([[0., 0, 0], [1., 2, 3]])
        fields = {"breast": np.array([[0., 1, -2], [0, 2, -4]]), "chest": np.ones((2, 3))}
        result = audit.compose_morphs(vertices, fields, {"breast": .5, "chest": .25, "other-shape": 1})
        np.testing.assert_allclose(result, vertices + fields["breast"]*.5 + .25)
        np.testing.assert_array_equal(vertices, [[0, 0, 0], [1, 2, 3]])

    def test_current_female_vectors_are_preserved_and_male_rows_excluded(self):
        current, _ = audit.helpers()
        rows = audit.json_read(ROOT / "src/test/resources/geometry/expressive-fixture-vectors-v4.json")
        result = dict(audit.states(current.V4_PUBLIC_MORPHS, rows))
        females = [row for row in rows if row["sex"] == "female"]
        self.assertEqual(len(result), 7 + len(females))
        for row in females:
            self.assertEqual(result[row["fixture"]], row["values"])
        self.assertFalse(any(row["fixture"] in result for row in rows if row["sex"] == "male"))

    def test_unknown_names_duplicate_states_and_bad_coefficients_are_refused(self):
        current, _ = audit.helpers()
        for values, name in (({"unknown": .5}, "sample"), ({audit.BREAST: True}, "sample"),
                             ({audit.BREAST: float("inf")}, "sample"), ({audit.BREAST: -1}, "sample"),
                             ({audit.BREAST: 1.1}, "sample"), ({}, "neutral")):
            with self.subTest(values=values), self.assertRaises(ValueError):
                audit.states(current.V4_PUBLIC_MORPHS, [{"name": name, "values": values}])

    def test_new_output_is_external_json_and_cannot_replace_an_input_or_live_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "inputs" / "mesh.nif"
            source.parent.mkdir()
            source.write_bytes(b"immutable")
            good = root / "new-evidence" / "audit.json"
            self.assertEqual(audit.output_path(good, [source]), good.resolve())
            for bad in (source.parent / "audit.json", ROOT / "target" / "audit.json", root / "mods" / "audit.json", root / "audit.nif"):
                with self.subTest(path=bad), self.assertRaises(ValueError):
                    audit.output_path(bad, [source])
            good.parent.mkdir()
            good.write_text("existing")
            with self.assertRaises(ValueError): audit.output_path(good, [source])
            self.assertEqual(source.read_bytes(), b"immutable")

    def test_pin_changes_and_duplicate_nonfinite_json_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.json"
            path.write_text('{"x":1}')
            original = audit.pin(path)
            audit.unchanged([original])
            path.write_text('{"x":2}')
            with self.assertRaises(ValueError): audit.unchanged([original])
            for text in ('{"x":1,"x":2}', '{"x":NaN}'):
                path.write_text(text)
                with self.assertRaises(ValueError): audit.json_read(path)


if __name__ == "__main__":
    unittest.main()
