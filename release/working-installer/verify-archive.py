"""Compare literal ZIP-contained FOMOD outputs with a known-complete ZIP.

No release manifest, generated destination or packager resolver is consulted.
The rejected-v2 regression is invoked with --expect-rejection.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import xml.etree.ElementTree as ET
import zipfile


def read_zip(path):
    with zipfile.ZipFile(path) as reader:
        names = reader.namelist()
        if reader.testzip() or len(names) != len(set(n.casefold() for n in names)):
            raise ValueError("Invalid ZIP")
        return {n: reader.read(n) for n in names}


def safe(name):
    p = PurePosixPath(name)
    if not name or p.is_absolute() or ".." in p.parts or "\\" in name or ":" in name:
        raise ValueError("Unsafe archive path")
    return name


def installation(entries, family, host):
    config = ET.fromstring(entries["fomod/ModuleConfig.xml"])
    active = {"RaceMenu.esp", "HIMBO.esp", "CBBE.esp", "3BBB.esp", "OBody.esp"}
    flags = {}

    def condition(node):
        if node.tag == "fileDependency":
            return node.get("state") == ("Active" if node.get("file") in active else "Missing")
        if node.tag == "flagDependency":
            return flags.get(node.get("flag")) == node.get("value")
        if node.tag == "gameDependency":
            wanted = tuple(map(int, node.get("version").split(".")))
            return (1, 7, 104, 0) >= wanted
        if node.tag in ("dependencies", "visible", "moduleDependencies"):
            values = [condition(child) for child in node]
            if node.get("operator", "And") == "And": return all(values)
            if node.get("operator") == "Or": return any(values)
        raise ValueError("Unreviewed dependency " + node.tag)

    module = config.find("moduleDependencies")
    if module is not None and not condition(module): raise ValueError("Module refused")
    chosen_sources = {"10 Native", "20 Human Family/HIMBO-and-" + family}
    if host: chosen_sources.add("30 OBody Source")
    copies = list(config.find("requiredInstallFiles"))
    for step in config.findall("installSteps/installStep"):
        visible = step.find("visible")
        if visible is not None and not condition(visible): continue
        new_flags = {}
        for group in step.findall("optionalFileGroups/group"):
            picked = []
            for plugin in group.findall("plugins/plugin"):
                files = plugin.find("files")
                if files is None or len(files) != 1: raise ValueError("Unknown selectable shape")
                selected = files[0].get("source") in chosen_sources
                descriptor = plugin.find("typeDescriptor")
                direct = descriptor.find("type")
                if direct is not None:
                    typ = direct.get("name")
                else:
                    dependent = descriptor.find("dependencyType")
                    typ = dependent.find("defaultType").get("name")
                    for pattern in dependent.findall("patterns/pattern"):
                        if condition(pattern.find("dependencies")):
                            typ = pattern.find("type").get("name")
                            break
                if typ == "Required" and not selected: raise ValueError("Required option skipped")
                if not selected: continue
                if typ == "NotUsable": raise ValueError("Selected option unavailable")
                picked.append(plugin)
                copies.extend(files)
                for flag in plugin.findall("conditionFlags/flag"):
                    new_flags[flag.get("name")] = flag.text
            if group.get("type") == "SelectExactlyOne" and len(picked) != 1:
                raise ValueError("Exactly-one option mismatch")
        flags.update(new_flags)
    installed = {}
    for item in copies:
        source = safe(item.get("source"))
        destination = item.get("destination", "")
        if item.tag == "file":
            mappings = [(safe(destination), source)]
        elif item.tag == "folder":
            prefix = source.rstrip("/") + "/"
            mappings = [(safe((destination.rstrip("/") + "/" if destination else "") + n[len(prefix):]), n)
                        for n in entries if n.startswith(prefix)]
            if not mappings: raise ValueError("Missing folder source")
        else:
            raise ValueError("Unknown actual XML copy directive")
        for target, origin in mappings:
            if origin not in entries or target.casefold() in {n.casefold() for n in installed}:
                raise ValueError("Missing file source or duplicate destination")
            installed[target] = origin
    return installed


def verify(archive, baseline):
    entries, old = read_zip(archive), read_zip(baseline)
    config = ET.fromstring(entries["fomod/ModuleConfig.xml"])
    branches = {}
    for family, host in (("CBBE", False), ("CBBE", True), ("3BA", False), ("3BA", True)):
        actual, expected = installation(entries, family, host), installation(old, family, host)
        missing, extra = sorted(set(expected) - set(actual)), sorted(set(actual) - set(expected))
        changed = [n for n in set(expected) & set(actual) if entries[actual[n]] != old[expected[n]]]
        branches[family + ("-OBody" if host else "")] = {
            "passed": not (missing or extra or changed), "actualCount": len(actual),
            "baselineCount": len(expected), "missing": missing, "extra": extra, "changed": changed,
            "actualMappings": actual}
    return {"archive": str(archive), "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "baseline": str(baseline), "passed": all(v["passed"] for v in branches.values()),
            "literalFileTags": len(config.findall(".//file")),
            "requiredInstallEntries": [dict(row.attrib, kind=row.tag) for row in config.find("requiredInstallFiles")],
            "branches": branches, "method": "Literal ZIP-extracted XML only; no manifest or synthetic destinations"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--expect-rejection", action="store_true")
    args = parser.parse_args()
    report = verify(args.archive, args.baseline)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "literalFileTags": report["literalFileTags"],
                      "expectedRejection": args.expect_rejection}))
    raise SystemExit(0 if report["passed"] != args.expect_rejection else 1)
