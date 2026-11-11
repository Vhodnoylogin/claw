"""Prepare and score an owned FSMP motion probe; no transport or game side effects.

The caller owns admission, journalling each native intent before dispatch, exact
actor/root guards, and cleanup. A generated packet list is not launch permission.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
import statistics


MALE = ("NPC EarL [EarL]Bone01", "NPC EarL [EarL]Bone02",
        "NPC EarR [EarR]Bone01", "NPC EarR [EarR]Bone02",
        "TailBone01", "TailBone02", "TailBone03", "TailBone04", "TailBone05")
FEMALE = MALE + ("NPC L Breast P1", "NPC R Breast P1")
PHASES = ("active", "stopped", "restarted")
CONTROL = ("NPC Root [Root]", "NPC Pelvis [Pelv]", "NPC Spine2 [Spn2]")
INTERMEDIATES = ("CME TailBone01", "CME TailBone02", "CME TailBone03", "CME TailBone04")
FLOORS = {"translation": 1e-4, "rotationRowMajor": 1e-5}
OBSERVATION = {"mode": "single_main_thread_task", "physics": "not_sampled", "render": "not_synchronized"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def drivers(sex):
    require(sex in ("male", "female"), "Explicit fixture sex required")
    return MALE if sex == "male" else FEMALE


def anchors(sex):
    """Actual mass-zero anchors in fsmp_motion.render_xml, not guessed parents."""
    return {name: ("NPC Head [Head]" if i < 4 else "Tails" if i < 9
                   else "NPC L PreBreast P1" if i == 9 else "NPC R PreBreast P1")
            for i, name in enumerate(drivers(sex))}


def node_names(sex):
    return tuple(dict.fromkeys((*drivers(sex), *anchors(sex).values(), *CONTROL, *INTERMEDIATES)))


def numbers(values, length):
    require(type(values) is list and len(values) == length and
            all(type(v) in (int, float) and math.isfinite(v) for v in values), "Invalid finite vector")
    return [float(v) for v in values]


def form(value):
    require(isinstance(value, str) and value.lower().startswith("0x"), "Explicit hex actor form required")
    number = int(value, 16)
    require(0 < number <= 0xffffffff and number != 0x14, "Use an owned NPC, never the player")
    return f"0x{number:08X}"


def transform(value):
    translation = numbers(value["translation"], 3)
    rotation = numbers(value["rotationRowMajor"], 9)
    scale = value["scale"]
    require(type(scale) in (int, float) and math.isfinite(scale) and scale > 0, "Invalid scale")
    rows = [rotation[i:i + 3] for i in (0, 3, 6)]
    require(all(abs(sum(x*x for x in row) - 1) <= .001 for row in rows) and
            all(abs(sum(x*y for x, y in zip(rows[i], rows[j]))) <= .001
                for i, j in ((0, 1), (0, 2), (1, 2))), "Invalid rotation basis")
    a, b, c = rows
    determinant = (a[0]*(b[1]*c[2] - b[2]*c[1]) - a[1]*(b[0]*c[2] - b[2]*c[0])
                   + a[2]*(b[0]*c[1] - b[1]*c[0]))
    require(abs(determinant - 1) <= .001, "Reflected rotation basis")
    return {"translation": translation, "rotationRowMajor": rotation, "scale": float(scale)}


def relative(child, parent):
    """Inverse parent NiTransform * child, including parent rotation and scale."""
    c, p = transform(child), transform(parent)
    cr, pr = c["rotationRowMajor"], p["rotationRowMajor"]
    delta = [x - y for x, y in zip(c["translation"], p["translation"])]
    return {"translation": [sum(pr[j*3 + i]*delta[j] for j in range(3))/p["scale"] for i in range(3)],
            "rotationRowMajor": [sum(pr[k*3 + i]*cr[k*3 + j] for k in range(3))
                                 for i in range(3) for j in range(3)],
            "scale": c["scale"]/p["scale"]}


def bool_vector(values, length):
    require(type(values) is list and len(values) == length and all(type(x) is bool for x in values),
            "TogglePhysics must return the exact bool[]; missing/partial/int results are unknown")
    return values[:]


def binding_gate(sex, receipts):
    """Validate real previous-state receipts, independently of transform motion.

    A first-off false bit is ambiguous (unbound OR originally kinematic), so stop
    before excitation. Caller restores only originally true positions. An absent
    native return never authorizes a replay or guessed all-on cleanup.
    """
    count = len(drivers(sex))
    for action, expected in (("first-off", True), ("reenable", False),
                             ("second-off", True), ("restore", False)):
        bits = bool_vector(receipts[action]["previous"], count)
        require(bits == [expected]*count, "Dynamic-body binding/state gate failed: " + action)
    return {"dynamicBodyGate": True, "restoredPreviousState": True,
            "solverQualified": False, "contactQualified": False}


def prepare(reference, sex, origin):
    reference, origin = form(reference), numbers(origin, 3)
    names = node_names(sex)
    query = {"kind": "world_observer", "refs": [reference], "actors": True,
             "nodes": [{"ref": reference, "name": name, "firstPerson": False} for name in names]}
    # Same small, closed trajectory in all three windows. Explicit float JSON
    # arguments are necessary: DevBench does not coerce int Papyrus parameters.
    positions = [[origin[0] + .5*math.sin(2*math.pi*i/12), origin[1], origin[2]] for i in range(25)]
    positions[-1] = origin[:]
    windows = {}
    for phase in PHASES:
        windows[phase] = [{"expectedPosition": position, "steps": [
            {"tool": "papyrus", "args": {"action": "call", "script": "ObjectReference", "function": "SetPosition",
                                          "self": {"form": reference}, "args": position[:], "timeoutMs": 8000}},
            {"wait": 200}, {"tool": "inspect", "args": copy.deepcopy(query)}]} for position in positions]
    toggles = {action: {"tool": "papyrus", "args": {"action": "call", "script": "DynamicHDT",
        "function": "TogglePhysics", "args": [{"form": reference}, list(drivers(sex)), on], "timeoutMs": 8000}}
        for action, on in (("first-off", False), ("reenable", True), ("second-off", False), ("restore", True))}
    return {"schemaVersion": 1, "reference": reference, "sex": sex, "origin": origin,
            "baselineQuery": {"tool": "inspect", "args": query}, "togglePackets": toggles, "windows": windows,
            "order": ["baseline", "first-off", "STOP unless exact all-true previous-state return", "reenable",
                      "settle", "active", "second-off", "settle", "stopped", "restore", "settle", "restarted"],
            "settleMilliseconds": 2000, "runtimeQualified": False,
            "requirements": ["Fresh owned actor/incarnation/root before and after every mutation.",
                "Verify actual provider DLL, all four mesh hooks/XML/skeleton winners and no competing CBPC first.",
                "Describe actual DynamicHDT.TogglePhysics and ObjectReference.SetPosition signatures before first mutation.",
                "Journal native intent before one dispatch; unknown completion forbids replay/guessed restoration.",
                "After any completed first-off failure, restore only originally true indices on the same owned root.",
                "Read back every SetPosition via observer; a void Papyrus call is not positional evidence.",
                "Keep morphs, animation ownership and every other node writer unchanged throughout all windows.",
                "Retain full raw local/world snapshots, receipts, monotonic times, source/provider pins and command results.",
                "Each window starts/ends at the captured origin; restore position on failure under the same owner guard.",
                "Missing/nonadvancing samples or local animation activity mean unconfirmed, never solver proof."]}


def snapshot(raw, reference, sex):
    """Read actual SE observer rows without inventing producer frames or phases."""
    require(raw.get("ok") is True and raw.get("quality") == "complete" and raw.get("schemaVersion") == 1,
            "Incomplete observer snapshot")
    require(raw.get("phase") == "skse_main_thread_task" and raw.get("units") == "skyrim_engine_units"
            and raw.get("space") == "world" and raw.get("coherence") == OBSERVATION, "Wrong observation contract")
    require(type(raw.get("sessionId")) is str and raw["sessionId"] and
            all(type(raw.get(k)) is int and raw[k] > 0 for k in ("loadGeneration", "sampleId", "producerMonotonicNs")),
            "Missing session/time/epoch")
    require(type(raw.get("refs")) is list and len(raw["refs"]) == 1, "Exact one-actor snapshot required")
    ref = raw["refs"][0]
    require(ref.get("status") == "available" and ref.get("loaded3D") is True and
            ref.get("deleted") is False and ref.get("disabled") is False, "Actor not available")
    identity, root, actor = ref["identity"], ref["rootIdentity"], ref["actor"]
    require(form(identity["form"]) == reference and identity["loadGeneration"] == raw["loadGeneration"] and
            type(identity["runtimeHandle"]) is int and identity["runtimeHandle"] > 0, "Wrong actor incarnation")
    require(root.get("firstPerson") is False and root.get("identityBasis") ==
            "sampled_pointer_and_handle_changes_no_object_retention" and
            type(root.get("sampledRootToken")) is int and root["sampledRootToken"] > 0, "Missing sampled root")
    require(actor.get("status") == "available" and actor.get("raceStatus") == "available" and
            type(actor.get("sex")) is int and actor["sex"] == (sex == "female"), "Wrong/unavailable actor metadata")
    weight = actor["weight"]
    require(weight.get("status") == "available" and type(weight["rawNPCWeight"]) in (int, float) and
            0 <= weight["rawNPCWeight"] <= 100, "Unavailable weight")
    require(ref["baseForm"] == actor["baseForm"], "Actor base disagreement")
    require(type(ref["scale"]) in (int, float) and math.isfinite(ref["scale"]) and ref["scale"] > 0,
            "Invalid actor scale")
    rows = raw["nodes"]
    require(type(rows) is list and len(rows) == len(node_names(sex)), "Missing/extra node rows")
    nodes = {}
    for row in rows:
        name = row["name"]
        require(name in node_names(sex) and name not in nodes and row.get("status") == "available"
                and row.get("firstPerson") is False and form(row["form"]) == reference and
                row["identity"] == identity and row["rootIdentity"] == root, "Wrong/missing node/root identity")
        nodes[name] = {key: transform(row[key]) for key in ("world", "local")}
    return {"guard": {"session": raw["sessionId"], "generation": raw["loadGeneration"],
                      "observerVersion": raw["observerVersion"], "identity": identity, "root": root,
                      "actor": actor, "scale": ref["scale"]},
            "sample": raw["sampleId"], "time": raw["producerMonotonicNs"],
            "position": numbers(ref["position"], 3), "angles": numbers(ref["anglesRadians"], 3),
            "root": transform(ref["sceneTransform"]), "nodes": nodes}


def spread(vectors):
    return max(math.sqrt(statistics.pvariance(column)) for column in zip(*vectors))


def max_delta(a, b):
    return max(abs(x - y) for x, y in zip(a, b))


def reference_excitation(observed, baseline, expected):
    require(max_delta(observed["position"], expected) <= .025, "Excitation readback mismatch")
    reference_delta = [x-y for x, y in zip(observed["position"], baseline["position"])]
    root_delta = [x-y for x, y in zip(observed["root"]["translation"], baseline["root"]["translation"])]
    require(max_delta(reference_delta, root_delta) <= .025, "Reference moved without matching model root")


def anchor_offset(index):
    return [float(.5*math.sin(2*math.pi*index/12)) if index != 24 else 0., 0., 0.]


def anchor_excitation(observed, baseline, sex, offset):
    """Read actual keyed-anchor displacement; stored SKEE values alone do not qualify."""
    require(max_delta(observed["position"], baseline["position"]) <= .025 and
            max_delta(observed["root"]["translation"], baseline["root"]["translation"]) <= .025,
            "Actor/root moved during direct anchor stimulus")
    for name in dict.fromkeys(anchors(sex).values()):
        delta = relative(observed["nodes"][name]["world"], baseline["nodes"][name]["world"])
        require(max_delta(delta["translation"], offset) <= .003,
                "Mass-zero anchor world displacement missing/wrong: " + name)
        require(max_delta(delta["rotationRowMajor"], [1.,0.,0.,0.,1.,0.,0.,0.,1.]) <= 1e-5 and
                abs(delta["scale"] - 1.) <= 1e-5, "Anchor rotated/scaled during keyed position stimulus")


def score(document):
    reference, sex = form(document["reference"]), document["sex"]
    gate = binding_gate(sex, document["receipts"])
    baseline = snapshot(document["baseline"], reference, sex)
    plan = prepare(reference, sex, baseline["position"])
    windows, previous = {}, baseline
    stimulus = document.get("stimulus", "reference")
    require(stimulus in ("reference", "xml-anchors"), "Unknown excitation contract")
    receipt_rows = []

    def consume(raw):
        nonlocal previous
        observed = snapshot(raw, reference, sex)
        require(observed["guard"] == baseline["guard"], "Actor/root/source continuity lost")
        require(observed["sample"] > previous["sample"] and observed["time"] > previous["time"],
                "Replayed/nonadvancing observation")
        previous = observed
        return observed

    def transition(action):
        for side in ("before", "after"):
            row = consume(document["receipts"][action][side])
            require(max_delta(row["position"], baseline["position"]) <= .025, "Binding transition displaced fixture")
            receipt_rows.append(row)

    transition("first-off")
    transition("reenable")
    stimulus_baseline = consume(document["stimulusBaseline"]) if stimulus == "xml-anchors" else baseline
    calibration_rows = []
    if stimulus == "xml-anchors":
        for name, offset in (("moved", [.25, 0., 0.]), ("reset", [0., 0., 0.])):
            value = consume(document["anchorCalibration"][name])
            anchor_excitation(value, stimulus_baseline, sex, offset)
            calibration_rows.append(value)
    for phase in PHASES:
        if phase == "stopped":
            transition("second-off")
        elif phase == "restarted":
            transition("restore")
        rows = document["windows"][phase]
        require(type(rows) is list and len(rows) == 25, "Exactly 25 real samples per excitation window required")
        windows[phase] = []
        for index, (raw, command) in enumerate(zip(rows, plan["windows"][phase])):
            observed = consume(raw)
            if stimulus == "xml-anchors":
                anchor_excitation(observed, stimulus_baseline, sex, anchor_offset(index))
            else:
                reference_excitation(observed, baseline, command["expectedPosition"])
            require(max_delta(observed["angles"], baseline["angles"]) <= 1e-5 and
                    max_delta(observed["root"]["rotationRowMajor"], baseline["root"]["rotationRowMajor"]) <= 1e-5 and
                    abs(observed["root"]["scale"] - baseline["root"]["scale"]) <= 1e-5, "Root rotated/scaled")
            require(all(abs(observed["nodes"][name][space]["scale"] - stimulus_baseline["nodes"][name][space]["scale"]) <= 1e-5
                        for name in node_names(sex) for space in ("world", "local")), "Node/anchor scale changed")
            windows[phase].append(observed)
        gaps = [(b["time"] - a["time"])/1e9 for a, b in zip(windows[phase], windows[phase][1:])]
        require(min(gaps) >= .1 and max(gaps) <= 1 and sum(gaps) >= 4, "Insufficient real observation cadence/span")
    result = {**gate, "status": "unconfirmed", "physicsPhaseObserved": False, "channels": {},
              "stimulus": stimulus, "anchorExcitationQualified": stimulus == "xml-anchors",
              "selectiveChannels": [], "localAnimationQuiet": True, "controlParentsQuiet": True,
              "anchorsRootRelativeQuiet": True if stimulus == "reference" else None,
              "excitationTimingComparable": True,
              "cadence": {phase: {"samples": len(rows), "spanSeconds": (rows[-1]["time"]-rows[0]["time"])/1e9}
                          for phase, rows in windows.items()},
              "limits": ["Scene samples are not synchronized with the physics/render phase.",
                         "Binding receipts and selective on/off/on response are separate evidence.",
                         "No contact, appearance, animation lifecycle or solver-source/binary equivalence claim."]}
    phase_gaps = {phase: [(b["time"] - a["time"])/1e9 for a, b in zip(rows, rows[1:])]
                  for phase, rows in windows.items()}
    for gaps in zip(*phase_gaps.values()):
        result["excitationTimingComparable"] &= max(gaps) - min(gaps) <= max(.05, .25*min(gaps))
    all_rows = [baseline, stimulus_baseline, *calibration_rows, *receipt_rows] + [row for phase in PHASES for row in windows[phase]]
    # Animation controls cannot be replaced by stationary actor coordinates.
    for name in node_names(sex):
        if stimulus == "xml-anchors" and name in anchors(sex).values():
            continue  # These two mass-zero anchor positions are the declared input.
        for key, floor in FLOORS.items():
            values = [row["nodes"][name]["local"][key] for row in all_rows]
            result["localAnimationQuiet"] &= all(max_delta(value, values[0]) <= floor for value in values)
    static_controls = CONTROL if stimulus == "xml-anchors" else (*anchors(sex).values(), *CONTROL)
    for name in dict.fromkeys(static_controls):
        values = [relative(row["nodes"][name]["world"], row["root"]) for row in all_rows]
        for key, floor in FLOORS.items():
            result["controlParentsQuiet"] &= all(max_delta(value[key], values[0][key]) <= floor for value in values)
    if stimulus == "reference":
        result["anchorsRootRelativeQuiet"] = result["controlParentsQuiet"]
    for name, anchor in anchors(sex).items():
        result["channels"][name] = {"anchor": anchor, "worldRelative": {}, "local": {}}
        for key, floor in FLOORS.items():
            stats = {phase: spread([relative(row["nodes"][name]["world"], row["nodes"][anchor]["world"])[key]
                                    for row in rows]) for phase, rows in windows.items()}
            result["channels"][name]["worldRelative"][key] = stats
            result["channels"][name]["local"][key] = {
                phase: spread([row["nodes"][name]["local"][key] for row in rows]) for phase, rows in windows.items()}
            active = min(stats["active"], stats["restarted"])
            if active > 4*floor and stats["stopped"] <= max(floor, .25*active):
                result["selectiveChannels"].append({"node": name, "channel": key})
    if (result["selectiveChannels"] and result["localAnimationQuiet"] and result["controlParentsQuiet"]
            and result["excitationTimingComparable"]):
        result["status"] = "sampled-selective-contrast-observed"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    command = parser.add_subparsers(dest="command", required=True)
    plan = command.add_parser("prepare")
    plan.add_argument("--reference", required=True)
    plan.add_argument("--sex", choices=("male", "female"), required=True)
    plan.add_argument("--origin", nargs=3, type=float, required=True)
    check = command.add_parser("score")
    check.add_argument("report", type=Path)
    for sub in (plan, check):
        sub.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = (prepare(args.reference, args.sex, args.origin) if args.command == "prepare"
              else score(json.loads(args.report.read_bytes())))
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(args.output)


if __name__ == "__main__":
    main()
