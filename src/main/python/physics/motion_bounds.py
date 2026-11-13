"""Extend named-morph spheres for the declared small-motion adapter envelope."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
TOOLS = ROOT / "src/main/python/build-tools"
sys.path.insert(0, str(TOOLS))
import runtime_bounds as bounds
from head_split import Nif
import breast_rig as rig


def motion_bound_extra(center, radius, pivots):
    """Conservative composition of five nominal bounded joint corrections.

    Each step can move by sqrt(3)*.5 and rotate by at most 3*.0105 radians.
    The recurrence also allows earlier corrections to increase the lever arm.
    This covers CBPC's original ear/tail/P1 constants at unit amplitude and the
    FSMP adapter's smaller limits; it is not an actual solver-overshoot bound.
    """
    center, pivots = np.asarray(center, float), np.asarray(pivots, float)
    if center.shape != (3,) or pivots.ndim != 2 or pivots.shape[1] != 3 or not len(pivots):
        raise ValueError("Motion envelope requires a sphere center and existing driver pivots")
    if not np.isfinite(center).all() or not np.isfinite(pivots).all() or not math.isfinite(radius) or radius <= 0:
        raise ValueError("Motion envelope sphere/pivots must be finite")
    lever = float(np.linalg.norm(pivots - center, axis=1).max()) + radius + 1.0
    rotation_gain = 2 * math.sin(3 * .0105 / 2)
    extra = 0.0
    for _ in range(5):
        extra = (1 + rotation_gain) * extra + math.sqrt(3) * .5 + rotation_gain * lever
    return extra * 1.001


def build(sourceDir, outputDir):
    source, out = Path(sourceDir).resolve(), Path(outputDir).resolve()
    bounds.body.authored_output(out, [source / "malebodywerewolf_0.nif"])
    names = [sex + "bodywerewolf" + ending for sex in ("male", "female") for ending in ("_0.nif", "_1.nif", ".tri")]
    pins = {name: rig.sha256(source / name) for name in names}
    source_files = [Path(__file__), Path(bounds.__file__), TOOLS / "head_split.py",
                    Path(__file__).with_name("motion_adapter.py"), Path(__file__).with_name("recipe.json"),
                    Path(__file__).with_name("fsmp_motion.py"),
                    Path(__file__).with_name("breast-motion.json"), Path(__file__).with_name("p1-rig-v3.json")]
    sources = {str(path): rig.sha256(path) for path in source_files}
    skeleton = ROOT / "src/main/resources/donors/skeleton.nif"
    if rig.sha256(skeleton) != "b64b614d06eb854512ef4a9d6b08777fe0f9580f47d495d20db16dabb9fc2dd0":
        raise ValueError("Motion-bound pivot skeleton changed")
    api, _ = bounds.body.load_api()
    skel = api.NifFile(str(skeleton))
    drivers = ("NPC EarL [EarL]Bone01", "NPC EarL [EarL]Bone02", "NPC EarR [EarR]Bone01", "NPC EarR [EarR]Bone02",
               *["TailBone0" + str(i) for i in range(1, 6)], "NPC L Breast P1", "NPC R Breast P1")
    pivots = [list(skel.nodes[node].global_transform.translation) for node in drivers]
    out.mkdir(parents=True, exist_ok=False)
    pending = out / "FAILED-unverified-do-not-install"
    pending.write_text("Motion bounds build incomplete.\n")
    target = out / bounds.MESH
    target.mkdir(parents=True)
    report = {"schema": "claw-motion-bounds/1", "status": "building", "sourceSha256": pins,
              "sourceFilesSha256": sources, "skeletonSha256": rig.sha256(skeleton), "driverPivots": dict(zip(drivers, pivots)),
              "nominalEnvelope": {"maximumJointChain": 5, "translationPerAxis": .5, "rotationPerEulerAxisRadians": .0105,
                                  "leverMargin": 1., "packedSumMargin": 1.001},
              "assumptions": ["Unit actor/node scale and adapter amplitude; no external driver, collision/armor pushup or animation displacement",
                              "Input spheres already contain the selected named morph0..1 domain; original center retained",
                              "Nominal FSMP constraints can numerically overshoot; runtime tracing remains required"],
              "gameValidated": False, "shapes": {}, "outputSha256": {}}
    for name in names:
        destination = target / name
        if name.endswith(".tri"):
            shutil.copyfile(source / name, destination)
            continue
        nif = Nif((source / name).read_bytes())
        readback = api.NifFile(str(source / name))
        details = []
        for shape in readback.shapes:
            center = list(shape.properties.boundingSphereCenter)
            radius = float(shape.properties.boundingSphereRadius)
            old = struct.pack("<4f", *center, radius)
            block = nif.blocks[shape.id]
            if block.count(old) != 1:
                raise ValueError("Cannot uniquely locate current sphere: " + shape.name)
            extra = motion_bound_extra(center, radius, pivots)
            new_radius = float(np.nextafter(np.float32(radius + extra), np.float32(np.inf)))
            offset = block.index(old)
            nif.blocks[shape.id] = block[:offset] + struct.pack("<4f", *center, new_radius) + block[offset + 16:]
            details.append({"shape": shape.name, "center": center, "inputRadius": radius,
                            "nominalMotionExtra": extra, "outputRadius": new_radius})
        destination.write_bytes(nif.bytes())
        changed = bounds.bounds_only(source / name, destination, api)
        if len(changed) != len(readback.shapes):
            raise ValueError("Every selected shape needs its explicit motion margin")
        report["shapes"][name] = details
    if pins != {name: rig.sha256(source / name) for name in names} or any(rig.sha256(path) != value for path, value in sources.items()):
        raise ValueError("Motion bounds input/source changed")
    report["outputSha256"] = {name: rig.sha256(target / name) for name in names}
    report["status"] = "nominal-motion-spheres-built-solver-and-game-pending"
    (out / "motion-bounds-report.json").write_text(json.dumps(report, indent=2) + "\n")
    pending.unlink()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.out), indent=2))
