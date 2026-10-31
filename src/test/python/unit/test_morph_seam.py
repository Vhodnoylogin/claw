import struct
import sys
from pathlib import Path
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[4]/'src/main/python/build-tools'))
import morph_seam as seam
import tri_patch


class SeamTests(unittest.TestCase):
    def test_append_preserves_old_record_bytes_and_reconstructs_envelope(self):
        raw = b'PIRT'+struct.pack('<H', 1)+b'\x04head'+struct.pack('<H', 1)+b'\x01G'+struct.pack('<fH', .01, 1)+struct.pack('<H3h', 0, 1, 2, 3)
        out, report = seam.append_record(raw, 'head', 'W', .01, {1: (2, 3, 4)})
        a, b = tri_patch.offsets(raw), tri_patch.offsets(out)
        self.assertEqual(a['head', 'G', 0], b['head', 'G', 0])
        self.assertTrue(report['originalStreamReconstructionExact'])
        with self.assertRaises(ValueError): seam.append_record(raw, 'head', 'G', .01, {1: (2, 3, 4)})
        with self.assertRaises(ValueError): seam.append_record(raw, 'absent', 'W', .01, {1: (2, 3, 4)})
        with self.assertRaises(ValueError): seam.append_record(raw+b'extension', 'head', 'W', .01, {1: (2, 3, 4)})

    def test_exact_duplicate_constraints_cannot_be_averaged_to_hide_infeasibility(self):
        v = [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 0]]
        f = [[0, 1, 2], [3, 1, 2]]
        with self.assertRaises(ValueError): seam.harmonic_band(v, f, [0, 3], [[1, 0, 0], [2, 0, 0]], [], 2)
        with self.assertRaises(ValueError): seam.harmonic_band(v, f, [0], [[1, 0, 0]], [3], 2)

    def test_band_has_exact_anchors_exact_far_zero_and_exact_protected_zero(self):
        v = [[x, y, 0] for x in range(5) for y in (0, 1)]
        f = [[2*x, 2*x+2, 2*x+1] for x in range(4)]+[[2*x+1, 2*x+2, 2*x+3] for x in range(4)]
        result, report = seam.harmonic_band(v, f, [0, 1], [[1, 0, 0], [1, 0, 0]], [7], 3.)
        np.testing.assert_array_equal(result[[0, 1]], [[1, 0, 0], [1, 0, 0]])
        np.testing.assert_array_equal(result[[6, 7, 8, 9]], np.zeros((4, 3)))
        self.assertTrue(np.all(result[[2, 3, 4, 5], 0] > 0))
        self.assertTrue(np.all(result[[2, 3, 4, 5], 0] < 1))
        self.assertLess(report['solverResidual'], 1e-12)

    def test_quantization_retains_exact_source_grid_constraints_and_zero(self):
        scale = struct.unpack('<f', struct.pack('<f', .0002))[0]
        packed, decoded = seam.quantize(np.asarray([[17, -23, 0], [0, 0, 0]])*scale, scale)
        np.testing.assert_array_equal(packed, [[17, -23, 0], [0, 0, 0]])
        np.testing.assert_array_equal(decoded, np.asarray([[17, -23, 0], [0, 0, 0]])*scale)
        with self.assertRaises(ValueError): seam.quantize([[32768*scale, 0, 0]], scale)

    def test_reference_band_has_exact_constraints_and_smooth_finite_support(self):
        v = [[x, y, 0] for x in range(5) for y in (0, 1)]
        f = [[2*x, 2*x+2, 2*x+1] for x in range(4)]+[[2*x+1, 2*x+2, 2*x+3] for x in range(4)]
        result, _ = seam.reference_band(v, f, [0, 1], [[1, 0, 0], [1, 0, 0]], [7], 3., [[1, 0, 0]]*10)
        np.testing.assert_array_equal(result[[0, 1]], [[1, 0, 0], [1, 0, 0]])
        np.testing.assert_array_equal(result[[6, 7, 8, 9]], np.zeros((4, 3)))
        self.assertAlmostEqual(result[2, 0], 1-(1/3)**2*(3-2/3))
        with self.assertRaises(ValueError): seam.reference_band(v, f, [0, 1], [[1, 0, 0]], [], 3., [[1, 0, 0]]*10)


if __name__ == '__main__':
    unittest.main()
