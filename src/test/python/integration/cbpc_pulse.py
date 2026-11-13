"""Pure CBPC pulse evidence scorer; no provider, process or scene side effects.

CBPC writes each driver's own local transform. A child that only inherits a
bound parent's world movement must not count as a bound/responding driver.
"""
from __future__ import annotations

import statistics

import cbpc_probe as cbpc
import fsmp_probe as scene
import fsmp_pulse as pulse


XP32_SHA256 = "b64b614d06eb854512ef4a9d6b08777fe0f9580f47d495d20db16dabb9fc2dd0"


def parent_paths(sex):
    """Immediate-parent-first paths read through public PyNifly from b64b614d XP32."""
    paths = {scene.MALE[0]: ["NPC Head [Head]"], scene.MALE[1]: [scene.MALE[0], "NPC Head [Head]"],
             scene.MALE[2]: ["NPC Head [Head]"], scene.MALE[3]: [scene.MALE[2], "NPC Head [Head]"]}
    tail = ["Tails"]
    for index, name in enumerate(scene.MALE[4:]):
        paths[name] = tail[:]
        tail = [f"CME TailBone{index + 1:02}", name, *tail]
    if sex == "female":
        paths.update({scene.FEMALE[-2]: ["NPC L PreBreast P1"], scene.FEMALE[-1]: ["NPC R PreBreast P1"]})
    scene.drivers(sex)
    return paths


def protocol():
    return {**pulse.protocol(), "id": "claw-cbpc-anchor-pulse/1", "dynamicLocalWrites": True,
            "requireOwnLocalAndImmediateParentRelativeResponse": True}


def prepare(reference, sex):
    plan = cbpc.prepare(reference, sex)
    return {"schemaVersion": 1, "reference": plan["reference"], "sex": sex, "protocol": protocol(),
            "stimulus": "anchor-pulse", "query": plan["query"], "calls": plan["calls"],
            "skeletonSha256": XP32_SHA256, "parentPaths": parent_paths(sex),
            "families": {anchor: list(nodes) for anchor, nodes in pulse.families(sex).items()},
            "bindingState": "unknown", "runtimeQualified": False}


def score(document):
    spec = protocol()
    scene.require(document.get("schemaVersion") == 1 and document.get("protocol") == spec and
                  document.get("stimulus") == "anchor-pulse", "Missing/changed CBPC pulse protocol")
    reference, sex = scene.form(document["reference"]), document["sex"]
    plan, paths = prepare(reference, sex), parent_paths(sex)
    scene.require(document.get("skeletonSha256") == XP32_SHA256 and document.get("parentPaths") == paths,
                  "Pinned XP32 immediate-parent paths unavailable/changed")
    groups = pulse.families(sex)
    originals = document["anchorOriginals"]
    keys = [originals[anchor]["key"] for anchor in groups]
    scene.require(all(type(key) is str and key.startswith("CLAW.FSMPProbe.") and len(key) > len("CLAW.FSMPProbe.")
                      for key in keys) and len(set(keys)) == 1 and
                  all(originals[anchor].get("keysBefore") == [] for anchor in groups),
                  "Fresh anchors and one explicit run-owned pulse key required")
    baseline = previous = scene.snapshot(document["baseline"], reference, sex)
    actor = baseline["guard"]["actor"]
    scene.require(all(isinstance(actor.get(key), str) and actor[key].lower() == "0x000cdd84"
                      for key in ("race", "baseRace")), "Born-beast fixture required")

    def consume(raw):
        nonlocal previous
        value = scene.snapshot(raw, reference, sex)
        scene.require(value["guard"] == baseline["guard"], "CBPC actor/root/source continuity lost")
        scene.require(value["sample"] > previous["sample"] and value["time"] > previous["time"],
                      "Replayed/nonadvancing CBPC pulse observation")
        scene.require(scene.max_delta(value["position"], baseline["position"]) <= .025 and
                      scene.max_delta(value["angles"], baseline["angles"]) <= 1e-5, "CBPC fixture moved/rotated")
        pulse._same_transform(value["root"], baseline["root"], "CBPC root moved/rotated/scaled")
        for name in scene.node_names(sex):
            for space in ("local", "world"):
                scene.require(abs(value["nodes"][name][space]["scale"] - baseline["nodes"][name][space]["scale"]) <= 1e-5,
                              "CBPC node scale changed")
        previous = value
        return value

    def transition(action):
        receipts = document["receipts"][action]
        scene.require(type(receipts) is list and len(receipts) == len(plan["calls"][action]), "Every CBPC node needs one receipt")
        for receipt, request in zip(receipts, plan["calls"][action]):
            consume(receipt["before"])
            cbpc.completed(receipt, request)
            consume(receipt["after"])

    transition("start")
    primed = consume(document["stimulusBaseline"])

    def controls(value, moving=None):
        # Dynamic driver local transforms are CBPC outputs, not animation
        # controls. Independent torso/root/CME local transforms remain fixed.
        for name in (*scene.CONTROL, *scene.INTERMEDIATES, *groups):
            if name != moving:
                pulse._same_transform(value["nodes"][name]["local"], primed["nodes"][name]["local"],
                                      "Independent CBPC local control changed: " + name)
        for name in scene.CONTROL:
            pulse._same_transform(scene.relative(value["nodes"][name]["world"], value["root"]),
                                  scene.relative(primed["nodes"][name]["world"], primed["root"]), "CBPC parent control moved")
        for name in groups:
            if name != moving:
                pulse._same_transform(value["nodes"][name]["world"], primed["nodes"][name]["world"],
                                      "CBPC pulse anchor did not return/drifted: " + name)

    windows, timings, holds = {}, {}, {}
    for phase, action in zip(scene.PHASES, (None, "stop", "restart")):
        if action:
            transition(action)
        rows = document["pulses"][phase]
        scene.require(set(rows) == set(groups), "Missing/extra CBPC pulse families")
        windows[phase], timings[phase], holds[phase] = {}, {}, {}
        for anchor in groups:
            row = rows[anchor]
            for stage, displacement in (("moved", pulse.offset(anchor)), ("returned", [0., 0., 0.])):
                pulse._commands(row["commands"][stage], reference, sex, anchor, originals[anchor]["key"], displacement)
            before = consume(row["beforePulse"])
            controls(before)
            moved = consume(row["moved"])
            pulse.anchor_excitation(moved, primed, sex, anchor, pulse.offset(anchor))
            controls(moved, moving=anchor)
            returned = consume(row["returned"])
            pulse.anchor_excitation(returned, primed, sex, anchor, [0., 0., 0.])
            controls(returned)
            hold = (returned["time"] - moved["time"])/1e9
            scene.require(spec["holdSeconds"] <= hold <= spec["maxHoldSeconds"], "CBPC pulse hold outside declaration")
            raw_samples = row["samples"]
            scene.require(type(raw_samples) is list and len(raw_samples) == spec["samples"], "Exactly 25 read-only CBPC samples required")
            samples = []
            for raw in raw_samples:
                sample = consume(raw)
                controls(sample)
                samples.append(sample)
            gaps = [(b["time"] - a["time"])/1e9 for a, b in zip(samples, samples[1:])]
            scene.require((samples[0]["time"] - returned["time"])/1e9 <= spec["maxGapSeconds"] and
                          min(gaps) >= spec["minGapSeconds"] and max(gaps) <= spec["maxGapSeconds"] and
                          sum(gaps) >= spec["minSpanSeconds"], "CBPC pulse cadence/span outside declaration")
            windows[phase][anchor] = {"before": before, "samples": samples, "excursion": [moved, returned, *samples]}
            timings[phase][anchor] = {"samples": len(samples), "spanSeconds": sum(gaps), "meanGapSeconds": statistics.mean(gaps)}
            holds[phase][anchor] = hold

    comparable = True
    for anchor in groups:
        times = [timings[phase][anchor]["meanGapSeconds"] for phase in scene.PHASES]
        durations = [holds[phase][anchor] for phase in scene.PHASES]
        comparable &= max(times) - min(times) <= spec["cadenceComparabilityFraction"]*min(times)
        comparable &= max(durations) - min(durations) <= spec["holdComparabilityFraction"]*min(durations)
    result = {"status": "unconfirmed", "bindingState": "unknown", "nativeCompletionsVerified": True,
              "protocol": spec, "channels": {}, "selectiveChannels": [], "missingDrivers": [],
              "cadence": timings, "holdSeconds": holds, "excitationTimingComparable": comparable,
              "solverQualified": False, "contactQualified": False, "physicsPhaseObserved": False,
              "runtimeQualified": False, "limits": ["Void calls do not prove binding or original state.",
                  "Pinned parent paths require matching externally verified winning XP32 resources.",
                  "No contact, render/solver-phase, undisclosed driver-writer or lifecycle qualification."]}
    for anchor, nodes in groups.items():
        for name in nodes:
            parent = paths[name][0]
            output = result["channels"][name] = {"anchor": anchor, "immediateParent": parent,
                                                "local": {}, "worldImmediateParent": {}, "parentMotion": {}}
            for space in ("local", "worldImmediateParent"):
                for channel in scene.FLOORS:
                    stats = {}
                    for phase in scene.PHASES:
                        window = windows[phase][anchor]
                        def vector(value):
                            own = value["nodes"][name]
                            return (own["local"] if space == "local" else
                                    scene.relative(own["world"], value["nodes"][parent]["world"]))[channel]
                        stats[phase] = pulse.residual([vector(value) for value in window["samples"]], vector(window["before"]))
                    output[space][channel] = stats
            for phase in ("active", "restarted"):
                window = windows[phase][anchor]
                zero = window["before"]["nodes"][parent]["world"]
                output["parentMotion"][phase] = {channel: pulse.residual(
                    [value["nodes"][parent]["world"][channel] for value in window["excursion"]], zero[channel])["peak"]
                    for channel in scene.FLOORS}
            parent_moved = all(any(output["parentMotion"][phase][channel] > 4*floor for channel, floor in scene.FLOORS.items())
                               for phase in ("active", "restarted"))
            for channel, floor in scene.FLOORS.items():
                selective = parent_moved
                for space in ("local", "worldImmediateParent"):
                    stats = output[space][channel]
                    on = min(stats["active"]["rms"], stats["restarted"]["rms"])
                    variation = min(stats["active"]["variation"], stats["restarted"]["variation"])
                    selective &= (on > spec["minimumSignalFloors"]*floor and variation > spec["minimumSignalFloors"]*floor and
                                  stats["stopped"]["rms"] <= max(floor, spec["maximumOffRatio"]*on))
                if selective:
                    result["selectiveChannels"].append({"node": name, "channel": channel})
            if not any(row["node"] == name for row in result["selectiveChannels"]):
                result["missingDrivers"].append(name)
    if not result["missingDrivers"] and comparable:
        result["status"] = "sampled-pulse-contrast-observed"
    return result
