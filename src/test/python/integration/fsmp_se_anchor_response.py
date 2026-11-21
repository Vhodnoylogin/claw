"""Evaluate a parsed nominal SE left PreBreast step and its confirmed inverse."""

from math import dist, frexp, fsum, hypot, isfinite, ldexp
from statistics import median

if __package__:
    from .fsmp_joint_limit_readback import DRIVERS, PARENTS, joint_frame, pose_transform
    from .fsmp_scene_writeback import RIGHT_ABSOLUTE_LIMIT_GU
else:
    from fsmp_joint_limit_readback import DRIVERS, PARENTS, joint_frame, pose_transform
    from fsmp_scene_writeback import RIGHT_ABSOLUTE_LIMIT_GU


PHASES = ("quiet", "held", "returned")
MOMENTS = ("pre", "post")
NOMINAL_JOINT_X_GU = 0.10
MINIMUM_SIGNAL_GU = 0.005
ANCHOR_TOLERANCE_GU = 0.002
ANCHOR_BASIS_TOLERANCE = 1e-5


def _pose(row, roles, moment, rest):
    source = dict(zip(roles, row[moment], strict=True))
    for name, value in source.items():
        fixed = name in PARENTS
        if (value["rigidBody"] is not True
                or value["inverseMass"] != (0 if fixed else 20)
                or value["flags"] & 3 != (2 if fixed else 0)):
            raise ValueError("Expected the original unit-scale kinematic anchors and 0.05-mass P1 bodies")
    world = {name: pose_transform(value) for name, value in source.items()}
    joints = {driver: joint_frame(world[parent], world[driver], rest[driver])["translation"]
              for parent, driver in zip(PARENTS, DRIVERS, strict=True)}
    return world, joints


def _span(points):
    """A conservative upper bound on the largest pairwise distance."""
    return hypot(*(max(values) - min(values) for values in zip(*points, strict=True)))


def _summarize(pairs, poses):
    result = {
        "pairCount": len(pairs),
        "firstPair": None, "lastPair": None,
        "qpcSpanTicks": 0, "hostTimeStepSumSeconds": 0,
    }
    if not pairs:
        return result
    first, last = pairs[0], pairs[-1]
    result.update(firstPair=first["pair"], lastPair=last["pair"], firstPreQpc=first["preQpc"],
                  lastPostQpc=last["postQpc"], qpcSpanTicks=last["postQpc"] - first["preQpc"],
                  hostTimeStepSumSeconds=fsum(row["hostTimeStep"] for row in pairs))
    if poses:
        result["leftJointXRangeGU"] = [
            min(joints[DRIVERS[0]][0] for _, joints in poses),
            max(joints[DRIVERS[0]][0] for _, joints in poses),
        ]
    return result


def evaluate(rows, roles, spans, *, rest, anchor_delta):
    """Return movement/return evidence within three explicit host-QPC intervals.

    The caller verifies trace ownership, the actuator receipt and the exact
    role-to-token association before passing rows from native parse_trace.
    The intervals contain whole pairs. The release interval between held and
    returned is descriptive and does not estimate a continuous or rendered peak.
    """
    if len(roles) != 4 or set(roles) != set((*PARENTS, *DRIVERS)) or set(rest) != set(DRIVERS):
        raise ValueError("Expected four explicit P1 roles in trace slot order and both rest frames")
    if (set(spans) != set(PHASES)
            or any(len(spans[name]) != 2 or any(type(tick) is not int or tick <= 0 for tick in spans[name])
                   or spans[name][0] >= spans[name][1] for name in PHASES)
            or any(spans[a][1] > spans[b][0] for a, b in zip(PHASES, PHASES[1:]))):
        raise ValueError("Expected ordered nonoverlapping quiet, held and returned QPC intervals")
    if (not rows or any(row["preQpc"] >= row["postQpc"] for row in rows)
            or any(b["pair"] != a["pair"] + 1 or b["preQpc"] <= a["postQpc"]
                   for a, b in zip(rows, rows[1:]))):
        raise ValueError("Expected contiguous advancing native pose pairs")
    if type(anchor_delta) in (int, float):
        anchor_delta = (anchor_delta, 0, 0)
    if (not isinstance(anchor_delta, (tuple, list)) or len(anchor_delta) != 3
            or any(type(x) not in (int, float) or not isfinite(x) for x in anchor_delta)
            or not hypot(*anchor_delta)):
        raise ValueError("Expected a nonzero finite anchor-local displacement")

    def inside(span):
        begin, end = span
        return [row for row in rows if begin <= row["preQpc"] < row["postQpc"] <= end]

    pairs = {name: inside(spans[name]) for name in PHASES}
    checks = {"completePhaseCoverage": all(len(rows) >= 3 for rows in pairs.values())}
    result = {
        "scope": "sampled native P1 step and return; no continuous or rendered motion claim",
        "qualified": False,
        "checks": checks,
        "phases": {name: _summarize(phase, ()) for name, phase in pairs.items()},
        "releaseTransient": {"available": False, "pairCount": 0},
    }
    if not checks["completePhaseCoverage"]:
        return result

    all_pairs = inside((spans["quiet"][0], spans["returned"][1]))
    poses = {row["pair"]: [_pose(row, roles, moment, rest) for moment in MOMENTS] for row in all_pairs}
    phase_poses = {name: [pose for row in phase for pose in poses[row["pair"]]]
                   for name, phase in pairs.items()}
    result["phases"] = {name: _summarize(phase, phase_poses[name]) for name, phase in pairs.items()}
    quiet, held, returned = (phase_poses[name] for name in PHASES)
    left_anchor, right_anchor = PARENTS
    left_driver, right_driver = DRIVERS
    base_anchor = quiet[0][0][left_anchor]
    origin, orientation = base_anchor["translation"], base_anchor["rotationRowMajor"]
    expected = [fsum(orientation[3*i+j] * anchor_delta[j] for j in range(3)) for i in range(3)]
    held_target = [offset + initial for offset, initial in zip(expected, origin, strict=True)]
    commanded_length = hypot(*expected)
    axis = [component / commanded_length for component in expected]

    def translations(phase, role):
        return [world[role]["translation"] for world, _ in phase]

    complete = [pose for row in all_pairs for pose in poses[row["pair"]]]
    magnitude = max(abs(x) for phase in phase_poses.values() for world, _ in phase
                    for state in world.values() for x in state["translation"])
    # A native subtraction compares two rounded float32 coordinates. Include two ulps of
    # the largest recorded world position, before applying the independent noise margin.
    binary_floor = ldexp(1.0, max(-149, frexp(magnitude)[1] - 24)) * 2
    numeric_floor = max(1e-4, binary_floor)
    anchor_tolerance = max(ANCHOR_TOLERANCE_GU, 2*numeric_floor)
    held_anchor_error = max(dist(t, held_target) for t in translations(held, left_anchor))
    quiet_anchor_error = max(dist(t, origin) for t in translations((*quiet, *returned), left_anchor))
    anchor_basis_error = max(
        abs(a-b) for role in PARENTS for world, _ in complete
        for a, b in zip(world[role]["rotationRowMajor"], quiet[0][0][role]["rotationRowMajor"], strict=True)
    )
    quiet_left = translations(quiet, left_driver)
    quiet_spread = _span(quiet_left)
    quiet_centre = [median(col) for col in zip(*quiet_left, strict=True)]
    held_centre = [median(col) for col in zip(*translations(held, left_driver), strict=True)]
    held_travel = fsum((b - a) * u for a, b, u in zip(quiet_centre, held_centre, axis, strict=True))
    returned_error = max(dist(t, quiet_centre) for t in translations(returned, left_driver))
    signal_floor = max(MINIMUM_SIGNAL_GU, 4*numeric_floor, 4*quiet_spread)
    return_tolerance = max(ANCHOR_TOLERANCE_GU, 2*numeric_floor, 2*quiet_spread)
    right_span = max(_span(translations(complete, right_anchor)),
                     _span(translations(complete, right_driver)),
                     _span([joints[right_driver] for _, joints in complete]))
    checks.update(
        commandedAnchorHeldAndReturned=(commanded_length > 2 * anchor_tolerance
                                         and max(held_anchor_error, quiet_anchor_error) <= anchor_tolerance),
        anchorRotationStable=anchor_basis_error <= ANCHOR_BASIS_TOLERANCE,
        independentRightControl=right_span <= RIGHT_ABSOLUTE_LIMIT_GU,
        quietLeftStable=quiet_spread <= MINIMUM_SIGNAL_GU,
        nominalLeftRest=all(abs(joints[left_driver][0] - NOMINAL_JOINT_X_GU) <= MINIMUM_SIGNAL_GU
                            for _, joints in (*quiet, *returned)),
        leftMovedInCommandedDirection=held_travel >= signal_floor,
        leftReturned=returned_error <= return_tolerance and returned_error <= held_travel / 2,
    )
    result.update(qualified=all(checks.values()), measures={
        "commandedWorldAnchorDeltaGU": expected,
        "heldAnchorMaximumErrorGU": held_anchor_error,
        "quietOrReturnedAnchorMaximumErrorGU": quiet_anchor_error,
        "anchorMaximumRotationComponentError": anchor_basis_error,
        "rightSpanUpperGU": right_span,
        "rightAbsoluteLimitGU": RIGHT_ABSOLUTE_LIMIT_GU,
        "quietLeftWorldSpanUpperGU": quiet_spread,
        "leftHeldSignedTravelGU": held_travel,
        "leftReturnedMaximumErrorGU": returned_error,
        "float32TranslationFloorGU": binary_floor,
        "effectiveSignalFloorGU": signal_floor,
        "returnToleranceGU": return_tolerance,
    })

    release = inside((spans["held"][1], spans["returned"][0]))
    if release:
        release_poses = [poses[row["pair"]] for row in release]
        observed = [pose for pair in release_poses for pose in pair]
        summary = _summarize(release, observed)
        quiet_joint_x = median(joints[left_driver][0] for _, joints in quiet)
        summary.update(available=True, quietReferenceLeftJointXGU=quiet_joint_x,
                       largestObservedAbsLeftJointXDeviationGU=max(
                           abs(joints[left_driver][0] - quiet_joint_x) for _, joints in observed),
                       largestObservedWithinPairAbsLeftJointXDeltaGU=max(
                           abs(after[left_driver][0] - before[left_driver][0])
                           for (_, before), (_, after) in release_poses))
        result["releaseTransient"] = summary
    return result
