"""Measure and refit existing Havok bodies at explicit TRI states, offline only.

Uses Morphbench's public facade. Node-local CBPC capsules and Havok ragdoll
frames are deliberately separate; this tool never exports one as the other.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import numpy as np


def pin(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    if data.startswith(b"version https://git-lfs.github.com/spec/v1"):
        raise ValueError("Unmaterialized LFS input: " + str(path))
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def signed_distances(points, capsules):
    """Exact outside-union distance; negative interior is a per-capsule proxy.

    The minimum signed capsule field establishes membership, but is not distance
    to the union boundary inside overlapping capsules. Do not use its negative
    side to certify maximum protrusion of an overlapping bundle.
    """
    points = np.asarray(points, dtype=np.float64).reshape(-1, 3)
    if not np.isfinite(points).all() or not capsules:
        raise ValueError("Finite points and at least one capsule required")
    distances = np.full(len(points), np.inf)
    for capsule in capsules:
        a, b = (np.asarray(capsule[k], dtype=np.float64) for k in ("p1", "p2"))
        radius = float(capsule["radius"])
        if a.shape != (3,) or b.shape != (3,) or not np.isfinite([*a, *b, radius]).all() or radius <= 0:
            raise ValueError("Invalid capsule")
        axis = b - a
        length2 = float(axis @ axis)
        t = np.clip((points - a) @ axis / length2, 0, 1) if length2 > 1e-20 else np.zeros(len(points))
        one = np.linalg.norm(points - (a + t[:, None] * axis), axis=1) - radius
        distances = np.minimum(distances, one)
    return distances


def metrics(points, capsules):
    if not len(points):
        return {"points": 0, "measured": False}
    distances = signed_distances(points, capsules)
    return {"points": len(points), "measured": True,
            "outsideFraction": float(np.mean(distances > 1e-5)),
            "worstOutside": float(max(0, distances.max())),
            "meanSignedCapsuleProxy": float(distances.mean()),
            "insideCapsuleProxyP95": float(np.percentile(np.maximum(0, -distances), 95)),
            "absoluteCapsuleProxyP95": float(np.percentile(abs(distances), 95)),
            "interiorIsUnionBoundaryDistance": False}


def sample_states(names):
    names = sorted(names)
    if not names or len(names) != len(set(names)):
        raise ValueError("Nonempty unique morph names required")
    return ([{"name": "neutral", "values": {}}] +
            [{"name": name + "-1", "values": {name: 1.0}} for name in names] +
            [{"name": "mixed-035", "values": dict.fromkeys(names, .35)},
             {"name": "mixed-1", "values": dict.fromkeys(names, 1.0)},
             {"name": "return-neutral", "values": {}}])


def measure(points_by_bone, colliders):
    return [{"bone": row["bone"], "capsuleCount": len(row["capsules"]),
             **metrics(points_by_bone[row["bone"]], row["capsules"])} for row in colliders]


def transform_matrix(buf):
    """Public PyNifly transform buffer, column-vector convention."""
    if buf is None:
        raise ValueError("Missing explicit bind transform")
    matrix = np.eye(4, dtype=np.float64)
    matrix[:3, :3] = np.asarray([list(row) for row in buf.rotation]) * float(buf.scale)
    matrix[:3, 3] = list(buf.translation)
    if not np.isfinite(matrix).all() or abs(np.linalg.det(matrix[:3, :3])) < 1e-12:
        raise ValueError("Invalid bind transform")
    return matrix


def apply_lbs(matrices, vertices):
    """Apply the complete weighted rest-node/bind product to each morph vertex."""
    vertices = np.asarray(vertices, dtype=np.float64).reshape(-1, 3)
    matrices = np.asarray(matrices, dtype=np.float64)
    if matrices.shape != (len(vertices), 4, 4) or not np.isfinite(matrices).all() or not np.isfinite(vertices).all():
        raise ValueError("Finite per-vertex LBS matrices required")
    homogeneous = np.column_stack((vertices, np.ones(len(vertices))))
    return np.einsum("nij,nj->ni", matrices, homogeneous)[:, :3]


def skin_data(pynifly, body_path, skeleton_path, parts, collision_bones, minimum=.5):
    """Read actual bind transforms/weights with public bindings, not a NIF parser.

    A selected vertex belongs to its greatest-weight bone, then to the nearest
    collision-bearing ancestor. All its weights, including nondominant ones,
    contribute to the rest-LBS pose. The selection threshold is not a skinning
    approximation.
    """
    body, skeleton = pynifly.NifFile(str(body_path)), pynifly.NifFile(str(skeleton_path))
    nodes = skeleton.nodes
    parents = {name: node.parent.name if node.parent is not None else None for name, node in nodes.items()}
    owners = set(collision_bones)
    result, summaries = {}, []
    for shape in body.shapes:
        if shape.name not in parts:
            continue
        vertices = np.asarray(shape.verts, dtype=np.float64).reshape(-1, 3)
        count = len(vertices)
        if not shape.has_global_to_skin:
            raise ValueError("Explicit global-to-skin transform required: " + shape.name)
        global_to_skin = transform_matrix(shape.global_to_skin)
        blended = np.zeros((count, 4, 4), dtype=np.float64)
        sums, best = np.zeros(count), np.zeros(count)
        dominant = np.full(count, "", dtype=object)
        bindings = []
        for bone, pairs in shape.bone_weights.items():
            pairs = list(pairs)
            if not pairs:
                continue
            if bone not in nodes:
                raise ValueError("Skin bone missing from supplied skeleton: " + bone)
            indices = np.asarray([int(pair[0]) for pair in pairs], dtype=np.int64)
            weights = np.asarray([float(pair[1]) for pair in pairs], dtype=np.float64)
            if len(set(indices.tolist())) != len(indices) or np.any(indices < 0) or np.any(indices >= count):
                raise ValueError("Invalid/duplicate skin indices")
            if not np.isfinite(weights).all() or np.any(weights < 0):
                raise ValueError("Invalid skin weights")
            rest_node = transform_matrix(nodes[bone].global_transform)
            skin_to_bone = transform_matrix(shape.get_shape_skin_to_bone(bone))
            product = rest_node @ skin_to_bone @ global_to_skin
            blended[indices] += weights[:, None, None] * product
            sums[indices] += weights
            take = weights > best[indices]
            dominant[indices[take]] = bone
            best[indices[take]] = weights[take]
            bindings.append({"bone": bone, "weightedVertices": len(indices),
                             "restNode": rest_node.tolist(), "skinToBone": skin_to_bone.tolist(),
                             "restProduct": product.tolist()})
        # Do not silently normalize a materially different stored weight vector.
        if np.any(abs(sums - 1) > .005):
            raise ValueError("Unnormalized/unweighted skin vertices: " + shape.name)
        selected = {bone: [] for bone in collision_bones}
        omitted = {"belowOwnershipThreshold": 0, "noCollisionAncestor": 0}
        for index, source_bone in enumerate(dominant):
            if best[index] < minimum:
                omitted["belowOwnershipThreshold"] += 1
                continue
            bone, seen = source_bone, set()
            while bone and bone not in owners:
                if bone in seen:
                    raise ValueError("Skeleton parent cycle")
                seen.add(bone)
                bone = parents.get(bone)
            if bone:
                selected[bone].append(index)
            else:
                omitted["noCollisionAncestor"] += 1
        selected = {bone: np.asarray(indices, dtype=np.int64) for bone, indices in selected.items()}
        rest = apply_lbs(blended, vertices)
        result[shape.name] = {"raw": vertices, "matrices": blended, "selected": selected}
        summaries.append({"shape": shape.name, "vertices": count,
                          "selected": sum(len(indices) for indices in selected.values()), "omitted": omitted,
                          "maxWeightSumResidual": float(abs(sums - 1).max()),
                          "weightsRenormalized": False,
                          "globalToSkin": global_to_skin.tolist(), "shapeTransform": transform_matrix(shape.transform).tolist(),
                          "maxRawToRestDisplacement": float(np.linalg.norm(rest - vertices, axis=1).max()),
                          "bindings": bindings})
    if set(result) != set(parts):
        raise ValueError("Missing explicitly selected bound skin shape")
    return result, summaries


def posed_points(mb, skins, bones):
    chunks = {bone: [] for bone in bones}
    for name, skin in skins.items():
        rest = apply_lbs(skin["matrices"], mb.deformed(name))
        for bone, indices in skin["selected"].items():
            if len(indices):
                chunks[bone].append(rest[indices])
    return {bone: np.concatenate(rows) if rows else np.empty((0, 3)) for bone, rows in chunks.items()}


def infer_frame(read_world_endpoint, probe_span=1000., tolerance=.005):
    """Recover a frame using public numeric setters/readers with rounded output.

    The caller uses a disposable rig. Large independent probes reduce the .001
    game-unit reporting quantization; a held-out combined probe bounds error.
    """
    origin = np.asarray(read_world_endpoint([0, 0, 0]), dtype=np.float64)
    basis = np.column_stack([(np.asarray(read_world_endpoint(axis * probe_span)) - origin) / probe_span for axis in np.eye(3)])
    singular = np.linalg.svd(basis, compute_uv=False)
    if not np.isfinite(basis).all() or np.linalg.det(basis) <= 0 or singular.min() < 1e-8:
        raise ValueError("Invalid ragdoll frame probe")
    if singular.max() - singular.min() > 1e-5:
        raise ValueError("Nonuniform/sheared ragdoll frame cannot be represented by a capsule")
    matrix = np.eye(4)
    matrix[:3, :3], matrix[:3, 3] = basis, origin
    heldout = np.array([500., -333., 777.])
    predicted = basis @ heldout + origin
    actual = np.asarray(read_world_endpoint(heldout), dtype=np.float64)
    residual = float(np.max(abs(predicted - actual)))
    if residual > tolerance:
        raise ValueError("Rounded public frame probe exceeded its error limit")
    return matrix, {"probeSpan": probe_span, "reportingResolution": .001,
                    "heldoutPoint": heldout.tolist(), "heldoutMaxCoordinateResidual": residual,
                    "maximumAcceptedResidual": tolerance, "matrix": matrix.tolist()}


def body_frames(probe, bones):
    frames, receipts = {}, []
    for bone in bones:
        def read(endpoint):
            probe.collider_set(bone, 0, p1=endpoint, p2=endpoint, radius=1.)
            row = next(row for row in probe.colliders(bone) if row["bone"] == bone)
            return row["capsules"][0]["p1"]
        frames[bone], receipt = infer_frame(read)
        receipts.append({"bone": bone, **receipt})
    return frames, receipts


def fit_capsule(points, percentile):
    """PCA capsule in the supplied body frame, with explicit percentile coverage."""
    points = np.asarray(points, dtype=np.float64).reshape(-1, 3)
    if len(points) < 4 or not np.isfinite(points).all():
        return None
    centre = points.mean(axis=0)
    _, _, vh = np.linalg.svd(points - centre, full_matrices=False)
    axis = vh[0]
    # Fix PCA sign for deterministic slice order across an identical state.
    if axis[np.argmax(abs(axis))] < 0:
        axis = -axis
    along = (points - centre) @ axis
    radial = np.linalg.norm(points - centre - along[:, None] * axis, axis=1)
    radius = float(np.percentile(radial, percentile))
    if radius <= 1e-6:
        return None
    inside = radial <= radius
    slack = np.sqrt(np.maximum(0, radius * radius - radial[inside] ** 2))
    lower, upper = float(np.min(along[inside] + slack)), float(np.max(along[inside] - slack))
    half = max(0., (upper - lower) / 2)
    mid = centre + axis * ((upper + lower) / 2)
    return {"p1": (mid - half * axis).tolist(), "p2": (mid + half * axis).tolist(), "radius": radius}


def fit_posed(mb, points_by_bone, frames, percentile, original):
    rows = []
    previous = {row["bone"]: row for row in original}
    for row in mb.colliders():
        bone = row["bone"]
        points = points_by_bone[bone]
        count = len(row["capsules"])
        if len(points) < max(4, 12 * count):
            if row["capsules"] != previous[bone]["capsules"]:
                raise ValueError("Unfitted body was changed during bundle allocation: " + bone)
            rows.append({"bone": bone, "points": len(points), "fitted": False, "reason": "Too few selected vertices for allocated bundle"})
            continue
        inverse = np.linalg.inv(frames[bone])
        local = (np.column_stack((points, np.ones(len(points)))) @ inverse.T)[:, :3]
        _, _, vh = np.linalg.svd(local - local.mean(axis=0), full_matrices=False)
        axis = vh[0]
        if axis[np.argmax(abs(axis))] < 0:
            axis = -axis
        order = np.argsort((local - local.mean(axis=0)) @ axis, kind="stable")
        fitted = [fit_capsule(local[chunk], percentile) for chunk in np.array_split(order, count)]
        if any(cap is None for cap in fitted):
            if row["capsules"] != previous[bone]["capsules"]:
                raise ValueError("Degenerate body was changed during bundle allocation: " + bone)
            rows.append({"bone": bone, "points": len(points), "fitted": False, "reason": "Degenerate selected point cloud"})
            continue
        for index, cap in enumerate(fitted):
            mb.collider_set(bone, index, **cap)
        rows.append({"bone": bone, "points": len(points), "fitted": True, "count": count,
                     "method": "PCA axis slices of actual rest-LBS vertices; public setters into allocated bundle"})
    return rows


def verify_serialized(expected, actual, original):
    if len(expected) != len(actual) or len(expected) != len(original):
        raise ValueError("Serialized collision body count changed")
    for planned, saved, previous in zip(expected, actual, original, strict=True):
        for key in ("bone", "kind", "physics", "ragdoll"):
            if planned[key] != saved[key] or previous[key] != saved[key]:
                raise ValueError("Serialized collision identity/properties/frame changed: " + planned["bone"])
        if len(planned["capsules"]) != len(saved["capsules"]):
            raise ValueError("Serialized capsule bundle lost")
        for a, b in zip(planned["capsules"], saved["capsules"], strict=True):
            for key in ("p1", "p2", "radius"):
                if not np.allclose(a[key], b[key], rtol=0, atol=.002):
                    raise ValueError("Serialized capsule geometry changed")
    return {"passed": True, "bodies": len(actual), "capsules": sum(len(row["capsules"]) for row in actual),
            "maximumGeometryDifferenceAllowed": .002,
            "scope": "Public numeric geometry, identity, returned physics properties and ragdoll departure; not active Havok or constraint/inertia acceptance"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--body", type=Path, required=True)
    parser.add_argument("--tri", type=Path, required=True)
    parser.add_argument("--skeleton", type=Path, required=True)
    parser.add_argument("--hkx", type=Path, required=True)
    parser.add_argument("--morphbench", type=Path, required=True, help="Morphbench repository")
    parser.add_argument("--pynifly", type=Path, required=True, help="Explicit io_scene_nifly dependency directory")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--bundle", type=int, choices=(1, 2, 3), default=2)
    parser.add_argument("--percentile", type=float, default=95)
    args = parser.parse_args(argv)
    if not 0 < args.percentile <= 100:
        parser.error("percentile must be in (0,100]")
    source = Path(__file__).resolve()
    safety_spec = importlib.util.spec_from_file_location("claw_fit_safety", source.with_name("fit-colliders.py"))
    safety = importlib.util.module_from_spec(safety_spec)
    safety_spec.loader.exec_module(safety)
    inputs = [source, source.with_name("fit-colliders.py"), args.body, args.tri, args.skeleton, args.hkx]
    out = safety.validate_destination(args.out, inputs, None)
    mb_root = args.morphbench.resolve()
    pynifly_root = args.pynifly.resolve()
    inputs += [mb_root / "mb.py", *sorted((mb_root / "morphbench").rglob("*.py")),
               *sorted((pynifly_root / "pyn").rglob("*.py")), pynifly_root / "NiflyDLL.dll",
               Path(sys.executable), Path(np.__file__)]
    numpy_root = Path(np.__file__).resolve().parent
    inputs += [*sorted(numpy_root.rglob("*.pyd")), *sorted(numpy_root.rglob("*.dll")),
               *sorted((numpy_root.parent / "numpy.libs").glob("*.dll"))]
    # Morphbench's public open_skeleton also tries the adjacent HKX before the
    # explicit one is selected. Retain that consumed input if it differs.
    adjacent = [p for p in args.skeleton.resolve().parent.iterdir()
                if p.name.lower() == args.skeleton.stem.lower() + ".hkx"]
    inputs += [path for path in adjacent if path.resolve() != args.hkx.resolve()]
    inputs = list(dict.fromkeys(path.resolve() for path in inputs))
    # Recheck after dependency discovery as well: an output beneath a selected
    # PyNifly/numpy/Morphbench source folder is not an external audit location.
    out = safety.validate_destination(args.out, inputs, None)
    captured = [pin(p) for p in inputs]
    out.mkdir(parents=True)
    marker = out / "FAILED-unverified-do-not-install"
    marker.write_text("Offline audit incomplete. Do not install.\n", encoding="utf-8")
    manifest = {"schemaVersion": 1, "status": "incomplete", "inputs": captured,
                "startedAt": datetime.now(timezone.utc).isoformat(),
                "gameValidated": False, "installed": False, "dynamicHavok": False,
                "frame": "supplied-skeleton-rest-model-space-game-units-via-actual-LBS",
                "parts": ["body", "head", "claws"], "ownershipMinimum": .5,
                "percentile": args.percentile, "bundle": args.bundle,
                "scope": "Dominant-weight selected skin vertex samples, actual per-vertex rest-node/bind LBS, explicit sampled TRI states. No surface-area, animated-contact, runtime world or continuous-domain acceptance.",
                "unionMetricLimit": "Outside distance/membership is exact for capsule union. All negative/interior metrics are per-capsule proxy fields, not distance to the union boundary inside overlaps.",
                "python": {"executable": sys.executable, "version": sys.version},
                "numpy": {"version": np.__version__, "packageFile": np.__file__}}
    try:
        sys.path.insert(0, str(mb_root))
        from morphbench.api import MorphBench
        from morphbench.config import Config, DEFAULTS
        import morphbench.api as mb_api
        if not Path(mb_api.__file__).resolve().is_relative_to(mb_root):
            raise ValueError("Loaded Morphbench is not the explicitly pinned repository")
        config_path = out / "morphbench-settings.json"
        config_path.write_text(json.dumps({**DEFAULTS, "language": "en", "logFile": "",
                                           "pynifly": str(pynifly_root),
                                           "colliderMinWeight": .5, "bundleMinPoints": 12}), encoding="utf-8")
        mb = MorphBench(Config(config_path))
        mb.open(args.body, args.tri, args.skeleton)
        mb.open_ragdoll(args.hkx)
        from pyn import pynifly, niflydll
        if not Path(pynifly.__file__).resolve().is_relative_to(pynifly_root):
            raise ValueError("Loaded PyNifly is not the explicitly pinned wrapper")
        if Path(niflydll.nifly_path).resolve() != (pynifly_root / "NiflyDLL.dll").resolve():
            raise ValueError("Loaded NiflyDLL differs from explicit dependency (including development environment override)")
        manifest["actualLoadedDependencies"] = {"morphbench": str(Path(mb_api.__file__).resolve()),
                                               "pynifly": str(Path(pynifly.__file__).resolve()),
                                               "NiflyDLL": str(Path(niflydll.nifly_path).resolve())}
        manifest["ragdoll"] = mb.ragdoll()
        if manifest["ragdoll"].get("state") != "read" or manifest["ragdoll"].get("unmatched"):
            raise ValueError("Readable fully matched explicit ragdoll required")
        present = {s["name"] for s in mb.shapes()}
        if not set(manifest["parts"]).issubset(present):
            raise ValueError("Missing explicitly selected skin parts")
        mb.only(manifest["parts"])
        original = mb.colliders()
        bones = [row["bone"] for row in original]
        skins, skin_summary = skin_data(pynifly, args.body, args.skeleton, manifest["parts"], bones)
        for name, data in skins.items():
            if not np.allclose(mb.deformed(name), data["raw"], rtol=0, atol=1e-6):
                raise ValueError("Public mesh readers disagree on original vertices")
        manifest["restSkinning"] = {"formula": "sum(weight * restNode * skinToBone * globalToSkin * (rawVertex + TRI delta))",
                                   "skinningPose": "Exact supplied skeleton NIF rest nodes; no animation, actor transform, node override or game session",
                                   "shapeTransformNotSubstitutedForBinds": True, "shapes": skin_summary}
        probe = MorphBench(Config(config_path))
        probe.open_skeleton(args.skeleton)
        probe.open_ragdoll(args.hkx)
        frames, manifest["ragdollFrameProbes"] = body_frames(probe, bones)
        manifest["ragdollFramePrecisionLimit"] = "Public setters/readers report .001-unit rounded endpoints; 1000-unit probes with held-out residual <=.005. Fits are not exact continuous-space guarantees."
        neutral_fitted = None
        rows = []
        for state in sample_states(mb.morphs()):
            mb.reset_sliders()
            mb.set_sliders(state["values"])
            mb.open_skeleton(args.skeleton)
            mb.open_ragdoll(args.hkx)
            points = posed_points(mb, skins, bones)
            original_measure = measure(points, original)
            # Public facade creates finite bundles. Its raw-vertex fit is used
            # only for allocation; each successful body is overwritten below
            # from actual rest-LBS points before any candidate is saved.
            allocation = mb.collider_fit(percentile=args.percentile, bundle=args.bundle, split="axis")
            fit = fit_posed(mb, points, frames, args.percentile, original)
            fitted = mb.colliders()
            if neutral_fitted is None:
                neutral_fitted = fitted
            neutral_measure = measure(points, neutral_fitted)
            row = {**state, "original": original_measure, "neutralCandidate": neutral_measure,
                   "refitted": measure(points, fitted), "fit": fit,
                   "unfittedBodies": [entry for entry in fit if not entry["fitted"]],
                   "bundleAllocation": allocation, "worldCapsules": fitted,
                   "worldCapsulesFrame": manifest["frame"], "ragdollLocalCapsules": mb.collider_local()}
            if state["name"] in ("neutral", "mixed-1"):
                name = state["name"] + "-skeleton-candidate.nif"
                candidate = out / name
                row["candidate"] = pin(mb.collider_save(candidate))
                reader = MorphBench(Config(config_path))
                reader.open_skeleton(candidate)
                reader.open_ragdoll(args.hkx)
                row["serializedReadback"] = verify_serialized(fitted, reader.colliders(), original)
                if state["name"] == "neutral":
                    manifest["neutralCandidate"] = row["candidate"]
                    manifest["neutralSerializedReadback"] = row["serializedReadback"]
            if state["name"] == "return-neutral":
                row["identicalNeutralGeometry"] = all(
                    a["capsules"] == b["capsules"] for a, b in zip(neutral_fitted, fitted, strict=True))
                if not row["identicalNeutralGeometry"]:
                    raise ValueError("Identical neutral coefficients did not restore identical offline capsule geometry")
            rows.append(row)
        manifest["states"] = rows
        manifest["configuration"] = pin(config_path)
        if captured != [pin(p) for p in inputs]:
            raise ValueError("Source changed during audit")
        state = subprocess.run(["git", "-C", str(mb_root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        manifest["morphbenchCommit"] = state.stdout.strip()
        manifest["status"] = "offline-sampled-candidates-only"
        manifest["completedAt"] = datetime.now(timezone.utc).isoformat()
        (out / "morph-collider-audit.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        marker.unlink()
        print(json.dumps({"status": manifest["status"], "states": len(rows), "bones": len(original), "out": str(out)}))
        return 0
    except Exception as exc:
        manifest["error"] = str(exc)
        (out / "failed-audit.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
