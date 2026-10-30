"""Package the frozen CLAW payload as one deterministic FOMOD ZIP; never install."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "release/unified-installer"
FROZEN = ROOT / "assets/release/se-core-20261030"
MOD_NAME = "CLAW - Configurable Lycanthrope Anatomy and Weight"
ARCHIVE = MOD_NAME + " - 20261030.zip"
FROZEN_MANIFEST_SHA256 = "d915156d9620770153e26d5bbbe1577da828c69f572daac402e2e93756e20ed9"
MESH = "Meshes/Actors/WerewolfBeast/Character Assets"
BASE_RUNTIME = {"CLAW.esp"} | {MESH+"/"+sex+"bodywerewolf"+suffix
    for sex in ("male", "female") for suffix in ("_0.nif", "_1.nif", ".tri")}
NATIVE_RUNTIME = {"SKSE/Plugins/CLAWDistribution.dll", "Scripts/CLAWDistributionNative.pex"}
HOST_RUNTIME = {"CLAW - OBody Integration.esp", "Scripts/CLAWOBodySourceHost.pex"}
FAMILY_DEST = "SKSE/Plugins/CLAW/MorphLinks.xml"
RUNTIME_SUFFIXES = {".esp", ".pex", ".dll", ".nif", ".tri"}


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def safe_path(value):
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "\\" in value or ":" in value or str(path) != value:
        raise ValueError("Unsafe archive path: " + str(value))
    return value


class Inputs:
    def __init__(self): self.payloads = {}

    def read(self, path):
        path = Path(path)
        if path.is_symlink(): raise ValueError("Symlink input refused: " + str(path))
        path = path.resolve()
        if path not in self.payloads:
            self.payloads[path] = path.read_bytes()
        return self.payloads[path]

    def verify(self):
        for path, payload in self.payloads.items():
            if path.read_bytes() != payload: raise ValueError("Input changed during packaging: " + str(path))


def version(value):
    if not re.fullmatch(r"\d+(?:\.\d+){0,3}", value): raise ValueError("Invalid four-part game version")
    return tuple((list(map(int,value.split(".")))+[0]*4)[:4])


def dependency(element, game_version, active, flags):
    tag = element.tag
    if tag == "gameDependency": return version(game_version) >= version(element.attrib["version"])
    if tag == "fileDependency":
        actual = "Active" if element.attrib["file"] in active else "Missing"
        return element.attrib["state"] == actual
    if tag == "flagDependency": return flags.get(element.attrib["flag"]) == element.attrib["value"]
    if tag in {"dependencies", "visible", "moduleDependencies"}:
        values = [dependency(child,game_version,active,flags) for child in element]
        operator = element.get("operator", "And")
        if operator == "And": return all(values)
        if operator == "Or": return any(values)
    raise ValueError("Unsupported FOMOD dependency: " + tag)


def plugin_type(plugin, game_version, active, flags):
    descriptor = plugin.find("typeDescriptor")
    simple = descriptor.find("type")
    if simple is not None: return simple.attrib["name"]
    dependent = descriptor.find("dependencyType")
    for pattern in dependent.findall("patterns/pattern"):
        if dependency(pattern.find("dependencies"),game_version,active,flags):
            return pattern.find("type").attrib["name"]
    return dependent.find("defaultType").attrib["name"]


def resolve_selection(config, archive_paths, game_version="1.7.104.0", racemenu=True,
                      obody=True, native=False, family=None, host=False):
    """Evaluate the shipped XML's reviewed subset, returning installed destinations.

    Four-component minimum-version and first-matching-pattern semantics match
    the pinned local primary installer implementation. This is offline readback,
    not execution of MO2 or a claim about other installers.
    """
    active = ({"RaceMenu.esp"} if racemenu else set()) | ({"OBody.esp"} if obody else set())
    if family not in (None, "CBBE", "3BA"): raise ValueError("Unknown human resource family")
    if not native and (family is not None or host): raise ValueError("Family/host requires selected native linkage")
    if native and family is None: raise ValueError("Native linkage requires one human family")
    choices = {"10 Native"} if native else set()
    if family: choices.add("20 Human Family/HIMBO-and-"+family)
    if host: choices.add("30 OBody Source")
    folders = list(config.findall("requiredInstallFiles/folder")); flags = {}; selected = set()
    module = config.find("moduleDependencies")
    if module is not None and not dependency(module,game_version,active,flags): raise ValueError("Module dependency refused")
    for step in config.findall("installSteps/installStep"):
        visible = step.find("visible")
        if visible is not None and not dependency(visible,game_version,active,flags): continue
        step_flags = {}
        for group in step.findall("optionalFileGroups/group"):
            picked = []
            for plugin in group.findall("plugins/plugin"):
                files = plugin.find("files")
                if files is None or len(files) != 1 or files[0].tag != "folder":
                    raise ValueError("Every selectable option requires one explicit folder")
                source = files[0].attrib["source"]
                if source not in choices: continue
                if plugin_type(plugin,game_version,active,flags) == "NotUsable":
                    raise ValueError("Unsupported or dependency-blocked option: " + plugin.attrib["name"])
                picked.append(plugin); selected.add(source); folders.extend(files)
                for flag in plugin.findall("conditionFlags/flag"):
                    step_flags[flag.attrib["name"]] = flag.text or ""
            if group.attrib["type"] == "SelectExactlyOne" and len(picked) != 1:
                raise ValueError("Exactly one option must be selected: " + group.attrib["name"])
            if group.attrib["type"] not in {"SelectAny", "SelectExactlyOne"}: raise ValueError("Unreviewed group type")
        flags.update(step_flags)  # Prior-step flags only, matching the primary installer.
    if selected != choices: raise ValueError("Selection was hidden or incomplete")
    installed = {}
    for folder in folders:
        source = safe_path(folder.attrib["source"]).rstrip("/")+"/"
        target = folder.attrib.get("destination", "").rstrip("/")
        matches = [name for name in archive_paths if name.startswith(source)]
        if not matches: raise ValueError("Missing selected archive folder: " + source)
        for name in matches:
            destination = safe_path((target+"/" if target else "")+name[len(source):])
            if destination.casefold() in {path.casefold() for path in installed}:
                raise ValueError("Conflicting installed destination: " + destination)
            installed[destination] = name
    return installed


def checked_frozen(inputs, frozen):
    raw = inputs.read(frozen/"claw-build.json")
    if sha(raw) != FROZEN_MANIFEST_SHA256: raise ValueError("Frozen input manifest differs from reviewed baseline")
    manifest = json.loads(raw)
    if manifest.get("schemaVersion") != 1 or manifest.get("releaseId") != "se-core-20261030":
        raise ValueError("Unexpected frozen release manifest")
    payloads = {}
    for package in manifest["packages"]:
        component = package["component"]
        if component not in {"base", "distribution"} or component in payloads: raise ValueError("Unexpected frozen component")
        expected = {safe_path(row["path"]):row for row in package["files"]}
        if len(expected) != len(package["files"]): raise ValueError("Duplicate frozen file")
        actual = {path.relative_to(frozen/component).as_posix() for path in (frozen/component).rglob("*") if path.is_file()}
        if actual != set(expected): raise ValueError("Frozen component inventory differs: " + component)
        rows = {}
        for name, pin in expected.items():
            payload = inputs.read(frozen/component/name)
            if len(payload) != pin["bytes"] or sha(payload) != pin["sha256"]:
                raise ValueError("Frozen payload hash differs: " + component+"/"+name)
            rows[name] = payload
        payloads[component] = rows
    if set(payloads) != {"base", "distribution"}: raise ValueError("Both frozen components required")
    pin = manifest["correspondingSource"]
    source = inputs.read(frozen/safe_path(pin["path"]))
    if sha(source) != pin["sha256"] or len(source) != pin["bytes"]: raise ValueError("Corresponding source hash differs")
    return manifest, payloads, source


def compose(inputs, frozen, installer=INSTALLER):
    manifest, components, source = checked_frozen(inputs,frozen)
    entries, provenance = {}, {}
    def add(name,payload,origin):
        safe_path(name)
        if name.casefold() in {key.casefold() for key in entries}: raise ValueError("Duplicate archive destination: "+name)
        entries[name] = payload; provenance[name] = origin
    for name,payload in components["base"].items():
        if name in BASE_RUNTIME: target = "00 Base/"+name
        elif name in {"README.md", "README.ru.md"}: target = "Docs/Base/"+name
        else: raise ValueError("Unexpected frozen base file: "+name)
        add(target,payload,"base/"+name)
    for name,payload in components["distribution"].items():
        if name in {"00 Core/README.md", "00 Core/README.ru.md"}: target = "Docs/Distribution/"+name.split("/",1)[1]
        elif name.startswith("00 Core/"): target = "10 Native/"+name[len("00 Core/"):]
        elif name.startswith("10 Human Family/"): target = "20 Human Family/"+name[len("10 Human Family/"):]
        elif name.startswith("20 OBody Source/"): target = "30 OBody Source/"+name[len("20 OBody Source/"):]
        elif name.startswith("fomod/"): target = "Source/Original-Distribution-Installer/"+name[len("fomod/"):]
        else: raise ValueError("Unexpected frozen Distribution file: "+name)
        add(target,payload,"distribution/"+name)
    add("Source/"+PurePosixPath(manifest["correspondingSource"]["path"]).name,source,manifest["correspondingSource"]["path"])
    add("Source/Frozen-Input-Manifest.json",inputs.read(frozen/"claw-build.json"),"claw-build.json")
    for name in ("ModuleConfig.xml", "info.xml"):
        add("fomod/"+name,inputs.read(installer/name),"release/unified-installer/"+name)
    readme = inputs.read(installer/"README.md")
    add("README.md",readme,"release/unified-installer/README.md")
    add("00 Base/README.md",readme,"release/unified-installer/README.md")
    return manifest, entries, provenance


def verify_selections(entries):
    config = ET.fromstring(entries["fomod/ModuleConfig.xml"])
    if config.find("moduleDependencies") is not None: raise ValueError("Optional native dependencies cannot block base installation")
    reports = []
    for family,host in ((None,False),("CBBE",False),("3BA",False),("CBBE",True),("3BA",True)):
        native = family is not None
        installed = resolve_selection(config,entries,native=native,family=family,host=host)
        runtime = {name for name in installed if PurePosixPath(name).suffix.lower() in RUNTIME_SUFFIXES}
        expected = BASE_RUNTIME | (NATIVE_RUNTIME if native else set()) | (HOST_RUNTIME if host else set())
        if runtime != expected: raise ValueError("Selected runtime inventory differs")
        if (FAMILY_DEST in installed) != native: raise ValueError("Human mapping selection differs")
        if native:
            path = installed[FAMILY_DEST]
            if not path.startswith("20 Human Family/HIMBO-and-"+family+"/"): raise ValueError("Wrong selected human mapping")
        if any(source.startswith("Source/") or name.endswith(".zip") for name,source in installed.items()):
            raise ValueError("Archive-only corresponding source selected for installation")
        reports.append({"selection":"base-only" if family is None else family+("+OBody" if host else ""),
                        "runtimeFiles":sorted(runtime), "runtimeFileCount":len(runtime),
                        "installedFiles":[{"path":name,"archivePath":source,"sha256":sha(entries[source]),"bytes":len(entries[source])}
                                          for name,source in sorted(installed.items())]})
    for game in ("1.4.15.0","1.5.97.0","1.6.1170.0","1.7.103.0","1.7.104.1","1.7.105.0","2.0.0.0"):
        installed = resolve_selection(config,entries,game_version=game)
        if set(name for name in installed if PurePosixPath(name).suffix.lower() in RUNTIME_SUFFIXES) != BASE_RUNTIME:
            raise ValueError("Unsupported runtime installed native files")
        try: resolve_selection(config,entries,game_version=game,native=True,family="CBBE")
        except ValueError: pass
        else: raise ValueError("Unsupported runtime accepted native selection: "+game)
    for kwargs in ({"racemenu":False,"native":True,"family":"CBBE"},
                   {"obody":False,"native":True,"family":"3BA","host":True}):
        try: resolve_selection(config,entries,**kwargs)
        except ValueError: pass
        else: raise ValueError("Missing native/host dependency was accepted")
    # No inactive/unselected host scripts can leak into the no-host outcomes.
    return reports


def output_directory(path):
    path = Path(path).resolve()
    if path.exists(): raise ValueError("Fresh external output directory required")
    if path == ROOT or ROOT in path.parents: raise ValueError("Output cannot be inside the checkout")
    if {part.lower() for part in path.parts} & {"data", "mods", "overwrite", "downloads"}:
        raise ValueError("Live game/mod/archive destinations are refused")
    if any((parent/".git").exists() for parent in path.parents): raise ValueError("Output cannot be inside another checkout")
    return path


def build(out, schema, installer_source, frozen=FROZEN):
    out = output_directory(out); inputs = Inputs()
    contract = json.loads(inputs.read(INSTALLER/"installer-contract.json"))
    for reference,path in zip(contract["primaryReferences"],(schema,installer_source),strict=True):
        if sha(inputs.read(path)) != reference["sha256"]: raise ValueError("Unreviewed FOMOD primary contract: "+reference["file"])
    script = inputs.read(Path(__file__))
    frozen_manifest,entries,provenance = compose(inputs,Path(frozen))
    selections = verify_selections(entries)
    files = [{"path":name,"bytes":len(payload),"sha256":sha(payload),"origin":provenance[name]}
             for name,payload in sorted(entries.items())]
    manifest = {"schemaVersion":1,"releaseId":"claw-20261030","modName":MOD_NAME,"archive":ARCHIVE,
                "kind":"Unified installer of exact frozen payloads; no runtime rebuild",
                "nativeRuntime":"Skyrim1.7.104.0 only; SKSE2.3.1, Address Library13, matching official RaceMenu required",
                "otherRuntimes":"Base resources only; no AE/VR native binary supplied or newly qualified",
                "frozenManifestSha256":sha(inputs.read(Path(frozen)/"claw-build.json")),
                "nativeSourceCommit":frozen_manifest["nativeSourceCommit"],
                "packagerSha256":sha(script),"installerContract":contract,
                "sourceArchiveInstalled":False,"runtimePayloadsModified":False,
                "files":files,"manifestSelfExcluded":True,"selections":selections}
    entries["claw-unified-release.json"] = (json.dumps(manifest,indent=2,sort_keys=True)+"\n").encode()
    inputs.verify()
    # Recheck inventory additions/removals as well as all captured file bytes.
    checked_frozen(inputs,Path(frozen))
    out.mkdir(parents=True,exist_ok=False)
    marker = out/"FAILED-do-not-publish"; marker.write_text("Packaging verification incomplete.\n")
    archive = out/ARCHIVE
    with zipfile.ZipFile(archive,"x",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as writer:
        for name,payload in sorted(entries.items()):
            info = zipfile.ZipInfo(name,(2026,10,30,0,0,0)); info.create_system = 3
            info.external_attr = 0o100644 << 16; info.compress_type = zipfile.ZIP_DEFLATED
            writer.writestr(info,payload,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    with zipfile.ZipFile(archive) as reader:
        if reader.testzip() or reader.namelist() != sorted(entries): raise ValueError("ZIP inventory/CRC failure")
        actual = {name:reader.read(name) for name in reader.namelist()}
        if actual != entries: raise ValueError("ZIP bytes differ from verified composition")
        verify_selections(actual)
    inputs.verify(); checked_frozen(inputs,Path(frozen))
    receipt = {"archive":str(archive),"sha256":sha(archive.read_bytes()),"bytes":archive.stat().st_size,
               "archiveFiles":len(entries),"validSelections":len(selections),"runtimePayloadsModified":False,
               "sourceArchiveInstalled":False,"gameOrManagerExecuted":False,
               "selections":[{"selection":row["selection"],"runtimeFileCount":row["runtimeFileCount"]} for row in selections]}
    # Explicit offline installation maps for consumers that need to stage one
    # chosen outcome. These receipts never install or activate the payload.
    for selection in selections:
        filename = "selection-"+selection["selection"].replace("+","-")+".json"
        mapping = {"schemaVersion":1,"modName":MOD_NAME,"archive":ARCHIVE,
                   "archiveSha256":receipt["sha256"],"gameVersion":"1.7.104.0" if selection["selection"] != "base-only" else None,
                   "installed":False,"dependencyChainVerified":False,**selection}
        (out/filename).write_text(json.dumps(mapping,indent=2)+"\n",encoding="utf-8")
    (out/"build-receipt.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
    marker.unlink()
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--schema",type=Path,required=True,help="reviewed local GenericModConfig5.0.xsd")
    parser.add_argument("--installer-source",type=Path,required=True,help="reviewed local primary fomodinstallerdialog.cpp")
    args = parser.parse_args(argv)
    try: result = build(args.out,args.schema,args.installer_source)
    except (OSError,ValueError,KeyError,TypeError,ET.ParseError,zipfile.BadZipFile) as error:
        parser.exit(2,"Unified CLAW release rejected: "+str(error)+"\n")
    print(json.dumps(result,indent=2))


if __name__ == "__main__": main()
