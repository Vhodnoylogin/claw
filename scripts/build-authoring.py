"""Build CLAW BodySlide authoring resources with official Outfit Studio automation.

The tool/app copy, config, logs and generated output stay in a NEW staging folder.
Neither the installed BodySlide config nor the live game/mod files are modified.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "scripts"
sys.path.insert(0, str(HERE))
import locate
import presets


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def below(path, parent):
    return path == parent or parent in path.parents


def new_staging(path, sources):
    path = path.resolve()
    if path.exists():
        raise ValueError("Staging must be a NEW directory")
    if any(below(path, source.resolve()) for source in sources):
        raise ValueError("Staging cannot be inside the input/tool directories")
    if {p.lower() for p in path.parts} & {"data", "mods", "overwrite", "downloads"}:
        raise ValueError("Staging cannot use a live game/mod/download directory")
    if below(path, ROOT) and not below(path, ROOT / "work"):
        raise ValueError("Repository output belongs in ignored work/")
    for parent in path.parents:
        if (parent / ".git").exists() and parent != ROOT:
            raise ValueError("Staging cannot be inside another source checkout")
    path.mkdir(parents=True, exist_ok=False)
    return path


def trip_reader(addon):
    spec = importlib.util.spec_from_file_location("_claw_authoring_trip", addon / "tri/tripfile.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.TripFile


def put(root, name, text):
    node = root.find(name)
    if node is None:
        node = ET.SubElement(root, name)
    node.text = str(text)


def automation(path, nif, tri, sex):
    root = ET.Element("AutomationScript", {"version": "1"})
    ET.SubElement(root, "Step", {"type": "ClearProject"})
    step = ET.SubElement(root, "Step", {"type": "ImportFile"})
    put(step, "FilePath", nif)
    step = ET.SubElement(root, "Step", {"type": "ImportSliderData"})
    put(step, "SliderDataFile", tri)
    put(step, "MergeSliders", "false")
    step = ET.SubElement(root, "Step", {"type": "SaveProject"})
    title = sex.title()
    for key, value in {"DisplayName": "CLAW " + title, "SliderSetFile": "CLAW " + title + ".osp",
                       "ShapeDataFolder": "CLAW" + title, "ShapeDataFile": "CLAW" + title + ".nif",
                       "OutputDataPath": "Meshes/Actors/WerewolfBeast/Character Assets",
                       "OutputFileName": sex + "bodywerewolf", "GenWeights": "true",
                       "AutoCopyRef": "true"}.items():
        put(step, key, value)
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool-root", required=True, type=Path, help="BodySlide directory containing OutfitStudio.exe and res/")
    parser.add_argument("--body-root", type=Path, default=ROOT / "assets/release/0.6.2.0/base")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args(argv)
    owned = None
    manifest = {"status": "incomplete", "gameValidated": False, "commands": []}
    try:
        tool, body_root = args.tool_root.resolve(), args.body_root.resolve()
        if not 1 <= args.timeout <= 300:
            raise ValueError("Timeout must be1..300seconds per sex")
        exe = tool / "OutfitStudio.exe"
        if not exe.is_file() or not (tool / "res").is_dir():
            raise ValueError("Official OutfitStudio.exe and res/ are required")
        cfg = locate.local_config(ROOT)
        addon = Path(cfg.get("pynifly", ""))
        if not (addon / "NiflyDLL.dll").is_file():
            raise ValueError("Configure PyNifly in build.local.json")
        TripFile = trip_reader(addon)
        sys.path.insert(0, str(addon))
        from pyn import pynifly
        pynifly.NifFile.Load(str(addon / "NiflyDLL.dll"))
        inputs = {"tool": {"path": str(exe), "sha256": sha(exe)}, "bodies": {}}
        asset = body_root / "Meshes/Actors/WerewolfBeast/Character Assets"
        expected = {}
        for sex in ("male", "female"):
            nif, tri = asset / (sex + "bodywerewolf_0.nif"), asset / (sex + "bodywerewolf.tri")
            if not nif.is_file() or not tri.is_file():
                raise ValueError("Missing source body/TRI for " + sex)
            with tri.open("rb") as stream:
                data = TripFile.from_file(stream).shapes
            expected[sex] = {"shapes": sorted(s.name for s in pynifly.NifFile(str(nif)).shapes),
                             "morphs": sorted({m for shapes in data.values() for m in shapes})}
            if not expected[sex]["shapes"] or set(expected[sex]["morphs"]) != presets.inventory()[sex]:
                raise ValueError("Authoring inputs must contain the complete base CLAW body/morph contract")
            inputs["bodies"][sex] = {"nif": str(nif), "nifSHA256": sha(nif), "tri": str(tri), "triSHA256": sha(tri)}
        owned = new_staging(args.out, [tool, body_root])
        app = owned / "private-tools/BodySlide"
        app.mkdir(parents=True)
        shutil.copy2(exe, app / exe.name)
        for name in ("res", "lang", "RefTemplates"):
            if (tool / name).is_dir():
                shutil.copytree(tool / name, app / name)
        project = owned / "package/CalienteTools/BodySlide"
        (project / "Automations").mkdir(parents=True)
        empty_data = owned / "empty-game-data"
        empty_data.mkdir()
        config = ET.parse(tool / "Config.xml").getroot() if (tool / "Config.xml").is_file() else ET.Element("Config")
        for name, value in {"TargetGame": 4, "ProjectPath": str(project) + "/",
                            "GameDataPath": str(empty_data) + "/", "OutputDataPath": str(owned / "built-data"),
                            "WarnMissingGamePath": "false", "BSATextureScan": "false"}.items():
            put(config, name, value)
        for node in config.findall("GameDataPaths/*"):
            node.text = str(empty_data) + "/"
        ET.ElementTree(config).write(app / "Config.xml", encoding="utf-8", xml_declaration=True)
        manifest.update(inputs=inputs, expected=expected, startedAt=datetime.now(timezone.utc).isoformat())
        for sex, source in inputs["bodies"].items():
            name = "claw-" + sex
            automation(project / "Automations" / (name + ".xml"), source["nif"], source["tri"], sex)
            startup = subprocess.STARTUPINFO() if sys.platform == "win32" else None
            if startup:
                startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startup.wShowWindow = 0
            command = [str(app / "OutfitStudio.exe"), "--automation", name]
            proc = subprocess.run(command, cwd=app, capture_output=True, timeout=args.timeout, startupinfo=startup)
            (owned / (sex + ".stdout.txt")).write_bytes(proc.stdout)
            (owned / (sex + ".stderr.txt")).write_bytes(proc.stderr)
            manifest["commands"].append({"argv": command, "returnCode": proc.returncode})
            if proc.returncode:
                raise ValueError("Official automation failed for " + sex)
            osp = project / "SliderSets" / ("CLAW " + sex.title() + ".osp")
            root = ET.parse(osp).getroot()
            selected = root.find("SliderSet")
            if selected is None or selected.get("name") != "CLAW " + sex.title():
                raise ValueError("Generated project has the wrong typed set")
            shapes = sorted(node.text for node in selected.findall("Shape"))
            morphs = sorted(node.get("name") for node in selected.findall("Slider"))
            if shapes != expected[sex]["shapes"] or morphs != expected[sex]["morphs"]:
                raise ValueError("Official importer dropped or changed shapes/morphs for " + sex)
            copied = project / "ShapeData" / selected.findtext("DataFolder") / selected.findtext("SourceFile")
            original = {s.name: s for s in pynifly.NifFile(source["nif"]).shapes}
            result = pynifly.NifFile(str(copied))
            if any(s.verts != original[s.name].verts or s.tris != original[s.name].tris for s in result.shapes):
                raise ValueError("Authoring reference geometry changed during official export")
            if sha(source["nif"]) != source["nifSHA256"] or sha(source["tri"]) != source["triSHA256"]:
                raise ValueError("Source body/TRI changed while building")
        groups = ET.Element("SliderGroups")
        for sex in ("Male", "Female"):
            group = ET.SubElement(groups, "Group", {"name": "CLAW " + sex})
            ET.SubElement(group, "Member", {"name": "CLAW " + sex})
        (project / "SliderGroups").mkdir(exist_ok=True)
        ET.ElementTree(groups).write(project / "SliderGroups/CLAW.xml", encoding="utf-8", xml_declaration=True)
        # Automations contain local input paths, so remain evidence rather than shipped resources.
        shutil.move(str(project / "Automations"), str(owned / "automation-evidence"))
        manifest["artifacts"] = [{"path": str(p.relative_to(owned / "package")), "sha256": sha(p), "bytes": p.stat().st_size}
                                  for p in sorted((owned / "package").rglob("*")) if p.is_file()]
        manifest["status"] = "authoring-resources-built-game-validation-pending"
        print(str(owned / "package"))
        return 0
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError, subprocess.SubprocessError) as error:
        manifest.update(status="failed", error=str(error))
        print("CLAW authoring: " + str(error), file=sys.stderr)
        return 2
    finally:
        if owned:
            manifest["finishedAt"] = datetime.now(timezone.utc).isoformat()
            (owned / "authoring-build.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
