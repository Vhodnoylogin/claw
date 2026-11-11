"""Pure, transport-free CBPC on/off/on scorer for owned born-beast fixtures.

StartPhysics/StopPhysics return None, not binding or previous-state evidence.
Only scene snapshot/transform primitives and the shared skeleton inventory are
reused from fsmp_probe; CBPC driver-local writes are expressly permitted.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import fsmp_probe as scene


PERIOD = .85
JITTER = .15
SAMPLES = 25
ACTIONS = {"start": "StartPhysics", "stop": "StopPhysics", "restart": "StartPhysics"}


def native_request(reference, node, function):
    return {"action": "call", "script": "CBPCPluginScript", "function": function,
            "args": [{"form": reference}, node], "timeoutMs": 8000}


def prepare(reference, sex):
    reference = scene.form(reference)
    return {"schemaVersion": 1, "reference": reference, "sex": sex,
            "query": {"kind": "world_observer", "refs": [reference], "actors": True,
                      "nodes": [{"ref": reference, "name": name, "firstPerson": False}
                                for name in scene.node_names(sex)]},
            "calls": {action: [native_request(reference, node, function) for node in scene.drivers(sex)]
                      for action, function in ACTIONS.items()},
            "anchors": scene.anchors(sex), "pointPeriodSeconds": PERIOD,
            "maximumPointJitterSeconds": JITTER,
            "offsets": [scene.anchor_offset(i) for i in range(SAMPLES)],
            "bindingState": "unknown", "runtimeQualified": False}


def completed(receipt, request):
    """Check the actual DevBench native-return shape; do not infer CBPC state."""
    scene.require(receipt.get("request") == request, "Wrong native request/node")
    result = receipt["nativeResult"]
    scene.require(type(result) is dict and result.get("called") is True and
                  result.get("returnedType") == "none" and "returned" in result and
                  result["returned"] is None and not result.get("error"),
                  "Uncertain/non-void native completion")


def score(document):
    scene.require(document.get("schemaVersion") == 1 and
                  document.get("declaredPointPeriodSeconds") == PERIOD,
                  "Missing predeclared CBPC cadence/schema")
    reference, sex = scene.form(document["reference"]), document["sex"]
    plan = prepare(reference, sex)
    baseline = previous = scene.snapshot(document["baseline"], reference, sex)
    scene.require(baseline["guard"]["actor"]["race"].lower() == "0x000cdd84",
                  "Born-beast werewolf fixture required")
    all_rows, windows = [baseline], {}

    def consume(raw):
        nonlocal previous
        row = scene.snapshot(raw, reference, sex)
        scene.require(row["guard"] == baseline["guard"], "Actor/root/source continuity lost")
        scene.require(row["sample"] > previous["sample"] and row["time"] > previous["time"],
                      "Replayed/nonadvancing observation")
        scene.require(scene.max_delta(row["position"], baseline["position"]) <= .025 and
                      scene.max_delta(row["root"]["translation"], baseline["root"]["translation"]) <= .025 and
                      scene.max_delta(row["angles"], baseline["angles"]) <= 1e-5 and
                      scene.max_delta(row["root"]["rotationRowMajor"], baseline["root"]["rotationRowMajor"]) <= 1e-5 and
                      abs(row["root"]["scale"] - baseline["root"]["scale"]) <= 1e-5,
                      "Fixture root moved/rotated/scaled")
        scene.require(all(abs(row["nodes"][name][space]["scale"] - baseline["nodes"][name][space]["scale"]) <= 1e-5
                          for name in scene.node_names(sex) for space in ("world", "local")), "Node scale changed")
        previous = row
        all_rows.append(row)
        return row

    def transition(action):
        receipts = document["receipts"][action]
        scene.require(type(receipts) is list and len(receipts) == len(plan["calls"][action]),
                      "Every selected node needs one native receipt")
        for receipt, request in zip(receipts, plan["calls"][action]):
            consume(receipt["before"])
            completed(receipt, request)
            after = consume(receipt["after"])
            if action != "start":
                scene.anchor_excitation(after, stimulus_baseline, sex, [0., 0., 0.])

    transition("start")
    stimulus_baseline = consume(document["stimulusBaseline"])
    for name, offset in (("moved", [.25, 0., 0.]), ("reset", [0., 0., 0.])):
        scene.anchor_excitation(consume(document["anchorCalibration"][name]), stimulus_baseline, sex, offset)
    for phase, action in zip(scene.PHASES, (None, "stop", "restart")):
        if action:
            transition(action)
        raw_rows = document["windows"][phase]
        scene.require(type(raw_rows) is list and len(raw_rows) == SAMPLES, "Exactly 25 real samples required")
        rows = windows[phase] = [consume(raw) for raw in raw_rows]
        for index, row in enumerate(rows):
            scene.anchor_excitation(row, stimulus_baseline, sex, plan["offsets"][index])
        gaps = [(b["time"] - a["time"])/1e9 for a, b in zip(rows, rows[1:])]
        scene.require(all(abs(gap - PERIOD) <= JITTER + 1e-9 for gap in gaps),
                      "Actual cadence differs from predeclared stimulus")

    controls_quiet = True
    for name in (*scene.CONTROL, *scene.INTERMEDIATES):
        for channel, floor in scene.FLOORS.items():
            origin = baseline["nodes"][name]["local"][channel]
            controls_quiet &= all(scene.max_delta(row["nodes"][name]["local"][channel], origin) <= floor
                                  for row in all_rows)
    for name in scene.CONTROL:
        origin = scene.relative(baseline["nodes"][name]["world"], baseline["root"])
        for channel, floor in scene.FLOORS.items():
            controls_quiet &= all(scene.max_delta(scene.relative(row["nodes"][name]["world"], row["root"])[channel],
                                                  origin[channel]) <= floor for row in all_rows)
    gaps = {phase: [(b["time"] - a["time"])/1e9 for a, b in zip(rows, rows[1:])]
            for phase, rows in windows.items()}
    comparable = all(max(group) - min(group) <= max(.05, .25*min(group))
                     for group in zip(*gaps.values()))
    result = {"status": "unconfirmed", "bindingState": "unknown", "nativeCompletionsVerified": True,
              "anchorExcitationQualified": True, "unaffectedControlsQuiet": controls_quiet,
              "excitationTimingComparable": comparable, "selectiveChannels": [], "channels": {},
              "physicsPhaseObserved": False, "solverQualified": False, "contactQualified": False,
              "cadence": {phase: {"samples": len(rows), "spanSeconds": (rows[-1]["time"]-rows[0]["time"])/1e9}
                          for phase, rows in windows.items()},
              "limits": ["Void native receipts do not prove binding or previous state.",
                         "Main-thread snapshots are not synchronized with physics or rendering.",
                         "Undisclosed direct driver writers, contacts and lifecycle are not qualified."]}
    for node, anchor in scene.anchors(sex).items():
        output = result["channels"][node] = {"anchor": anchor, "worldRelative": {}, "local": {}}
        for channel, floor in scene.FLOORS.items():
            stats = {phase: scene.spread([scene.relative(row["nodes"][node]["world"],
                                                       row["nodes"][anchor]["world"])[channel] for row in rows])
                     for phase, rows in windows.items()}
            output["worldRelative"][channel] = stats
            output["local"][channel] = {phase: scene.spread([row["nodes"][node]["local"][channel] for row in rows])
                                        for phase, rows in windows.items()}
            on = min(stats["active"], stats["restarted"])
            if on > 4*floor and stats["stopped"] <= max(floor, .25*on):
                result["selectiveChannels"].append({"node": node, "channel": channel})
    if result["selectiveChannels"] and controls_quiet and comparable:
        result["status"] = "sampled-selective-contrast-observed"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = score(json.loads(args.report.read_bytes()))
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
