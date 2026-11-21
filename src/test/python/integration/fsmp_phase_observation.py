"""Summarize individual scene windows from a hash-pinned FSMP replay."""

from argparse import ArgumentParser
from hashlib import sha256
import json
from math import hypot
from pathlib import Path

if __package__:
    from .fsmp_phase_comparison import PHASES, _motion, _read
    from .fsmp_scene_writeback import score_right_control
else:
    from fsmp_phase_comparison import PHASES, _motion, _read
    from fsmp_scene_writeback import score_right_control


def observe_window(window):
    """Measure positions in a joined window independently of any matched comparison."""
    _, poses = _read(window)
    phases = {phase: _motion(poses, phase) for phase in PHASES[2:]}
    stock = phases["afterStockWrite"]
    right = None
    if all(side["anchorDeltaGU"] == (0., 0., 0.) for side in stock.values()):
        right = score_right_control({"stockWriteDistanceGU": hypot(*stock["right"]["worldDeltaGU"])})
    return {"phases": phases, "rightStockControl": right}


def summarize_replay(replay):
    passive, active = replay["observedWindows"]
    if (not passive["scope"] or passive["scope"] != active["scope"]
            or passive["forceApplied"] is not False or active["forceApplied"] is not True):
        raise ValueError("A passive window and an active window for the same scope are required")
    return {
        "passive": observe_window(passive),
        "active": observe_window(active),
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
