"""Stage the male VR pose-contact fixture and complete CLAW host outside the game."""

import argparse
import json
from pathlib import Path, PurePosixPath
import sys

from freeze_tail_refit_subject import (
    CARRIER, MESH, RACEMENU, RETAINED, ROOT, SKEE, STOCK_CONTEXT_SHA, STOCK_VFS_SHA,
    WITNESS_BUILD_SHA, pin, read_pinned, same_bytes, write_member,
)
from prepare_tail_refit_contrast import PROFILE_SHA

sys.path.insert(0, str(ROOT / "src/main/python/physics"))
from wiring import PLUGIN, recipe, validate_plugin


MASTER = "SKSE/Plugins/CBPCMasterConfig.txt"
COLLISION = "SKSE/Plugins/CBPCollisionConfig.txt"
FIXTURE = "test_CLAW - VR CBPC Contact Fixture.esp"
ALIAS = "CLAW_CBPCBenchTail"
CONDITION = f"IsRaceFormId(Skyrim.esm|0CDD84) AND IsMale() AND IsActorBase({FIXTURE}|000800)"
CARRIER_FACADE = "Scripts/CLAWDistributionNative.pex"
CARRIER_FACADE_SHA = "b3f39d5bc4a2a67c2de9ccecc82d4bebf4ab006780bd9ee59171ff5e114656ef"
HOST_SCRIPTS = {
    "CLAWPhysicsActor.pex", "CLAWPhysicsControl.pex", "CLAWPhysicsData.pex",
    "CLAWPhysicsHost.pex", "CLAWPhysicsLoadRelay.pex", "CLAWPhysicsNative.pex",
}


def male_layout(profile):
    slots = profile["slots"]
    active = [(index, item["node"]) for index, item in enumerate(slots) if item["male"] is not None]
    for _, node in active:
        if (type(node) is not str or not node or node.strip() != node or node.startswith("[") or
                any(character in node for character in "\r\n=<>#,()\0")):
            raise ValueError("Invalid single-node CBPC group name")
    nodes = tuple(dict.fromkeys(node for _, node in active))
    if (len(slots), len(active), len(nodes)) != (128, 120, 25):
        raise ValueError("Expected the pinned 128-slot profile with 120 male slots on 25 nodes")
    return active, nodes


def replace_lines(contents, substitutions):
    lines = contents.decode("ascii").splitlines()
    for old, new in substitutions.items():
        if lines.count(old) != 1:
            raise ValueError(f"Unexpected pinned template line: {old}")
        index = lines.index(old)
        lines[index:index + 1] = new
    return ("\n".join(lines) + "\n").encode("ascii")


def full_host_configs(master, collision, nodes):
    # Plain rows create independent affected groups. A single alias shares the
    # pinned tuning without chaining the affected node names together.
    return {
        MASTER: replace_lines(master, {
            "MalePhysics=0": ["MalePhysics=1"],
            f"TailBone02={ALIAS}={CONDITION}": [f"{node}={ALIAS}={CONDITION}" for node in nodes],
        }),
        COLLISION: replace_lines(collision, {"TailBone02": list(nodes)}),
    }


def exact_runtime_inputs(args, profile, current_vfs):
    source_assets = {Path(item["path"]).name: item for item in profile["sourceInputs"]}
    body = {virtual: args.body_assets / PurePosixPath(virtual).name for virtual in CARRIER.values()}
    body[MESH + "skeleton.nif"] = args.skeleton
    inputs = {virtual: pin(source) for virtual, source in body.items()}
    for virtual, item in inputs.items():
        same_bytes(item, source_assets[PurePosixPath(virtual).name])
    inputs["CLAW.esp"] = pin(args.carrier / "CLAW.esp")
    same_bytes(inputs["CLAW.esp"], current_vfs["CLAW.esp"])
    facade_path = args.carrier / PurePosixPath(CARRIER_FACADE)
    read_pinned(facade_path, CARRIER_FACADE_SHA)
    inputs[CARRIER_FACADE] = pin(facade_path)

    # RaceMenu is supplied by the profile. Preserve the exact expected winners
    # in the handoff so staging cannot silently substitute a different provider.
    dependencies = {SKEE: pin(args.racemenu_vr / PurePosixPath(SKEE))}
    same_bytes(dependencies[SKEE], current_vfs[SKEE])
    for name, digest in RACEMENU.items():
        read_pinned(args.racemenu / name, digest)
        dependencies[name] = pin(args.racemenu / name)
    return inputs, dependencies


def stage(args):
    out = args.out.resolve()
    if out == ROOT or ROOT in out.parents or any(part.casefold() in {"data", "mods", "overwrite", "profiles"}
                                                for part in out.parts):
        raise ValueError("Choose a new detached staging directory")

    profile = json.loads(read_pinned(args.profile, PROFILE_SHA))
    active, nodes = male_layout(profile)
    model = profile["modelIdentity"]
    stock_case = args.stock_case.resolve(strict=True)
    vfs = stock_case / "poststage-vfs.expected.json"
    current_vfs = stock_case / "ROOT-CURRENT-VFS.json"
    stock = json.loads(read_pinned(vfs, STOCK_VFS_SHA))
    context = {item["virtual"]: item["actual"]
               for item in json.loads(read_pinned(current_vfs, STOCK_CONTEXT_SHA))["resources"]}
    expected = {item["virtual"]: item["actual"] for item in stock["resources"]}
    inputs = {}
    for name in (*stock["cbpcConfigInventory"], *RETAINED):
        inputs[name] = pin(stock_case / "contact-inputs" / PurePosixPath(name))
        same_bytes(inputs[name], expected[name])
    generated = full_host_configs(Path(inputs[MASTER]["path"]).read_bytes(),
                                  Path(inputs[COLLISION]["path"]).read_bytes(), nodes)
    runtime_inputs, dependencies = exact_runtime_inputs(args, profile, context)
    inputs.update(runtime_inputs)

    witness = json.loads(read_pinned(args.pose_witness_receipt, WITNESS_BUILD_SHA))
    inputs["SKSE/Plugins/CLAWVRNpcPose.dll"] = witness["dll"]
    inputs["Scripts/CLAWVRNpcPose.pex"] = witness["pex"]
    for entry in (witness["dll"], witness["pex"]):
        same_bytes(pin(Path(entry["path"])), entry)

    distribution = json.loads(args.trace_receipt.read_bytes())
    header = distribution["configurationPins"]["combinedHeader"]
    compiled_model = read_pinned(Path(header["path"]), header["sha256"])
    if model.encode("ascii") not in compiled_model or b"CLAW_PHYSICS_POSED_VR_SUPPORT" not in compiled_model:
        raise ValueError("Trace build has a different compiled pose model")
    native = distribution["lanes"]["trace"]["dll"]
    if b"claw-posed-vr-ack/1" not in read_pinned(Path(native["path"]), native["sha256"]):
        raise ValueError("Distribution DLL has no pose ACK trace")
    inputs["SKSE/Plugins/CLAWDistribution.dll"] = native

    scripts = json.loads(args.papyrus_receipt.read_bytes())
    if not scripts["compiled"] or not scripts["inputsUnchanged"] or scripts["installed"] or scripts["gameStarted"]:
        raise ValueError("Expected an offline pinned Papyrus build")
    records = scripts["commands"]
    script_names = {Path(item["pex"]["path"]).name for item in records}
    if len(records) != len(HOST_SCRIPTS) or script_names != HOST_SCRIPTS or any(item["exitCode"] for item in records):
        raise ValueError("Expected all six compiled host scripts")
    for item in records:
        script = item["pex"]
        name = Path(script["path"]).name
        pex = read_pinned(Path(script["path"]), script["sha256"])
        if not pex.startswith(b"\xfa\x57\xc0\xde") or (name == "CLAWPhysicsData.pex" and model.encode("ascii") not in pex):
            raise ValueError(f"Host script is not for the pinned model: {name}")
        if name in ("CLAWPhysicsHost.pex", "CLAWPhysicsNative.pex") and b"AcknowledgePoseSnapshot" not in pex:
            raise ValueError(f"Host and native façade must both support pose ACK: {name}")
        inputs[f"Scripts/{name}"] = script

    if args.host_plugin.name != PLUGIN:
        raise ValueError(f"Expected the original quest plugin {PLUGIN}")
    validate_plugin(args.host_plugin, recipe())
    inputs[PLUGIN] = pin(args.host_plugin)

    out.mkdir(parents=True, exist_ok=False)
    subject = out / "subject" / "Data"
    for name, origin in inputs.items():
        path = subject / PurePosixPath(name)
        if name in generated:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(generated[name])
        else:
            write_member(path, origin)
    report = {
        "schema": "claw-vr-pose-host-staging/1", "model": model,
        "fixture": {"plugin": FIXTURE, "baseLocalId": "000800", "race": "Skyrim.esm|0CDD84", "sex": "male", "weight": 50},
        "affectedGroups": {node: [slot for slot, owner in active if owner == node] for node in nodes},
        "playerSphere": {"node": "LeftWandNode", "centerLocalGu": [0, -6, -2], "radiusAtUnitScaleGu": 3},
        "originReceipts": [pin(path) for path in (vfs, current_vfs, args.profile, args.trace_receipt,
                                                  args.papyrus_receipt, args.pose_witness_receipt)],
        "inputMembers": inputs,
        "stagedMembers": {p.relative_to(subject).as_posix(): pin(p) for p in sorted(subject.rglob("*")) if p.is_file()},
        "expectedProfileDependencies": dependencies,
        "expectedCbpcConfigInventory": stock["cbpcConfigInventory"],
        "mustBeAbsent": stock["mustBeAbsent"],
        "installed": False, "gameValidated": False,
    }
    target = out / "subject-staging.json"
    with target.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    return pin(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("stock-case", "profile", "trace-receipt", "papyrus-receipt", "pose-witness-receipt",
                 "host-plugin", "body-assets", "skeleton", "carrier", "racemenu", "racemenu-vr", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    try:
        print(json.dumps(stage(parser.parse_args())))
    except (ValueError, OSError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
