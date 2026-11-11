"""Pure, separately declared anchor-pulse protocol and retained-evidence scorer.

Only zero-return read-only samples contribute response. This avoids treating a
stale disabled driver's motion relative to a moving anchor as physical motion.
No transport, process, provider or model mutation occurs in this module.
"""
from __future__ import annotations

import math
import statistics

import fsmp_probe as probe


def protocol():
    return {"id": "claw-fsmp-anchor-pulse/2", "offset": [.5, 0., 0.], "p1Offset": [.1, 0., 0.],
            "holdSeconds": .12, "maxHoldSeconds": .6, "holdComparabilityFraction": .25,
            "samples": 25, "samplePeriodSeconds": .1, "minGapSeconds": .04,
            "maxGapSeconds": .2, "minSpanSeconds": 2.1, "cadenceComparabilityFraction": .25,
            "minimumSignalFloors": 4, "maximumOffRatio": .25, "requireReadOnlyVariation": True}


def offset(anchor=None):
    if anchor is not None:
        probe.require(anchor in families("female"), "Unknown pulse family")
    return protocol()["p1Offset" if anchor in ("NPC L PreBreast P1", "NPC R PreBreast P1") else "offset"]


def families(sex):
    result = {}
    for driver, anchor in probe.anchors(sex).items():
        result[anchor] = (*result.get(anchor, ()), driver)
    return result


def prepare(reference, sex, origin):
    reference, origin = probe.form(reference), probe.numbers(origin, 3)
    return {"schemaVersion": 1, "reference": reference, "sex": sex, "origin": origin,
            "protocol": protocol(), "families": {anchor: list(nodes) for anchor, nodes in families(sex).items()},
            "baselineQuery": {"tool": "inspect", "args": {"kind": "world_observer", "refs": [reference],
                "actors": True, "nodes": [{"ref": reference, "name": name, "firstPerson": False}
                                           for name in probe.node_names(sex)]}},
            "runtimeQualified": False}


def _same_transform(actual, expected, message):
    for channel, floor in probe.FLOORS.items():
        probe.require(probe.max_delta(actual[channel], expected[channel]) <= floor, message)
    probe.require(abs(actual["scale"] - expected["scale"]) <= 1e-5, message)


def anchor_excitation(observed, baseline, sex, anchor, displacement):
    """Actual single-anchor offset, including inverse baseline rotation/scale."""
    probe.require(anchor in families(sex), "Unknown pulse family")
    displacement = probe.numbers(displacement, 3)
    probe.require(probe.max_delta(observed["position"], baseline["position"]) <= .025,
                  "Actor moved during anchor pulse")
    _same_transform(observed["root"], baseline["root"], "Model root moved during anchor pulse")
    for name in families(sex):
        actual = observed["nodes"][name]["world"]
        initial = baseline["nodes"][name]["world"]
        relative = probe.relative(actual, initial)
        wanted = displacement if name == anchor else [0., 0., 0.]
        probe.require(probe.max_delta(relative["translation"], wanted) <= .003,
                      "Actual pulse anchor displacement missing/wrong: " + name)
        probe.require(probe.max_delta(relative["rotationRowMajor"], [1.,0.,0.,0.,1.,0.,0.,0.,1.]) <= 1e-5
                      and abs(relative["scale"] - 1.) <= 1e-5, "Pulse anchor rotated/scaled")


def _completed_none(value):
    return (type(value) is dict and value.get("called") is True and value.get("returnedType") == "none" and
            "returned" in value and value["returned"] is None and not value.get("error"))


def _commands(rows, reference, sex, anchor, key, displacement):
    probe.require(type(rows) is list and len(rows) == 2, "Exact two pulse write completions required")
    args = [{"form": reference}, False, sex == "female", anchor]
    expected = (("AddNodeTransformPosition", args + [key, displacement]), ("UpdateNodeTransform", args))
    for row, (function, arguments) in zip(rows, expected):
        actual = row.get("args", [])
        probe.require(row.get("script") == "NiOverride" and row.get("function") == function and
                      actual == arguments and type(actual[1]) is bool and type(actual[2]) is bool and
                      (function != "AddNodeTransformPosition" or all(type(v) is float for v in actual[-1])) and
                      _completed_none(row.get("nativeResult", {})),
                      "Pulse write completion/arguments unavailable; do not infer or replay")


def residual(vectors, baseline):
    """Maximum component RMS and peak relative to the same zero baseline."""
    deltas = [[value - initial for value, initial in zip(vector, baseline)] for vector in vectors]
    return {"rms": max(math.sqrt(statistics.mean(value*value for value in column)) for column in zip(*deltas)),
            "peak": max(abs(value) for vector in deltas for value in vector), "variation": probe.spread(vectors)}


def score(document):
    spec = protocol()
    probe.require(document.get("protocol") == spec and document.get("stimulus") == "xml-anchor-pulse",
                  "Pulse protocol was absent or changed")
    reference, sex = probe.form(document["reference"]), document["sex"]
    groups = families(sex)
    keys = [document["anchorOriginals"][anchor]["key"] for anchor in groups]
    probe.require(all(type(key) is str and key.startswith("CLAW.FSMPProbe.") and len(key) > len("CLAW.FSMPProbe.")
                      for key in keys) and len(set(keys)) == 1, "One explicit run-owned pulse key required")
    probe.require(all(document["anchorOriginals"][anchor].get("keysBefore") == [] for anchor in groups),
                  "Fresh pulse anchors require explicit initially empty key sets")
    gate = probe.binding_gate(sex, document["receipts"])
    baseline = probe.snapshot(document["baseline"], reference, sex)
    previous = baseline

    def consume(raw):
        nonlocal previous
        value = probe.snapshot(raw, reference, sex)
        probe.require(value["guard"] == baseline["guard"], "Actor/root/source continuity lost")
        probe.require(value["sample"] > previous["sample"] and value["time"] > previous["time"],
                      "Replayed/nonadvancing pulse observation")
        probe.require(probe.max_delta(value["position"], baseline["position"]) <= .025 and
                      probe.max_delta(value["angles"], baseline["angles"]) <= 1e-5,
                      "Pulse fixture moved/rotated")
        _same_transform(value["root"], baseline["root"], "Pulse root moved/rotated/scaled")
        for name in probe.node_names(sex):
            for space in ("world", "local"):
                probe.require(abs(value["nodes"][name][space]["scale"] - baseline["nodes"][name][space]["scale"]) <= 1e-5,
                              "Pulse node scale changed")
        previous = value
        return value

    def transition(action):
        receipt = document["receipts"][action]
        native = receipt.get("nativeResult", {})
        probe.require(native.get("called") is True and native.get("returnedType") == "bool[]" and
                      probe.bool_vector(native.get("returned"), len(probe.drivers(sex))) == receipt["previous"] and
                      not native.get("error"),
                      "Native physics transition completion missing/uncertain")
        for side in ("before", "after"):
            consume(receipt[side])

    transition("first-off")
    transition("reenable")
    primed = consume(document["stimulusBaseline"])

    def controls(value, moving=None):
        for name in probe.node_names(sex):
            if name == moving:
                continue  # Only this mass-zero anchor's declared translation is written.
            for channel, floor in probe.FLOORS.items():
                probe.require(probe.max_delta(value["nodes"][name]["local"][channel], primed["nodes"][name]["local"][channel]) <= floor,
                              "Local animation changed during pulse: " + name)
        for name in probe.CONTROL:
            _same_transform(probe.relative(value["nodes"][name]["world"], value["root"]),
                            probe.relative(primed["nodes"][name]["world"], primed["root"]), "Pulse control parent moved")
        for name in groups:
            if name != moving:
                _same_transform(value["nodes"][name]["world"], primed["nodes"][name]["world"],
                                "Pulse anchor did not return or drifted: " + name)

    windows, timings, holds = {}, {}, {}
    for phase in probe.PHASES:
        if phase == "stopped":
            transition("second-off")
        elif phase == "restarted":
            transition("restore")
        rows = document["pulses"][phase]
        probe.require(set(rows) == set(groups), "Missing/extra pulse families")
        windows[phase], timings[phase], holds[phase] = {}, {}, {}
        for anchor in groups:
            pulse = rows[anchor]
            key = document["anchorOriginals"][anchor]["key"]
            _commands(pulse["commands"]["moved"], reference, sex, anchor, key, offset(anchor))
            _commands(pulse["commands"]["returned"], reference, sex, anchor, key, [0., 0., 0.])
            before = consume(pulse["beforePulse"])
            controls(before)
            moved = consume(pulse["moved"])
            anchor_excitation(moved, primed, sex, anchor, offset(anchor))
            controls(moved, moving=anchor)
            returned = consume(pulse["returned"])
            anchor_excitation(returned, primed, sex, anchor, [0., 0., 0.])
            controls(returned)
            hold = (returned["time"] - moved["time"])/1e9
            probe.require(spec["holdSeconds"] <= hold <= spec["maxHoldSeconds"], "Pulse hold duration outside declared range")
            raw_samples = pulse["samples"]
            probe.require(type(raw_samples) is list and len(raw_samples) == spec["samples"], "Exactly 25 read-only pulse samples required")
            samples = []
            for raw in raw_samples:
                value = consume(raw)
                controls(value)
                samples.append(value)
            gaps = [(b["time"] - a["time"])/1e9 for a, b in zip(samples, samples[1:])]
            probe.require((samples[0]["time"] - returned["time"])/1e9 <= spec["maxGapSeconds"] and
                          min(gaps) >= spec["minGapSeconds"] and max(gaps) <= spec["maxGapSeconds"] and
                          sum(gaps) >= spec["minSpanSeconds"], "Read-only pulse cadence/span outside declared range")
            windows[phase][anchor] = {"before": before, "samples": samples}
            timings[phase][anchor] = {"samples": len(samples), "spanSeconds": sum(gaps), "gapsSeconds": gaps}
            holds[phase][anchor] = hold

    comparable = True
    for anchor in groups:
        durations = [holds[phase][anchor] for phase in probe.PHASES]
        comparable &= max(durations) - min(durations) <= spec["holdComparabilityFraction"]*min(durations)
        means = [statistics.mean(timings[phase][anchor]["gapsSeconds"]) for phase in probe.PHASES]
        comparable &= max(means) - min(means) <= spec["cadenceComparabilityFraction"]*min(means)
    result = {**gate, "protocol": spec, "status": "unconfirmed", "physicsPhaseObserved": False,
              "channels": {}, "selectiveChannels": [], "missingDrivers": [],
              "anchorReturnedBeforeSampling": True, "localAnimationQuiet": True, "controlParentsQuiet": True,
              "excitationTimingComparable": comparable, "cadence": timings, "holdSeconds": holds,
              "limits": ["Read-only scene samples are not synchronized with the physics/render phase.",
                         "Native body bindings and pulse response are separate evidence.",
                         "No contact, appearance, animation lifecycle or solver-source/binary equivalence claim."]}
    for anchor, nodes in groups.items():
        for node in nodes:
            channels = {}
            for channel, floor in probe.FLOORS.items():
                stats = {}
                for phase in probe.PHASES:
                    window = windows[phase][anchor]
                    zero = probe.relative(window["before"]["nodes"][node]["world"], window["before"]["nodes"][anchor]["world"])[channel]
                    values = [probe.relative(row["nodes"][node]["world"], row["nodes"][anchor]["world"])[channel]
                              for row in window["samples"]]
                    stats[phase] = residual(values, zero)
                channels[channel] = stats
                active = min(stats["active"]["rms"], stats["restarted"]["rms"])
                variation = min(stats["active"]["variation"], stats["restarted"]["variation"])
                if (active > spec["minimumSignalFloors"]*floor and variation > spec["minimumSignalFloors"]*floor and
                        stats["stopped"]["rms"] <= max(floor, spec["maximumOffRatio"]*active)):
                    result["selectiveChannels"].append({"node": node, "channel": channel})
            result["channels"][node] = {"anchor": anchor, "worldRelative": channels}
            if not any(row["node"] == node for row in result["selectiveChannels"]):
                result["missingDrivers"].append(node)
    if not result["missingDrivers"] and comparable:
        result["status"] = "sampled-pulse-contrast-observed"
    return result
