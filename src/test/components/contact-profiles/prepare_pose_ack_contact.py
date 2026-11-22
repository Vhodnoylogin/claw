"""Find a same-pose sphere contrast between two acknowledged VR capsule banks."""

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path

import numpy as np

from prepare_tail_refit_contrast import MIN_MARGIN, REPO, signed_capsules
from verify_pose_ack import parse_id, require, selected_receipts, verify


GRID_STEP = 0.25
MAX_POINTS = 2_000_000


def banks_at_token(lines, actor, generation, profile, token, node):
    verify(lines, actor=actor, generation=generation, profile=profile, expected_tokens=(token,))
    ledger = {}
    for current, _, receipt, bank in selected_receipts(lines, actor, generation):
        if current != token:
            ledger.update(bank)
            continue
        require(receipt["previousToken"] > 0 and receipt["application"] == "delta",
                "Choose a pose token acknowledged by the Host delta path")
        slots = sorted(slot for slot, (name, _) in ledger.items() if name == node)
        require(set(slots).intersection(receipt["changedSlots"]), "The selected node has no changed slot")
        bone = next((entry for entry in receipt["bones"] if entry["name"] == node), None)
        require(bone is not None, "The selected node has no transform in the fit input")
        return receipt, slots, bone["world"], [ledger[slot][1] for slot in slots], [bank.get(slot, ledger[slot])[1] for slot in slots]
    raise ValueError("Requested token is missing from the verified chain")


def project(bank, transform, hand_radius):
    linear, translation = transform[:, :3], transform[:, 3]
    scale = float(np.linalg.norm(linear[:, 0]))
    require(math.isfinite(scale) and scale > 0, "The attachment scale must be positive and finite")
    rotation = linear / scale
    require(np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-5, rtol=0) and
            np.linalg.det(rotation) > 0, "The attachment transform must be a positive uniform scale and rotation")
    result = []
    for ends, radius in bank:
        p1, p2 = np.asarray(ends) @ linear.T + translation
        expanded = radius * scale + hand_radius
        require(np.isfinite([p1, p2]).all() and math.isfinite(expanded), "Projected capsule is not finite")
        result.append({"p1": p1, "p2": p2, "radius": expanded})
    return result


def paired_bank_bound(clear, overlap):
    # Same-slot endpoint pairing bounds the segment Hausdorff distance. Adding
    # the radius change then bounds the difference between the signed gaps.
    bound = 0.
    for old, new in zip(clear, overlap, strict=True):
        direct = max(math.dist(old["p1"], new["p1"]), math.dist(old["p2"], new["p2"]))
        reversed_ends = max(math.dist(old["p1"], new["p2"]), math.dist(old["p2"], new["p1"]))
        bound = max(bound, min(direct, reversed_ends) + abs(old["radius"] - new["radius"]))
    return bound / 2.


def contrast(clear, overlap, minimum_margin):
    # A point penetrating the destination union lies inside this box.
    lower = np.min([np.minimum(cap["p1"], cap["p2"]) - cap["radius"] for cap in overlap], axis=0)
    upper = np.max([np.maximum(cap["p1"], cap["p2"]) + cap["radius"] for cap in overlap], axis=0)
    span = upper - lower
    require(np.isfinite(span).all(), "Invalid waypoint search extent")
    divisions = [max(1, math.ceil(width / GRID_STEP)) for width in span]
    require(math.prod(count + 1 for count in divisions) <= MAX_POINTS, "Waypoint search exceeds the sample budget")
    axes = [np.linspace(lo, hi, count + 1) for lo, hi, count in zip(lower, upper, divisions, strict=True)]
    points = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 3)
    separation = signed_capsules(points, clear)
    penetration = -signed_capsules(points, overlap)
    margin = np.minimum(separation, penetration)
    index = int(np.argmax(margin))
    # The worst of the two signed gaps is 1-Lipschitz. Outside the box
    # the destination penetration is nonpositive.
    cover = math.hypot(*(span / divisions)) / 2.
    upper_bound = min(paired_bank_bound(clear, overlap), max(0., float(margin[index]) + cover))
    return {"testedCenters": len(points), "bestSampledMarginGu": float(margin[index]), "marginUpperBoundGu": upper_bound,
            "meetsRequestedMargin": bool(margin[index] >= minimum_margin),
            "sphereCenterRootRelativeGu": points[index].tolist(), "separationGu": float(separation[index]),
            "overlapGu": float(penetration[index])}


def prepare(lines, profile, *, actor, generation, token, node, hand_radius, minimum_margin=MIN_MARGIN):
    require(math.isfinite(hand_radius) and hand_radius > 0., "The projected hand radius must be positive and finite")
    require(math.isfinite(minimum_margin) and minimum_margin > 0., "The minimum margin must be positive and finite")
    receipt, slots, matrix, old, new = banks_at_token(lines, actor, generation, profile, token, node)
    # Hold the current bone transform fixed for both banks so bone motion
    # alone cannot produce an apparent change in overlap.
    transform = np.asarray(matrix, dtype=float).reshape(3, 4)
    previous = project(old, transform, hand_radius)
    current = project(new, transform, hand_radius)
    return {"schema": "claw-vr-pose-contact-contrast/1", "actor": actor, "generation": generation,
            "world": receipt["world"], "registration": receipt["registration"], "model": receipt["model"],
            "previousToken": receipt["previousToken"], "token": token, "node": node, "slots": slots,
            "handSphereRadiusGu": hand_radius, "requiredMarginGu": minimum_margin, "gridStepGu": GRID_STEP,
            "oldClearNewOverlap": contrast(previous, current, minimum_margin),
            "oldOverlapNewClear": contrast(current, previous, minimum_margin),
            "scope": "Same captured bone transform in both banks, world axes relative to the actor root.",
            "controllerReachChecked": False, "contactVerified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("log", "profile", "out"):
        parser.add_argument("--" + name, required=True, type=Path)
    for name in ("actor", "generation", "token"):
        parser.add_argument("--" + name, required=True, type=parse_id)
    parser.add_argument("--node", required=True, help="sole attachment bone in the CBPC test group")
    parser.add_argument("--hand-radius-gu", required=True, type=float, help="projected world-space sphere radius")
    parser.add_argument("--margin-gu", default=MIN_MARGIN, type=float)
    args = parser.parse_args()
    try:
        output = args.out.resolve()
        require(not output.exists() and REPO not in output.parents and
                all(part.casefold() not in ("mods", "data", "overwrite", "downloads") for part in output.parts),
                "Use a new external report path")
        log, profile = args.log.read_bytes(), args.profile.read_bytes()
        report = prepare(log.decode("utf-8-sig").splitlines(), json.loads(profile), actor=args.actor,
                         generation=args.generation, token=args.token, node=args.node,
                         hand_radius=args.hand_radius_gu, minimum_margin=args.margin_gu)
        report["logSha256"] = sha256(log).hexdigest()
        report["profileSha256"] = sha256(profile).hexdigest()
        with output.open("x", encoding="utf-8") as file:
            json.dump(report, file, indent=2, allow_nan=False)
            file.write("\n")
    except (ValueError, OSError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(report, allow_nan=False))


if __name__ == "__main__":
    main()
