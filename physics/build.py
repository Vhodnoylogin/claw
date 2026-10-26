"""Validate/build an offline CBPC motion + actor-capsule source candidate. Never install."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
# Anchor provenance to the code actually loaded, including when a stale .pyc was
# used or the builder was edited after import. Compile from captured bytes and
# compare with the live module code, rather than hashing whatever is on disk later.
BUILDER_BYTES = Path(__file__).read_bytes()
if compile(BUILDER_BYTES, sys._getframe().f_code.co_filename, "exec", dont_inherit=True,
           optimize=sys.flags.optimize) != sys._getframe().f_code:
    raise ValueError("Builder source bytes do not match the loaded code")
NODES = ("NPC EarL [EarL]Bone01", "NPC EarL [EarL]Bone02",
         "NPC EarR [EarR]Bone01", "NPC EarR [EarR]Bone02",
         "TailBone01", "TailBone02", "TailBone03", "TailBone04", "TailBone05")
ALIASES = ("CLAW_EarL", "CLAW_EarR", "CLAW_Tail")
BREAST_NODES = ("NPC L Breast P1", "NPC R Breast P1")
# Exact ancestor union in the pinned b64b614d XP32 donor. A configured simulation
# on these nodes can move P1 by inheritance; ordinary animation is not scanned.
BREAST_ANCESTORS = ("NPC L PreBreast P1", "NPC R PreBreast P1", "Breast P1", "CME Spine2 [Spn2]",
                    "NPC Spine2 [Spn2]", "CME Spine1 [Spn1]", "NPC Spine1 [Spn1]", "CME Spine [Spn0]",
                    "NPC Spine [Spn0]", "CME UBody [UBody]", "CME Body [Body]", "NPC COM [COM ]",
                    "NPC Root [Root]", "NPC", "skeleton.nif")
BREAST_ALIASES = ("CLAW_BreastL", "CLAW_BreastR")
ORDINARY_BREAST_NODES = tuple(f"NPC {side} {part}" for side in ("L", "R") for part in ("Breast", "Breast01")) + tuple(
    f"{side} Breast0{part}" for side in ("L", "R") for part in (1, 2, 3))
SCRIPTS = ("CLAWPhysicsActor.psc", "CLAWPhysicsHost.psc", "CLAWPhysicsLoadRelay.psc", "CLAWPhysicsControl.psc", "CLAWPhysicsNative.psc")
PARAMETERS = {
    "stiffness", "stiffness2", "damping", "timetick", "timeStep", "timeStepRot", "forceMultipler",
    "linearX", "linearY", "linearZ", "rotationalX", "rotationalY", "rotationalZ",
    "gravityBias", "gravityCorrection", "collisionFriction", "collisionPenetration",
    "collisionMultipler", "collisionMultiplerRot", "collisionElastic", "collisionElasticConstraints",
    *(f"linear{axis}rotation{other}" for axis in "XYZ" for other in "XYZ"),
    *(f"collision{axis}{side}offset" for axis in "XYZ" for side in ("min", "max"))
}


class SourceInputs:
    """Read once, consume these exact bytes, and reject subsequent disk changes."""
    def __init__(self, breast=False, breast_contact=False, breast_profile=None):
        self.root = ROOT
        self.breast_contact = breast_contact
        self.breast_name = "breast-contact-motion.json" if breast_contact else "breast-motion.json"
        self.breast_profile = None
        names = ["recipe.json", "capsules.json", "sources.json", "README.md", "build.py",
                 *("papyrus/" + name for name in SCRIPTS)]
        if breast or breast_contact: names.append(self.breast_name)
        self.payloads = {name:(self.root / name).read_bytes() for name in names}
        if breast_profile is not None:
            payload = breast_profile.read_bytes()
            if len(payload) > 1024 * 1024: raise ValueError("Breast resource profile exceeds 1 MiB")
            self.breast_profile = {"path":str(breast_profile.resolve()), "payload":payload,
                                   "sha256":hashlib.sha256(payload).hexdigest()}
        if self.payloads["build.py"] != BUILDER_BYTES:
            raise ValueError("Builder source changed since its code was loaded")

    def json(self, name):
        return json.loads(self.payloads[name])

    def rows(self):
        rows = [{"path":name, "sha256":hashlib.sha256(payload).hexdigest()}
                for name, payload in self.payloads.items()]
        if self.breast_profile: rows.append({"path":self.breast_profile["path"], "sha256":self.breast_profile["sha256"], "role":"explicit-breast-resource-profile"})
        return rows

    def verify(self):
        for name, payload in self.payloads.items():
            if (self.root / name).read_bytes() != payload:
                raise ValueError("Source input changed after consumption: " + name)
        if self.breast_profile and Path(self.breast_profile["path"]).read_bytes() != self.breast_profile["payload"]:
            raise ValueError("Breast resource profile changed after consumption")


class NoDoctypeTreeBuilder(ET.TreeBuilder):
    def doctype(self, name, pubid, system):
        # Expat reports DOCTYPE after decoding XML's declared encoding, so UTF-16
        # cannot bypass this guard and entity declarations are never consumed.
        raise ValueError("DTD/entity declarations are unsupported")

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

def fitted_model(path):
    """Consume an explicit offline fit, never infer a mesh from a live profile."""
    payload = path.read_bytes()
    model = json.loads(payload)
    validate_fitted_model(model)
    return {"model": model, "input": {"path":str(path.resolve()), "bytes":len(payload),
                                       "sha256":hashlib.sha256(payload).hexdigest()}}


def validate_fitted_model(model):
    if type(model.get("schemaVersion")) is not int or model["schemaVersion"] not in (1, 2, 3) or model.get("frame") != "node-local-game-units":
        raise ValueError("Unsupported fitted capsule model/frame")
    if model.get("domain") != [0, 1] or any(isinstance(value, bool) for value in model["domain"]):
        raise ValueError("Fitted morph domain must be the explicit closed [0,1] box")
    names = model.get("morphs")
    if not isinstance(names, list) or not 1 <= len(names) <= 32 or not all(isinstance(name, str) for name in names) or len(set(names)) != len(names):
        raise ValueError("Fitted model needs 1..32 distinct ordered effective morph names")
    if not all(isinstance(name, str) and re.fullmatch(r"CLAW[A-Za-z0-9_]{1,64}", name) for name in names):
        raise ValueError("Invalid fitted morph name")
    if model["schemaVersion"] == 3:
        if "weightDependent" in model and type(model["weightDependent"]) is not bool:
            raise ValueError("Weight dependence must be an explicit boolean")
        slots = model.get("slots")
        if not isinstance(slots, list) or not 1 <= len(slots) <= 128:
            raise ValueError("Current-vector model requires 1..128 stable slots")
        if not re.fullmatch(r"CLAW\.Physics\.CurrentVector\.[0-9a-f]{64}", model.get("modelIdentity", "")):
            raise ValueError("Current-vector model identity must pin its own complete support data")
        identity_keys = ("evaluator", "morphs", "regions", "slots") + (("weightDependent",) if "weightDependent" in model else ())
        canonical = json.dumps({key:model[key] for key in identity_keys}, sort_keys=True, separators=(",", ":")).encode()
        if model["modelIdentity"] != "CLAW.Physics.CurrentVector." + hashlib.sha256(canonical).hexdigest():
            raise ValueError("Current-vector model identity differs from its complete support data")
        regions = model.get("regions")
        if not isinstance(regions, dict): raise ValueError("Current-vector support regions missing")
        for slot in slots:
            if slot.get("node") not in NODES + BREAST_NODES or slot["node"] == "TailBone04":
                raise ValueError("Current-vector slot must retain measured existing XP32 ear/tail nodes")
            female_only = slot.get("sexMask") == "female"
            if slot.get("sexMask") not in (None, "both", "female"):
                raise ValueError("Unknown capsule sex mask")
            if female_only and slot["node"] not in BREAST_NODES or slot["node"] in BREAST_NODES and not female_only:
                raise ValueError("P1 slots require explicit female-only metadata")
            for sex in ("male", "female"):
                if female_only and sex == "male":
                    if slot.get(sex) is not None: raise ValueError("Female P1 slot cannot supply male contact data")
                    continue
                region = regions.get(sex + "/" + slot["node"])
                if not isinstance(region, dict) or not isinstance(slot.get(sex), dict):
                    raise ValueError("Current-vector model requires both measured sexes")
                if not region.get("points") or not isinstance(region.get("deltas"), dict):
                    raise ValueError("Current-vector support points/deltas missing")
                for point in region["points"]:
                    if not isinstance(point, list) or len(point) != 3: raise ValueError("Invalid support xyz")
                    for value in point: number(value)
                if model.get("weightDependent"):
                    weight_deltas = region.get("weightDeltas")
                    if not isinstance(weight_deltas, list) or len(weight_deltas) != len(region["points"]):
                        raise ValueError("Weight-dependent model needs complete endpoint base deltas")
                    for vector in weight_deltas:
                        if len(vector) != 3: raise ValueError("Invalid weight endpoint xyz")
                        for value in vector: number(value)
                for name, values in region["deltas"].items():
                    if name not in names or len(values) != len(region["points"]): raise ValueError("Invalid sparse morph field")
                    for vector in values:
                        if len(vector) != 3: raise ValueError("Invalid morph field xyz")
                        for value in vector: number(value)
                selected = slot[sex].get("partitionIndices")
                if not isinstance(selected, list) or len(selected) < 2 or not all(type(value) is int and 0 <= value < len(region["points"]) for value in selected):
                    raise ValueError("Current-vector slot has invalid support indices")
        return
    if model["schemaVersion"] == 2:
        slots = model.get("slots")
        if not isinstance(slots, list) or not 1 <= len(slots) <= 32 or not all(isinstance(row, dict) for row in slots):
            raise ValueError("Fitted bundle must supply 1..32 stable capsule slots")
        if set(row.get("node") for row in slots) != set(NODES) - {"TailBone04"}:
            raise ValueError("Bundle must retain the eight measured nodes and omit unmeasured TailBone04")
    else:
        for sex in ("male", "female"):
            if not isinstance(model.get(sex), dict) or set(model[sex]) != set(NODES) or model[sex]["TailBone04"] is not None:
                raise ValueError("Fitted node list must retain the exact nine existing XP32 nodes; no fabricated TailBone04")
    for sex in ("male", "female"):
        for index, node in enumerate(data_nodes(model)):
            row = data_row(model, sex, index)
            if row is None:
                if model["schemaVersion"] == 2: raise ValueError("Each bundle slot requires both measured sexes")
                continue
            if not isinstance(row, dict) or not isinstance(row.get("coefficients"), dict) or not set(row["coefficients"]) <= set(names):
                raise ValueError("Invalid fitted capsule coefficients")
            for part in [row.get("base"), *row["coefficients"].values()]:
                if not isinstance(part, dict) or not {"p1", "p2", "radius"} <= set(part):
                    raise ValueError("Incomplete fitted capsule vector")
                for key in ("p1", "p2"):
                    if not isinstance(part[key], list) or len(part[key]) != 3: raise ValueError("Fitted endpoint requires xyz")
                    for value in part[key]: number(value)
                number(part["radius"])
            # The serialized affine radius is bounded analytically over the box.
            low = row["base"]["radius"] + sum(min(0, p["radius"]) for p in row["coefficients"].values())
            high = row["base"]["radius"] + sum(max(0, p["radius"]) for p in row["coefficients"].values())
            if not 0.001 <= low <= high <= 100:
                raise ValueError("Fitted capsule radius becomes invalid inside its morph domain")


def data_nodes(model=None):
    return NODES if model is None or model["schemaVersion"] == 1 else tuple(row["node"] for row in model["slots"])


def data_row(model, sex, index):
    return model[sex][NODES[index]] if model["schemaVersion"] == 1 else model["slots"][index].get(sex)


def capsule_slot_count(model=None):
    return len(data_nodes(model))


def expected_capsule_count(model=None):
    return 8 if model is None or model["schemaVersion"] == 1 else capsule_slot_count(model)


def expected_capsule_count_for_sex(model, sex):
    if model is not None and model["schemaVersion"] == 3:
        return sum(slot.get(sex) is not None for slot in model["slots"])
    return expected_capsule_count(model)


def verify_fitted_unchanged(fitted):
    if fitted is not None:
        pin = fitted["input"]
        payload = Path(pin["path"]).read_bytes()
        if hashlib.sha256(payload).hexdigest() != pin["sha256"] or json.loads(payload) != fitted["model"]:
            raise ValueError("Fitted capsule model changed after consumption")


def render_morph_data(model=None):
    names = [] if model is None else model["morphs"]
    lines = ["", "Int Function MorphCount() Global", f"  Return {len(names)}", "EndFunction", "",
             "String Function MorphName(Int index) Global"]
    for index, name in enumerate(names):
        lines += [("  If" if index == 0 else "  ElseIf") + f" index == {index}", f'    Return "{name}"']
    if names: lines += ["  EndIf"]
    lines += ['  Return ""', "EndFunction", "", "Bool Function MorphValuesValid(Float[] values) Global"]
    if names:
        lines += [f"  If values == None || values.Length != {len(names)}", "    Return False", "  EndIf",
                  "  Return MorphValuesValidCopy(values)"]
    else:
        lines += ["  Return values == None || values.Length == 0"]
    lines += ["EndFunction", "", "Bool Function MorphValuesValidCopy(Float[] values) Global"]
    if names:
        lines += [f"  If values == None || values.Length < {len(names)}", "    Return False", "  EndIf", "  Int index = 0",
                  f"  While index < {len(names)}", "    If !(values[index] >= 0.0 && values[index] <= 1.0)",
                  "      Return False", "    EndIf", "    index += 1", "  EndWhile"]
    lines += ["  Return True", "EndFunction", "",
              "Float[] Function PointForMorphs(Int slot, Bool female, Bool second, Float[] values) Global",
              "  Float[] result = Point(slot, female, second)"]
    if model and model["schemaVersion"] == 3:
        lines += ["  ; Current-vector geometry must come from the exact native snapshot.",
                  "  Return None", "EndFunction", "",
                  "Float Function RadiusForMorphs(Int slot, Bool female, Float[] values) Global",
                  "  Return -1.0", "EndFunction"]
        return "\n".join(lines) + "\n"
    if model and model["schemaVersion"] != 3:
        first = True
        for sex in ("male", "female"):
            for slot, node in enumerate(data_nodes(model)):
                row = data_row(model, sex, slot)
                if row is None: continue
                for second in (False, True):
                    part = "p2" if second else "p1"
                    changes = [(names.index(name), vector[part]) for name, vector in row["coefficients"].items() if any(vector[part])]
                    if not changes: continue
                    lines += [("  If " if first else "  ElseIf ") + f"slot == {slot} && female == {str(sex == 'female')} && second == {str(second)}"]
                    first = False
                    for index, vector in changes:
                        for axis, value in enumerate(vector):
                            if value: lines += [f"    result[{axis}] += {value:.9f} * values[{index}]"]
        if not first: lines += ["  EndIf"]
    lines += ["  Return result", "EndFunction", "",
              "Float Function RadiusForMorphs(Int slot, Bool female, Float[] values) Global", "  Float result = Radius(slot, female)"]
    if model and model["schemaVersion"] != 3:
        first = True
        for sex in ("male", "female"):
            for slot, node in enumerate(data_nodes(model)):
                row = data_row(model, sex, slot)
                if row is None: continue
                changes = [(names.index(name), vector["radius"]) for name, vector in row["coefficients"].items() if vector["radius"]]
                if not changes: continue
                lines += [("  If " if first else "  ElseIf ") + f"slot == {slot} && female == {str(sex == 'female')}"]
                first = False
                for index, value in changes: lines += [f"    result += {value:.9f} * values[{index}]"]
        if not first: lines += ["  EndIf"]
    lines += ["  Return result", "EndFunction"]
    return "\n".join(lines) + "\n"


def render_data(recipe, capsules, model=None):
    identity = hashlib.sha256(json.dumps(model if model is not None else
        {"capsules":capsules,"policy":recipe["capsulePolicy"]}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if model and model["schemaVersion"] == 3: identity = model["modelIdentity"]
    lines = ['Scriptname CLAWPhysicsData Hidden', '; Generated from pinned own measurements; no NIF edits.',
             'String Function ModelIdentity() Global', f'  Return "{identity}"', 'EndFunction', '',
             'Bool Function NativeFitRequired() Global', f'  Return {str(model is not None and model["schemaVersion"] == 3)}', 'EndFunction', '',
             'String Function Node(Int slot) Global']
    for index, name in enumerate(data_nodes(model)):
        lines += [("  If" if index == 0 else "  ElseIf") + f" slot == {index}", f'    Return "{name}"']
    lines += ['  EndIf', '  Return ""', 'EndFunction', '',
              'Int Function ColliderIndex(Int slot) Global', f'  Return {recipe["indexBase"]} + slot', 'EndFunction', '',
              'Int Function SlotCount() Global', f'  Return {capsule_slot_count(model)}', 'EndFunction', '',
              'Int Function ExpectedCapsuleCount() Global', f'  Return {expected_capsule_count(model)}', 'EndFunction', '',
              'Bool Function HasCapsule(Int slot) Global', f'  Return slot >= 0 && slot < {capsule_slot_count(model)}' + (' && slot != 7' if model is None or model['schemaVersion'] == 1 else ''), 'EndFunction', '',
              'Int Function ExpectedCapsuleCountForSex(Bool female) Global', '  If female',
              f'    Return {expected_capsule_count_for_sex(model, "female")}', '  EndIf',
              f'  Return {expected_capsule_count_for_sex(model, "male")}', 'EndFunction', '',
              'Bool Function SlotEnabled(Int slot, Bool female) Global']
    if model and model["schemaVersion"] == 3:
        disabled = [index for index, slot in enumerate(model["slots"]) if slot.get("sexMask") == "female"]
        if disabled:
            lines += ['  If !female && (' + ' || '.join(f'slot == {index}' for index in disabled) + ')',
                      '    Return False', '  EndIf']
    lines += ['  Return HasCapsule(slot)', 'EndFunction', '',
              'Float[] Function Point(Int slot, Bool female, Bool second) Global', '  Float[] result = new Float[3]']
    first = True
    for sex in ("male", "female"):
        for index, name in enumerate(data_nodes(model)):
            row = None if model is None else data_row(model, sex, index)
            cap = capsules[sex][name] if model is None else (None if row is None or model["schemaVersion"] == 3 else row["base"])
            if cap is None: continue
            for second in (False, True):
                clause = f'slot == {index} && female == {str(sex == "female")} && second == {str(second)}'
                lines.append(('  If ' if first else '  ElseIf ') + clause); first = False
                for component, value in enumerate(cap['p2' if second else 'p1']): lines.append(f'    result[{component}] = {value:.6f}')
    if not first: lines += ['  EndIf']
    lines += ['  Return result', 'EndFunction', '', 'Float Function Radius(Int slot, Bool female) Global']
    first = True
    for sex in ("male", "female"):
        for index, name in enumerate(data_nodes(model)):
            row = None if model is None else data_row(model, sex, index)
            cap = capsules[sex][name] if model is None else (None if row is None or model["schemaVersion"] == 3 else row["base"])
            if cap is None: continue
            radius = cap["radius"] if model else min(cap["radius"] * recipe["capsulePolicy"]["radiusScale"], recipe["capsulePolicy"]["maximumRadius"])
            lines += [('  If ' if first else '  ElseIf ') + f'slot == {index} && female == {str(sex == "female")}', f'    Return {radius:.6f}']; first = False
    if not first: lines += ['  EndIf']
    lines += ['  Return 0.0', 'EndFunction']
    return "\n".join(lines) + "\n" + render_morph_data(model)

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
    """Check known static ownership; absence never qualifies a loaded provider."""
    audit = audit_provider(directory)
    require_provider_clear(audit)
    return audit


def provider_inputs(directory):
    directory = directory.resolve()
    if not directory.is_dir(): raise ValueError("Provider snapshot directory is missing")
    paths = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file(): continue
        relative = path.relative_to(directory)
        name = path.name.lower()
        relevant = path.suffix.lower() == ".xml" or (len(relative.parts) == 1 and (
            name in {"cbp.dll", "hdtsmp64.dll"} or
            name.startswith(("cbpconfig", "cbpcmasterconfig", "cbpcollisionconfig"))
            and path.suffix.lower() in {".txt", ".ini"}))
        if relevant:
            if directory not in path.resolve().parents:
                raise ValueError("Provider snapshot input escapes its directory")
            payload = path.read_bytes()
            paths.append((path, payload, {"path":relative.as_posix(), "bytes":len(payload),
                                       "sha256":hashlib.sha256(payload).hexdigest()}))
    return paths


def audit_provider(directory):
    """Inventory supplied winning bytes, preserving all declarations and conditions.

    We deliberately do not choose between duplicate rows, evaluate conditions,
    infer SMP selection, or infer loaded native ownership from a text search.
    """
    inputs = provider_inputs(directory)
    report = {"schemaVersion":1, "snapshot":str(directory.resolve()),
              "status":"static-audit-only", "runtimeQualified":False,
              "files":[row for _, _, row in inputs], "mappings":[],
              "privateAliasDefinitions":[], "smpReferences":[], "uncertainties":[],
              "scope":"Explicit SKSE/Plugins snapshot only; no VFS/archive, NIF extra-data, loaded-module, generated-binding or native-index proof"}
    all_nodes = set(NODES + BREAST_NODES + BREAST_ANCESTORS + ORDINARY_BREAST_NODES)
    all_aliases = set(ALIASES + BREAST_ALIASES)
    masters = 0
    for path, payload, record in inputs:
        name = path.name.lower()
        if path.suffix.lower() == ".xml":
            try:
                tree = ET.fromstring(payload, parser=ET.XMLParser(target=NoDoctypeTreeBuilder()))
                for element in tree.iter():
                    for attribute, value in [("#text", element.text or ""), *element.attrib.items()]:
                        if value.strip() in all_nodes:
                            report["smpReferences"].append({"path":record["path"], "element":element.tag,
                                                           "attribute":attribute, "node":value.strip()})
            except (ValueError, ET.ParseError) as error:
                report["uncertainties"].append({"path":record["path"], "error":str(error)})
            continue
        if path.suffix.lower() not in {".txt", ".ini"}: continue
        is_master = name.startswith("cbpcmasterconfig")
        if is_master: masters += 1
        try:
            text = payload.decode("utf-8-sig")
        except UnicodeError as error:
            report["uncertainties"].append({"path":record["path"], "error":str(error)})
            continue
        active = False
        for line_number, raw in enumerate(text.splitlines(), 1):
            line = raw.split("#", 1)[0].strip()  # CBPC Utility.hpp:skipComments only strips '#'.
            if is_master:
                if line.startswith("["): active = line == "[ConfigMap]"
                elif active and line and not line.startswith(("<", ">")):
                    # Pinned provider reads the first three '=' fields, not an arbitrary expression.
                    fields = [field.strip() for field in line.split("=")]
                    node = fields[0]
                    alias = fields[1] if len(fields) > 1 else ""
                    if node in all_nodes or alias in all_aliases:
                        report["mappings"].append({"path":record["path"], "line":line_number,
                            "node":node, "alias":alias, "condition":fields[2] if len(fields) > 2 else ""})
            elif name.startswith("cbpconfig") and line and not line.startswith("#"):
                token = line.split()[0]
                alias = token.split(".", 1)[0]
                if alias in all_aliases:
                    report["privateAliasDefinitions"].append({"path":record["path"], "line":line_number,
                                                              "alias":alias, "parameter":token})
    if not masters: report["uncertainties"].append({"error":"Provider snapshot contains no master config"})
    report["earTailConflicts"] = provider_conflicts(report, NODES, ALIASES)
    report["breastConflicts"] = provider_conflicts(report, BREAST_NODES + BREAST_ANCESTORS, BREAST_ALIASES)
    report["ordinaryBreastMappings"] = [row for row in report["mappings"] if row["node"] in ORDINARY_BREAST_NODES]
    report["ordinaryBreastMeaning"] = "These are separate XP32 branches; ordinary breast mappings alone establish neither P1 ownership nor P1 motion"
    return report


def provider_conflicts(report, nodes, aliases):
    return ([{"kind":"CBPC mapping", **row} for row in report["mappings"]
             if row["node"] in nodes or row["alias"] in aliases] +
            [{"kind":"private alias parameter", **row} for row in report["privateAliasDefinitions"] if row["alias"] in aliases] +
            [{"kind":"potential SMP reference", **row} for row in report["smpReferences"] if row["node"] in nodes])


def require_provider_clear(report, breast=False):
    conflicts = report["earTailConflicts"] + (report["breastConflicts"] if breast else [])
    if report["uncertainties"] or conflicts:
        raise ValueError("Provider snapshot unresolved: " + json.dumps({"conflicts":conflicts, "uncertainties":report["uncertainties"]}))


def verify_provider_unchanged(report):
    current = [row for _, _, row in provider_inputs(Path(report["snapshot"]))]
    if current != report["files"]:
        raise ValueError("Provider snapshot changed after audit")


def read_breast_recipe(source_inputs):
    recipe = source_inputs.json(source_inputs.breast_name)
    contact = source_inputs.breast_contact
    if recipe.get("schemaVersion") != 1 or recipe.get("namespace") != ("CLAW.Physics.Breast.Contact" if contact else "CLAW.Physics.Breast"):
        raise ValueError("Unsupported breast motion/contact recipe")
    if source_inputs.breast_profile is not None:
        profile = json.loads(source_inputs.breast_profile["payload"])
        if profile.get("schemaVersion") != 1 or not re.fullmatch(r"[A-Za-z0-9_.-]{1,160}", profile.get("id", "")) or profile.get("p1Bones") != list(BREAST_NODES):
            raise ValueError("Invalid explicit breast resource binding")
        inputs = profile.get("inputs", {})
        required = ("bodyNifSha256", "skeletonSha256") + (("bodyWeight1NifSha256",) if contact else ())
        if not all(re.fullmatch(r"[0-9a-f]{64}", inputs.get(name, "")) for name in required):
            raise ValueError("Breast resource binding lacks required exact input hashes")
        if inputs["skeletonSha256"] != recipe["inputs"]["skeletonSha256"]:
            raise ValueError("Breast resource profile changed the reviewed XP32 skeleton")
        if contact and not re.fullmatch(r"CLAW\.Physics\.CurrentVector\.[0-9a-f]{64}", profile.get("capsuleModelIdentity", "")):
            raise ValueError("P1 contact profile must bind an exact current-vector capsule model")
        recipe["inputs"] = inputs
        recipe["resourceProfile"] = {"id":profile["id"], "path":source_inputs.breast_profile["path"],
            "sha256":source_inputs.breast_profile["sha256"], "capsuleModelIdentity":profile.get("capsuleModelIdentity")}
    elif contact:
        raise ValueError("P1 contact requires an explicit current resource profile")
    expected_nodes = tuple(group["nodes"][0] for group in recipe["groups"])
    if expected_nodes != BREAST_NODES or tuple(group["alias"] for group in recipe["groups"]) != BREAST_ALIASES:
        raise ValueError("Breast motion must retain isolated existing XP32 P1 nodes/aliases")
    if recipe["raceCondition"] != "IsRaceFormId(Skyrim.esm|000CDD84) AND IsFemale()":
        raise ValueError("Breast motion must remain female and vanilla-werewolf gated")
    for group in recipe["groups"]:
        if len(group["nodes"]) != 1: raise ValueError("Breast motion cannot drive ancestors")
        number(group["maxOffset"], 0.001, 0.15)
        number(group["maxOffsetRot"], 0.001, 0.1)
    if set(recipe["commonOverrides"]) != {"forceMultipler", "rotationalX", "rotationalY", "rotationalZ",
                                          "collisionMultipler", "collisionMultiplerRot"}:
        raise ValueError("Unexpected breast trial parameter override")
    for key, value in recipe["commonOverrides"].items():
        maximum = 0.03 if key == "forceMultipler" else (0.05 if key == "collisionMultipler" and contact else (0.01 if key == "collisionMultiplerRot" and contact else 0.005))
        number(value, 0, maximum)
    if not contact and (recipe["commonOverrides"]["collisionMultipler"] != 0 or recipe["commonOverrides"]["collisionMultiplerRot"] != 0):
        raise ValueError("This breast source trial has no qualified contact model")
    if contact and (recipe["commonOverrides"]["collisionMultipler"] <= 0 or recipe["commonOverrides"]["collisionMultiplerRot"] <= 0):
        raise ValueError("P1 contact response cannot be silently disabled")
    recipe["common"] = {**source_inputs.json("recipe.json")["common"], **recipe["commonOverrides"]}
    return recipe


def breast_motion_inputs(body, skeleton, source_inputs=None, body_weight1=None):
    source_inputs = source_inputs or SourceInputs(breast=True)
    recipe = read_breast_recipe(source_inputs)
    pins = []
    selected = [("body", body, recipe["inputs"]["bodyNifSha256"]),
                ("skeleton", skeleton, recipe["inputs"]["skeletonSha256"])]
    if "bodyWeight1NifSha256" in recipe["inputs"]:
        selected.append(("bodyWeight1", body_weight1, recipe["inputs"]["bodyWeight1NifSha256"]))
    elif body_weight1 is not None:
        raise ValueError("Weight-1 breast body requires an explicit resource profile")
    for label, path, expected in selected:
        if path is None: raise ValueError("Breast motion requires explicit pinned body and XP32 skeleton inputs")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != expected: raise ValueError("Breast motion " + label + " hash differs from reviewed rig")
        pins.append({"kind":label, "path":str(path.resolve()), "sha256":digest})
    return recipe, pins


def require_breast_fit(breast, fitted):
    if not breast or breast[0].get("namespace") != "CLAW.Physics.Breast.Contact": return
    if fitted is None or fitted["model"].get("schemaVersion") != 3 or not fitted["model"].get("weightDependent"):
        raise ValueError("P1 contact requires a current-vector model with both independent weight endpoints")
    recipe, pins = breast
    model = fitted["model"]
    if recipe["resourceProfile"]["capsuleModelIdentity"] != model["modelIdentity"]:
        raise ValueError("Breast resource profile and capsule model identities differ")
    if {slot["node"] for slot in model["slots"] if slot.get("sexMask") == "female"} != set(BREAST_NODES):
        raise ValueError("P1 contact requires measured female-only slots for both existing P1 bones")
    source_hashes = {row.get("sha256") for row in model.get("sourceInputs", []) if isinstance(row, dict)}
    if not all(pin["sha256"] in source_hashes for pin in pins):
        raise ValueError("P1 capsule model does not pin the supplied body endpoints and XP32 skeleton")

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

def build(out, recipe, capsules, provider_audit=None, breast=None, source_inputs=None, fitted=None):
    out = destination(out)
    if breast and provider_audit is None: raise ValueError("Breast motion requires an explicit provider snapshot audit")
    source_inputs = source_inputs or SourceInputs(breast=breast is not None,
        breast_contact=breast is not None and breast[0].get("namespace") == "CLAW.Physics.Breast.Contact",
        breast_profile=None if breast is None or not breast[0].get("resourceProfile") else Path(breast[0]["resourceProfile"]["path"]))
    if recipe != source_inputs.json("recipe.json") or capsules != source_inputs.json("capsules.json"):
        raise ValueError("Parsed recipe/capsules differ from captured source inputs")
    if breast and breast[0] != read_breast_recipe(source_inputs):
        raise ValueError("Parsed breast recipe differs from captured source inputs")
    require_breast_fit(breast, fitted)
    source_inputs.verify()
    verify_fitted_unchanged(fitted)
    if provider_audit is not None:
        require_provider_clear(provider_audit, breast=breast is not None)
        verify_provider_unchanged(provider_audit)
    out.mkdir(parents=True, exist_ok=False)
    pending = out / "FAILED-unverified-do-not-install"
    pending.write_text("Build incomplete; only a completed manifest establishes offline checks.\n", encoding="utf-8")
    master, bounce = render_motion(recipe)
    plugins = out / "SKSE/Plugins"; plugins.mkdir(parents=True)
    source = out / "Scripts/Source"; source.mkdir(parents=True)
    (plugins / "CBPCMasterConfig_CLAWPhysics.txt").write_text(master, encoding="utf-8")
    (plugins / "CBPConfig_CLAWPhysics.txt").write_text(bounce, encoding="utf-8")
    if breast:
        breast_recipe, pins = breast
        for pin in pins:
            if hashlib.sha256(Path(pin["path"]).read_bytes()).hexdigest() != pin["sha256"]:
                raise ValueError("Breast input changed after validation")
        breast_master, breast_bounce = render_motion(breast_recipe)
        suffix = "CLAWBreastContact" if breast_recipe["namespace"] == "CLAW.Physics.Breast.Contact" else "CLAWBreastPhysics"
        (plugins / ("CBPCMasterConfig_" + suffix + ".txt")).write_text(breast_master, encoding="utf-8")
        (plugins / ("CBPConfig_" + suffix + ".txt")).write_text(breast_bounce, encoding="utf-8")
    (source / "CLAWPhysicsData.psc").write_text(render_data(recipe, capsules, None if fitted is None else fitted["model"]), encoding="utf-8")
    for name in SCRIPTS:
        (source / name).write_bytes(source_inputs.payloads["papyrus/" + name])
    (out / "README.md").write_bytes(source_inputs.payloads["README.md"])
    manifest = {"schemaVersion":1, "namespace":"CLAW.Physics", "status":"source-candidate", "releaseReady":False,
        "gameValidated":False, "capsuleSlots":expected_capsule_count(None if fitted is None else fitted["model"]), "motionNodes":11 if breast else 9,
        "host":{"included":"optional-source-only", "maximumActorSlots":16, "automaticAssignment":False,
                "pluginRecordsIncluded":False, "lifecycleDeliveryValidated":False},
        "recipe":recipe, "measurementProvenance":capsules["provenance"] if fitted is None else fitted["model"].get("sourceInputs"),
        "providerAudit":provider_audit,
        "fittedCapsules":None if fitted is None else {"input":fitted["input"], "model":fitted["model"],
             "effectiveAggregateRequired":True, "automaticMorphObserver":True, "runtimeFitQualified":False,
             "nativeModelRequired":fitted["model"]["schemaVersion"] == 3,
             "legacyRadiusHalvingApplied":False, "coordinateFrame":"node-local-game-units"},
        "breastMotion":None if breast is None else {"status":"uninstalled-source-trial", "recipe":breast[0],
             "inputs":breast[1], "runtimeOwnershipQualified":False, "contactQualified":False,
             "contactResponseNonzero":breast[0]["namespace"] == "CLAW.Physics.Breast.Contact",
             "contactModelIdentity":None if breast[0]["namespace"] != "CLAW.Physics.Breast.Contact" else fitted["model"]["modelIdentity"],
             "skeletonWritten":False, "capsulesAdded":False},
        "sourceInputs":source_inputs.rows(),
        "outputs":[{"path":str(path.relative_to(out)),"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
                   for path in sorted(out.rglob("*")) if path.is_file() and path != pending]}
    if provider_audit is not None: verify_provider_unchanged(provider_audit)
    if breast:
        for pin in breast[1]:
            if hashlib.sha256(Path(pin["path"]).read_bytes()).hexdigest() != pin["sha256"]:
                raise ValueError("Breast input changed during build")
    source_inputs.verify()
    verify_fitted_unchanged(fitted)
    (out / "claw-physics-source.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    pending.unlink()
    return manifest

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,help="new offline staging directory; omission validates only")
    parser.add_argument("--check-provider",type=Path,help="explicit effective SKSE/Plugins snapshot; check duplicate motion drivers")
    parser.add_argument("--measurements",type=Path,help="verify exact pinned Morphbench measurement data")
    parser.add_argument("--with-breast-motion",action="store_true",help="explicit uninstalled female P1 motion source trial; requires provider/body/skeleton pins")
    parser.add_argument("--with-breast-contact",action="store_true",help="explicit measured female P1 contact source trial; requires current weight-dependent model and matching resource profile")
    parser.add_argument("--breast-profile",type=Path,help="explicit reviewed resource profile for new pinned body endpoints; does not alter the legacy profile")
    parser.add_argument("--breast-body",type=Path,help="exact reviewed female P1 body weight-0 input")
    parser.add_argument("--breast-body-weight1",type=Path,help="exact reviewed female P1 body weight-1 input declared by resource profile")
    parser.add_argument("--skeleton",type=Path,help="read-only exact reviewed XP32 skeleton for breast source trial")
    parser.add_argument("--fitted-capsules",type=Path,help="explicit affine node-local ear/tail fit; requires effective morph snapshots at runtime")
    args = parser.parse_args(argv)
    try:
        if args.with_breast_motion and args.with_breast_contact:
            raise ValueError("Choose either breast motion-only or breast contact; duplicate P1 drivers are refused")
        source_inputs = SourceInputs(breast=args.with_breast_motion or args.with_breast_contact,
            breast_contact=args.with_breast_contact, breast_profile=args.breast_profile)
        recipe=source_inputs.json("recipe.json"); capsules=source_inputs.json("capsules.json")
        validate(recipe,capsules)
        fitted = fitted_model(args.fitted_capsules) if args.fitted_capsules else None
        audit = check_master_conflicts(args.check_provider) if args.check_provider else None
        breast = None
        if args.with_breast_motion or args.with_breast_contact:
            if audit is None: raise ValueError("Breast motion requires --check-provider with explicit winning bytes")
            require_provider_clear(audit, breast=True)
            breast = breast_motion_inputs(args.breast_body, args.skeleton, source_inputs, args.breast_body_weight1)
            require_breast_fit(breast, fitted)
        elif args.breast_body or args.breast_body_weight1 or args.breast_profile or args.skeleton:
            raise ValueError("Breast inputs require explicit --with-breast-motion")
        if args.measurements: verify_measurements(capsules,args.measurements)
        if args.out: build(args.out,recipe,capsules,audit,breast,source_inputs,fitted)
        else: source_inputs.verify()
        print(json.dumps({"status":"source-candidate" if args.out else "valid", "motionNodes":11 if breast else 9,
                          "capsuleSlots":expected_capsule_count(None if fitted is None else fitted["model"]),"providerAudited":audit is not None,"gameValidated":False}))
        return 0
    except (OSError,KeyError,TypeError,ValueError) as error:
        print("CLAW physics: "+str(error),file=sys.stderr); return 2

if __name__ == "__main__": raise SystemExit(main())
