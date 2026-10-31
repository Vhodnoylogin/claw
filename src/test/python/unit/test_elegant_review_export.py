"""Source-only author-review export identity and refusal contracts; no donor/API."""
import ast
import hashlib
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[4]
TOOLS = ROOT/'src/main/python/build-tools'
SPEC = importlib.util.spec_from_file_location('claw_review_export', TOOLS/'export-elegant-review.py')
exporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exporter)


class ElegantReviewExportTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT/'target/test-elegant-review-export'
        parent.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)

    def test_export_is_exact_published_standalone_and_refuses_overwrite(self):
        output = self.folder/'elegant_head_body_split.py'
        exporter.export(output)
        original = output.read_bytes()
        self.assertEqual(hashlib.sha256(original).hexdigest(), exporter.REVIEW_SHA256)
        ast.parse(original.decode('utf-8'))
        with self.assertRaisesRegex(ValueError, 'new output file'):
            exporter.export(output)
        self.assertEqual(output.read_bytes(), original)

    def test_source_drift_cannot_claim_the_existing_review_identity(self):
        for name in ('breast_rig.py', 'vr_head.py', 'head_split.py'):
            shutil.copyfile(TOOLS/name, self.folder/name)
        source = self.folder/'breast_rig.py'
        text = source.read_text(encoding='utf-8')
        self.assertIn('def rotation(axis,degrees):', text)
        source.write_text(text.replace('def rotation(axis,degrees):', 'def rotation(axis,degrees=1):', 1), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'differs from the published review'):
            exporter.render(self.folder)

    def test_generated_tool_cannot_be_written_into_tracked_source(self):
        output = ROOT/'src/main/python/build-tools/SHOULD_NOT_EXIST_REVIEW.py'
        self.assertFalse(output.exists())
        with self.assertRaisesRegex(ValueError, 'target/'):
            exporter.export(output)
        self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
