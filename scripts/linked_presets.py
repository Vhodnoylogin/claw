"""Offline exact human/beast preset pairing and exclusive-key policy planner.

No game calls, OBody writes, actor discovery or acknowledgment. The current DLL
does not consume these plans. Pure functions receive normalized catalog/contracts.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

KEYS = ["CLAW.Distribution", "CLAW.Link"]
BREAST = "CLAWTorsoBreastSize"


def text(value):
    if not isinstance(value, str) or not value or value != value.strip() or len(value.encode("utf-8")) > 512:
        raise ValueError("Expected a bounded exact identifier")
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError("Control characters in identifier")
    return value


def number(value, high=1):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= high or not math.isfinite(value):
        raise ValueError("Expected a finite bounded number")
    return float(value)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def confirmed_source(source):
    return (isinstance(source, dict) and set(source) == {"profile", "preset", "confirmed"}
            and source["confirmed"] is True and isinstance(source["profile"], str)
            and (source["preset"] is None or isinstance(source["preset"], str)))


def vector(value, allowed):
    if not isinstance(value, dict) or set(value).difference(allowed):
        raise ValueError("Unsupported morph in coefficient vector")
    return {name: number(v) for name, v in value.items()}


def catalog_index(catalog, allowed):
    result = {}
    for row in catalog:
        if set(row) != {"name", "sex", "morphs"} or row["sex"] not in allowed:
            raise ValueError("Invalid normalized preset")
        name = text(row["name"])
        if name in result or not isinstance(row["morphs"], dict) or set(row["morphs"]).difference(allowed[row["sex"]]):
            raise ValueError("Duplicate/unsupported preset")
        for endpoints in row["morphs"].values():
            if not isinstance(endpoints, dict) or set(endpoints) != {"small", "big"}:
                raise ValueError("Need normalized small/big endpoints")
            for coefficient in endpoints.values():
                number(coefficient)
        result[name] = row
    return result


def interpolate(preset, weight, allowed):
    weight = number(weight, 100) / 100
    return {name: preset["morphs"].get(name, {}).get("small", 0.0) * (1 - weight)
                  + preset["morphs"].get(name, {}).get("big", 0.0) * weight
            for name in sorted(allowed)}


def rules_index(document, catalog, allowed):
    if not isinstance(document, dict) or set(document) != {"schemaVersion", "pairs"} or type(document["schemaVersion"]) is not int or document["schemaVersion"] != 1:
        raise ValueError("Unsupported paired-preset document")
    if not isinstance(document["pairs"], list) or len(document["pairs"]) > 4096:
        raise ValueError("Invalid pair list")
    result, identifiers = {}, set()
    for row in document["pairs"]:
        if not isinstance(row, dict) or set(row) != {"id", "sourceProfile", "sourcePreset", "sex", "targetPreset", "bodyMorphs"}:
            raise ValueError("Unknown/missing pair properties")
        for field in ("id", "sourceProfile", "sourcePreset", "targetPreset"):
            text(row[field])
        sex = row["sex"]
        if sex not in allowed or row["id"] in identifiers:
            raise ValueError("Invalid pair sex or duplicate id")
        key = row["sourceProfile"], row["sourcePreset"], sex
        domain = row["bodyMorphs"]
        if key in result or not isinstance(domain, list) or not domain or any(not isinstance(n, str) for n in domain) or len(set(domain)) != len(domain):
            raise ValueError("Ambiguous pair or invalid replacement domain")
        if set(domain).difference(allowed[sex]) or BREAST in domain:
            raise ValueError("Unsupported/unqualified paired morph")
        target = catalog.get(row["targetPreset"])
        if target is None or target["sex"] != sex:
            raise ValueError("Missing/wrong-sex paired target")
        identifiers.add(row["id"])
        result[key] = row
    return result


def plan(snapshot, document=None, catalog=None, allowed=None):
    """Return pending intent; cleanup/defer precedes provider/catalog validation."""
    if not isinstance(snapshot, dict) or snapshot.get("schemaVersion") != 1 or type(snapshot["schemaVersion"]) is not int:
        raise ValueError("Unsupported snapshot")
    identity = text(snapshot["identity"])
    sex = snapshot.get("sex")
    if any(type(snapshot[k]) is not bool for k in ("isBeast", "loaded", "suppressed")):
        raise ValueError("Expected exact observation/control booleans")
    mode = snapshot.get("mode")
    saved = snapshot.get("previous")
    if saved is not None and not isinstance(saved, dict):
        raise ValueError("Saved state must be an object or null")
    previous = copy.deepcopy(saved or {})
    if previous and (type(previous.get("schemaVersion")) is not int or previous.get("schemaVersion") != 1 or previous.get("identity") != identity):
        raise ValueError("Saved state identity/schema mismatch")
    generation = previous.get("generation", 0)
    if type(generation) is not int or not 0 <= generation < 2**63 - 1:
        raise ValueError("Invalid saved generation")
    state = previous | {"schemaVersion": 1, "identity": identity, "generation": generation + 1}
    result = {"generation": generation + 1, "pending": True, "policy": mode,
              "activeKey": None, "clearKeys": [], "desiredMorphs": {}, "diagnostics": [], "state": state}
    if not snapshot["loaded"]:
        result.update(policy="deferred", diagnostics=["unloaded; no writes, reconciliation pending"])
        return result
    result["clearKeys"] = KEYS.copy()
    if not snapshot["isBeast"] or snapshot["suppressed"]:
        result["policy"] = "suppressed" if snapshot["isBeast"] else "human"
        return result
    try:
        if sex not in ("male", "female") or previous.get("sex", sex) != sex:
            raise ValueError("Unreadable/changed selected body sex; explicit rebind required")
        if mode not in ("independent", "linked", "manual"):
            raise ValueError("Explicit policy mode required")
        state["sex"] = sex
        if allowed is None or sex not in allowed:
            raise ValueError("Missing explicit morph contract")
        source = snapshot.get("source")
        source_ready = confirmed_source(source)
        if mode == "linked" and not source_ready and previous.get("lastLink"):
            last = previous["lastLink"]
            desired = vector(last["desiredMorphs"], allowed[sex])
            if desired.get(BREAST, 0) != 0:
                raise ValueError("Unqualified cached linked breast value")
            result.update(policy="stale-link", activeKey=KEYS[1], desiredMorphs=desired,
                          diagnostics=["source unavailable/unconfirmed; retained last resolved linked intent"])
            return result
        weight = number(snapshot["weight"], 100)
        index = catalog_index(catalog, allowed)
        selected = snapshot.get("manualPreset") if mode == "manual" else snapshot["independentPreset"]
        preset = index.get(text(selected))
        if preset is None or preset["sex"] != sex:
            raise ValueError("Missing/wrong-sex selected preset")
        desired = interpolate(preset, weight, allowed[sex])
        result["activeKey"] = KEYS[0]
        if mode == "linked":
            traits = vector(snapshot["traits"], allowed[sex])
            if BREAST in traits:
                raise ValueError("Unqualified individual breast trait")
            if "traits" in previous and previous["traits"] != traits:
                raise ValueError("Saved individual traits changed without explicit rebind")
            # Even an unmapped new human preset must not reroll ears/tail.
            desired.update(traits)
            if sex == "female":
                desired[BREAST] = 0.0
            state["traits"] = copy.deepcopy(traits)
            if source_ready and source["preset"] is None:
                text(source["profile"])
                # Only retire the pinned link after the independent preset,
                # weight and saved individual traits have resolved successfully.
                state.pop("lastLink", None)
                result["diagnostics"].append("source confirmed unassigned; independent fallback, previous link retired")
            elif not source_ready:
                result["diagnostics"].append("source unavailable/unconfirmed; independent fallback")
            else:
                text(source["profile"])
                text(source["preset"])
                rules = rules_index(document, index, allowed)
                rule = rules.get((source["profile"], source["preset"], sex))
                last = previous.get("lastLink")
                if rule is None:
                    if last and last["source"] == source:
                        raise ValueError("Previously pinned pair disappeared; explicit rebind required")
                    result["diagnostics"].append("exact source pair unmapped; independent fallback")
                else:
                    if set(traits).intersection(rule["bodyMorphs"]):
                        raise ValueError("Individual traits overlap body replacement domain")
                    target = index[rule["targetPreset"]]
                    binding = {"id": rule["id"], "ruleSha256": fingerprint(rule), "targetSha256": fingerprint(target)}
                    if last and (last["source"] == source or last["binding"]["id"] == rule["id"]) and last["binding"] != binding:
                        raise ValueError("Pinned pair/target changed; explicit rebind required")
                    replacement = interpolate(target, weight, allowed[sex])
                    for morph in rule["bodyMorphs"]:
                        desired[morph] = replacement[morph]
                    desired.update(traits)
                    desired[BREAST] = 0.0 if sex == "female" else desired.get(BREAST, 0.0)
                    if sex == "male":
                        desired.pop(BREAST, None)
                    state.update(traits=copy.deepcopy(traits), lastLink={"source": copy.deepcopy(source),
                                 "binding": binding, "desiredMorphs": copy.deepcopy(desired)})
                    result.update(policy="linked", activeKey=KEYS[1])
        if mode == "linked" and result["activeKey"] == KEYS[0]:
            result["policy"] = "independent"
        result["desiredMorphs"] = desired
    except (ValueError, KeyError, TypeError) as error:
        result.update(policy="error", activeKey=None, clearKeys=[], desiredMorphs={}, diagnostics=[str(error)])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--pairs", type=Path)
    parser.add_argument("--presets", type=Path)
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8-sig"))
    # A human-return/deferred/suppressed plan needs no source/catalog files.
    needs = snapshot.get("isBeast") is True and snapshot.get("loaded") is True and snapshot.get("suppressed") is False
    catalog, rules, allowed = None, None, None
    if needs:
        import presets
        allowed = presets.inventory()
        source_ready = confirmed_source(snapshot.get("source"))
        previous = snapshot.get("previous")
        cached = isinstance(previous, dict) and previous.get("lastLink")
        stale = snapshot.get("mode") == "linked" and not source_ready and cached
        if args.presets and not stale:
            catalog = presets.load_tree(args.presets)["presets"]
        if args.pairs and snapshot.get("mode") == "linked" and source_ready and snapshot["source"]["preset"] is not None:
            rules = json.loads(args.pairs.read_text(encoding="utf-8-sig"))
    result = plan(snapshot, rules, catalog, allowed)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 2 if result["policy"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
