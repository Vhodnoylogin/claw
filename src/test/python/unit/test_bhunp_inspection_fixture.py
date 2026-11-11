import json
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
FIXTURE = ROOT/'src/test/resources/inspection/bhunp'


class BHUNPInspectionFixtureTests(unittest.TestCase):
    def test_presets_cover_actual_matrix_sources_and_both_endpoint_morphs(self):
        catalog = ET.parse(ROOT/'src/main/resources/profiles/MorphLinks.xml').getroot()
        profile = next(p for p in catalog.findall('Profile') if p.get('family') == 'BHUNP')
        keys = {r.get('source') for r in profile.findall('Rule')
                if r.get('source') and not r.get('source').startswith('$')}
        self.assertEqual(len(keys), 62)
        presets = ET.parse(FIXTURE/'CLAW-BHUNP-Technical.xml').getroot().findall('Preset')
        self.assertEqual(len(presets), 3)
        for preset in presets:
            self.assertEqual(preset.get('set'), 'BHUNP 3BBB Advanced Ver2 Nevernude')
            endpoints = {}
            for slider in preset.findall('SetSlider'):
                identity = (slider.get('name'), slider.get('size'))
                self.assertNotIn(identity, endpoints)
                endpoints[identity] = float(slider.get('value'))
            self.assertEqual(set(endpoints), {(key, size) for key in keys for size in ('small', 'big')})
            self.assertTrue(all(-100 <= value <= 100 for value in endpoints.values()))
            for suffix in (' Low', ' High'):
                self.assertTrue(any(key.endswith(suffix) and value != 0
                                    for (key, _), value in endpoints.items()))

    def test_six_owned_actors_match_complete_twelve_base_distribution(self):
        case = json.loads((FIXTURE/'scenario.json').read_bytes())
        config = json.loads((FIXTURE/'OBody_presetDistributionConfig.json').read_bytes())
        self.assertEqual(len(case['actors']), 6)
        self.assertEqual(len({a['tag'] for a in case['actors']}), 6)
        self.assertEqual(case['maximumCreations'], 6)
        self.assertEqual(case['maximumFixtures'], 12)
        self.assertEqual(case['ownedSaveParticipants'], 6)
        self.assertEqual(sum(len(rows) for rows in config['npcFormID'].values()), 12)
        female_names = {p.get('name') for p in ET.parse(FIXTURE/'CLAW-BHUNP-Technical.xml').getroot()}
        for actor in case['actors']:
            self.assertEqual(actor['initialForm'], 'human')
            base = actor['initialNpcBase']
            self.assertEqual(config['npcFormID'][base['plugin']][base['localFormId'].zfill(8)],
                             [actor['humanPreset']])
            if actor['sex'] == 'female':
                self.assertIn(actor['humanPreset'], female_names)
        self.assertEqual(set(config['raceFemale']['WerewolfBeastRace']), female_names)
        self.assertEqual(case['beforeAnyFixtureCreation']['globalAIEnabled'], False)
        self.assertEqual(case['beforeAnyFixtureCreation']['globalCollisionEnabled'], False)

    def test_fixture_is_portable_source_without_session_references(self):
        for path in FIXTURE.iterdir():
            self.assertIn(path.suffix, ('.md', '.xml', '.json'))
            text = path.read_text(encoding='utf-8-sig')
            self.assertIsNone(re.search(r'(?<![A-Za-z0-9])[A-Za-z]:[\\/]', text))
            self.assertIsNone(re.search(r'0xFF[0-9A-Fa-f]{6}', text))
        case = json.loads((FIXTURE/'scenario.json').read_bytes())
        self.assertFalse(case['automaticSpawn'])
        self.assertTrue(case['freshReferencesRequired'])


if __name__ == '__main__':
    unittest.main()
