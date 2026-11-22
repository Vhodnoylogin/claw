"""Join the live pose ACK, scene measurements and sealed CBPC callback for one group."""

import argparse
from hashlib import sha256
import json
from math import dist
from pathlib import Path

from posed_contact import native_vector, read_pose
from prepare_pose_ack_contact import banks_at_token
from verify_pose_ack import selected_receipts
from verify_tail_refit import (
    DRIFT, MARGIN, MAX_GAP_NS, MIN_HOLD, NANO, NATIVE, POSE, QPC, Subject,
    _same_pose, bank_gap, callback_snapshot, inspect_frame, ordered, positive_int, require, transform, typed,
)
from cbpc_event_readback import score


CONTROL = "CLAWPhysicsControl"
PHASES = ("unattachedNear", "nearBefore", "far", "nearAfter", "nearDetached")
ACTIVE = PHASES[1:4]
CLOCK = "msvc-14.51.36231-qpc-10000000"
TICKS_PER_US = QPC // 1_000_000


def pose_sample(ledger, index, subject, model, receipt):
    raw = json.loads(typed(ledger, index, POSE, "ReadNpc", "string"))
    args = [raw["nonce"], raw["sequence"]]
    typed(ledger, index, POSE, "ReadNpc", "string", args)
    sample = raw["sample"]
    sex, morphs, weight, _ = read_pose(raw, native_vector(model, raw), model)
    require((raw["pid"], raw["qpcFrequency"], sample["actor"], sample["base"], sample["cell"]) ==
            (subject.pid, QPC, subject.actor, subject.base, subject.cell) and sex == "male" and
            sample["race"] == 0xCDD84 and sample["bodyAddon"] == 0xCDD87 and sample["bodyItem"] == 0xCDD86 and
            weight == receipt["weight"] and morphs == {item["name"]: item["value"] for item in receipt["morphs"]},
            "Independent pose does not match the actor, fitted input vector or body slot")
    return sample, raw["sequence"]


def hold_ticks(frames, durations):
    require(all(type(value) is int and 0 <= value <= MAX_GAP_NS // 1000 for value in durations),
            "Missing or invalid Observer task duration")
    ends = [frame["ns"] + (duration + 1) * 1000 for frame, duration in zip(frames, durations, strict=True)]
    require(all(0 < current["ns"] - previous["ns"] <= MAX_GAP_NS and end <= current["ns"]
                for previous, current, end in zip(frames[:-1], frames[1:], ends[:-1], strict=True)),
            "Observer cadence leaves a gap or task samples overlap")
    # The first frame begins before its transforms are read. The performed
    # measurements support a dwell only from its completion to the last start.
    start = (ends[0] * QPC + NANO - 1) // NANO
    end = frames[-1]["ns"] * QPC // NANO
    require(end - start >= MIN_HOLD, "Measured hold is too short after inward rounding")
    return start, end, (ends[-1] * QPC + NANO - 1) // NANO


def cap_values(bank):
    return [[*ends[0], *ends[1], radius] for ends, radius in bank]


def verify(manifest, ledger, ack_lines, model):
    require(manifest["schema"] == "claw-vr-pose-contact-reads/1" and manifest["clock"] == CLOCK,
            "Expected the pinned pose-contact schema and 10 MHz QPC provenance")
    subject = Subject(**manifest["subject"])
    require(all(positive_int(value) for value in vars(subject).values()) and
            0xFF000000 <= subject.actor < 0xFFFFFFFF and subject.base & 0xFFFFFF == 0x800,
            "An exact disposable pose fixture is required")
    token, node = manifest["token"], manifest["node"]
    require(isinstance(node, str) and node in {"TailBone02", "NPC EarL [EarL]Bone01"},
            "Choose the approved single-node tail or left ear case")
    receipt, slots, _, old, new = banks_at_token(ack_lines, subject.actor, subject.generation, model, token, node)
    old, new = cap_values(old), cap_values(new)
    require(not receipt["female"], "Expected the staged male fixture")
    chain = [row[2] for row in selected_receipts(ack_lines, subject.actor, subject.generation)]
    first_publication = TICKS_PER_US * chain[0]["publishedUs"]
    acknowledged = TICKS_PER_US * (receipt["acknowledgedUs"] + 1) - 1
    next_publication = next((TICKS_PER_US * row["publishedUs"] for row in chain if row["token"] > token), None)

    capture, holds, release = manifest["capture"], manifest["holds"], manifest["release"]
    baseline = "unattachedFar" if "unattachedFar" in holds else "unattachedNear"
    phases = (baseline, *PHASES[1:])
    require(set(holds) == set(phases), "Complete pre-append, near, far, repeat and detached holds required")
    indices = [manifest["modelRead"], capture["idle"], capture["arm"], *holds[baseline]["frames"], manifest["ledgerCount"]]
    for name in ACTIVE:
        hold = holds[name]
        indices += [hold["currentBefore"], hold["poseBefore"], *hold["frames"], hold["poseAfter"], hold["currentAfter"]]
    indices += [release["call"], release["count"], release["actorCurrent"], *holds["nearDetached"]["frames"], capture["seal"], capture["read"]]
    ordered(indices, "Reused, missing or out-of-order ledger receipts")
    require(indices[-1] < len(ledger), "Receipt index exceeds the captured ledger")
    require(typed(ledger, manifest["modelRead"], NATIVE, "GetModelIdentity", "string", []) == model["modelIdentity"],
            "The observed Distribution fit differs from the staged profile")
    enabled = sum(item["sexMask"] in ("male", "both") for item in model["slots"])
    host_counts = (typed(ledger, manifest["ledgerCount"], CONTROL, "GetLedgerCount", "int", [0]),
                   typed(ledger, release["call"], CONTROL, "ReleaseActor", "int", [0]),
                   typed(ledger, release["count"], CONTROL, "GetLedgerCount", "int", [0]))
    require(all(type(value) is int for value in host_counts) and host_counts == (enabled, 0, 0) and
            typed(ledger, release["actorCurrent"], NATIVE, "ActorCurrent", "bool", [subject.form]) is False,
            "Full attachment or scoped host retirement is unproven")
    event, audience = callback_snapshot(ledger, subject, capture, node)
    require(event["qpcFrequency"] == QPC and event["armedQpc"] < first_publication,
            "Native and CBPC clocks or initial capture order differ")

    origin = previous = pose_origin = last_pose = near_source = None
    windows, gaps = {}, {}
    for name in phases:
        hold = holds[name]
        rows = hold["frames"]
        require(2 <= len(rows) <= 8, "Each hold needs bounded independent frame samples")
        frames = [inspect_frame(ledger, index, subject, node) for index in rows]
        durations = [ledger[index]["result"].get("durationUs") for index in rows]
        start, end, last_read = hold_ticks(frames, durations)
        earliest = frames[0]["ns"] * QPC // NANO
        require(event["armedQpc"] <= earliest and last_read < event["closedQpc"],
                "Observer tasks extend outside the sealed capture")
        if name == baseline:
            require(last_read < first_publication, "Pre-append samples overlap initial publication")
        if name in ACTIVE:
            expected = [subject.form, subject.generation, token]
            for key in ("currentBefore", "currentAfter"):
                require(typed(ledger, hold[key], NATIVE, "SnapshotCurrent", "bool", expected) is True,
                        "The exact acknowledged token did not remain current around the hold")
            before, seq_before = pose_sample(ledger, hold["poseBefore"], subject, model, receipt)
            after, seq_after = pose_sample(ledger, hold["poseAfter"], subject, model, receipt)
            require(acknowledged < before["qpcBegin"] <= before["qpcEnd"] < earliest and
                    last_read < after["qpcBegin"] <= after["qpcEnd"] and
                    (next_publication is None or after["qpcEnd"] < next_publication),
                    "The pose and measured hold do not fit the accepted snapshot window")
            for sample, sequence in ((before, seq_before), (after, seq_after)):
                pose_origin = pose_origin or sample
                require(all(sample[key] == pose_origin[key] for key in ("rootToken", "runtimeHandle", "loadEpoch")) and
                        all(_same_pose(transform(sample[key]), transform(pose_origin[key]), DRIFT)
                            for key in ("rootWorld", "bodyCloneWorld")) and
                        (last_pose is None or (sequence > last_pose[0] and sample["qpcBegin"] > last_pose[1])),
                        "Independent pose sequence or loaded model incarnation changed")
                last_pose = (sequence, sample["qpcEnd"])

        for row in ledger[rows[0]:rows[-1] + 1]:
            require(not (row.get("kind") == "driver" and row.get("action") in ("publish", "release")) and
                    not (row.get("tool") == "papyrus" and row.get("args", {}).get("action") == "call"),
                    "A driver or Papyrus operation interrupted the observed hold")
        old_gap, new_gap = [], []
        first = frames[0]
        for frame in frames:
            origin = origin or frame
            require(frame["session"] == origin["session"] and frame["epoch"] == origin["epoch"] and
                    (previous is None or all(previous[key] < frame[key] for key in ("sample", "frame", "ns"))) and
                    all(frame[key][0] == origin[key][0] and dist(frame[key][1], origin[key][1]) <= DRIFT and
                        _same_pose(frame[key][2], origin[key][2], DRIFT) for key in ("player", "actor")) and
                    _same_pose(frame["root"], origin["root"], DRIFT) and
                    all(_same_pose(value, origin["controls"][key], DRIFT) for key, value in frame["controls"].items()) and
                    _same_pose({**origin["left"], "translation": frame["left"]["translation"]}, frame["left"], DRIFT) and
                    dist(frame["source"], first["source"]) <= DRIFT,
                    "Controller motion or incoherent actor/Observer identity within a hold")
            if name in ACTIVE:
                require(frame["actor"][0]["runtimeHandle"] == pose_origin["runtimeHandle"] and
                        _same_pose(frame["actor"][2], transform(pose_origin["rootWorld"]), DRIFT),
                        "World Observer and native pose witness refer to different body incarnations")
            previous = frame
            old_gap.append(bank_gap(frame, old))
            new_gap.append(bank_gap(frame, new))
        if name == "nearBefore":
            near_source = first["source"]
            offset = dist(near_source, origin["source"])
            require(offset <= DRIFT if baseline == "unattachedNear" else offset >= 2 * MARGIN,
                    "The reached near pose does not contrast with the pre-append control")
        elif name != baseline:
            offset = dist(first["source"], near_source)
            require(offset >= 2 * MARGIN if name == "far" else offset <= DRIFT,
                    "The controller did not reproduce the required test position")
        if name in ACTIVE or name == "unattachedFar":
            require(min(old_gap) >= MARGIN, "Old capsule bank is not separated in the measured pose")
        require(min(new_gap) >= MARGIN if name in ("unattachedFar", "far") else max(new_gap) <= -MARGIN,
                "The updated capsule bank does not give the measured near/far margin")
        windows[name] = (start, end)
        gaps[name] = {"oldGapGu": [min(old_gap), max(old_gap)], "newGapGu": [min(new_gap), max(new_gap)]}

    result = score(event, audience, windows, .3, MIN_HOLD)
    return {**result, "actor": subject.actor, "node": node, "token": token, "previousToken": receipt["previousToken"],
            "preAppendPosition": baseline,
            "slots": slots, "holdQpc": windows, "worldGapRanges": gaps, "providerShapeInventoryVerified": False,
            "perSlotCallbackAttribution": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("manifest", "steps", "ack-log", "profile"):
        parser.add_argument("--" + arg, type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_bytes())
        inputs = {key: getattr(args, key).read_bytes() for key in ("steps", "ack_log", "profile")}
        require({key: sha256(raw).hexdigest() for key, raw in inputs.items()} == manifest["sha256"],
                "The run manifest does not pin these exact ledger, ACK log and profile bytes")
        result = verify(manifest, [json.loads(line) for line in inputs["steps"].splitlines()],
                        inputs["ack_log"].decode("utf-8-sig").splitlines(), json.loads(inputs["profile"]))
    except (KeyError, TypeError, ValueError, OSError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result["status"] == "qualified-emission-contrast" else 1


if __name__ == "__main__":
    raise SystemExit(main())
