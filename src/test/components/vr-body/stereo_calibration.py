"""Calibrate captured OpenVR optics from independent world-space controls."""
from __future__ import annotations

import numpy as np

BASIS_ERROR_GU = .05
EDGE_ERROR_SLOPE = .001
SIDES = ('left', 'right', 'bottom', 'top')


def finite_array(values, shape):
    array = np.asarray(values)
    if array.shape != shape or array.dtype.kind not in 'iuf' or not np.isfinite(array).all():
        raise ValueError('Expected a finite numerical array of shape ' + str(shape))
    return array.astype(float)


def transform_points(transform, points):
    return points @ transform[:3, :3].T + transform[:3, 3]


def read_anchors(rows, world_to_hmd):
    if type(rows) is not list or not 4 <= len(rows) <= 16:
        raise ValueError('Four to sixteen independent 3D anchors are required')
    provider = np.array([finite_array(row['providerHeadMeters'], (3,)) for row in rows])
    world = np.array([finite_array(row['worldGu'], (3,)) for row in rows])
    extent = np.linalg.svd(provider - provider.mean(0), compute_uv=False)
    if extent[-1] < .005 or extent[-1] < .05 * extent[0]:
        raise ValueError('Head controls do not span three independent axes')
    return provider, transform_points(world_to_hmd, world)


def calibrate_head(hmd_world, fit, holdout):
    """Fit one uniform unit conversion and an orthogonal basis, allowing a handedness change."""
    world_to_hmd = np.linalg.inv(hmd_world)
    source, target = read_anchors(fit, world_to_hmd)
    hold_source, hold_target = read_anchors(holdout, world_to_hmd)
    if min(np.linalg.norm(source[:, None] - hold_source, axis=2).flat) < .001:
        raise ValueError('Head holdout repeats a fit control')
    a, b = source - source.mean(0), target - target.mean(0)
    u, singular, vt = np.linalg.svd(b.T @ a)
    scale = singular.sum() / np.sum(a * a)
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError('Game units per provider metre could not be estimated')
    transform = np.eye(4)
    transform[:3, :3] = scale * (u @ vt)
    transform[:3, 3] = target.mean(0) - transform[:3, :3] @ source.mean(0)
    provider_to_world = hmd_world @ transform
    world_scale = float(np.linalg.norm(provider_to_world[:3, 0]))
    errors = [float(np.linalg.norm(transform_points(provider_to_world, positions) -
                                  transform_points(hmd_world, expected), axis=1).max())
              for positions, expected in ((source, target), (hold_source, hold_target))]
    if not np.isfinite(errors).all() or max(errors) > BASIS_ERROR_GU:
        raise ValueError('Provider head basis exceeds the world-space fit or holdout tolerance')
    return provider_to_world, world_scale, {'fitMaxErrorGu': errors[0], 'holdoutMaxErrorGu': errors[1]}


def calibrated_eye(eye, controls, provider_to_world, game_units_per_metre):
    """Use the measured eye offset and accept frustum slopes only after independent edge controls."""
    if eye['engineOrthographic'] is not False:
        raise ValueError('The eye replay requires a perspective camera')
    provider_eye = np.eye(4)
    provider_eye[:3] = eye['openVrEyeToHeadRows']
    world_to_eye = np.linalg.inv(provider_to_world @ provider_eye)
    # OpenVR uses +X right, +Y up and -Z forward. Clipping uses positive depth.
    world_to_eye[2] *= -1
    left, right, top, bottom = eye['openVrProjectionRawLTRB']
    if top < bottom:
        top, bottom = -top, -bottom
    near, far = (value / game_units_per_metre for value in eye['engineFrustumLTRB_NF'][4:])
    planes = dict(left=left, right=right, bottom=bottom, top=top, near=near, far=far)
    if not (left < right and bottom < top and 0 < near < far):
        raise ValueError('OpenVR aperture cannot be ordered in the clip convention')
    if type(controls) is not dict or set(controls) != {*SIDES, 'near', 'interior'}:
        raise ValueError('Independent four edge, near and interior world controls required per eye')
    projected = {name: transform_points(world_to_eye, finite_array(point, (3,)))
                 for name, point in controls.items()}
    for name, (x, y, depth) in projected.items():
        if depth <= 0:
            raise ValueError('An independent eye control is behind the eye')
        u, v = x / depth, y / depth
        if not (left - EDGE_ERROR_SLOPE <= u <= right + EDGE_ERROR_SLOPE and
                bottom - EDGE_ERROR_SLOPE <= v <= top + EDGE_ERROR_SLOPE):
            raise ValueError('Independent eye control lies outside the calibrated aperture')
        if name in SIDES:
            axis = u if name in ('left', 'right') else v
            if abs(axis - planes[name]) > EDGE_ERROR_SLOPE or not near < depth < far:
                raise ValueError('Independent projected edge does not match ' + name)
        elif name == 'near':
            if abs(depth - near) * game_units_per_metre > BASIS_ERROR_GU:
                raise ValueError('Independent near plane does not match calibrated depth')
        elif not (near < depth < far and left < u < right and bottom < v < top):
            raise ValueError('Independent interior control does not project inside the eye')
    return world_to_eye, planes
