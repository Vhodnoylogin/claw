"""Compare official BodySlide batch output against source NIF plus TRI deltas.

Explicit offline integration check; copies tools/projects into new staging and
never writes installed bodies, presets, configuration or game files.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import locate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authoring", required=True, type=Path, help="staged CalienteTools/BodySlide directory")
    parser.add_argument("--tool-root", required=True, type=Path)
    parser.add_argument("--body-root", type=Path, default=ROOT / 'target/references/releases/0.6.2.0/base')
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("claw_authoring_build", HERE / "build-authoring.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    out = builder.new_staging(args.out, [args.authoring, args.tool_root, args.body_root])
    report = {"status": "running", "scope": "offline-official-bodyslide-output", "cases": []}
    try:
        addon = Path(locate.local_config(ROOT)["pynifly"])
        TripFile = builder.trip_reader(addon)
        sys.path.insert(0, str(addon))
        from pyn import pynifly
        pynifly.NifFile.Load(str(addon / "NiflyDLL.dll"))
        app = out / "private-tools/BodySlide"
        app.mkdir(parents=True)
        shutil.copy2(args.tool_root / "BodySlide.exe", app / "BodySlide.exe")
        shutil.copytree(args.tool_root / "res", app / "res")
        project = out / "authoring"
        shutil.copytree(args.authoring, project)
        (project / "SliderPresets/CLAW").mkdir(parents=True, exist_ok=True)
        empty = out / "empty-game-data"
        empty.mkdir()
        config = ET.Element("Config")
        for name, value in {"TargetGame": 4, "ProjectPath": str(project) + "/", "GameDataPath": str(empty) + "/",
                            "WarnMissingGamePath": "false", "BSATextureScan": "false", "LogLevel": 3}.items():
            builder.put(config, name, value)
        ET.ElementTree(config).write(app / "Config.xml", encoding="utf-8", xml_declaration=True)
        cases = {"zero": {}, "ear-one": {"CLAWHeadEarSize": 1.0},
                 "mixed": {"CLAWHeadEarSize": .25, "CLAWTailLength": .30, "CLAWHeadMuzzleLong": .10}}
        asset = args.body_root / "Meshes/Actors/WerewolfBeast/Character Assets"
        for sex in ("male", "female"):
            source = asset / (sex + "bodywerewolf_0.nif")
            tri = asset / (sex + "bodywerewolf.tri")
            original = {shape.name: shape for shape in pynifly.NifFile(str(source)).shapes}
            with tri.open("rb") as stream:
                offsets = TripFile.from_file(stream).shapes
            for case, values in cases.items():
                name = "CLAW verification " + sex + " " + case
                xml = ET.Element("SliderPresets")
                preset = ET.SubElement(xml, "Preset", {"name": name, "set": "CLAW " + sex.title()})
                ET.SubElement(preset, "Group", {"name": "CLAW " + sex.title()})
                for morph, value in values.items():
                    for size in ("small", "big"):
                        ET.SubElement(preset, "SetSlider", {"name": morph, "size": size, "value": str(value * 100)})
                ET.ElementTree(xml).write(project / "SliderPresets/CLAW/verification.xml", encoding="utf-8", xml_declaration=True)
                target = out / "built" / (sex + "-" + case)
                target.mkdir(parents=True)
                command = [str(app / "BodySlide.exe"), "--groupbuild", "CLAW " + sex.title(),
                           "--targetdir", str(target), "--preset", name]
                startup = subprocess.STARTUPINFO() if sys.platform == "win32" else None
                if startup:
                    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startup.wShowWindow = 0
                process = subprocess.run(command, cwd=app, capture_output=True, timeout=120, startupinfo=startup)
                record = {"sex": sex, "case": case, "argv": command, "returnCode": process.returncode,
                          "sourceNIFSHA256": builder.sha(source), "sourceTRISHA256": builder.sha(tri), "endpoints": []}
                report["cases"].append(record)
                (out / (sex + "-" + case + ".stdout.txt")).write_bytes(process.stdout)
                (out / (sex + "-" + case + ".stderr.txt")).write_bytes(process.stderr)
                if process.returncode:
                    raise ValueError("Official batch build failed")
                for weight in (0, 1):
                    built = target / "Meshes/Actors/WerewolfBeast/Character Assets" / (sex + f"bodywerewolf_{weight}.nif")
                    loaded = pynifly.NifFile(str(built))
                    if set(original) != {shape.name for shape in loaded.shapes}:
                        raise ValueError("BodySlide changed shape inventory")
                    worst = 0.0
                    for shape in loaded.shapes:
                        reference = original[shape.name]
                        expected = np.asarray(reference.verts, dtype=np.float64)
                        for morph, value in values.items():
                            for index, delta in offsets.get(shape.name, {}).get(morph, []):
                                expected[index] += np.asarray(delta) * value
                        actual = np.asarray(shape.verts)
                        if expected.shape != actual.shape or shape.tris != reference.tris or shape.uvs != reference.uvs:
                            raise ValueError("BodySlide changed vertex indexing/topology/UV")
                        worst = max(worst, float(np.max(np.abs(expected - actual))))
                    record["endpoints"].append({"weightFile": weight, "path": str(built.relative_to(out)),
                                                 "sha256": builder.sha(built), "maxCoordinateError": worst})
                    if worst > .0001:
                        raise ValueError("BodySlide output differs from NIF + TRI definition")
        report["status"] = "passed"
        print("Passed6official BodySlide builds /12endpoints against independent NIF+TRI expectations")
        return 0
    except (OSError, ValueError, KeyError, ET.ParseError, subprocess.SubprocessError) as error:
        report.update(status="failed", error=str(error))
        print("CLAW authoring check: " + str(error), file=sys.stderr)
        return 2
    finally:
        (out / "authoring-check.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
