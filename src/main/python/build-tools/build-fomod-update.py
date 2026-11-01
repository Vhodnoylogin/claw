"""Update only the installer XML in a pinned, runtime-only CLAW 0.7 archive."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

ACCEPTED_INPUTS = {
    "dec2a2a9abca26c6d597e21f415875b175d82675eb9a6c67949e1d649080feec",
    "ebb0967fcf428fdcbcc801f0d51065edde721698f69aaf5bf0ad928af89df215",
}
ARCHIVE_NAME = "CLAW - Configurable Lycanthrope Anatomy and Weight.zip"
VERSION = "0.7.1"
XML_MEMBERS = {"fomod/ModuleConfig.xml", "fomod/info.xml"}
FOLDERS = {family: "20 Human Family/HIMBO-and-"+family for family in ("CBBE", "3BA")}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def choice(parent, name, sex, family, description):
    plugin = ET.SubElement(parent, "plugin", name=name)
    ET.SubElement(plugin, "description").text = description
    ET.SubElement(ET.SubElement(plugin, "conditionFlags"), "flag", name=sex+"Family").text = family
    return plugin

def body_step(name, group_name):
    step = ET.Element("installStep", name=name)
    groups = ET.SubElement(step, "optionalFileGroups", order="Explicit")
    group = ET.SubElement(groups, "group", name=group_name, type="SelectExactlyOne")
    return step, ET.SubElement(group, "plugins", order="Explicit")

def update_config(data):
    config = ET.fromstring(data)
    steps = config.find("installSteps")
    matches = [step for step in steps if {row.get("source") for row in step.findall(".//files/folder")} == set(FOLDERS.values())]
    if len(matches) != 1 or config.find("conditionalFileInstalls") is not None:
        raise ValueError("Expected the published 0.7 combined body step")
    old = matches[0]; index = list(steps).index(old)
    dependencies = config.find("moduleDependencies")
    if dependencies is not None:
        for row in list(dependencies):
            if row.tag == "fileDependency" and row.get("file") in {"HIMBO.esp", "CBBE.esp"}:
                dependencies.remove(row)
    male, plugins = body_step("Male body", "Male human body")
    option = choice(plugins, "HIMBO", "male", "HIMBO",
                    "This version uses HIMBO for male human inputs. Install HIMBO separately; no human body meshes are included.")
    ET.SubElement(ET.SubElement(option, "typeDescriptor"), "type", name="Required")
    female, plugins = body_step("Female body", "Female human body")
    for family, label in (("CBBE", "CBBE"), ("3BA", "CBBE + 3BA")):
        option = choice(plugins, label, "female", family,
            "Choose the female body whose meshes actually win in your mod manager. Plugin markers only recommend a choice; they cannot determine the winner when several bodies are installed. Both choices remain available. Bodies and physics are not bundled.")
        descriptor = ET.SubElement(ET.SubElement(option, "typeDescriptor"), "dependencyType")
        ET.SubElement(descriptor, "defaultType", name="Recommended" if family == "CBBE" else "Optional")
        pattern = ET.SubElement(ET.SubElement(descriptor, "patterns"), "pattern")
        required = ET.SubElement(pattern, "dependencies", operator="And")
        ET.SubElement(required, "fileDependency", file="3BBB.esp", state="Active")
        ET.SubElement(pattern, "type", name="Optional" if family == "CBBE" else "Recommended")
    steps.remove(old); steps.insert(index, male); steps.insert(index+1, female)
    patterns = ET.SubElement(ET.SubElement(config, "conditionalFileInstalls"), "patterns")
    for family, source in FOLDERS.items():
        pattern = ET.SubElement(patterns, "pattern")
        required = ET.SubElement(pattern, "dependencies", operator="And")
        ET.SubElement(required, "flagDependency", flag="maleFamily", value="HIMBO")
        ET.SubElement(required, "flagDependency", flag="femaleFamily", value=family)
        ET.SubElement(ET.SubElement(pattern, "files"), "folder", source=source, destination="", priority="0")
    ET.indent(config)
    # Vortex converts to UTF-16 but fails to remove ElementTree's single-quoted encoding declaration.
    return ET.tostring(config, encoding="utf-8", xml_declaration=False)

def selection(config, entries, family, host):
    """Audit only this pinned release's explicit base/native/family/host layout."""
    installed = {}
    for row in config.findall("requiredInstallFiles/file"):
        installed[row.attrib["destination"]] = row.attrib["source"]
    conditional = config.find("conditionalFileInstalls")
    if conditional is None:
        sources = [row.get("source") for row in config.findall("installSteps/installStep/optionalFileGroups/group/plugins/plugin/files/folder")
                   if row.get("source") == FOLDERS[family]]
    else:
        flags = {"maleFamily": "HIMBO", "femaleFamily": family}
        sources = [pattern.find("files/folder").get("source") for pattern in conditional.findall("patterns/pattern")
                   if all(flags.get(row.get("flag")) == row.get("value") for row in pattern.findall("dependencies/flagDependency"))]
    if sources != [FOLDERS[family]]:
        raise ValueError("Body flags do not select exactly the original resource folder")
    for source in ["10 Native", *sources, *(["30 OBody Source"] if host else [])]:
        for name in entries:
            if name.startswith(source+"/"):
                destination = name[len(source)+1:]
                if destination in installed: raise ValueError("Conflicting installed paths")
                installed[destination] = name
    if len(installed) != (12 if host else 10) or any(source not in entries for source in installed.values()):
        raise ValueError("Published runtime inventory differs")
    return {destination: sha(entries[source]) for destination, source in sorted(installed.items())}

def build(archive, out):
    archive, out = Path(archive), Path(out)
    raw = archive.read_bytes()
    if sha(raw) not in ACCEPTED_INPUTS: raise ValueError("Expected an exact approved runtime-only 0.7 archive")
    if out.exists(): raise ValueError("Choose a new output directory; original artifacts are never overwritten")
    with zipfile.ZipFile(archive) as source:
        infos = source.infolist()
        if source.testzip() or len({row.filename.casefold() for row in infos}) != len(infos):
            raise ValueError("Corrupt or case-colliding input archive")
        before = {row.filename: source.read(row.filename) for row in infos}
    after = dict(before); after["fomod/ModuleConfig.xml"] = update_config(before["fomod/ModuleConfig.xml"])
    info = ET.fromstring(before["fomod/info.xml"]); version = info.find("Version")
    if version is None: raise ValueError("Missing published version")
    version.text = VERSION
    if "MachineVersion" in version.attrib: version.set("MachineVersion", VERSION)
    after["fomod/info.xml"] = ET.tostring(info, encoding="utf-8", xml_declaration=False)
    old_config, config = (ET.fromstring(entries["fomod/ModuleConfig.xml"]) for entries in (before, after))
    rows = []
    for family in FOLDERS:
        for host in (False, True):
            selected = selection(config, after, family, host)
            if selected != selection(old_config, before, family, host): raise ValueError("Runtime payload changed")
            rows.append({"maleFamily": "HIMBO", "femaleFamily": family, "obody": host, "files": selected})
    if {name for name in before if before[name] != after[name]} != XML_MEMBERS:
        raise ValueError("Only the two installer XML members may change")
    out.mkdir(parents=True); target = out/ARCHIVE_NAME
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as result:
        for item in infos: result.writestr(item, after[item.filename], compress_type=item.compress_type, compresslevel=9)
    with zipfile.ZipFile(target) as result:
        if result.testzip() or {name: result.read(name) for name in result.namelist()} != after:
            raise ValueError("Literal archive readback differs")
    report = {"schema": "claw-071-installer-only-update/1", "version": VERSION,
        "source": {"path": str(archive), "sha256": sha(raw), "bytes": len(raw)},
        "archive": {"path": str(target), "sha256": sha(target.read_bytes()), "bytes": target.stat().st_size},
        "changedMembers": sorted(XML_MEMBERS), "allOtherMemberContentsByteIdentical": True,
        "separateBodyPages": ["Male body", "Female body"], "selections": rows,
        "members": {name: {"oldSha256": sha(before[name]), "newSha256": sha(after[name]), "changed": before[name] != after[name]} for name in before},
        "runtimeRebuilt": False, "installedOrPublished": False}
    (out/"build-receipt.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True); parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build(args.archive, args.out)
        print(json.dumps({key: result[key] for key in ("archive", "changedMembers", "separateBodyPages")}, indent=2))
    except (OSError, ValueError, KeyError, ET.ParseError, zipfile.BadZipFile) as error:
        parser.exit(2, "CLAW FOMOD update: "+str(error)+"\n")
if __name__ == "__main__": main()
