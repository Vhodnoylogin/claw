"""Check standalone preset archives through their actual installed paths and bytes."""
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'src/main/python/build-tools'))
spec = importlib.util.spec_from_file_location("preset_package", ROOT / 'src/main/python/build-tools/package-presets.py')
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)
XML = b'<SliderPresets><Preset name="Author - Wolf" set="CLAW Male"/></SliderPresets>'


class PresetPackage(unittest.TestCase):
    def test_installable_deterministic_archive_preserves_xml_and_excludes_other_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Author").mkdir()
            (root / "Author/wolf.xml").write_bytes(XML)
            (root / "test.esp").write_bytes(b"fixture")
            archive, receipt = packager.package(root)
            self.assertEqual(archive, packager.package(root)[0])
            with zipfile.ZipFile(io.BytesIO(archive)) as result:
                self.assertIsNone(result.testzip())
                self.assertEqual(result.namelist(), [packager.PREFIX + "Author/wolf.xml"])
                self.assertEqual(result.read(result.namelist()[0]), XML)
            self.assertEqual(receipt["presetCount"], 1)

    def test_duplicates_or_invalid_typed_presets_leave_no_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.xml").write_bytes(XML)
            (root / "b.xml").write_bytes(XML)
            with self.assertRaises(ValueError):
                packager.package(root)
            (root / "b.xml").write_bytes(XML.replace(b"CLAW Male", b"HIMBO"))
            with self.assertRaises(ValueError):
                packager.package(root)
            self.assertEqual(packager.main([str(root), "--out", str(root / "bad.zip")]), 2)
            self.assertFalse((root / "bad.zip").exists())

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "wolf.xml").write_bytes(XML)
            (root / "owner.zip").write_bytes(b"owner")
            self.assertEqual(packager.main([str(root / "wolf.xml"), "--out", str(root / "owner.zip")]), 2)
            self.assertEqual((root / "owner.zip").read_bytes(), b"owner")

    def test_windows_device_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # A directory can be emulated in the path check without creating a Windows device.
            from unittest.mock import patch
            fake = root / "CON.xml"
            with patch.object(Path, "is_file", return_value=True), patch.object(Path, "exists", return_value=True):
                with self.assertRaisesRegex(ValueError, "Windows"):
                    packager.package(fake)


if __name__ == "__main__":
    unittest.main()
