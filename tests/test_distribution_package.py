"""Reject stale compiled inputs and unexpected files before preparing an install."""
import hashlib
import json
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("claw_packaging", ROOT / "scripts/package-distribution.py")
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class DistributionPackage(unittest.TestCase):
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
