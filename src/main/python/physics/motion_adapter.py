"""Build a separate CBPC motion adapter from explicit inspected bodies; never install.

This contains no collider model or Papyrus host. Its constants drive the existing
weighted skeleton nodes, independently of which morph-family evaluator is used.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("claw_motion_source_build", ROOT / "build.py")
source = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source)
SOURCE_BYTES = Path(__file__).read_bytes()
if compile(SOURCE_BYTES, sys._getframe().f_code.co_filename, "exec", dont_inherit=True,
           optimize=sys.flags.optimize) != sys._getframe().f_code:
    raise ValueError("Motion adapter source bytes do not match the loaded code")

BODY_ROLES = ("male0", "male1", "female0", "female1")
PACKAGE_NAME = "CLAW Physics - CBPC Motion.zip"


def pin(path):
    path = Path(path).resolve()
    payload = path.read_bytes()
    return {"path": str(path), "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


def unchanged(rows):
    for row in rows:
        if pin(row["path"]) != row:
            raise ValueError("Input changed during adapter build: " + row["path"])


def load_pynifly(directory):
    """Use only public read APIs; do not initialize Blender or write any NIF."""
    directory = directory.resolve()
    if not (directory / "pyn/pynifly.py").is_file() or not (directory / "NiflyDLL.dll").is_file():
        raise ValueError("--pynifly must name a public PyNifly add-on with NiflyDLL.dll")
    dependencies = [pin(directory / "NiflyDLL.dll"),
                    *[pin(path) for path in sorted((directory / "pyn").rglob("*.py"))]]
    sys.path.insert(0, str(directory))
    from pyn import pynifly
    if Path(pynifly.__file__).resolve() != directory / "pyn/pynifly.py":
        raise ValueError("A different PyNifly module is already loaded")
    pynifly.NifFile.Load(str(directory / "NiflyDLL.dll"))
    unchanged(dependencies)
    return pynifly, dependencies


def inspect_body(nif, nodes, label):
    """Require serialized nonzero skin influence for every intended driver."""
    missing = set(nodes) - set(nif.nodes)
    if missing:
        raise ValueError(label + " lacks driver nodes: " + ", ".join(sorted(missing)))
    coverage = {node: {} for node in nodes}
    for shape in nif.shapes:
        weights = shape.bone_weights
        vertex_count = len(shape.verts)
        for node in nodes:
            selected = weights.get(node, ())
            positive = set()
            for index, weight in selected:
                if not math.isfinite(weight) or weight < 0 or weight > 1:
                    raise ValueError(label + " contains invalid stored skin weights")
                if type(index) is not int or not 0 <= index < vertex_count:
                    raise ValueError(label + " contains an invalid stored vertex index")
                if weight > 0:
                    positive.add(index)
            if positive:
                coverage[node][shape.name] = len(positive)
    absent = [node for node, shapes in coverage.items() if not shapes]
    if absent:
        raise ValueError(label + " has no stored skin influence for: " + ", ".join(absent))
    return coverage


def inspect_resources(api, resources, breast):
    skeleton = api.NifFile(str(resources["skeleton"]))
    required = source.NODES + (source.BREAST_NODES if breast else ())
    missing = set(required) - set(skeleton.nodes)
    if missing:
        raise ValueError("Skeleton lacks existing driver nodes: " + ", ".join(sorted(missing)))
    result = {}
    for role in BODY_ROLES:
        nodes = source.NODES + (source.BREAST_NODES if breast and role.startswith("female") else ())
        result[role] = inspect_body(api.NifFile(str(resources[role])), nodes, role)
    return result


def motion_files(inputs, breast):
    recipe = inputs.json("recipe.json")
    source.validate(recipe, inputs.json("capsules.json"))
    recipe = copy.deepcopy(recipe)
    # Motion queue and contact queue are separate. Do not expose a pre-existing
    # provider collision configuration through the motion-only adapter.
    recipe["common"]["collisionMultipler"] = 0.0
    recipe["common"]["collisionMultiplerRot"] = 0.0
    recipe["common"]["amplitude"] = 1.0
    master, bounce = source.render_motion(recipe)
    files = {"SKSE/Plugins/CBPCMasterConfig_CLAWMotion.txt": master.encode(),
             "SKSE/Plugins/CBPConfig_CLAWMotion.txt": bounce.encode()}
    if breast:
        breast_recipe = source.read_breast_recipe(inputs)
        breast_recipe["common"]["amplitude"] = 1.0
        master, bounce = source.render_motion(breast_recipe)
        files.update({"SKSE/Plugins/CBPCMasterConfig_CLAWBreastMotion.txt": master.encode(),
                      "SKSE/Plugins/CBPConfig_CLAWBreastMotion.txt": bounce.encode()})
    return files


def archive(path, files):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for name, payload in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            output.writestr(info, payload)
    with zipfile.ZipFile(path) as output:
        if output.namelist() != sorted(files) or any(output.read(name) != payload for name, payload in files.items()):
            raise ValueError("Motion archive readback differs from its generated files")


def build_adapter(out, provider_snapshot, resources, pynifly, *, breast=False, provider="cbpc", api=None):
    if provider == "fsmp":
        from fsmp_motion import build_adapter as fsmp_builder
        return fsmp_builder(out, provider_snapshot, resources, pynifly, breast=breast, api=api)
    if provider != "cbpc":
        raise ValueError("Unsupported motion provider; choose cbpc or fsmp")
    out = source.destination(out)
    if set(resources) != set(BODY_ROLES) | {"skeleton"}:
        raise ValueError("Explicit male/female weight-0/1 bodies and skeleton are all required")
    resources = {role: Path(path).resolve() for role, path in resources.items()}
    if len(set(resources.values())) != len(resources):
        raise ValueError("Each body endpoint and the skeleton need their own explicit path")
    for directory in (Path(provider_snapshot).resolve(), *[path.parent for path in resources.values()]):
        if directory == out or directory in out.parents:
            raise ValueError("Adapter output cannot be inside an input directory")
    resource_pins = {role: pin(path) for role, path in resources.items()}
    if any(not row["bytes"] for row in resource_pins.values()):
        raise ValueError("Body endpoints and skeleton must be nonempty")
    inputs = source.SourceInputs(breast=breast)
    skeleton_pin = inputs.json("capsules.json")["provenance"]["xp32Sha256"]
    if resource_pins["skeleton"]["sha256"] != skeleton_pin:
        raise ValueError("Skeleton differs from the reviewed existing XP32 donor")
    audit = source.audit_provider(provider_snapshot)
    source.require_provider_clear(audit, breast=breast)
    if not any(row["path"].casefold() == "cbp.dll" and row["bytes"] for row in audit["files"]):
        raise ValueError("Explicit provider snapshot must include a nonempty cbp.dll; its presence does not qualify its behavior")
    own_sources = [pin(ROOT / "motion_adapter.py"), pin(ROOT / "motion-adapters.md")]
    if (ROOT / "motion_adapter.py").read_bytes() != SOURCE_BYTES:
        raise ValueError("Motion adapter source changed since loading")
    dependencies = []
    if api is None:
        api, dependencies = load_pynifly(Path(pynifly))
    coverage = inspect_resources(api, resources, breast)
    # A resource profile records the actual inspected endpoints for the existing
    # motion-only recipe. It adds no contact model and never rewrites the recipe.
    profile = None
    if breast:
        profile = {"schemaVersion": 1, "id": "CLAW.Motion.InspectedP1",
                   "p1Bones": list(source.BREAST_NODES),
                   "inputs": {"bodyNifSha256": resource_pins["female0"]["sha256"],
                              "bodyWeight1NifSha256": resource_pins["female1"]["sha256"],
                              "skeletonSha256": resource_pins["skeleton"]["sha256"]}}
        # Keep exact parser/validation shared with the existing source generator.
        payload = json.dumps(profile, sort_keys=True).encode()
        inputs.breast_profile = {"path": "generated-inspected-resource-profile", "payload": payload,
                                 "sha256": hashlib.sha256(payload).hexdigest()}
    files = motion_files(inputs, breast)
    # The generated profile is internal evidence, not an on-disk SourceInputs
    # dependency. SourceInputs still verifies every consumed authored source.
    inputs.breast_profile = None
    readme = ("CLAW Physics - CBPC Motion\n\n"
              "Separate optional development adapter for the exact inspected body endpoints.\n"
              "Requires CBPC and the existing XP32 skeleton. Race: vanilla WerewolfBeastRace.\n"
              "Ear/tail: both sexes. Female P1: " + ("included" if breast else "excluded") + ".\n"
              "Install as its own mod after the selected CLAW body; choose one motion writer.\n"
              "Do not combine with the older CLAWPhysics/CLAWBreastPhysics/CLAWBreastContact configs.\n"
              "No collider response, DLL, ESP, scripts, body or skeleton is included.\n"
              "Current linked morphs deform the skinned mesh; the same stored driver weights remain active.\n"
              "These motion constants do not adapt stiffness, node origins or contacts to morph values.\n"
              "Game/node-trace/visual/lifecycle acceptance remains pending.\n\n"
              "Source: https://github.com/Vhodnoylogin/claw/tree/feature/post-070-backlog/src/main/python/physics\n")
    files["README.txt"] = readme.encode()
    unchanged([*resource_pins.values(), *dependencies, *own_sources])
    inputs.verify()
    source.verify_provider_unchanged(audit)
    out.mkdir(parents=True, exist_ok=False)
    pending = out / "FAILED-unverified-do-not-install"
    pending.write_text("Incomplete adapter build; inspect failure.\n", encoding="utf-8")
    package = out / "package"
    for name, payload in files.items():
        target = package / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    archive(out / PACKAGE_NAME, files)
    unchanged([*resource_pins.values(), *dependencies, *own_sources])
    inputs.verify()
    source.verify_provider_unchanged(audit)
    report = {"schemaVersion": 1, "status": "built-offline-motion-adapter-runtime-pending",
              "provider": provider, "runtimeQualified": False, "gameValidated": False, "releaseReady": False,
              "motionNodes": list(source.NODES + (source.BREAST_NODES if breast else ())),
              "femaleOnlyNodes": list(source.BREAST_NODES) if breast else [],
              "collisionResponseEnabled": False, "colliderHostIncluded": False,
              "morphBehavior": "Skinned-node motion applies to the current morphed mesh; constants do not observe coefficients or refit contacts",
              "resources": resource_pins, "storedWeightCoverage": coverage,
              "breastResourceProfile": profile, "providerAudit": audit,
              "dependencies": dependencies, "sourceInputs": [*inputs.rows(), *own_sources],
              "files": [{"path": name, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
                        for name, payload in sorted(files.items())],
              "archive": pin(out / PACKAGE_NAME)}
    (out / "motion-adapter-build.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    pending.unlink()
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("cbpc", "fsmp"), default="cbpc")
    parser.add_argument("--provider-snapshot", type=Path, required=True, help="baseline winning SKSE/Plugins bytes before this adapter")
    for role in BODY_ROLES:
        parser.add_argument("--" + role, type=Path, required=True, help="explicit selected body NIF endpoint")
    parser.add_argument("--skeleton", type=Path, required=True, help="existing read-only reviewed XP32 skeleton")
    parser.add_argument("--pynifly", type=Path, required=True, help="public PyNifly add-on directory")
    parser.add_argument("--with-breast-motion", action="store_true", help="require actual bilateral P1 skin weights on both female endpoints")
    parser.add_argument("--out", type=Path, required=True, help="new external directory; never installs")
    args = parser.parse_args(argv)
    try:
        report = build_adapter(args.out, args.provider_snapshot,
                               {role: getattr(args, role) for role in (*BODY_ROLES, "skeleton")},
                               args.pynifly, breast=args.with_breast_motion, provider=args.provider)
        print(json.dumps({"status": report["status"], "motionNodes": len(report.get("motionNodes", source.NODES + (source.BREAST_NODES if args.with_breast_motion else ()))),
                          "package": report["archive"]["path"], "gameValidated": False}))
        return 0
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
        print("CLAW motion adapter: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
