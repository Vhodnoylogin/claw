"""Score the fixed breast-fur trial from owned SE World Observer pose samples."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import runpy
import sys

import numpy as np

import fsmp_probe as probe
from p1_surface_replay import node_matrix, read_pinned

ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / "src/main/python"
sys.path.insert(0, str(SOURCE / "physics"))
from attachment_audit import compose_morphs, measure_binding

POINTS = {"fur_belly": (577, 578, 579, 580, 581, 582), "head": (779, 1676, 1677)}
BARYCENTRIC = np.asarray((0.036153677056990685, 0.026443406809902925, 0.9374029161331064))


def validate_selection(names, morphs):
    probe.require(len(names) == len(set(names)) and 1 <= len(names) <= 16
                  and len(morphs) == len(set(morphs)) and 1 <= len(morphs) <= 32,
                  "Expected distinct observed nodes and morphs")


def request(reference, names, morphs):
    validate_selection(names, morphs)
    ref = probe.form(reference)
    return {"kind": "world_observer", "refs": [ref], "actors": True,
            "nodes": [{"ref": ref, "name": name, "firstPerson": False} for name in names],
            "skee": {"refs": [ref], "morphs": list(morphs)}}


def observe(raw, reference, base, names, morphs):
    validate_selection(names, morphs)
    ref = probe.form(reference)
    probe.require(int(ref, 16) >> 24 == 0xFF, "Expected a disposable owned actor")
    probe.require(raw.get("ok") is True and raw.get("quality") == "complete" and raw.get("schemaVersion") == 1
                  and raw.get("phase") == "skse_main_thread_task" and raw.get("space") == "world"
                  and raw.get("units") == "skyrim_engine_units" and raw.get("coherence") == probe.OBSERVATION
                  and isinstance(raw.get("sessionId"), str) and bool(raw["sessionId"])
                  and all(type(raw.get(key)) is int and raw[key] > 0
                          for key in ("loadGeneration", "sampleId", "producerMonotonicNs")),
                  "Incomplete World Observer snapshot")
    refs = raw.get("refs")
    probe.require(isinstance(refs, list) and len(refs) == 1, "Expected one owned actor")
    subject = refs[0]
    identity, root, actor = (subject[key] for key in ("identity", "rootIdentity", "actor"))
    probe.require(probe.form(identity["form"]) == ref and identity.get("loadGeneration") == raw["loadGeneration"]
                  and type(identity.get("runtimeHandle")) is int and identity["runtimeHandle"] > 0
                  and root.get("firstPerson") is False and root.get("identityBasis") ==
                  "sampled_pointer_and_handle_changes_no_object_retention"
                  and type(root.get("sampledRootToken")) is int and root["sampledRootToken"] > 0
                  and subject.get("status") == actor.get("status") == actor.get("raceStatus") == "available"
                  and subject.get("loaded3D") is True and subject.get("deleted") is False
                  and subject.get("disabled") is False and type(actor.get("sex")) is int and actor["sex"] == 1
                  and probe.form(subject["baseForm"]) == probe.form(actor["baseForm"]) == probe.form(base)
                  and probe.form(actor["race"]) == "0x000CDD84" and actor["weight"].get("status") == "available"
                  and actor["weight"]["rawNPCWeight"] == 100, "Wrong fixture or unavailable actor/root")
    rows = raw.get("nodes")
    probe.require(isinstance(rows, list) and len(rows) == len(names), "Missing or extra observed node")
    nodes = {}
    for row in rows:
        name = row.get("name")
        probe.require(name in names and name not in nodes and row.get("status") == "available"
                      and row.get("firstPerson") is False and row.get("form") == ref
                      and row.get("identity") == identity and row.get("rootIdentity") == root,
                      "Observed node differs from the sampled root or palette")
        nodes[name] = {"world": probe.transform(row["world"]), "local": probe.transform(row["local"])}
    observations = raw.get("skee")
    probe.require(isinstance(observations, list) and len(observations) == 1, "Expected one SKEE observation")
    value = observations[0]
    probe.require(isinstance(value, dict) and isinstance(value.get("provider"), dict),
                  "Missing SKEE provider provenance")
    provider = value["provider"]
    epoch = provider.get("interfaceEpoch")
    probe.require(value.get("status") == provider.get("status") == "available"
                  and value.get("form") == ref and value.get("identity") == identity
                  and value.get("rootIdentity") == root
                  and provider.get("interfaceVersion") == 5 and type(epoch) is int and epoch > 0,
                  "SKEE observation differs from the sampled root or provider")
    rows = value.get("morphs")
    probe.require(isinstance(rows, list) and len(rows) == len(morphs), "Missing effective morph values")
    coeffs = {}
    for item in rows:
        probe.require(isinstance(item, dict) and isinstance(item.get("aggregate"), dict)
                      and isinstance(item.get("keys"), dict), "Missing SKEE aggregate fields")
        name, aggregate, keys = item.get("name"), item["aggregate"], item["keys"]
        number = aggregate.get("value")
        probe.require(name in morphs and name not in coeffs
                      and item.get("status") == aggregate.get("status") == "available"
                      and aggregate.get("method") == "GetBodyMorphs"
                      and keys.get("status") == "available" and keys.get("truncated") is False
                      and type(number) in (int, float) and math.isfinite(number) and 0 <= number <= 1,
                      "Incomplete or invalid SKEE aggregate")
        coeffs[name] = float(number)
    probe.require(set(coeffs) == set(morphs), "Missing effective morph values")
    return {"guard": {"session": raw["sessionId"], "generation": raw["loadGeneration"],
                      "observerVersion": raw["observerVersion"], "identity": identity, "root": root,
                      "actor": actor, "skeeEpoch": epoch},
            "sample": raw["sampleId"], "time": raw["producerMonotonicNs"],
            "nodes": nodes, "root": probe.transform(subject["sceneTransform"]), "morphs": coeffs}


def observer_matrix(frame):
    return node_matrix({"rotation": frame["rotationRowMajor"], "scale": frame["scale"],
                        "translation": frame["translation"]})


def posed_bones(model, pose):
    return np.stack([observer_matrix(probe.relative(pose["nodes"][name]["world"], pose["root"]))
                     for name in model["names"]])


def deformation(model, pose, normalize):
    """Project stored vertices into the observed actor-root frame."""
    verts = compose_morphs(model["vertices"], model["morphs"], pose["morphs"])
    transforms = posed_bones(model, pose) @ model["binds"]
    homogeneous = np.column_stack((verts, np.ones(len(verts))))
    weights = model["weights"]
    if normalize:
        weights = weights / weights.sum(axis=1, keepdims=True)
    return np.einsum("nb,bij,nj->ni", weights, transforms[:, :3, :], homogeneous)


def model(nif, raw_morphs, rig, morph_names):
    shapes = {shape.name: shape for shape in nif.shapes}
    groups = {}
    for role, indices in POINTS.items():
        shape = shapes[role]
        points = list(indices)
        names = tuple(shape.bone_weights)
        weights = rig.read_weights(shape, names)[points]
        use = np.flatnonzero(np.any(weights > 0, axis=0))
        names = tuple(names[i] for i in use)
        probe.require(shape.has_global_to_skin, f"Missing skin frame for {role}")
        skin = rig.matrix(shape.global_to_skin)
        groups[role] = {"names": names, "vertices": np.asarray(shape.verts, dtype=float)[points],
                        "weights": weights[:, use],
                        "binds": np.stack([rig.matrix(shape.get_shape_skin_to_bone(n)) @ skin for n in names]),
                        "morphs": {n: rig.dense_morph(raw_morphs, role, n, len(shape.verts))[points]
                                   for n in morph_names if n in raw_morphs.get(role, {})}}
    return groups


def compare(models, before, after):
    probe.require(before["guard"] == after["guard"] and before["sample"] < after["sample"]
                  and before["time"] < after["time"], "Fresh observations of the same owned root required")
    probe.require(before["morphs"] == after["morphs"], "Effective SKEE coefficients changed between poses")
    result = {}
    for label, normalize in (("rawPacked", False), ("normalized", True)):
        result[label] = {}
        for variant, roles in models.items():
            poses = (before, after)
            head_skin = roles["head"]
            root_index = POINTS["fur_belly"].index(578)
            roots = np.asarray([deformation(roles["fur_belly"], pose, normalize)[root_index] for pose in poses])
            triangles = np.asarray([deformation(head_skin, pose, normalize) for pose in poses])
            old, new = (posed_bones(head_skin, pose)[:, :3, :3] for pose in poses)
            transport = np.stack([np.broadcast_to(np.eye(3), old.shape), new @ np.linalg.inv(old)])
            metrics = measure_binding(roots[:, None, :], triangles[:, None, :, :], BARYCENTRIC[None, :],
                                      head_skin["weights"][None, :, :], transport, roots[:1], triangles[:1])
            offsets = roots - np.einsum("i,pij->pj", BARYCENTRIC, triangles)
            result[label][variant] = {"rootToTriangleBefore": offsets[0].tolist(),
                                      "rootToTriangleAfter": offsets[1].tolist(),
                                      "transportedOffsetDriftGU": float(metrics["poseTransportedOffsetDrift"][1, 0])}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("baseline", "trial", "tri"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--pynifly", type=Path)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--base")
    parser.add_argument("--observations", type=Path, help="JSON array of two raw World Observer samples in capture order.")
    args = parser.parse_args()
    files = {"baseline": args.baseline, "candidate": args.trial, "tri": args.tri}
    pins = runpy.run_path(str(ROOT / "src/test/cpp/geometry_witness/make_manifest.py"))["PINS"]
    for name, path in files.items():
        read_pinned(path, pins[name])
    from attachment_audit import helpers

    hooks, rig = helpers()
    api, TripFile, _ = rig.load_pynifly(args.pynifly)
    shapes = TripFile.from_filepath(str(args.tri)).shapes
    morphs = sorted({name for fields in shapes.values() for name in fields})
    probe.require(set(morphs) == set(hooks.V4_PUBLIC_MORPHS), "Unexpected TRI morph catalog")
    models = {name: model(api.NifFile(str(files[name])), shapes, rig, morphs) for name in ("baseline", "candidate")}
    names = sorted({n for roles in models.values() for group in roles.values() for n in group["names"]})
    for name, path in files.items():
        read_pinned(path, pins[name])
    query = request(args.reference, names, morphs)
    if args.observations:
        if args.base is None:
            parser.error("--base is required to associate the observations with the owned actor")
        raw_a, raw_b = json.loads(args.observations.read_bytes())
        before, after = (observe(raw, args.reference, args.base, names, morphs) for raw in (raw_a, raw_b))
        result = {"inputs": pins, "samples": [before["sample"], after["sample"]],
                  "scope": "Counterfactual from exact file assets and sampled scene nodes/SKEE; pose is not solver/render synchronized.",
                  "geometry": compare(models, before, after)}
    else:
        result = query
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
