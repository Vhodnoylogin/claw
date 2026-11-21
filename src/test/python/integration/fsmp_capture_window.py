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
