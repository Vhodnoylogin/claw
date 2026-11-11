"""One provider-specific test callback inside an already owned Autotest Session.

The external harness supplies machine paths/profile and invokes this callback
after the ordinary fixture scenario. This module does not launch or install.
"""
import json
from pathlib import Path
import time

import fsmp_probe as probe


def run(session, reference, sex, *, maximum_seconds=160):
    probe.require(type(maximum_seconds) in (int, float) and 30 <= maximum_seconds <= 180,
                  "FSMP callback requires a finite 30..180-second bound")
    end = time.monotonic() + maximum_seconds
    output = session.dir / "fsmp-probe"
    output.mkdir(exist_ok=False)
    state = {"reference": reference, "sex": sex, "receipts": {}, "windows": {},
             "original": None, "current": None, "uncertain": False, "intent": None}
    baseline = previous = None
    cleaning = False

    def save():
        (output / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
        session.state["fsmpProbe"] = {"directory": str(output), "intent": state["intent"],
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
        for phase in probe.PHASES:
            if phase == "stopped":
                probe.require(toggle("second-off", False) == [True]*expected, "Second off state mismatch")
            elif phase == "restarted":
                probe.require(toggle("restore", True) == [False]*expected, "Restore state mismatch")
            wait(2., phase + "-settle")
            state["windows"][phase] = []
            for index, point in enumerate(plan["windows"][phase]):
                observe(phase + "-guard-" + str(index))
                state["intent"] = {"action": "position", "expectedPosition": point["expectedPosition"]}
                save()
                call(phase + "-position-" + str(index), "papyrus", point["steps"][0]["args"])
                wait(.2, phase + "-wait-" + str(index))
                raw = observe(phase + "-sample-" + str(index))
                actual = probe.snapshot(raw, reference, sex)["position"]
                probe.require(probe.max_delta(actual, point["expectedPosition"]) <= .025, "Position readback mismatch")
                state["windows"][phase].append(raw)
                state["intent"] = None
                save()
        diagnostic = probe.score(state)
        (output / "diagnostic.json").write_text(json.dumps(diagnostic, indent=2), encoding="utf-8")
        session.state["checks"].append({"name": "fsmp-previous-state-protocol", "result": "passed",
                                         "observation": diagnostic})
        session.save()
        return diagnostic
    finally:
        cleaning = True
        cleanup = {"physics": "no-known-restore-needed", "position": "not-admitted"}
        try:
            if baseline is not None and not state["uncertain"] and state["original"] is not None and state["current"] is not None:
                names = [name for name, old, now in zip(probe.drivers(sex), state["original"], state["current"]) if old and not now]
                if names:
                    probe.require(toggle("cleanup", True, names) == [False]*len(names), "Known-state cleanup mismatch")
                    cleanup["physics"] = "originally-true-only-restored"
            elif state["uncertain"]:
                cleanup["physics"] = "unknown-no-replay; owned game teardown required"
            if baseline is not None and end - time.monotonic() > 5:
                observe("cleanup-position-guard")
                call("cleanup-position", "papyrus", {"action": "call", "script": "ObjectReference", "function": "SetPosition",
                    "self": {"form": reference}, "args": baseline["position"], "timeoutMs": 8000})
                wait(.2, "cleanup-position-wait")
                actual = probe.snapshot(observe("cleanup-position-readback"), reference, sex)["position"]
                probe.require(probe.max_delta(actual, baseline["position"]) <= .025, "Original position restore not observed")
                cleanup["position"] = "observed-original-origin"
        except Exception as error:
            cleanup["error"] = str(error)
            raise
        finally:
            (output / "cleanup.json").write_text(json.dumps(cleanup, indent=2), encoding="utf-8")
            save()
