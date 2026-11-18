"""Read-only finite current-v4 breast attachment measurements; never edit resources."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / "build-tools"
SOURCE_BYTES = Path(__file__).read_bytes()
BREAST = "CLAWTorsoBreastSize"


def finite(value, shape=None):
    result = np.asarray(value, dtype=float)
    if not np.isfinite(result).all() or (shape is not None and result.shape != shape):
        raise ValueError("Unexpected shape or nonfinite numeric data")
    return result


def compose_morphs(vertices, fields, values):
    """Compose all declared fields before skinning, without clamping or extrapolation."""
    result = finite(vertices).copy()
    if result.ndim != 2 or result.shape[1] != 3 or not len(result):
        raise ValueError("Expected nonempty N by 3 geometry")
    for name, amount in values.items():
        if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not np.isfinite(amount) or not 0 <= amount <= 1:
            raise ValueError("Morph coefficients must be finite numbers in [0,1]")
        if name in fields:
            result += finite(fields[name], result.shape) * amount
    return result


def measure_binding(roots, triangles, bary, source_weights, rotations, neutral_roots, neutral_triangles):
    """Separate static morph changes from pose drift of the transported rest offset.

    Positions already use the declared raw/normalized LBS convention. Offset
    transport uses barycentric, per-skin-vertex normalized influence blends in
    both conventions, as a geometric diagnostic rather than a shader assertion.
    Pose zero must be rest, and rotations are posed-global times inverse rest.
    """
    roots = finite(roots)
    if roots.ndim != 3 or roots.shape[2] != 3 or min(roots.shape[:2]) == 0:
        raise ValueError("Expected pose by root by xyz positions")
    poses, count, _ = roots.shape
    triangles = finite(triangles, (poses, count, 3, 3))
    bary = finite(bary, (count, 3))
    weights = finite(source_weights)
    rotations = finite(rotations)
    if weights.ndim != 3 or weights.shape[:2] != (count, 3) or not weights.shape[2]:
        raise ValueError("Expected root by source-corner by bone weights")
    if (weights < 0).any() or (weights.sum(axis=2) <= 0).any():
        raise ValueError("Invalid source skin weights")
    if (bary < -1e-10).any() or not np.allclose(bary.sum(axis=1), 1, rtol=0, atol=1e-8):
        raise ValueError("Invalid barycentric weights")
    bones = weights.shape[2]
    rotations = finite(rotations, (poses, bones, 3, 3))
    if not np.allclose(rotations[0], np.eye(3), rtol=0, atol=1e-8):
        raise ValueError("First pose must be rest")
    neutral_roots = finite(neutral_roots, (count, 3))
    neutral_triangles = finite(neutral_triangles, (count, 3, 3))
    attach = np.einsum("prcj,rc->prj", triangles, bary)
    offset = roots - attach
    neutral_offset = neutral_roots - np.einsum("rcj,rc->rj", neutral_triangles, bary)
    blended = np.einsum("rcb,rc->rb", weights / weights.sum(axis=2)[:, :, None], bary)
    transport = np.einsum("pbij,rb->prij", rotations, blended, optimize=True)
    current_transport = np.einsum("prij,rj->pri", transport, offset[0])
    neutral_transport = np.einsum("prij,rj->pri", transport, neutral_offset)
    normal = np.cross(triangles[:, :, 1] - triangles[:, :, 0], triangles[:, :, 2] - triangles[:, :, 0])
    area = np.linalg.norm(normal, axis=2)
    valid = area > 1e-12
    signed = np.einsum("prj,prj->pr", offset, normal / np.maximum(area[:, :, None], 1e-30))
    return {"staticMorphOffsetChange": np.linalg.norm(offset[0] - neutral_offset, axis=1),
            "poseTransportedOffsetDrift": np.linalg.norm(offset - current_transport, axis=2),
            "neutralOffsetResidual": np.linalg.norm(offset - neutral_transport, axis=2),
            "rootToSkinDistance": np.linalg.norm(offset, axis=2),
            "signedTriangleStandOff": signed, "signedValid": valid}


def distribution(values):
    values = finite(values).ravel()
    if not len(values):
        return {"count": 0, "min": None, "p50": None, "p95": None, "max": None}
    return {"count": len(values), "min": float(values.min()), "p50": float(np.median(values)),
            "p95": float(np.quantile(values, .95)), "max": float(values.max())}


def summarize(measured, poses, region_weights=None):
    count = len(measured["staticMorphOffsetChange"])
    region_weights = np.ones(count) if region_weights is None else finite(region_weights, (count,))
    if (region_weights <= 0).any() or (region_weights > 1 + 1e-12).any():
        raise ValueError("Only enabled bounded root region weights can be summarized")
    full = region_weights >= 1 - 1e-12

    def metric(values):
        row = distribution(values)
        # A deliberately faded follower may underfollow skin. Keep that class
        # distinct from full followers when choosing a later repair target.
        for label, selection in (("fullWeight", full), ("fadeWeight", ~full)):
            row[label + "Max"] = float(values[..., selection].max()) if selection.any() else None
        return row

    static = measured["staticMorphOffsetChange"]
    worst = int(np.argmax(static))
    result = {"staticMorphOffsetChange": {**metric(static), "worstRootIndex": worst,
                                        "worstRegionWeight": float(region_weights[worst])},
              "rootClasses": {"fullWeight": int(full.sum()), "fadeWeight": int((~full).sum())}, "poseGroups": {}}
    for group in sorted({group for _, _, group in poses}):
        ids = [i for i, (_, _, current) in enumerate(poses) if current == group]
        row = {}
        for key in ("poseTransportedOffsetDrift", "neutralOffsetResidual", "rootToSkinDistance"):
            values = measured[key][ids]
            worst_pose, worst_root = np.unravel_index(np.argmax(values), values.shape)
            row[key] = {**metric(values), "worstPose": poses[ids[worst_pose]][0], "worstRootIndex": int(worst_root),
                        "worstRegionWeight": float(region_weights[worst_root])}
        valid = measured["signedValid"][ids]
        signed = measured["signedTriangleStandOff"][ids][valid]
        row["signedTriangleStandOff"] = {**distribution(signed), "negativeCount": int((signed < 0).sum()),
                                         "degenerateTriangleSamples": int((~valid).sum())}
        result["poseGroups"][group] = row
    return result


def json_read(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key: " + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))


def states(public, vectors=None):
    result = [("neutral", {}), ("breast-half", {BREAST: .5}), ("breast-full", {BREAST: 1.})]
    result += [("breast-and-" + name, {BREAST: 1., morph: 1.}) for name, morph in
               (("chest", "CLAWTorsoChestSize"), ("girth", "CLAWTorsoGirth"),
                ("lean", "CLAWTorsoLean"), ("shoulder", "CLAWTorsoShoulderGirth"))]
    if vectors is not None:
        if not isinstance(vectors, list) or len(vectors) > 64:
            raise ValueError("Vectors must be a list of at most 64 named records")
        for row in vectors:
            if not isinstance(row, dict) or row.get("sex") not in (None, "male", "female"):
                raise ValueError("Invalid named vector/sex")
            if row.get("sex") == "male":
                continue
            result.append((row.get("name", row.get("fixture")), row.get("values")))
    seen = set()
    for name, values in result:
        if not isinstance(name, str) or not name.strip() or len(name) > 100 or name in seen or not isinstance(values, dict):
            raise ValueError("Every state needs a unique bounded name and values object")
        seen.add(name)
        if not set(values) <= set(public):
            raise ValueError("State names an unknown current-v4 morph")
        compose_morphs([[0, 0, 0]], {}, values)
    return result


def pin(path):
    path = Path(path).resolve(strict=True)
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def unchanged(pins):
    for row in pins:
        if pin(row["path"]) != row:
            raise ValueError("Consumed file changed during audit: " + row["path"])


def output_path(path, inputs):
    original = Path(path).absolute()
    for ancestor in (original, *original.parents):
        if ancestor.exists() and (ancestor.is_symlink() or ancestor.is_junction()):
            raise ValueError("Output ancestry cannot contain a link/junction")
    out = original.resolve()
    blocked = [ROOT.resolve(), *[Path(p).resolve().parent for p in inputs]]
    if out.suffix.lower() != ".json" or out.exists() or any(out == p or p in out.parents for p in blocked):
        raise ValueError("Choose a new external JSON file outside input directories")
    if any(part.casefold() in {"mods", "profiles", "overwrite", "mo2", "modorganizer", "skyrimvr", "skyrim special edition"} for part in out.parts):
        raise ValueError("Output points into a live game/mod-manager tree")
    return out


def helpers():
    sys.path.insert(0, str(TOOLS))
    spec = importlib.util.spec_from_file_location("claw_attachment_p1", HERE / "p1_rig.py")
    current = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(current)
    rig = current.rig
    for module, expected in ((rig, TOOLS / "breast_rig.py"), (rig.surface, TOOLS / "surface_collar.py")):
        if Path(module.__file__).resolve() != expected.resolve():
            raise ValueError("A different local geometry helper is loaded")
    return current, rig


def frozen_bindings(shapes, vertices, faces, profile, rig):
    surface = rig.surface
    collar = surface.Collar(vertices["body"], faces["body"], vertices["head"], faces["head"], profile["collar"],
                            rig.SurfaceProjector(vertices["body"], faces["body"]))
    result = [{"name": "head-collar", "shape": "head", "roots": collar.anchors,
               "groups": [[int(i)] for i in collar.anchors], "binding": collar.binding, "source": "body", "weights": np.ones(len(collar.anchors))}]
    skin = np.r_[vertices["body"], vertices["head"]]
    triangles = np.r_[faces["body"], faces["head"] + len(vertices["body"])]
    projector = rig.SurfaceProjector(skin, triangles)
    for rule in profile["layers"]:
        name = rule["shape"]
        layer = surface.Layer(vertices[name], faces[name], skin, triangles, rule, projector)
        ids = np.flatnonzero(layer.weights > 0)
        roots = []
        for group in ids:
            candidates = layer.groups[group]
            matches = candidates[np.all(vertices[name][candidates] == layer.binding.points[group], axis=1)]
            if not len(matches):
                raise ValueError("Frozen representative does not identify a layer vertex")
            roots.append(int(matches[0]))
        if not len(roots):
            raise ValueError("Current-v4 layer has no eligible roots: " + name)
        # Keep one detached binding with the selected existing triangle indices.
        result.append({"name": name, "shape": name, "roots": np.asarray(roots), "groups": [layer.groups[i].tolist() for i in ids],
                       "binding": layer.binding, "selection": ids, "source": "skin", "weights": layer.weights[ids],
                       "excludedGroups": len(layer.groups) - len(ids)})
    return result


def audit(body, tri, skeleton, profile, out, *, pynifly=None, vectors=None, body_sha256=None):
    inputs = [Path(p).resolve(strict=True) for p in (body, tri, skeleton, profile)]
    body, tri, skeleton, profile = inputs
    if vectors is not None:
        vectors = Path(vectors).resolve(strict=True)
        inputs.append(vectors)
    out = output_path(out, inputs)
    source_paths = [Path(__file__), HERE / "p1_rig.py", TOOLS / "breast_rig.py", TOOLS / "surface_collar.py",
                    TOOLS / "locate.py", HERE / "p1-rig-v4.json", ROOT / "src/main/resources/recipes/breast-rig-canonical.json"]
    pins = [pin(path) for path in dict.fromkeys([*inputs, *source_paths])]
    if Path(__file__).read_bytes() != SOURCE_BYTES:
        raise ValueError("Attachment audit source changed since loading")
    current, rig = helpers()
    p = current.validate_profile(json_read(profile))
    if p != json_read(HERE / "p1-rig-v4.json"):
        raise ValueError("Select the exact authored current-v4 P1 profile")
    expected = p["inputs"]
    for path, key in ((tri, "triSha256"), (skeleton, "skeletonSha256")):
        if pin(path)["sha256"] != expected[key]:
            raise ValueError("Current-v4 input pin differs: " + key)
    if body_sha256 is not None and (not isinstance(body_sha256, str) or len(body_sha256) != 64 or
                                    any(c not in "0123456789abcdef" for c in body_sha256) or pin(body)["sha256"] != body_sha256):
        raise ValueError("Supplied rigged-body receipt hash differs")
    api, TripFile, dependency = rig.load_pynifly(pynifly)
    dependency = dependency.resolve(strict=True)
    if Path(api.__file__).resolve() != (dependency / "pyn/pynifly.py").resolve():
        raise ValueError("A different PyNifly module is already loaded")
    dependencies = [pin(path) for path in [dependency / "NiflyDLL.dll", *sorted(dependency.rglob("*.py"))]]
    # Retain the interpreter and NumPy computation identities as well as the reader.
    import numpy._core._multiarray_umath as numpy_native
    dependencies += [pin(sys.executable), pin(np.__file__), pin(numpy_native.__file__)]
    nif, skel = api.NifFile(str(body)), api.NifFile(str(skeleton))
    if len(nif.nodes) != expected["outputNodeCount"]:
        raise ValueError("Audit requires the current unsplit 91-node P1 carrier")
    tolerance = p["verification"]["nodeMatrixTolerance"]
    for name in p["requiredNodes"]:
        if name not in nif.nodes or name not in skel.nodes or nif.nodes[name].parent.name != skel.nodes[name].parent.name or not np.allclose(
                finite(rig.matrix(nif.nodes[name].global_transform)), finite(rig.matrix(skel.nodes[name].global_transform)), rtol=0, atol=tolerance):
            raise ValueError("Existing XP32 P1 ancestry/rest transform differs: " + name)
    shapes = {shape.name: shape for shape in nif.shapes}
    if len(shapes) != len(nif.shapes) or not {"body", "head", *[r["shape"] for r in p["layers"]]} <= set(shapes):
        raise ValueError("Missing or duplicate current body/layer shapes")
    vertices = {name: rig.surface.positions(shape.verts) for name, shape in shapes.items()}
    if any(not len(value) for value in vertices.values()):
        raise ValueError("Empty serialized shape")
    faces = {name: rig.surface.triangles(shape.tris, len(vertices[name])) for name, shape in shapes.items()}
    raw = TripFile.from_filepath(str(tri)).shapes
    if not set(raw) <= set(shapes):
        raise ValueError("Current TRI has a shape absent from the supplied NIF")
    public = {name for morphs in raw.values() for name in morphs}
    current.validate_public_morphs(p, public)
    fields = {name: {m: finite(rig.dense_morph(raw, name, m, len(v)), v.shape) for m in raw.get(name, {})} for name, v in vertices.items()}
    state_list = states(public, json_read(vectors) if vectors else None)
    names = sorted({name for shape in shapes.values() for name in shape.bone_weights})
    if not set(names) <= set(skel.nodes):
        raise ValueError("Serialized skin uses a bone absent from XP32")
    index = {name: i for i, name in enumerate(names)}
    weights = {name: rig.read_weights(shape, names) for name, shape in shapes.items()}
    for name, w in weights.items():
        if (w > 1).any() or (w > 0).sum(axis=1).max() > 4 or abs(w.sum(axis=1) - 1).max() > p["verification"]["packedWeightSumTolerance"]:
            raise ValueError("Invalid serialized packed skin budget: " + name)
    rig.require_serialized_head_mobility(weights["head"], names, vertices["head"], p["p1Bones"])
    rest = {name: finite(rig.matrix(node.global_transform), (4, 4)) for name, node in skel.nodes.items()}
    parents = {name: node.parent.name if node.parent else None for name, node in skel.nodes.items()}
    poses = rig.pose_definitions(p["p1Bones"], p["verification"]["p1Degrees"], p["verification"]["seed"])
    globals_ = finite(rig.posed_globals(rest, parents, names, poses))
    rotations = globals_[:, :, :3, :3] @ np.linalg.inv(np.asarray([rest[n][:3, :3] for n in names]))
    binds = {}
    for name, shape in shapes.items():
        if not shape.has_global_to_skin:
            raise ValueError("Missing serialized global-to-skin frame")
        value = np.zeros((len(names), 4, 4))
        for bone in shape.bone_weights:
            value[index[bone]] = finite(rig.matrix(shape.get_shape_skin_to_bone(bone)), (4, 4)) @ finite(rig.matrix(shape.global_to_skin), (4, 4))
        binds[name] = globals_ @ value
    frozen = frozen_bindings(shapes, vertices, faces, p, rig)
    need = {name: set() for name in shapes}
    for row in frozen:
        selected = row.get("selection", np.arange(len(row["roots"])))
        binding = row["binding"]
        row["bary"] = binding.weights[selected]
        corners = binding.faces[binding.indices[selected]]
        row["corners"] = [[("body", int(i)) if row["source"] == "body" or i < len(vertices["body"]) else
                           ("head", int(i - len(vertices["body"]))) for i in triangle] for triangle in corners]
        need[row["shape"]].update(row["roots"].tolist())
        for triangle in row["corners"]:
            for name, i in triangle:
                need[name].add(i)
    ids = {name: np.asarray(sorted(values), int) for name, values in need.items() if values}
    lookup = {name: {int(i): j for j, i in enumerate(values)} for name, values in ids.items()}
    report = {"schema": "claw-current-v4-breast-attachment-audit/1", "status": "measured-finite-states-no-acceptance",
              "inputsAndSources": pins, "dependencies": dependencies, "runtime": {"python": platform.python_version(), "numpy": np.__version__},
              "contract": {"triSkeletonProfileExact": True, "riggedBodyReceiptHashChecked": body_sha256 is not None,
                           "profileBodyHashDescribesUnriggedSource": True, "sourceBodyGeometryEquivalenceChecked": False},
              "poseDefinitions": [{"name": n, "group": g, "localRotations": {b: m.tolist() for b, m in e.items()}} for n, e, g in poses],
              "states": {name: values for name, values in state_list}, "bindings": {}, "measurements": {},
              "limits": ["Finite authored morph/pose samples, not game, renderer, collision or aesthetic acceptance.",
                         "Nearest neutral triangle bindings stay frozen; signed stand-off uses its current winding, not a watertight inside/outside test.",
                         "A nonzero donor offset is preserved, not treated as an already closed seam. Static morph error and pose drift are separate.",
                         "Raw packed and normalized LBS are separate calculations; neither is asserted to reproduce the game shader.",
                         "Offset transport uses barycentric blends of per-skin-vertex normalized posed/rest linear maps in both conventions.",
                         "Only enabled roots in the exact profile region are measured; full/fade region classes are separate because faded followers can intentionally underfollow skin.",
                         "Card tips, edge strain, alpha coverage and self-intersections are not checked.",
                         "Rigged NIF is recorded and structurally checked; profile pins its unrigged source, not bytewise identity of this supplied carrier."]}
    for row in frozen:
        report["bindings"][row["name"]] = {"targetShape": row["shape"], "rootVertices": row["roots"].tolist(),
            "groups": row["groups"], "sourceCorners": row["corners"], "barycentricWeights": row["bary"].tolist(),
            "regionWeights": row["weights"].tolist(), "excludedGroups": row.get("excludedGroups", 0)}
    neutral = {}
    for state, values in state_list:
        report["measurements"][state] = {}
        for normalize in (False, True):
            mode = "normalized" if normalize else "rawPacked"
            posed = {name: finite(rig.lbs(compose_morphs(vertices[name], fields[name], values)[selected],
                        weights[name][selected], binds[name], normalize)) for name, selected in ids.items()}
            rows = {}
            for row in frozen:
                roots = posed[row["shape"]][:, [lookup[row["shape"]][int(i)] for i in row["roots"]]]
                triangles = np.stack([np.stack([posed[n][:, lookup[n][i]] for n, i in triangle], axis=1) for triangle in row["corners"]], axis=1)
                source_weights = np.asarray([[weights[n][i] for n, i in triangle] for triangle in row["corners"]])
                key = mode, row["name"]
                if state == "neutral":
                    neutral[key] = roots[0].copy(), triangles[0].copy()
                measured = measure_binding(roots, triangles, row["bary"], source_weights, rotations, *neutral[key])
                rows[row["name"]] = summarize(measured, poses, row["weights"])
            report["measurements"][state][mode] = rows
    unchanged([*pins, *dependencies])
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("body", "tri", "skeleton", "profile", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--pynifly", type=Path)
    parser.add_argument("--vectors", type=Path)
    parser.add_argument("--body-sha256")
    args = parser.parse_args(argv)
    try:
        result = audit(args.body, args.tri, args.skeleton, args.profile, args.out,
                       pynifly=args.pynifly, vectors=args.vectors, body_sha256=args.body_sha256)
        print(json.dumps({"status": result["status"], "report": str(args.out.resolve())}))
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, np.linalg.LinAlgError) as error:
        print("Attachment audit: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
