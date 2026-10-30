import copy
import importlib.util
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('claw_test_fixture_package', ROOT/'scripts/build-test-fixture-package.py')
package = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package)


class TestFixturePackageTests(unittest.TestCase):
    def test_actual_repository_plugin_is_six_unplaced_wolves_of_both_sexes(self):
        info = package.fixture_records((ROOT/'tests/assets/plugins'/package.PLUGIN).read_bytes())
        self.assertEqual(info['masters'], ['Skyrim.esm'])
        self.assertEqual(len(info['npcBases']), 6)
        self.assertEqual(info['placedReferences'], 0)
        self.assertEqual([row['sex'] for row in info['npcBases']], ['male']*3+['female']*3)

    def test_plugin_rejects_truncation_and_unexpected_record(self):
        raw = (ROOT/'tests/assets/plugins'/package.PLUGIN).read_bytes()
        with self.assertRaises(ValueError):
            package.fixture_records(raw[:-1])
        raw += struct.pack('<4s5I', b'QUST', 0, 0, 0x1000900, 0, 0)
        with self.assertRaises(ValueError):
            package.fixture_records(raw)

    def test_actual_six_human_presets_have_equal_endpoints_and_exact_families(self):
        raw = (ROOT/'tests/fixtures/CLAW-Human-Contrast.xml').read_bytes()
        rows = package.preset_records(raw)
        self.assertEqual([row['sliderCountPerEndpoint'] for row in rows], [124]*3+[154]*3)
        self.assertEqual(len({row['vectorSha256'] for row in rows}), 6)
        with self.assertRaises(ValueError):
            package.preset_records(raw.replace(b'value="-20"', b'value="-21"', 1))
        with self.assertRaises(ValueError):
            package.preset_records(raw.replace(b'set="HIMBO"', b'set="CLAW Male"', 1))

    def test_historical_equality_drops_all_instance_references_and_rejects_difference(self):
        source = {'sourceComparisonPassed': True, 'pairs': [
            {'type': name, 'passed': True, 'errors': [], 'sourceCount': 61 if index < 3 else 52,
             'sourceAggregateDifferences': 0, 'sourceKeyDifferences': 0, 'rawWeightDifference': 0,
             'humanReference': '0xFF123456', 'statePath': 'D:/private/state.json'}
            for index, name in enumerate(package.PAIR_TYPES)]}
        result = package.historic_pairs(json.dumps(source))
        self.assertTrue(result['allSixSourceVectorsEqual'])
        self.assertNotIn('FF123456', json.dumps(result))
        self.assertNotIn('private', json.dumps(result))
        source['pairs'][0]['sourceKeyDifferences'] = 1
        with self.assertRaises(ValueError):
            package.historic_pairs(json.dumps(source))

    def test_working_archive_checks_every_selection_and_rejects_collision_or_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'working.zip'
            def write(destination='CLAW.esp', expected=None):
                data = b'production'
                manifest = {'selections': [{'selection': 'base-only', 'installedFiles': [
                    {'path': destination, 'archivePath': '00 Base/CLAW.esp', 'bytes': len(data),
                     'sha256': expected or package.sha(data)}]}]}
                with zipfile.ZipFile(path, 'w') as writer:
                    writer.writestr('00 Base/CLAW.esp', data)
                    writer.writestr('claw-unified-release.json', json.dumps(manifest))
            write()
            self.assertEqual(len(package.working_collisions(package.Inputs(), path, package.PAYLOAD)['selections']), 1)
            write(package.PLUGIN.upper())
            with self.assertRaises(ValueError):
                package.working_collisions(package.Inputs(), path, package.PAYLOAD)
            write(expected='0'*64)
            with self.assertRaises(ValueError):
                package.working_collisions(package.Inputs(), path, package.PAYLOAD)

    def test_fresh_external_destination_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in (root, ROOT/'new-test-output', root/'mods/new', root/'profiles/new', root/'Data/new'):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    package.safe_output(path)
            self.assertEqual(package.safe_output(root/'new'), (root/'new').resolve())
            (root/'.git').mkdir()
            with self.assertRaises(ValueError):
                package.safe_output(root/'new')


if __name__ == '__main__':
    unittest.main()
