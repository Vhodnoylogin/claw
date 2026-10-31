import copy
import importlib.util
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location('claw_test_fixture_package', ROOT/'src/main/python/build-tools/build-test-fixture-package.py')
package = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package)


class CompiledWildFixtureIntegrationTests(unittest.TestCase):
    def test_actual_repository_plugin_is_six_unplaced_wolves_of_both_sexes(self):
        info = package.fixture_records((ROOT/'target/test-assets/plugins'/package.PLUGIN).read_bytes())
        self.assertEqual(info['masters'], ['Skyrim.esm'])
        self.assertEqual(len(info['npcBases']), 6)
        self.assertEqual(info['placedReferences'], 0)
        self.assertEqual([row['sex'] for row in info['npcBases']], ['male']*3+['female']*3)

    def test_plugin_rejects_truncation_and_unexpected_record(self):
        raw = (ROOT/'target/test-assets/plugins'/package.PLUGIN).read_bytes()
        with self.assertRaises(ValueError):
            package.fixture_records(raw[:-1])
        raw += struct.pack('<4s5I', b'QUST', 0, 0, 0x1000900, 0, 0)
        with self.assertRaises(ValueError):
            package.fixture_records(raw)


if __name__ == "__main__":
    unittest.main()
