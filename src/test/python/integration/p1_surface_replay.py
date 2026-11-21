"""Replay the contribution of captured P1 bones to an authored NIF surface."""

from argparse import ArgumentParser
import hashlib
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[4]
P1 = {"leftP1": "NPC L Breast P1", "rightP1": "NPC R Breast P1"}


def node_matrix(pose):
    matrix = np.eye(4)
    matrix[:3, :3] = np.asarray(pose["rotation"], dtype=float).reshape(3, 3) * pose["scale"]
    matrix[:3, 3] = pose["translation"]
    if not np.isfinite(matrix).all() or pose["scale"] <= 0:
        raise ValueError("Expected a finite, positive-scale scene transform")
    return matrix


def surface_contribution(vertices, weights, captured_weights, transform_changes):
    """Compute only the measured bones' LBS terms, at fixed vertex positions and weights."""
    homogeneous = np.column_stack((vertices, np.ones(len(vertices))))
    for bone_weights, transforms in zip(captured_weights, transform_changes, strict=True):
        if len(bone_weights) != len(vertices) or transforms.shape != (4, 4):
            raise ValueError("A captured bone requires one influence per vertex and a 4x4 change")
    raw = np.einsum("bk,bij,kj->ki", captured_weights, transform_changes, homogeneous)[:, :3]
    return raw, raw / weights.sum(axis=1, keepdims=True)


def summarize(delta, weighted):
    ids = np.flatnonzero(weighted)
    distance = np.linalg.norm(delta[ids], axis=1)
    peak = ids[np.argmax(distance)]
    return {"influencedVertexCount": len(ids), "p95GU": float(np.quantile(distance, .95)),
            "maxGU": float(distance.max()), "maxVertex": int(peak), "maxXYZGU": delta[peak].tolist()}


def replay_surfaces(nif, rig, observations):
    changes = {}
    for lane, window in zip(("passive", "active"), observations, strict=True):
        for phase in ("afterStockWrite", "afterOuterUpdate"):
            changes[lane, phase] = {
                bone: node_matrix(window[phase][name]) - node_matrix(window["beforeStockWrite"][name])
                for name, bone in P1.items()
            }
    result = {}
    for shape in nif.shapes:
        names = tuple(shape.bone_weights)
        captured = [(bone, names.index(bone)) for bone in P1.values() if bone in names]
        if not captured:
            continue
        if not shape.has_global_to_skin:
            raise ValueError(f"Missing skin frame for {shape.name}")
        vertices = np.asarray(shape.verts, dtype=float)
        weights = rig.read_weights(shape, names)
        influence = weights[:, [index for _, index in captured]].T
        if not np.any(influence):
            continue
        global_to_skin = rig.matrix(shape.global_to_skin)
        binds = {bone: rig.matrix(shape.get_shape_skin_to_bone(bone)) @ global_to_skin for bone, _ in captured}
        for (lane, phase), matrices in changes.items():
            deltas = np.stack([matrices[bone] @ binds[bone] for bone, _ in captured])
            raw, normalized = surface_contribution(vertices, weights, influence, deltas)
            weighted = influence.any(axis=0)
            result.setdefault(shape.name, {}).setdefault(lane, {})[phase] = {
                "rawPacked": summarize(raw, weighted), "normalized": summarize(normalized, weighted),
            }
    if not result:
        raise ValueError("No P1 vertices in the selected mesh")
    return result


def read_pinned(path, digest):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError(f"Digest mismatch for {path.name}")
    return data


def main():
    parser = ArgumentParser(description=__doc__)
    for label in ("body", "replay"):
        parser.add_argument(label, type=Path)
        parser.add_argument(label + "_sha256")
    parser.add_argument("--pynifly", type=Path)
    args = parser.parse_args()
    read_pinned(args.body, args.body_sha256)
    replay = json.loads(read_pinned(args.replay, args.replay_sha256))
    sys.path.insert(0, str(ROOT / "src/main/python/physics"))
    from attachment_audit import helpers

    _, rig = helpers()
    api, _, _ = rig.load_pynifly(args.pynifly)
    surfaces = replay_surfaces(api.NifFile(str(args.body)), rig, replay["numericWorldByLane"])
    read_pinned(args.body, args.body_sha256)
    print(json.dumps({"bodySha256": args.body_sha256, "replaySha256": args.replay_sha256,
                      "scope": "Stored weight-100 vertices, P1 contribution only, no observed morph vector or pixels",
                      "surfaces": surfaces}, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
