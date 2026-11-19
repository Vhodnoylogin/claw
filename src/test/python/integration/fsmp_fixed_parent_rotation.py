"""Conservative rotation bound for whole-window extrema and a fixed parent basis."""

from fractions import Fraction
from math import isfinite, isqrt


IDENTITY = (1, 0, 0, 0, 1, 0, 0, 0, 1)
ANGLE_LIMIT = Fraction(1, 250)
ROUNDING_SCALE = 1 << 60


def _matrix(values):
    if len(values) != 9 or any(type(value) not in (float, int) or not isfinite(value)
                               for value in values):
        raise ValueError('Nine finite rotation components required')
    return tuple(map(Fraction, values))


def _transpose(values):
    return tuple(values[column * 3 + row] for row in range(3) for column in range(3))


def _multiply(left, right):
    return tuple(sum(left[row * 3 + k] * right[k * 3 + column] for k in range(3))
                 for row in range(3) for column in range(3))


def _norm_upper(values):
    squared = sum(value * value for value in values)
    scaled = squared * ROUNDING_SCALE ** 2
    root = isqrt(scaled.numerator // scaled.denominator)
    return Fraction(root + (root * root < scaled), ROUNDING_SCALE)


def _orthogonality_defect(gram):
    return _norm_upper(value - identity for value, identity in zip(gram, IDENTITY))


def fixed_parent_frobenius_bound(parent_min, parent_max, driver_min, driver_max, rest):
    """Bound the Frobenius norm of A^T B R^T - I for every recorded post-step."""
    parent = _matrix(parent_min)
    if parent != _matrix(parent_max):
        raise ValueError('Fixed parent rotation required across the entire window')
    lower, upper = _matrix(driver_min), _matrix(driver_max)
    if any(lo > hi for lo, hi in zip(lower, upper)):
        raise ValueError('Ordered driver extrema required')
    rest = _matrix(rest)
    reference = _multiply(parent, rest)
    world_error = _norm_upper(max(abs(lo - expected), abs(hi - expected))
                              for lo, hi, expected in zip(lower, upper, reference))
    parent_defect = _orthogonality_defect(_multiply(_transpose(parent), parent))
    rest_defect = _orthogonality_defect(_multiply(rest, _transpose(rest)))

    # A^T B R^T - I = A^T(B - A R)R^T + (A^T A)(R R^T) - I.
    # The Gram defects bound both operator norms and the second term.
    norm_factor = (1 + parent_defect) * (1 + rest_defect)
    return world_error * norm_factor + parent_defect + rest_defect + parent_defect * rest_defect


def within_rotation_limit(frobenius_bound):
    """Check .004 rad using the exact lower bound sin(x) >= x - x^3/6."""
    half_angle = ANGLE_LIMIT / 2
    chord_lower_squared = 8 * (half_angle - half_angle ** 3 / 6) ** 2
    return 0 <= frobenius_bound and frobenius_bound ** 2 <= chord_lower_squared
