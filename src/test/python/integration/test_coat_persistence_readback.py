import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from coat_persistence_readback import verify_automatic_roundtrip


ROOT = Path(__file__).resolve().parents[4]
APPEARANCE = ROOT / 'src/main/resources/appearance'
PATTERN = 'elegant-2k-2.1/valley-brown'


def retained_case():
    library = ET.parse(APPEARANCE / 'CoatLibrary.xml').getroot()
    textures = {entry.attrib['name']: entry.attrib['path'] for entry in library.findall("./Patterns/Pattern[@id='valley-brown']/Texture")}
    paths = {row.attrib['name'].casefold(): textures[row.attrib['texture']] for row in library.findall('./Surfaces/Surface')}
    context = {'schemaVersion': 1, 'protocol': 'npc-persistence/1', 'runId': 'fixture-run', 'providerSession': 'nonce',
               'saveTag': 'coat', 'bindingId': 'save-binding', 'pid': 7892, 'saveOrdinal': 1}
    source = {'tag': 'FControlWolf', 'base': '0x000A2C91', 'creationId': 'a' * 32, 'persistent': True,
              'savedReference': '0xFF000861', 'savedVmHandle': '4294901785'}
    previous = {**source, 'currentReference': '0xFF000861', 'currentVmHandle': source['savedVmHandle'], 'runtimeHandle': 9}
    restored = {**source, 'currentReference': '0xFF000970', 'resolvedReference': '0xFF000970',
                'currentVmHandle': '4294901800', 'resolvedVmHandle': '4294901800',
                'runtimeHandle': 14, 'formResolved': True, 'handleResolved': True}
    witness = {'tag': 'FControlHuman'}
    pair = {'completed': True, 'ownedByAttempt': True, 'saveTag': 'coat', 'bindingId': context['bindingId'],
            'stem': 'Autotest_fixture_run_coat', 'essSha256': 'b' * 64, 'skseSha256': 'c' * 64}
    saved = {'nativePersistenceReceipt': {**context, 'phase': 'saved', 'loadOrdinal': 0, 'actors': [previous, witness]},
             'save': pair}
    loaded = {'nativePersistenceReceipt': {**context, 'phase': 'loaded', 'loadOrdinal': 1, 'actors': [restored, witness]},
              'save': dict(pair), 'load': {'completed': True, 'sameProcess': True, 'worldGeneration': 4,
                                           'saveTag': 'coat', 'actorWitnessCount': 2},
              'lifecycle': {'worldReady': True, 'pidChanged': False, 'generationChanged': True, 'worldGeneration': 4}}

    def observation(actor, generation):
        rows = [{'name': name, 'managed': True, 'healthyLease': True, 'ownDiffuse': True,
                 'diffusePath': path.replace('/', '\\'), 'diffuseResource': path, 'feature': 0, 'tint': None}
                for name, path in paths.items()]
        audit = {'schema': 1, 'stringEncoding': 'bytes-u00xx', 'leaseRootCurrent': True, 'ageMs': 30,
                 'sample': str(100 + generation), 'modelGeneration': str(generation), 'surfaces': rows,
                 'coatDecision': {'pattern': PATTERN, 'variation': .5733334}}
        return {'runId': context['runId'], 'pid': context['pid'], 'reference': actor['currentReference'],
                'runtimeHandle': actor['runtimeHandle'], 'worldGeneration': generation,
                'manualOverride': '', 'appliedPattern': PATTERN, 'audit': audit}

    options = {'tag': 'FControlWolf', 'pattern': PATTERN, 'expected_paths': paths,
               'skin_aware': .57333338, 'seed_only': .50000003}
    return (saved, loaded, observation(previous, 3), observation(restored, 4)), options


class CoatPersistenceReadbackTests(unittest.TestCase):
    def test_automatic_pattern_survives_reference_remap(self):
        evidence, options = retained_case()
        result = verify_automatic_roundtrip(*evidence, **options)
        self.assertEqual(result, {'pattern': PATTERN, 'variation': .5733334, 'distinguishesSkinTerm': True,
                                  'worldGeneration': 4, 'managedSurfaces': 12})

    def test_valid_save_does_not_substitute_for_actual_loaded_coat(self):
        for field, value, reason in (
                ('manualOverride', PATTERN, 'automatic selection'),
                ('worldGeneration', 3, 'another fixture or world'),
                ('reference', '0xFF000861', 'another fixture or world')):
            with self.subTest(field=field):
                evidence, options = retained_case()
                evidence[3][field] = value
                with self.assertRaisesRegex(ValueError, reason):
                    verify_automatic_roundtrip(*evidence, **options)
        evidence, options = retained_case()
        evidence[3]['audit']['surfaces'][0]['diffuseResource'] = 'textures/actors/wolf/wolfblack.dds'
        with self.assertRaisesRegex(ValueError, 'bound resource'):
            verify_automatic_roundtrip(*evidence, **options)

    def test_wrong_save_and_replayed_effective_material_are_rejected(self):
        evidence, options = retained_case()
        evidence[1]['save']['skseSha256'] = 'd' * 64
        with self.assertRaisesRegex(ValueError, 'identical attempt-owned'):
            verify_automatic_roundtrip(*evidence, **options)
        evidence, options = retained_case()
        evidence[3]['audit'] = evidence[2]['audit']
        with self.assertRaisesRegex(ValueError, 'was reused'):
            verify_automatic_roundtrip(*evidence, **options)

    def test_fixture_describes_the_current_canonical_mapping(self):
        fixture = json.loads((ROOT / 'src/test/resources/inspection/coats/scenario.json').read_bytes())
        mapping = ET.parse(APPEARANCE / 'CoatMapping.xml').getroot()
        contract = fixture['coatContract']
        canonical = {entry.attrib['id'] for entry in mapping.findall('Range')}
        aliases = {entry.attrib['id'] for entry in mapping.findall('Alias')}
        variants = [entry.attrib['id'] for entry in mapping.findall('Group/Variant')]
        self.assertEqual(str(contract['mappingSchemaVersion']), mapping.attrib['schemaVersion'])
        self.assertEqual(len(canonical), contract['catalogueSize'])
        self.assertEqual(len(canonical), contract['fallbackMembers'])
        self.assertEqual(len(mapping.findall('Group')), contract['hairPoolCount'])
        self.assertEqual(len(variants), len(canonical))
        self.assertEqual(set(variants), canonical)
        self.assertTrue(canonical.isdisjoint(aliases))
        self.assertTrue(set(contract['manualPatterns']) <= canonical)
        self.assertNotIn(contract['automaticHairSaveActor'], contract['manualSaveActors'])


if __name__ == '__main__':
    unittest.main()
