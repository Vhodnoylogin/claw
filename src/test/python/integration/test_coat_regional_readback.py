"""Synthetic discrimination controls for the regional coat scenes."""

import json
from pathlib import Path
import unittest

from coat_regional_palette import load_palette
from coat_regional_readback import (
    compare_pairs, expected_paths, inspect_discrete_regions, inspect_regions, verify_human, verify_random_combos,
    verify_skin_only,
)
from coat_regional_scene import RANDOM_PALETTE, SKIN_PALETTE, rgb_key


TEST_SOURCE = Path(__file__).resolve().parents[2]
APPEARANCE = TEST_SOURCE.parent / 'main/resources/appearance'
with (TEST_SOURCE / 'resources/inspection/regional-coats/pairs.json').open(encoding='utf-8') as file:
    FIXTURE = json.load(file)

BLENDS = {'chestblend', 'furfaceblend', 'scalpfurblend'}
BODY_TINT = ([159, 156, 151], [179, 179, 179])
HAIR_TINT = ([68, 68, 70], [102, 100, 89])


def audit(surfaces, *, wolf):
    return {'schema': 1, 'ageMs': 30, 'sample': '13', 'modelGeneration': '9',
            'stringEncoding': 'bytes-u00xx', 'leaseRootCurrent': wolf, 'surfaces': surfaces}


def human(pair):
    return audit([{'feature': 6, 'tint': [component * 2 / 255 for component in pair['hair']]},
                  {'feature': 5, 'tint': [component / 255 for component in pair['skinRecordRGB8']]}], wolf=False)


def wolf(paths, index):
    body, hair = BODY_TINT[index % 2], HAIR_TINT[index // 2]
    alpha = (.871139, .90194863)[index // 2]
    return audit([
        {'name': name, 'geometryId': str(ordinal), 'feature': 5, 'managed': True, 'healthyLease': True,
         'ownDiffuse': True, 'diffusePath': path, 'diffuseResource': path,
         'tint': [component / 255 for component in (body if name == 'body' else hair)],
         'materialAlpha': alpha if name in BLENDS else 1.}
        for ordinal, (name, path) in enumerate(paths.items(), 1)
    ], wolf=True)


class RegionalCoatReadbackTests(unittest.TestCase):
    def setUp(self):
        self.pairs = FIXTURE['pairs']
        self.paths = expected_paths(APPEARANCE, FIXTURE['fixedCoat'])

    def measurements(self):
        return [inspect_regions(wolf(self.paths, index), pair, self.paths)
                for index, pair in enumerate(self.pairs)]

    def test_catalog_resolves_twelve_surface_paths_for_the_same_donor(self):
        self.assertEqual(len(self.paths), 12)
        self.assertEqual(self.paths['body'], 'textures/DiverseElegantWerewolves/ValleyGrey/body.dds')
        self.assertEqual(self.paths['fur_back'], self.paths['scalpfurblend'])
        with self.assertRaisesRegex(ValueError, 'canonical coat range'):
            expected_paths(APPEARANCE, 'elegant-2k-2.1/maned')

    def test_skin_coat_groups_hold_texture_constant_when_hair_changes(self):
        coats = FIXTURE['skinCoats']
        groups = [[pair for pair in self.pairs if rgb_key(pair['skinRecordRGB8']) == skin] for skin in coats]
        self.assertEqual([len(group) for group in groups], [2, 2])
        for group in groups:
            self.assertNotEqual(group[0]['hair'], group[1]['hair'])
        body_paths = {expected_paths(APPEARANCE, coat)['body'] for coat in coats.values()}
        self.assertEqual(len(body_paths), 2)

    def test_discrete_audit_requires_hair_paths_on_head_and_fur(self):
        hair = expected_paths(APPEARANCE, FIXTURE['hairCoats']['20,20,24'])
        sample = wolf(dict(hair, body=self.paths['body']), 0)
        for surface in sample['surfaces']:
            surface.update(feature=0, tint=None)
        inspect_discrete_regions(sample, self.pairs[0], self.paths, hair)
        wrong = next(surface for surface in sample['surfaces'] if surface['name'] == 'head')
        wrong.update(diffusePath=self.paths['head'], diffuseResource=self.paths['head'])
        with self.assertRaises(ValueError):
            inspect_discrete_regions(sample, self.pairs[0], self.paths, hair)

    def test_palette_and_four_pair_measurements_pass(self):
        for pair in self.pairs:
            self.assertEqual(verify_human(human(pair), pair),
                             {'hairRGB8': pair['hair'], 'skinRGB8': pair['skinRecordRGB8']})
        report = compare_pairs(self.measurements(), self.pairs)
        self.assertEqual(report['alphaRowsThatChanged'], sorted(BLENDS))
        self.assertEqual(report['alphaBySurface']['body'], [1.] * 4)

    def test_skin_sweep_requires_constant_hair_and_matching_twins(self):
        pairs = json.loads(SKIN_PALETTE.read_bytes())['pairs']
        rows = [(verify_human(human(pair), pair), verify_human(human(pair), pair)) for pair in pairs]
        report = verify_skin_only(rows)
        self.assertEqual(report['hairRGB8'], [20, 20, 24])
        self.assertEqual(report['skinRGB8'], [pair['skinRecordRGB8'] for pair in pairs])
        with self.assertRaises(ValueError):
            verify_skin_only(rows[::-1])
        with self.assertRaises(ValueError):
            verify_skin_only([*rows[:4], (rows[4][0], rows[3][1])])
        changed_hair = dict(rows[4][0], hairRGB8=[81, 77, 57])
        with self.assertRaises(ValueError):
            verify_skin_only([*rows[:4], (changed_hair, changed_hair)])

    def test_human_palette_requires_actual_hair_and_skin(self):
        for index, color in enumerate(('hair', 'skin')):
            with self.subTest(color=color):
                sample = human(self.pairs[0])
                sample['surfaces'][index]['tint'] = [0., 0., 0.]
                with self.assertRaisesRegex(ValueError, color + ' tint differs'):
                    verify_human(sample, self.pairs[0])

    def test_seeded_palette_replays_and_keeps_a_same_skin_comparison(self):
        default = load_palette(RANDOM_PALETTE)
        self.assertEqual(default, load_palette(RANDOM_PALETTE, default['selectionSeed']))
        self.assertNotEqual(default['pairs'], load_palette(RANDOM_PALETTE, 41)['pairs'])
        self.assertEqual([row['base'] for row in default['pairs']],
                         ['0x00013602', '0x00013356', '0x00013397', '0x00013BAB', '0x00013282'])
        left, right = default['pairs'][0], default['pairs'][3]
        self.assertEqual(left['skinRecordRGB8'], right['skinRecordRGB8'])
        self.assertNotEqual(left['hair'], right['hair'])

    def test_seeded_audit_requires_variation_and_matching_twins(self):
        palette = load_palette(RANDOM_PALETTE)
        rows = [(verify_human(human(pair), pair), verify_human(human(pair), pair)) for pair in palette['pairs']]
        self.assertEqual(verify_random_combos(rows, palette['selectionSeed'])['pairs'], [row[0] for row in rows])
        with self.assertRaisesRegex(ValueError, 'identical input'):
            verify_random_combos([*rows[:4], (rows[4][0], rows[0][1])], 808)
        duplicate = dict(rows[4][0], hairRGB8=rows[0][0]['hairRGB8'])
        with self.assertRaisesRegex(ValueError, 'five hair colours'):
            verify_random_combos([*rows[:4], (duplicate, duplicate)], 808)

    def test_requires_fresh_owned_donor_on_all_surfaces(self):
        for field, value, reason in (('diffuseResource', 'textures/other.dds', 'fixed donor'),
                                     ('ownDiffuse', False, 'unhealthy'),
                                     ('tint', [0., 0., 0.], 'regional tint differs'),
                                     ('materialAlpha', float('nan'), 'alpha unavailable')):
            with self.subTest(field=field):
                sample = wolf(self.paths, 0)
                sample['surfaces'][0][field] = value
                with self.assertRaisesRegex(ValueError, reason):
                    inspect_regions(sample, self.pairs[0], self.paths)
        sample = wolf(self.paths, 0)
        sample['leaseRootCurrent'] = False
        with self.assertRaisesRegex(ValueError, 'Fresh'):
            inspect_regions(sample, self.pairs[0], self.paths)

    def test_alpha_must_follow_hair_only_on_blends(self):
        for indices, surface, value, reason in (
                ((1,), 'chestblend', .9, 'skin-only'),
                ((2, 3), 'body', .97, 'only on'),
                ((0, 1), 'chestblend', .75, 'fitted donor')):
            with self.subTest(surface=surface, value=value):
                groups = self.measurements()
                for index in indices:
                    groups[index][surface]['materialAlpha'] = value
                with self.assertRaisesRegex(ValueError, reason):
                    compare_pairs(groups, self.pairs)


if __name__ == '__main__':
    unittest.main()
