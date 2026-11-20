"""Measure a prospective one-sided VR P1 step from validated witness pairs."""
import math
import statistics

if __package__:
    from . import fsmp_joint_limit_readback as joint
else:
    import fsmp_joint_limit_readback as joint


PHASES = ("quiet", "held", "returned")
ROLES = (*joint.PARENTS, *joint.DRIVERS)
STEP = .04
MINIMUM_PAIRS = 8
ANCHOR_TOLERANCE = .003
require = joint.require


def _phase_pairs(rows, spans):
    require(set(spans) == set(PHASES), "Exact quiet, held and returned QPC spans required")
    previous_end = 0
    selected = {}
    for phase in PHASES:
        start, end = spans[phase]
        require(type(start) is int and type(end) is int and previous_end < start < end,
                "Positive disjoint chronological QPC spans required")
        previous_end = end
        cohort = [row for row in rows if start < row["preQpc"] < row["postQpc"] < end]
        require(len(cohort) >= MINIMUM_PAIRS, "Too few complete pairs inside the " + phase + " span")
        selected[phase] = cohort
    return selected


def _check_anchor(ref, actual, expected):
    delta = joint.probe.relative(actual, ref)
    rotation = [1., 0., 0., 0., 1., 0., 0., 0., 1.]
    require(joint.probe.max_delta(delta["translation"], [expected, 0., 0.]) <= ANCHOR_TOLERANCE
            and joint.probe.max_delta(delta["rotationRowMajor"], rotation) <= joint.ROTATION_MATCH,
            "Held/quiet/returned kinematic pose differs from the declared P1 input")


def _coordinate_floor(world):
    # Native positions are binary32. Use a full ULP for each component and
    # combine as a norm so it also covers any axis of an orthonormal basis.
    return math.hypot(*(math.ldexp(1., max(-149, math.frexp(abs(v))[1] - 24))
                        if v else math.ldexp(1., -149) for v in world["translation"]))


def _measure(poses, side, rest, scale, axis):
    anchor, driver = poses[side], poses[side + 2]
    value = joint.joint_frame(anchor, driver, rest)["translation"][0] / scale
    driver_floor = _coordinate_floor(driver) / scale
    world = sum(v * component for v, component in zip(driver["translation"], axis)) / scale
    return (value, _coordinate_floor(anchor) / scale + driver_floor), (world, driver_floor)


def _amplitudes(phases, channel):
    quiet = statistics.median(row[channel][0] for row in phases["quiet"])
    uncertainty = max(row[channel][1] for row in phases["quiet"])
    return {phase: {"pairs": len(values), "peak": max(abs(row[channel][0] - quiet) for row in values),
                    "positionRoundoffBound": uncertainty + max(row[channel][1] for row in values)}
            for phase, values in phases.items()}


def _contrast(left, right, tolerance):
    quiet_bound = max(left["quiet"]["peak"] + left["quiet"]["positionRoundoffBound"], tolerance)
    lower = max(0., left["held"]["peak"] - left["held"]["positionRoundoffBound"])
    right_bound = max(row["peak"] + row["positionRoundoffBound"] for row in right.values())
    recovered = left["returned"]["peak"] <= quiet_bound + left["returned"]["positionRoundoffBound"]
    return lower, lower > max(quiet_bound, right_bound) and recovered


def _paired_change(before, after):
    return tuple((abs(b - a), a_floor + b_floor) for (a, a_floor), (b, b_floor) in zip(before, after))


def _observed_steps(changes, tolerance):
    controls = (*changes['quiet'][0], *changes['returned'][0],
                *(row for phase in PHASES for row in changes[phase][1]))
    bounds = [max(tolerance, *(rows[index][0] + rows[index][1] for rows in controls)) for index in range(2)]
    return sum(all(delta - floor > bound for (delta, floor), bound in zip(row, bounds))
               for row in changes['held'][0])


def evaluate(rows, spans, *, rest, scale):
    """Evaluate only observed solver positions. The caller owns live admission.

    Pass ordered ROLES from the *current* proven actor graph and rows from
    validate_trace. Spans come from independent phase readback and typed update
    completions on that same QPC clock. Rest frames use the authored pose at
    the observed world scale. A sampled contrast cannot qualify rendering.
    """
    require(type(scale) in (int, float) and math.isfinite(scale) and scale > 0,
            "Positive observed scale required")
    require(set(rest) == set(joint.DRIVERS), "Both direct-parent rest frames required")
    cohorts = _phase_pairs(rows, spans)
    baseline = [joint.pose_transform(pose) for pose in cohorts["quiet"][0]["pre"]]
    axes = [anchor["rotationRowMajor"][::3] for anchor in baseline[:2]]
    channels = {side: {} for side in ("left", "right")}
    changes = {}
    for phase, rows in cohorts.items():
        values = [[], []]
        changes[phase] = [[], []]
        for row in rows:
            both = []
            for moment in ("pre", "post"):
                poses = [joint.pose_transform(pose) for pose in row[moment]]
                _check_anchor(baseline[0], poses[0], STEP * scale if phase == "held" else 0.)
                _check_anchor(baseline[1], poses[1], 0.)
                both.append([_measure(poses, side, rest[name], scale, axes[side])
                             for side, name in enumerate(joint.DRIVERS)])
            for side in range(2):
                before, after = both[0][side], both[1][side]
                values[side].append(after)
                changes[phase][side].append(_paired_change(before, after))
        for side, key in enumerate(channels):
            channels[key][phase] = values[side]

    evidence = {key: {side: _amplitudes(phases, index) for side, phases in channels.items()}
                for index, key in enumerate(("jointLocalX", "driverWorldProjectedX"))}
    contrasts = {name: _contrast(rows["left"], rows["right"], ANCHOR_TOLERANCE / scale)
                 for name, rows in evidence.items()}
    steps = _observed_steps(changes, ANCHOR_TOLERANCE / scale)
    phase_contrast = all(ok for _, ok in contrasts.values())
    return {"status": "sampled-solver-contrast" if phase_contrast and steps else "inconclusive",
            "phaseContrastObserved": phase_contrast, "matchingHeldPrePostPairs": steps,
            "leftHeldPeakLowerBounds": {name: lower for name, (lower, _) in contrasts.items()}, "samples": evidence,
            "renderedMotionQualified": False}
