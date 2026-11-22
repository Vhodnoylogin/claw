import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from verify_dispatch_markers import (ADDON, BODY, ITEM, ROUTES, SCHEMA, SCHEMA_V5, SCHEMA_V6, SCHEMA_TOKENS,
                                     TOKENS, verify_dispatch_markers)

FIXTURE = (0x0B000801, 0x0B000800)


def capture(schema=SCHEMA_V5):
    sample = {'actor': 0x14, 'race': 0xCDD84, 'base': 7, 'cell': 0x1234, 'runtimeHandle': 80,
              'sex': 0, 'weight': 37.0, 'qpcBegin': 1200, 'qpcEnd': 1260, 'qpcFrequency': 10000000,
              'roots': {'default': 1, 'thirdPerson': 1, 'firstPerson': 2},
              'views': {view: {'available': True} for view, _ in ROUTES},
              'distinctRoots': [{'id': alias} for alias in range(1, 7)], 'body32Markers': []}
    if schema == SCHEMA:
        sample['playerBody32Fixture'] = None
    for index, (view, bank) in enumerate(ROUTES):
        sample['views'][view][bank] = [dict(slot=BODY, clone=index + 3, item=ITEM, addon=ADDON,
                                           modelPath=r'Actors\Character\misleading-selection.nif', partHandlePresent=True)]
        sample['body32Markers'].append(dict(view=view, bank=bank, slot=BODY, clone=index + 3,
                                            classification='unmarked', counts=[0] * len(SCHEMA_TOKENS[schema])))
    mark(sample, 2, 'M1')
    mark(sample, 3, 'M0')
    return dict(schema=schema, status='ready', pid=492, nonce=3, epoch=7, sample=sample)


def mark(sample, index, *markers, classification=None):
    row = sample['body32Markers'][index]
    row['counts'] = [markers.count(token) for token in TOKENS[:len(row['counts'])]]
    row['classification'] = classification or ('ambiguous' if len(markers) > 1 else 'marked' if markers else 'unmarked')


def verify(data, **overrides):
    return verify_dispatch_markers(data, **(dict(view='firstPerson', pid=492, nonce=3, epoch=7) | overrides))


class DispatchMarkersTests(unittest.TestCase):
    def test_marker_origin_comes_from_requested_active_clone(self):
        result = verify(capture())
        self.assertEqual(result['status'], 'origin_observed')
        self.assertEqual(result['observedMarker'], 'CLAW_VR_DISPATCH_PROBE_M1')
        self.assertTrue(result['markerFixtureModel'].endswith(r'male\Body_1.nif'))
        self.assertEqual(result['observations'][2]['clone'], 5)
        self.assertEqual(result['observations'][3]['markers'], {'M0': 1})
        self.assertTrue(result['observations'][2]['reportedModelPath'].endswith('misleading-selection.nif'))
        self.assertEqual(result['observedActorWeight'], 37)
        self.assertTrue(result['modelOriginVerified'])
        self.assertFalse(result['weightInterpolationVerified'])
        self.assertFalse(result['renderedPixelsVerified'])
        self.assertFalse(result['installedAssetWinnerVerified'])
        self.assertEqual(verify(capture(), view='thirdPerson')['status'], 'unmarked')

    def test_buffered_and_opposite_view_cannot_supply_a_missing_active_clone(self):
        data = capture()
        sample = data['sample']
        mark(sample, 0, 'M0')
        mark(sample, 2, classification='unloaded')
        sample['body32Markers'][2]['clone'] = 0
        sample['views']['firstPerson']['active'][0]['clone'] = 0
        self.assertEqual(verify(data)['status'], 'unloaded')
        self.assertEqual(verify(data, view='thirdPerson')['status'], 'origin_observed')
        sample['views']['firstPerson']['active'].clear()
        self.assertIsNone(verify(data)['observedMarker'])

    def test_foreign_detached_and_incomplete_are_distinct(self):
        data = capture()
        sample = data['sample']
        mark(sample, 2, classification='foreign_slot')
        self.assertEqual(verify(data)['status'], 'foreign_slot')  # Exact forms can have a foreign biped owner.
        mark(sample, 2, classification='detached')
        mark(sample, 3, classification='detached')
        sample['roots']['firstPerson'] = 0
        self.assertEqual(verify(data)['status'], 'detached')
        mark(sample, 2, 'M1', classification='indeterminate')
        with self.assertRaisesRegex(ValueError, 'actor root'):
            verify(data)
        sample['roots']['firstPerson'] = 2
        result = verify(data)
        self.assertEqual(result['status'], 'indeterminate')
        self.assertIsNone(result['observedMarker'])

    def test_conflicting_and_duplicate_markers_are_ambiguous(self):
        data = capture()
        for markers in (('M0', 'M1'), ('M1', 'M1'), ('M1', 'F0')):
            with self.subTest(markers=markers):
                mark(data['sample'], 2, *markers)
                self.assertEqual(verify(data)['status'], 'ambiguous')
        mark(data['sample'], 2, 'M1', 'M1', classification='marked')
        with self.assertRaisesRegex(ValueError, 'contradict'):
            verify(data)

    def test_wrong_sex_and_wrong_expected_marker_have_separate_results(self):
        data = capture()
        self.assertEqual(verify(data, expect='M0')['status'], 'unexpected_origin')
        mark(data['sample'], 2, 'F1')
        self.assertEqual(verify(data)['status'], 'wrong_sex')
        data['sample']['sex'] = 1
        self.assertEqual(verify(data, expect='F1')['status'], 'origin_observed')
        mark(data['sample'], 2, 'H_M0')
        self.assertEqual(verify(data)['status'], 'wrong_sex')
        data['sample']['sex'] = 0
        self.assertTrue(verify(data, expect='H_M0')['markerFixtureModel'].endswith('1stperson_werewolf_hands.nif'))

    def test_v6_fsmp_aliases_identify_both_sexes_and_refuse_static_carriers(self):
        for sex, motion_index, motion, static_index, static in (
            (0, 7, 'H_M_FSMP', 5, 'H_M_STATIC'),
            (1, 8, 'H_F_FSMP', 6, 'H_F_STATIC'),
        ):
            with self.subTest(sex=sex):
                data = capture(SCHEMA_V6)
                sample = data['sample']
                sample['sex'] = sex
                active, buffered = sample['body32Markers'][:2]
                active['classification'] = 'marked'
                active['counts'][motion_index] = 1
                result = verify(data, view='thirdPerson', expect=motion)
                self.assertTrue(result['modelOriginVerified'])
                self.assertEqual(result['observedMarker'], 'CLAW_VR_DISPATCH_PROBE_' + motion)
                self.assertTrue(result['markerFixtureModel'].endswith('1stperson_werewolf_hands.nif'))
                self.assertFalse(result['installedAssetWinnerVerified'])

                sample['sex'] = 1 - sex
                self.assertEqual(verify(data, view='thirdPerson', expect=motion)['status'], 'wrong_sex')
                sample['sex'] = sex
                active['counts'][motion_index] = 0
                active['counts'][static_index] = 1
                buffered['classification'] = 'marked'
                buffered['counts'][motion_index] = 1
                result = verify(data, view='thirdPerson', expect=motion)
                self.assertEqual(result['status'], 'unexpected_origin')
                self.assertEqual(result['observedMarker'], 'CLAW_VR_DISPATCH_PROBE_' + static)
                self.assertEqual(result['observations'][1]['markers'], {motion: 1})
                self.assertFalse(result['modelOriginVerified'])
                self.assertTrue(verify(data, view='thirdPerson', expect=static)['modelOriginVerified'])

    def test_legacy_male_marker_does_not_confirm_the_new_static_fixture(self):
        data = capture(SCHEMA_V6)
        mark(data['sample'], 0, 'H_M0')
        result = verify(data, view='thirdPerson', expect='H_M_STATIC')
        self.assertEqual(result['status'], 'unexpected_origin')
        self.assertFalse(result['modelOriginVerified'])

    def test_v6_mixed_static_and_fsmp_or_duplicate_fsmp_markers_are_ambiguous(self):
        data = capture(SCHEMA_V6)
        for markers in (('H_M_STATIC', 'H_M_FSMP'), ('H_M_FSMP', 'H_M_FSMP')):
            with self.subTest(markers=markers):
                mark(data['sample'], 0, *markers)
                result = verify(data, view='thirdPerson', expect='H_M_FSMP')
                self.assertEqual(result['status'], 'ambiguous')
                self.assertIsNone(result['observedMarker'])
                self.assertFalse(result['modelOriginVerified'])

    def test_marker_width_and_expectations_are_bound_to_capture_version(self):
        archived = capture(SCHEMA_V5)
        self.assertTrue(verify(archived, expect='M1')['modelOriginVerified'])
        for token in ('H_M_STATIC', 'H_F_STATIC', 'H_M_FSMP', 'H_F_FSMP'):
            with self.subTest(token=token), self.assertRaisesRegex(ValueError, 'marker for capture schema'):
                verify(archived, expect=token)
        for data in (archived | {'schema': SCHEMA_V6}, capture(SCHEMA_V6) | {'schema': SCHEMA_V5},
                     capture(SCHEMA) | {'schema': SCHEMA_V6}):
            with self.subTest(schema=data['schema']), self.assertRaisesRegex(ValueError, 'marker counts'):
                verify(data)

    def test_v7_links_both_player_models_to_independently_admitted_forms(self):
        for sex, marker, path in ((0, 'P_M', r'male\Body_1.nif'), (1, 'P_F', r'female\Body_1.nif')):
            with self.subTest(sex=sex):
                data = capture(SCHEMA)
                sample = data['sample']
                sample['sex'] = sex
                sample['playerBody32Fixture'] = dict(zip(('item', 'addon'), FIXTURE, strict=True))
                row = sample['views']['firstPerson']['active'][0]
                row.update(sample['playerBody32Fixture'])
                mark(sample, 2, marker)
                outcome = verify(data, expect=marker, fixture_forms=FIXTURE)
                self.assertEqual(outcome['status'], 'origin_observed')
                self.assertTrue(outcome['markerFixtureModel'].endswith(path))
                self.assertFalse(outcome['installedAssetWinnerVerified'])
                self.assertEqual(verify(data, expect=marker)['status'], 'unadmitted_fixture')
                with self.assertRaisesRegex(ValueError, 'admitted plugin'):
                    verify(data, expect=marker, fixture_forms=(0x0C000801, 0x0C000800))
                row.update(item=ITEM, addon=ADDON)
                self.assertEqual(verify(data, expect=marker, fixture_forms=FIXTURE)['status'], 'wrong_fixture_route')

    def test_v7_null_fixture_preserves_stock_and_refuses_partial_or_mixed_forms(self):
        data = capture(SCHEMA)
        self.assertTrue(verify(data, expect='M1')['modelOriginVerified'])
        for invalid in ({'item': FIXTURE[0]}, {'item': FIXTURE[0], 'addon': ADDON}):
            data['sample']['playerBody32Fixture'] = invalid
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, 'fixture'):
                verify(data)
        data['sample']['playerBody32Fixture'] = dict(zip(('item', 'addon'), FIXTURE, strict=True))
        row = data['sample']['views']['firstPerson']['active'][0]
        row.update(item=FIXTURE[0])
        with self.assertRaisesRegex(ValueError, 'foreign item or addon'):
            verify(data, fixture_forms=FIXTURE)
        row.update(addon=FIXTURE[1])
        self.assertEqual(verify(data, fixture_forms=FIXTURE)['status'], 'wrong_fixture_route')

    def test_aliased_roots_and_clones_do_not_prove_distinct_views(self):
        data = capture()
        sample = data['sample']
        sample['roots']['firstPerson'] = 1
        self.assertEqual(verify(data)['status'], 'aliased_view')
        sample['roots']['firstPerson'] = 2
        sample['body32Markers'][0]['clone'] = sample['views']['thirdPerson']['active'][0]['clone'] = 5
        with self.assertRaisesRegex(ValueError, 'Conflicting marker counts for the same clone'):
            verify(data)
        mark(sample, 0, 'M1')
        self.assertEqual(verify(data)['status'], 'aliased_view')
        sample['body32Markers'][0]['clone'] = sample['views']['thirdPerson']['active'][0]['clone'] = 3
        sample['body32Markers'][2]['clone'] = sample['views']['firstPerson']['active'][0]['clone'] = 2
        self.assertEqual(verify(data)['status'], 'aliased_view')
        sample['body32Markers'][2]['clone'] = sample['views']['firstPerson']['active'][0]['clone'] = 1
        self.assertEqual(verify(data)['status'], 'aliased_view')  # The clone is also the opposite graph root.

    def test_malformed_routes_aliases_slot_records_and_counts_are_refused(self):
        cases = (
            (lambda sample: sample['body32Markers'].reverse(), 'row route'),
            (lambda sample: sample['body32Markers'][2].update(clone=6), 'differs from topology slot'),
            (lambda sample: sample['body32Markers'][2].update(clone=8), 'Unknown marker clone'),
            (lambda sample: sample['body32Markers'][2].update(counts=[False, 1, 0, 0, 0]), 'marker count'),
            (lambda sample: sample['body32Markers'][2].update(counts=[0, 3, 0, 0, 0]), 'marker count'),
            (lambda sample: sample['views']['firstPerson']['active'][0].update(addon=0xCDD89), 'foreign item or addon'),
            (lambda sample: sample['views']['firstPerson'].update(available=False), 'unavailable biped'),
            (lambda sample: sample['views']['firstPerson']['active'].append({'slot': BODY}), 'Duplicate topology slot'),
            (lambda sample: sample['roots'].update(firstPerson=11), 'Unknown actor root'),
            (lambda sample: sample['distinctRoots'].append({'id': 2}), 'Duplicate graph alias'),
        )
        for change, message in cases:
            data = capture()
            change(data['sample'])
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                verify(data)

    def test_capture_identity_and_qpc_are_checked(self):
        data = capture()
        for field in ('pid', 'nonce', 'epoch'):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, f'Capture {field} differs'):
                verify(data, **{field: 1})
        for field, value in (('runtimeHandle', False), ('sex', 2), ('weight', float('nan')), ('weight', 101), ('qpcFrequency', 0),
                             ('qpcBegin', 1260), ('qpcEnd', 1100), ('qpcEnd', 31_000_000)):
            data = capture()
            data['sample'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                verify(data)
        for changed in ({'schema': 'claw-vr-model-topology/4'}, {'status': 'pending'}):
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, 'ready native VR topology /5'):
                verify(capture() | changed)
        data = capture()
        data['sample']['weight'] = None
        self.assertIsNone(verify(data)['observedActorWeight'])
        del data['sample']['weight']
        with self.assertRaisesRegex(ValueError, 'actor weight'):
            verify(data)

    def test_cli_hashes_input_and_preserves_observed_result_on_unmet_expectation(self):
        with TemporaryDirectory() as temp:
            source = Path(temp) / 'capture.json'
            payload = json.dumps(capture()).encode()
            source.write_bytes(payload)
            cmd = [sys.executable, str(Path(__file__).with_name('verify_dispatch_markers.py')), str(source),
                   '--view', 'firstPerson', '--pid', '492', '--nonce', '3', '--epoch', '7']
            accepted = subprocess.run(cmd, capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(accepted.stdout)['captureSha256'], hashlib.sha256(payload).hexdigest())
            rejected = subprocess.run(cmd + ['--expect', 'M0'], capture_output=True, text=True)
            self.assertEqual(rejected.returncode, 1)
            self.assertEqual(json.loads(rejected.stdout)['status'], 'unexpected_origin')
            source.write_bytes(b'{"sample": {}, ' + payload[1:])
            malformed = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(malformed.returncode, 2)
            self.assertIn('Duplicate JSON key', malformed.stderr)


if __name__ == '__main__':
    unittest.main()
