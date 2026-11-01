"""Versioned current-TRI P1 rig stages; no retained runtime assets."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
TOOLS = ROOT / "src/main/python/build-tools"
sys.path.insert(0, str(TOOLS))
import breast_rig as rig


V3_PROFILE = "expressive-v3-current-tri-existing-xp32-p1-v1"
V4_PROFILE = "expressive-v4-current-tri-existing-xp32-p1-v1"
V4_SEMANTICS = "expressive-body-v4-separate-biceps-triceps-soft-arm-girth"
V4_PUBLIC_MORPHS = tuple(sorted((
    "CLAWArmBiceps", "CLAWArmTriceps", "CLAWArmClawLong", "CLAWArmGirth",
    "CLAWArmLean", "CLAWArmPawSize", "CLAWHeadEarSize", "CLAWHeadEarTilt",
    "CLAWHeadMuzzleLong", "CLAWHeadMuzzleWide", "CLAWHeadSize",
    "CLAWLegCalfGirth", "CLAWLegCalfLean", "CLAWLegClawLong", "CLAWLegDigitigrade",
    "CLAWLegPawSize", "CLAWLegThighGirth", "CLAWLegThighLean", "CLAWTailFluff",
    "CLAWTailLength", "CLAWTailLift", "CLAWTorsoBackWide", "CLAWTorsoBellyRound",
    "CLAWTorsoBreastSize", "CLAWTorsoChestSize", "CLAWTorsoFlankWidth",
    "CLAWTorsoGirth", "CLAWTorsoLean", "CLAWTorsoNeckGirth",
    "CLAWTorsoShoulderGirth", "CLAWTorsoWaistNarrow",
)))


def profile_generation(profile):
    name = profile.get("name")
    if name == V3_PROFILE:
        return "v3"
    if name == V4_PROFILE:
        return "v4"
    raise ValueError("Select an explicit versioned current-TRI P1 profile")


def validate_profile(profile):
    template = json.loads((TOOLS / "../../resources/recipes/breast-rig-canonical.json").resolve().read_text())
    generation = profile_generation(profile)
    if profile.get("schemaVersion") != 1:
        raise ValueError("Current-TRI P1 profile schema differs")
    if generation == "v4" and (profile.get("semanticVersion") != V4_SEMANTICS or
                                profile.get("publicMorphNames") != list(V4_PUBLIC_MORPHS)):
        raise ValueError("Current-TRI v4 requires its separate biceps/triceps public contract")
    for key in ("spineBone", "p1Bones", "requiredNodes", "publicMorph", "mobility", "layers", "verification", "outputRelativeNif"):
        if profile.get(key) != template[key]:
            raise ValueError("Current-TRI rig must retain existing bounded rig policy: " + key)
    expected_collar = {**template["collar"], "anchorCountRange": [53, 53]}
    if profile.get("collar") != expected_collar:
        raise ValueError("Current-TRI rig requires its measured53anchor collar")
    inputs = profile.get("inputs", {})
    morph_count = 29 if generation == "v3" else 31
    if (inputs.get("sourceNodeCount"), inputs.get("outputNodeCount"), inputs.get("anchorCount"), inputs.get("publicMorphCount")) != (85, 91, 53, morph_count):
        raise ValueError("Current-TRI " + generation + " resource structure differs")
    for key in ("bodyNifSha256", "triSha256", "skeletonSha256"):
        value = inputs.get(key, "")
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("Current-TRI " + generation + " profile requires exact resource pins")
    if inputs["skeletonSha256"] != template["inputs"]["skeletonSha256"]:
        raise ValueError("Current-TRI rig cannot replace the reviewed XP32 skeleton")
    return profile


def validate_public_morphs(profile, public):
    public = set(public)
    if len(public) != profile["inputs"]["publicMorphCount"] or any(not name.startswith("CLAW") for name in public):
        raise ValueError("Current TRI public morph contract differs")
    if profile_generation(profile) == "v4" and public != set(V4_PUBLIC_MORPHS):
        raise ValueError("Current TRI does not contain the exact expressive-v4 public inventory")


def mobility(vertices, delta, anchors, profile):
    """A new scalar support, derived only from the exact current public TRI."""
    vertices = rig.surface.positions(vertices)
    delta = rig.surface.positions(delta)
    if delta.shape != vertices.shape:
        raise ValueError("Current BreastSize field does not match the head")
    amplitude = np.linalg.norm(delta, axis=1)
    maximum = float(amplitude.max())
    if maximum <= 1e-4:
        raise ValueError("Current BreastSize has no usable head displacement")
    q = profile["mobility"]
    desired = q["maximum"] * np.clip(amplitude / maximum, 0, 1)
    desired *= rig.smooth((vertices[:, 2] - q["bottomStart"]) / q["bottomWidth"])
    desired *= rig.smooth((q["topEnd"] - vertices[:, 2]) / q["topWidth"])
    desired[anchors] = 0
    desired[vertices[:, 1] >= q["faceCutoffY"]] = 0
    desired[desired <= q["minimum"]] = 0
    if not np.any(desired):
        raise ValueError("Current-TRI guarded mobility is empty")
    return desired, {"method": "current-TRI-head-displacement-magnitude-normalized-by-current-maximum",
                     "maximumInputDisplacement": maximum, "mobility": rig.stats(desired),
                     "legacyModerateTriUsed": False}


def build_candidate(body, tri, skeleton, profile_file, output, pynifly_directory=None):
    body, tri, skeleton, profile_file = [Path(p).resolve(strict=True) for p in (body, tri, skeleton, profile_file)]
    p = validate_profile(json.loads(profile_file.read_text(encoding="utf-8-sig")))
    # These are separate authored input contracts. The v3 and older
    # 55-anchor/moderate-TRI profiles retain their own frozen resource contracts.
    source_files = [Path(__file__), TOOLS / "breast_rig.py", TOOLS / "surface_collar.py", profile_file,
                    ROOT / "src/main/resources/recipes/breast-rig-canonical.json"]
    pins = {str(path): rig.sha256(path) for path in (body, tri, skeleton, *source_files)}
    for path, key in ((body, "bodyNifSha256"), (tri, "triSha256"), (skeleton, "skeletonSha256")):
        if pins[str(path)] != p["inputs"][key]:
            raise ValueError("Current-TRI P1 input pin differs: " + key)
    out = rig.safe_output(output, (body, tri, skeleton, profile_file))
    api, TripFile, dependency = rig.load_pynifly(pynifly_directory)
    dependencies = {str(path): rig.sha256(path) for path in
                    (dependency / "NiflyDLL.dll", dependency / "pyn/pynifly.py", dependency / "tri/tripfile.py")}
    nif = api.NifFile(str(body))
    if len(nif.nodes) != p["inputs"]["sourceNodeCount"]:
        raise ValueError("Current-TRI rig requires the declared unrigged node count")
    shapes = {shape.name: shape for shape in nif.shapes}
    raw = TripFile.from_filepath(str(tri)).shapes
    public = {name for morphs in raw.values() for name in morphs}
    validate_public_morphs(p, public)
    vertices = {name: np.asarray(shape.verts) for name, shape in shapes.items()}
    faces = {name: np.asarray(shape.tris) for name, shape in shapes.items()}
    collar = rig.surface.Collar(vertices["body"], faces["body"], vertices["head"], faces["head"], p["collar"],
                                rig.SurfaceProjector(vertices["body"], faces["body"]))
    if len(collar.anchors) != p["inputs"]["anchorCount"]:
        raise ValueError("Current-TRI collar count differs from the explicit profile")
    mobile, reconstruction = mobility(vertices["head"], rig.dense_morph(raw, "head", p["publicMorph"], len(vertices["head"])), collar.anchors, p)
    fields = {"head": mobile}
    skin = np.r_[vertices["body"], vertices["head"]]
    triangles = np.r_[faces["body"], faces["head"] + len(vertices["body"])]
    scalar = np.column_stack((np.r_[np.zeros(len(vertices["body"])), mobile], np.zeros(len(skin)), np.zeros(len(skin))))
    projector = rig.SurfaceProjector(skin, triangles)
    for rule in p["layers"]:
        name = rule["shape"]
        layer = rig.surface.Layer(vertices[name], faces[name], skin, triangles, rule, projector)
        fields[name] = layer.reconcile(np.zeros_like(vertices[name]), scalar)[:, 0]
    names = sorted({name for shape in shapes.values() for name in shape.bone_weights} | set(p["p1Bones"]))
    index = {name: i for i, name in enumerate(names)}
    planned = {}
    for name, desired in fields.items():
        old = rig.read_weights(shapes[name], names)
        fade = rig.capacity_fade(vertices[name], faces[name], old, p["mobility"]["capacityGuardWidth"], p["mobility"]["weldDecimals"])
        weights, _ = rig.transfer_spine2(old, desired, fade, index[p["spineBone"]],
                                         *[index[n] for n in p["p1Bones"]], vertices[name])
        planned[name] = {"weights": weights, "names": names}
    out.mkdir(parents=True, exist_ok=False)
    pending = out / "FAILED-unverified-do-not-install"
    pending.write_text("P1 rig build incomplete.\n")
    target = out / p["outputRelativeNif"]
    if out not in target.resolve().parents:
        raise ValueError("P1 output escapes staging")
    target.parent.mkdir(parents=True, exist_ok=True)
    rig._write_rig(api, body, skeleton, p, planned, target)
    shutil.copyfile(tri, target.with_suffix(".tri"))
    verification = rig.verify_candidate(api, body, target, skeleton, tri, raw, p, planned, collar.anchors)
    generation = profile_generation(p)
    verification["poseConvention"] = verification["poseConvention"].replace("moderate BreastSize", "actual current " + generation + " BreastSize")
    for path, expected in {**pins, **dependencies}.items():
        if rig.sha256(path) != expected:
            raise ValueError("P1 input/source/dependency changed during build: " + path)
    report = {"status": "verified-current-tri-P1-offline-runtime-pending", "profile": p,
              "inputsAndSources": pins, "dependencies": dependencies,
              "reconstruction": reconstruction, "verification": verification,
              "outputs": {str(path.relative_to(out)): rig.sha256(path) for path in (target, target.with_suffix(".tri"))},
              "gameValidated": False, "runtimeQualified": False,
              "limits": ["Current BreastSize states 0/.5/1 and existing151controlled skeletal poses; other morph combinations need later bounds/acceptance",
                         "Per-layer capacity guards do not establish common fur/skin motion or visually closed seams",
                         "No retained moderate TRI, NIF or weight blob used; body geometry and current TRI remain fixed"]}
    if generation == "v4":
        report["semanticVersion"] = p["semanticVersion"]
        report["publicMorphNames"] = sorted(public)
    report_path = out / "report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    pending.unlink()
    return report_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("body", "tri", "skeleton", "profile", "out", "pynifly"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = build_candidate(args.body, args.tri, args.skeleton, args.profile, args.out, args.pynifly)
        print(str(result))
        return 0
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as error:
        print("Current-TRI P1 rig: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
