"""Source-only donor selection and fail-before-output contracts; no NIF/game calls."""
import contextlib
import hashlib
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location(
    "claw_source_only_contract", ROOT / "src/main/python/build-tools/build-all.py")
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


class SourceOnlyBuildTests(unittest.TestCase):
    def setUp(self):
        temporary_root = ROOT / "target/test-source-only"
        temporary_root.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=temporary_root)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.assertTrue(self.root.resolve().is_relative_to(temporary_root.resolve()))
        self.repo = self.root / "checkout"
        self.donor = self.repo / "src/main/resources/donors/body.nif"
        self.donor.parent.mkdir(parents=True)
        self.data = b"pinned donor byte fixture, not an actual NIF"
        self.donor.write_bytes(self.data)
        self.installed_root = self.root / "fake-mods"
        self.installed = self.installed_root / "Donor/meshes/body.nif"
        self.installed.parent.mkdir(parents=True)
        self.installed.write_bytes(self.data)
        self.out = self.root / "uncreated-output"
        self.spec = {"sources": {"donor": {
            "file": "src/main/resources/donors/body.nif",
            "mod": "Donor", "path": "meshes/body.nif",
            "bytes": len(self.data), "crc": build.crc32(self.donor),
            "sha256": hashlib.sha256(self.data).hexdigest()}}}

    def pipeline(self, *, installed=False, allow_installed=False):
        patches = contextlib.ExitStack()
        self.addCleanup(patches.close)
        patches.enter_context(patch.object(build, "ROOT", self.repo))
        patches.enter_context(patch.object(
            build, "P", SimpleNamespace(mods=self.installed_root if installed else None)))
        return build.Pipeline(self.spec, self.out, allow_installed_sources=allow_installed)

    def test_local_pinned_donor_checks_without_mod_manager_configuration(self):
        pipe = self.pipeline()
        with contextlib.redirect_stdout(io.StringIO()):
            rows = pipe.check_sources(False)
        self.assertIsNone(pipe.mods)
        self.assertEqual(Path(rows[0]["path"]), self.donor.resolve())
        self.assertEqual(rows[0]["state"], "совпал")
        self.assertEqual(rows[0]["sha256"], hashlib.sha256(self.data).hexdigest())
        self.assertFalse(self.out.exists())

    def test_missing_local_donor_never_silently_uses_an_installed_copy(self):
        self.donor.unlink()
        pipe = self.pipeline(installed=True)
        self.assertEqual(pipe.source("donor"), self.donor.resolve())
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            pipe.check_sources(False)
        self.assertEqual(self.installed.read_bytes(), self.data)
        self.assertFalse(self.out.exists())

    def test_explicit_installed_fallback_still_checks_the_same_pins(self):
        self.donor.unlink()
        pipe = self.pipeline(installed=True, allow_installed=True)
        with contextlib.redirect_stdout(io.StringIO()):
            rows = pipe.check_sources(False)
        self.assertEqual(Path(rows[0]["path"]), self.installed)
        self.assertEqual(rows[0]["state"], "совпал")
        self.assertFalse(self.out.exists())

    def test_escaping_and_absolute_local_donor_paths_are_rejected(self):
        pipe = self.pipeline(installed=True, allow_installed=True)
        for filename in ("../outside.nif", "src/main/resources/donors/../outside.nif",
                         str(self.donor.resolve())):
            with self.subTest(file=filename):
                self.spec["sources"]["donor"]["file"] = filename
                with self.assertRaisesRegex(ValueError, "beneath"):
                    pipe.source("donor")
        self.assertFalse(self.out.exists())

    def test_sha_mismatch_fails_even_when_crc_and_size_match(self):
        pipe = self.pipeline()
        node = self.spec["sources"]["donor"]
        self.assertEqual(node["crc"], build.crc32(self.donor))
        self.assertEqual(node["bytes"], self.donor.stat().st_size)
        node["sha256"] = "0" * 64
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            pipe.check_sources(False)
        self.assertFalse(self.out.exists())

    def test_a_local_donor_without_a_sha_pin_is_rejected(self):
        pipe = self.pipeline(installed=True, allow_installed=True)
        del self.spec["sources"]["donor"]["sha256"]
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            pipe.source("donor")
        self.assertFalse(self.out.exists())

    def test_skip_installed_verification_cannot_install_or_reverify(self):
        for action in ("--install", "--verify-only"):
            with self.subTest(action=action), patch.object(
                    build, "Pipeline", side_effect=AssertionError("Must reject before pipeline construction")):
                with self.assertRaisesRegex(SystemExit, "cannot be combined"):
                    build.main(["--skip-installed-verify", action, "--out", str(self.out)])
                self.assertFalse(self.out.exists())


if __name__ == "__main__":
    unittest.main()
