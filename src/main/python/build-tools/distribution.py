"""Offline reference core for linked human/beast morphs; no game or OBody writes.

The future runtime adapter must supply a save-stable actor identity, actual current
race/3D state, explicit body family and already interpolated human coefficients.
This module produces a pending plan; it cannot observe or apply anything in game.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Morph coefficients must be numbers")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("Morph coefficients must be finite")
    return value


def clamp(value):
    return min(1.0, max(0.0, finite(value)))


def trait(identity, name, limits):
    if not isinstance(identity, str) or not identity.strip():
        raise ValueError("A save-stable actor identity is required")
    low, high = map(finite, limits)
    if not 0 <= low <= high <= 1:
        raise ValueError("Invalid trait range")
    payload = json.dumps(["CLAW.Link/1", identity, name], ensure_ascii=False,
                         separators=(",", ":")).encode("utf-8")
    fraction = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") / (2**64 - 1)
    return low + fraction * (high - low)


def known_morphs():
    names = set()
    for filename in ("full-body.json", "female.json"):
        names.update(row["morph"] for row in json.loads(
            (ROOT / 'src/main/resources/recipes' / filename).read_text(encoding="utf-8")) if "morph" in row)
    adult = json.loads((ROOT / 'src/main/resources/recipes/build.json').read_text(encoding="utf-8"))["adultMorphs"]
    return names.difference(adult)


def derive(identity, family, human, sex, recipe):
    if sex not in ("male", "female"):
        raise ValueError("Expected actual selected body sex: male or female")
    if family is not None and family not in recipe["bodyFamilies"]:
        raise ValueError("Unsupported body family; use null for a native beast")
    if recipe["schemaVersion"] != 1 or recipe["key"] != "CLAW.Link":
        raise ValueError("Unsupported recipe contract")
    human = {name: finite(value) for name, value in human.items()}
    result = {name: trait(identity, name, limits)
              for name, limits in recipe["inherentTraits"].items()}
    if family is None:
        if human:
            raise ValueError("A native beast cannot silently discard human coefficients")
        result.update({name: trait(identity, name, limits)
                       for name, limits in recipe["nativeBeastTraits"].items()})
    else:
        for name, rule in recipe["bodyFamilies"][family].items():
            # Signed source contributions combine before the resulting trait is clamped.
            value = sum(human.get(source, 0.0) * finite(weight)
                        for source, weight in rule["inputs"].items())
            result[name] = clamp(value) * clamp(rule["limit"])
    if set(result).difference(known_morphs()):
        raise ValueError("Recipe contains unsupported or adult CLAW morphs")
    # Current breast shape is intentionally not randomized or inferred from human size.
    if sex == "female":
        result["CLAWTorsoBreastSize"] = 0.0
    elif "CLAWTorsoBreastSize" in result:
        raise ValueError("Female breast morph cannot be applied to the male body")
    return dict(sorted(result.items()))


def plan_update(previous, identity, family, human, sex, is_beast, loaded, recipe):
    """Plan scoped writes after a race/preset/load event, preserving unrelated keys.

    Each invocation increments a generation. The adapter must discard any queued
    plan whose generation or captured race differs from the latest actor state.
    Every plan remains pending until actual set/update/readback succeeds.
    """
    if type(is_beast) is not bool or type(loaded) is not bool:
        raise ValueError("Race and loaded-state observations must be booleans")
    if not isinstance(identity, str) or not identity.strip():
        raise ValueError("A save-stable actor identity is required")
    if sex not in ("male", "female"):
        raise ValueError("Expected actual selected body sex: male or female")
    if recipe["schemaVersion"] != 1 or recipe["key"] != "CLAW.Link":
        raise ValueError("Unsupported recipe contract")
    state = copy.deepcopy(previous) if previous else {}
    if state and (state.get("schemaVersion") != 1 or state.get("identity") != identity):
        raise ValueError("State schema or actor identity mismatch")
    generation = state.get("generation", 0)
    if type(generation) is not int or generation < 0:
        raise ValueError("Invalid saved generation")
    # Returning to human must still clear our key if the source provider vanished,
    # changed body family or supplied malformed coefficients during transformation.
    if is_beast:
        coefficients = derive(identity, family, human, sex, recipe)
        state.update(bodyFamily=family, sourceMorphs=copy.deepcopy(human),
                     beastMorphs=coefficients)
    else:
        state.setdefault("bodyFamily", None)
        state.setdefault("sourceMorphs", {})
        state.setdefault("beastMorphs", {})
    state.update(schemaVersion=1, identity=identity, sex=sex,
                 currentForm="beast" if is_beast else "human",
                 generation=generation + 1, pending=True)
    actions = []
    if loaded:
        actions.append({"op": "clear_key", "key": recipe["key"]})
        if is_beast:
            actions.extend({"op": "set", "key": recipe["key"], "morph": name, "value": value}
                           for name, value in state["beastMorphs"].items())
        actions.append({"op": "update_model"})
    return {"state": state, "generation": state["generation"],
            "observedForm": state["currentForm"], "actions": actions,
            "status": "pending-runtime-validation"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON actor snapshot; no live game connection")
    parser.add_argument("--recipe", type=Path, default=ROOT / 'src/main/resources/recipes/distribution.json')
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8-sig"))
    recipe = json.loads(args.recipe.read_text(encoding="utf-8-sig"))
    plan = plan_update(data.get("previous"), data["identity"], data["bodyFamily"],
                       data["humanMorphs"], data["sex"], data["isBeast"], data["loaded"], recipe)
    print(json.dumps(plan, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
