"""Verify actor-scoped Distribution pose ACKs from one Skyrim VR log."""
import argparse
from collections import Counter
import json
from pathlib import Path
import struct
import sys


PREFIX = "CLAW posed VR ACK "
SCHEMA = "claw-posed-vr-ack/1"
STAGES = ("capturedUs", "computedUs", "publishedUs", "acknowledgedUs")
MAX_TOKEN = 0xFFFFFF
MAX_SLOT = 127
MAX_POSE_CHANGED_SLOTS = 42
MAX_MORPHS = 32
COLLIDER_INDEX_BASE = 0x434C0000
UINT64_MAX = 0xFFFFFFFFFFFFFFFF


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, name, low, high):
    require(type(value) is int and low <= value <= high, f"Invalid {name}")
    return value


def finite(value):
    return type(value) in (float, int) and -sys.float_info.max <= value <= sys.float_info.max


def number_array(value, length, name):
    require(type(value) is list and len(value) == length and all(map(finite, value)), f"Invalid {name}")
    return [float(item) for item in value]


def name(value, field):
    require(isinstance(value, str) and bool(value.strip()), f"Missing {field}")
    return value


def names(entries, field):
    require(isinstance(entries, list) and entries and all(isinstance(entry, dict) for entry in entries),
            f"Missing {field}")
    result = [name(entry.get("name"), field) for entry in entries]
    require(len(set(result)) == len(result), f"Repeated {field}")
    return result


def unit(value):
    return (finite(value) and 0 <= value <= 1 and
            struct.unpack("<f", struct.pack("<f", value))[0] == value)


def affine_inverse(world, inverse):
    # Native uses three rows of [linear x, linear y, linear z, translation].
    for row in range(3):
        for column in range(4):
            terms = [world[4 * row + axis] * inverse[4 * axis + column] for axis in range(3)]
            if column == 3:
                terms.append(world[4 * row + 3])
            tolerance = 1e-8 * max(1.0, *map(abs, terms))
            if not all(map(finite, terms)) or abs(sum(terms) - (row == column)) > tolerance:
                return False
    return True


def capsule_geometry(entry):
    geometry = number_array(entry.get("geometry"), 7, "capsule geometry")
    try:
        # Compare the arguments CBPC receives at its Float32 boundary.
        packed = struct.pack("<7f", *geometry)
    except (OverflowError, struct.error) as error:
        raise ValueError("Capsule geometry is outside finite Float32") from error
    normalized = struct.unpack("<7f", packed)
    require(all(map(finite, normalized)) and normalized[-1] > 0, "Invalid positive Float32 capsule radius")
    ends = tuple(sorted((normalized[:3], normalized[3:6])))
    return ends, normalized[-1]


def typed_receipt(receipt):
    require(isinstance(receipt, dict) and receipt.get("schema") == SCHEMA, "Invalid ACK schema")
    integer(receipt.get("actor"), "actor", 1, 0xFFFFFFFF)
    integer(receipt.get("generation"), "generation", 1, 0x7FFFFFFF)
    for field in ("world", "registration", *STAGES):
        integer(receipt.get(field), field, 1, UINT64_MAX)
    token = integer(receipt.get("token"), "token", 1, MAX_TOKEN)
    previous = integer(receipt.get("previousToken"), "previousToken", 0, token - 1)
    stage_times = [receipt[field] for field in STAGES]
    require(stage_times == sorted(stage_times), "Invalid capture, compute, publish or ACK stage order")
    if "claimedUs" in receipt:
        claimed = integer(receipt["claimedUs"], "claimedUs", receipt["publishedUs"], receipt["acknowledgedUs"])
        require(claimed - receipt["capturedUs"] <= 500_000, "Expired capture at host claim")
    name(receipt.get("model"), "model")
    require(type(receipt.get("female")) is bool and unit(receipt.get("weight")), "Invalid sex or normalized weight")
    application = receipt.get("application")
    require(application == "full" or (application == "delta" and previous > 0), "Invalid Host application")

    morphs, bones = receipt.get("morphs"), receipt.get("bones")
    require(len(names(morphs, "morph name")) <= MAX_MORPHS and all(unit(item.get("value")) for item in morphs),
            "Invalid effective morph vector")
    names(bones, "bone name")
    for bone in bones:
        world = number_array(bone.get("world"), 12, "world transform")
        inverse = number_array(bone.get("worldToBone"), 12, "worldToBone transform")
        require(affine_inverse(world, inverse), "World and worldToBone transforms are not inverses")

    changed, capsules = receipt.get("changedSlots"), receipt.get("capsules")
    require(isinstance(changed, list) and changed, "Missing changed slots")
    for slot in changed:
        integer(slot, "changed slot", 0, MAX_SLOT)
    require(changed == sorted(set(changed)) and (previous == 0 or len(changed) <= MAX_POSE_CHANGED_SLOTS),
            "Changed slots must be unique, sorted and within the pose budget")
    require(isinstance(capsules, list) and capsules and all(isinstance(item, dict) for item in capsules),
            "Missing Host capsule arguments")
    slot_ids = [integer(item.get("slot"), "capsule slot", 0, MAX_SLOT) for item in capsules]
    require(slot_ids == sorted(set(slot_ids)), "Host capsule slots must be unique and sorted")
    require(slot_ids == changed if application == "delta" or previous == 0 else set(changed) <= set(slot_ids),
            "Host capsule arguments do not cover the declared changed slots")
    for slot, item in zip(slot_ids, capsules, strict=True):
        index = item.get("colliderIndex")
        require(type(index) is int and index == COLLIDER_INDEX_BASE + slot,
                "Capsule collider index does not match its owned slot")
    return {slot: (name(item.get("node"), "attachment node"), capsule_geometry(item))
            for slot, item in zip(slot_ids, capsules, strict=True)}


def unique_object(pairs):
    result = dict(pairs)
    require(len(result) == len(pairs), "Repeated JSON key")
    return result


def profile_slots(profile, receipt):
    require(isinstance(profile, dict) and profile.get("modelIdentity") == receipt["model"],
            "ACK does not match the supplied fitted profile identity")
    require(profile.get("morphs") == [entry["name"] for entry in receipt["morphs"]],
            "ACK morph order does not match the supplied fitted profile")
    slots = profile.get("slots")
    require(isinstance(slots, list) and 0 < len(slots) <= MAX_SLOT + 1, "Invalid fitted profile slots")
    active = {}
    sex = "female" if receipt["female"] else "male"
    for slot, entry in enumerate(slots):
        require(isinstance(entry, dict) and entry.get("sexMask") in ("male", "female", "both"),
                "Invalid fitted profile sex mask")
        if entry["sexMask"] in (sex, "both"):
            active[slot] = name(entry.get("node"), "profile attachment node")
    return active


def selected_receipts(lines, actor, generation):
    seen, selected = set(), []
    for line_number, line in enumerate(lines, 1):
        _, marker, payload = line.partition(PREFIX)
        if not marker:
            continue
        try:
            receipt = json.loads(payload, object_pairs_hook=unique_object)
            bank = typed_receipt(receipt)
            token = receipt["token"]
            require(token not in seen, f"Duplicate ACK token {token}")
            seen.add(token)
            if (receipt["actor"], receipt["generation"]) == (actor, generation):
                selected.append((token, line_number, receipt, bank))
        except ValueError as error:
            raise ValueError(f"Log line {line_number}: {error}") from error
    # Native assigns and accepts the token under a lock, then emits the line.
    # Writer scheduling may reverse adjacent lines without changing acceptance.
    return sorted(selected, key=lambda entry: entry[0])


def verify(lines, *, actor, generation, profile=None, expected_tokens=(), require_delta=False):
    integer(actor, "requested actor", 1, 0xFFFFFFFF)
    integer(generation, "requested generation", 1, 0x7FFFFFFF)
    missing = {integer(token, "expected token", 1, MAX_TOKEN) for token in expected_tokens}
    receipts = selected_receipts(lines, actor, generation)
    require(receipts, "No ACK for the requested actor and generation")
    counts = Counter()
    preceding, binding, ledger, expected_nodes = None, None, {}, {}
    for token, line_number, receipt, bank in receipts:
        try:
            previous = receipt["previousToken"]
            bone_names = [bone["name"] for bone in receipt["bones"]]
            morph_names = [morph["name"] for morph in receipt["morphs"]]
            current_binding = (receipt["world"], receipt["registration"], receipt["model"], receipt["female"],
                               morph_names, bone_names)
            if preceding is None:
                require(previous == 0, "Initial full ACK is missing")
                binding = current_binding
                expected_nodes = (profile_slots(profile, receipt) if profile is not None else
                                  {slot: item[0] for slot, item in bank.items()})
            else:
                require(binding == current_binding, "ACK actor binding changed inside the selected generation")
                require(preceding["acknowledgedUs"] <= receipt["acknowledgedUs"], "ACK time regressed")
            actual_nodes = {slot: item[0] for slot, item in bank.items()}
            require(all(expected_nodes.get(slot) == node for slot, node in actual_nodes.items()),
                    "ACK capsule slot or attachment node does not match the binding")
            if receipt["application"] == "full":
                require(actual_nodes == expected_nodes, "Full ACK omits enabled slots")

            if previous:
                require(preceding is not None and previous == preceding["token"], "Previous ACK token is missing or stale")
                require(preceding["acknowledgedUs"] <= receipt["capturedUs"] and
                        preceding["morphs"] == receipt["morphs"] and preceding["weight"] == receipt["weight"],
                        "Pose ACK is not based on the previous accepted inputs")
                observed = [slot for slot in bank if bank[slot] != ledger[slot]]
                require(observed == receipt["changedSlots"],
                        "Host geometry contradicts the declared pose-only changes")
            ledger.update(bank)
            preceding = receipt
            counts[receipt["application"]] += 1
            counts["pose"] += bool(previous)
            counts["nativeFull"] += previous == 0
            missing.discard(token)
        except ValueError as error:
            raise ValueError(f"Log line {line_number}: {error}") from error

    require(not missing, f"Expected ACK token is missing from the selected binding: {sorted(missing)}")
    require(not require_delta or counts["delta"] > 0, "No successful Host delta application")
    return {"schema": SCHEMA, "actor": actor, "generation": generation, "model": preceding["model"],
            "lastToken": preceding["token"], "nativeFull": counts["nativeFull"], "pose": counts["pose"],
            "hostFull": counts["full"], "hostDelta": counts["delta"], "enabledSlots": len(expected_nodes),
            "profileBindingsVerified": profile is not None, "solverGeometryVerified": False, "contactVerified": False}


def parse_id(value):
    try:
        return int(value, 16 if value.lower().startswith("0x") else 10)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Expected a decimal or 0x-prefixed integer") from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--actor", required=True, type=parse_id, help="actor FormID in hex or decimal")
    parser.add_argument("--generation", required=True, type=parse_id)
    parser.add_argument("--profile", type=Path, help="fitted VR model JSON for exact enabled-slot validation")
    parser.add_argument("--token", action="append", type=parse_id, default=[],
                        help="require this exact token in the selected actor binding (repeatable)")
    parser.add_argument("--require-delta", action="store_true", help="require Host delta instead of only full application")
    args = parser.parse_args()
    try:
        profile = json.loads(args.profile.read_text(encoding="utf-8-sig")) if args.profile is not None else None
        with args.log.open(encoding="utf-8-sig") as log:
            result = verify(log, actor=args.actor, generation=args.generation, profile=profile,
                            expected_tokens=args.token, require_delta=args.require_delta)
    except (ValueError, OSError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
