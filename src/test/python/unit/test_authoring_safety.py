"""Guards for the offline tool-copy/build destination, independent of BodySlide."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location("claw_authoring_safety", ROOT / 'src/main/python/build-tools/build-authoring.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class AuthoringSafety(unittest.TestCase):
    def test_existing_and_source_destinations_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "original-tool"
            source.mkdir()
            sentinel = source / "Config.xml"
            sentinel.write_bytes(b"owner configuration")
            for destination in (source, source / "nested-copy"):
                with self.subTest(destination=destination), self.assertRaises(ValueError):
                    builder.new_staging(destination, [source])
            self.assertEqual(sentinel.read_bytes(), b"owner configuration")
            self.assertFalse((source / "nested-copy").exists())

    def test_live_and_other_checkout_paths_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for component in ("Data", "mods", "overwrite", "downloads"):
                with self.subTest(component=component), self.assertRaises(ValueError):
                    builder.new_staging(root / component / "new-run", [])
            foreign = root / "foreign-checkout"
            (foreign / ".git").mkdir(parents=True)
            with self.assertRaises(ValueError):
                builder.new_staging(foreign / "generated", [])

    def test_new_external_staging_is_created_without_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "new-run"
            self.assertEqual(builder.new_staging(target, []), target.resolve())
            (target / "retained.txt").write_bytes(b"evidence")
            with self.assertRaises(ValueError):
                builder.new_staging(target, [])
            self.assertEqual((target / "retained.txt").read_bytes(), b"evidence")


if __name__ == "__main__":
    unittest.main()
