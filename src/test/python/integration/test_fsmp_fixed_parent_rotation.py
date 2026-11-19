"""Check the fixed-parent proof at the observed numerical failure boundary."""

from fractions import Fraction
import math
import unittest

from fsmp_fixed_parent_rotation import (
    IDENTITY,
    fixed_parent_frobenius_bound,
    within_rotation_limit,
)


def z_rotation(angle):
    cosine, sine = math.cos(angle), math.sin(angle)
    return (cosine, -sine, 0, sine, cosine, 0, 0, 0, 1)


class RotationBoundTests(unittest.TestCase):
    def test_oblique_parent_with_small_rotation(self):
        parent = z_rotation(.84)
        poses = [z_rotation(.84 + angle) for angle in (-.0035, 0, .0035)]
        lower = tuple(map(min, zip(*poses)))
        upper = tuple(map(max, zip(*poses)))
        bound = fixed_parent_frobenius_bound(parent, parent, lower, upper, IDENTITY)
        self.assertTrue(within_rotation_limit(bound))

    def test_large_rotation_refused(self):
        pose = z_rotation(.0041)
        self.assertFalse(within_rotation_limit(
            fixed_parent_frobenius_bound(IDENTITY, IDENTITY, pose, pose, IDENTITY)))

    def test_nonorthogonal_parent_deviation_is_counted(self):
        parent = (1.004, *IDENTITY[1:])
        bound = fixed_parent_frobenius_bound(parent, parent, parent, parent, IDENTITY)
        self.assertGreaterEqual(bound, Fraction(parent[0]) ** 2 - 1)
        self.assertFalse(within_rotation_limit(bound))

    def test_parent_change_and_invalid_extrema_refused(self):
        with self.assertRaisesRegex(ValueError, 'Fixed parent'):
            fixed_parent_frobenius_bound(IDENTITY, z_rotation(.001), IDENTITY, IDENTITY, IDENTITY)
        with self.assertRaisesRegex(ValueError, 'Ordered'):
            fixed_parent_frobenius_bound(IDENTITY, IDENTITY, (2, *IDENTITY[1:]), IDENTITY, IDENTITY)
        with self.assertRaisesRegex(ValueError, 'finite'):
            fixed_parent_frobenius_bound(IDENTITY, IDENTITY, (math.nan, *IDENTITY[1:]), IDENTITY, IDENTITY)
