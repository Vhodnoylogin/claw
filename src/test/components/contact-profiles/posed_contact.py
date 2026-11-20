"""Offline check of archived CLAW ear/tail capsule support against one VR pose."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT/"src/main/python"/part) for part in ("build-tools", "physics", "vr")]
import breast_rig
import contact_fit
from body_resource import read_json
from tri_patch import offsets

DEFAULT_OWNERS = {"NPC EarR [EarR]Bone01", "NPC EarR [EarR]Bone02", "TailBone03", "TailBone05"}
ALLOWED_OWNERS = DEFAULT_OWNERS | {"NPC EarL [EarL]Bone01", "NPC EarL [EarL]Bone02", "TailBone01", "TailBone02"}
IDENTITY_FIELDS = ("actor", "base", "runtimeHandle", "loadEpoch", "rootToken", "qpcBegin", "qpcEnd")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def world_matrix(world):
    rotation = np.asarray(world["rotationRowMajor"], dtype=float)
    translation = np.asarray(world["translation"], dtype=float)
    scale = world["scale"]
    require(rotation.shape == (9,) and translation.shape == (3,) and
            np.isfinite(rotation).all() and np.isfinite(translation).all() and
            type(scale) in (int, float) and np.isfinite(scale) and scale > 0,
            "Invalid pose transform")
    rotation = rotation.reshape(3, 3)
    require(np.allclose(rotation.T @ rotation, np.eye(3), atol=2e-4, rtol=0) and
            np.linalg.det(rotation) > 0, "Expected a proper rotation with separate uniform scale")
    result = np.eye(4)
    result[:3, :3] = rotation * scale
    result[:3, 3] = translation
    return result


def read_pose(pose, vector, model):
    sample = pose["sample"]
    require(pose["schema"] == "claw-vr-npc-pose/1" and pose["status"] == "ready" and
            sample["phase"] == "skse_main_thread_task" and sample["view"] == "third_person" and
            type(pose["sequence"]) is int and 0 <= pose["sequence"] <= 16 and
            pose["nonce"] == sample["rootToken"] and
            all(type(pose[field]) is int and pose[field] > 0 for field in ("pid", "qpcFrequency", "nonce")) and
            all(type(sample[field]) is int and sample[field] > 0 for field in IDENTITY_FIELDS) and
            0xFF000000 <= sample["actor"] < 0xFFFFFFFF and sample["qpcBegin"] <= sample["qpcEnd"],
            "Expected a bounded third-person native witness sample")
    require(vector["pid"] == pose["pid"] and vector["sequence"] == pose["sequence"] and
            all(vector[field] == sample[field] for field in IDENTITY_FIELDS) and
            vector["modelIdentity"] == model["modelIdentity"], "Morph vector does not belong to this pose/model")
    sex = vector["sex"]
    require(sex in ("male", "female") and sample["sex"] == ("male", "female").index(sex),
            "Morph vector sex differs from the observed actor")
    values = vector["morphs"]
    weight = vector["weight"]
    require(set(values) == set(model["morphs"]) and
            all(type(value) in (int, float) and np.isfinite(value) and 0 <= value <= 1
                for value in (*values.values(), weight)) and sample["weight"] / 100 == weight,
            "Expected all explicit normalized morphs and the observed normalized actor weight")
    nodes = sample["nodes"]
    frames = {row["name"]: world_matrix(row["world"]) for row in nodes}
    require(len(nodes) == len(frames), "Duplicate node names in witness sample")
    return sex, values, weight, frames


def owner_support(vertices, weights, binds, global_to_skin, frames, owner):
    require(owner in frames, "Missing owner world transform: " + owner)
    missing = sorted(set(weights) - frames.keys())
    require(not missing, "Missing influential bone world transforms: " + ", ".join(missing))
    inverse = np.linalg.inv(frames[owner])
    names = list(weights)
    columns = np.stack([weights[name] for name in names], axis=1)
    require(np.isfinite(columns).all() and (columns >= 0).all() and (columns.sum(axis=1) > 0).all(),
            "Each support vertex must retain positive packed skin weight")
    matrices = np.stack([inverse @ frames[name] @ binds[name] @ global_to_skin for name in names])
    result = breast_rig.lbs(vertices, columns, matrices[None], normalize=True)[0]
    require(np.isfinite(result).all(), "Posed support has nonfinite coordinates")
    return result


def compare_support(rest, posed, faces, padding):
    static = contact_fit.capsule(rest, padding)
    refit = contact_fit.capsule(posed, padding)
    return {name: {"capsule": capsule,
                   "maxAssignedExcess": max(0., float(contact_fit.signed_capsules(posed, [capsule]).max())),
                   "surface": contact_fit.surface_metrics(posed, faces, [capsule])}
            for name, capsule in (("static", static), ("refit", refit))}


def pinned_asset(model, filename):
    source, = [row for row in model["sourceInputs"] if Path(row["path"]).name.lower() == filename]
    path = Path(source["path"])
    raw = path.read_bytes()
    require(len(raw) == source["bytes"] and sha256(raw).hexdigest() == source["sha256"],
            "Archived source bytes changed: " + filename)
    return path, raw


class Skin:
    """Serialized vertex, packed weight and TRI inputs for one authored shape."""

    def __init__(self, shape, records, values):
        self.faces = np.asarray(shape.tris, dtype=int)
        self.vertices = np.asarray(shape.verts, dtype=float)
        self.names = list(shape.bone_weights)
        self.weights = breast_rig.read_weights(shape, self.names)
        self.binds = {name: breast_rig.matrix(shape.get_shape_skin_to_bone(name)) for name in self.names}
        self.global_to_skin = breast_rig.matrix(shape.global_to_skin)
        for (shape_name, morph, vertex), offset in records.items():
            value = values.get(morph, 0)
            if shape_name == shape.name and value:
                self.vertices[vertex] += value * (np.asarray(offset.packed) * offset.scale)

    def support(self, ids, frames, owner):
        rows = self.weights[ids]
        return owner_support(self.vertices[ids], {name: rows[:, i] for i, name in enumerate(self.names)
                             if np.any(rows[:, i] > 0)}, self.binds, self.global_to_skin, frames, owner)


def check(model, pose, vector, slot_indexes, pynifly=None):
    sex, values, weight, frames = read_pose(pose, vector, model)
    require(model["supportProfile"] == "vr-detailed-whole-body-v1" and len(model["slots"]) == 128,
            "Expected the archived conservative 128-slot VR contact model")
    slots = model["slots"]
    indexes = slot_indexes or [i for i, slot in enumerate(slots) if slot["node"] in DEFAULT_OWNERS]
    require(len(indexes) == len(set(indexes)) and all(0 <= i < len(slots) and
            slots[i]["node"] in ALLOWED_OWNERS and slots[i][sex] is not None for i in indexes),
            "Choose unique, active authored VR ear or tail slots")
    mesh_path, low = pinned_asset(model, sex+"bodywerewolf_0.nif")
    _, high = pinned_asset(model, sex+"bodywerewolf_1.nif")
    require(low == high, "Distinct mesh endpoints require their own verified interpolation")
    _, tri = pinned_asset(model, sex+"bodywerewolf.tri")
    skeleton_path, _ = pinned_asset(model, "skeleton.nif")
    api, _, _ = breast_rig.load_pynifly(pynifly)
    mesh = api.NifFile(str(mesh_path))
    skeleton = api.NifFile(str(skeleton_path))
    rest_frames = {name: breast_rig.matrix(node.global_transform) for name, node in skeleton.nodes.items()}
    tri_records = offsets(tri)
    skins = {name: Skin(mesh.shape_dict[name], tri_records, values) for name in ("body", "head")}
    scores = []
    for index in indexes:
        slot = slots[index]
        owner = slot["node"]
        region = model["regions"][sex+"/"+owner]
        source, = region["sources"]
        skin = skins[source["shape"]]
        partition = slot[sex]["partitionIndices"]
        triangle_ids = slot[sex]["triangleIndices"]
        require(partition == region["partitions"][slot["partition"]] and
                triangle_ids == region["triangleGroups"][slot["partition"]],
                "Slot no longer matches the archived partition")
        vertices = np.asarray(source["vertices"], dtype=int)
        faces = np.asarray(region["faces"], dtype=int)[triangle_ids]
        source_faces = np.asarray(source["sourceTriangleIndices"], dtype=int)[triangle_ids]
        require(np.array_equal(vertices[faces], skin.faces[source_faces]), "Archived source triangle correspondence changed")
        local_index = {v: i for i, v in enumerate(partition)}
        local_faces = [[local_index[v] for v in face] for face in faces]
        ids = vertices[partition]
        require(not region.get("axisHints") and not region.get("contactPasses"), "Expected the canonical enclosing fitter")
        rest = contact_fit.deform(region, {name: values[name] for name in region["morphs"]}, weight)[partition]
        independent_rest = skin.support(ids, rest_frames, owner)
        error = float(abs(rest - independent_rest).max())
        require(error <= 1e-8, "Archived rest support does not match the exact serialized NIF/TRI")
        posed = skin.support(ids, frames, owner)
        scores.append({"slot": index, "owner": owner, "vertices": len(ids), "triangles": len(local_faces),
                       "restEquivalenceMax": error, **compare_support(rest, posed, local_faces, region["padding"])})
    return {"schema": "claw-posed-contact-geometry/1", "modelIdentity": model["modelIdentity"],
            "sex": sex, "weight": weight, "morphs": values, "pid": pose["pid"], "sequence": pose["sequence"],
            "qpcFrequency": pose["qpcFrequency"], **{field: vector[field] for field in IDENTITY_FIELDS},
            "distanceUnits": "capsule owner-local units", "slots": scores}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--pose", type=Path, required=True, help="Ready VR NPC pose witness response")
    parser.add_argument("--vector", type=Path, required=True, help="Complete normalized target vector bound to the pose")
    parser.add_argument("--pynifly", type=Path)
    parser.add_argument("--slot", action="append", type=int)
    args = parser.parse_args()
    raw = args.model.read_bytes()
    require(sha256(raw).hexdigest() == args.model_sha256, "Archived model SHA-256 differs")
    print(json.dumps(check(json.loads(raw), read_json(args.pose), read_json(args.vector), args.slot,
                           args.pynifly), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
