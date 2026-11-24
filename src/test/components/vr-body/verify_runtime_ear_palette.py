"""Classify the stock male VR ear binding captured by the Body32 test."""

import argparse
import json
from pathlib import Path

from verify_dispatch_markers import object_value, require, unique_json_object

HEAD = "head_CLAWHead"
EARS = "head_CLAWHead_CLAWEars"
TRI = "actors/werewolfbeast/claw/firstperson/male/earworldtrial.tri"
EXPECTED = {3: "NPC Head [Head]", 8: "NPC EarL [EarL]Bone01", 10: "NPC EarL [EarL]Bone02"}


def bound_to_world(row):
    if row.get("bone") != row["expected"] or row.get("worldTransformPresent") is not True:
        return False
    if row["boneMembership"].get("worldActor") is not True:
        return False
    return all(row[owner].get(relation) is True for owner in ("worldActor", "skinRoot")
               for relation in ("found", "sameBone", "sameTransform"))


def verify_runtime_ear_palette(summary):
    summary = object_value(summary, "summary")
    morph_state = object_value(summary.get("stockMorphState"), "stockMorphState")
    require(summary.get("pending") is None and morph_state.get("status") == 2,
            "Expected the settled stock wolf with applied morphs")
    capture = summary["captures"]["stock"]
    require(capture.get("view") == "thirdPerson" and capture.get("sex") == 0,
            "Expected a male third-person topology capture")
    world = [row for row in capture["observations"]
             if row.get("view") == "thirdPerson" and row.get("bank") == "active"]
    require(len(world) == 1 and (world[0].get("item"), world[0].get("addon")) == (0xCDD86, 0xCDD87)
            and type(world[0].get("clone")) is int and world[0]["clone"] > 0
            and world[0]["clone"] != world[0].get("actorRoot"), "Expected an attached stock Body32 clone")
    measured = object_value(capture["meshSource"]["measured"], "measured shapes")
    require(measured.keys() == {HEAD, EARS}, "Expected the ear mesh and its adjacent head")
    inspected = {}
    for name, geometry in ((HEAD, (6980, 12733)), (EARS, (1354, 2394))):
        mesh = measured[name]
        tri = mesh.get("bodyTri")
        require(isinstance(tri, str) and tri.casefold().replace("\\", "/") == TRI and
                (mesh.get("partitionVertices"), mesh.get("partitionTriangles")) == geometry,
                f"Unexpected source topology or TRI for {name}")
        palette = object_value(mesh.get("runtimePalette"), name)
        membership = object_value(palette.get("rootMembership"), "skin root membership")
        require(palette.get("boneCount") == 17 and palette.get("matrixCount") in (0, 17)
                and membership.get("worldActor") is True,
                f"Unexpected world palette size or root for {name}")
        rows = palette.get("reviewedSlots")
        require(isinstance(rows, list) and len(rows) == len(EXPECTED) and
                all(isinstance(row, dict) for row in rows) and
                [(row.get("slot"), row.get("expected")) for row in rows] == list(EXPECTED.items()),
                f"Unexpected reviewed palette slots for {name}")
        for row in rows:
            for key in ("boneMembership", "worldActor", "skinRoot"):
                object_value(row.get(key), key)
        inspected[name] = palette
    ear = inspected[EARS]
    head, *left = ear["reviewedSlots"]
    require(ear["matrixCount"] == 17 and bound_to_world(head), "World head control is unavailable")
    return {"schema": "claw-vr-stock-ear-palette/1", "worldHeadControl": True,
            "leftEarBoundToWorld": {row["expected"]: bound_to_world(row) for row in left},
            "adjacentHeadMatrices": inspected[HEAD]["matrixCount"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.summary.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_json_object)
        report = verify_runtime_ear_palette(data)
    except (KeyError, OSError, TypeError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
