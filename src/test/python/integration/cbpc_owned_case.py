"""Node-scoped CBPC pulse transport inside an already owned disposable Session.

The caller qualifies a fresh born-beast fixture/resources and owns launch,
provider installation and final fixture disposal. Void controls never establish
binding, previous state or authority for compensating provider mutations.
"""
import json
import math
import time

import cbpc_probe as cbpc
import cbpc_pulse as probe
import fsmp_probe as scene
import fsmp_pulse as pulse
from owned_anchors import OwnedAnchors, dispose_fixture as _dispose_fixture


def dispose_fixture(session, reference, sex, admitted, **kwargs):
    """Disable only the guarded fixture; never reset unknown CBPC state."""
    return _dispose_fixture(session, reference, sex, admitted, output_subdir="cbpc-probe", **kwargs)


def run(session, reference, sex, *, maximum_seconds=160, sleep=time.sleep):
    scene.require(type(maximum_seconds) in (int, float) and math.isfinite(maximum_seconds) and
                  30 <= maximum_seconds <= 180, "CBPC callback requires a finite 30..180-second bound")
    plan = probe.prepare(reference, sex)
    reference = plan["reference"]
    end = time.monotonic() + maximum_seconds
    output = session.dir / "cbpc-probe"
    output.mkdir(exist_ok=False)
    observations = output / "observations"
    observations.mkdir()
    state = {key: plan[key] for key in ("schemaVersion", "reference", "sex", "protocol", "stimulus",
                                      "skeletonSha256", "parentPaths")}
    state.update(receipts={}, pulses={}, anchorOriginals={}, intent=None, attemptedNodeCalls=[],
                 bindingState="unknown", providerOriginalState="unknown", providerRestorationClaimed=False,
                 uncertain=False, freshBornBeastRequired=True)
    baseline = previous = None
    cleaning = False

    def save(*, full=False):
        journal = {key: value for key, value in state.items() if key not in
                   ("baseline", "stimulusBaseline", "pulses", "receipts", "intent")}
        journal["pulses"] = {phase: {name: {
            **{side: row[side]["sampleId"] for side in ("beforePulse", "moved", "returned") if side in row},
            "samples": [sample["sampleId"] for sample in row.get("samples", [])], "commands": row["commands"]}
            for name, row in rows.items()} for phase, rows in state["pulses"].items()}
        journal["receipts"] = {action: [{key: value for key, value in receipt.items() if key not in ("before", "after")}
            | {side + "Sample": receipt[side]["sampleId"] for side in ("before", "after")} for receipt in receipts]
            for action, receipts in state["receipts"].items()}
        intent = state["intent"]
        journal["intent"] = ({key: value for key, value in intent.items() if key != "before"}
            | ({"beforeSample": intent["before"]["sampleId"]} if "before" in intent else {})) if intent else None
        (output / "journal.json").write_text(json.dumps(journal, indent=2), encoding="utf-8")
        if full:
            (output / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
        session.state["cbpcProbe"] = {"directory": str(output), "intent": journal["intent"],
                                       "uncertain": state["uncertain"], "bindingState": "unknown"}
        session.save()

    def call(name, tool, args):
        remaining = end - (0 if cleaning else 20) - time.monotonic()
        scene.require(remaining > 0, "Finite CBPC case deadline exhausted")
        session.phase("cbpc: " + name, min(remaining, 12) + 2)
        return session.tool(tool, args, timeout=min(remaining, 10), deadline=end)

    def observe(name):
        nonlocal previous
        raw = call(name, "inspect", plan["query"])
        value = scene.snapshot(raw, reference, sex)
        if baseline is not None:
            scene.require(value["guard"] == baseline["guard"], "Owned CBPC actor/root continuity lost")
        if previous is not None:
            scene.require(value["sample"] > previous["sample"] and value["time"] > previous["time"],
                          "Replayed/nonadvancing CBPC guard")
        previous = value
        (observations / (str(value["sample"]) + "-" + name + ".json")).write_text(json.dumps(raw, indent=2), encoding="utf-8")
        return raw

    def receipt(name, script, function, args):
        return call(name, "papyrus", {"action": "call", "script": script, "function": function,
                                      "args": args, "timeoutMs": 8000})

    def wait(seconds, name):
        result = receipt(name, "Utility", "Wait", [float(seconds)])
        scene.require(pulse._completed_none(result), "CBPC settle completion uncertain")

    def transition(action):
        scene.require(action not in state["receipts"], "One-shot CBPC transition already attempted")
        state["receipts"][action] = []
        for request in plan["calls"][action]:
            before = observe(action + "-before-" + request["args"][1])
            state["intent"] = {"action": action, "request": request, "before": before}
            state["attemptedNodeCalls"].append({"action": action, "request": request})
            save()
            try:
                native = call(action + "-" + request["args"][1], "papyrus", request)
                state["intent"]["nativeResult"] = native
                save()
                result = {"request": request, "nativeResult": native}
                cbpc.completed(result, request)
                result.update(before=before, after=observe(action + "-after-" + request["args"][1]))
            except Exception as error:
                state["uncertain"] = True
                state["uncertainProviderCall"] = {"action": action, "request": request,
                    "beforeSample": before["sampleId"], "nativeResult": state["intent"].get("nativeResult"),
                    "errorType": type(error).__name__, "error": str(error)}
                save()
                raise
            state["receipts"][action].append(result)
            state["intent"] = None
            save()

    anchors = OwnedAnchors(reference, sex, "CLAW.FSMPProbe." + session.state["id"], state,
                           observe=observe, receipt=receipt, wait=wait, persist=save, strict=True)
    try:
        raw = observe("baseline")
        baseline = scene.snapshot(raw, reference, sex)
        actor = baseline["guard"]["actor"]
        scene.require(all(isinstance(actor.get(key), str) and actor[key].lower() == "0x000cdd84"
                          for key in ("race", "baseRace")), "Fresh owned born-beast fixture required")
        state["baseline"] = raw
        (output / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
        save()
        transition("start")
        anchors.capture()
        anchors.apply([0., 0., 0.])
        wait(2., "anchor-prime-settle")
        raw = observe("stimulus-baseline")
        primed = scene.snapshot(raw, reference, sex)
        state["stimulusBaseline"] = raw
        save()
        for phase, action in zip(scene.PHASES, (None, "stop", "restart")):
            if action:
                transition(action)
            wait(2., phase + "-settle")
            anchors.collect_phase(phase, state["protocol"], primed, sleep=sleep)
        diagnostic = probe.score(state)
        (output / "diagnostic.json").write_text(json.dumps(diagnostic, indent=2), encoding="utf-8")
        session.state["checks"].append({"name": "cbpc-node-scoped-pulse-protocol", "result": "passed", "observation": diagnostic})
        session.save()
        return diagnostic
    except Exception as error:
        state["primaryError"] = str(error)
        raise
    finally:
        cleaning = True
        # No compensating Start/Stop: even successful void returns do not reveal
        # original state. Only exact run-owned anchor data may be cleaned here.
        restored, errors = anchors.restore()
        cleanup = {"anchors": restored, "errors": errors, "primaryError": state.get("primaryError"),
                   "providerState": "unknown", "providerRestorationClaimed": False,
                   "providerCleanupCalls": [], "fixtureDisposalRequired": True}
        (output / "cleanup.json").write_text(json.dumps(cleanup, indent=2), encoding="utf-8")
        save(full=True)
        if errors:
            raise ValueError("; ".join((["primary: " + state["primaryError"]] if state.get("primaryError") else []) + errors))
