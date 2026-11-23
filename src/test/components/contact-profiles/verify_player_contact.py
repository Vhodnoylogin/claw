"""Verify the recorded VR player's isolated ear or tail CBPC contact experiment."""

import argparse
from hashlib import sha256
import json
from math import dist
from pathlib import Path

from stage_player_contact import PROFILE_SHA, neutral_capsules
from player_contact_custody import BODY_SHA, CONFIG_SHA, verify_custody
from verify_equipped_turnover import ACTOR, ACTOR_ID, TOPOLOGY, TOPOLOGY_SCHEMA, capture_pair, fixture_forms, route
from verify_pose_ack import unique_object
from verify_pose_contact_window import CLOCK, PHASES, hold_ticks
from verify_tail_refit import CBPC, DRIFT, MARGIN, MIN_HOLD, NANO, QPC, Subject, bank_gap, inspect_frame, ordered, typed
from cbpc_event_readback import Audience, PLAYER_BODY_CONTACT_NODES, positive_int, require, score_player
from cbpc_vr_geometry import _same_pose


SCHEMA = "claw-vr-player-cbpc-contact-reads/1"
EVENTS = "CLAWVRPlayerCBPCEvents"
EVENT_SCHEMA = "claw-vr-cbpc-player-events/1"
BRACKETS = ("before", "attached", "detached", "after")
ARM_NODES = {"left-ear": "NPC EarL [EarL]Bone01", "tail": "TailBone02"}


def decode(payload):
    return json.loads(payload, object_pairs_hook=unique_object)


def listener(ledger, capture, subject, node, sex):
    nonce = capture["nonce"]
    require(positive_int(nonce) and nonce <= 0x7FFFFFFF and subject.generation <= 0x7FFFFFFF,
            "Expected a positive Papyrus nonce and callback generation")
    args = [nonce, subject.generation]
    idle, armed = (decode(typed(ledger, capture[name], EVENTS, "GetCaptureState", "string", [])) for name in ("idle", "armed"))
    require(idle == {"pid": subject.pid, "schema": EVENT_SCHEMA, "generation": subject.generation,
                     "status": "idle", "sinkRegistered": True, "loading": False} and armed == {**idle, "status": "armed"},
            "Expected same-process idle and armed player callback states")
    signed_cell = subject.cell if subject.cell <= 0x7FFFFFFF else subject.cell - 0x100000000
    require(typed(ledger, capture["arm"], EVENTS, "Arm", "bool", [*args, ACTOR_ID, signed_cell]) is True and
            typed(ledger, capture["seal"], EVENTS, "Seal", "bool", args) is True,
            "Missing scoped player callback arm or seal acknowledgement")
    snapshot = decode(typed(ledger, capture["read"], EVENTS, "Read", "string", args))
    return idle, snapshot, Audience(subject.pid, nonce, subject.generation, ACTOR_ID, subject.base, subject.cell, sex, node)


def scene_brackets(ledger, captures, subject, snapshot, fixture, female):
    clocks, epoch, previous = {}, None, 0
    for name in BRACKETS:
        nonce = captures[name]["nonce"]
        require(positive_int(nonce) and previous < nonce <= 0x7FFFFFFF, "Topology nonces must be fresh and increasing")
        _, raw = capture_pair(ledger, captures[name], TOPOLOGY, "CaptureDispatch", TOPOLOGY_SCHEMA, subject.pid, nonce)
        epoch = epoch if epoch is not None else raw["epoch"]
        observed = route(raw, (subject.pid, epoch, subject.base, subject.cell,
                               snapshot["body32"]["runtimeHandle"], int(female)), nonce, fixture, equipped=True)
        require(observed["observedActorWeight"] == 0. and observed["observedActorWeight"] is not None,
                "The isolated fitted capsule bank requires the weight-zero player")
        clocks[name] = observed["captureClock"]
        previous = nonce
    return clocks


def receipts(manifest):
    fixture, capture, captures, holds = (manifest[key] for key in ("fixtureReads", "capture", "topology", "holds"))
    require(set(holds) == set(PHASES) and set(captures) == set(BRACKETS),
            "Expected all observed holds and topology clock brackets")

    def pair(name):
        return [captures[name]["request"], captures[name]["capture"]]

    rows = [manifest["association"], fixture["item"], fixture["addon"], capture["idle"], capture["arm"], capture["armed"],
            *pair("before"), *holds["unattachedNear"], *manifest["attach"], *pair("attached"),
            *holds["nearBefore"], *holds["far"], *holds["nearAfter"], *manifest["detach"],
            *pair("detached"), *holds["nearDetached"], *pair("after"), capture["seal"], capture["read"]]
    ordered(rows, "Missing, reused or out-of-order experiment receipts")
    return rows


def scope_calls(ledger, first, last, recorded, capture):
    """Refuse unaccounted writes while permitting the witness's result polls."""
    for i in range(first, last + 1):
        row, args = ledger[i], ledger[i].get("args", {})
        if i in recorded or row.get("tool") != "papyrus" or args.get("action") != "call":
            continue
        script, method, values = args.get("script"), args.get("function"), args.get("args")
        require((script, method, values) in ((EVENTS, "GetCaptureState", []),
                                             (EVENTS, "Read", [capture["nonce"], capture["generation"]])) or
                (script, method) == (TOPOLOGY, "Read"), "Unaccounted Papyrus operation in the player contact window")


def capsule_calls(ledger, manifest, node, bank):
    for item, append, detach in zip(bank, manifest["attach"], manifest["detach"], strict=True):
        values, index = item["geometry"], item["colliderIndex"]
        require(typed(ledger, append, CBPC, "AttachColliderCapsule", "bool",
                      [ACTOR, node, values[:3], values[6], values[3:6], values[6], 0., index, True]) is True and
                typed(ledger, detach, CBPC, "DetachCollider", "bool", [ACTOR, node, 1, index, True]) is True,
                "Expected acknowledged attach and detach of all four fitted capsules")


def measured_holds(ledger, holds, subject, handle, node, bank, clocks):
    origin = previous = None
    windows, gaps = {}, {}
    for name in PHASES:
        rows = holds[name]
        require(3 <= len(rows) <= 8, "Each hold requires bounded independent frame samples")
        frames = [inspect_frame(ledger, index, subject, node, own_body=True) for index in rows]
        start, end, last_read = hold_ticks(frames, [ledger[index]["result"].get("durationUs") for index in rows])
        lower, upper = (("before", "attached") if name == "unattachedNear" else
                        ("detached", "after") if name == "nearDetached" else ("attached", "detached"))
        require(clocks[lower]["qpcEnd"] < frames[0]["ns"] * QPC // NANO and last_read < clocks[upper]["qpcBegin"],
                "Measured frames are outside their attachment topology bracket")
        for row in ledger[rows[0]:rows[-1] + 1]:
            require(row.get("kind") != "driver" and row.get("tool", "inspect") == "inspect",
                    "A non-observer operation interrupted the measured hold")
        first = frames[0]
        phase_gaps = []
        for frame in frames:
            origin = origin or frame
            identity = frame["player"][0]
            require(frame["session"] == origin["session"] and frame["epoch"] == origin["epoch"] and
                    identity == origin["player"][0] and identity["runtimeHandle"] == handle and
                    (previous is None or all(frame[key] > previous[key] for key in ("sample", "frame", "ns"))) and
                    _same_pose(frame["root"], origin["root"], DRIFT) and
                    all(_same_pose(value, origin["controls"][key], DRIFT) for key, value in frame["controls"].items()) and
                    _same_pose(frame["left"], first["left"], DRIFT) and dist(frame["source"], first["source"]) <= DRIFT,
                    "Player, controller or Observer identity drifted during contact holds")
            previous = frame
            phase_gaps.append(bank_gap(frame, bank))
        gap = dist(first["source"], origin["source"])
        require((gap >= 2 * MARGIN and min(phase_gaps) >= MARGIN) if name == "far" else
                (gap <= DRIFT and _same_pose(first["left"], origin["left"], DRIFT) and max(phase_gaps) <= -MARGIN),
                "Hand did not reproduce nominal near/far clearance against the fitted bank")
        windows[name] = (start, end)
        gaps[name] = [min(phase_gaps), max(phase_gaps)]
    return windows, gaps


def verify(manifest, ledger, profile):
    require(manifest["schema"] == SCHEMA and manifest["clock"] == CLOCK, "Expected the pinned player contact clock and schema")
    node = ARM_NODES[manifest["arm"]]
    sex = manifest["sex"]
    require(sex in ("Male", "Female"), "Expected the equipped player's recorded sex")
    capture = manifest["capture"]
    subject = Subject(manifest["pid"], ACTOR_ID, 7, manifest["cell"], capture["generation"])
    require(all(positive_int(value) for value in vars(subject).values()) and subject.cell <= 0xFFFFFFFF,
            "Invalid scoped player receipt identity")
    indices = receipts(manifest)
    require(indices[-1] < len(ledger), "Receipt index exceeds the recorded steps")
    scope_calls(ledger, capture["arm"], capture["read"], set(indices), capture)
    idle, snapshot, audience = listener(ledger, capture, subject, node, sex)
    fixture = fixture_forms(ledger, manifest["fixtureReads"])
    clocks = scene_brackets(ledger, manifest["topology"], subject, snapshot, fixture, sex == "Female")
    require(snapshot["qpcFrequency"] == QPC and all(a["qpcEnd"] < b["qpcBegin"] for a, b in zip(
        (clocks[name] for name in BRACKETS[:-1]), (clocks[name] for name in BRACKETS[1:]), strict=True)) and
        snapshot["armedQpc"] < clocks["before"]["qpcBegin"] and clocks["after"]["qpcEnd"] < snapshot["closedQpc"],
        "Topology clock brackets are overlapping or outside the sealed callback window")
    slots = PLAYER_BODY_CONTACT_NODES[node]
    bank = neutral_capsules(profile, slots)[sex.lower()]
    capsule_calls(ledger, manifest, node, bank)
    handle = snapshot["body32"]["runtimeHandle"]
    windows, gaps = measured_holds(ledger, manifest["holds"], subject, handle, node, [item["geometry"] for item in bank], clocks)
    result = score_player(snapshot, idle, audience, windows, body32=fixture, runtime_handle=handle, minimum_hold_ticks=MIN_HOLD)
    return {**result, "actor": ACTOR_ID, "node": node, "slots": list(slots), "arm": manifest["arm"], "holdQpc": windows,
            "signedGapRangesGu": gaps, "providerShapeInventoryVerified": False, "perSlotCallbackAttribution": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "steps", "profile", "state", "backing", "config", "body"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = decode(args.manifest.read_bytes())
        data = {name: getattr(args, name).read_bytes() for name in ("steps", "profile", "state", "backing", "config", "body")}
        digests = {name: sha256(payload).hexdigest() for name, payload in data.items()}
        require(all(digests[key] == digest for key, digest in (("profile", PROFILE_SHA), ("config", CONFIG_SHA), ("body", BODY_SHA))) and
                all(digests[key] == manifest["sha256"][key] for key in ("steps", "state", "backing")),
                "A recorded input or pinned asset hash does not match")
        rows = [decode(line) for line in data["steps"].splitlines()]
        result = verify(manifest, rows, decode(data["profile"]))
        backing = decode(data["backing"])
        result["custody"] = verify_custody(decode(data["state"]), rows[manifest["association"]],
                                           backing.get("providerBacking", backing), decode(data["config"]), data["body"], manifest)
        result["inputSha256"] = digests
    except (KeyError, ValueError, TypeError, OSError, AttributeError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result["status"] == "qualified-emission-contrast" else 1


if __name__ == "__main__":
    raise SystemExit(main())
