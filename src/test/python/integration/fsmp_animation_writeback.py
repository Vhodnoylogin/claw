"""Compare an independently observed animated joint to nearby solver targets."""

from bisect import bisect_left, bisect_right
from math import dist, isfinite

if __package__:
    from . import fsmp_probe as probe
    from .fsmp_joint_limit_readback import joint_frame
else:
    import fsmp_probe as probe
    from fsmp_joint_limit_readback import joint_frame


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


def evaluate_translation(writer, *, sync_end_parent, scene_parent, scene_world, scene_local, rest_local, tolerance):
    """Score one joined unit-scale P1 write and the later WORLD read.

    The caller binds the actor, directed joint, clock and neighboring syncs.
    A later hierarchy match establishes the sampled pose after the assignment.
    It does not identify which code changed the transform.
    """
    if type(tolerance) not in (int, float) or not isfinite(tolerance) or tolerance < 0:
        raise ValueError("Expected a finite nonnegative translation tolerance")
    residual = hierarchy_residual(scene_parent, scene_world, scene_local)["translationGU"]
    result = {"writer": writer["writer"], "hierarchyResidualGU": residual}
    if writer["writer"] != "observed":
        return result

    before = writer.get("writerBefore", writer.get("before"))
    target, after, final = (writer.get(key) for key in ("target", "after", "final"))
    phases = (before, target, after, final)
    if any(type(value) is not dict or type(value.get("qpc")) is not int or value["qpc"] <= 0 for value in phases):
        raise ValueError("Direct write phases are incomplete or reversed")
    if any(first["qpc"] > second["qpc"] for first, second in zip(phases, phases[1:])):
        raise ValueError("Direct write phases are incomplete or reversed")
    before, target, after, final = map(probe.transform, phases)
    joint_final = joint_frame(sync_end_parent, final, rest_local)["translation"]
    joint_scene = joint_frame(scene_parent, scene_world, rest_local)["translation"]
    result.update(
        targetVsAssignmentGU=dist(target["translation"], after["translation"]),
        stockDisplacementGU=dist(before["translation"], after["translation"]),
        assignmentVsSyncEndGU=dist(after["translation"], final["translation"]),
        syncEndVsNextWorldJointGU=dist(joint_final, joint_scene),
    )
    if result["targetVsAssignmentGU"] > tolerance:
        status = "assignment-differs-from-target"
    elif result["assignmentVsSyncEndGU"] > tolerance:
        status = "changed-by-sync-return"
    elif result["syncEndVsNextWorldJointGU"] <= tolerance:
        status = "retained-at-world-sample"
    elif residual <= tolerance:
        status = "later-world-matches-hierarchy"
    else:
        status = "later-world-moved"
    return dict(result, status=status)


def world_sample_qpc(started_ns, duration_us, request_qpc, response_qpc, frequency):
    """Bound a WORLD sample after verifying that its steady clock uses the same QPC.

    The caller pins the observer clock implementation. The transport bracket
    independently checks the conversion, including both timestamp truncations.
    """
    values = (started_ns, duration_us, request_qpc, response_qpc, frequency)
    if (any(type(value) is not int for value in values) or started_ns <= 0 or duration_us < 0
            or frequency <= 0 or not 0 < request_qpc < response_qpc):
        raise ValueError("Expected valid WORLD sample and request clocks")
    nanos_per_second = 1_000_000_000
    start = started_ns * frequency // nanos_per_second
    stop_ns = started_ns + (duration_us + 1) * 1000 + 1
    stop = (stop_ns * frequency + nanos_per_second - 1) // nanos_per_second
    if not request_qpc <= start <= stop <= response_qpc:
        raise ValueError("WORLD clock does not fit inside the host request interval")
    return start, stop


def preceding_frame_sync(syncs, sample_start, sample_stop, maximum_interval_ticks):
    """Find a completed sync followed by the full scene read before the next sync."""
    if (type(sample_start) is not int or type(sample_stop) is not int
            or type(maximum_interval_ticks) is not int or not 0 < sample_start <= sample_stop
            or maximum_interval_ticks <= 0):
        raise ValueError("Expected a bound scene read and a positive maximum sync interval")
    if (any(type(start) is not int or type(end) is not int or not 0 < start <= end for start, end in syncs)
            or any(second[0] <= first[1] for first, second in zip(syncs, syncs[1:]))):
        raise ValueError("Expected ordered nonoverlapping FrameSync receipts")
    index = bisect_left([end for _, end in syncs], sample_start) - 1
    if (index < 0 or index + 1 >= len(syncs) or sample_stop >= syncs[index + 1][0]
            or syncs[index + 1][0] - syncs[index][1] > maximum_interval_ticks):
        return None
    return index


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
