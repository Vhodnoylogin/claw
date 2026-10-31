"""Contract tests for the authored opposed fields and exact quantization."""
import json
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[4]/'src/main/python/build-tools'))
import expressive_body as body


class ExpressiveBodyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recipe = json.loads((body.ROOT/'src/main/resources/recipes/expressive-body-v1.json').read_text())
        cls.parameters = cls.recipe['parameters']

    def test_lean_and_growth_are_opposed_bounded_endpoints(self):
        v = np.array([[33., 15., 98.], [14., 13., 62.], [14.5, 8., 32.], [12., 10., 84.]])
        fields = body.fields(v, 'body', self.parameters)
        for lean, growth in zip(body.NAMES[:4], body.NAMES[4:8]):
            self.assertLess(float(np.sum(fields[lean]*fields[growth])), 0)
            for value in (0, .25, .5, .75, 1):
                self.assertTrue(np.isfinite(v+value*fields[lean]).all())
        self.assertTrue(np.all(fields['CLAWArmLean'][:, 0] == 0))
        self.assertTrue(np.all(fields['CLAWLegThighLean'][:, 2] == 0))
        self.assertTrue(np.all(fields['CLAWLegCalfLean'][:, 2] == 0))

    def test_face_feet_and_unsupported_shapes_are_fixed(self):
        points = np.array([[0., 65., 120.], [14., 20., 0.], [0., -60., 45.]])
        for value in body.fields(points, 'body', self.parameters).values():
            np.testing.assert_array_equal(value, np.zeros_like(points))
        for value in body.fields(np.array([[33., 15., 98.]]), 'eyes', self.parameters).values():
            np.testing.assert_array_equal(value, np.zeros((1, 3)))

    def test_common_skin_seams_and_uv_splits_share_field(self):
        points = np.array([[15., 19., 94.], [15., 19., 94.], [-12., 8., 88.]])
        a = body.fields(points, 'body', self.parameters)
        b = body.fields(points, 'head', self.parameters)
        for name in body.NAMES:
            np.testing.assert_array_equal(a[name], b[name])
            np.testing.assert_array_equal(a[name][0], a[name][1])

    def test_serialization_roundtrip_error_is_explicitly_bounded(self):
        delta = np.array([[0., 0., 0.], [4.2, -3.4, .001], [1e-9, .2, -2.]])
        record = body.encode_field('CLAWArmLean', delta)
        data = body.write_trip(b'PIRT', [['body', [record]]])
        decoded = body.decode(data, {'body': 3})['body', 'CLAWArmLean']
        self.assertLessEqual(float(np.max(abs(decoded-delta))), record[1]/2+1e-12)
        self.assertEqual([row[0] for row in record[2]], [1, 2])



if __name__ == '__main__':
    unittest.main()
