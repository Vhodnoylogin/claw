"""Pure scorer for an independently admitted, actor-owned CBPC event window."""
from dataclasses import dataclass
import math
import struct

_VR_SCHEMA = "claw-vr-cbpc-events/1"
_VR_PLAYER_SCHEMA = "claw-vr-cbpc-player-events/1"
_SE_SCHEMA = "claw-se-cbpc-events/1"
_SE_RUNTIME = "SkyrimSE-1.7.104"
PLAYER_BODY_CONTACT_NODES = {"NPC EarL [EarL]Bone01": (88, 89, 90, 91), "TailBone02": (108, 109, 110, 111)}


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


def matches_snapshot(snapshot, audience, *, schema=_VR_SCHEMA):
    identity = (audience.pid, audience.nonce, audience.generation, audience.actor, audience.base, audience.cell)
    keys = ("pid", "nonce", "generation", "actorFormId", "baseFormId", "cellFormId")
    allowed = (audience.actor == 0x14 and audience.base == 7 if schema == _VR_PLAYER_SCHEMA
               else 0xFF000000 <= audience.actor < 0xFFFFFFFF)
    require(all(positive_int(value) for value in identity) and allowed
            and audience.sex in ("Male", "Female") and type(audience.bone) is str and audience.bone.strip(),
            "Explicit disposable actor and event scope required")
    require(all(positive_int(snapshot.get(key)) and snapshot[key] == value for key, value in zip(keys, identity))
            and snapshot.get("schema") == schema and snapshot.get("status") == "sealed"
            and snapshot.get("observation") == "skse_mod_callback", "Foreign, unsupported or incomplete witness")
    require(snapshot.get("sealedWithoutLocalDrops") is True
            and type(snapshot.get("dropped")) is int and snapshot["dropped"] == 0
            and type(snapshot.get("unattributed")) is int and snapshot["unattributed"] == 0,
            "Dropped or unattributed event evidence")


def score(snapshot, audience, holds, minimum_duration, minimum_hold_ticks):
    """Score positive and silent holds supplied by an independent scene witness.

    Holds use the same QPC clock and the callback must name the exact
    audience bone. An optional first unattachedNear or unattachedFar hold
    requires silence before append. The caller qualifies capsule or sphere geometry, actor
    continuity, provider and attachment custody independently.
    """
    matches_snapshot(snapshot, audience)
    return _score_holds(snapshot, audience, holds, minimum_duration, minimum_hold_ticks)


def score_se(snapshot, readiness, audience, holds, minimum_duration, minimum_hold_ticks):
    """Score an SE window with its independently observed pre-arm producer receipt."""
    matches_snapshot(snapshot, audience, schema=_SE_SCHEMA)
    require(snapshot.get("runtime") == _SE_RUNTIME and isinstance(readiness, dict)
            and readiness.get("schema") == _SE_SCHEMA
            and readiness.get("runtime") == _SE_RUNTIME and readiness.get("status") == "idle"
            and readiness.get("sinkRegistered") is True and readiness.get("loading") is False
            and all(positive_int(readiness.get(key)) and readiness[key] == snapshot[key]
                    for key in ("pid", "generation")),
            "Foreign or incomplete SE callback producer receipt")
    require("unattachedNear" in holds and "nearDetached" in holds,
            "SE callback contrast requires pre-append and detached holds")
    return _score_holds(snapshot, audience, holds, minimum_duration, minimum_hold_ticks)


def score_player(snapshot, readiness, audience, holds, *, body32, runtime_handle, minimum_hold_ticks):
    """Score the sole configured wand/target contrast after independent geometry admission."""
    matches_snapshot(snapshot, audience, schema=_VR_PLAYER_SCHEMA)
    require(readiness == {"schema": _VR_PLAYER_SCHEMA, "status": "idle", "pid": audience.pid,
                          "generation": audience.generation, "sinkRegistered": True, "loading": False},
            "Foreign or incomplete equipped-player callback producer receipt")
    item, addon = body32
    require(positive_int(item) and positive_int(addon) and positive_int(runtime_handle) and 0 < item >> 24 < 0xFE
            and item & 0xFFFFFF == 0x801 and addon == item - 1 and audience.bone in PLAYER_BODY_CONTACT_NODES,
            "Expected independently admitted equipped player and single target node")
    observed = snapshot.get("body32", {})
    require((observed.get("item"), observed.get("addon"), observed.get("runtimeHandle")) == (item, addon, runtime_handle)
            and observed.get("female") is (audience.sex == "Female") and observed.get("checkedAtSeal") is True,
            "Equipped player Body32 did not remain current at callback seal")
    require("unattachedNear" in holds and "nearDetached" in holds,
            "Player callback contrast requires matching unappended and detached near controls")
    return _score_holds(snapshot, audience, holds, .3, minimum_hold_ticks)


def _score_holds(snapshot, audience, holds, minimum_duration, minimum_hold_ticks):
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
    baseline = next((name for name in ("unattachedNear", "unattachedFar") if name in holds), None)
    if baseline:
        phases = (baseline, *phases)
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

    unattached = collected.pop(baseline) if baseline else None
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
