"""Read-only verifier for the four-slot VR TailBone02 refit scenario.

The caller supplies the original Polygon steps.jsonl and a manifest of zero-based
indices into that ledger. The manifest names subject FormIDs, fitter tokens and
raw reads. Measurements, acknowledgements and times come from the raw rows.
test_tail_refit.py shows the manifest layout. The scenario owns fixture admission,
effective provider-config isolation, snapshot collection and cleanup.
"""
import argparse
from dataclasses import dataclass
import json
from math import dist
from pathlib import Path
import struct
import sys

from prepare_tail_refit_contrast import CHANNEL, PROFILE_SHA, SLOT_IDS, STATES, read_pinned
from posed_contact import native_vector, read_pose
from tail_refit_morph import MORPH_SCRIPT, TEST_KEY, check_registry, key_value

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / "src/test/python/physics")]
from cbpc_event_readback import Audience, matches_snapshot, positive_int, require
from cbpc_vr_geometry import _point_segment_distance, _same_pose, _sphere, measure_frame
from src.test.python.integration.fsmp_probe import numbers, transform


PROOF_SHA = "40e4bc0d6de967e0a0d0199d59721287b928d40a5d9842ee7b7d59c8e5838be5"
NODE = "TailBone02"
CONTACT_NODES = {
    "NPC EarL [EarL]Bone01", "NPC EarL [EarL]Bone02", "NPC EarR [EarR]Bone01", "NPC EarR [EarR]Bone02",
    "TailBone01", NODE, "TailBone03", "TailBone04", "TailBone05", "NPC Head [Head]", "Tails", "NPC Root [Root]",
    "NPC Spine2 [Spn2]", "NPC Pelvis [Pelv]", "NPC R Thigh [LThg]",
}
NATIVE, POSE, EVENTS, CBPC = "CLAWPhysicsNative", "CLAWVRNpcPose", "CLAWVRCBPCEvents", "CBPCPluginScript"
NANO = 1_000_000_000
QPC = 10_000_000
MARGIN = .75
DRIFT = .35
MIN_HOLD = 15_000_000
MAX_GAP_NS = 900_000_000
PHASES = ("unattached", "neutral", "morphed", "returned", "detached")


@dataclass(frozen=True)
class Subject:
    pid: int
    actor: int
    base: int
    cell: int
    generation: int

    @property
    def form(self):
        return {"form": f"0x{self.actor:08X}"}


def f32(values):
    return struct.pack("<" + "f" * len(values), *values)


def same_args(actual, expected):
    if isinstance(expected, list):
        return type(actual) is list and len(actual) == len(expected) and all(
            same_args(a, b) for a, b in zip(actual, expected, strict=True))
    if type(expected) is float:
        return type(actual) in (int, float) and float(actual) == expected
    return type(actual) is type(expected) and actual == expected


def typed(ledger, index, script, method, result_type, expected=None):
    require(type(index) is int and 0 <= index < len(ledger), "Ledger index is missing or out of bounds")
    row = ledger[index]
    args, result = row.get("args", {}), row.get("result", {})
    require(row.get("tool") == "papyrus" and args.get("action") == "call" and
            (args.get("script"), args.get("function")) == (script, method) and "self" not in args and
            (expected is None or same_args(args.get("args"), expected)) and
            result.get("called") is True and str(result.get("returnedType", "")).casefold() == result_type and
            "returned" in result and not (result.get("error") or result.get("isError")),
            f"Missing exact typed {script}.{method} receipt")
    return result["returned"]


def tracked_pose(ledger, index, subject, model, phase, sequence):
    args = ledger[index].get("args", {}).get("args", [])
    require(len(args) == 2 and positive_int(args[0]) and type(args[1]) is int and args[1] == sequence,
            "The native model lease did not read the next sequence")
    pose = json.loads(typed(ledger, index, POSE, "ReadNpc", "string", args))
    sample = pose["sample"]
    vector = native_vector(model, pose)
    sex, morphs, weight, nodes = read_pose(pose, vector, model)
    require(pose["pid"] == subject.pid and pose["qpcFrequency"] == QPC and pose["nonce"] == args[0] and
            pose["sequence"] == sequence and sample["actor"] == subject.actor and sample["base"] == subject.base and
            sample["cell"] == subject.cell and sample["race"] == 0xCDD84 and sample["bodyAddon"] == 0xCDD87 and
            sample["bodyItem"] == 0xCDD86 and positive_int(sample["threadID"]) and
            sex == "male" and weight == .5 and set(nodes) == CONTACT_NODES and
            all(value == (STATES[phase] if name == CHANNEL else 0.) for name, value in morphs.items()),
            "Native model lease, body binding, or effective SKEE phase differs")
    return sample, [morphs[name] for name in model["morphs"]]


def inspect_frame(ledger, index, subject, node=NODE):
    row = ledger[index]
    args, raw = row.get("args", {}), row["result"]
    require(row.get("tool") == "inspect" and args.get("kind") == "world_observer" and
            args.get("action") == "snapshot", "Expected a direct World Observer tool receipt")
    measured = measure_frame(raw, actor=subject.actor, base=subject.base, cell=subject.cell, pid=subject.pid,
                             target_offset=[0., 0., 0.], target_radius=1., target_node=node)
    require({item.get("name") for item in raw["nodes"]} == {node, "NPC Root [Root]"} and
            len(raw["nodes"]) == 2, "Expected the exact target node and its tracked actor root")
    roots = {item["name"]: item for item in raw["nodes"]}
    root = roots["NPC Root [Root]"]
    require(root["identity"] == measured["actor"][0] and root["form"] == subject.form["form"] and
            root["firstPerson"] is False and root["status"] == "available",
            "World Observer root does not belong to the measured third-person actor")
    measured["root"] = transform(root["world"])
    measured["targetPose"] = transform(roots[node]["world"])
    return measured


def bank_gap(frame, bank):
    gaps = []
    for capsule in bank:
        p1, radius = _sphere(frame["targetPose"], capsule[:3], capsule[6])
        p2, _ = _sphere(frame["targetPose"], capsule[3:6], capsule[6])
        gaps.append(_point_segment_distance(frame["source"], p1, p2) - radius - 3. * frame["left"]["scale"])
    return min(gaps)


def ordered(indices, message):
    require(all(type(index) is int and index >= 0 for index in indices)
            and indices == sorted(set(indices)), message)


def phase_bank(ledger, subject, model, proof, phase, number, previous_token, mutations):
    token = phase["token"]
    require(positive_int(token) and token < 0x01000000 and
            all(len(phase[name]) == len(SLOT_IDS) for name in ("capsules", "attach", "detach")),
            "Expected one native snapshot and all four TailBone02 slot receipts")
    args = [subject.form, subject.generation, token]
    before, values = tracked_pose(ledger, phase["poseBefore"], subject, model, number, 2 * number + 1)
    after, end_values = tracked_pose(ledger, phase["poseAfter"], subject, model, number, 2 * number + 2)
    event = json.loads(typed(ledger, phase["event"], POSE, "ReadPhysicsSnapshot", "string",
                             [before["rootToken"], previous_token]))
    tick = event["eventQpc"]
    require(event.get("schema") == "claw-vr-npc-pose/1" and event.get("status") == "ready"
            and event.get("pid") == subject.pid and event.get("qpcFrequency") == QPC
            and event.get("nonce") == before["rootToken"] and event.get("snapshotToken") == token
            and all(event.get(key) == before[key] for key in ("actor", "base", "runtimeHandle", "rootToken", "loadEpoch"))
            and positive_int(tick) and tick <= before["qpcBegin"],
            "Missing actor-bound native refit event")
    require(values == end_values and
            numbers(typed(ledger, phase["values"], NATIVE, "GetValues", "float[]", args), 31) == values and
            typed(ledger, phase["weight"], NATIVE, "GetWeight", "float", args) == .5,
            "Native snapshot inputs do not match the co-sampled effective SKEE vector")
    require(all(typed(ledger, phase[key], NATIVE, "SnapshotCurrent", "bool", args) is True
                for key in ("begin", "end")), "A native capsule snapshot did not remain current")
    bank = []
    for slot, read, append, detach, reference in zip(
            SLOT_IDS, phase["capsules"], phase["attach"], phase["detach"],
            proof["capsulesByPhase"][number], strict=True):
        capsule = numbers(typed(ledger, read, NATIVE, "GetCapsule", "float[]", [*args, slot]), 7)
        expected = [*reference["p1"], *reference["p2"], reference["radius"]]
        require(capsule[6] > 0 and f32(capsule) == f32(expected),
                "Native capsule differs from the pinned exact refit bank")
        index = 0x434C0000 + slot
        require(typed(ledger, append, CBPC, "AttachColliderCapsule", "bool",
                      [subject.form, NODE, capsule[:3], capsule[6], capsule[3:6], capsule[6], 0., index, True]) is True and
                typed(ledger, detach, CBPC, "DetachCollider", "bool", [subject.form, NODE, 1, index, True]) is True,
                "Expected acknowledged append and exact slot retirement")
        bank.append(capsule)
        mutations.update((append, detach))
    return bank, before, after, tick


def morph_writes(ledger, subject, phases, recorded):
    index = recorded["describe"]
    require(type(index) is int and 0 <= index < len(ledger), "Missing RaceMenu registry receipt")
    describe = ledger[index]
    require(describe.get("tool") == "papyrus" and describe.get("args") == {"action": "describe", "script": MORPH_SCRIPT},
            "Expected direct RaceMenu registry description")
    check_registry(describe["result"])
    initial, apply, restore = (recorded[key] for key in ("initial", "apply", "restore"))
    ordered([recorded["describe"], *initial, phases[0]["event"], *phases[0]["detach"], *apply,
             phases[1]["event"], *phases[1]["detach"], *restore, phases[2]["event"]],
            "Tail morph calls must occur between the correct refit phases")
    args = [subject.form, CHANNEL, TEST_KEY]
    for value, checks in ((0., initial), (1., apply[2:]), (0., restore[2:])):
        present, read = checks
        require(typed(ledger, present, MORPH_SCRIPT, "HasBodyMorph", "bool", args) is (value != 0.)
                and key_value(typed(ledger, read, MORPH_SCRIPT, "GetBodyMorph", "float", args)) == value,
                "Stored tail morph was not isolated or cleared")
    for calls, method, mutation_args in ((apply, "SetBodyMorph", [*args, 1.]), (restore, "ClearBodyMorph", args)):
        require(typed(ledger, calls[0], MORPH_SCRIPT, method, "none", mutation_args) is None
                and typed(ledger, calls[1], MORPH_SCRIPT, "UpdateModelWeight", "none", [subject.form]) is None,
                "Missing acknowledged RaceMenu change and model update")
    writes = {i for i, row in enumerate(ledger) if row.get("tool") == "papyrus"
              and row.get("args", {}).get("script") == MORPH_SCRIPT and row["args"].get("action") == "call"
              and row["args"].get("function") in ("SetBodyMorph", "ClearBodyMorph", "UpdateModelWeight")}
    require(writes == {*apply[:2], *restore[:2]}, "Unexpected RaceMenu writes in the refit scenario")


def callback_snapshot(ledger, subject, capture, node=NODE):
    event = json.loads(typed(ledger, capture["read"], EVENTS, "Read", "string"))
    nonce, generation = (event[key] for key in ("nonce", "generation"))
    audience = Audience(subject.pid, nonce, generation, subject.actor, subject.base, subject.cell, "Male", node)
    matches_snapshot(event, audience)
    idle = json.loads(typed(ledger, capture["idle"], EVENTS, "GetCaptureState", "string", []))
    require(idle == {"pid": subject.pid, "schema": "claw-vr-cbpc-events/1", "generation": generation,
                    "status": "idle", "sinkRegistered": True, "loading": False},
            "Exact idle callback capture is missing")
    require(typed(ledger, capture["arm"], EVENTS, "Arm", "bool",
                  [nonce, generation, subject.actor - 0x100000000, subject.cell]) is True and
            typed(ledger, capture["seal"], EVENTS, "Seal", "bool", [nonce, generation]) is True,
            "Arm or seal acknowledgement is missing")
    typed(ledger, capture["read"], EVENTS, "Read", "string", [nonce, generation])
    return event, audience


def callback_counts(ledger, subject, capture, holds):
    event, _ = callback_snapshot(ledger, subject, capture)
    start, armed, closed = (event[key] for key in ("requestedQpc", "armedQpc", "closedQpc"))
    require(event["qpcFrequency"] == QPC and all(positive_int(value) for value in (start, armed, closed)) and
            start <= armed < closed < start + 60 * QPC and
            armed <= holds[PHASES[0]][0] < holds[PHASES[-1]][1] < closed,
            "Expected one bounded sealed QPC interval for all fixed-controller phases")
    events = event["events"]
    require(type(events) is list and len(events) <= 128 and type(event["lastSequence"]) is int and
            event["lastSequence"] == len(events), "Incomplete callback sequence")
    counts = dict.fromkeys(PHASES, 0)
    previous, outside = armed, 0
    for sequence, row in enumerate(events, 1):
        qpc, duration = row["qpc"], row["numArg"]
        require(type(row["sequence"]) is int and row["sequence"] == sequence and
                positive_int(qpc) and previous <= qpc <= closed and
                row["eventName"] == "CBPCPlayerCollisionWithMaleEvent" and row["strArg"] == NODE and
                type(row["senderFormId"]) is int and row["senderFormId"] == subject.actor and
                numbers([duration], 1)[0] >= struct.unpack("<f", f32([.3]))[0],
                "Callback lacks exact actor, bone, time or duration provenance")
        previous = qpc
        owner = next((name for name, (begin, end) in holds.items() if begin <= qpc <= end), None)
        if owner is None:
            outside += 1
        else:
            counts[owner] += 1
    require(counts["morphed"] > 0 and all(counts[name] == 0 for name in PHASES if name != "morphed"),
            "Same-node callbacks do not distinguish the adaptive bank from neutral and detached holds")
    return counts, outside


def verify(manifest, ledger, model, proof):
    require(type(manifest) is dict and manifest.get("schema") == "claw-vr-tail02-refit-reads/2",
            "Expected a tail refit index manifest for the original raw ledger")
    subject = Subject(**manifest["subject"])
    require(all(positive_int(value) for value in vars(subject).values()) and
            0xFF000000 <= subject.actor < 0xFFFFFFFF and 0 < subject.base < 0xFF000000 and
            subject.cell == 0x0A01A5C6, "Require one owned RealmLorkhan test actor and native generation")
    require(len(model["morphs"]) == len(set(model["morphs"])) == 31 and CHANNEL in model["morphs"] and
            model["modelIdentity"] == proof["model"] and
            tuple(i for i, slot in enumerate(model["slots"]) if slot["node"] == NODE and slot["male"] is not None)
            == SLOT_IDS and tuple(proof["slots"]) == SLOT_IDS and tuple(proof["values"]) == STATES,
            "Expected the full original VR model and same-node bank")
    phases, capture = manifest["phases"], manifest["capture"]
    require(len(phases) == 3 and all(len(phase["hold"]) >= 2 for phase in phases),
            "Require three distinct morph stages with actual World Observer holds")
    indices = [manifest["modelRead"], capture["idle"], capture["arm"], *manifest["unattached"]]
    tokens = []
    for phase in phases:
        tokens.append(phase["token"])
        indices += [phase["event"], phase["begin"], phase["values"], phase["weight"], *phase["capsules"], *phase["attach"],
                    phase["poseBefore"], *phase["hold"], phase["poseAfter"], phase["end"], *phase["detach"]]
    indices += [*manifest["detached"], capture["seal"], capture["read"]]
    ordered(indices, "Typed sample, bank mutation or capture indices are replayed or out of phase")
    ordered(tokens, "Neutral, changed and returned shapes need three advancing native snapshot tokens")
    require(indices[-1] < len(ledger) and
            typed(ledger, manifest["modelRead"], NATIVE, "GetModelIdentity", "string", []) == model["modelIdentity"],
            "The observed Distribution DLL did not identify the pinned VR fitter")

    mutations = set()
    states = [phase_bank(ledger, subject, model, proof, phase, number, previous, mutations)
              for number, (phase, previous) in enumerate(zip(phases, (0, *tokens[:-1]), strict=True))]
    morph_writes(ledger, subject, phases, manifest["morph"])
    provider_calls = {i for i, row in enumerate(ledger) if row.get("tool") == "papyrus" and
                      row.get("args", {}).get("script") == CBPC and row["args"].get("action") == "call"
                      and row["args"].get("function") != "GetVersion"}
    require(provider_calls == mutations, "Unexpected provider operations outside the four indexed slots")
    require(not any(row.get("kind") == "driver" and row.get("action") in ("publish", "release")
                    for row in ledger[capture["arm"]:capture["seal"]]),
            "Controller was driven again during the fixed-controller contrast")
    banks = [row[0] for row in states]
    require(banks[0] == banks[2] and banks[0] != banks[1], "Neutral bank did not return after a real native refit")
    samples = [sample for _, before, after, _ in states for sample in (before, after)]
    first = samples[0]
    scene_root = transform(first["rootWorld"])
    body_root = transform(first["bodyCloneWorld"])
    require(all(sample["rootToken"] == first["rootToken"] and sample["loadEpoch"] == first["loadEpoch"] and
                sample["runtimeHandle"] == first["runtimeHandle"] and
                _same_pose(transform(sample["rootWorld"]), scene_root, DRIFT) and
                _same_pose(transform(sample["bodyCloneWorld"]), body_root, DRIFT)
                for sample in samples)
            and all(a["qpcEnd"] < b["qpcBegin"] for a, b in zip(samples, samples[1:])),
            "Different or replayed actor root and loaded body clone in the native lease")
    require(all(old["qpcEnd"] < current[3] for old, current in zip(samples[1:-1:2], states[1:], strict=True)),
            "A refit event predates the preceding completed pose hold")

    groups = [manifest["unattached"], *(phase["hold"] for phase in phases), manifest["detached"]]
    require(all(2 <= len(group) <= 8 for group in groups), "Expected bounded observed frame holds")
    origin = previous = None
    windows, ranges = {}, {}
    previous_end = 0
    for number, (name, group) in enumerate(zip(PHASES, groups, strict=True)):
        frames = [inspect_frame(ledger, index, subject) for index in group]
        start = (frames[0]["ns"] * QPC + NANO - 1) // NANO
        end = frames[-1]["ns"] * QPC // NANO
        require(previous_end < start and end - start >= MIN_HOLD, "Observed hold is too short or overlaps another hold")
        if 1 <= number <= 3:
            _, before, after, _ = states[number - 1]
            require(before["qpcEnd"] < start < end < after["qpcBegin"],
                    "Native SKEE lease samples do not bracket the observed hold")
        gaps = [[], []]
        for frame in frames:
            origin = frame if origin is None else origin
            require(frame["session"] == origin["session"] and frame["epoch"] == origin["epoch"] and
                    frame["actor"][0]["runtimeHandle"] == first["runtimeHandle"] and
                    (previous is None or all(previous[key] < frame[key] for key in ("sample", "frame", "ns"))) and
                    all(frame[key][0] == origin[key][0] and dist(frame[key][1], origin[key][1]) <= DRIFT and
                        _same_pose(frame[key][2], origin[key][2], DRIFT) for key in ("player", "actor")) and
                    _same_pose(frame["actor"][2], scene_root, DRIFT) and
                    _same_pose(frame["root"], origin["root"], DRIFT) and
                    all(_same_pose(value, origin["controls"][key], DRIFT) for key, value in frame["controls"].items()) and
                    _same_pose(frame["left"], origin["left"], DRIFT) and dist(frame["source"], origin["source"]) <= DRIFT,
                    "Controller or owned actor/root moved, or the world frame is stale or foreign")
            previous = frame
            for bank, bucket in zip(banks[:2], gaps, strict=True):
                bucket.append(bank_gap(frame, bank))
        require(all(later["ns"] - earlier["ns"] <= MAX_GAP_NS for earlier, later in zip(frames, frames[1:])) and
                min(gaps[0]) >= MARGIN and max(gaps[1]) <= -MARGIN,
                "Observed hand pose does not discriminate both capsule banks at the same measured tail pose")
        windows[name] = (start, end)
        previous_end = end
        ranges[name] = {"neutralGapGu": [min(gaps[0]), max(gaps[0])],
                        "morphedGapGu": [min(gaps[1]), max(gaps[1])]}
    counts, outside = callback_counts(ledger, subject, capture, windows)
    return {"status": "qualified-scoped-tail02-refit-evidence", "model": model["modelIdentity"],
            "slots": list(SLOT_IDS), "snapshotTokens": tokens, "holdQpc": windows, "worldGapRanges": ranges,
            "sameNodeCallbacks": counts, "callbacksOutsideHolds": outside,
            "perSlotCallbackAttribution": False, "providerShapeInventoryVerified": False,
            "havokContactQualified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "steps", "profile", "basis"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    try:
        result = verify(json.loads(args.manifest.read_bytes()),
                        [json.loads(line) for line in args.steps.read_bytes().splitlines()],
                        json.loads(read_pinned(args.profile, PROFILE_SHA)),
                        json.loads(read_pinned(args.basis, PROOF_SHA)))
    except (OSError, ValueError, TypeError, KeyError, IndexError, OverflowError, struct.error) as error:
        print(json.dumps({"status": "unqualified-tail02-refit-evidence", "reason": str(error)}))
        return 2
    print(json.dumps(result, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
