"""Synthetic discrimination controls for the fixed-donor four-pair scene."""

import json
from pathlib import Path
import unittest

from coat_regional_readback import compare_pairs, expected_paths, inspect_regions, verify_human


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

    def test_palette_and_four_pair_measurements_pass(self):
        for pair in self.pairs:
            self.assertEqual(verify_human(human(pair), pair),
                             {'hairRGB8': pair['hair'], 'skinRGB8': pair['skinRecordRGB8']})
        report = compare_pairs(self.measurements(), self.pairs)
        self.assertEqual(report['alphaRowsThatChanged'], sorted(BLENDS))
        self.assertEqual(report['alphaBySurface']['body'], [1.] * 4)

    def test_human_palette_requires_actual_hair_and_skin(self):
        for index, color in enumerate(('hair', 'skin')):
            with self.subTest(color=color):
                sample = human(self.pairs[0])
                sample['surfaces'][index]['tint'] = [0., 0., 0.]
                with self.assertRaisesRegex(ValueError, color + ' tint differs'):
                    verify_human(sample, self.pairs[0])

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
