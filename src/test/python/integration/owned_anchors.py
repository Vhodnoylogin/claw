"""Provider-neutral run-key anchor operations for owned disposable fixtures.

No launch, provider toggles or binding-state inference. The caller supplies its
guarded observation, native transport, finite wait and durable journal boundary.
"""
import copy
import json
import math
import re
import time

import fsmp_probe as scene
import fsmp_pulse as pulse


def next_sample_time(start, index, period, minimum_gap, last_completed=None):
    target = start + index*period
    return target if last_completed is None else max(target, last_completed + minimum_gap)


def evidence_subdir(kind, segment=None):
    scene.require(kind in ("fsmp-probe", "cbpc-probe"), "Unknown owned probe evidence kind")
    if segment is None:
        return kind
    scene.require(type(segment) is str and re.fullmatch(r"[a-z][a-z0-9-]{0,47}", segment) is not None,
                  "Invalid finite probe segment identifier")
    return kind + "/" + segment


def dispose_fixture(session, reference, sex, admitted, *, maximum_seconds=8, sleep=time.sleep,
                    output_subdir="fsmp-probe", segment=None):
    """Disable only the admitted disposable actor, then verify world/crosshair release."""
    scene.form(reference)  # Hard player refusal before any file, transport or Disable.
    scene.require(type(maximum_seconds) in (int, float) and math.isfinite(maximum_seconds) and 1 <= maximum_seconds <= 15,
                  "Owned fixture disposal requires a finite 1..15-second bound")
    expected = scene.snapshot(admitted, reference, sex)
    end = time.monotonic() + maximum_seconds
    output_subdir = evidence_subdir(output_subdir, segment)
    output = session.dir / output_subdir / "fixture-disposal.json"
    record = {"reference": reference, "intent": None, "observations": []}

    def save():
        output.write_text(json.dumps(record, indent=2), encoding="utf-8")

    def call(tool, args):
        remaining = end - time.monotonic()
        scene.require(remaining > 0, "Owned fixture disposal deadline exhausted")
        session.phase(output_subdir + ": dispose-fixture", remaining + 1)
        return session.tool(tool, args, timeout=min(remaining, 5), deadline=end)

    query = {"kind": "world_observer", "refs": [reference], "actors": True,
             "nodes": [{"ref": reference, "name": name, "firstPerson": False} for name in scene.node_names(sex)]}
    before = call("inspect", query)
    current = scene.snapshot(before, reference, sex)
    record["before"] = before
    save()
    scene.require(current["guard"] == expected["guard"], "Owned fixture changed before disposal")
    scene.require(current["sample"] > expected["sample"] and current["time"] > expected["time"],
                  "Owned fixture disposal precondition was replayed")
    record["intent"] = {"script": "ObjectReference", "function": "Disable", "self": {"form": reference}, "args": [False]}
    save()  # A unique void-call intent; no mutation replay after an uncertain result.
    record["receipt"] = call("papyrus", {"action": "call", **record["intent"], "timeoutMs": 5000})
    save()
    receipt = record["receipt"]
    scene.require(receipt.get("called") is True and receipt.get("returnedType") == "none" and
                  "returned" in receipt and receipt["returned"] is None and not receipt.get("error"),
                  "Owned fixture Disable completion uncertain; do not replay")
    last_sample, last_time = current["sample"], current["time"]
    while time.monotonic() < end:
        raw = call("inspect", {"kind": "world_observer", "refs": [reference], "actors": True})
        rows = raw.get("refs", [])
        scene.require(raw.get("ok") is True and raw.get("quality") == "complete" and len(rows) == 1 and
                      raw.get("sessionId") == before["sessionId"] and raw.get("loadGeneration") == before["loadGeneration"] and
                      raw.get("sampleId", 0) > last_sample and raw.get("producerMonotonicNs", 0) > last_time,
                      "Owned fixture disposal observation lost continuity")
        row = rows[0]
        scene.require(row.get("identity") == before["refs"][0]["identity"] and
                      row.get("baseForm") == before["refs"][0]["baseForm"] and row.get("deleted") is False,
                      "Owned fixture identity changed during disposal")
        last_sample, last_time = raw["sampleId"], raw["producerMonotonicNs"]
        crosshair = call("papyrus", {"action": "call", "script": "Game", "function": "GetCurrentCrosshairRef", "args": []})
        record["observations"].append({"world": raw, "crosshair": crosshair})
        save()
        scene.require(crosshair.get("called") is True and "returned" in crosshair and not crosshair.get("error"),
                      "Crosshair readback value unavailable")
        if crosshair["returned"] is None:
            scene.require(crosshair.get("returnedType") == "none", "Crosshair null result type unavailable")
        if row.get("disabled") is True and crosshair["returned"] is None:
            record["verifiedDisabledAndCrosshairReleased"] = True
            save()
            return record
        sleep(.1)
    raise ValueError("Owned fixture disabled/null-crosshair readback not observed")


class OwnedAnchors:
    def __init__(self, reference, sex, key, state, *, observe, receipt, wait, persist, strict=False,
                 actor_role="disposable-npc"):
        self.reference, self.sex = scene.actor_reference(reference, actor_role), sex
        self.actor_role = actor_role
        self.names = tuple(dict.fromkeys(scene.anchors(sex).values()))
        scene.require(type(key) is str and key.startswith("CLAW.FSMPProbe.") and len(key) > len("CLAW.FSMPProbe."),
                      "Explicit run-owned anchor key required")
        self.key, self.state, self.strict = key, state, strict
        self.observe, self.receipt, self.wait, self.persist = observe, receipt, wait, persist
        self.originals = state.setdefault("anchorOriginals", {})

    def _snapshot(self, raw):
        return scene.snapshot(raw, self.reference, self.sex, actor_role=self.actor_role)

    def _args(self, name):
        scene.require(name in self.names, "Only declared mass-zero anchors may be written")
        return [{"form": self.reference}, False, self.sex == "female", name]

    def _read(self, label, script, function, args):
        result = self.receipt(label, script, function, args)
        if self.strict:
            scene.require(type(result) is dict and result.get("called") is True and
                          "returned" in result and not result.get("error"), "Anchor read unavailable")
        return result["returned"]

    def _mutate(self, label, script, function, args, returned_type):
        before = self.observe(label + "-guard")
        self.state["intent"] = {"action": "anchor", "script": script, "function": function,
                                "args": args, "before": before}
        self.persist()
        try:
            result = self.receipt(label, script, function, args)
            self.state["intent"]["nativeResult"] = result
            self.persist()
            if self.strict:
                scene.require(type(result) is dict and result.get("called") is True and "returned" in result and
                              result.get("returnedType") == returned_type and not result.get("error") and
                              (result["returned"] is None if returned_type == "none" else type(result["returned"]) is bool),
                              "Anchor pulse write completion uncertain; do not replay")
        except Exception:
            self.state.setdefault("uncertainAnchorWrites", []).append(copy.deepcopy(self.state["intent"]))
            self.persist()
            raise
        self.state["intent"] = None
        self.persist()
        return result

    def capture(self):
        for name in self.names:
            current = self._snapshot(self.observe("anchor-original-" + name))
            keys = self._read("anchor-original-keys-" + name, "NiOverride", "GetNodeTransformKeys", self._args(name))
            scene.require(keys == [], "Fresh anchor has external transform keys; do not recompose them")
            exists = self._read("anchor-own-key-absent-" + name, "NiOverride", "HasNodeTransformPosition", self._args(name) + [self.key])
            scene.require(exists is False, "Own anchor key already exists")
            self.originals[name] = {"key": self.key, "keysBefore": keys,
                                    "local": current["nodes"][name]["local"], "world": current["nodes"][name]["world"]}
            self.persist()

    def apply(self, offset, names=None):
        offset = scene.numbers(offset, 3)
        commands = []
        for name in self.names if names is None else names:
            scene.require(name in self.originals, "Anchor was not captured")
            args = self._args(name) + [self.key]
            for function, values in (("AddNodeTransformPosition", args + [offset]), ("UpdateNodeTransform", self._args(name))):
                result = self._mutate("anchor-" + function + "-" + name, "NiOverride", function, values, "none")
                commands.append({"script": "NiOverride", "function": function, "args": values, "nativeResult": result})
                if function == "AddNodeTransformPosition":
                    value = self._read("anchor-storage-" + name, "NiOverride", "GetNodeTransformPosition", args)
                    scene.require(scene.max_delta(scene.numbers(value, 3), offset) <= 1e-6, "Own anchor key storage mismatch")
        return commands

    def collect_phase(self, phase, spec, baseline, *, sleep=time.sleep, clock=time.perf_counter):
        rows = self.state["pulses"][phase] = {}
        for name in self.names:
            row = rows[name] = {"commands": {}, "samples": []}
            row["beforePulse"] = self.observe(phase + "-before-pulse-" + name)
            pulse.anchor_excitation(self._snapshot(row["beforePulse"]), baseline, self.sex, name, [0., 0., 0.])
            row["commands"]["moved"] = self.apply(pulse.offset(name), (name,))
            row["moved"] = self.observe(phase + "-pulse-moved-" + name)
            pulse.anchor_excitation(self._snapshot(row["moved"]), baseline, self.sex, name, pulse.offset(name))
            self.persist()
            sleep(spec["holdSeconds"])
            row["commands"]["returned"] = self.apply([0., 0., 0.], (name,))
            row["returned"] = self.observe(phase + "-pulse-returned-" + name)
            pulse.anchor_excitation(self._snapshot(row["returned"]), baseline, self.sex, name, [0., 0., 0.])
            self.persist()
            # Windows Python 3.12 monotonic uses the coarse GetTickCount64.
            # QPC schedules samples; lifecycle deadlines retain their own clock.
            started, completed = clock(), None
            for index in range(spec["samples"]):
                at = next_sample_time(started, index, spec["samplePeriodSeconds"], spec["minGapSeconds"], completed)
                sleep(max(0., at - clock()))
                row["samples"].append(self.observe(phase + "-pulse-sample-" + name + "-" + str(index)))
                completed = clock()
                self.persist()
        return rows

    def restore(self):
        restored, errors = {}, []
        for name, original in self.originals.items():
            try:
                self.observe("cleanup-anchor-guard-" + name)
                args = self._args(name) + [self.key]
                keys = self._read("cleanup-anchor-keys-" + name, "NiOverride", "GetNodeTransformKeys", self._args(name))
                scene.require(set(keys) <= {self.key}, "New foreign anchor key; do not overwrite its transform")
                if self._read("cleanup-anchor-has-" + name, "NiOverride", "HasNodeTransformPosition", args):
                    result = self._mutate("cleanup-anchor-remove-" + name, "NiOverride", "RemoveNodeTransformPosition", args, "bool")
                    scene.require(result["returned"] is True, "Own anchor position component removal failed")
                    self._mutate("cleanup-anchor-apply-" + name, "NiOverride", "UpdateNodeTransform", self._args(name), "none")
                # SKEE's cached rest pose can differ from the captured pose.
                # Restore that complete local pose after removing only our key.
                for function, channel, kind in (("SetNodeLocalPosition", "translation", "bool"),
                                                ("SetNodeLocalRotationMatrix", "rotationRowMajor", "bool"),
                                                ("SetNodeScale", "scale", "none")):
                    result = self._mutate("cleanup-" + function + "-" + name, "NetImmerse", function,
                                         [{"form": self.reference}, name, original["local"][channel], False], kind)
                    if kind == "bool":
                        scene.require(result["returned"] is True, "Anchor local restore not accepted")
                self.wait(.2, "cleanup-anchor-wait-" + name)
                current = self._snapshot(self.observe("cleanup-anchor-readback-" + name))
                for channel, floor in scene.FLOORS.items():
                    scene.require(scene.max_delta(current["nodes"][name]["local"][channel], original["local"][channel]) <= max(floor, .001),
                                  "Original anchor local transform not restored")
                scene.require(abs(current["nodes"][name]["local"]["scale"] - original["local"]["scale"]) <= 1e-5,
                              "Original anchor scale not restored")
                # HasPosition can remain true for an empty SKEE key container.
                result = self._mutate("cleanup-anchor-component-absent-" + name, "NiOverride", "RemoveNodeTransformPosition", args, "bool")
                scene.require(result["returned"] is False, "Own anchor position component still existed")
                container = self._read("cleanup-anchor-container-" + name, "NiOverride", "HasNodeTransformPosition", args)
                restored[name] = {"ownPositionComponentAbsent": True, "originalLocalReadback": current["nodes"][name]["local"],
                                  "hasKeyContainerAfterRemoval": container, "emptyKeyContainerMayRemain": True}
            except Exception as error:
                restored[name] = {"error": str(error)}
                errors.append(name + ": " + str(error))
        return restored, errors
