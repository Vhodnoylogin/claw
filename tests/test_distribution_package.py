"""Reject stale compiled inputs and unexpected files before preparing an install."""
import hashlib
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
