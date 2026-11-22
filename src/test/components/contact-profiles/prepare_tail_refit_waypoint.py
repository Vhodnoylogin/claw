"""Project both TailBone02 banks over actual fixed-slot VR observations."""

import argparse
from hashlib import sha256
import json
from math import dist, isfinite
from pathlib import Path, PureWindowsPath

import numpy as np

from prepare_tail_refit_contrast import HAND_RADIUS, MIN_MARGIN, REPO, read_pinned, signed_capsules
from verify_tail_refit import DRIFT, MAX_GAP_NS, NANO, PROOF_SHA, Subject, _same_pose, _sphere, inspect_frame, require


NEUTRAL = np.array([-.30, 1.20, -.35])
AXES = (3, 7, 11)
STOCK_REACH = .30
STOCK_MIN_HEIGHT = .90
GAIN_MAX = 72.
GRID_STEP = .35
HOLD_NAMES = ("unattachedNear", "nearDetached")


def archived_input(path, receipt):
    data = path.read_bytes()
    digest = sha256(data).hexdigest()
    matches = [item for item in receipt["evidence"] if PureWindowsPath(item["path"]).name == path.name]
    require(len(matches) == 1 and (matches[0]["bytes"], matches[0]["sha256"]) == (len(data), digest),
            f"Archived receipt does not pin {path.name}")
    return data


def poses(ledger, evidence, subject):
    samples = {}
    for index, row in enumerate(ledger):
        payload = row.get("result")
        if row.get("tool") == "inspect" and isinstance(payload, dict) and "sampleId" in payload:
            samples.setdefault(payload["sampleId"], []).append(index)

    def locate(sample):
        matches = [i for i in samples.get(sample["sampleId"], []) if ledger[i]["result"] == sample]
        require(len(matches) == 1, "Every selected frame must match one original World Observer receipt")
        return inspect_frame(ledger, matches[0], subject)

    origin = locate(evidence["afterPosition"])
    moved = locate(evidence["preAppendGeometry"][0])
    holds = [[locate(sample) for sample in evidence["frames"][key]] for key in HOLD_NAMES]
    require(all(2 <= len(hold) <= 8 and hold[-1]["ns"] - hold[0]["ns"] >= 1.5 * NANO
                and all(0 < b["ns"] - a["ns"] <= MAX_GAP_NS for a, b in zip(hold, hold[1:]))
                for hold in holds), "The archived controls need two measured stable holds")
    frames = [moved, *[frame for hold in holds for frame in hold]]
    require(all(a["ns"] < b["ns"] for a, b in zip([origin, *frames], frames)), "Reused or out-of-order VR frames")
    for frame in frames:
        require((frame["session"], frame["epoch"]) == (origin["session"], origin["epoch"]) and
                all(frame[key][0] == origin[key][0] and _same_pose(frame[key][2], origin[key][2], DRIFT)
                    for key in ("actor", "player")) and _same_pose(origin["root"], frame["root"], DRIFT) and
                all(_same_pose(origin["controls"][key], value, DRIFT) for key, value in frame["controls"].items()) and
                _same_pose(moved["left"], frame["left"], DRIFT) and
                _same_pose({**origin["left"], "translation": frame["left"]["translation"]}, frame["left"], DRIFT),
                "The archived owner, calibration basis or stationary controls changed")
    return origin, moved, holds


def calibration(origin, moved, policy, publication):
    matrix = np.array(policy["columnsGuPerMetre"], dtype=float).T
    require(matrix.shape == (3, 3) and np.isfinite(matrix).all(), "Invalid retained controller basis")
    minimum, maximum = np.linalg.svd(matrix, compute_uv=False)[[2, 0]]
    require(68. <= minimum <= maximum <= GAIN_MAX and maximum <= 1.03 * minimum,
            "Retained controller basis is not near rigid")
    xyz = np.array(publication["frame"]["left"]["matrix"])[list(AXES)]
    require(publication["status"] == "acknowledged" and np.array_equal(xyz, policy["nearMetres"]) and
            dist(matrix @ (xyz - NEUTRAL) + origin["source"], moved["source"]) <= DRIFT,
            "Archived actual command does not validate the retained axis projection")
    return matrix, minimum


def world_capsules(frame, bank):
    capsules = []
    for shape in bank:
        p1, radius = _sphere(frame["targetPose"], shape["p1"], shape["radius"])
        p2, _ = _sphere(frame["targetPose"], shape["p2"], shape["radius"])
        capsules.append({"p1": p1, "p2": p2, "radius": radius + HAND_RADIUS * frame["left"]["scale"]})
    return capsules


def point_clearance(origin, points, role):
    start = np.asarray(origin["source"])
    line = points - start
    relative = np.asarray(origin["controls"][role]["translation"]) - start
    squares = np.einsum("ij,ij->i", line, line)
    fraction = np.clip((line @ relative) / np.where(squares > 0., squares, 1.), 0., 1.)
    return np.linalg.norm(fraction[:, None] * line - relative, axis=1) - HAND_RADIUS * origin["left"]["scale"] - DRIFT


def waypoint(origin, frames, banks, matrix, minimum_gain, max_travel=None):
    require(max_travel is None or (isfinite(max_travel) and max_travel > 0.),
            "Controller travel budget must be positive and finite")
    # A shared overlapping point must lie in every inflated morphed-bank box.
    geometry = [(world_capsules(frame, banks[0]), world_capsules(frame, banks[1])) for frame in frames]
    lower = np.max([np.min([np.minimum(cap["p1"], cap["p2"]) - cap["radius"] for cap in active], axis=0)
                    for _, active in geometry], axis=0)
    upper = np.min([np.max([np.maximum(cap["p1"], cap["p2"]) + cap["radius"] for cap in active], axis=0)
                    for _, active in geometry], axis=0)
    if np.any(upper < lower):
        return {"testedCenters": 0, "stockEnvelopeMarginUpperGu": 0., "waypoint": None}
    divisions = np.ceil((upper - lower) / GRID_STEP).astype(int).clip(min=1)
    require(int((divisions + 1).prod()) <= 2_000_000, "The retained stationary contrast exceeds the grid budget")
    axes = [np.linspace(lo, hi, n + 1) for lo, hi, n in zip(lower, upper, divisions, strict=True)]
    points = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 3)
    cover = float(np.linalg.norm((upper - lower) / divisions) / 2.)
    displacement = (points - origin["source"]) @ np.linalg.inv(matrix).T
    clearance = {role: point_clearance(origin, points, role) for role in ("head", "right")}
    admitted = (clearance["head"] >= .30 * GAIN_MAX) & (clearance["right"] >= .50 * GAIN_MAX)
    travel = np.linalg.norm(displacement, axis=1)
    if max_travel is not None:
        admitted &= travel <= max_travel
    stock_enlarged = (travel <= STOCK_REACH + cover / minimum_gain) & (
        NEUTRAL[1] + displacement[:, 1] >= STOCK_MIN_HEIGHT - cover / minimum_gain)
    neutral = np.full(len(points), np.inf)
    overlap = neutral.copy()
    for resting, active in geometry:
        neutral = np.minimum(neutral, signed_capsules(points, resting))
        overlap = np.minimum(overlap, -signed_capsules(points, active))
    margin = np.minimum(neutral, overlap)
    # Each signed gap and its minimum over the observed frames are 1-Lipschitz.
    stock_upper = max(0., float(np.max(margin[stock_enlarged])) + cover) if stock_enlarged.any() else 0.
    selected = None
    if np.any(admitted & (margin >= MIN_MARGIN)):
        best = int(np.argmax(np.where(admitted, margin, -np.inf)))
        position = NEUTRAL + displacement[best]
        within = travel[best] <= STOCK_REACH and position[1] >= STOCK_MIN_HEIGHT
        selected = {"leftTranslationMetres": position.tolist(), "controllerTravelMetres": float(travel[best]),
                    "sphereCenterGu": points[best].tolist(), "neutralSeparationGu": float(neutral[best]),
                    "morphedOverlapGu": float(overlap[best]), "insideStockEnvelope": bool(within),
                    "directSweepClearanceGu": {name: float(values[best]) for name, values in clearance.items()}}
    return {"testedCenters": len(points), "stockEnvelopeMarginUpperGu": stock_upper, "waypoint": selected}


def prepare(receipt, evidence, ledger, basis, max_travel=None):
    require(receipt["restored"] is True and receipt["collectionComplete"] is True and
            receipt["caseResult"] == "passed" and receipt["scopedCalls"]["AttachColliderCapsule"] == 1 and
            evidence["status"] == "qualified-emission-contrast" and evidence["intent"] is None and
            evidence["unknownMutation"] is False, "Expected a restored original single-slot run with complete evidence")
    sealed = evidence["sealed"]
    subject = Subject(receipt["game"]["pid"], evidence["actor"], evidence["base"], evidence["scope"]["cell"]["formId"], 1)
    require((sealed["pid"], sealed["actorFormId"], sealed["baseFormId"], sealed["cellFormId"]) ==
            (subject.pid, subject.actor, subject.base, subject.cell), "Archived capture refers to a different actor")
    origin, moved, holds = poses(ledger, evidence, subject)
    columns, minimum_gain = calibration(origin, moved, evidence["scope"]["tail02Target"], evidence["loweredPublication"])
    report = waypoint(origin, [frame for hold in holds for frame in hold], basis["capsulesByPhase"], columns,
                      minimum_gain, max_travel)
    if max_travel is not None:
        report["maxControllerTravelMetres"] = max_travel
    return {"scope": "Archived fixed-slot pose prediction only; each hold must be remeasured in the live refit.",
            "run": receipt["runId"], "normalOriginalExit": receipt["normalExit"], "model": basis["model"],
            "holdSampleIds": {name: [frame["sample"] for frame in hold] for name, hold in zip(HOLD_NAMES, holds, strict=True)},
            "requiredMarginGu": MIN_MARGIN, **report, "adaptiveContactQualified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("restored", "evidence", "steps", "basis", "out"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--max-travel-metres", type=float, help="optional radial limit from the recorded neutral position")
    args = parser.parse_args()
    output = args.out.resolve()
    require(not output.exists() and REPO not in output.parents and
            all(part.casefold() not in ("mods", "data", "overwrite", "downloads") for part in output.parts),
            "Use a new external report path")
    receipt = json.loads(args.restored.read_bytes())
    evidence_data = archived_input(args.evidence, receipt)
    steps_data = archived_input(args.steps, receipt)
    basis_data = read_pinned(args.basis, PROOF_SHA)
    report = prepare(receipt, json.loads(evidence_data), [json.loads(line) for line in steps_data.splitlines()],
                     json.loads(basis_data), args.max_travel_metres)
    report["stepsSha256"] = sha256(steps_data).hexdigest()
    report["stockEvidenceSha256"] = sha256(evidence_data).hexdigest()
    report["basisSha256"] = PROOF_SHA
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(report, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
