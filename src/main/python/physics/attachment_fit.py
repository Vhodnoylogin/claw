"""Pure bounded one-dimensional attachment fitting; no resources or quantization.

Each last-axis vector is a sample with residual r and response d to a weight
shift x. Constrain ||r+x*d||-||r|| <= norm_tolerance for every sample, then
minimize the weighted sum of squared residuals inside the supplied shift bounds.
Zero-weight samples still constrain the fit. All calculations use float64.
"""
from __future__ import annotations

import numpy as np


def _numeric(value, name):
    raw = np.asarray(value)
    if raw.dtype.kind not in "iuf":
        raise ValueError(name + " must contain real numbers")
    result = np.asarray(raw, dtype=float)
    if not np.isfinite(result).all():
        raise ValueError(name + " must be finite")
    return result


def _norm(values):
    scale = np.max(abs(values), axis=1)
    scaled = np.divide(values, scale[:, None], out=np.zeros_like(values), where=scale[:, None] != 0)
    return scale * np.sqrt(np.sum(scaled * scaled, axis=1))


def fit_shift(residual, response, bounds, norm_tolerance=1e-8, *, objective_weights=None):
    """Return a verified shift, intersected interval and measured fit statistics.

    Arrays must have equal nonempty (..., vector_dimension) shapes. Tolerances
    and optional nonnegative objective weights broadcast over the sample axes.
    Finite bounds must contain zero. Quantization, meaningful-gain policies,
    other skin/card constraints and actual serialized verification belong to
    the caller. Shift arithmetic is normalized to the caller's bounds; inputs,
    effective responses and reported objective values must fit float64.
    """
    r, d = _numeric(residual, "Residual"), _numeric(response, "Response")
    if r.shape != d.shape or r.ndim < 1 or not r.size or not r.shape[-1]:
        raise ValueError("Residual and response need the same nonempty vector shape")
    limits = _numeric(bounds, "Bounds")
    if limits.shape != (2,) or not limits[0] <= 0 <= limits[1]:
        raise ValueError("Ordered finite shift bounds must contain zero")
    try:
        tolerance = np.broadcast_to(_numeric(norm_tolerance, "Tolerance"), r.shape[:-1]).ravel()
        weights = np.ones_like(tolerance) if objective_weights is None else np.broadcast_to(
            _numeric(objective_weights, "Objective weights"), r.shape[:-1]).ravel()
    except ValueError as error:
        raise ValueError("Tolerance/weights must broadcast over the sample axes") from error
    if (tolerance < 0).any() or (weights < 0).any():
        raise ValueError("Tolerance and objective weights must be nonnegative")
    r, d = r.reshape(-1, r.shape[-1]), d.reshape(-1, d.shape[-1])
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            shift_scale = float(abs(limits).max())
            scaled_limits = limits / shift_scale if shift_scale else limits.copy()
            effective = d * shift_scale
            if shift_scale and np.any((d != 0) & (effective == 0)):
                raise ValueError("Bound-scaled response underflows float64")
            # Scale each constraint before forming its discriminant. The stable
            # far-root/product form retains the near root when cancellation
            # would round (-b + sqrt(b*b-a*c)) to zero.
            scale = np.maximum.reduce([abs(r).max(1), abs(effective).max(1), tolerance])
            scale[scale == 0] = 1
            rn, dn, tn = r / scale[:, None], effective / scale[:, None], tolerance / scale
            a, b = np.sum(dn * dn, axis=1), np.sum(rn * dn, axis=1)
            c = -2 * _norm(rn) * tn - tn * tn
            # Triangle inequality proves these samples safe throughout the
            # normalized [-1,1] range, including genuinely tiny responses.
            unrestricted = _norm(effective) <= tolerance
            lost_response = np.any((effective != 0) & (dn == 0), axis=1)
            if np.any((~unrestricted) & (lost_response | (a == 0))):
                raise ValueError("Constraint response underflows float64")
            lower, upper = np.full(len(r), -np.inf), np.full(len(r), np.inf)
            active = (a > 0) & (~unrestricted)
            aa, bb, cc = a[active], b[active], c[active]
            disc = np.hypot(bb, np.sqrt(aa) * np.sqrt(-cc))
            far = (-bb - np.where(bb >= 0, 1., -1.) * disc) / aa
            near = np.divide(cc, aa * far, out=np.zeros_like(far), where=far != 0)
            lower[active], upper[active] = np.minimum(far, near), np.maximum(far, near)
            ilow, ihigh = int(np.argmax(lower)), int(np.argmin(upper))
            low, high = max(float(scaled_limits[0]), float(lower[ilow])), min(float(scaled_limits[1]), float(upper[ihigh]))
            if not low <= 0 <= high:
                raise ValueError("Numerical constraint intersection lost its zero fallback")
            # Zero-weight controls constrain the interval but cannot set the
            # objective scale and erase the positively weighted response.
            positive = weights > 0
            curvature = gradient = 0.
            if positive.any():
                scale = max(float(abs(r[positive]).max()), float(abs(effective[positive]).max()))
                if scale:
                    wg = weights[positive] / weights[positive].max()
                    rg, dg = r[positive] / scale, effective[positive] / scale
                    curvature = float(np.sum(wg * np.sum(dg * dg, axis=1)))
                    gradient = float(np.sum(wg * np.sum(rg * dg, axis=1)))
            shift = float(np.clip(-gradient / curvature, low, high) * shift_scale) if curvature > 0 else 0.
            before_norm = _norm(r)
            after_norm = _norm(r + shift * d)
            backed_off = bool(np.any(after_norm - before_norm > tolerance))
            if backed_off:
                # Tighten a rounded boundary, never increase the tolerance.
                shift *= 1 - 1e-12
                after_norm = _norm(r + shift * d)
                if np.any(after_norm - before_norm > tolerance):
                    shift, after_norm = 0., before_norm.copy()
            before_terms = weights * before_norm * before_norm
            after_terms = weights * after_norm * after_norm
            if np.any((weights > 0) & (((before_norm > 0) & (before_terms == 0)) |
                                      ((after_norm > 0) & (after_terms == 0)))):
                raise ValueError("Objective metrics underflow float64")
            before, after = float(np.sum(before_terms)), float(np.sum(after_terms))
            if not np.isfinite([before, after]).all():
                raise ValueError("Objective metrics exceed float64 range")
            if after >= before:
                shift, after, after_norm = 0., before, before_norm.copy()
    except FloatingPointError as error:
        raise ValueError("Fit data or metrics exceed float64 range") from error
    return {"shift": shift, "feasible_interval": [low * shift_scale, high * shift_scale],
            "lower_sample": ilow if lower[ilow] > scaled_limits[0] else None,
            "upper_sample": ihigh if upper[ihigh] < scaled_limits[1] else None,
            "sample_count": len(r), "squared_residual_before": before, "squared_residual_after": after,
            "maximum_norm_increase": float(np.max(after_norm - before_norm)),
            "rounding_backoff": backed_off, "status": "fit" if shift != 0 else "no_op"}
