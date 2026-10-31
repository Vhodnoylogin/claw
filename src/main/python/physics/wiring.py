"""Original finite quest wiring; JSON is used as a strict YAML-compatible source.

The binary readback below verifies the emitted record/VMAD wiring independently
of Spriggit text formatting. It does not execute aliases, Papyrus or CBPC.
"""
from __future__ import annotations
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parent
PLUGIN = "CLAW - Physics.esp"
QUEST = "000800:" + PLUGIN
EDITOR = "CLAWPhysicsHostQuest"
ACTOR_IDS = tuple(range(16))
PLAYER_ID = 16
GATES = ("ExclusiveIndexRange", "ProviderQualified", "StaticPoseAccepted")


def recipe():
    value = json.loads((ROOT / "host-wiring.json").read_text())
    validate_recipe(value)
    return value


def validate_recipe(value):
    expected = {"schemaVersion": 1, "plugin": PLUGIN, "masters": ["Skyrim.esm", "CLAW.esp"],
                "questFormId": "000800", "questEditorId": EDITOR, "actorAliasIds": list(ACTOR_IDS),
                "playerAliasId": PLAYER_ID, "playerReference": "000014:Skyrim.esm",
                "allowPlayerRelayReuse": True,
                "startGameEnabled": False, "integrationOptIn": False,
                "providerQualified": False, "exclusiveIndexRange": False, "staticPoseAccepted": False}
    # bool/int equality in Python must not admit True as schemaVersion/alias 1.
    if json.dumps(value, sort_keys=True) != json.dumps(expected, sort_keys=True):
        raise ValueError("Unsupported host wiring: stable IDs, explicit null actor fills and false gates are fixed")


def object_ref(alias):
    return {"Object": QUEST, "Alias": alias}


def bool_property(name):
    return {"MutagenObjectType": "ScriptBoolProperty", "Name": name, "Data": False}


def records(value):
    validate_recipe(value)
    adapter = {"Scripts": [{"Name": "CLAWPhysicsHost", "Properties": [
        {"MutagenObjectType": "ScriptObjectListProperty", "Name": "ActorSlots",
         "Objects": [object_ref(alias) for alias in ACTOR_IDS]}, bool_property("IntegrationOptIn")]}],
        "FileName": "", "Aliases": []}
    aliases = []
    for alias in (*ACTOR_IDS, PLAYER_ID):
        actor = alias != PLAYER_ID
        aliases.append({"ID": alias, "Name": f"CLAWPhysicsActor{alias:02d}" if actor else "CLAWPhysicsPlayerLoad",
                        "Flags": ["Optional", "AllowReuseInQuest"],
                        # An explicit null forced-reference field, never find-matching.
                        "ForcedReference": "Null" if actor else value["playerReference"]})
        script = {"Name": "CLAWPhysicsActor" if actor else "CLAWPhysicsLoadRelay"}
        if actor:
            script["Properties"] = [bool_property(name) for name in GATES]
        adapter["Aliases"].append({"Property": object_ref(alias), "Scripts": [script]})
    header = {"SpriggitSource": {"PackageName": "Spriggit.Yaml.Skyrim", "Version": 0.41},
              "ModKey": PLUGIN, "GameRelease": "SkyrimSE", "ModHeader": {
                  "FormVersion": 39, "Author": "CLAW", "Description": "Optional finite CLAW physics host; explicit opt-in and provider qualification required",
                  "MasterReferences": [{"Master": name, "FileSize": 0} for name in value["masters"]]}}
    quest = {"FormKey": QUEST, "EditorID": EDITOR, "VirtualMachineAdapter": adapter,
             "Name": {"TargetLanguage": "English", "Value": "CLAW optional physics host"},
             "Priority": 10, "NextAliasID": 17, "Aliases": aliases}
    return {"RecordData.yaml": header,
            "spriggit-meta.json": {"PackageName": "Spriggit.Yaml.Skyrim", "Version": "0.41.0", "Release": "SkyrimSE", "ModKey": PLUGIN},
            f"Quests/{EDITOR} - 000800_{PLUGIN}.yaml": quest}


def write_sources(out, value):
    paths = records(value)
    out.mkdir(parents=True, exist_ok=False)
    for relative, content in paths.items():
        path = out / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")


def validate_source_tree(folder, value):
    expected = records(value)
    actual = {p.relative_to(folder).as_posix(): json.loads(p.read_text()) for p in folder.rglob("*") if p.is_file()}
    if actual != expected:
        raise ValueError("Host source tree differs from the fixed same-quest wiring contract")


def validate_host_package(folder, script_names):
    expected = {PLUGIN, "README.md"}
    for name in script_names:
        expected.add("Scripts/" + Path(name).with_suffix(".pex").name)
        expected.add("Scripts/Source/" + name)
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()}
    if actual != expected:
        raise ValueError("Host-only package must contain exactly its ESP, own scripts and README; motion configs are separate")


class Reader:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def take(self, count):
        if count < 0 or self.pos + count > len(self.data):
            raise ValueError("Truncated plugin/VMAD field")
        value = self.data[self.pos:self.pos + count]
        self.pos += count
        return value

    def unpack(self, fmt):
        return struct.unpack(fmt, self.take(struct.calcsize(fmt)))[0]

    def string(self):
        return self.take(self.unpack("<H")).decode("utf-8")

    def object(self, object_format):
        if object_format != 2:
            raise ValueError("Only verified VMAD object format 2 is supported")
        unused = self.unpack("<H")
        alias = self.unpack("<h")
        form = self.unpack("<I")
        if unused:
            raise ValueError("Unexpected VMAD object padding")
        return {"form": form, "alias": alias}

    def scripts(self, object_format):
        result = []
        for _ in range(self.unpack("<H")):
            name, flags = self.string(), self.unpack("<B")
            properties = []
            for _ in range(self.unpack("<H")):
                prop, kind, prop_flags = self.string(), self.unpack("<B"), self.unpack("<B")
                if kind == 5:
                    raw = self.unpack("<B")
                    if raw not in (0, 1):
                        raise ValueError("Invalid VMAD boolean")
                    data = bool(raw)
                elif kind == 11:
                    data = [self.object(object_format) for _ in range(self.unpack("<I"))]
                else:
                    raise ValueError("Unexpected VMAD property type in finite host")
                properties.append({"name": prop, "type": kind, "flags": prop_flags, "data": data})
            result.append({"name": name, "flags": flags, "properties": sorted(properties, key=lambda p: p["name"])})
        return result


def vmad(data):
    reader = Reader(data)
    version, object_format = reader.unpack("<h"), reader.unpack("<H")
    scripts = reader.scripts(object_format)
    bind_version = reader.unpack("<B")
    fragments = reader.unpack("<H")
    filename = reader.string()
    if fragments or filename:
        raise ValueError("Unexpected quest fragment in manual-only host")
    aliases = []
    for _ in range(reader.unpack("<H")):
        ref = reader.object(object_format)
        alias_version, alias_format = reader.unpack("<h"), reader.unpack("<H")
        aliases.append({"object": ref, "version": alias_version, "format": alias_format,
                        "scripts": reader.scripts(alias_format)})
    if reader.pos != len(data):
        raise ValueError("Unexpected trailing quest VMAD data")
    return {"version": version, "format": object_format, "bindVersion": bind_version,
            "scripts": scripts, "aliases": aliases}


def subrecords(data):
    reader = Reader(data)
    result = []
    while reader.pos < len(data):
        kind, size = reader.take(4), reader.unpack("<H")
        if kind == b"XXXX":
            raise ValueError("Extended subrecord not expected in finite host")
        result.append((kind, reader.take(size)))
    return result


def plugin_records(data):
    reader, result = Reader(data), []
    while reader.pos < len(data):
        start = reader.pos
        kind, size = reader.take(4), reader.unpack("<I")
        rest = reader.take(16)
        if kind == b"GRUP":
            if size < 24:
                raise ValueError("Invalid group size")
            if rest[:4] != b"QUST" or struct.unpack_from("<I", rest, 4)[0] != 0:
                raise ValueError("Only the top-level original quest group is allowed")
            result.extend(plugin_records(reader.take(size - 24)))
        else:
            flags, form = struct.unpack_from("<II", rest)
            if flags & 0x40000:
                raise ValueError("Compressed records are not used by this host")
            result.append({"type": kind, "flags": flags, "form": form, "fields": subrecords(reader.take(size))})
        if reader.pos <= start:
            raise ValueError("Invalid plugin record")
    return result


def inspect_plugin(path):
    rows = plugin_records(path.read_bytes())
    if [r["type"] for r in rows] != [b"TES4", b"QUST"]:
        raise ValueError("Finite host must contain only a TES4 header and its original quest")
    header, quest = rows
    if header["flags"] or quest["flags"]:
        raise ValueError("Host must be an ordinary uncompressed ESP without ESL/master/deleted flags")
    masters = [v.rstrip(b"\0").decode() for k, v in header["fields"] if k == b"MAST"]
    fields = quest["fields"]
    allowed = {b"EDID", b"VMAD", b"FULL", b"DNAM", b"NEXT", b"ANAM", b"ALST", b"ALID", b"FNAM", b"ALFR", b"ALED"}
    if any(k not in allowed for k, _ in fields):
        raise ValueError("Unexpected quest behavior/stage/fill field")
    unique = {k: v for k, v in fields if k in (b"EDID", b"DNAM", b"ANAM", b"VMAD")}
    if len(unique) != 4 or any(sum(k == key for k, _ in fields) != 1 for key in unique):
        raise ValueError("Missing quest control/VMAD fields")
    aliases, current = [], None
    allowed_alias = {b"ALST", b"ALID", b"FNAM", b"ALFR", b"ALED"}
    for kind, data in fields:
        if kind == b"ALST":
            if current is not None:
                raise ValueError("Unterminated alias")
            current = {"id": struct.unpack("<I", data)[0]}
        elif current is not None:
            if kind not in allowed_alias:
                raise ValueError("Unexpected alias fill/behavior field: " + kind.decode())
            if kind == b"ALID": current["name"] = data.rstrip(b"\0").decode()
            if kind == b"FNAM": current["flags"] = struct.unpack("<I", data)[0]
            if kind == b"ALFR": current["forced"] = struct.unpack("<I", data)[0]
            if kind == b"ALED": aliases.append(current); current = None
    if current is not None:
        raise ValueError("Unterminated alias")
    return {"masters": masters, "questForm": quest["form"], "editorId": unique[b"EDID"].rstrip(b"\0").decode(),
            "questData": unique[b"DNAM"].hex(), "nextAlias": struct.unpack("<I", unique[b"ANAM"])[0],
            "aliases": aliases, "vmad": vmad(unique[b"VMAD"])}


def validate_plugin(path, value):
    validate_recipe(value)
    result = inspect_plugin(path)
    quest_form = (len(value["masters"]) << 24) | 0x800
    def prop(name, kind, data):
        return {"name": name, "type": kind, "flags": 1, "data": data}
    def script(name, properties):
        return {"name": name, "flags": 0, "properties": properties}
    host = script("CLAWPhysicsHost", [prop("ActorSlots", 11, [{"form": quest_form, "alias": a} for a in ACTOR_IDS]),
                                      prop("IntegrationOptIn", 5, False)])
    alias_scripts = [{"object": {"form": quest_form, "alias": a}, "version": 5, "format": 2,
                      "scripts": [script("CLAWPhysicsActor", [prop(n, 5, False) for n in GATES])
                                  if a != PLAYER_ID else script("CLAWPhysicsLoadRelay", [])]}
                     for a in (*ACTOR_IDS, PLAYER_ID)]
    expected_aliases = [{"id": a, "name": f"CLAWPhysicsActor{a:02d}" if a != PLAYER_ID else "CLAWPhysicsPlayerLoad",
                         "flags": 10, "forced": 0 if a != PLAYER_ID else 0x14} for a in (*ACTOR_IDS, PLAYER_ID)]
    if result["masters"] != value["masters"] or result["questForm"] != quest_form or result["editorId"] != EDITOR:
        raise ValueError("Wrong quest identity/masters; no overrides are allowed")
    # DNAM begins with UInt16 flags and UInt8 priority. No StartGameEnabled bit.
    raw_quest = bytes.fromhex(result["questData"])
    if raw_quest != bytes.fromhex("00000aff0000000000000000"):
        raise ValueError("Quest must be stopped by default with priority 10")
    if result["nextAlias"] != 17 or result["aliases"] != expected_aliases:
        raise ValueError("Alias IDs/flags/explicit forced fills differ from the finite wiring contract")
    if result["vmad"] != {"version": 5, "format": 2, "bindVersion": 2, "scripts": [host], "aliases": alias_scripts}:
        raise ValueError("VMAD host array, same-quest alias scripts or false gates differ")
    return result
