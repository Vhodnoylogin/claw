"""Pure scorer for an independently admitted, actor-owned CBPC event window."""
from dataclasses import dataclass
import math
import struct


@dataclass(frozen=True)
class Audience:
    pid: int
    nonce: int
    generation: int
    actor: int
    base: int
    cell: int
    sex: str
    bone: str


def require(ok, message):
    if not ok:
        raise ValueError(message)


def positive_int(value):
    return type(value) is int and value > 0


def matches_snapshot(snapshot, audience):
    identity = (audience.pid, audience.nonce, audience.generation, audience.actor, audience.base, audience.cell)
    keys = ("pid", "nonce", "generation", "actorFormId", "baseFormId", "cellFormId")
    require(all(positive_int(value) for value in identity) and 0xFF000000 <= audience.actor < 0xFFFFFFFF
            and audience.sex in ("Male", "Female") and type(audience.bone) is str and audience.bone.strip(),
            "Explicit disposable actor and event scope required")
    require(all(positive_int(snapshot.get(key)) and snapshot[key] == value for key, value in zip(keys, identity))
            and snapshot.get("schema") == "claw-vr-cbpc-events/1" and snapshot.get("status") == "sealed"
            and snapshot.get("observation") == "skse_mod_callback", "Foreign, unsupported or incomplete witness")
    require(snapshot.get("sealedWithoutLocalDrops") is True
            and type(snapshot.get("dropped")) is int and snapshot["dropped"] == 0
            and type(snapshot.get("unattributed")) is int and snapshot["unattributed"] == 0,
            "Dropped or unattributed event evidence")


def score(snapshot, audience, holds, minimum_duration, minimum_hold_ticks):
    """Score positive and silent holds supplied by an independent scene witness.

    Holds use the same QPC clock and the callback must name the exact
    audience bone. An optional first unattachedNear hold requires silence
    before append. The caller qualifies capsule or sphere geometry, actor
    continuity, provider and attachment custody independently.
    """
    matches_snapshot(snapshot, audience)
    require(type(minimum_duration) in (int, float) and math.isfinite(minimum_duration) and minimum_duration > 0,
            "Explicit positive configured engine-duration threshold required")
    try:
        minimum_duration, = struct.unpack("<f", struct.pack("<f", minimum_duration))
    except (OverflowError, struct.error) as error:
        raise ValueError("Float32 engine-duration threshold required") from error
    require(math.isfinite(minimum_duration) and minimum_duration > 0 and positive_int(minimum_hold_ticks),
            "Positive float32 threshold and explicit QPC hold minimum required")
    frequency, request, armed, closed = (snapshot.get(key) for key in
                                         ("qpcFrequency", "requestedQpc", "armedQpc", "closedQpc"))
    require(all(positive_int(value) for value in (frequency, request, armed, closed)) and request <= armed < closed,
            "Invalid capture clock or interval")
    require(closed - request < 60 * frequency, "Capture closed at or beyond witness expiry")
    phases = ("nearBefore", "far", "nearAfter")
    if "nearDetached" in holds:
        phases += ("nearDetached",)
    if "unattachedNear" in holds:
        phases = ("unattachedNear", *phases)
    require(set(holds) == set(phases), "Complete near/far/near hold set required")
    last = armed - 1
    for phase in phases:
        begin, end = holds[phase]
        require(positive_int(begin) and positive_int(end) and last < begin < end < closed
                and end-begin >= minimum_hold_ticks, "Holds overlap, are too short or lie outside the sealed window")
        last = end

    events = snapshot.get("events")
    require(isinstance(events, list) and len(events) <= 128 and type(snapshot.get("lastSequence")) is int
            and snapshot["lastSequence"] == len(events), "Incomplete local callback sequence")
    collected = {phase: [] for phase in phases}
    gaps = 0
    last = armed
    event_name = f"CBPCPlayerCollisionWith{audience.sex}Event"
    for sequence, row in enumerate(events, start=1):
        qpc, duration = row.get("qpc"), row.get("numArg")
        require(positive_int(row.get("sequence")) and row["sequence"] == sequence
                and positive_int(qpc) and last <= qpc <= closed, "Out-of-order local callback")
        require(row.get("eventName") == event_name and row.get("strArg") == audience.bone
                and row.get("senderFormId") == audience.actor, "Unexpected actor, event or group payload")
        require(type(duration) in (int, float) and math.isfinite(duration) and duration >= minimum_duration,
                "Unqualified provider duration payload")
        phase = next((name for name, (begin, end) in holds.items() if begin <= qpc <= end), None)
        if phase is None:
            gaps += 1
        else:
            collected[phase].append(duration)
        last = qpc

    unattached = collected.pop("unattachedNear", None)
    require(not unattached, "Provider emitted a callback in the pre-append hold")
    has_controls = bool(collected["nearBefore"] and collected["nearAfter"])
    silent = not collected["far"] and not collected.get("nearDetached")
    result = {"status": "qualified-emission-contrast" if has_controls and silent else "insufficient-emission-contrast",
              "qualifiedHeldEventCounts": {phase: len(values) for phase, values in collected.items()},
              "minimumObservedEngineDurations": {phase: min(values) if values else None for phase, values in collected.items()},
              "eventsOutsideHolds": gaps, "solverPairCoverageQualified": False, "havokContactQualified": False}
    if unattached is not None:
        result["preAppendCallbacks"] = 0
    return result
