"""Keep a native screenshot request within a qualified FSMP object window."""

from math import hypot, isfinite

if __package__:
    from .fsmp_phase_comparison import P1_ROLES
else:
    from fsmp_phase_comparison import P1_ROLES


def observe_pose_span(window, tokens):
    """Measure the first pre and all recorded post poses of associated P1 bodies."""
    start, end = (window[key] for key in ("firstPreQpc", "lastPostQpc"))
    if (window["schemaVersion"] != 4 or window["status"] != "complete" or window["coherent"] is not True
            or window["awaitingPost"] is not False or window["callbackDrops"] != 0 or window["failureCode"] != 0
            or window["pairedSteps"] != window["pairedStepLimit"] or window["pairedSteps"] < 2
            or not isfinite(window["minimumPairedHostTimeStep"]) or window["minimumPairedHostTimeStep"] <= 0
            or type(start) is not int or type(end) is not int or not 0 < start < end):
        raise ValueError("Expected a completed, advancing, lossless FSMP object window")
    objects = {row["token"]: row for row in window["objects"]}
    if (len(objects) != len(window["objects"]) or len(objects) != window["objectCount"]
            or set(tokens) != set(P1_ROLES) or len(set(tokens.values())) != len(P1_ROLES)
            or any(type(token) is not int or token <= 0 for token in tokens.values())
            or not set(tokens.values()) <= set(objects)):
        raise ValueError("Expected four distinct, associated P1 roles in the same window")
    poses = {}
    for name, token in tokens.items():
        row = objects[token]
        lo, hi, pre, post = (row["minimumPostWorld"], row["maximumPostWorld"],
                             row["initialPre"]["world"], row["lastPost"]["world"])
        if (any(len(values) != 12 or not all(map(isfinite, values)) for values in (lo, hi, pre, post))
                or any(not a <= value <= b for a, b, value in zip(lo, hi, post, strict=True))):
            raise ValueError("Invalid or incomplete native pose extrema")
        widths = [max(b, first) - min(a, first) for a, b, first in zip(lo, hi, pre, strict=True)]
        poses[name] = {"translationSpanUpperGU": hypot(*widths[9:]),
                       "maximumRotationComponentSpan": max(widths[:9])}
    return {"firstPreQpc": start, "lastPostQpc": end, "pairedSteps": window["pairedSteps"], "poseSpans": poses}


def bracket_capture(observation, request_qpc, response_qpc, *, translation_limit, rotation_limit):
    """Use host QPC for the entire capture call; a completion-frame ID is insufficient."""
    if (type(request_qpc) is not int or type(response_qpc) is not int
            or not observation["firstPreQpc"] < request_qpc < response_qpc < observation["lastPostQpc"]):
        raise ValueError("The complete screenshot request needs to lie inside the solver window")
    if any(type(limit) not in (int, float) or not isfinite(limit) or limit < 0
           for limit in (translation_limit, rotation_limit)):
        raise ValueError("Expected explicit finite pose stability limits")
    failed = [name for name, span in observation["poseSpans"].items()
              if span["translationSpanUpperGU"] > translation_limit
              or span["maximumRotationComponentSpan"] > rotation_limit]
    return {"withinSolverWindow": True, "sampledPoseStable": not failed, "failedRoles": failed,
            "requestQpc": request_qpc, "responseQpc": response_qpc}


def bracket_trace_capture(rows, roles, request_qpc, response_qpc, *, translation_limit, rotation_limit):
    """Use the enclosing pairs from a parsed complete trace for one stable hold.

    Include both the last whole pair before the request and the first whole
    pair after the response. This permits other, moving phases in the same
    trace, while keeping the actual screenshot exposure time unspecified.
    """
    if (len(roles) != len(P1_ROLES) or set(roles) != set(P1_ROLES) or not rows
            or type(request_qpc) is not int or type(response_qpc) is not int
            or not rows[0]["postQpc"] < request_qpc < response_qpc < rows[-1]["preQpc"]):
        raise ValueError("Expected four roles and a complete capture interval inside the paired trace")
    start = max(i for i, row in enumerate(rows) if row["postQpc"] < request_qpc)
    stop = next(i for i, row in enumerate(rows) if row["preQpc"] > response_qpc)
    pairs = rows[start:stop + 1]
    if (len(pairs) < 3 or any(row["preQpc"] >= row["postQpc"] for row in pairs)
            or any(b["pair"] != a["pair"] + 1 or b["preQpc"] <= a["postQpc"]
                   for a, b in zip(pairs, pairs[1:]))):
        raise ValueError("Expected contiguous native pose pairs spanning the capture interval")
    poses = {}
    for index, name in enumerate(roles):
        worlds = [row[phase][index]["world"] for row in pairs for phase in ("pre", "post")]
        if any(len(world) != 12 or not all(map(isfinite, world)) for world in worlds):
            raise ValueError("Expected complete finite trace poses")
        widths = [max(values) - min(values) for values in zip(*worlds, strict=True)]
        poses[name] = {"translationSpanUpperGU": hypot(*widths[9:]),
                       "maximumRotationComponentSpan": max(widths[:9])}
    observation = {"firstPreQpc": pairs[0]["preQpc"], "lastPostQpc": pairs[-1]["postQpc"], "poseSpans": poses}
    return {**bracket_capture(observation, request_qpc, response_qpc,
                              translation_limit=translation_limit, rotation_limit=rotation_limit),
            "firstPair": pairs[0]["pair"], "lastPair": pairs[-1]["pair"], "poseSpans": poses}
