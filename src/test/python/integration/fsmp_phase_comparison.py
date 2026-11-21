"""Compare joined passive and active FSMP observations at the same game boundaries."""

from math import hypot, isfinite
from struct import pack, unpack

if __package__:
    from .fsmp_scene_writeback import _delta, _position, score_right_control
else:
    from fsmp_scene_writeback import _delta, _position, score_right_control


ROLES = ("leftAnchor", "leftP1", "rightAnchor", "rightP1")
PHASES = ("outerEntry", "beforeStockWrite", "afterStockWrite", "afterOuterUpdate")
P1_ROLES = ("NPC L PreBreast P1", "NPC L Breast P1", "NPC R PreBreast P1", "NPC R Breast P1")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _float32(value):
    return unpack("<f", pack("<f", value))[0]


def observe_passive_admission(roles):
    """Replay the existing private provider baseline check before requesting a pulse."""
    _require(len(roles) == 15 and tuple(row["name"] for row in roles[11:]) == P1_ROLES,
             "The exact fifteen-role passive solver receipt is required")
    maximum = _float32(.008)
    measured = {}
    failed = []
    for index, role in enumerate(roles[11:]):
        anchor = index % 2 == 0
        _require(role["flags"] == (2 if anchor else 0) and
                 role["inverseMass"] == (0. if anchor else 20.) and role["engineScale"] == 1.,
                 "The passive provider role has a different rig type, mass or scale")
        before, after = (_position(role[key][9:]) for key in ("pre", "post"))
        shift = tuple(_float32(value) for value in _delta(after, before))
        measured[role["name"]] = shift
        if max(map(abs, shift)) > maximum:
            failed.append(role["name"])
    return {"stationary": not failed, "componentCeilingGU": maximum,
            "solverTranslationsGU": measured, "failedRoles": failed}


def _read(window):
    times = window["phaseQpc"]
    _require(set(times) == set(PHASES), "Every nested game boundary must have a timestamp")
    timestamps = tuple(times[name] for name in PHASES)
    _require(all(type(stamp) is int and stamp > 0 for stamp in timestamps)
             and all(a < b for a, b in zip(timestamps, timestamps[1:])),
             "Game boundary times must be strictly increasing")
    snapshots = window["worldByPhase"]
    _require(set(snapshots) == set(PHASES), "Every game boundary must have a pose")
    poses = {}
    for phase, snapshot in snapshots.items():
        _require(set(snapshot) == set(ROLES), "Every phase must include both drivers and both anchors")
        poses[phase] = {role: _position(value) for role, value in snapshot.items()}
    return timestamps, poses


def _motion(poses, phase):
    before, after = (poses[name] for name in ("beforeStockWrite", phase))
    result = {}
    for side in ("left", "right"):
        node, anchor = side + "P1", side + "Anchor"
        world = _delta(after[node], before[node])
        follow = _delta(after[anchor], before[anchor])
        result[side] = {"worldDeltaGU": world, "anchorDeltaGU": follow,
                        "relativeDeltaGU": _delta(world, follow)}
    return result


def compare(passive, active):
    """Score two normalized observations, with custody and actual force joined upstream.

    The caller verifies the actor and fixture identities, source clocks, writer
    measurements, force receipt and ordinary force clear. Equal solver durations
    must be observations from the two actual windows. A phase or renderer metric
    cannot substitute for a failed absolute stock-writer control.
    """
    _require(bool(passive["scope"]) and passive["scope"] == active["scope"],
             "Both windows must retain the same run, provider and four-role ownership")
    _require(passive["forceApplied"] is False and active["forceApplied"] is True,
             "One observed passive window and one observed force window are required")
    _require(set(passive["incomingParentLocal"]) == set(ROLES)
             and passive["incomingParentLocal"] == active["incomingParentLocal"],
             "The incoming parent and local transforms must match in all four roles")
    steps = tuple(active["solverSteps"])
    _require(tuple(passive["solverSteps"]) == steps and len(steps) == 2 and
             all(type(step) in (int, float) and isfinite(step) and step > 0 for step in steps),
             "Both windows require the same two observed positive solver step durations")
    quiet_times, quiet = _read(passive)
    pulse_times, pulse = _read(active)
    _require(quiet_times[-1] < pulse_times[0], "The passive window must finish before the active window opens")
    _require(all(quiet[phase] == pulse[phase] for phase in PHASES[:2]),
             "Incoming world poses must match at outer entry and before stock write")

    results = {}
    for phase in PHASES[2:]:
        baseline, response = (_motion(poses, phase) for poses in (quiet, pulse))
        _require(all(baseline[side]["anchorDeltaGU"] == response[side]["anchorDeltaGU"] for side in response),
                 "The anchor trajectories must match at corresponding phases")
        results[phase] = {"passive": baseline, "active": response, "activeMinusPassiveGU": {
            side: _delta(response[side]["relativeDeltaGU"], baseline[side]["relativeDeltaGU"])
            for side in response
        }}
    stock = results["afterStockWrite"]
    _require(all(role["anchorDeltaGU"] == (0., 0., 0.)
                 for lane in ("passive", "active") for role in stock[lane].values()),
             "The original absolute stock-writer gate requires stationary anchors")
    return {"phases": results, "rightStockControls": {
        lane: score_right_control({"stockWriteDistanceGU": hypot(*stock[lane]["right"]["worldDeltaGU"])})
        for lane in ("passive", "active")
    }}
