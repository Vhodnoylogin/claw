"""Assemble a hash-verified development companion in NEW external staging.

This packages already built candidates; it never installs, starts the game or
promotes a candidate to release. Native/data receipts must match current sources.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import presets

NATIVE_SOURCES = {"distribution/CMakeLists.txt", "distribution/dependencies.json",
                  "distribution/src/Plugin.cpp", "distribution/src/Preset.cpp",
                  "distribution/src/Tool.cpp", "distribution/tests/CoreTests.cpp",
                  "distribution/include/claw/Preset.h", "distribution/include/claw/RequestOwnership.h"}


def builder_module():
    spec = importlib.util.spec_from_file_location("claw_distribution_package", ROOT / "scripts/build-authoring.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def same_file(path, digest, size, sha):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing or linked input: " + str(path))
    if path.stat().st_size != size or sha(path).lower() != digest.lower():
        raise ValueError("Receipt does not match bytes: " + str(path))


def current_source(path, digest, sha):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT) or sha(path).lower() != digest.lower():
        raise ValueError("Receipt does not match current source: " + str(path))


def artifact_tree(package, records, expected, sha):
    actual = {p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()}
    declared = {Path(r["path"]).as_posix() for r in records}
    if actual != expected or declared != expected or len(records) != len(expected):
        raise ValueError("Unexpected or missing compiled data files")
    for record in records:
        same_file(package / record["path"], record["sha256"], record["bytes"], sha)


def native_receipts(folder, combined=None):
    """Normalize historical review receipts or one source/artifact build freeze."""
    if combined is not None:
        document = json.loads(combined.read_text(encoding="utf-8-sig"))
        checks = document.get("tests", {})
        exits_ok = all(type(checks.get(key)) is int and checks[key] == 0
                       for key in ("ctestExitCode", "cliExitCode"))
        ran_tests = all(type(checks.get(key)) is int and checks[key] > 0
                        for key in ("registeredCTestTests", "contractCases", "validExamplePresets"))
        if (document.get("status") != "compiled-offline-verified-development-candidate-awaiting-root-review"
                or not exits_ok or not ran_tests
                or checks.get("engineABIMockedOrExecuted") is not False):
            raise ValueError("Expected a compiled, offline-verified native development freeze")
        sources = [{"Path": row["path"], "SHA256": row["sha256"], "Bytes": row["bytes"]}
                   for row in document["sourceFiles"]]
        artifacts = [{"Path": row["path"], "SHA256": row["sha256"], "Bytes": row["bytes"]}
                     for row in document["artifacts"]]
        return sources, artifacts, combined, combined
    source = folder / "source-manifest-review.json"
    artifact = folder / "artifacts-review.json"
    return (json.loads(source.read_text(encoding="utf-8-sig")),
            json.loads(artifact.read_text(encoding="utf-8-sig")), source, artifact)


def native_sources(sources, sha):
    present = set()
    for item in sources:
        current_source(item["Path"], item["SHA256"], sha)
        present.add(Path(item["Path"]).resolve().relative_to(ROOT).as_posix())
    if not NATIVE_SOURCES.issubset(present):
        raise ValueError("Native source receipt is incomplete")


def native_binaries(folder, records, sha):
    verified = {}
    for name in ("CLAWDistribution.dll", "claw-preset-tool.exe", "claw-preset-tests.exe"):
        matches = [row for row in records if Path(row["Path"]).name == name]
        if len(matches) != 1:
            raise ValueError("Need exactly one compiled native artifact receipt: " + name)
        record = matches[0]
        path = Path(record["Path"]).resolve()
        if not path.is_relative_to(folder):
            raise ValueError("Native artifact must belong to the specified build: " + name)
        same_file(path, record["SHA256"], record["Bytes"], sha)
        verified[name] = (record, path)
    return verified


def archive(folder, target):
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED) as output:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                output.write(path, path.relative_to(folder).as_posix())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-build", type=Path, required=True,
                        help="Contains artifacts-review.json and source-manifest-review.json")
    parser.add_argument("--native-receipt", type=Path,
                        help="Optional unified native build freeze with sourceFiles/artifacts/tests")
    parser.add_argument("--data-build", type=Path, required=True,
                        help="Contains distribution-data-build.json and package/")
    parser.add_argument("--presets", type=Path, required=True, help="CLAW preset XML subtree")
    parser.add_argument("--license", action="append", default=[], metavar="NAME=FILE",
                        help="Required names: commonlib, pugixml, fmt, spdlog, rapidcsv")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    helper = builder_module()
    owned = None
    report = {"status": "incomplete", "gameValidated": False, "runtime": "Skyrim VR 1.4.15"}
    try:
        native, data, preset_root = args.native_build.resolve(), args.data_build.resolve(), args.presets.resolve()
        combined = args.native_receipt.resolve() if args.native_receipt else None
        if combined is not None and not combined.is_relative_to(native):
            raise ValueError("Native build freeze must belong to the specified build")
        sources, native_artifacts, source_receipt, artifact_receipt = native_receipts(native, combined)
        native_sources(sources, helper.sha)
        verified_binaries = native_binaries(native, native_artifacts, helper.sha)
        dll, dll_path = verified_binaries["CLAWDistribution.dll"]
        data_report = data / "distribution-data-build.json"
        compiled = json.loads(data_report.read_text(encoding="utf-8"))
        if compiled["status"] != "built-game-validation-pending" or compiled["gameValidated"] is not False:
            raise ValueError("Expected an explicitly unaccepted development data build")
        if {Path(p).as_posix() for p in compiled["inputs"]["sourceSha256"]} != {
                "distribution/papyrus/CLAWDistributionNative.psc", "integration/papyrus/CLAWDistributionMenu.psc"}:
            raise ValueError("Compiled script source receipt is incomplete")
        for path, digest in compiled["inputs"]["sourceSha256"].items():
            current_source(ROOT / path, digest, helper.sha)
        quest = ROOT / "plugins/CLAW - Distribution"
        quest_sources = compiled["inputs"]["questSourceSha256"]
        if {p.relative_to(quest).as_posix() for p in quest.rglob("*") if p.is_file()} != {
                Path(p).as_posix() for p in quest_sources}:
            raise ValueError("Quest source inventory changed since build")
        for path, digest in quest_sources.items():
            current_source(quest / path, digest, helper.sha)
        expected = {"CLAW - Distribution.esp", "Scripts/CLAWDistributionMenu.pex", "Scripts/CLAWDistributionNative.pex"}
        artifact_tree(data / "package", compiled["artifacts"], expected, helper.sha)
        if preset_root.is_symlink() or not preset_root.is_dir():
            raise ValueError("Need a real preset subtree")
        xmls = sorted(preset_root.rglob("*.xml"))
        if not xmls or any(p.is_symlink() for p in preset_root.rglob("*")):
            raise ValueError("Preset subtree is empty or contains links")
        catalog = presets.load_tree(preset_root)
        licenses = {}
        for value in args.license:
            name, separator, path = value.partition("=")
            if not separator or name in licenses:
                raise ValueError("Invalid/duplicate license argument")
            licenses[name] = Path(path).resolve()
        if set(licenses) != {"commonlib", "pugixml", "fmt", "spdlog", "rapidcsv"}:
            raise ValueError("Supply all five dependency license texts")
        for path in licenses.values():
            if not path.is_file() or path.stat().st_size < 100:
                raise ValueError("Missing license text: " + str(path))
        owned = helper.new_staging(args.out, [native, data, preset_root, *licenses.values()])
        package, examples = owned / "companion", owned / "example-presets"
        shutil.copytree(data / "package", package)
        target_dll = package / "SKSE/Plugins/CLAWDistribution.dll"
        target_dll.parent.mkdir(parents=True)
        shutil.copy2(dll_path, target_dll)
        docs = package / "Docs/CLAWDistribution"
        notices = docs / "ThirdParty"
        notices.mkdir(parents=True)
        for name, path in licenses.items():
            shutil.copy2(path, notices / (name + ".txt"))
        for name, source in {"README.md": ROOT / "distribution/README.md", "Preset-authoring.md": ROOT / "docs/presets.md",
                             "Build-dependencies.json": ROOT / "distribution/dependencies.json"}.items():
            shutil.copy2(source, docs / name)
        shutil.copy2(ROOT / "distribution/papyrus/CLAWDistributionNative.psc", docs / "CLAWDistributionNative.psc")
        (package / "CLAW Distribution - DEVELOPMENT.txt").write_text(
            "Development candidate; not runtime accepted. Skyrim VR 1.4.15 only.\n"
            "Requires CLAW 0.6.2.0, its dependencies, SKSEVR, RaceMenu VR and UIExtensions.\n"
            "Keep neutral CLAW body meshes. Install at least one typed preset mod separately.\n"
            "F8 opens werewolf presets for the crosshair target, or the player.\n"
            "OBody remains responsible for human presets; no OBody fork is required.\n"
            "Use respectful morph application with OBody 4.4.3.\n"
            "No geometry repair, physics, test actors or external executables are included.\n",
            encoding="utf-8", newline="\n")
        for path in xmls:
            destination = examples / "CalienteTools/BodySlide/SliderPresets/CLAW" / path.relative_to(preset_root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
            if helper.sha(path) != helper.sha(destination):
                raise ValueError("Preset input changed while packaging")
        (examples / "CLAW Example Presets - DEVELOPMENT.txt").write_text(
            "Independent typed BodySlide presets for the CLAW Distribution development candidate.\n"
            "Ears and tail examples; no claim of game-qualified appearance or physics.\n"
            "Do not move the XML into OBody's top-level preset pool.\n", encoding="utf-8", newline="\n")
        report["inputs"] = {"nativeSourceReceipt": {"path": str(source_receipt), "sha256": helper.sha(source_receipt)},
                            "nativeArtifactReceipt": {"path": str(artifact_receipt), "sha256": helper.sha(artifact_receipt)},
                            "dataReceipt": {"path": str(data_report), "sha256": helper.sha(data_report)},
                            "licenses": {name: {"path": str(p), "sha256": helper.sha(p)} for name, p in licenses.items()}}
        same_file(target_dll, dll["SHA256"], dll["Bytes"], helper.sha)
        for record in compiled["artifacts"]:
            same_file(package / record["path"], record["sha256"], record["bytes"], helper.sha)
        report["presetCount"] = len(catalog["presets"])
        report["presetInputs"] = catalog["inputs"]
        report["files"] = [{"path": str(p.relative_to(owned)), "sha256": helper.sha(p), "bytes": p.stat().st_size}
                           for folder in (package, examples) for p in sorted(folder.rglob("*")) if p.is_file()]
        for folder, name in ((package, "CLAW Distribution - development.zip"),
                             (examples, "CLAW Example Presets - development.zip")):
            archive(folder, owned / name)
        report["archives"] = [{"path": p.name, "sha256": helper.sha(p), "bytes": p.stat().st_size}
                              for p in sorted(owned.glob("*.zip"))]
        report["status"] = "packaged-game-validation-pending"
        print(str(owned))
        return 0
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError) as error:
        report.update(status="failed", error=str(error))
        print("CLAW package: " + str(error), file=sys.stderr)
        return 2
    finally:
        if owned:
            (owned / "distribution-package.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
