"""Clip triangles in an already calibrated perspective eye coordinate frame."""
from __future__ import annotations

import numpy as np


def _clip_polygon(polygon, distances):
    result = []
    previous, previous_distance = polygon[-1], distances[-1]
    for current, current_distance in zip(polygon, distances, strict=True):
        if (current_distance >= 0) != (previous_distance >= 0):
            # Opposite signs make the normalized denominator nonzero and
            # avoid overflow when adding large signed distances directly.
            scale = max(abs(previous_distance), abs(current_distance))
            a, b = abs(previous_distance) / scale, abs(current_distance) / scale
            amount = a / (a + b)
            result.append(previous * (1 - amount) + current * amount)
        if current_distance >= 0:
            result.append(current)
        previous, previous_distance = current, current_distance
    return np.asarray(result)


def clip_frustum(triangles, *, left, right, bottom, top, near, far):
    """Count actual triangle intersections with a closed perspective frustum.

    Input shape is N×3×3 and positive z points forward in eye coordinates.
    Side limits are signed x/z or y/z slopes. Boundary-only contact counts
    as intersection. A near crossing requires points strictly on both sides
    of the near plane after the four side planes and far plane are applied.
    ``nearestDepth`` is the minimum z over the surviving clipped polygons, or
    None if no triangle intersects. This makes no pixel/culling assertion.
    """
    vertices = np.asarray(triangles, dtype=float)
    limits = np.asarray((left, right, bottom, top, near, far), dtype=float)
    if vertices.ndim != 3 or vertices.shape[1:] != (3, 3) or not np.isfinite(vertices).all():
        raise ValueError('Expected finite N×3×3 eye-space triangles')
    if limits.shape != (6,) or not np.isfinite(limits).all():
        raise ValueError('Expected finite scalar frustum limits')
    left, right, bottom, top, near, far = limits
    if not (left < right and bottom < top and 0 < near < far):
        raise ValueError('Expected ordered side slopes and 0 < near < far')

    # All inequalities have the form normal · point + offset >= 0.
    normals = np.array([[1, 0, -left], [-1, 0, right], [0, 1, -bottom],
                        [0, -1, top], [0, 0, -1], [0, 0, 1]])
    offsets = np.array([0, 0, 0, 0, far, -near])
    try:
        with np.errstate(over='raise', invalid='raise'):
            return _clip_triangles(vertices, normals, offsets, near)
    except FloatingPointError as error:
        raise ValueError('Frustum clip exceeded finite numeric range') from error


def _clip_triangles(vertices, normals, offsets, near):
    signed = np.einsum('tvc,pc->tpv', vertices, normals) + offsets[None, :, None]
    if not np.isfinite(signed).all():
        raise ValueError('Frustum clip exceeded finite numeric range')
    inside = np.all(signed >= 0, axis=(1, 2))
    outside = np.any(np.all(signed < 0, axis=2), axis=1)
    intersecting = int(np.count_nonzero(inside))
    nearest = float(vertices[inside, :, 2].min()) if intersecting else None
    crossing = 0
    for polygon in vertices[~(inside | outside)]:
        for normal, offset in zip(normals[:-1], offsets[:-1], strict=True):
            polygon = _clip_polygon(polygon, polygon @ normal + offset)
            if not len(polygon):
                break
        if not len(polygon):
            continue
        distances = polygon[:, 2] - near
        straddles = distances.min() < 0 < distances.max()
        polygon = _clip_polygon(polygon, distances)
        if not len(polygon):
            continue
        crossing += int(straddles)
        intersecting += 1
        depth = max(float(near), float(polygon[:, 2].min()))
        nearest = depth if nearest is None else min(nearest, depth)
    return {'intersectingTriangles': intersecting, 'crossingNearTriangles': crossing, 'nearestDepth': nearest}
