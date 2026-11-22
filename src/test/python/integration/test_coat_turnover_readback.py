"""Synthetic ownership controls using the shipped coat's expected paths."""

from copy import deepcopy
import unittest

from coat_turnover_readback import verify_same_root_turnover
from test_coat_persistence_readback import retained_case


FOREIGN = 'textures/actors/wolf/wolfblack.dds'


def managed(observations, phase, name):
    return next(row for row in observations[phase]['audit']['surfaces'] if row['name'] == name)


def case():
    (_, _, baseline, _), options = retained_case()
    for identity, row in enumerate(baseline['audit']['surfaces'], 1):
        row['geometryId'] = str(identity)
    baseline['audit']['surfaces'].append({'name': 'eyes', 'managed': False, 'geometryId': '13'})
    foreign = deepcopy(baseline)
    foreign['appliedPattern'] = ''
    foreign['audit'].update(sample='104')
    del foreign['audit']['coatDecision']
    for row in foreign['audit']['surfaces']:
        row.update(healthyLease=False, ownDiffuse=False)
        if row['name'] == 'body':
            row.update(diffusePath='Data\\Textures\\Actors\\Wolf\\WolfBLACK.dds', diffuseResource=FOREIGN)
    sibling = deepcopy(foreign)
    sibling['audit']['sample'] = '105'
    recovered = deepcopy(baseline)
    recovered['audit']['sample'] = '106'
    observations = dict(baseline=baseline, foreign=foreign, sibling=sibling, recovered=recovered)
    managed(observations, 'sibling', 'head')['geometryId'] = '14'
    managed(observations, 'recovered', 'head')['geometryId'] = '14'
    managed(observations, 'recovered', 'body')['geometryId'] = '15'
    return observations, dict(pattern=options['pattern'], expected_paths=options['expected_paths'], foreign_body_path=FOREIGN)


class CoatTurnoverReadbackTests(unittest.TestCase):
    def test_proves_both_exact_replacements_under_the_retained_root(self):
        observations, options = case()
        result = verify_same_root_turnover(observations, **options)
        self.assertEqual(result, {'pattern': options['pattern'], 'variation': .5733334,
                                  'worldGeneration': 3, 'modelGeneration': '3', 'managedSurfaces': 12,
                                  'replacedGeometry': {'head': '14', 'body': '15'}})

    def test_replayed_stale_or_different_root_audits_are_rejected(self):
        for field, value, reason in (('sample', '104', 'replayed'), ('ageMs', 2001, 'Fresh'),
                                     ('modelGeneration', '4', 'root changed'), ('leaseRootCurrent', False, 'Fresh')):
            with self.subTest(field=field):
                observations, options = case()
                observations['sibling']['audit'][field] = value
                with self.assertRaisesRegex(ValueError, reason):
                    verify_same_root_turnover(observations, **options)

    def test_all_samples_require_the_same_actor_process_world_and_run(self):
        for field, value in (('reference', '0xFF000862'), ('runtimeHandle', 19),
                             ('pid', 7893), ('worldGeneration', 4), ('runId', 'other-fixture-run')):
            with self.subTest(field=field):
                observations, options = case()
                observations['recovered'][field] = value
                with self.assertRaisesRegex(ValueError, 'another actor or world'):
                    verify_same_root_turnover(observations, **options)

    def test_missing_duplicate_and_reused_geometry_cannot_prove_replacement(self):
        for phase, role, value, reason in (('foreign', 'body', '16', 'material change replaced'),
                                          ('sibling', 'body', '16', 'only HEAD'),
                                          ('sibling', 'head', '1', 'Duplicate'),
                                          ('sibling', 'head', None, 'geometry identity'),
                                          ('recovered', 'body', '1', 'only BODY'),
                                          ('recovered', 'head', '16', 'only BODY')):
            with self.subTest(phase=phase, role=role, value=value):
                observations, options = case()
                managed(observations, phase, role)['geometryId'] = value
                with self.assertRaisesRegex(ValueError, reason):
                    verify_same_root_turnover(observations, **options)
        observations, options = case()
        observations['sibling']['audit']['surfaces'].remove(managed(observations, 'sibling', 'head'))
        with self.assertRaisesRegex(ValueError, 'all twelve'):
            verify_same_root_turnover(observations, **options)

    def test_renamed_or_reattached_old_geometry_is_still_detected(self):
        for phase, role, reason in (('sibling', 'head', 'detach the old'),
                                    ('recovered', 'body', 'superseded geometry detached'),
                                    ('recovered', 'head', 'superseded geometry detached')):
            with self.subTest(phase=phase, role=role):
                observations, options = case()
                old = managed(observations, 'foreign', role)['geometryId']
                observations[phase]['audit']['surfaces'].append({'name': 'renamed', 'managed': False, 'geometryId': old})
                with self.assertRaisesRegex(ValueError, reason):
                    verify_same_root_turnover(observations, **options)
        observations, options = case()
        observations['baseline']['audit']['surfaces'].append({'name': 'extra', 'managed': False, 'geometryId': '13'})
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            verify_same_root_turnover(observations, **options)

    def test_actual_diffuse_paths_and_no_intermediate_lease_are_required(self):
        for phase, field, value, reason in (('foreign', 'diffusePath', 'textures/not-foreign.dds', 'foreign BODY'),
                                            ('sibling', 'diffuseResource', 'textures/not-foreign.dds', 'foreign BODY'),
                                            ('sibling', 'healthyLease', True, 'retained a private'),
                                            ('recovered', 'diffuseResource', FOREIGN, 'bound resource')):
            with self.subTest(phase=phase, field=field):
                observations, options = case()
                managed(observations, phase, 'body')[field] = value
                with self.assertRaisesRegex(ValueError, reason):
                    verify_same_root_turnover(observations, **options)

    def test_missing_or_changed_automatic_decision_does_not_qualify(self):
        observations, options = case()
        observations['baseline']['manualOverride'] = options['pattern']
        with self.assertRaisesRegex(ValueError, 'Manual coat'):
            verify_same_root_turnover(observations, **options)
        observations, options = case()
        del observations['recovered']['audit']['coatDecision']
        with self.assertRaisesRegex(ValueError, 'Missing actual automatic'):
            verify_same_root_turnover(observations, **options)
        observations, options = case()
        observations['recovered']['audit']['coatDecision']['variation'] = .57
        with self.assertRaisesRegex(ValueError, 'variation changed'):
            verify_same_root_turnover(observations, **options)


if __name__ == '__main__':
    unittest.main()
