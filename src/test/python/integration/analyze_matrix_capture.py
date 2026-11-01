"""Inspect captured SKEE storage using the pinned native matrix CLI.

This reads retained files only. It neither connects to Skyrim nor implements
matrix arithmetic. Global own-key absence needs the complete namespace wire
contract; no report qualifies the collector, rendering or physics independently.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys

SHA256 = re.compile(r"[0-9a-f]{64}\Z")
STAGES = {"linked-beast", "human-own-clear", "suppressed-own-clear"}
ASCII_FOLD = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def read_json(path):
    def nonfinite(value):
        raise ValueError("Nonfinite JSON value: " + value)
    return json.loads(Path(path).read_bytes(), object_pairs_hook=_object_pairs,
                      parse_constant=nonfinite)


def number(value):
    if type(value) not in (int, float):
        raise ValueError("Finite numeric observation required")
    try:
        if not math.isfinite(value):
            raise ValueError("Nonfinite numeric observation")
    except OverflowError as error:
        raise ValueError("Numeric observation exceeds finite range") from error
    return value


def identifier(value, *, morph=True):
    if (not isinstance(value, str) or not value or value != value.strip() or
            len(value.encode("utf-8")) > (160 if morph else 128) or
            any(ord(char) < 32 or ord(char) > 126 for char in value)):
        raise ValueError("Bounded printable identifier required: " + repr(value))
    return value


def identity(value):
    # SKEE's supported ASCII provider identity; preserve authored spelling in output.
    return value.translate(ASCII_FOLD)


def named_map(value, label):
    if not isinstance(value, dict) or len(value) > 4096:
        raise ValueError(label + ": bounded object required")
    result = {}
    for name, entry in value.items():
        folded = identity(identifier(name))
        if folded in result:
            raise ValueError(label + ": ambiguous case aliases")
        result[folded] = (name, entry)
    return result


def observed(value, label):
    if (not isinstance(value, dict) or value.get("available") is not True or
            type(value.get("present")) is not bool):
        raise ValueError(label + ": availability/presence unavailable")
    number(value.get("value"))
    if not value["present"] and value["value"] != 0:
        raise ValueError(label + ": absent entry has a nonzero value")
    return {"present": value["present"], "value": value["value"]}


def key_map(value, label):
    if not isinstance(value, list) or len(value) > 4096:
        raise ValueError(label + ": full bounded key enumeration required")
    result = {}
    for entry in value:
        if not isinstance(entry, dict):
            raise ValueError(label + ": key record required")
        name = identifier(entry.get("key"), morph=False)
        folded = identity(name)
        if folded in result:
            raise ValueError(label + ": duplicate/ambiguous provider key")
        result[folded] = {"name": name, **observed(entry, label + "/" + name)}
    return result


def unwrap(value):
    raw = value.get("raw", value) if isinstance(value, dict) else None
    if not isinstance(raw, dict):
        raise ValueError("Captured raw object required")
    return raw


def checked_namespace(value):
    """Consume the qualified VisitMorphValues wire contract, not target guesses."""
    if (not isinstance(value, dict) or value.get("method") != "VisitMorphValues" or
            value.get("scope") != "stored_morph_key_values" or value.get("status") != "available"):
        raise ValueError("Full namespace method/scope/status unavailable")
    for flag in ("complete", "providerTraversalCompleted", "contextGuardProvided", "contextCurrent"):
        if value.get(flag) is not True:
            raise ValueError("Full namespace completeness/context flag unavailable: " + flag)
    for flag in ("truncated", "invalidMorph", "invalidKey", "invalidActor", "nonFinite", "captureFailure",
                 "aliasAmbiguous", "duplicatePair", "identityUnsupported"):
        if value.get(flag) is not False:
            raise ValueError("Full namespace cannot prove completeness: " + flag)
    entries = value.get("entries")
    if (not isinstance(entries, list) or len(entries) > 4096 or
            type(value.get("callbackCount")) is not int or type(value.get("retainedCount")) is not int or
            value["callbackCount"] != len(entries) or value["retainedCount"] != len(entries)):
        raise ValueError("Full namespace callback/retention counts disagree")
    start, finish = value.get("startedMonotonicNs"), value.get("finishedMonotonicNs")
    if type(start) is not int or type(finish) is not int or not 0 <= start <= finish:
        raise ValueError("Full namespace interval is unavailable")
    result = {}
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("status") != "available":
            raise ValueError("Unavailable full namespace tuple")
        morph, key = identifier(entry.get("morph")), identifier(entry.get("key"), morph=False)
        folded, folded_key = identity(morph), identity(key)
        if folded in result and result[folded]["name"] != morph:
            raise ValueError("Full namespace ambiguous morph case alias")
        row = result.setdefault(folded, {"name": morph, "keys": {}})
        if folded_key in row["keys"]:
            raise ValueError("Duplicate/ambiguous full namespace tuple")
        row["keys"][folded_key] = {"name": key, "present": True, "value": number(entry.get("value"))}
    if len(result) > 512:
        raise ValueError("Full namespace distinct-morph bound exceeded")
    return result


def captured_reference(raw):
    context = raw.get("identity", {})
    if not isinstance(context, dict) or not isinstance(context.get("identity", {}), dict):
        raise ValueError("Captured identity object unavailable")
    nested = context.get("identity", {}).get("form")
    direct = raw.get("reference")
    for value in (direct, nested):
        if value is not None:
            identifier(value)
    if direct is not None and nested is not None and identity(direct) != identity(nested):
        raise ValueError("Captured reference witnesses disagree")
    return direct if direct is not None else nested


def actor_weight_witness(raw, *, required=False):
    """Read the independent observer actor sample, never a SKEE pseudo-morph."""
    context = raw.get("identity", {})
    actor = context.get("actor", {}) if isinstance(context, dict) else {}
    weight = actor.get("weight") if isinstance(actor, dict) else None
    if weight is None:
        if required:
            raise ValueError("Actor weight unavailable: independent identity.actor.weight witness required")
        return None
    if (not isinstance(weight, dict) or weight.get("status") != "available" or
            not isinstance(context.get("sessionId"), str) or not context["sessionId"] or
            type(context.get("loadGeneration")) is not int or context["loadGeneration"] < 0 or
            not isinstance(context.get("identity"), dict) or
            not isinstance(context["identity"].get("form"), str) or
            captured_reference(raw) is None):
        raise ValueError("Actor weight unavailable: observed actor/session/world identity required")
    value = number(weight.get("rawNPCWeight"))
    # The native captureActor path owns float32/raw-domain validation and /100.
    # Convenience fields from the existing collector must agree with its sample.
    if "weightRaw" in raw and number(raw["weightRaw"]) != value:
        raise ValueError("Actor raw weight convenience value disagrees with independent witness")
    if "weightNormalized" in raw:
        if number(raw["weightNormalized"]) != number(weight.get("normalizedNPCWeight")):
            raise ValueError("Actor normalized weight convenience value disagrees with independent witness")
    return {"rawNPCWeight": value, "source": "identity.actor.weight",
            "reference": context["identity"]["form"], "sessionId": context["sessionId"],
            "loadGeneration": context["loadGeneration"]}


def normalize(raw):
    raw = unwrap(raw)
    stage = raw.get("stage")
    if stage not in STAGES:
        raise ValueError("Unknown captured lifecycle stage")
    own_key = identity(identifier(raw.get("ownKey"), morph=False))
    sources, own = {}, {}
    source_names = named_map(raw.get("sources"), "sources")
    own_names = named_map(raw.get("own"), "own")
    targets = named_map(raw.get("targetKeys"), "targetKeys")
    if set(own_names) != set(targets):
        raise ValueError("Own observations and target key enumerations differ")
    for folded, (name, entry) in source_names.items():
        scalar = observed(entry, "source/" + name)
        keys = key_map(entry.get("keys"), "source keys/" + name)
        # HasBodyMorphName reports the name bucket, which ClearMorph can leave
        # behind after removing its final key. A present, keyless bucket is not
        # an absent name. Only the reverse contradiction is invalid.
        if not scalar["present"] and any(key["present"] for key in keys.values()):
            raise ValueError("Absent source has stored provider keys: " + name)
        if keys.get(own_key, {}).get("present") is True:
            raise ValueError("CLAW-owned input feedback observed: " + name)
        sources[folded] = {"name": name, **scalar, "keys": keys}
    for folded, (name, entry) in own_names.items():
        scalar = observed(entry, "own/" + name)
        keys = key_map(targets[folded][1], "target keys/" + name)
        stored = keys.get(own_key, {"present": False, "value": 0})
        if scalar["present"] != stored["present"] or scalar["value"] != stored["value"]:
            raise ValueError("Own scalar disagrees with independent key enumeration: " + name)
        own[folded] = {"name": name, **scalar, "keys": keys}
    namespace = checked_namespace(raw["namespace"]) if "namespace" in raw else None
    if namespace is not None:
        for rows in (sources, own):
            for name, row in rows.items():
                stored = namespace.get(name, {"keys": {}})["keys"]
                expected = {key: value["value"] for key, value in stored.items()}
                captured = {key: value["value"] for key, value in row["keys"].items() if value["present"]}
                if expected != captured:
                    raise ValueError("Requested key list disagrees with full namespace: " + row["name"])
    return {"stage": stage, "ownKey": own_key, "sources": sources, "own": own, "namespace": namespace,
            "actorWeight": actor_weight_witness(raw)}


class NativeMatrix:
    """Only the CLI executes coefficients, functions, float32 and epsilon policy."""

    def __init__(self, xml, xml_sha256, cli, cli_sha256, timeout=30):
        self.xml, self.cli = Path(xml).resolve(), Path(cli).resolve()
        self.pins = {self.xml: xml_sha256, self.cli: cli_sha256}
        self.timeout = timeout
        self.cache = {}
        self.graph_cache = {}
        self.invocations = 0
        if not 0 < timeout <= 60:
            raise ValueError("Native CLI timeout must be in (0,60] seconds")
        self.verify()
        catalog = self._run(["families", str(self.xml)])
        self.catalog = {row["id"]: row for row in catalog["profiles"]}
        if len(catalog["profiles"]) != len(self.catalog):
            raise ValueError("Ambiguous duplicate native profile ID")

    def verify(self):
        for path, expected in self.pins.items():
            if not isinstance(expected, str) or not SHA256.fullmatch(expected) or digest(path) != expected:
                raise ValueError("Pinned file mismatch: " + str(path))

    def _run(self, arguments, text=""):
        self.verify()
        process = subprocess.run([str(self.cli), *arguments], input=text, text=True,
                                 capture_output=True, timeout=self.timeout, check=False)
        self.invocations += 1
        self.verify()
        if process.returncode:
            raise ValueError("Native matrix CLI rejected input: " + process.stderr.strip())
        if len(process.stdout) > 4 * 1024 * 1024:
            raise ValueError("Native matrix response exceeds bound")
        return json.loads(process.stdout, object_pairs_hook=_object_pairs)

    def graph(self, selected):
        self.verify()
        if selected not in self.graph_cache:
            graph = self._run(["matrix-info", str(self.xml), selected])
            if (graph.get("schema") != "claw-matrix-input-graph/1" or graph.get("profile") != selected or
                    graph.get("sex") != self.catalog[selected]["sex"] or
                    not isinstance(graph.get("sources"), list) or len(graph["sources"]) > 128 or
                    not isinstance(graph.get("targets"), list) or len(graph["targets"]) > 64):
                raise ValueError("Native active input graph unavailable")
            sources = {}
            for row in graph["sources"]:
                name = identifier(row.get("name"))
                kind = row.get("kind")
                if kind not in {"skee-morph", "actor-weight"} or identity(name) in sources:
                    raise ValueError("Native input graph has unknown/ambiguous source kind")
                sources[identity(name)] = {"name": name, "kind": kind}
            targets = {identity(identifier(name)) for name in graph["targets"]}
            if len(targets) != len(graph["targets"]):
                raise ValueError("Native input graph has ambiguous target identities")
            self.graph_cache[selected] = {"sources": sources, "targets": targets}
        return self.graph_cache[selected]

    def evaluate(self, raw, profile_id=None):
        self.verify()
        values = normalize(raw)
        raw = unwrap(raw)
        selected = profile_id or raw.get("familyId")
        if selected not in self.catalog or raw.get("familyId", selected) != selected:
            raise ValueError("Captured profile is not the selected XML profile")
        if raw.get("sex") != self.catalog[selected]["sex"]:
            raise ValueError("Captured sex differs from selected profile")
        graph = self.graph(selected)
        declared_sources = {name for name, row in graph["sources"].items() if row["kind"] == "skee-morph"}
        scalar_sources = {name for name, row in graph["sources"].items() if row["kind"] == "actor-weight"}
        declared_targets = graph["targets"]
        if declared_sources - values["sources"].keys():
            raise ValueError("Missing declared source observations: " + str(sorted(declared_sources - values["sources"].keys())))
        if declared_targets - values["own"].keys():
            raise ValueError("Missing declared target observations: " + str(sorted(declared_targets - values["own"].keys())))
        if scalar_sources & values["sources"].keys():
            raise ValueError("Actor scalar must not be supplied as a SKEE morph/key observation")
        witness = actor_weight_witness(raw, required=True) if scalar_sources else None
        text = "".join(graph["sources"][name]["name"] + "\t" + format(values["sources"][name]["value"], ".17g") + "\n"
                       for name in sorted(declared_sources))
        arguments = ["matrix", str(self.xml), selected]
        if witness is not None:
            arguments += ["--actor-weight-raw", format(witness["rawNPCWeight"], ".17g")]
        key = selected, text, tuple(arguments[3:])
        if key not in self.cache:
            output = self._run(arguments, text)
            checked = named_map(output, "native output")
            self.cache[key] = {name: {"name": spelling, "value": number(value)}
                               for name, (spelling, value) in checked.items()}
        return selected, values, self.cache[key]


def analyze_capture(capture, evaluator, profile_id=None, tolerance=1e-4):
    if type(tolerance) not in (int, float) or not math.isfinite(tolerance) or not 0 < tolerance <= 1e-4:
        raise ValueError("Tolerance must be finite and in (0,1e-4]")
    raw = unwrap(capture)
    selected, values, kernel = evaluator.evaluate(raw, profile_id)
    errors, checked = [], []
    targets = set(values["own"]) | {name for name, row in kernel.items() if row["value"] != 0}
    for target in sorted(targets):
        expected = kernel.get(target, {}).get("value", 0) if values["stage"] == "linked-beast" else 0
        actual = values["own"].get(target)
        name = actual["name"] if actual else kernel[target]["name"]
        reason = None
        if actual is None:
            reason = "Expected nonzero output lacks an independent target observation"
        elif expected == 0 and actual["present"]:
            reason = "Own key must be absent, including zero/tiny stored entries"
        elif expected != 0 and not actual["present"]:
            reason = "Expected nonzero output key is absent"
        elif expected != 0 and actual["value"] <= 0:
            reason = "Expected nonzero output has a zero/negative stored coefficient"
        elif expected != 0 and abs(actual["value"] - expected) > tolerance:
            reason = "Stored coefficient differs from the native matrix"
        checked.append({"target": name, "expected": expected, "present": actual["present"] if actual else None,
                        "actual": actual["value"] if actual else None,
                        "absoluteError": abs(actual["value"] - expected) if actual else None})
        if reason:
            errors.append({"target": name, "error": reason})
    namespace = values["namespace"]
    namespace_own = None
    if namespace is not None:
        namespace_own = {name: row for name, row in namespace.items() if values["ownKey"] in row["keys"]}
        for name, row in namespace_own.items():
            expected = kernel.get(name, {}).get("value", 0) if values["stage"] == "linked-beast" else 0
            actual = row["keys"][values["ownKey"]]["value"]
            if expected == 0:
                errors.append({"target": row["name"], "scope": "full-namespace", "error": "Unexpected own namespace entry, including zero/tiny stored keys"})
            elif actual <= 0 or abs(actual - expected) > tolerance:
                errors.append({"target": row["name"], "scope": "full-namespace", "error": "Own namespace coefficient differs from native output"})
        if values["stage"] == "linked-beast":
            for name, row in kernel.items():
                if row["value"] != 0 and name not in namespace_own:
                    errors.append({"target": row["name"], "scope": "full-namespace", "error": "Required nonzero own namespace entry is absent"})
    return {"profile": selected, "fixtureTag": raw.get("fixtureTag"), "snapshotLabel": raw.get("snapshotLabel"),
            "reference": captured_reference(raw), "stage": values["stage"], "passed": not errors,
            "sourcesObserved": len(values["sources"]), "targetsObserved": len(values["own"]),
            "targets": checked, "errors": errors,
            "coefficientValuesWithinTolerance": all(row["absoluteError"] is not None and row["absoluteError"] <= tolerance for row in checked),
            "ownPresencePolicyPassed": all(row["present"] == (row["expected"] != 0) and
                                          (row["expected"] == 0 or row["actual"] > 0) for row in checked),
            "sourceCoveragePolicy": "Native canonical active graph; SKEE aggregates/keys and independent actor weight are separate; no copied epsilon or normalization formula",
            "actorWeightWitness": values["actorWeight"],
            "actorWeightNormalization": ("native captureActor raw NPC0..100 input"
                if any(row["kind"] == "actor-weight" for row in evaluator.graph(selected)["sources"].values())
                else "not used by this matrix"),
            "ownNamespaceCoverage": ("complete: VisitMorphValues stored keypair wire contract; producer qualification required" if namespace is not None else
                                     "unavailable: current capture enumerates keys for specified targets only"),
            "ownNamespaceEntries": ({row["name"]: row["keys"][values["ownKey"]]["value"] for row in namespace_own.values()}
                                    if namespace_own is not None else None),
            "globalOwnKeyAbsenceProven": namespace_own == {},
            "globalOwnKeySetMatchesKernel": (not any(row.get("scope") == "full-namespace" for row in errors)
                                             if namespace is not None else None),
            "renderedGeometryAccepted": False}


def _key_signature(keys, own_key):
    return {key: {"present": value["present"], "value": value["value"]}
            for key, value in keys.items() if key != own_key}


def _own_signature(rows):
    return {name: {"present": row["present"], "value": row["value"],
                   "keys": _key_signature(row["keys"], "")}
            for name, row in rows.items()}


def compare_captures(before, after):
    before, after = unwrap(before), unwrap(after)
    a, b = normalize(before), normalize(after)
    if a["ownKey"] != b["ownKey"]:
        raise ValueError("Comparison own-provider identity differs")
    for name in ("fixtureTag", "sex", "familyId"):
        if not isinstance(before.get(name), str) or before[name] != after.get(name):
            raise ValueError("Same-reference comparison witness unavailable/different: " + name)
    if (not isinstance(captured_reference(before), str) or not isinstance(captured_reference(after), str) or
            identity(captured_reference(before)) != identity(captured_reference(after))):
        raise ValueError("Same-reference comparison witness unavailable/different: reference")
    session_a = before.get("identity", {}).get("sessionId")
    session_b = after.get("identity", {}).get("sessionId")
    if session_a != session_b:
        raise ValueError("Captured native session changed")
    changed_sources, changed_foreign = [], []
    for name in sorted(set(a["sources"]) | set(b["sources"])):
        left, right = a["sources"].get(name), b["sources"].get(name)
        if (left is None or right is None or
                {key: left[key] for key in ("present", "value")} != {key: right[key] for key in ("present", "value")} or
                _key_signature(left["keys"], a["ownKey"]) != _key_signature(right["keys"], b["ownKey"])):
            changed_sources.append(name)
    for name in sorted(set(a["own"]) | set(b["own"])):
        left, right = a["own"].get(name), b["own"].get(name)
        if (left is None or right is None or
                _key_signature(left["keys"], a["ownKey"]) != _key_signature(right["keys"], b["ownKey"])):
            changed_foreign.append(name)
    global_foreign_changes = None
    if a["namespace"] is not None and b["namespace"] is not None:
        def foreign_namespace(value):
            return {name: keys for name, row in value["namespace"].items()
                    if (keys := _key_signature(row["keys"], value["ownKey"]))}
        left, right = foreign_namespace(a), foreign_namespace(b)
        global_foreign_changes = [name for name in sorted(set(left) | set(right)) if left.get(name) != right.get(name)]
    weight_a, weight_b = a["actorWeight"], b["actorWeight"]
    weight_observed = weight_a is not None and weight_b is not None
    weight_same = weight_a["rawNPCWeight"] == weight_b["rawNPCWeight"] if weight_observed else None
    weight_consistent = (weight_same is True) if weight_a is not None or weight_b is not None else True
    return {"passed": not changed_sources and not changed_foreign and not global_foreign_changes and weight_consistent,
            "sourcePreservationPassed": not changed_sources and weight_consistent, "changedSources": changed_sources,
            "actorWeightPreservationPassed": weight_same,
            "actorWeightCoverage": "same-reference independent raw NPC samples" if weight_observed else "unavailable: two independent actor-weight witnesses required",
            "foreignTargetKeyPreservationPassed": not changed_foreign, "changedForeignTargets": changed_foreign,
            "globalForeignKeyPreservationPassed": not global_foreign_changes if global_foreign_changes is not None else None,
            "changedGlobalForeignMorphs": global_foreign_changes,
            "scope": ("Supplied same-reference source/target lists and complete stored provider namespace"
                      if global_foreign_changes is not None else
                      "Supplied same-reference captured source/target lists; global provider namespace unavailable"),
            "independentSaveRemapVerification": "unavailable"}


def analyze_file(path, evaluator, *, before=None, profile_id=None, tolerance=1e-4):
    value = read_json(path)
    report = analyze_capture(value, evaluator, profile_id, tolerance)
    report.update(path=str(Path(path).resolve()), sha256=digest(path))
    if before is not None:
        report["comparison"] = compare_captures(before, value)
        report["passed"] &= report["comparison"]["passed"]
    # Current morph_session emits repeated passive samples; each must preserve
    # the same independent source/key storage without action replay.
    if isinstance(value, dict) and "interval" in value:
        interval = value["interval"]
        if not isinstance(interval, dict) or interval.get("actionReplayCount") != 0:
            raise ValueError("Capture interval has unknown/replayed actions")
        samples = interval.get("samples")
        if not isinstance(samples, list) or len(samples) < 2:
            raise ValueError("Capture interval lacks repeated passive samples")
        passive = []
        for index, sample in enumerate(samples):
            result = analyze_capture(sample, evaluator, profile_id, tolerance)
            preserved = compare_captures(value, sample)
            stable_own = _own_signature(normalize(value)["own"]) == _own_signature(normalize(sample)["own"])
            passive.append({"index": index, "passed": result["passed"] and preserved["passed"] and stable_own,
                            "errors": result["errors"], "preservation": preserved,
                            "ownStorageUnchanged": stable_own})
        report["intervalChecks"] = passive
        report["passed"] &= all(row["passed"] for row in passive)
        report["intervalSamplesChecked"] = len(samples)
        report["observedSpanSeconds"] = number(interval.get("observedSpanSeconds"))
    return report, value


def analyze_run(order_path, run_path, evaluator, tolerance=1e-4):
    order, run = read_json(order_path), Path(run_path)
    if order.get("schemaVersion") != 2 or not order.get("inputs"):
        raise ValueError("Pinned schema2 subject order required")
    xml_pins = [row for row in order["inputs"] if row.get("role") == "subject" and Path(row["path"]).name.lower() == "morphlinks.xml"]
    if len(xml_pins) != 1 or xml_pins[0]["sha256"] != evaluator.pins[evaluator.xml]:
        raise ValueError("Archived XML is not the exact selected installed subject pin")
    steps = order["subjectPlan"]["steps"]
    compiled = read_json(run / "scenario.json")["steps"]
    if len(steps) != len(compiled) or any(a["name"] != b["name"] for a, b in zip(steps, compiled)):
        raise ValueError("Collected scenario checkpoint identity differs from order")
    snapshots, reports = {}, []
    for index, step in enumerate(steps):
        request = step.get("parameters", {}).get("request", {})
        if request.get("domain") not in {"actor-morph-link-evaluation", "actor-morph-capture"}:
            continue
        path = run / f"step-{index:03d}.json"
        try:
            before_name = request.get("compareSnapshot")
            if before_name is not None and before_name not in snapshots:
                raise ValueError("Requested predecessor snapshot unavailable")
            item, capture = analyze_file(path, evaluator, before=snapshots.get(before_name),
                                         profile_id=request["familyId"], tolerance=tolerance)
            raw = unwrap(capture)
            if raw.get("snapshotLabel") != request["captureSnapshot"] or raw.get("stage") != request["stage"]:
                raise ValueError("Snapshot label/stage differs from frozen checkpoint")
            actor = request.get("actor", {})
            if actor.get("fixtureTag") is not None and raw.get("fixtureTag") != actor["fixtureTag"]:
                raise ValueError("Capture fixture identity differs from frozen request")
            if request["domain"] == "actor-morph-capture":
                def names(items):
                    if not isinstance(items, list):
                        raise ValueError("Frozen capture name list unavailable")
                    result = {identity(identifier(name)) for name in items}
                    if len(result) != len(items):
                        raise ValueError("Frozen capture list has ambiguous aliases")
                    return result
                if (names(request.get("sourceMorphs")) != set(named_map(raw.get("sources"), "sources")) or
                        names(request.get("targetMorphs")) != set(named_map(raw.get("own"), "own")) or
                        identity(identifier(request.get("ownKey"), morph=False)) != identity(raw["ownKey"])):
                    raise ValueError("Capture name/key coverage differs from frozen request")
                if request.get("requireFullNamespace") is True and "namespace" not in raw:
                    raise ValueError("Frozen request requires a complete namespace")
            elif set(named_map(raw.get("own"), "own")) != {identity(identifier(name)) for name in request["publicTargets"]}:
                raise ValueError("Legacy public target coverage differs from frozen request")
            if item.get("observedSpanSeconds", 0) < request.get("minimumObservationSpanSeconds", 0):
                raise ValueError("Requested passive observation interval is incomplete")
            snapshots[request["captureSnapshot"]] = capture
            item["check"] = step["name"]
        except (ValueError, KeyError, OSError, ET.ParseError, subprocess.TimeoutExpired) as error:
            item = {"check": step["name"], "path": str(path), "passed": False, "error": str(error)}
        reports.append(item)
    if not reports:
        raise ValueError("No requested matrix capture checkpoints")
    result = read_json(run / "result.json")
    return {"orderId": order["id"], "orderSha256": digest(order_path), "run": str(run.resolve()),
            "scenarioSha256": digest(run / "scenario.json"), "resultSha256": digest(run / "result.json"),
            "captures": reports, "numericAndObservedPreservationPassed": all(row["passed"] for row in reports),
            "retainedGameResult": result.get("result"), "retainedRestored": result.get("restored"),
            "wholeModAcceptance": "unavailable: this analyzer does not qualify collection, lifecycle, rendering or global namespaces"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xml", type=Path, required=True)
    parser.add_argument("--xml-sha256", required=True)
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--cli-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--before", type=Path)
    parser.add_argument("--profile")
    parser.add_argument("--order", type=Path)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--tolerance", type=float, default=1e-4)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("Preserve existing output report")
    if bool(args.capture) == bool(args.run) or bool(args.run) != bool(args.order) or args.before and not args.capture:
        parser.error("Use --capture [--before], or --run with --order")
    try:
        evaluator = NativeMatrix(args.xml, args.xml_sha256, args.cli, args.cli_sha256)
        if args.capture:
            item, _ = analyze_file(args.capture, evaluator, before=read_json(args.before) if args.before else None,
                                   profile_id=args.profile, tolerance=args.tolerance)
            report = {"captures": [item], "numericAndObservedPreservationPassed": item["passed"]}
        else:
            if args.profile:
                raise ValueError("Run mode uses each frozen capture profile")
            report = analyze_run(args.order, args.run, evaluator, args.tolerance)
        evaluator.verify()
        full_count = sum(row.get("ownNamespaceCoverage", "").startswith("complete:") for row in report["captures"])
        comparisons = sum("comparison" in row for row in report["captures"])
        report.update(schemaVersion=1, xml=str(evaluator.xml), xmlSha256=args.xml_sha256,
                      cli=str(evaluator.cli), cliSha256=args.cli_sha256, nativeInvocations=evaluator.invocations,
                      arithmetic="Pinned shared native matrix CLI; no Python matrix formula",
                      fullOwnNamespaceCoverage=("complete" if full_count == len(report["captures"]) else "partial" if full_count else "unavailable"),
                      globalOwnKeyAbsenceProven=all(row.get("globalOwnKeyAbsenceProven") is True for row in report["captures"]),
                      preservationComparisons=comparisons,
                      preservationCoverage=("explicit supplied before/after snapshots" if comparisons else "unavailable: no explicit comparison requested"),
                      renderedGeometryAccepted=False)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as writer:
            json.dump(report, writer, indent=2, ensure_ascii=False, allow_nan=False)
            writer.write("\n")
        print(json.dumps({"report": str(args.output), "numericAndObservedPreservationPassed": report["numericAndObservedPreservationPassed"]}))
        return 0 if report["numericAndObservedPreservationPassed"] else 1
    except (ValueError, KeyError, OSError, ET.ParseError, subprocess.TimeoutExpired) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
