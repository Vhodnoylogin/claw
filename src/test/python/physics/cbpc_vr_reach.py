"""Select a sampled EarR reach window from measured controller poses.

Callers admit the native capture and bind the near/far slices to their
independent controller receipts. This calculation neither dispatches input
nor establishes contact, solver coverage, or motion between samples.
"""

from dataclasses import dataclass
from itertools import pairwise
from math import dist, isfinite

from cbpc_event_readback import positive_int, require
from cbpc_vr_geometry import _finite_positive, _point_segment_distance, _same_basis, _same_pose, _sphere
from src.test.python.integration.fsmp_probe import numbers, transform


EAR = "NPC EarR [EarR]Bone01"
IDENTITY = ("pid", "nonce", "loadEpoch", "actor", "base", "handle", "cell", "addon", "rootToken")
FIXED = ("actorRootWorld", "rightWandWorld", "uprightHmdWorld")
POSES = (*FIXED, "leftWandWorld", "earWorld")


@dataclass(frozen=True)
class PoseWindow:
    """One complete slice of an independently identified callback capture."""

    identity: dict
    role: str
    qpc_frequency: int
    bounds: tuple[int, int]
    rows: list[dict]


def _measured(window, identity, frequency, maximum_gap_ticks):
    require(isinstance(window, PoseWindow) and window.role == EAR and window.identity == identity
            and all(positive_int(window.identity.get(name)) for name in IDENTITY)
            and type(window.qpc_frequency) is int and window.qpc_frequency == frequency
            and isinstance(window.bounds, tuple) and len(window.bounds) == 2
            and all(positive_int(value) for value in window.bounds)
            and isinstance(window.rows, (list, tuple)) and len(window.rows) >= 2,
            "Missing or foreign EarR calibration or target window")
    samples = []
    for row in window.rows:
        require(isinstance(row, dict) and all(name in row for name in POSES)
                and all(positive_int(row.get(name)) for name in ("phaseSequence", "qpcBegin", "qpcEnd"))
                and row["qpcBegin"] <= row["qpcEnd"], "Malformed timed pose")
        samples.append({**row, **{name: transform(row[name]) for name in POSES}})
    require(window.bounds == (samples[0]["qpcBegin"], samples[-1]["qpcEnd"]),
            "Declared QPC window differs from its measured boundaries")
    for earlier, later in pairwise(samples):
        require(later["phaseSequence"] == earlier["phaseSequence"] + 1
                and earlier["qpcEnd"] <= later["qpcBegin"]
                and 0 < later["qpcBegin"] - earlier["qpcBegin"] <= maximum_gap_ticks,
                "Missing callback or QPC cadence gap")
    return samples


def _inner_bounds(samples):
    return samples[0]["qpcEnd"], samples[-1]["qpcBegin"]


def _held_sources(samples, offset, radius, drift):
    baseline = samples[0]["leftWandWorld"]
    sources = []
    for row in samples:
        pose = row["leftWandWorld"]
        require(_same_pose(baseline, pose, drift), "Left controller moved during calibration")
        sources.append(_sphere(pose, offset, radius))
    return sources


def select_window(target, near, far, *, expected_identity, qpc_frequency, capsule, wand,
                  minimum_hold_ticks, minimum_calibration_ticks, maximum_gap_ticks,
                  minimum_surface_margin=.75, maximum_pose_drift=.35):
    """Return one QPC interval with robust sampled reach, or None.

    The three slices must be disjoint in callback sequence and QPC. Each
    target pose is evaluated against every independently measured near pose
    and every far pose. A saved or projected controller transform does not
    qualify as either measurement.
    """
    require(isinstance(expected_identity, dict) and set(expected_identity) == set(IDENTITY)
            and all(positive_int(expected_identity[name]) for name in IDENTITY)
            and 0xFF000000 <= expected_identity["actor"] < 0xFFFFFFFF
            and all(positive_int(x) for x in (qpc_frequency, minimum_hold_ticks,
                                             minimum_calibration_ticks, maximum_gap_ticks))
            and maximum_gap_ticks < min(minimum_hold_ticks, minimum_calibration_ticks)
            and _finite_positive(minimum_surface_margin) and _finite_positive(maximum_pose_drift),
            "Explicit owned capture, clock and positive reach bounds required")
    targets, near_rows, far_rows = streams = [
        _measured(window, expected_identity, qpc_frequency, maximum_gap_ticks) for window in (target, near, far)]
    for first, second in pairwise(sorted(streams, key=lambda sequence: sequence[0]["qpcBegin"])):
        require(first[-1]["qpcEnd"] < second[0]["qpcBegin"]
                and first[-1]["phaseSequence"] < second[0]["phaseSequence"],
                "Target, near and far must be independently measured windows")
    for rows in (near_rows, far_rows):
        begin, end = _inner_bounds(rows)
        require(end - begin >= minimum_calibration_ticks, "Controller calibration window is too short")
    baseline = targets[0]
    require(all(_same_pose(baseline[name], row[name], maximum_pose_drift)
                for stream in streams for row in stream for name in FIXED)
            and all(_same_basis(baseline["leftWandWorld"], row["leftWandWorld"])
                    for stream in streams for row in stream), "Fixed scene controls or left tracking basis changed")
    p1, p2 = numbers(capsule["p1"], 3), numbers(capsule["p2"], 3)
    wand_offset = numbers(wand["local"], 3)
    require(p1 != p2 and _finite_positive(capsule["radius"]) and _finite_positive(wand["radius"]),
            "Expected positive sphere and nondegenerate capsule geometry")
    near_sources = _held_sources(near_rows, wand_offset, wand["radius"], maximum_pose_drift)
    far_sources = _held_sources(far_rows, wand_offset, wand["radius"], maximum_pose_drift)
    require(all(dist(a, b) >= 2 * minimum_surface_margin for a, _ in near_sources for b, _ in far_sources),
            "Near and far controller calibration is ambiguous")

    intervals = []
    current = []
    for row in targets:
        start, radius = _sphere(row["earWorld"], p1, capsule["radius"])
        end, _ = _sphere(row["earWorld"], p2, capsule["radius"])

        def gap(source, source_radius):
            value = _point_segment_distance(source, start, end) - radius - source_radius
            require(isfinite(value), "Invalid nominal signed surface gap")
            return value

        near_gap = max(gap(*source) for source in near_sources)
        far_gap = min(gap(*source) for source in far_sources)
        if near_gap <= -minimum_surface_margin and far_gap >= minimum_surface_margin:
            current.append((row, near_gap, far_gap))
        elif current:
            intervals.append(current)
            current = []
    if current:
        intervals.append(current)

    choices = []
    for interval in intervals:
        begin, end = _inner_bounds([entry[0] for entry in interval])
        if end - begin >= minimum_hold_ticks:
            choices.append((end - begin, end, interval, begin))
    if not choices:
        return None
    _, end, interval, begin = max(choices, key=lambda choice: choice[:2])
    return {"observation": "sampled_nominal_capsule_reach", "providerContactMeasured": False,
            "identity": dict(expected_identity), "role": EAR, "qpcFrequency": qpc_frequency,
            "qpc": (begin, end), "phaseSequence": (interval[0][0]["phaseSequence"], interval[-1][0]["phaseSequence"]),
            "maximumNearSignedGap": max(row[1] for row in interval),
            "minimumFarSignedGap": min(row[2] for row in interval),
            "nearCalibrationQpc": _inner_bounds(near_rows), "farCalibrationQpc": _inner_bounds(far_rows)}
