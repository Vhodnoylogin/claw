"""One provider-specific test callback inside an already owned Autotest Session.

The external harness supplies machine paths/profile and invokes this callback
after the ordinary fixture scenario. This module does not launch or install.
"""
import copy
import json
import time

import fsmp_probe as probe
import fsmp_pulse as pulse
from owned_anchors import (OwnedAnchors, next_sample_time, dispose_fixture, evidence_subdir,
                           completed_native, quarantine_fixture, fixture_quarantined)


def run(session, reference, sex, *, maximum_seconds=160, stimulus="reference", sleep=time.sleep,
        actor_role="disposable-npc", segment=None, cancelled=lambda: False):
    probe.require(not fixture_quarantined(session), "Owned fixture quarantined; do not start another callback")
    probe.require(type(maximum_seconds) in (int, float) and 30 <= maximum_seconds <= 180,
                  "FSMP callback requires a finite 30..180-second bound")
    probe.require(stimulus in ("reference", "xml-anchors", "xml-anchor-pulse"), "Unknown excitation contract")
    reference = probe.actor_reference(reference, actor_role)
    probe.require(actor_role != "owned-player" or stimulus == "xml-anchor-pulse",
                  "Owned-player probe requires the declared anchor-pulse protocol")
    probe.drivers(sex)  # Validate the explicit sex before any observation or write.
    is_anchor = stimulus != "reference"
    is_pulse = stimulus == "xml-anchor-pulse"
    end = time.monotonic() + maximum_seconds
    subdir = evidence_subdir("fsmp-probe", segment)
    output = session.dir / subdir
    if segment is not None:
        output.parent.mkdir(exist_ok=True)
    output.mkdir(exist_ok=False)
    observations = output / "observations"
    observations.mkdir()
    state = {"reference": reference, "sex": sex, "actorRole": actor_role, "segment": segment,
             "receipts": {}, "windows": {},
             "original": None, "current": None, "uncertain": False, "quarantined": False, "intent": None,
             "stimulus": stimulus, "anchorOriginals": {}}
    state["declaredPointPeriodSeconds"] = .85 if stimulus == "xml-anchors" else None
    if is_pulse:
        state.update(protocol=pulse.protocol(), pulses={})
    baseline = previous = None
    cleaning = False

    def save_raw(*, full=False):
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
                                      "uncertain": state["uncertain"], "quarantined": state["quarantined"],
                                      "segment": segment, "actorRole": actor_role}
        session.save()

    def quarantine(error):
        quarantine_fixture(session, state, error)

    def save(*, full=False):
        try:
            save_raw(full=full)
        except BaseException as error:
            quarantine(error)
            raise

    def remember_failure(error):
        quarantine(error)  # Never depend on journal/session.save succeeding.
        try:
            save_raw(full=True)
        except BaseException as failure:
            state.setdefault("persistenceErrors", []).append(type(failure).__name__ + ": " + str(failure))

    def checkpoint():
        try:
            requested = cancelled()
        except BaseException as error:
            remember_failure(error)
            raise
        if requested:
            error = RuntimeError("FSMP callback cancelled; owned Session teardown required")
            remember_failure(error)
            raise error
        probe.require(not state["quarantined"] and not fixture_quarantined(session),
                      "FSMP callback quarantined; no further tools or disposal")

    def call(name, tool, args):
        checkpoint()
        deadline = end if cleaning else end - 20
        remaining = deadline - time.monotonic()
        probe.require(remaining > 0, "Finite FSMP case deadline exhausted")
        try:
            session.phase("fsmp: " + name, min(remaining, 12) + 2)
            result = session.tool(tool, args, timeout=min(remaining, 10), deadline=deadline)
        except BaseException as error:
            remember_failure(error)
            raise
        if type(result) is not dict or result.get("error") or result.get("isError"):
            state["lastNativeReply"] = result
            if state["intent"] is not None:
                state["intent"]["nativeResult"] = result
            error = ValueError("FSMP transport error envelope; completion uncertain; do not replay")
            remember_failure(error)
            raise error
        return result

    def mutate(name, request, validate, *, before=None):
        checkpoint()
        probe.require(state["intent"] is None, "Previous FSMP mutation completion unresolved")
        state["intent"] = {"action": name, "request": copy.deepcopy(request)}
        if before is not None:
            state["intent"]["before"] = before
        try:
            save()  # Durable intent before one dispatch.
            result = call(name, "papyrus", request)
            state["intent"]["nativeResult"] = result
            validate(result)
            save()  # Persist the raw completed reply before clearing intent.
            state["lastCompletedMutation"] = {
                key: copy.deepcopy(value) for key, value in state["intent"].items() if key != "before"}
            if before is not None:
                state["lastCompletedMutation"]["beforeSample"] = before["sampleId"]
            state["intent"] = None
            save()
        except BaseException as error:
            remember_failure(error)
            raise
        checkpoint()
        return result

    def require_none(result, message):
        probe.require(completed_native(result, "none"), message)

    query = {"kind": "world_observer", "refs": [reference], "actors": True,
             "nodes": [{"ref": reference, "name": name, "firstPerson": False} for name in probe.node_names(sex)]}

    def observe(name):
        nonlocal previous
        raw = call(name, "inspect", query)
        try:
            value = snapshot(raw)
            if baseline is not None:
                probe.require(value["guard"] == baseline["guard"], "Owned FSMP actor/root continuity lost")
            if previous is not None:
                probe.require(value["sample"] > previous["sample"] and value["time"] > previous["time"],
                              "Replayed/nonadvancing FSMP guard")
            previous = value
            (observations / (str(value["sample"]) + "-" + name + ".json")).write_text(
                json.dumps(raw, indent=2), encoding="utf-8")
            return raw
        except BaseException as error:
            state["lastObservation"] = raw
            remember_failure(error)
            raise

    def snapshot(raw):
        return probe.snapshot(raw, reference, sex, actor_role=actor_role)

    def toggle(action, on, names=None):
        names = list(names or probe.drivers(sex))
        before = observe(action + "-before")
        state["current"] = None  # Unknown until this unique native return is captured.
        def validate(result):
            probe.require(completed_native(result, "bool[]"),
                          "Native pulse body-state completion uncertain; do not replay")
            probe.bool_vector(result["returned"], len(names))
        result = mutate(action, {"action": "call", "script": "DynamicHDT", "function": "TogglePhysics",
            "args": [{"form": reference}, names, on], "timeoutMs": 8000}, validate, before=before)
        bits = probe.bool_vector(result["returned"], len(names))
        after = observe(action + "-after")
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
        mutate(name, {"action": "call", "script": "Utility", "function": "Wait",
                      "args": [float(seconds)], "timeoutMs": 8000},
               lambda result: require_none(result, "FSMP settle completion uncertain; do not replay"))

    def pap_receipt(name, script, function, args):
        return call(name, "papyrus", {"action": "call", "script": script, "function": function,
                                      "args": args, "timeoutMs": 8000})

    key = "CLAW.FSMPProbe." + session.state["id"] + ("." + segment if segment else "")
    anchors = OwnedAnchors(reference, sex, key, state, actor_role=actor_role,
                           observe=observe, receipt=pap_receipt, wait=wait, persist=save, strict=is_pulse,
                           on_quarantine=quarantine)
    apply_anchors = anchors.apply

    primary = None
    result = None
    try:
        raw = observe("baseline")
        baseline = snapshot(raw)
        state["baseline"] = raw
        plan = (pulse.prepare(reference, sex, baseline["position"], actor_role=actor_role) if is_pulse
                else probe.prepare(reference, sex, baseline["position"]))
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
            stimulus_baseline = snapshot(raw)
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
                    probe.anchor_excitation(snapshot(raw), stimulus_baseline, sex, offset)
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
                    mutate(phase + "-position-" + str(index), point["steps"][0]["args"],
                           lambda result: require_none(result, "Reference position completion uncertain"))
                wait(.2, phase + "-wait-" + str(index))
                raw = observe(phase + "-sample-" + str(index))
                state["windows"][phase].append(raw)
                state["intent"] = None
                save()
                observed = snapshot(raw)
                if stimulus == "xml-anchors":
                    probe.anchor_excitation(observed, stimulus_baseline, sex, probe.anchor_offset(index))
                else:
                    probe.reference_excitation(observed, baseline, point["expectedPosition"])
        diagnostic = (pulse.score if is_pulse else probe.score)(state)
        (output / "diagnostic.json").write_text(json.dumps(diagnostic, indent=2), encoding="utf-8")
        session.state["checks"].append({"name": "fsmp-previous-state-protocol" + (":" + segment if segment else ""),
                                         "reference": reference, "actorRole": actor_role, "result": "passed",
                                         "observation": diagnostic})
        save()
        result = diagnostic
    except BaseException as error:
        primary = error
        state["primaryError"] = type(error).__name__ + ": " + str(error)
        if not isinstance(error, Exception) or isinstance(error, OSError):
            remember_failure(error)
    finally:
        cleaning = True
        cleanup = {"physics": "no-known-restore-needed", "position": "not-admitted"}
        if is_anchor:
            cleanup["position"] = "not-mutated-by-anchor-probe"
        errors = []
        cleanup_interrupt = None
        try:
            if baseline is not None and not state["quarantined"] and state["original"] is not None and state["current"] is not None:
                names = [name for name, old, now in zip(probe.drivers(sex), state["original"], state["current"]) if old and not now]
                if names:
                    probe.require(toggle("cleanup", True, names) == [False]*len(names), "Known-state cleanup mismatch")
                    cleanup["physics"] = "originally-true-only-restored"
            elif state["quarantined"]:
                cleanup["physics"] = "unknown-no-replay; owned game teardown required"
        except BaseException as error:
            if not isinstance(error, Exception):
                remember_failure(error)
                cleanup_interrupt = error
            errors.append("physics: " + type(error).__name__ + ": " + str(error))
        if state["anchorOriginals"] and not state["quarantined"]:
            try:
                cleanup["anchors"], anchor_errors = anchors.restore()
                errors.extend(anchor_errors)
            except BaseException as error:
                remember_failure(error)
                errors.append("anchors: " + type(error).__name__ + ": " + str(error))
                if not isinstance(error, Exception):
                    cleanup_interrupt = cleanup_interrupt or error
        try:
            if not state["quarantined"] and baseline is not None and stimulus == "reference" and end - time.monotonic() > 5:
                observe("cleanup-position-guard")
                mutate("cleanup-position", {"action": "call", "script": "ObjectReference", "function": "SetPosition",
                    "self": {"form": reference}, "args": baseline["position"], "timeoutMs": 8000},
                    lambda result: require_none(result, "Cleanup position completion uncertain"))
                wait(.2, "cleanup-position-wait")
                actual = snapshot(observe("cleanup-position-readback"))["position"]
                probe.require(probe.max_delta(actual, baseline["position"]) <= .025, "Original position restore not observed")
                cleanup["position"] = "observed-original-origin"
        except BaseException as error:
            if not isinstance(error, Exception):
                remember_failure(error)
                cleanup_interrupt = cleanup_interrupt or error
            errors.append("position: " + type(error).__name__ + ": " + str(error))
        cleanup["errors"] = errors
        cleanup["primaryError"] = state.get("primaryError")
        cleanup["quarantined"] = state["quarantined"]
        cleanup["outerDisposalPermitted"] = not state["quarantined"]
        try:
            (output / "cleanup.json").write_text(json.dumps(cleanup, indent=2), encoding="utf-8")
            save(full=True)
        except BaseException as error:
            remember_failure(error)
            if not isinstance(error, Exception):
                cleanup_interrupt = cleanup_interrupt or error
            errors.append("cleanup evidence: " + type(error).__name__ + ": " + str(error))
        if primary is not None:
            if errors and hasattr(primary, "add_note"):
                primary.add_note("FSMP cleanup: " + "; ".join(errors))
            raise primary
        if cleanup_interrupt is not None:
            raise cleanup_interrupt
        if errors:
            raise ValueError("; ".join(errors))
    return result
