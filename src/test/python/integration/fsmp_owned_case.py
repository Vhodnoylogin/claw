"""One provider-specific test callback inside an already owned Autotest Session.

The external harness supplies machine paths/profile and invokes this callback
after the ordinary fixture scenario. This module does not launch or install.
"""
import json
import time

import fsmp_probe as probe
import fsmp_pulse as pulse
from owned_anchors import OwnedAnchors, next_sample_time, dispose_fixture


def run(session, reference, sex, *, maximum_seconds=160, stimulus="reference", sleep=time.sleep):
    probe.require(type(maximum_seconds) in (int, float) and 30 <= maximum_seconds <= 180,
                  "FSMP callback requires a finite 30..180-second bound")
    probe.require(stimulus in ("reference", "xml-anchors", "xml-anchor-pulse"), "Unknown excitation contract")
    probe.drivers(sex)  # Validate the explicit sex before any observation or write.
    is_anchor = stimulus != "reference"
    is_pulse = stimulus == "xml-anchor-pulse"
    end = time.monotonic() + maximum_seconds
    output = session.dir / "fsmp-probe"
    output.mkdir(exist_ok=False)
    observations = output / "observations"
    observations.mkdir()
    state = {"reference": reference, "sex": sex, "receipts": {}, "windows": {},
             "original": None, "current": None, "uncertain": False, "intent": None,
             "stimulus": stimulus, "anchorOriginals": {}}
    state["declaredPointPeriodSeconds"] = .85 if stimulus == "xml-anchors" else None
    if is_pulse:
        state.update(protocol=pulse.protocol(), pulses={})
    baseline = previous = None
    cleaning = False

    def save(*, full=False):
        # Large immutable observations are written once. The pre-dispatch
        # journal stays small instead of reserializing every previous window on
        # every key operation, which changed the actual stimulus cadence.
        journal = {key: value for key, value in state.items() if key not in (
            "windows", "pulses", "baseline", "stimulusBaseline", "anchorCalibration", "receipts", "intent")}
        journal["windows"] = {phase: [row["sampleId"] for row in rows] for phase, rows in state["windows"].items()}
        if is_pulse:
            journal["pulses"] = {phase: {name: {
                **{side: row[side]["sampleId"] for side in ("beforePulse", "moved", "returned") if side in row},
                "samples": [sample["sampleId"] for sample in row.get("samples", [])], "commands": row.get("commands", {})}
                for name, row in families.items()} for phase, families in state["pulses"].items()}
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
            if is_pulse:
                probe.require(result.get("called") is True and result.get("returnedType") == "bool[]" and
                              "returned" in result and not result.get("error"),
                              "Native pulse body-state completion uncertain; do not replay")
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
        result = call(name, "papyrus", {"action": "call", "script": "Utility", "function": "Wait",
                                        "args": [float(seconds)], "timeoutMs": 8000})
        if is_pulse:
            probe.require(pulse._completed_none(result), "FSMP settle completion uncertain; do not replay")

    def pap_receipt(name, script, function, args):
        return call(name, "papyrus", {"action": "call", "script": script, "function": function,
                                      "args": args, "timeoutMs": 8000})

    anchors = OwnedAnchors(reference, sex, "CLAW.FSMPProbe." + session.state["id"], state,
                           observe=observe, receipt=pap_receipt, wait=wait, persist=save, strict=is_pulse)
    apply_anchors = anchors.apply

    try:
        raw = observe("baseline")
        baseline = probe.snapshot(raw, reference, sex)
        state["baseline"] = raw
        plan = (pulse.prepare if is_pulse else probe.prepare)(reference, sex, baseline["position"])
        (output / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
        save()
        expected = len(probe.drivers(sex))
        probe.require(toggle("first-off", False) == [True]*expected, "Fresh dynamic-body gate failed; no excitation")
        probe.require(toggle("reenable", True) == [False]*expected, "Reenable state mismatch")
        stimulus_baseline = baseline
        if is_anchor:
            anchors.capture()
            apply_anchors([0., 0., 0.])
            wait(2., "anchor-prime-settle")
            raw = observe("stimulus-baseline")
            stimulus_baseline = probe.snapshot(raw, reference, sex)
            state["stimulusBaseline"] = raw
            save()
            if not is_pulse:
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
            if is_pulse:
                anchors.collect_phase(phase, state["protocol"], stimulus_baseline, sleep=sleep)
                continue
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
        diagnostic = (pulse.score if is_pulse else probe.score)(state)
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
        if is_anchor:
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
            cleanup["anchors"], anchor_errors = anchors.restore()
            errors.extend(anchor_errors)
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
