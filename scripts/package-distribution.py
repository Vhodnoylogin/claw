"""Assemble a hash-verified development companion in NEW external staging.

This packages already built candidates; it never installs, starts the game or
promotes a candidate to release. Native/data receipts must match current sources.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import shutil
import struct
import sys
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import presets

NATIVE_SOURCES = {"distribution/CMakeLists.txt", "distribution/dependencies.json",
                  "distribution/src/Plugin.cpp", "distribution/src/Preset.cpp",
                  "distribution/src/Tool.cpp", "distribution/tests/CoreTests.cpp",
                  "distribution/include/claw/Preset.h", "distribution/include/claw/RequestOwnership.h",
                  "distribution/build.ps1", "distribution/README.md", "distribution/papyrus/CLAWDistributionNative.psc"}
BASE_LICENSES = {"commonlib", "pugixml", "fmt", "spdlog", "rapidcsv"}
SE_LICENSES = BASE_LICENSES | {"directxmath", "directxtk", "openvr"}
RUNTIMES = {"VR": {"label": "Skyrim VR 1.4.15", "native": "Skyrim VR 1.4.15",
                   "requires": "SKSEVR, matching VR Address Library, RaceMenu VR and UIExtensions"},
            "SE": {"label": "Skyrim SE 1.7.104.0", "native": "SkyrimSE.exe1.7.104.0",
                   "requires": "SKSE 2.3.1, matching Address Library v13, runtime-compatible RaceMenu/SKEE and UIExtensions"}}


def builder_module():
    spec = importlib.util.spec_from_file_location("claw_distribution_package", ROOT / "scripts/build-authoring.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def same_file(path, digest, size, sha):
    path = Path(path)
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest) or type(size) is not int or size < 0:
        raise ValueError("Malformed file receipt")
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


def native_receipts(folder, combined=None, runtime="VR"):
    """Normalize historical review receipts or one source/artifact build freeze."""
    if runtime == "SE" and combined is None:
        raise ValueError("SE requires a unified, root-reviewed native freeze")
    if combined is not None:
        document = json.loads(combined.read_text(encoding="utf-8-sig"))
        if not isinstance(document, dict) or not isinstance(document.get("tests"), dict):
            raise ValueError("Expected a compiled, offline-verified native development freeze")
        checks = document["tests"]
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
        name = Path(item["Path"]).resolve().relative_to(ROOT).as_posix()
        if name in present:
            raise ValueError("Duplicate native source receipt")
        present.add(name)
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


def pe_metadata(path):
    """Read the actual exported metadata; never load or execute the DLL."""
    if Path(path).stat().st_size > 64 * 1024 * 1024:
        raise ValueError("Native DLL is unexpectedly large")
    data = Path(path).read_bytes()
    try:
        def unpack(fmt, position):
            return struct.unpack_from(fmt, data, position)
        if data[:2] != b"MZ":
            raise ValueError("Native DLL is not PE")
        pe, = unpack("<I", 0x3c)
        if data[pe:pe + 4] != b"PE\0\0" or unpack("<H", pe + 4)[0] != 0x8664:
            raise ValueError("Need an x64 PE native DLL")
        count, = unpack("<H", pe + 6)
        optional_size, = unpack("<H", pe + 20)
        optional = pe + 24
        if unpack("<H", optional)[0] != 0x20b or not 0 < count <= 96 or optional_size < 120:
            raise ValueError("Malformed native PE headers")
        headers_size, = unpack("<I", optional + 60)
        sections = [unpack("<IIII", optional + optional_size + index * 40 + 8) for index in range(count)]
        def offset(rva):
            if rva < headers_size and rva < len(data):
                return rva
            for virtual_size, base, raw_size, raw in sections:
                if base <= rva < base + max(virtual_size, raw_size) and rva - base < raw_size:
                    return raw + rva - base
            raise ValueError("Unmapped native PE data")
        export_rva, export_size = unpack("<II", optional + 112)
        if not export_rva:
            raise ValueError("Native DLL lacks SKSE exports")
        fields = unpack("<IIHHIIIIIII", offset(export_rva))
        _, _, _, _, _, _, functions, names, function_table, name_table, ordinal_table = fields
        if not 0 < functions <= 4096 or names > functions:
            raise ValueError("Malformed native PE exports")
        export_names = []
        for index in range(names):
            name_rva, = unpack("<I", offset(name_table) + index * 4)
            name_start = offset(name_rva)
            name_end = data.find(b"\0", name_start, name_start + 256)
            if name_end < 0:
                raise ValueError("Malformed native PE export name")
            export_names.append(data[name_start:name_end])
        if not {b"SKSEPlugin_Query", b"SKSEPlugin_Load"}.issubset(export_names):
            raise ValueError("Native DLL lacks SKSE Query/Load exports")
        for index, name in enumerate(export_names):
            if name != b"SKSEPlugin_Version":
                continue
            ordinal, = unpack("<H", offset(ordinal_table) + index * 2)
            if ordinal >= functions:
                raise ValueError("Malformed native PE export ordinal")
            target, = unpack("<I", offset(function_table) + ordinal * 4)
            if export_rva <= target < export_rva + export_size:
                raise ValueError("SKSE metadata cannot be a forwarded export")
            start = offset(target)
            raw = data[start:start + 0x350]
            if len(raw) != 0x350:
                raise ValueError("Truncated SKSE metadata")
            return {"dataVersion": unpack("<I", start)[0], "pluginVersionPacked": unpack("<I", start + 4)[0],
                    "pluginName": raw[8:0x108].split(b"\0")[0].decode("utf-8"),
                    "versionIndependenceEx": unpack("<I", start + 0x304)[0],
                    "versionIndependence": unpack("<I", start + 0x308)[0],
                    "compatibleVersionsPacked": list(unpack("<16I", start + 0x30c)),
                    "minimumSKSEVersionPacked": unpack("<I", start + 0x34c)[0]}
        return None
    except (struct.error, UnicodeError, IndexError) as error:
        raise ValueError("Malformed native PE metadata") from error


def linked_document(link, sha):
    if not isinstance(link, dict):
        raise ValueError("Missing linked native receipt")
    path = Path(link["path"])
    same_file(path, link["sha256"], link["bytes"], sha)
    path = path.resolve()
    return path, json.loads(path.read_text(encoding="utf-8-sig"))


def source_map(rows):
    result = {}
    for row in rows:
        name = Path(row["path"]).resolve().relative_to(ROOT).as_posix()
        if name in result:
            raise ValueError("Duplicate writer source")
        result[name] = (row["sha256"].lower(), row["bytes"])
    return result


def artifact_map(rows):
    result = {}
    for row in rows:
        name = Path(row["path"]).name
        if name in result:
            raise ValueError("Duplicate writer artifact")
        result[name] = (row["sha256"].lower(), row["bytes"])
    if set(result) != {"CLAWDistribution.dll", "claw-preset-tool.exe", "claw-preset-tests.exe"}:
        raise ValueError("Incomplete writer native artifacts")
    return result


def native_runtime(runtime, combined, verified, sha):
    """Bind SE review, immutable writer build, current sources and actual DLL data."""
    if runtime not in RUNTIMES:
        raise ValueError("Unsupported package runtime")
    document = json.loads(combined.read_text(encoding="utf-8-sig")) if combined else {}
    actual = pe_metadata(verified["CLAWDistribution.dll"][1])
    configuration = document.get("configuration", {})
    if runtime == "VR":
        declared = configuration.get("runtime")
        if declared is not None and declared not in ("Skyrim VR 1.4.15", "SkyrimVR.exe1.4.15.0"):
            raise ValueError("Native receipt runtime does not match VR package")
        if actual is not None and actual["compatibleVersionsPacked"] != [0x010400f0] + [0] * 15:
            raise ValueError("DLL metadata does not match VR package")
        return {"document": document, "metadata": actual}
    if combined is None:
        raise ValueError("SE requires a unified native receipt")
    if configuration.get("runtime") != RUNTIMES["SE"]["native"] or configuration.get("SKSEMinimum") != "2.3.1":
        raise ValueError("SE native runtime/SKSE declarations do not match")
    review = document.get("rootReview", {})
    if (review.get("status") != "passed-for-external-development-packaging-only"
            or review.get("gameValidated") is not False or review.get("installed") is not False):
        raise ValueError("SE requires explicit root review for development packaging")
    expected = {"dataVersion": 1, "pluginVersionPacked": 0x00010000, "pluginName": "CLAWDistribution",
                "versionIndependenceEx": 2, "versionIndependence": 4,
                "compatibleVersionsPacked": [0x01070680] + [0] * 15, "minimumSKSEVersionPacked": 0x02030010}
    declared_metadata = document.get("binaryInspection", {}).get("metadata")
    if (actual != expected or not isinstance(declared_metadata, dict)
            or json.dumps({k: declared_metadata.get(k) for k in expected}, sort_keys=True) != json.dumps(expected, sort_keys=True)):
        raise ValueError("SE requires matching actual 1.7.104/V5/updated-struct SKSE metadata")
    writer_path, writer = linked_document(document.get("writerFreeze"), sha)
    if writer.get("tests") != document.get("tests") or writer.get("configuration") != configuration:
        raise ValueError("SE review changed writer test/configuration lineage")
    if writer.get("binaryInspection", {}).get("metadata") != declared_metadata:
        raise ValueError("SE review changed writer metadata")
    if artifact_map(writer["artifacts"]) != artifact_map(document["artifacts"]):
        raise ValueError("SE review mixed writer native binaries")
    before, after = source_map(writer["sourceFiles"]), source_map(document["sourceFiles"])
    if set(before) != set(after) or not NATIVE_SOURCES.issubset(after):
        raise ValueError("SE review changed writer source inventory")
    if before != after:
        raise ValueError("SE review contains unbuilt writer/current source changes")
    if "configurationDelta" in document:
        raise ValueError("SE package requires a fresh writer build without configurationDelta")
    for field in ("dependencyReceipt", "licensesReceipt"):
        if document.get(field) != writer.get(field):
            raise ValueError("SE review changed writer dependency/license binding")
    dependency_path, dependency = linked_document(document.get("dependencyReceipt"), sha)
    license_path, _ = linked_document(document.get("licensesReceipt"), sha)
    for native_key, dependency_key in (("CommonLibCommit", "sdkOwnerApprovedCommit"),
                                       ("CommonLibParent", "sdkCanonicalParent"), ("OpenVRGitlink", "openvrGitlink")):
        if not configuration.get(native_key) or configuration[native_key] != dependency.get(dependency_key):
            raise ValueError("SE SDK configuration and dependency receipt do not match")
    if (dependency.get("licensesReceiptSha256") != sha(license_path)
            or Path(dependency.get("licensesReceipt", "")).resolve() != license_path):
        raise ValueError("Modern dependency and license receipts do not match")
    return {"document": document, "metadata": actual, "writer": writer, "writerPath": writer_path,
            "dependency": dependency, "dependencyPath": dependency_path, "licensePath": license_path}


def dependency_licenses(arguments, receipt, runtime_info, runtime, sha):
    manual = {}
    for value in arguments:
        name, separator, path = value.partition("=")
        if not separator or name in manual or name not in BASE_LICENSES:
            raise ValueError("Invalid/duplicate license argument")
        manual[name] = Path(path).resolve()
    licenses = {name: [path] for name, path in manual.items()}
    if receipt is not None:
        if runtime != "SE" or receipt.resolve() != runtime_info["licensePath"]:
            raise ValueError("License receipt does not match native SE dependency binding")
        link = runtime_info["document"]["licensesReceipt"]
        same_file(receipt, link["sha256"], link["bytes"], sha)
        aliases = {"CommonLibSSE-NG": "commonlib", "OpenVR": "openvr"}
        document = json.loads(receipt.read_text(encoding="utf-8-sig"))
        seen = set()
        for original, rows in document["files"].items():
            name = aliases.get(original, original)
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", name) or name in seen or not isinstance(rows, list) or not rows:
                raise ValueError("Invalid modern license inventory")
            seen.add(name)
            paths = []
            for row in rows:
                path = Path(row["path"]).resolve()
                if path.is_symlink() or not path.is_file() or sha(path).lower() != row["sha256"].lower():
                    raise ValueError("Modern license bytes do not match receipt")
                paths.append(path)
            if name in manual and not any(sha(manual[name]) == sha(path) for path in paths):
                raise ValueError("Manual license conflicts with modern dependency receipt: " + name)
            licenses[name] = paths
    if runtime == "SE":
        if receipt is None:
            raise ValueError("SE requires the bound modern licenses receipt")
        # Pugixml is built from the separate pinned source, not the modern prefix.
        writer_path, writer = runtime_info["writerPath"], runtime_info["writer"]
        cache = writer_path.parent / "CMakeCache.txt"
        if sha(cache) != writer.get("evidenceFiles", {}).get("CMakeCache.txt"):
            raise ValueError("Missing frozen writer CMake cache for pugixml license")
        match = re.search(r"^FETCHCONTENT_SOURCE_DIR_PUGIXML:[^=\r\n]+=([^\r\n]+)$", cache.read_text(encoding="utf-8-sig"), re.MULTILINE)
        expected_license = Path(match[1]) / "LICENSE.md" if match else None
        if not expected_license or "pugixml" not in manual or sha(manual["pugixml"]) != sha(expected_license):
            raise ValueError("Pugixml license does not match frozen build source")
    required = SE_LICENSES if runtime == "SE" else BASE_LICENSES
    if not required.issubset(licenses) or (runtime == "VR" and set(licenses) != BASE_LICENSES):
        raise ValueError("Supply all required dependency license texts")
    for paths in licenses.values():
        for path in paths:
            if path.is_symlink() or not path.is_file() or path.stat().st_size < 100:
                raise ValueError("Missing license text: " + str(path))
    return licenses


def se_dependency_report(info, combined, sha):
    dependency = info["dependency"]
    return {"runtime": RUNTIMES["SE"]["label"],
            "nativeConfiguration": {k: v for k, v in info["document"]["configuration"].items() if k != "buildDirectory"},
            "writerFreezeSha256": info["document"]["writerFreeze"]["sha256"], "nativeReviewSha256": sha(combined),
            "dependencyReceiptSha256": sha(info["dependencyPath"]), "licensesReceiptSha256": sha(info["licensePath"]),
            "sdkCommit": dependency["sdkOwnerApprovedCommit"], "sdkCanonicalParent": dependency["sdkCanonicalParent"],
            "openvrGitlink": dependency["openvrGitlink"], "triplet": dependency["triplet"], "crt": dependency["crt"],
            "packages": dependency["actualInstalledVersions"]}


def archive(folder, target):
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED) as output:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                output.write(path, path.relative_to(folder).as_posix())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=str.upper, choices=sorted(RUNTIMES), default="VR")
    parser.add_argument("--native-build", type=Path, required=True,
                        help="Contains artifacts-review.json and source-manifest-review.json")
    parser.add_argument("--native-receipt", type=Path,
                        help="Optional unified native build freeze with sourceFiles/artifacts/tests")
    parser.add_argument("--data-build", type=Path, required=True,
                        help="Contains distribution-data-build.json and package/")
    parser.add_argument("--presets", type=Path, required=True, help="CLAW preset XML subtree")
    parser.add_argument("--license", action="append", default=[], metavar="NAME=FILE",
                        help="Required names: commonlib, pugixml, fmt, spdlog, rapidcsv")
    parser.add_argument("--licenses-receipt", type=Path,
                        help="SE requires its frozen modern dependency license inventory")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    helper = builder_module()
    owned = None
    profile = RUNTIMES[args.runtime]
    report = {"status": "incomplete", "gameValidated": False, "runtime": profile["label"], "runtimeTarget": args.runtime}
    try:
        native, data, preset_root = args.native_build.resolve(), args.data_build.resolve(), args.presets.resolve()
        combined = args.native_receipt.resolve() if args.native_receipt else None
        if combined is not None and not combined.is_relative_to(native):
            raise ValueError("Native build freeze must belong to the specified build")
        sources, native_artifacts, source_receipt, artifact_receipt = native_receipts(native, combined, args.runtime)
        native_sources(sources, helper.sha)
        verified_binaries = native_binaries(native, native_artifacts, helper.sha)
        runtime_info = native_runtime(args.runtime, combined, verified_binaries, helper.sha)
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
        licenses = dependency_licenses(args.license, args.licenses_receipt, runtime_info, args.runtime, helper.sha)
        license_hashes = {name: [helper.sha(path) for path in paths] for name, paths in licenses.items()}
        license_paths = [path for paths in licenses.values() for path in paths]
        owned = helper.new_staging(args.out, [native, data, preset_root, *license_paths])
        package, examples = owned / "companion", owned / "example-presets"
        shutil.copytree(data / "package", package)
        target_dll = package / "SKSE/Plugins/CLAWDistribution.dll"
        target_dll.parent.mkdir(parents=True)
        shutil.copy2(dll_path, target_dll)
        docs = package / "Docs/CLAWDistribution"
        notices = docs / "ThirdParty"
        notices.mkdir(parents=True)
        for name, paths in licenses.items():
            for index, path in enumerate(paths):
                destination = notices / (name + (f"-{index + 1:02}" if len(paths) > 1 else "") + ".txt")
                shutil.copy2(path, destination)
                if helper.sha(destination) != license_hashes[name][index]:
                    raise ValueError("License input changed while packaging")
        for name, source in {"README.md": ROOT / "distribution/README.md", "Preset-authoring.md": ROOT / "docs/presets.md"}.items():
            shutil.copy2(source, docs / name)
        if args.runtime == "VR":
            shutil.copy2(ROOT / "distribution/dependencies.json", docs / "Build-dependencies.json")
        else:
            dependency_report = se_dependency_report(runtime_info, combined, helper.sha)
            dependency_report["licenseNotices"] = {name: len(paths) for name, paths in licenses.items()}
            (docs / "Build-dependencies.json").write_text(json.dumps(dependency_report, indent=2) + "\n", encoding="utf-8")
        shutil.copy2(ROOT / "distribution/papyrus/CLAWDistributionNative.psc", docs / "CLAWDistributionNative.psc")
        (package / "CLAW Distribution - DEVELOPMENT.txt").write_text(
            f"Development test candidate; not runtime accepted. Target: {profile['label']}.\n"
            f"Requires CLAW 0.6.2.0, its dependencies, {profile['requires']}.\n"
            "Keep neutral CLAW body meshes. Install at least one typed preset mod separately.\n"
            "F8 opens werewolf presets for the crosshair target, or the player.\n"
            "OBody is optional and must support the selected game runtime; its human presets remain separate.\n"
            "The current exact runtime bound describes this test candidate, not the final support matrix.\n"
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
                            "licenses": {name: [{"path": str(p), "sha256": digest} for p, digest in zip(paths, license_hashes[name])]
                                         for name, paths in licenses.items()}}
        if args.runtime == "SE":
            report["inputs"].update(writerFreeze=runtime_info["document"]["writerFreeze"],
                                    dependencyReceipt=runtime_info["document"]["dependencyReceipt"],
                                    licensesReceipt=runtime_info["document"]["licensesReceipt"])
            report["nativeMetadata"] = runtime_info["metadata"]
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
