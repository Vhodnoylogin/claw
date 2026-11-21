"""Compare an independently observed animated joint to nearby solver targets."""

from bisect import bisect_left, bisect_right
from math import dist, isfinite

if __package__:
    from . import fsmp_probe as probe
else:
    import fsmp_probe as probe


def hierarchy_residual(parent_world, child_world, child_local):
    """Compare an observed WORLD pose with the hierarchy's parent × local pose."""
    parent = probe.transform(parent_world)
    scene_relative = probe.relative(child_world, parent)
    local = probe.transform(child_local)
    return {
        "translationGU": parent["scale"] * dist(scene_relative["translation"], local["translation"]),
        "rotationComponent": probe.max_delta(scene_relative["rotationRowMajor"], local["rotationRowMajor"]),
        "scale": abs(scene_relative["scale"] - local["scale"]),
    }


def compare_animated_joint_x(solver, samples, *, tolerance, maximum_interval_ticks):
    """Use neighboring post-step values to bound the asynchronous scene read.

    Each solver sample is (post QPC, joint X) and each scene sample is
    (request QPC, response QPC, joint X). The caller must bind both sources
    to the same actor, roles, rest pose and host clock. A value outside the
    envelope still needs a stock writeback or renderer boundary to explain it.
    """
    if (type(tolerance) not in (int, float) or not isfinite(tolerance) or tolerance < 0
            or type(maximum_interval_ticks) is not int or maximum_interval_ticks <= 0):
        raise ValueError("Expected explicit finite tolerances")
    if (len(solver) < 3
            or any(type(at) is not int or at <= 0 or not isfinite(value) for at, value in solver)
            or any(b[0] <= a[0] for a, b in zip(solver, solver[1:]))):
        raise ValueError("Expected an advancing native joint trajectory")
    times = [time for time, _ in solver]
    results = []
    last_response = 0
    for start, finish, scene in samples:
        if (type(start) is not int or type(finish) is not int
                or not 0 <= last_response <= start < finish or not isfinite(scene)):
            raise ValueError("Expected ordered scene reads with valid QPC intervals")
        last_response = finish
        left = bisect_left(times, start) - 1
        right = bisect_right(times, finish)
        result = {"sceneJointXGU": scene, "sceneRequestQpc": start, "sceneResponseQpc": finish}
        if left < 0 or right >= len(solver) or times[right] - times[left] > maximum_interval_ticks:
            result["status"] = "unbracketed"
        else:
            values = [value for _, value in solver[left:right + 1]]
            lo, hi = min(values), max(values)
            error = max(lo - scene, scene - hi, 0.)
            result.update(status="within" if error <= tolerance else "outside",
                          solverRangeGU=[lo, hi], outsideRangeGU=error,
                          solverPostQpcBounds=[times[left], times[right]])
        results.append(result)
    return results
