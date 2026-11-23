"""Project the self-contact test cues into a measured wolf-player scene."""

import argparse
import json
from pathlib import Path

from stage_player_contact import pinned, require
from player_contact_custody import CONFIG_SHA
from verify_equipped_turnover import TOPOLOGY_SCHEMA, route
from verify_tail_refit import MARGIN, NANO, QPC, Subject, bank_gap, inspect_frame, numbers, positive_int
from cbpc_vr_geometry import PLAYER, _sphere


CUE_SHA = "040ff2ac67fd91cf4ce8a925d176a6ce76a72b766d4486ebc8489c5c7dd3d43c"


def retarget(frame, anchors, geometry):
    left, target = frame["left"], frame["targetPose"]
    source = frame["source"]
    result = {}
    for phase in ("near", "far"):
        local = numbers(anchors[phase]["handFromTargetBoneGu"], 3)
        center, _ = _sphere(target, local, 1.)
        translation = [old + desired - current for old, desired, current in zip(left["translation"], center, source, strict=True)]
        wand = {**left, "translation": translation}
        center, radius = _sphere(wand, (0., -6., -2.), 3.)
        gap = bank_gap({**frame, "left": wand, "source": center}, geometry)
        require(gap <= -MARGIN if phase == "near" else gap >= MARGIN,
                f"The {phase} cue has insufficient fitted clearance with the measured controller and bone scales")
        result[phase] = {"leftWand": wand, "sphereCenterGu": center, "sphereRadiusGu": radius, "signedGapGu": gap}
    return result


def plan(row, topology, fixture_forms, subject, config, cues, arm, sex):
    profile = config["arms"][arm]
    anchors = cues["results"][sex]["arms"][arm]
    node = profile["node"]
    require(anchors["targetNode"] == node and anchors["sourceSlotIndices"] == profile["slots"],
            "Morphbench cues describe a different target or capsule set")
    scene = inspect_frame([row], 0, subject, node, own_body=True)
    handle = scene["player"][0]["runtimeHandle"]
    require(topology["schema"] == TOPOLOGY_SCHEMA, "Expected the adjacent equipped Body32 topology /8 reply")
    evidence = route(topology, (subject.pid, topology["epoch"], subject.base, subject.cell, handle, int(sex == "female")),
                     topology["nonce"], fixture_forms, equipped=True)
    require(evidence["observedActorWeight"] == 0. and evidence["captureClock"]["qpcEnd"] < scene["ns"] * QPC // NANO,
            "Expected the measured weight-zero equipped player after the topology sample")
    targets = retarget(scene, anchors, [capsule["geometry"] for capsule in profile["capsules"][sex]])
    return {"observerSession": scene["session"], "observerSample": scene["sample"], "actor": PLAYER,
            "runtimeHandle": handle, "node": node, "slots": profile["slots"],
            "units": "skyrim_engine_units", "unchangedControls": scene["controls"], "targets": targets,
            "hardwareReachVerified": False, "controllerMappingVerified": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("scene", "topology", "config", "cues"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--fixture-forms", nargs=2, type=lambda text: int(text, 0), required=True, metavar=("ITEM", "ADDON"))
    parser.add_argument("--arm", choices=("left-ear", "tail"), required=True)
    parser.add_argument("--sex", choices=("male", "female"), required=True)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--cell", type=lambda text: int(text, 0), required=True)
    args = parser.parse_args()
    try:
        require(positive_int(args.pid) and positive_int(args.cell) and args.cell <= 0xFFFFFFFF, "Explicit VR process and cell required")
        print(json.dumps(plan(json.loads(args.scene.read_bytes()), json.loads(args.topology.read_bytes()), tuple(args.fixture_forms),
                              Subject(args.pid, PLAYER, 7, args.cell, 0),
                              json.loads(pinned(args.config, CONFIG_SHA)), json.loads(pinned(args.cues, CUE_SHA)),
                              args.arm, args.sex), indent=2, allow_nan=False))
    except (KeyError, TypeError, ValueError, OSError) as error:
        parser.exit(1, f"{error}\n")
