"""Reject stale compiled inputs and unexpected files before preparing an install."""
import hashlib
import copy
import json
import importlib.util
from pathlib import Path
import tempfile
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("claw_packaging", ROOT / "scripts/package-distribution.py")
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def record(path):
    return {"path": str(path), "sha256": sha(path), "bytes": path.stat().st_size}


def pe_fixture(version=0x01070680, flags=4, extended=2, minimum=0x02030010, metadata=True):
    """Fixed PE data-layout fixture, never an engine executable or ABI simulation."""
    data = bytearray(0x1200)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3c, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HH", data, 0x84, 0x8664, 1)
    struct.pack_into("<H", data, 0x94, 0xf0)
    optional = 0x98
    struct.pack_into("<H", data, optional, 0x20b)
    struct.pack_into("<I", data, optional + 60, 0x200)
    struct.pack_into("<II", data, optional + 112, 0x1000, 0x180)
    struct.pack_into("<IIII", data, optional + 0xf0 + 8, 0x1000, 0x1000, 0x1000, 0x200)
    names = [b"SKSEPlugin_Query", b"SKSEPlugin_Load"] + ([b"SKSEPlugin_Version"] if metadata else [])
    struct.pack_into("<IIHHIIIIIII", data, 0x200, 0, 0, 0, 0, 0, 1, len(names), len(names), 0x1090, 0x1080, 0x10a0)
    for index, name in enumerate(names):
        struct.pack_into("<I", data, 0x280 + index * 4, 0x10b0 + index * 0x20)
        struct.pack_into("<I", data, 0x290 + index * 4, [0x1200, 0x1210, 0x1400][index])
        struct.pack_into("<H", data, 0x2a0 + index * 2, index)
        data[0x2b0 + index * 0x20:0x2b0 + index * 0x20 + len(name) + 1] = name + b"\0"
    struct.pack_into("<II", data, 0x600, 1, 0x00010000)
    data[0x608:0x608 + 17] = b"CLAWDistribution\0"
    struct.pack_into("<II", data, 0x904, extended, flags)
    struct.pack_into("<I", data, 0x90c, version)
    struct.pack_into("<I", data, 0x94c, minimum)
    return bytes(data)


def se_fixture(folder):
    binaries = []
    for name in ("CLAWDistribution.dll", "claw-preset-tool.exe", "claw-preset-tests.exe"):
        path = folder / name
        path.write_bytes(pe_fixture() if name.endswith("dll") else name.encode())
        binaries.append(record(path))
    sources = [record(ROOT / name) for name in sorted(package.NATIVE_SOURCES)]
    license_folder = folder / "licenses"
    license_folder.mkdir()
    files = {}
    for name in ("CommonLibSSE-NG", "OpenVR", "fmt", "spdlog", "rapidcsv", "directxmath", "directxtk"):
        rows = []
        for index in range(3 if name == "CommonLibSSE-NG" else 1):
            path = license_folder / (name + str(index) + ".txt")
            path.write_text((name + " legal notice fixture. ") * 20)
            rows.append({"path": str(path), "sha256": sha(path)})
        files[name] = rows
    license_receipt = folder / "licenses.json"
    license_receipt.write_text(json.dumps({"files": files}))
    dependency = folder / "dependency.json"
    dependency_data = {"licensesReceipt": str(license_receipt), "licensesReceiptSha256": sha(license_receipt),
                       "sdkOwnerApprovedCommit": "fixture-sdk", "sdkCanonicalParent": "fixture-parent", "openvrGitlink": "fixture-openvr",
                       "triplet": "x64-windows-static-md", "crt": "dynamic /MD", "actualInstalledVersions": [{"Package": "fmt", "Version": "12.2.0"}]}
    dependency.write_text(json.dumps(dependency_data))
    pugi = folder / "pugixml"
    pugi.mkdir()
    (pugi / "LICENSE.md").write_text("Pugixml fixture legal notice. " * 20)
    writer_path = folder / "writer/freeze.json"
    writer_path.parent.mkdir()
    cache = writer_path.parent / "CMakeCache.txt"
    cache.write_text("FETCHCONTENT_SOURCE_DIR_PUGIXML:PATH=" + str(pugi) + "\n")
    checks = {"ctestExitCode": 0, "cliExitCode": 0, "registeredCTestTests": 1,
              "contractCases": 23, "validExamplePresets": 4, "engineABIMockedOrExecuted": False}
    writer = {"status": "original-writer-status-must-not-be-normalized-in-place", "sourceFiles": sources,
              "artifacts": binaries, "tests": checks,
              "configuration": {"runtime": "SkyrimSE.exe1.7.104.0", "SKSEMinimum": "2.3.1",
                                "CommonLibCommit": "fixture-sdk", "CommonLibParent": "fixture-parent", "OpenVRGitlink": "fixture-openvr",
                                "buildDirectory": "private-build-directory"},
              "binaryInspection": {"metadata": package.pe_metadata(folder / "CLAWDistribution.dll")},
              "dependencyReceipt": record(dependency), "licensesReceipt": record(license_receipt),
              "evidenceFiles": {"CMakeCache.txt": sha(cache)}}
    writer_path.write_text(json.dumps(writer))
    document = copy.deepcopy(writer)
    document.update(status="compiled-offline-verified-development-candidate-awaiting-root-review",
                    writerFreeze=record(writer_path), rootReview={"status": "passed-for-external-development-packaging-only", "gameValidated": False, "installed": False})
    review = folder / "review.json"
    review.write_text(json.dumps(document))
    return {"document": document, "review": review, "writer": writer, "writerPath": writer_path,
            "licenses": license_receipt, "pugi": pugi / "LICENSE.md", "folder": folder}


def runtime_info(fixture, runtime="SE"):
    fixture["review"].write_text(json.dumps(fixture["document"]))
    sources, artifacts, _, _ = package.native_receipts(fixture["folder"], fixture["review"], runtime)
    package.native_sources(sources, sha)
    verified = package.native_binaries(fixture["folder"], artifacts, sha)
    return package.native_runtime(runtime, fixture["review"], verified, sha)


class DistributionPackage(unittest.TestCase):
    def test_legacy_vr_pe_without_modern_metadata_remains_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            path = folder / "CLAWDistribution.dll"
            path.write_bytes(pe_fixture(metadata=False))
            result = package.native_runtime("VR", None, {"CLAWDistribution.dll": (None, path)}, sha)
            self.assertIsNone(result["metadata"])

    def test_se_dependency_report_uses_bound_modern_inputs_and_rejects_sdk_mix(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = se_fixture(Path(directory))
            info = runtime_info(fixture)
            report = package.se_dependency_report(info, fixture["review"], sha)
            self.assertEqual(report["sdkCommit"], "fixture-sdk")
            self.assertEqual(report["packages"], [{"Package": "fmt", "Version": "12.2.0"}])
            self.assertEqual(report["runtime"], "Skyrim SE 1.7.104.0")
            self.assertNotIn("buildDirectory", report["nativeConfiguration"])
            dependency = Path(info["dependencyPath"])
            changed = json.loads(dependency.read_text())
            changed["sdkOwnerApprovedCommit"] = "some-other-sdk-build"
            dependency.write_text(json.dumps(changed))
            for document in (fixture["writer"], fixture["document"]):
                document["dependencyReceipt"] = record(dependency)
            fixture["writerPath"].write_text(json.dumps(fixture["writer"]))
            fixture["document"]["writerFreeze"] = record(fixture["writerPath"])
            with self.assertRaisesRegex(ValueError, "SDK configuration"):
                runtime_info(fixture)

    def test_se_requires_unified_review_and_retains_writer_file(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            with self.assertRaisesRegex(ValueError, "unified"):
                package.native_receipts(folder, runtime="SE")
            fixture = se_fixture(folder)
            before = fixture["writerPath"].read_bytes()
            info = runtime_info(fixture)
            self.assertEqual(info["metadata"]["compatibleVersionsPacked"][0], 0x01070680)
            self.assertEqual(fixture["writerPath"].read_bytes(), before)
            fixture["document"].pop("rootReview")
            with self.assertRaisesRegex(ValueError, "root review"):
                runtime_info(fixture)

    def test_runtime_label_cannot_relabel_se_binary_as_vr(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = se_fixture(Path(directory))
            with self.assertRaisesRegex(ValueError, "runtime.*VR"):
                runtime_info(fixture, "VR")
            fixture["document"]["configuration"]["runtime"] = "Skyrim VR 1.4.15"
            with self.assertRaisesRegex(ValueError, "metadata.*VR"):
                runtime_info(fixture, "VR")
            with self.assertRaisesRegex(ValueError, "runtime/SKSE"):
                runtime_info(fixture)
            with self.assertRaisesRegex(ValueError, "Unsupported"):
                runtime_info(fixture, "AE")

    def test_se_actual_pe_rejects_missing_or_incompatible_metadata_despite_receipt(self):
        cases = {"old-SE": {"version": 0x01064920}, "other-1.7": {"version": 0x01070630},
                 "VR": {"version": 0x010400f0}, "missing-V5": {"extended": 0},
                 "missing-struct": {"flags": 0}, "old-SKSE": {"minimum": 0x02020060},
                 "missing-export": {"metadata": False}}
        for label, options in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                fixture = se_fixture(Path(directory))
                dll = Path(directory) / "CLAWDistribution.dll"
                dll.write_bytes(pe_fixture(**options))
                for document in (fixture["document"], fixture["writer"]):
                    document["artifacts"][0] = record(dll)
                fixture["writerPath"].write_text(json.dumps(fixture["writer"]))
                fixture["document"]["writerFreeze"] = record(fixture["writerPath"])
                with self.assertRaisesRegex(ValueError, "SKSE metadata"):
                    runtime_info(fixture)

    def test_declared_metadata_must_match_actual_typed_values(self):
        for change in ("missing", "boolean", "wrong-minimum"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                fixture = se_fixture(Path(directory))
                metadata = fixture["document"]["binaryInspection"]["metadata"]
                if change == "missing":
                    metadata.pop("versionIndependenceEx")
                elif change == "boolean":
                    metadata["dataVersion"] = True
                else:
                    metadata["minimumSKSEVersionPacked"] = 0
                with self.assertRaisesRegex(ValueError, "SKSE metadata"):
                    runtime_info(fixture)

    def test_se_writer_hash_and_all_three_artifacts_bind_review(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = se_fixture(Path(directory))
            fixture["writerPath"].write_text(fixture["writerPath"].read_text() + " ")
            with self.assertRaisesRegex(ValueError, "Receipt does not match"):
                runtime_info(fixture)
        with tempfile.TemporaryDirectory() as directory:
            fixture = se_fixture(Path(directory))
            tool = Path(directory) / "claw-preset-tool.exe"
            tool.write_bytes(b"different native build CLI")
            fixture["document"]["artifacts"][1] = record(tool)
            with self.assertRaisesRegex(ValueError, "mixed writer native binaries"):
                runtime_info(fixture)

    def test_review_cannot_change_tests_dependencies_or_writer_source_inventory(self):
        for change in ("tests", "dependency", "source"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                fixture = se_fixture(Path(directory))
                if change == "tests":
                    fixture["document"]["tests"]["contractCases"] = 24
                elif change == "dependency":
                    fixture["document"]["dependencyReceipt"]["sha256"] = "0" * 64
                else:
                    fixture["document"]["sourceFiles"] = [row for row in fixture["document"]["sourceFiles"] if Path(row["path"]).name != "README.md"]
                with self.assertRaises(ValueError):
                    runtime_info(fixture)

    def test_every_unbuilt_source_change_and_stray_configuration_delta_is_refused(self):
        for name in ("distribution/CMakeLists.txt", "distribution/src/Plugin.cpp"):
            with self.subTest(source=name), tempfile.TemporaryDirectory() as directory:
                fixture = se_fixture(Path(directory))
                row = next(row for row in fixture["writer"]["sourceFiles"] if Path(row["path"]) == ROOT / name)
                row["sha256"] = "0" * 64
                fixture["writerPath"].write_text(json.dumps(fixture["writer"]))
                fixture["document"]["writerFreeze"] = record(fixture["writerPath"])
                with self.assertRaisesRegex(ValueError, "unbuilt.*source"):
                    runtime_info(fixture)
        for delta in (None, {}, {"artifactsUnchanged": True, "testLineage": "writerFreeze"}):
            with self.subTest(delta=delta), tempfile.TemporaryDirectory() as directory:
                fixture = se_fixture(Path(directory))
                fixture["document"]["configurationDelta"] = delta
                with self.assertRaisesRegex(ValueError, "configurationDelta"):
                    runtime_info(fixture)

    def test_modern_notices_keep_five_dependencies_and_every_commonlib_notice(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = se_fixture(Path(directory))
            info = runtime_info(fixture)
            notices = package.dependency_licenses(["pugixml=" + str(fixture["pugi"])], fixture["licenses"], info, "SE", sha)
            self.assertTrue(package.SE_LICENSES.issubset(notices))
            self.assertEqual(len(notices["commonlib"]), 3)
            with self.assertRaisesRegex(ValueError, "bound modern"):
                package.dependency_licenses(["pugixml=" + str(fixture["pugi"])], None, info, "SE", sha)
            wrong = Path(directory) / "wrong-license.txt"
            wrong.write_text("A different version's license text. " * 20)
            for name in ("fmt", "commonlib", "pugixml"):
                arguments = ["pugixml=" + str(fixture["pugi"])] if name != "pugixml" else []
                arguments.append(name + "=" + str(wrong))
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, "license"):
                    package.dependency_licenses(arguments, fixture["licenses"], info, "SE", sha)

    def test_modern_license_inventory_must_match_frozen_bytes_and_required_names(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = se_fixture(Path(directory))
            info = runtime_info(fixture)
            license_doc = json.loads(fixture["licenses"].read_text())
            path = Path(license_doc["files"]["directxtk"][0]["path"])
            path.write_text("modified license content" * 20)
            with self.assertRaisesRegex(ValueError, "license bytes"):
                package.dependency_licenses(["pugixml=" + str(fixture["pugi"])], fixture["licenses"], info, "SE", sha)
        with tempfile.TemporaryDirectory() as directory:
            fixture = se_fixture(Path(directory))
            license_doc = json.loads(fixture["licenses"].read_text())
            license_doc["files"].pop("directxtk")
            fixture["licenses"].write_text(json.dumps(license_doc))
            # A newly coherent fixture receipt still cannot omit an applicable linked dependency.
            dependency_path = Path(fixture["writer"]["dependencyReceipt"]["path"])
            dependency_doc = json.loads(dependency_path.read_text())
            dependency_doc["licensesReceiptSha256"] = sha(fixture["licenses"])
            dependency_path.write_text(json.dumps(dependency_doc))
            for document in (fixture["writer"], fixture["document"]):
                document.update(licensesReceipt=record(fixture["licenses"]), dependencyReceipt=record(dependency_path))
            fixture["writerPath"].write_text(json.dumps(fixture["writer"]))
            fixture["document"]["writerFreeze"] = record(fixture["writerPath"])
            info = runtime_info(fixture)
            with self.assertRaisesRegex(ValueError, "required dependency"):
                package.dependency_licenses(["pugixml=" + str(fixture["pugi"])], fixture["licenses"], info, "SE", sha)

    def test_unverified_combined_native_freeze_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            receipt = folder / "freeze.json"
            receipt.write_text(json.dumps({"status":"compiled-offline-verified-development-candidate-awaiting-root-review",
                "tests":{"ctestExitCode":1,"cliExitCode":0,"engineABIMockedOrExecuted":False},
                "sourceFiles":[],"artifacts":[]}))
            with self.assertRaisesRegex(ValueError, "offline-verified"):
                package.native_receipts(folder, receipt)

    def test_false_exit_or_zero_executed_tests_do_not_attest_native_checks(self):
        checks = {"ctestExitCode":0, "cliExitCode":0, "registeredCTestTests":1,
                  "contractCases":20, "validExamplePresets":4, "engineABIMockedOrExecuted":False}
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            receipt = folder / "freeze.json"
            for key, value in (("ctestExitCode", False), ("cliExitCode", False),
                               ("registeredCTestTests", 0), ("contractCases", 0),
                               ("validExamplePresets", 0)):
                with self.subTest(key=key, value=value):
                    receipt.write_text(json.dumps({"status":"compiled-offline-verified-development-candidate-awaiting-root-review",
                        "tests":{**checks, key:value}, "sourceFiles":[], "artifacts":[]}))
                    with self.assertRaisesRegex(ValueError, "offline-verified"):
                        package.native_receipts(folder, receipt)

    def test_offline_cli_and_test_sources_cannot_be_omitted_from_receipt(self):
        records = [{"Path":str(ROOT / name), "SHA256":sha(ROOT / name)}
                   for name in sorted(package.NATIVE_SOURCES)]
        for missing in ("Tool.cpp", "CoreTests.cpp"):
            with self.subTest(missing=missing), self.assertRaisesRegex(ValueError, "incomplete"):
                package.native_sources([row for row in records if Path(row["Path"]).name != missing], sha)

    def test_offline_binaries_must_be_present_inside_build_with_matching_bytes(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as external:
            folder = Path(directory)
            records = []
            for name in ("CLAWDistribution.dll", "claw-preset-tool.exe", "claw-preset-tests.exe"):
                path = folder / name
                path.write_bytes(name.encode())
                records.append({"Path":str(path), "SHA256":sha(path), "Bytes":path.stat().st_size})
            with self.assertRaisesRegex(ValueError, "claw-preset-tests"):
                package.native_binaries(folder, records[:-1], sha)
            tool = Path(records[1]["Path"])
            outside = Path(external) / tool.name
            outside.write_bytes(tool.read_bytes())
            foreign = [{**row, "Path":str(outside)} if row is records[1] else row for row in records]
            with self.assertRaisesRegex(ValueError, "belong"):
                package.native_binaries(folder, foreign, sha)
            tool.write_bytes(b"stale CLI bytes")
            with self.assertRaisesRegex(ValueError, "Receipt does not match"):
                package.native_binaries(folder, records, sha)

    def test_changed_compiled_bytes_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.dll"
            path.write_bytes(b"first compiled candidate")
            digest, size = sha(path), path.stat().st_size
            path.write_bytes(b"other compiled candidate")
            with self.assertRaisesRegex(ValueError, "Receipt does not match"):
                package.same_file(path, digest, size, sha)

    def test_stale_source_receipt_is_refused(self):
        path = ROOT / "distribution/src/Plugin.cpp"
        with self.assertRaisesRegex(ValueError, "current source"):
            package.current_source(path, "0" * 64, sha)

    def test_external_source_cannot_attest_repository_build(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Plugin.cpp"
            path.write_text("externally modified source")
            with self.assertRaisesRegex(ValueError, "current source"):
                package.current_source(path, sha(path), sha)

    def test_extra_data_file_is_refused_even_if_three_receipts_match(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            expected = {"companion.esp", "native.pex", "menu.pex"}
            records = []
            for name in expected:
                path = folder / name
                path.write_bytes(name.encode())
                records.append({"path": name, "sha256": sha(path), "bytes": path.stat().st_size})
            (folder / "test-actor.esp").write_bytes(b"must never be packaged")
            with self.assertRaisesRegex(ValueError, "Unexpected or missing"):
                package.artifact_tree(folder, records, expected, sha)


if __name__ == "__main__":
    unittest.main()
