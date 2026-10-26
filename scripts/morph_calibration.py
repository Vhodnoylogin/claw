"""Frozen anatomical projection fields and sparse signed morph calibration.

This is an offline first-order geometry calibration, not an appearance oracle.
It never needs preset names or a human-to-wolf preset pairing.
"""
import itertools
import numpy as np


def unique_physical_samples(vertices, bones, deltas, frames):
    """Remove exact response duplicates without merging distinct skin bindings.

    Splitting a shape duplicates seam vertices. Counting those twice would alter
    frozen regional quantiles despite an unchanged physical shape. Coordinates,
    every stored bone weight, calibrated TRI response and bind-frame class must
    all agree; equal positions alone are insufficient.
    """
    vertices = np.asarray(vertices, dtype=float)
    count = len(vertices)
    columns = [vertices, np.asarray(frames, dtype=float).reshape(-1, 1)]
    columns.extend(np.asarray(bones[name], dtype=float).reshape(-1, 1) for name in sorted(bones))
    columns.extend(np.asarray(deltas[name], dtype=float) for name in sorted(deltas))
    if vertices.shape != (count, 3) or any(len(column) != count for column in columns):
        raise ValueError('Physical sample dimensions differ')
    signature = np.column_stack(columns)
    if not np.isfinite(signature).all():
        raise ValueError('Nonfinite physical sample')
    return np.sort(np.unique(signature, axis=0, return_index=True)[1])


def feature(points, mask, kind, *, axis=None):
    points = np.asarray(points, float)
    mask = np.asarray(mask, bool)
    if mask.shape != (len(points),) or mask.sum() < 8 or not np.isfinite(points).all():
        raise ValueError("Insufficient finite anatomical support")
    ids = np.flatnonzero(mask)
    cloud = points[ids]
    centre = cloud.mean(0)
    relative = cloud - centre
    directions = np.zeros_like(cloud)
    if kind in ("width", "depth"):
        dimension = 0 if kind == "width" else 1
        directions[:, dimension] = np.sign(relative[:, dimension])
        scale = np.mean(abs(relative[:, dimension]))
    elif kind == "front":
        front = relative[:, 1] >= np.quantile(relative[:, 1], .6)
        ids, cloud, relative = ids[front], cloud[front], relative[front]
        directions = np.zeros_like(cloud)
        directions[:, 1] = 1.
        scale = np.mean(abs(relative[:, 1]))
    elif kind == "radial":
        if axis is None:
            _, _, axes = np.linalg.svd(relative, full_matrices=False)
            axis = axes[0]
        axis = np.asarray(axis, float)
        axis /= np.linalg.norm(axis)
        radial = relative - (relative @ axis)[:, None] * axis
        lengths = np.linalg.norm(radial, axis=1)
        directions = radial / np.maximum(lengths[:, None], 1e-12)
        scale = lengths.mean()
    else:
        raise ValueError("Unknown anatomical projection")
    if not np.isfinite(scale) or scale <= 1e-5:
        raise ValueError("Degenerate anatomical scale")
    return {"indices": ids, "directions": directions / (len(ids) * scale),
            "scale": float(scale), "kind": kind}


def response(delta, fields):
    delta = np.asarray(delta, float)
    if not np.isfinite(delta).all():
        raise ValueError("Nonfinite authored morph")
    return np.asarray([np.sum(delta[row["indices"]] * row["directions"]) for row in fields])


def nnls(matrix, target, iterations=400):
    """Deterministic small nonnegative coordinate solve, without SciPy."""
    matrix, target = np.asarray(matrix, float), np.asarray(target, float)
    if matrix.ndim != 2 or target.shape != (matrix.shape[0],) or not np.isfinite(matrix).all() or not np.isfinite(target).all():
        raise ValueError("Invalid calibration matrix")
    values = np.zeros(matrix.shape[1])
    residual = target.copy()
    for _ in range(iterations):
        change = 0.
        for index in range(len(values)):
            column = matrix[:, index]
            norm = float(column @ column)
            if norm < 1e-12:
                continue
            new = max(0., values[index] + float(column @ residual) / norm)
            new = min(new, 8.)
            residual -= column * (new - values[index])
            change = max(change, abs(new - values[index]))
            values[index] = new
        if change < 1e-10:
            break
    return values


def signed_fit(matrix, human):
    """Enumerate every allowed target polarity; optimize each half-wave.

    Runtime applies one signed sum then one clamp per target. Positive and
    negative human source fixtures therefore need separate geometric scoring.
    No single target can increase on both signs of the same source in this
    linear native contract. Up to eight logically allowed targets are supported.
    """
    matrix, human = np.asarray(matrix, float), np.asarray(human, float)
    count = matrix.shape[1]
    if not 1 <= count <= 8:
        raise ValueError("Expected one to eight logical targets")
    best = None
    # Include saturation in the score: source+/-1 are effective coefficients,
    # not a claim that XML or any arbitrary provider is restricted to that box.
    for pattern in itertools.product((False, True), repeat=count):
        pattern = np.asarray(pattern, bool)
        gains = np.zeros(count)
        for sign, mask in ((1., pattern), (-1., ~pattern)):
            if mask.any():
                gains[mask] = sign * nnls(matrix[:, mask], sign * human)
        positive = matrix @ np.clip(gains, 0, 1)
        negative = matrix @ np.clip(-gains, 0, 1)
        error = float(np.sum((positive - human) ** 2) + np.sum((negative + human) ** 2))
        score = (error, float(np.sum(abs(gains))), tuple(gains))
        if best is None or score < best[0]:
            best = score, gains
    return best[1], best[0][0]


def compose(rules, sources):
    """Independent numerical oracle for the shipped native sum/clamp contract."""
    result = {}
    for rule in rules:
        value = float(sources.get(rule["source"], 0.))
        if not np.isfinite(value):
            raise ValueError("Nonfinite source coefficient")
        result[rule["target"]] = result.get(rule["target"], 0.) + value * rule["gain"]
    return {name: float(np.clip(value, 0, 1)) for name, value in result.items()}
