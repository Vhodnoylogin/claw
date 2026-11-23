"""Summarize individual scene windows from a hash-pinned FSMP replay."""

from argparse import ArgumentParser
from hashlib import sha256
import json
from math import hypot
from pathlib import Path

if __package__:
    from . import fsmp_probe as probe
    from .fsmp_phase_comparison import PHASES, ROLES, _motion, _read
    from .fsmp_scene_writeback import _delta, score_right_control
else:
    import fsmp_probe as probe
    from fsmp_phase_comparison import PHASES, ROLES, _motion, _read
    from fsmp_scene_writeback import _delta, score_right_control


def parent_frames(before, after):
    """Measure residual motion after carrying each driver with its full parent transform."""
    result = {}
    for side in ("left", "right"):
        node, anchor = side + "P1", side + "Anchor"
        old = probe.relative(before[node], before[anchor])
        new = probe.relative(after[node], after[anchor])
        translation = _delta(new["translation"], old["translation"])
        result[side] = {
            "parentLocalTranslationDelta": translation,
            "worldDistanceFromParentCarryGU": after[anchor]["scale"] * hypot(*translation),
            "parentLocalRotationComponentDelta": probe.max_delta(old["rotationRowMajor"], new["rotationRowMajor"]),
            "parentLocalScaleDelta": new["scale"] - old["scale"],
        }
    return result


def numeric_poses(numeric_world, positions):
    if set(numeric_world) != set(PHASES) or any(set(numeric_world[phase]) != set(ROLES) for phase in PHASES):
        raise ValueError("Numeric transforms are required for the same phases and roles")
    poses = {}
    for phase in PHASES:
        poses[phase] = {}
        for role, world in numeric_world[phase].items():
            value = probe.transform({"translation": world["translation"], "rotationRowMajor": world["rotation"],
                                     "scale": world["scale"]})
            if tuple(value["translation"]) != positions[phase][role]:
                raise ValueError("Numeric transform position differs from the joined scene observation")
            poses[phase][role] = value
    return poses


def observe_window(window, numeric_world=None):
    """Measure positions in a joined window independently of any matched comparison."""
    _, poses = _read(window)
    phases = {phase: _motion(poses, phase) for phase in PHASES[2:]}
    stock = phases["afterStockWrite"]
    right = None
    if all(side["anchorDeltaGU"] == (0., 0., 0.) for side in stock.values()):
        right = score_right_control({"stockWriteDistanceGU": hypot(*stock["right"]["worldDeltaGU"])})
    result = {"phases": phases, "rightStockControl": right}
    if numeric_world is not None:
        world = numeric_poses(numeric_world, poses)
        result["parentFrameMotion"] = {phase: parent_frames(world["beforeStockWrite"], world[phase]) for phase in PHASES[2:]}
    return result


def summarize_replay(replay):
    passive, active = replay["observedWindows"]
    if (not passive["scope"] or passive["scope"] != active["scope"]
            or passive["forceApplied"] is not False or active["forceApplied"] is not True):
        raise ValueError("A passive window and an active window for the same scope are required")
    numeric = replay.get("numericWorldByLane", [None, None])
    if "numericWorldByLane" in replay and (not isinstance(numeric, list) or len(numeric) != 2 or
                                           any(not isinstance(lane, dict) for lane in numeric)):
        raise ValueError("The numeric replay must include both passive and active lanes")
    return {
        "passive": observe_window(passive, numeric[0]),
        "active": observe_window(active, numeric[1]),
        "passiveSolverStepsS": passive["solverSteps"],
        "activeSolverStepsS": active["solverSteps"],
        "initialMatch": replay["initialMatch"],
        "comparisonUnavailable": replay.get("comparisonUnavailable"),
        "renderedMotionMeasured": replay["renderedMotionMeasured"],
    }


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("replay", type=Path)
    parser.add_argument("sha256")
    args = parser.parse_args()
    data = args.replay.read_bytes()
    if sha256(data).hexdigest() != args.sha256:
        parser.error("Replay SHA-256 differs from the expected digest")
    print(json.dumps(dict(summarize_replay(json.loads(data)), sourceSha256=args.sha256), indent=2))
