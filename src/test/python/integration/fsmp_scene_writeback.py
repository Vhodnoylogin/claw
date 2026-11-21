"""Decompose an already joined FSMP scene observation without changing its gate."""

from math import hypot, isfinite


RIGHT_ABSOLUTE_LIMIT_GU = 0.01000


def _position(value):
    if len(value) != 3 or any(type(component) not in (int, float) or not isfinite(component)
                              for component in value):
        raise ValueError("A finite observed XYZ position is required")
    return tuple(value)


def _delta(after, before):
    return tuple(a - b for a, b in zip(after, before, strict=True))


def decompose(*, scene_read, scene_before_write, target_before_step, target_after_step,
              scene_after_write, scene_after_update):
    """Use measured world coordinates from a single role and stock writer window.

    The caller joins the actor, role and clocks against the original run.
    The target and scene terms explain the write displacement in world XYZ.
    Pre-write drift and post-write recomposition remain visible as separate terms.
    """
    read, before, target_in, target_out, written, returned = map(_position, (
        scene_read, scene_before_write, target_before_step, target_after_step,
        scene_after_write, scene_after_update,
    ))
    write = _delta(written, before)
    return {
        "preStepTargetMinusSceneReadGU": _delta(target_in, read),
        "solverTargetChangeGU": _delta(target_out, target_in),
        "sceneReadToBeforeWriteGU": _delta(before, read),
        "writtenMinusSolverTargetGU": _delta(written, target_out),
        "stockWriteDeltaGU": write,
        "stockWriteDistanceGU": hypot(*write),
        "postWriteToOuterReturnGU": _delta(returned, written),
        "sceneReadToOuterReturnGU": _delta(returned, read),
    }


def score_right_control(observation):
    """Score the original right-side gate after verifying a stationary anchor."""
    distance = observation["stockWriteDistanceGU"]
    return {
        "absoluteRightStockWriteGU": distance,
        "absoluteRightLimitGU": RIGHT_ABSOLUTE_LIMIT_GU,
        "absoluteRightGateMet": distance <= RIGHT_ABSOLUTE_LIMIT_GU,
    }
