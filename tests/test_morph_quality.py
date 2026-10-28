import struct
import sys
from pathlib import Path
import unittest
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import morph_quality as quality


class QualityTests(unittest.TestCase):
    def test_duplicate_names_rejected_for_either_endpoint(self):
        unique = [SimpleNamespace(name='body'), SimpleNamespace(name='head')]
        duplicate = [*unique, SimpleNamespace(name='head')]
        for low, high in [(duplicate, unique), (unique, duplicate)]:
            with self.assertRaises(ValueError):
                quality.shape_map(low); quality.shape_map(high)

    def test_opposite_overlapping_fields_are_not_reported_as_independent(self):
        a = np.array([[1., 0, 0], [0, 2, 0], [0, 0, 0]])
        row = quality.field_pair(a, -2*a)
        self.assertAlmostEqual(row['cosine'], -1)
        self.assertEqual(row['fitBFromAGain'], -2)
        self.assertEqual(row['relativeFitResidual'], 0)
        self.assertEqual(row['supportJaccard'], 1)

    def test_same_support_can_be_orthogonal_and_zero_is_not_perfect_similarity(self):
        row = quality.field_pair([[1, 0, 0]], [[0, 1, 0]])
        self.assertEqual(row['cosine'], 0)
        self.assertEqual(row['supportJaccard'], 1)
        self.assertIsNone(quality.field_pair([[0, 0, 0]], [[0, 0, 0]])['cosine'])

    def test_regions_use_normalized_stored_weights_not_shape_names(self):
        row = quality.field_summary([[2, 0, 0], [1, 0, 0]],
                                    {'NPC Head [Head]': [(0, .2)], 'NPC Spine2 [Spn2]': [(0, .2), (1, .5)]})
        self.assertAlmostEqual(row['headJawEarWeightEnergyFraction'], .4)
        self.assertAlmostEqual(row['spineClavicleWeightEnergyFraction'], .6)

    def test_frozen_join_measures_relative_motion_even_if_gap_closes(self):
        a = np.array([[0., 0, 0], [1, 0, 0], [0, 1, 0]])
        b = a+[0, 0, .01]
        pairs = quality.freeze_join(a, [[0, 1, 2]], b, [[0, 1, 2]], .02)
        self.assertEqual(pairs.tolist(), [[0, 0], [1, 1], [2, 2]])
        row = quality.join_metrics(a, b, a, a, pairs)
        self.assertEqual(row['maxDistance'], 0)
        self.assertAlmostEqual(row['maxRelativeDisplacement'], .01)
        self.assertAlmostEqual(row['maxDistanceIncrease'], -.01)

    def test_join_uses_boundaries_and_does_not_pair_surface_interior(self):
        v = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [.5, .5, 0]]
        f = [[0, 1, 4], [1, 2, 4], [2, 3, 4], [3, 0, 4]]
        self.assertEqual(quality.freeze_join(v, f, v, f, 0).tolist(), [[i, i] for i in range(4)])

    def test_combined_fields_can_collapse_when_each_single_does_not(self):
        v = np.array([[0., 0, 0], [1, 0, 0], [0, 1, 0]])
        delta = np.array([[0., 0, 0], [-.5, 0, 0], [0, 0, 0]])
        self.assertEqual(quality.surface_metrics(v, v+delta, [[0, 1, 2]])['newCollapsedCount'], 0)
        both = quality.surface_metrics(v, v+2*delta, [[0, 1, 2]])
        self.assertEqual(both['newCollapsedTriangleIds'], [0])

    def test_normal_turn_and_original_degeneracy_are_separate(self):
        v = np.array([[0., 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 0]])
        current = v.copy(); current[2, 1] = -1
        row = quality.surface_metrics(v, current, [[0, 1, 2], [0, 0, 3]])
        self.assertEqual(row['normalTurnTriangleIds'], [0])
        self.assertEqual(row['neutralDegenerateCount'], 1)
        self.assertEqual(row['newCollapsedCount'], 0)

    def test_sparse_decode_retains_public_reader_subthreshold_values(self):
        scale = struct.unpack('<f', struct.pack('<f', .00001))[0]
        raw = b'PIRT'+struct.pack('<H', 1)+b'\x04head'+struct.pack('<H', 1)+b'\x01G'+struct.pack('<fH', scale, 2)+struct.pack('<H3hH3h', 0, 1, 0, 0, 1, 30, 0, 0)
        fields, report = quality.decode_fields(raw, {'head': {'G': [[1, (30*scale, 0, 0)]]}}, {'head': 2})
        self.assertEqual(fields['head', 'G'][0, 0], scale)
        self.assertEqual(report['retainedSubthresholdPairs'], 1)
        with self.assertRaises(ValueError):
            quality.decode_fields(raw, {'head': {'G': []}}, {'head': 2})
        with self.assertRaises(ValueError):
            quality.decode_fields(raw, {'head': {'G': []}}, {'head': 1})

    def test_states_are_deterministic_and_include_declared_pair_and_extremes(self):
        self.assertEqual(quality.sample_states(['B', 'A'], [('B', 'A')]), quality.sample_states(['A', 'B'], [('A', 'B')]))
        self.assertIn(('A+B', {'A': 1., 'B': 1.}), quality.sample_states(['A', 'B'], [('A', 'B')]))
        with self.assertRaises(ValueError):
            quality.sample_states(['A'], [('A', 'missing')])

    def test_invalid_geometry_and_output_locations_rejected(self):
        with self.assertRaises(ValueError):
            quality.surface_metrics([[0, 0, 0]], [[0, 0, float('nan')]], [[0, 0, 0]])
        with self.assertRaises(ValueError):
            quality.triangles([[0., 0, 0]], 1)
        with self.assertRaises(ValueError):
            quality.safe_output(quality.ROOT/'work'/'audit', [])
        with self.assertRaises(ValueError):
            quality.safe_output(Path('D:/MO2/mods/new-audit'), [])


if __name__ == '__main__':
    unittest.main()
