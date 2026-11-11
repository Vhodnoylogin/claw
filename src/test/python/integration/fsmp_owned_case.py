"""One provider-specific test callback inside an already owned Autotest Session.

The external harness supplies machine paths/profile and invokes this callback
after the ordinary fixture scenario. This module does not launch or install.
"""
import json
import math
from pathlib import Path
import time

import fsmp_probe as probe


def dispose_fixture(session, reference, sex, admitted, *, maximum_seconds=8, sleep=time.sleep):
    """Disable only the admitted disposable actor, then verify world/crosshair release."""
    probe.require(type(maximum_seconds) in (int, float) and math.isfinite(maximum_seconds) and 1 <= maximum_seconds <= 15,
                  "Owned fixture disposal requires a finite 1..15-second bound")
    expected = probe.snapshot(admitted, reference, sex)
    end = time.monotonic() + maximum_seconds
    output = session.dir / "fsmp-probe" / "fixture-disposal.json"
    record = {"reference": reference, "intent": None, "observations": []}

    def save():
        output.write_text(json.dumps(record, indent=2), encoding="utf-8")

    def call(tool, args):
        remaining = end - time.monotonic()
        probe.require(remaining > 0, "Owned fixture disposal deadline exhausted")
        session.phase("fsmp: dispose-fixture", remaining + 1)
        return session.tool(tool, args, timeout=min(remaining, 5), deadline=end)

    query = {"kind": "world_observer", "refs": [reference], "actors": True,
             "nodes": [{"ref": reference, "name": name, "firstPerson": False} for name in probe.node_names(sex)]}
    before = call("inspect", query)
    current = probe.snapshot(before, reference, sex)
    record["before"] = before
    save()
    probe.require(current["guard"] == expected["guard"], "Owned fixture changed before disposal")
    probe.require(current["sample"] > expected["sample"] and current["time"] > expected["time"],
                  "Owned fixture disposal precondition was replayed")
    record["intent"] = {"script": "ObjectReference", "function": "Disable", "self": {"form": reference}, "args": [False]}
    save()  # A unique void-call intent; no mutation replay after an uncertain result.
    record["receipt"] = call("papyrus", {"action": "call", **record["intent"], "timeoutMs": 5000})
    save()
    receipt = record["receipt"]
    probe.require(receipt.get("called") is True and receipt.get("returnedType") == "none" and
                  "returned" in receipt and receipt["returned"] is None and not receipt.get("error"),
                  "Owned fixture Disable completion uncertain; do not replay")
    last_sample, last_time = current["sample"], current["time"]
    while time.monotonic() < end:
        raw = call("inspect", {"kind": "world_observer", "refs": [reference], "actors": True})
        rows = raw.get("refs", [])
        probe.require(raw.get("ok") is True and raw.get("quality") == "complete" and len(rows) == 1 and
                      raw.get("sessionId") == before["sessionId"] and raw.get("loadGeneration") == before["loadGeneration"] and
                      raw.get("sampleId", 0) > last_sample and raw.get("producerMonotonicNs", 0) > last_time,
                      "Owned fixture disposal observation lost continuity")
        row = rows[0]
        probe.require(row.get("identity") == before["refs"][0]["identity"] and
                      row.get("baseForm") == before["refs"][0]["baseForm"] and row.get("deleted") is False,
                      "Owned fixture identity changed during disposal")
        last_sample, last_time = raw["sampleId"], raw["producerMonotonicNs"]
        crosshair = call("papyrus", {"action": "call", "script": "Game", "function": "GetCurrentCrosshairRef", "args": []})
        record["observations"].append({"world": raw, "crosshair": crosshair})
        save()
        probe.require(crosshair.get("called") is True and "returned" in crosshair, "Crosshair readback value unavailable")
        if row.get("disabled") is True and crosshair["returned"] is None:
            record["verifiedDisabledAndCrosshairReleased"] = True
            save()
            return record
        sleep(.1)
    raise ValueError("Owned fixture disabled/null-crosshair readback not observed")


def run(session, reference, sex, *, maximum_seconds=160, stimulus="reference", sleep=time.sleep):
    probe.require(type(maximum_seconds) in (int, float) and 30 <= maximum_seconds <= 180,
                  "FSMP callback requires a finite 30..180-second bound")
    probe.require(stimulus in ("reference", "xml-anchors"), "Unknown excitation contract")
    probe.drivers(sex)  # Validate the explicit sex before any observation or write.
    end = time.monotonic() + maximum_seconds
    output = session.dir / "fsmp-probe"
    output.mkdir(exist_ok=False)
    observations = output / "observations"
    observations.mkdir()
    state = {"reference": reference, "sex": sex, "receipts": {}, "windows": {},
             "original": None, "current": None, "uncertain": False, "intent": None,
             "stimulus": stimulus, "anchorOriginals": {}}
    state["declaredPointPeriodSeconds"] = .85 if stimulus == "xml-anchors" else None
    baseline = previous = None
    cleaning = False

    def save(*, full=False):
        # Large immutable observations are written once. The pre-dispatch
        # journal stays small instead of reserializing every previous window on
        # every key operation, which changed the actual stimulus cadence.
        journal = {key: value for key, value in state.items() if key not in (
            "windows", "baseline", "stimulusBaseline", "anchorCalibration", "receipts", "intent")}
        journal["windows"] = {phase: [row["sampleId"] for row in rows] for phase, rows in state["windows"].items()}
        journal["receipts"] = {action: {key: value for key, value in receipt.items() if key not in ("before", "after")}
                               | {side + "Sample": receipt[side]["sampleId"] for side in ("before", "after")}
                               for action, receipt in state["receipts"].items()}
        intent = state["intent"]
        journal["intent"] = ({key: value for key, value in intent.items() if key != "before"}
                             | ({"beforeSample": intent["before"]["sampleId"]} if "before" in intent else {})) if intent else None
        (output / "journal.json").write_text(json.dumps(journal, indent=2), encoding="utf-8")
        if full:
            (output / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
        session.state["fsmpProbe"] = {"directory": str(output), "intent": journal["intent"],
                                      "uncertain": state["uncertain"]}
        session.save()

    def call(name, tool, args):
        remaining = end - (0 if cleaning else 20) - time.monotonic()
        probe.require(remaining > 0, "Finite FSMP case deadline exhausted")
        session.phase("fsmp: " + name, min(remaining, 12) + 2)
        return session.tool(tool, args, timeout=min(remaining, 10), deadline=end)

    query = {"kind": "world_observer", "refs": [reference], "actors": True,
             "nodes": [{"ref": reference, "name": name, "firstPerson": False} for name in probe.node_names(sex)]}

    def observe(name):
        nonlocal previous
        raw = call(name, "inspect", query)
        value = probe.snapshot(raw, reference, sex)
        if baseline is not None:
            probe.require(value["guard"] == baseline["guard"], "Owned FSMP actor/root continuity lost")
        if previous is not None:
            probe.require(value["sample"] > previous["sample"] and value["time"] > previous["time"],
                          "Replayed/nonadvancing FSMP guard")
        previous = value
        (observations / (str(value["sample"]) + "-" + name + ".json")).write_text(
            json.dumps(raw, indent=2), encoding="utf-8")
        return raw

    def toggle(action, on, names=None):
        names = list(names or probe.drivers(sex))
        before = observe(action + "-before")
        state["intent"] = {"action": action, "on": on, "names": names, "before": before}
        state["current"] = None  # Unknown until this unique native return is captured.
        save()
        try:
            result = call(action, "papyrus", {"action": "call", "script": "DynamicHDT", "function": "TogglePhysics",
                "args": [{"form": reference}, names, on], "timeoutMs": 8000})
            bits = probe.bool_vector(result["returned"], len(names))
            state["intent"]["nativeResult"] = result
            save()
            after = observe(action + "-after")
        except Exception:
            state["uncertain"] = True
            save()
            raise
        receipt = {"previous": bits, "before": before, "after": after, "nativeResult": result}
        state["receipts"][action] = receipt
        if action == "first-off":
            state["original"] = bits[:]
        if names == list(probe.drivers(sex)):
            state["current"] = [on]*len(names)
        else:
            state["current"] = state["original"][:]
        state["intent"] = None
        save()
        return bits

    def wait(seconds, name):
        call(name, "papyrus", {"action": "call", "script": "Utility", "function": "Wait",
                               "args": [float(seconds)], "timeoutMs": 8000})

    def pap(name, script, function, args):
        return call(name, "papyrus", {"action": "call", "script": script, "function": function,
                                      "args": args, "timeoutMs": 8000})["returned"]

    def transform_args(name):
        return [{"form": reference}, False, sex == "female", name]

    def apply_anchors(offset):
        for name, original in state["anchorOriginals"].items():
            observe("anchor-write-guard-" + name)
            args = transform_args(name) + [original["key"]]
            state["intent"] = {"action": "anchor-own-key", "node": name, "key": original["key"], "offset": offset}
            save()
            pap("anchor-write-" + name, "NiOverride", "AddNodeTransformPosition", args + [offset])
            value = pap("anchor-storage-" + name, "NiOverride", "GetNodeTransformPosition", args)
            probe.require(probe.max_delta(probe.numbers(value, 3), offset) <= 1e-6, "Own anchor key storage mismatch")
            pap("anchor-apply-" + name, "NiOverride", "UpdateNodeTransform", transform_args(name))
            state["intent"] = None
            save()

    try:
        raw = observe("baseline")
        baseline = probe.snapshot(raw, reference, sex)
        state["baseline"] = raw
        plan = probe.prepare(reference, sex, baseline["position"])
        (output / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
        save()
        expected = len(probe.drivers(sex))
        probe.require(toggle("first-off", False) == [True]*expected, "Fresh dynamic-body gate failed; no excitation")
        probe.require(toggle("reenable", True) == [False]*expected, "Reenable state mismatch")
        stimulus_baseline = baseline
        if stimulus == "xml-anchors":
            key = "CLAW.FSMPProbe." + session.state["id"]
            for name in dict.fromkeys(probe.anchors(sex).values()):
                current = probe.snapshot(observe("anchor-original-" + name), reference, sex)
                keys = pap("anchor-original-keys-" + name, "NiOverride", "GetNodeTransformKeys", transform_args(name))
                probe.require(keys == [], "Fresh anchor has external transform keys; do not recompose them")
                exists = pap("anchor-own-key-absent-" + name, "NiOverride", "HasNodeTransformPosition", transform_args(name) + [key])
                probe.require(exists is False, "Own anchor key already exists")
                state["anchorOriginals"][name] = {"key": key, "keysBefore": keys,
                    "local": current["nodes"][name]["local"], "world": current["nodes"][name]["world"]}
                save()
            apply_anchors([0., 0., 0.])
            wait(2., "anchor-prime-settle")
            raw = observe("stimulus-baseline")
            stimulus_baseline = probe.snapshot(raw, reference, sex)
            state["stimulusBaseline"] = raw
            save()
            state["anchorCalibration"] = {}
            for tag, offset in (("moved", [.25, 0., 0.]), ("reset", [0., 0., 0.])):
                apply_anchors(offset)
                wait(.2, "anchor-calibration-" + tag)
                raw = observe("anchor-calibration-readback-" + tag)
                state["anchorCalibration"][tag] = raw
                save()
                probe.anchor_excitation(probe.snapshot(raw, reference, sex), stimulus_baseline, sex, offset)
        for phase in probe.PHASES:
            if phase == "stopped":
                probe.require(toggle("second-off", False) == [True]*expected, "Second off state mismatch")
            elif phase == "restarted":
                probe.require(toggle("restore", True) == [False]*expected, "Restore state mismatch")
            wait(2., phase + "-settle")
            state["windows"][phase] = []
            phase_start = time.monotonic()
            for index, point in enumerate(plan["windows"][phase]):
                if stimulus == "xml-anchors":
                    sleep(max(0., phase_start + index*state["declaredPointPeriodSeconds"] - time.monotonic()))
                observe(phase + "-guard-" + str(index))
                if stimulus == "xml-anchors":
                    apply_anchors(probe.anchor_offset(index))
                else:
                    state["intent"] = {"action": "position", "expectedPosition": point["expectedPosition"]}
                    save()
                    call(phase + "-position-" + str(index), "papyrus", point["steps"][0]["args"])
                wait(.2, phase + "-wait-" + str(index))
                raw = observe(phase + "-sample-" + str(index))
                state["windows"][phase].append(raw)
                state["intent"] = None
                save()
                observed = probe.snapshot(raw, reference, sex)
                if stimulus == "xml-anchors":
                    probe.anchor_excitation(observed, stimulus_baseline, sex, probe.anchor_offset(index))
                else:
                    probe.reference_excitation(observed, baseline, point["expectedPosition"])
        diagnostic = probe.score(state)
        (output / "diagnostic.json").write_text(json.dumps(diagnostic, indent=2), encoding="utf-8")
        session.state["checks"].append({"name": "fsmp-previous-state-protocol", "result": "passed",
                                         "observation": diagnostic})
        session.save()
        return diagnostic
    except Exception as error:
        state["primaryError"] = str(error)
        raise
    finally:
        cleaning = True
        cleanup = {"physics": "no-known-restore-needed", "position": "not-admitted"}
        if stimulus == "xml-anchors":
            cleanup["position"] = "not-mutated-by-anchor-probe"
        errors = []
        try:
            if baseline is not None and not state["uncertain"] and state["original"] is not None and state["current"] is not None:
                names = [name for name, old, now in zip(probe.drivers(sex), state["original"], state["current"]) if old and not now]
                if names:
                    probe.require(toggle("cleanup", True, names) == [False]*len(names), "Known-state cleanup mismatch")
                    cleanup["physics"] = "originally-true-only-restored"
            elif state["uncertain"]:
                cleanup["physics"] = "unknown-no-replay; owned game teardown required"
        except Exception as error:
            errors.append("physics: " + str(error))
        if state["anchorOriginals"]:
            cleanup["anchors"] = {}
            for name, original in state["anchorOriginals"].items():
                try:
                    observe("cleanup-anchor-guard-" + name)
                    args = transform_args(name) + [original["key"]]
                    keys = pap("cleanup-anchor-keys-" + name, "NiOverride", "GetNodeTransformKeys", transform_args(name))
                    probe.require(set(keys) <= {original["key"]}, "New foreign anchor key; do not overwrite its transform")
                    if pap("cleanup-anchor-has-" + name, "NiOverride", "HasNodeTransformPosition", args):
                        probe.require(pap("cleanup-anchor-remove-" + name, "NiOverride", "RemoveNodeTransformPosition", args) is True,
                                      "Own anchor position component removal failed")
                        pap("cleanup-anchor-apply-" + name, "NiOverride", "UpdateNodeTransform", transform_args(name))
                    # SKEE recomposes a cached rest pose. Restore the captured
                    # posed local transform, not that cached pose, after removing
                    # only our position component. No dynamic driver is written.
                    ni = [{"form": reference}, name]
                    for function, value in (("SetNodeLocalPosition", original["local"]["translation"]),
                                            ("SetNodeLocalRotationMatrix", original["local"]["rotationRowMajor"]),
                                            ("SetNodeScale", original["local"]["scale"])):
                        returned = pap("cleanup-" + function + "-" + name, "NetImmerse", function, ni + [value, False])
                        if function != "SetNodeScale":
                            probe.require(returned is True, "Anchor local restore not accepted")
                    wait(.2, "cleanup-anchor-wait-" + name)
                    current = probe.snapshot(observe("cleanup-anchor-readback-" + name), reference, sex)
                    for channel, floor in probe.FLOORS.items():
                        probe.require(probe.max_delta(current["nodes"][name]["local"][channel], original["local"][channel]) <= max(floor, .001),
                                      "Original anchor local transform not restored")
                    probe.require(abs(current["nodes"][name]["local"]["scale"] - original["local"]["scale"]) <= 1e-5,
                                  "Original anchor scale not restored")
                    # HasPosition reflects key-container presence in this SKEE
                    # implementation, even after all three components are gone.
                    # Only after the first known successful removal, a second
                    # scoped removal returning false proves no component remains.
                    probe.require(pap("cleanup-anchor-component-absent-" + name, "NiOverride", "RemoveNodeTransformPosition", args) is False,
                                  "Own anchor position component still existed")
                    has_container = pap("cleanup-anchor-container-" + name, "NiOverride", "HasNodeTransformPosition", args)
                    cleanup["anchors"][name] = {"ownPositionComponentAbsent": True, "originalLocalReadback": current["nodes"][name]["local"],
                                               "hasKeyContainerAfterRemoval": has_container, "emptyKeyContainerMayRemain": True}
                except Exception as error:
                    cleanup["anchors"][name] = {"error": str(error)}
                    errors.append(name + ": " + str(error))
        try:
            if baseline is not None and stimulus == "reference" and end - time.monotonic() > 5:
                observe("cleanup-position-guard")
                call("cleanup-position", "papyrus", {"action": "call", "script": "ObjectReference", "function": "SetPosition",
                    "self": {"form": reference}, "args": baseline["position"], "timeoutMs": 8000})
                wait(.2, "cleanup-position-wait")
                actual = probe.snapshot(observe("cleanup-position-readback"), reference, sex)["position"]
                probe.require(probe.max_delta(actual, baseline["position"]) <= .025, "Original position restore not observed")
                cleanup["position"] = "observed-original-origin"
        except Exception as error:
            errors.append("position: " + str(error))
        cleanup["errors"] = errors
        cleanup["primaryError"] = state.get("primaryError")
        (output / "cleanup.json").write_text(json.dumps(cleanup, indent=2), encoding="utf-8")
        save(full=True)
        if errors:
            raise ValueError("; ".join((["primary: " + state["primaryError"]] if state.get("primaryError") else []) + errors))
