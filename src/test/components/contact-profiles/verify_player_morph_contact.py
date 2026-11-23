"""Verify fixed-wand contact across three full morph refits of the equipped VR player."""

import argparse
from hashlib import sha256
import json
from math import dist
from pathlib import Path

from prepare_pose_ack_contact import read_morph_refits
from verify_equipped_turnover import EAR_MORPHS, TAIL_MORPHS, NATIVE, TOPOLOGY, TOPOLOGY_SCHEMA, capture_pair, fixture_forms, linked_pose, route
from verify_player_contact import ACTOR, ACTOR_ID, ARM_NODES, CLOCK, EVENTS, Subject, decode, listener
from verify_pose_contact_window import CONTROL, TICKS_PER_US, cap_values, hold_ticks
from verify_tail_refit import DRIFT, MARGIN, MIN_HOLD, NANO, QPC, bank_gap, inspect_frame, ordered, positive_int, require, typed
from cbpc_event_readback import MORPH_REFIT_PHASES, PLAYER_BODY_CONTACT_NODES, score_player
from cbpc_vr_geometry import _same_pose


SCHEMA = "claw-vr-player-morph-contact-reads/1"
TEST_KEY = "CLAWTest.PlayerMorphContact"


def scoped_operations(ledger, start, end, recorded, allowed_poses, channel):
    for index in range(start, end):
        if index in recorded:
            continue
        row = ledger[index]
        tool, args = row.get("tool"), row.get("args", {})
        if tool is None or tool == "inspect":
            continue
        require(tool == "papyrus", "Unaccounted tool operation inside the callback window")
        script, method, values = args.get("script"), args.get("function"), args.get("args")
        if method == "Read" and (script, tuple(values)) in allowed_poses:
            continue
        if (script, method, values) == (EVENTS, "GetCaptureState", []):
            continue
        morph = [ACTOR, channel, TEST_KEY]
        permitted = script == "NiOverride" and (
            (method == "SetBodyMorph" and values[:3] == morph and len(values) == 4) or
            (method in ("GetBodyMorph", "HasBodyMorph", "ClearBodyMorph") and values == morph) or
            (method == "UpdateModelWeight" and values == [ACTOR]))
        require(permitted, "Unaccounted Papyrus operation inside the callback window")


def measured_phase(ledger, frame_indices, subject, node, banks, observed_route, pose, origin, previous):
    frames = [inspect_frame(ledger, index, subject, node, own_body=True) for index in frame_indices]
    durations = [ledger[index]["result"].get("durationUs") for index in frame_indices]
    start, end, finish = hold_ticks(frames, durations)
    earliest = frames[0]["ns"] * QPC // NANO
    require(all(row.get("tool") == "inspect" and row.get("kind") != "driver"
                for row in ledger[frame_indices[0]:frame_indices[-1] + 1]), "Operation interrupted the measured hold")
    require(all(_same_pose(frames[0][key], pose[key], DRIFT) for key in ("left", "targetPose")),
            "Post-VRIK/HIGGS witness and World Observer disagree on the target bone or wand")
    origin = origin or frames[0]
    ranges = [[] for _ in banks]
    for frame in frames:
        identity = frame["player"][0]
        require(frame["session"] == origin["session"] and frame["epoch"] == origin["epoch"] and
                identity == origin["player"][0] and identity["runtimeHandle"] == observed_route["actorRuntimeHandle"] and
                (previous is None or all(previous[key] < frame[key] for key in ("sample", "frame", "ns"))) and
                all(_same_pose(frame[key], origin[key], DRIFT) for key in ("root", "left", "targetPose")) and
                all(_same_pose(value, origin["controls"][key], DRIFT) for key, value in frame["controls"].items()) and
                dist(frame["source"], origin["source"]) <= DRIFT,
                "Player, target bone or wand drifted across the fixed-controller comparison")
        previous = frame
        for bank, gaps in zip(banks, ranges, strict=True):
            gaps.append(bank_gap(frame, bank))
    require(min(ranges[0]) >= MARGIN and max(ranges[1]) <= -MARGIN and min(ranges[2]) >= MARGIN,
            "Observed wand does not separate all three banks at the same measured bone transform")
    return (start, end), (earliest, finish), origin, previous, [[min(gaps), max(gaps)] for gaps in ranges]


def verify(manifest, ledger, ack_lines, model):
    require(manifest["schema"] == SCHEMA and manifest["clock"] == CLOCK,
            "Expected equipped VR player morph-contact receipts with a common clock")
    arm, sex, capture = manifest["arm"], manifest["sex"], manifest["capture"]
    node = ARM_NODES[arm]
    require(sex in ("Male", "Female"), "Invalid observed sex")
    subject = Subject(manifest["pid"], ACTOR_ID, 7, manifest["cell"], capture["generation"])
    require(all(positive_int(value) for value in vars(subject).values()) and subject.cell <= 0xFFFFFFFF,
            "Invalid player contact identity")
    phases = manifest["phases"]
    require(set(phases) == set(MORPH_REFIT_PHASES), "Expected baseline, morphed and returned holds")
    rows = [phases[name] for name in MORPH_REFIT_PHASES]
    require(all(3 <= len(row["frames"]) <= 8 for row in rows), "Expected bounded World Observer frames for each morph")
    indices = [manifest["fixtureReads"]["item"], manifest["fixtureReads"]["addon"], manifest["generationRead"],
               capture["idle"], capture["arm"], capture["armed"]]
    for row in rows:
        indices += [row["currentBefore"], *(row["topology"][key] for key in ("request", "capture")),
                    *(row["pose"][key] for key in ("request", "capture")), *row["frames"], row["currentAfter"]]
    indices += [capture["seal"], capture["read"]]
    ordered(indices, "Reused or out-of-order morph contact receipts")
    require(indices[-1] < len(ledger), "Receipt index exceeds the recorded steps")
    generation = typed(ledger, manifest["generationRead"], CONTROL, "GetGeneration", "int", [0])
    require(positive_int(generation), "Expected the native actor registration generation")
    fixture = fixture_forms(ledger, manifest["fixtureReads"])
    idle, snapshot, audience = listener(ledger, capture, subject, node, sex)
    handle = snapshot["body32"]["runtimeHandle"]
    tokens = [row["token"] for row in rows]
    selected, chain = read_morph_refits(ack_lines, model, actor=ACTOR_ID, generation=generation, tokens=tokens)
    fields = TAIL_MORPHS if arm == "tail" else EAR_MORPHS
    before, adjusted = ({row["name"]: row["value"] for row in entry[2]["morphs"]} for entry in selected[:2])
    changed = {name for name in before if before[name] != adjusted[name]}
    require(len(changed) == 1 and changed <= fields, "Expected one effective TRI change for the measured target")
    allowed_poses = {(ledger[index]["args"]["script"], tuple(ledger[index]["args"]["args"]))
                     for row in rows for index in (row["topology"]["capture"], row["pose"]["capture"])}
    scoped_operations(ledger, capture["arm"], capture["seal"], set(indices), allowed_poses, next(iter(changed)))
    slots = PLAYER_BODY_CONTACT_NODES[node]
    require(all(tuple(slot for slot, (name, _) in entry[3].items() if name == node) == slots for entry in selected),
            "Expected all four native capsules of the scoped player node")
    banks = [cap_values([entry[3][slot][1] for slot in slots]) for entry in selected]
    armed, closed = snapshot["armedQpc"], snapshot["closedQpc"]
    require(snapshot["qpcFrequency"] == QPC, "Callback clock differs from the native ACK clock")
    windows, gaps = {}, {}
    origin = previous = epoch = None
    previous_capture = (0, 0, 0, armed)
    phase_interval = ledger[rows[0]["frames"][0]:rows[-1]["frames"][-1] + 1]
    require(not any(row.get("kind") == "driver" and row.get("action") != "status" for row in phase_interval),
            "Controller command changed between morph holds")
    for name, row, (token, _, ack, _) in zip(MORPH_REFIT_PHASES, rows, selected, strict=True):
        require(ack["female"] is (sex == "Female"), "Observed Body32 sex differs from the ACK")
        binding = [ACTOR, generation, token]
        require(all(typed(ledger, row[key], NATIVE, "SnapshotCurrent", "bool", binding) is True
                    for key in ("currentBefore", "currentAfter")), "Fitted token was not current across the hold")
        topology = row["topology"]
        nonce = topology["nonce"]
        _, raw = capture_pair(ledger, topology, TOPOLOGY, "CaptureDispatch", TOPOLOGY_SCHEMA, subject.pid, nonce)
        epoch = raw["epoch"] if epoch is None else epoch
        observed = route(raw, (subject.pid, epoch, subject.base, subject.cell, handle, int(ack["female"])), nonce, fixture, True)
        pose = linked_pose(ledger, row["pose"], raw, observed, ack, tail=arm == "tail", controller_node=node)
        clock = observed["captureClock"]
        acknowledged = (ack["acknowledgedUs"] + 1) * TICKS_PER_US - 1
        next_publish = next((entry[2]["publishedUs"] * TICKS_PER_US for entry in chain if entry[0] > token), closed)
        current_capture = (nonce, pose["nonce"], pose["phase"], clock["qpcBegin"])
        window, (earliest, finish), origin, previous, ranges = measured_phase(
            ledger, row["frames"], subject, node, banks, observed, pose, origin, previous)
        require(all(a < b for a, b in zip(previous_capture, current_capture, strict=True)) and
                max(acknowledged, armed) < clock["qpcBegin"] <= clock["qpcEnd"] < pose["qpcBegin"] < pose["qpcEnd"] <
                earliest <= finish < min(next_publish, closed), "Observation falls outside the same current ACK or callback window")
        previous_capture = (*current_capture[:3], finish)
        windows[name] = window
        gaps[name] = dict(zip(MORPH_REFIT_PHASES, ranges, strict=True))
    result = score_player(snapshot, idle, audience, windows, body32=fixture, runtime_handle=handle,
                          minimum_hold_ticks=MIN_HOLD, morph_refit=True)
    return {**result, "scope": "equipped-player-morph-refit", "actor": ACTOR_ID, "node": node, "tokens": tokens,
            "slots": list(slots), "signedGapRangesGu": gaps, "holdQpc": windows,
            "providerShapeInventoryVerified": False, "perSlotCallbackAttribution": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "ledger", "ack", "profile"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    try:
        manifest = decode(args.manifest.read_bytes())
        inputs = {name: getattr(args, name).read_bytes() for name in ("ledger", "ack", "profile")}
        require({name: sha256(raw).hexdigest() for name, raw in inputs.items()} == manifest["sha256"],
                "Input bytes differ from the pinned morph contact receipt")
        result = verify(manifest, [decode(row) for row in inputs["ledger"].splitlines()],
                        inputs["ack"].decode("utf-8-sig").splitlines(), decode(inputs["profile"]))
    except (KeyError, ValueError, IndexError, TypeError, OSError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
