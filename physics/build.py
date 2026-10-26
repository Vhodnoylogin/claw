"""Validate/build an offline CBPC motion + actor-capsule source candidate. Never install."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
NODES = ("NPC EarL [EarL]Bone01", "NPC EarL [EarL]Bone02",
         "NPC EarR [EarR]Bone01", "NPC EarR [EarR]Bone02",
         "TailBone01", "TailBone02", "TailBone03", "TailBone04", "TailBone05")
ALIASES = ("CLAW_EarL", "CLAW_EarR", "CLAW_Tail")
SCRIPTS = ("CLAWPhysicsActor.psc", "CLAWPhysicsHost.psc", "CLAWPhysicsLoadRelay.psc", "CLAWPhysicsControl.psc")
PARAMETERS = {
    "stiffness", "stiffness2", "damping", "timetick", "timeStep", "timeStepRot", "forceMultipler",
    "linearX", "linearY", "linearZ", "rotationalX", "rotationalY", "rotationalZ",
    "gravityBias", "gravityCorrection", "collisionFriction", "collisionPenetration",
    "collisionMultipler", "collisionMultiplerRot", "collisionElastic", "collisionElasticConstraints",
    *(f"linear{axis}rotation{other}" for axis in "XYZ" for other in "XYZ"),
    *(f"collision{axis}{side}offset" for axis in "XYZ" for side in ("min", "max"))
}

def number(value, low=-100, high=100):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError("Invalid/nonfinite candidate number")
    return value

def validate(recipe, capsules):
    if recipe["schemaVersion"] != 1 or recipe["namespace"] != "CLAW.Physics":
        raise ValueError("Unsupported physics recipe")
    if recipe["raceCondition"] != "IsRaceFormId(Skyrim.esm|000CDD84)":
        raise ValueError("Motion must remain restricted to the current vanilla werewolf race")
    if type(recipe["indexBase"]) is not int or recipe["indexBase"] != 0x434C0000:
        raise ValueError("Reserved CLAW.Physics index range changed")
    if tuple(g["alias"] for g in recipe["groups"]) != ALIASES:
        raise ValueError("Only isolated CLAW aliases are allowed")
    if tuple(node for g in recipe["groups"] for node in g["nodes"]) != NODES:
        raise ValueError("XP32 chains/order changed; keep TailBone04 and CME wrappers untouched")
    if set(recipe["common"]) != PARAMETERS:
        raise ValueError("Unsupported/missing CBPC parameter")
    for value in recipe["common"].values(): number(value)
    for key in ("stiffness", "stiffness2", "damping", "timeStep", "timeStepRot"):
        number(recipe["common"][key], 0.001, 1)
    number(recipe["common"]["forceMultipler"], 0.001, 0.1)
    for key in ("rotationalX", "rotationalY", "rotationalZ"): number(recipe["common"][key], 0, 0.03)
    for group in recipe["groups"]:
        number(group["maxOffset"], 0.01, 0.5); number(group["maxOffsetRot"], 0.01, 0.5)
    policy = recipe["capsulePolicy"]
    number(policy["radiusScale"], 0.01, 0.5); number(policy["maximumRadius"], 0.01, 2)
    if policy["scaleWeight"] != 0: raise ValueError("Unexpected scale policy")
    if capsules["schemaVersion"] != 1 or capsules["frame"] != "node-local-game-units":
        raise ValueError("Capsules must use node-local frames, never ragdoll frames")
    for key in ("xp32Sha256", "maleNifSha256", "femaleNifSha256", "measurementSha256"):
        if not re.fullmatch("[0-9a-f]{64}", capsules["provenance"][key]): raise ValueError("Missing input hash")
    for sex in ("male", "female"):
        if set(capsules[sex]) != set(NODES): raise ValueError("Missing/unknown capsule bone")
        for name, capsule in capsules[sex].items():
            if name == "TailBone04":
                if capsule is not None: raise ValueError("No fabricated TailBone04 collider")
                continue
            if not isinstance(capsule, dict) or set(capsule) != {"p1", "p2", "radius", "points"}:
                raise ValueError("Incomplete capsule record")
            for key in ("p1", "p2"):
                if len(capsule[key]) != 3: raise ValueError("Capsule endpoint must have three components")
                for value in capsule[key]: number(value)
            number(capsule["radius"], 0.001, 20)
            if type(capsule["points"]) is not int or capsule["points"] < 3: raise ValueError("Insufficient measured skin points")

def render_motion(recipe):
    master = ["# CLAW.Physics development candidate; no global settings or collision-config replacement.", "[ConfigMap]"]
    bounce = ["# Original conservative trial values; not game-qualified. Both weight endpoints identical.",
              "# No Conditions: these unique aliases are reached only by race-gated ConfigMap rows."]
    for group in recipe["groups"]:
        master.append("<")
        master.extend(f'{node}={group["alias"]}={recipe["raceCondition"]}' for node in group["nodes"])
        master.append(">")
        parameters = dict(recipe["common"])
        for axis in "XYZ":
            for suffix, magnitude in (("offset", group["maxOffset"]), ("offsetRot", group["maxOffsetRot"])):
                parameters[f"{axis}max{suffix}"] = magnitude
                parameters[f"{axis}min{suffix}"] = -magnitude
        bounce.append("")
        bounce.extend(f'{group["alias"]}.{name} {value:g}' for name, value in sorted(parameters.items()))
    return "\n".join(master) + "\n", "\n".join(bounce) + "\n"

def render_data(recipe, capsules):
    lines = ['Scriptname CLAWPhysicsData Hidden', '; Generated from pinned own measurements; no NIF edits.',
             'String Function Node(Int slot) Global']
    for index, name in enumerate(NODES):
        lines += [("  If" if index == 0 else "  ElseIf") + f" slot == {index}", f'    Return "{name}"']
    lines += ['  EndIf', '  Return ""', 'EndFunction', '',
              'Int Function ColliderIndex(Int slot) Global', f'  Return {recipe["indexBase"]} + slot', 'EndFunction', '',
              'Bool Function HasCapsule(Int slot) Global', '  Return slot >= 0 && slot < 9 && slot != 7', 'EndFunction', '',
              'Float[] Function Point(Int slot, Bool female, Bool second) Global', '  Float[] result = new Float[3]']
    first = True
    for sex in ("male", "female"):
        for index, name in enumerate(NODES):
            cap = capsules[sex][name]
            if cap is None: continue
            for second in (False, True):
                clause = f'slot == {index} && female == {str(sex == "female")} && second == {str(second)}'
                lines.append(('  If ' if first else '  ElseIf ') + clause); first = False
                for component, value in enumerate(cap['p2' if second else 'p1']): lines.append(f'    result[{component}] = {value:.6f}')
    lines += ['  EndIf', '  Return result', 'EndFunction', '', 'Float Function Radius(Int slot, Bool female) Global']
    first = True
    for sex in ("male", "female"):
        for index, name in enumerate(NODES):
            cap = capsules[sex][name]
            if cap is None: continue
            radius = min(cap["radius"] * recipe["capsulePolicy"]["radiusScale"], recipe["capsulePolicy"]["maximumRadius"])
            lines += [('  If ' if first else '  ElseIf ') + f'slot == {index} && female == {str(sex == "female")}', f'    Return {radius:.6f}']; first = False
    lines += ['  EndIf', '  Return 0.0', 'EndFunction']
    return "\n".join(lines) + "\n"

def destination(path):
    out = path.resolve()
    if out.exists(): raise ValueError("Output must be a new staging directory")
    if out == REPO or REPO in out.parents and not REPO / "work" in out.parents:
        raise ValueError("Output cannot be a source directory")
    if {part.lower() for part in out.parts} & {"data", "mods", "overwrite", "downloads"}:
        raise ValueError("Output cannot be a live game/mod/archive directory")
    for parent in out.parents:
        if (parent / ".git").exists() and not (parent == REPO and REPO / "work" in out.parents):
            raise ValueError("Output cannot be inside another checkout")
    return out

def check_master_conflicts(directory):
    """Inspect an explicitly supplied effective provider snapshot, never guess MO2 winners."""
    if not directory.is_dir(): raise ValueError("Provider snapshot directory is missing")
    paths = sorted(p for p in directory.iterdir() if p.is_file()
                   and p.name.lower().startswith("cbpcmasterconfig") and p.suffix.lower() in {".txt", ".ini"})
    if not paths: raise ValueError("Provider snapshot contains no master config")
    conflicts = []
    for path in paths:
        active = False
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            line = raw.split("#", 1)[0].strip()
            if line.startswith("["): active = line == "[ConfigMap]"
            elif active and line.split("=", 1)[0].strip() in NODES:
                conflicts.append({"path":str(path),"mapping":line})
    if conflicts: raise ValueError("Existing ear/tail driver mapping: " + json.dumps(conflicts))

def verify_measurements(capsules, path):
    payload=path.read_bytes()
    if hashlib.sha256(payload).hexdigest()!=capsules["provenance"]["measurementSha256"]:
        raise ValueError("Measurement hash differs from the pinned source")
    rows=json.loads(payload)
    for sex in ("male","female"):
        extracted={}
        for chain in rows[sex]:
            for link in chain["links"]:
                cap=link["capsule"]
                extracted[link["bone"]]=None if cap is None else {
                    "p1":cap["p1"],"p2":cap["p2"],"radius":cap["radius"],"points":link["points"]}
        if extracted!=capsules[sex]: raise ValueError("Capsule source data differs from the measurements")

def build(out, recipe, capsules):
    out = destination(out)
    master, bounce = render_motion(recipe)
    out.mkdir(parents=True, exist_ok=False)
    plugins = out / "SKSE/Plugins"; plugins.mkdir(parents=True)
    source = out / "Scripts/Source"; source.mkdir(parents=True)
    (plugins / "CBPCMasterConfig_CLAWPhysics.txt").write_text(master, encoding="utf-8")
    (plugins / "CBPConfig_CLAWPhysics.txt").write_text(bounce, encoding="utf-8")
    (source / "CLAWPhysicsData.psc").write_text(render_data(recipe, capsules), encoding="utf-8")
    for name in SCRIPTS:
        shutil.copyfile(ROOT / "papyrus" / name, source / name)
    shutil.copyfile(ROOT / "README.md", out / "README.md")
    manifest = {"schemaVersion":1, "namespace":"CLAW.Physics", "status":"source-candidate", "releaseReady":False,
        "gameValidated":False, "capsuleSlots":8, "motionNodes":9,
        "host":{"included":"optional-source-only", "maximumActorSlots":16, "automaticAssignment":False,
                "pluginRecordsIncluded":False, "lifecycleDeliveryValidated":False},
        "recipe":recipe, "measurementProvenance":capsules["provenance"],
        "sourceInputs":[{"path":str(path.relative_to(ROOT)),"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
                        for path in (ROOT/"recipe.json",ROOT/"capsules.json",ROOT/"sources.json",ROOT/"README.md",Path(__file__),
                                     *(ROOT/"papyrus"/name for name in SCRIPTS))],
        "outputs":[{"path":str(path.relative_to(out)),"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
                   for path in sorted(out.rglob("*")) if path.is_file()]}
    (out / "claw-physics-source.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    return manifest

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,help="new offline staging directory; omission validates only")
    parser.add_argument("--check-provider",type=Path,help="explicit effective SKSE/Plugins snapshot; check duplicate motion drivers")
    parser.add_argument("--measurements",type=Path,help="verify exact pinned Morphbench measurement data")
    args = parser.parse_args(argv)
    try:
        recipe=json.loads((ROOT/"recipe.json").read_text()); capsules=json.loads((ROOT/"capsules.json").read_text())
        validate(recipe,capsules)
        if args.check_provider: check_master_conflicts(args.check_provider)
        if args.measurements: verify_measurements(capsules,args.measurements)
        if args.out: build(args.out,recipe,capsules)
        print(json.dumps({"status":"source-candidate" if args.out else "valid", "motionNodes":9,"capsuleSlots":8,"gameValidated":False}))
        return 0
    except (OSError,KeyError,TypeError,ValueError) as error:
        print("CLAW physics: "+str(error),file=sys.stderr); return 2

if __name__ == "__main__": raise SystemExit(main())
