"""Requires an actual explicitly selected native CLI, never a Python evaluator."""
import copy
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location('claw_matrix_capture', Path(__file__).with_name('analyze_matrix_capture.py'))
capture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(capture)


def scalar(value=0, present=False):
    return {'available': True, 'present': present, 'value': value}


def key(name, value=0, present=True):
    return {'key': name, **scalar(value, present)}


def snapshot(value=0.5, expected=0.5, *, present=True, target='Ear.Size'):
    return {'sex': 'male', 'familyId': 'Test', 'stage': 'linked-beast',
            'ownKey': 'CLAW.Distribution', 'fixtureTag': 'Twins', 'reference': '0xFF000001',
            'sources': {'HumanVolume': {**scalar(value, True), 'keys': [key('OBody', value)]}},
            'own': {target: scalar(expected, present)},
            'targetKeys': {target: [key('CLAW.Distribution', expected)] if present else []}}


def with_actor_weight(raw, value=25, normalized=0.25):
    """Synthetic observer-shaped witness, not evidence of a game measurement."""
    raw['identity'] = {'sessionId': 'synthetic-observer', 'loadGeneration': 1,
                       'identity': {'form': raw['reference']},
                       'actor': {'weight': {'status': 'available', 'rawNPCWeight': value,
                                            'normalizedNPCWeight': normalized}}}
    raw['weightRaw'], raw['weightNormalized'] = value, normalized
    return raw


def namespace(raw):
    entries = []
    for name, row in raw['sources'].items():
        for entry in row['keys']:
            if entry['present']:
                entries.append({'morph': name, 'key': entry['key'], 'value': entry['value'], 'status': 'available'})
    for name, keys in raw['targetKeys'].items():
        for entry in keys:
            if entry['present']:
                entries.append({'morph': name, 'key': entry['key'], 'value': entry['value'], 'status': 'available'})
    value = {'method': 'VisitMorphValues', 'scope': 'stored_morph_key_values', 'status': 'available',
             'entries': entries, 'callbackCount': len(entries), 'retainedCount': len(entries),
             'startedMonotonicNs': 1, 'finishedMonotonicNs': 2}
    value.update({name: True for name in ('complete', 'providerTraversalCompleted', 'contextGuardProvided', 'contextCurrent')})
    value.update({name: False for name in ('truncated', 'invalidMorph', 'invalidKey', 'invalidActor', 'nonFinite', 'captureFailure',
                                         'aliasAmbiguous', 'duplicatePair', 'identityUnsupported')})
    return value


def append_namespace(raw, morph, provider, value):
    raw['namespace']['entries'].append({'morph': morph, 'key': provider, 'value': value, 'status': 'available'})
    raw['namespace']['callbackCount'] += 1
    raw['namespace']['retainedCount'] += 1


class MatrixCaptureNativeIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cli = os.environ.get('CLAW_MATRIX_CAPTURE_CLI')
        if not cli or not Path(cli).is_file():
            raise RuntimeError('Set CLAW_MATRIX_CAPTURE_CLI to a built shared-kernel claw-preset-tool; missing integration input is not a pass')
        cls.cli = Path(cli)
        cls.cli_sha = os.environ.get('CLAW_MATRIX_CAPTURE_CLI_SHA256', capture.digest(cls.cli))

    def setUp(self):
        parent = ROOT / 'target/test-work'
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='matrix-capture-', dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def evaluator(self, rules='<Rule source="HumanVolume" target="Ear.Size" gain="1" cap="1"/>'):
        path = self.folder/'MorphLinks.xml'
        path.write_text('<MorphLinkProfiles schemaVersion="1"><Profile id="Test" family="HIMBO" version="1" sex="male" calibration="test">'+rules+'</Profile></MorphLinkProfiles>', encoding='ascii')
        return capture.NativeMatrix(path, capture.digest(path), self.cli, self.cli_sha)

    def test_arbitrary_names_and_folded_source_use_real_native_power(self):
        evaluator = self.evaluator('<Rule source="HumanVolume" target="Ear.Size" gain="1" cap="1" function="power" exponent="2"/>')
        raw = snapshot(expected=0.25)
        raw['sources']['humanvolume'] = raw['sources'].pop('HumanVolume')
        result = capture.analyze_capture(raw, evaluator)
        self.assertTrue(result['passed'])
        self.assertEqual(result['targets'][0]['expected'], 0.25)
        self.assertFalse(result['globalOwnKeyAbsenceProven'])
        self.assertGreaterEqual(evaluator.invocations, 2)

    def test_constant_only_profile_has_no_human_input_requirement(self):
        evaluator = self.evaluator('<Rule source="" target="Ear.Size" gain="1" cap="1" function="constant" value="0.25"/>')
        raw = snapshot(expected=0.25)
        raw['sources'] = {}
        self.assertTrue(capture.analyze_capture(raw, evaluator)['passed'])

    def test_native_graph_separates_actual_weight_from_skee_and_omits_sparse_edges(self):
        evaluator = self.evaluator(
            '<Rule source="$actor.weight" target="Ear.Size" gain="1" cap="1"/>'
            '<Rule source="HumanVolume" target="Ear.Size" gain="0.2" cap="1"/>'
            '<Rule source="Ignored" target="Not.Required" gain="1e-50" cap="1"/>')
        graph = evaluator.graph('Test')
        self.assertEqual(graph['sources'], {
            '$actor.weight': {'name': '$actor.weight', 'kind': 'actor-weight'},
            'humanvolume': {'name': 'HumanVolume', 'kind': 'skee-morph'}})
        self.assertEqual(graph['targets'], {'ear.size'})
        self.assertTrue(capture.analyze_capture(with_actor_weight(snapshot(expected=0.35)), evaluator)['passed'])

    def test_scalar_only_uses_independent_raw_weight_and_native_normalization(self):
        evaluator = self.evaluator('<Rule source="$actor.weight" target="Ear.Size" gain="1" cap="1"/>')
        for raw_value, expected in ((0, 0), (25, 0.25), (50, 0.5), (100, 1)):
            raw = with_actor_weight(snapshot(expected=expected, present=expected != 0), raw_value, expected)
            raw['sources'] = {}
            result = capture.analyze_capture(raw, evaluator)
            self.assertTrue(result['passed'])
            self.assertEqual(result['sourcesObserved'], 0)
            self.assertEqual(result['actorWeightWitness']['rawNPCWeight'], raw_value)
            self.assertIn('native captureActor', result['actorWeightNormalization'])

    def test_weight_requires_actor_witness_not_flat_value_or_fake_provider_keys(self):
        evaluator = self.evaluator('<Rule source="$actor.weight" target="Ear.Size" gain="1" cap="1"/>')
        raw = snapshot(expected=0.25)
        raw['sources'] = {};raw['weightRaw'] = 25;raw['weightNormalized'] = 0.25
        with self.assertRaisesRegex(ValueError, 'Actor weight unavailable'):
            capture.analyze_capture(raw, evaluator)
        raw = with_actor_weight(snapshot(expected=0.25))
        raw['sources'] = {'$actor.weight': {**scalar(0.25, True), 'keys': [key('OBody', 0.25)]}}
        with self.assertRaisesRegex(ValueError, 'must not be supplied as a SKEE'):
            capture.analyze_capture(raw, evaluator)
        raw['sources'] = {}
        raw['identity']['actor']['weight']['status'] = 'unavailable'
        with self.assertRaisesRegex(ValueError, 'Actor weight unavailable'):
            capture.analyze_capture(raw, evaluator)

    def test_invalid_raw_actor_weight_and_incoherent_convenience_values_reject(self):
        evaluator = self.evaluator('<Rule source="$actor.weight" target="Ear.Size" gain="1" cap="1"/>')
        for value in (-1, 101, float('nan'), float('inf'), True):
            raw = with_actor_weight(snapshot(expected=0.25), value)
            raw['sources'] = {}
            with self.subTest(value=value), self.assertRaises(ValueError):
                capture.analyze_capture(raw, evaluator)
        for field, wrong in (('weightRaw', 26), ('weightNormalized', 0.5)):
            raw = with_actor_weight(snapshot(expected=0.25));raw['sources'] = {};raw[field] = wrong
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'disagrees'):
                capture.analyze_capture(raw, evaluator)
        raw = with_actor_weight(snapshot(expected=0.25));raw['sources'] = {}
        raw['identity']['identity']['form'] = '0xFF000002'
        with self.assertRaisesRegex(ValueError, 'witnesses disagree'):
            capture.analyze_capture(raw, evaluator)

    def test_actor_weight_rejects_empty_whitespace_control_and_oversized_references(self):
        evaluator = self.evaluator('<Rule source="$actor.weight" target="Ear.Size" gain="1" cap="1"/>')
        for bad in ('', ' ', '\t', 'actor\x01', 'x'*161):
            raw = with_actor_weight(snapshot(expected=0.25));raw['sources'] = {}
            raw['reference'] = raw['identity']['identity']['form'] = bad
            with self.subTest(reference=bad), self.assertRaisesRegex(ValueError, 'Bounded printable identifier'):
                capture.analyze_capture(raw, evaluator)

    def test_supplied_reference_validation_also_applies_to_ordinary_morph_captures(self):
        evaluator = self.evaluator()
        for bad in ('', ' ', 'actor\x01', 'x'*161):
            raw = snapshot();raw['reference'] = bad
            with self.subTest(reference=bad), self.assertRaisesRegex(ValueError, 'Bounded printable identifier'):
                capture.analyze_capture(raw, evaluator)

    def test_native_raw_option_preserves_legacy_normalized_input_and_rejects_double_supply(self):
        evaluator = self.evaluator('<Rule source="$actor.weight" target="Ear.Size" gain="1" cap="1"/>')
        args = ['matrix', str(evaluator.xml), 'Test']
        self.assertEqual(evaluator._run(args, '$actor.weight\t0.25\n')['Ear.Size'], 0.25)
        self.assertEqual(evaluator._run(args+['--actor-weight-raw', '25'])['Ear.Size'], 0.25)
        for extra, text in (([], ''), (['--actor-weight-raw', '101'], ''),
                            (['--actor-weight-raw', '25'], '$actor.weight\t0.25\n')):
            with self.subTest(extra=extra, text=text), self.assertRaisesRegex(ValueError, 'Native matrix CLI rejected'):
                evaluator._run(args+extra, text)

    def test_native_active_graph_does_not_require_omitted_sources_or_targets(self):
        evaluator = self.evaluator(
            '<Rule source="Never.Read" target="Never.Observe" gain="0" cap="1"/>'
            '<Rule source="$actor.weight" target="Also.Omitted" gain="1e-50" cap="1"/>'
            '<Rule source="" target="Ear.Size" gain="1" cap="1" function="constant" value="0.25"/>')
        raw = snapshot(expected=0.25);raw['sources'] = {}
        self.assertTrue(capture.analyze_capture(raw, evaluator)['passed'])
        self.assertEqual(evaluator.graph('Test')['sources'], {})

    def test_actor_weight_preservation_is_observed_separately_from_provider_keys(self):
        before = with_actor_weight(snapshot())
        after = copy.deepcopy(before)
        self.assertTrue(capture.compare_captures(before, after)['actorWeightPreservationPassed'])
        with_actor_weight(after, 50, 0.5)
        result = capture.compare_captures(before, after)
        self.assertFalse(result['passed'])
        self.assertFalse(result['actorWeightPreservationPassed'])
        self.assertEqual(result['changedSources'], [])

    def test_empty_profile_is_observed_neutral_with_no_global_namespace_claim(self):
        evaluator = self.evaluator('')
        raw = snapshot()
        raw['sources'], raw['own'], raw['targetKeys'] = {}, {}, {}
        result = capture.analyze_capture(raw, evaluator)
        self.assertTrue(result['passed'])
        self.assertEqual(result['targetsObserved'], 0)
        self.assertIn('unavailable', result['ownNamespaceCoverage'])

    def test_native_epsilon_omits_large_product_and_underflow_coefficient(self):
        for gain in ('0.000001', '-0.000001', '1e-50', '0'):
            with self.subTest(gain=gain):
                evaluator = self.evaluator(f'<Rule source="HumanVolume" target="Ear.Size" gain="{gain}" cap="1"/>')
                raw = snapshot(value=100000000, expected=0, present=False)
                self.assertTrue(capture.analyze_capture(raw, evaluator)['passed'])
                raw['own']['Ear.Size'] = scalar(0, True)
                raw['targetKeys']['Ear.Size'] = [key('CLAW.Distribution', 0)]
                self.assertFalse(capture.analyze_capture(raw, evaluator)['passed'])

    def test_neighbor_above_epsilon_requires_key_even_inside_numeric_tolerance(self):
        evaluator = self.evaluator('<Rule source="HumanVolume" target="Ear.Size" gain="0.0000010000001111620804" cap="1"/>')
        raw = snapshot(value=1, expected=0, present=False)
        result = capture.analyze_capture(raw, evaluator)
        self.assertFalse(result['passed'])
        self.assertIn('nonzero output key is absent', result['errors'][0]['error'])

    def test_missing_tiny_nonzero_and_present_zero_are_not_approximate_success(self):
        evaluator = self.evaluator()
        for present in (False, True):
            raw = snapshot(value=1e-7, expected=0, present=present)
            result = capture.analyze_capture(raw, evaluator)
            self.assertFalse(result['passed'])

    def test_human_and_suppressed_require_structural_own_absence(self):
        evaluator = self.evaluator()
        for stage in ('human-own-clear', 'suppressed-own-clear'):
            for value in (0, 0.00005):
                with self.subTest(stage=stage, value=value):
                    raw = snapshot(expected=value)
                    raw['stage'] = stage
                    self.assertFalse(capture.analyze_capture(raw, evaluator)['passed'])
            raw = snapshot(expected=0, present=False)
            raw['stage'] = stage
            self.assertTrue(capture.analyze_capture(raw, evaluator)['passed'])

    def test_extra_stale_custom_target_is_rejected(self):
        evaluator = self.evaluator()
        raw = snapshot()
        raw['own']['Old.Custom'] = scalar(0, True)
        raw['targetKeys']['Old.Custom'] = [key('CLAW.Distribution', 0)]
        self.assertFalse(capture.analyze_capture(raw, evaluator)['passed'])

    def test_unobserved_declared_inputs_and_targets_do_not_default_to_zero(self):
        evaluator = self.evaluator()
        for field in ('sources', 'own'):
            raw = snapshot()
            raw[field] = {}
            if field == 'own':
                raw['targetKeys'] = {}
            with self.assertRaisesRegex(ValueError, 'Missing declared'):
                capture.analyze_capture(raw, evaluator)

    def test_scalar_enumeration_disagreement_and_unavailable_keys_reject(self):
        evaluator = self.evaluator()
        raw = snapshot()
        raw['targetKeys']['Ear.Size'][0]['value'] = 0.6
        with self.assertRaisesRegex(ValueError, 'disagrees'):
            capture.analyze_capture(raw, evaluator)
        raw = snapshot()
        raw['sources']['HumanVolume']['keys'][0]['available'] = False
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            capture.analyze_capture(raw, evaluator)

    def test_keyless_present_source_bucket_is_distinct_from_an_absent_name(self):
        evaluator = self.evaluator()
        raw = snapshot(value=0, expected=0, present=False)
        raw['sources']['HumanVolume']['keys'] = []
        raw['namespace'] = namespace(raw)
        result = capture.analyze_capture(raw, evaluator)
        self.assertTrue(result['passed'])
        self.assertTrue(result['globalOwnKeyAbsenceProven'])
        after = copy.deepcopy(raw)
        after['sources']['HumanVolume']['present'] = False
        self.assertTrue(capture.analyze_capture(after, evaluator)['passed'])
        self.assertFalse(capture.compare_captures(raw, after)['sourcePreservationPassed'])
        after['sources']['HumanVolume']['keys'] = [key('OBody', 0)]
        del after['namespace']
        with self.assertRaisesRegex(ValueError, 'Absent source has stored'):
            capture.analyze_capture(after, evaluator)

    def test_foreign_zero_key_presence_and_value_changes_are_detected(self):
        before = snapshot()
        before['targetKeys']['Ear.Size'].append(key('Other.Mod', 0))
        after = copy.deepcopy(before)
        self.assertTrue(capture.compare_captures(before, after)['passed'])
        after['targetKeys']['Ear.Size'][-1]['value'] = 1e-10
        self.assertFalse(capture.compare_captures(before, after)['foreignTargetKeyPreservationPassed'])
        after = copy.deepcopy(before)
        after['targetKeys']['Ear.Size'].pop()
        self.assertFalse(capture.compare_captures(before, after)['passed'])

    def test_source_aggregate_or_foreign_source_key_mutation_is_detected(self):
        before = snapshot()
        after = copy.deepcopy(before)
        after['sources']['HumanVolume']['value'] += 1e-10
        self.assertFalse(capture.compare_captures(before, after)['sourcePreservationPassed'])
        after = copy.deepcopy(before)
        after['sources']['HumanVolume']['keys'][0]['value'] += 1e-10
        self.assertFalse(capture.compare_captures(before, after)['passed'])

    def test_provider_case_aliases_are_folded_but_ambiguous_names_reject(self):
        evaluator = self.evaluator()
        raw = snapshot()
        raw['own']['ear.size'] = raw['own'].pop('Ear.Size')
        raw['targetKeys']['ear.size'] = raw['targetKeys'].pop('Ear.Size')
        raw['targetKeys']['ear.size'][0]['key'] = 'claw.distribution'
        self.assertTrue(capture.analyze_capture(raw, evaluator)['passed'])
        raw['own']['Ear.Size'] = scalar(0, False)
        with self.assertRaisesRegex(ValueError, 'aliases'):
            capture.analyze_capture(raw, evaluator)

    def test_nonfinite_malformed_and_own_source_feedback_reject(self):
        evaluator = self.evaluator()
        for bad in (float('nan'), float('inf'), True):
            raw = snapshot(value=bad)
            with self.assertRaises(ValueError):
                capture.analyze_capture(raw, evaluator)
        raw = snapshot()
        raw['sources']['HumanVolume']['keys'].append(key('CLAW.Distribution', 0))
        with self.assertRaisesRegex(ValueError, 'feedback'):
            capture.analyze_capture(raw, evaluator)

    def test_changed_native_or_xml_pin_fails_and_report_is_not_overwritten(self):
        evaluator = self.evaluator()
        evaluator.evaluate(snapshot())
        evaluator.xml.write_text('changed', encoding='ascii')
        with self.assertRaisesRegex(ValueError, 'Pinned file mismatch'):
            evaluator.evaluate(snapshot())
        evaluator = self.evaluator()
        with self.assertRaisesRegex(ValueError, 'Pinned file mismatch'):
            capture.NativeMatrix(evaluator.xml, capture.digest(evaluator.xml), self.cli, '0'*64)
        output = self.folder/'report.json'
        output.write_text('existing report', encoding='ascii')
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            capture.main(['--xml', str(evaluator.xml), '--xml-sha256', capture.digest(evaluator.xml),
                          '--cli', str(self.cli), '--cli-sha256', self.cli_sha,
                          '--capture', str(self.folder/'absent.json'), '--output', str(output)])
        self.assertEqual(output.read_text(), 'existing report')

    def test_compare_cannot_mix_references_or_sessions(self):
        before, after = snapshot(), snapshot()
        after['reference'] = '0xFF000002'
        with self.assertRaisesRegex(ValueError, 'Same-reference'):
            capture.compare_captures(before, after)
        after = snapshot()
        after['identity'] = {'sessionId': 'other'}
        with self.assertRaisesRegex(ValueError, 'session'):
            capture.compare_captures(before, after)

    def test_strict_json_disallows_duplicate_keys_and_native_rejects_ambiguous_profile(self):
        path = self.folder/'capture.json'
        path.write_text('{"sources":{},"sources":{}}', encoding='ascii')
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON'):
            capture.read_json(path)
        with self.assertRaisesRegex(ValueError, 'Native matrix CLI rejected'):
            self.evaluator('<Rule source="HumanVolume" target="humanvolume" gain="1" cap="1"/>')

    def test_full_namespace_can_prove_human_cleanup_and_reconcile_case_keys(self):
        evaluator = self.evaluator()
        raw = snapshot(expected=0, present=False)
        raw['stage'] = 'human-own-clear'
        raw['namespace'] = namespace(raw)
        result = capture.analyze_capture(raw, evaluator)
        self.assertTrue(result['passed'])
        self.assertTrue(result['globalOwnKeyAbsenceProven'])
        self.assertTrue(result['globalOwnKeySetMatchesKernel'])
        raw = snapshot()
        raw['targetKeys']['Ear.Size'][0]['key'] = 'claw.distribution'
        raw['namespace'] = namespace(raw)
        result = capture.analyze_capture(raw, evaluator)
        self.assertTrue(result['passed'])
        self.assertFalse(result['globalOwnKeyAbsenceProven'])
        self.assertEqual(result['ownNamespaceEntries'], {'Ear.Size': 0.5})

    def test_global_namespace_rejects_unrequested_stale_zero_and_tiny_own_keys(self):
        evaluator = self.evaluator()
        for value in (0, 0.00005):
            raw = snapshot()
            raw['namespace'] = namespace(raw)
            append_namespace(raw, 'Old.Unrequested', 'claw.distribution', value)
            result = capture.analyze_capture(raw, evaluator)
            self.assertFalse(result['passed'])
            self.assertFalse(result['globalOwnKeySetMatchesKernel'])
            self.assertTrue(any(row.get('scope') == 'full-namespace' for row in result['errors']))

    def test_full_namespace_preserves_foreign_keys_outside_requested_names(self):
        before = snapshot()
        before['namespace'] = namespace(before)
        append_namespace(before, 'External.Custom', 'Foreign.Provider', 0)
        after = copy.deepcopy(before)
        self.assertTrue(capture.compare_captures(before, after)['globalForeignKeyPreservationPassed'])
        after['namespace']['entries'][-1]['value'] = 1e-10
        result = capture.compare_captures(before, after)
        self.assertFalse(result['passed'])
        self.assertEqual(result['changedGlobalForeignMorphs'], ['external.custom'])

    def test_partial_namespace_bad_flags_counts_aliases_and_unavailable_values_reject(self):
        evaluator = self.evaluator()
        for field, bad in (('complete', False), ('contextCurrent', False), ('truncated', True),
                           ('callbackCount', 0), ('retainedCount', True), ('startedMonotonicNs', -1)):
            with self.subTest(field=field):
                raw = snapshot()
                raw['namespace'] = namespace(raw)
                raw['namespace'][field] = bad
                with self.assertRaises(ValueError):
                    capture.analyze_capture(raw, evaluator)
        raw = snapshot()
        raw['namespace'] = namespace(raw)
        append_namespace(raw, 'ear.size', 'Foreign', 0)
        with self.assertRaisesRegex(ValueError, 'case alias'):
            capture.analyze_capture(raw, evaluator)

    def test_namespace_identity_and_duplicate_flags_are_mandatory_false(self):
        evaluator = self.evaluator()
        for field in ('duplicatePair', 'identityUnsupported'):
            for mode in ('true', 'missing'):
                with self.subTest(field=field, mode=mode):
                    raw = snapshot(expected=0, present=False)
                    raw['stage'] = 'human-own-clear'
                    raw['namespace'] = namespace(raw)
                    if mode == 'true':
                        raw['namespace'][field] = True
                    else:
                        del raw['namespace'][field]
                    with self.assertRaisesRegex(ValueError, field):
                        capture.analyze_capture(raw, evaluator)

    def test_full_namespace_disagreement_with_requested_readback_rejects(self):
        evaluator = self.evaluator()
        raw = snapshot()
        raw['namespace'] = namespace(raw)
        raw['namespace']['entries'][-1]['value'] = 0.6
        with self.assertRaisesRegex(ValueError, 'disagrees with full namespace'):
            capture.analyze_capture(raw, evaluator)

    def test_new_capture_nested_reference_works_and_missing_namespace_is_not_global(self):
        before, after = snapshot(), snapshot()
        for raw in (before, after):
            raw['identity'] = {'sessionId': 'one', 'identity': {'form': raw.pop('reference')}}
        self.assertTrue(capture.compare_captures(before, after)['passed'])
        self.assertIsNone(capture.compare_captures(before, after)['globalForeignKeyPreservationPassed'])

    def test_full_namespace_duplicate_folded_keys_bounds_and_status_are_refused(self):
        evaluator = self.evaluator()
        raw = snapshot()
        raw['namespace'] = namespace(raw)
        append_namespace(raw, 'Ear.Size', 'claw.distribution', 0.5)
        with self.assertRaisesRegex(ValueError, 'Duplicate/ambiguous'):
            capture.analyze_capture(raw, evaluator)
        for name, bad in (('key', 'a'*129), ('morph', 'a'*161), ('value', float('nan')), ('status', 'unavailable')):
            raw = snapshot()
            raw['namespace'] = namespace(raw)
            raw['namespace']['entries'][-1][name] = bad
            with self.assertRaises(ValueError):
                capture.analyze_capture(raw, evaluator)

    def test_interval_rejects_own_value_drift_inside_numeric_tolerance(self):
        evaluator = self.evaluator()
        raw = snapshot()
        sample = copy.deepcopy(raw)
        sample['own']['Ear.Size']['value'] = 0.50001
        sample['targetKeys']['Ear.Size'][0]['value'] = 0.50001
        value = {'raw': raw, 'interval': {'actionReplayCount': 0, 'observedSpanSeconds': 0.2,
                                        'samples': [{'raw': raw}, {'raw': sample}]}}
        path = self.folder/'interval.json'
        path.write_text(json.dumps(value), encoding='ascii')
        result, _ = capture.analyze_file(path, evaluator)
        self.assertFalse(result['passed'])
        self.assertFalse(result['intervalChecks'][1]['ownStorageUnchanged'])

    def test_run_mode_consumes_new_capture_domain_without_claiming_game_qualification(self):
        evaluator = self.evaluator()
        run = self.folder/'run'
        run.mkdir()
        raw = snapshot()
        raw['snapshotLabel'] = 'Twins-wolf'
        raw['namespace'] = namespace(raw)
        raw['identity'] = {'sessionId': 'one', 'identity': {'form': raw.pop('reference')}}
        (run/'step-000.json').write_text(json.dumps({'raw': raw}), encoding='ascii')
        (run/'scenario.json').write_text(json.dumps({'steps': [{'name': 'capture'}]}), encoding='ascii')
        (run/'result.json').write_text(json.dumps({'result': 'passed', 'restored': True}), encoding='ascii')
        order = {'schemaVersion': 2, 'id': 'synthetic-parser-contract-not-game-run',
                 'inputs': [{'role': 'subject', 'path': str(evaluator.xml), 'sha256': capture.digest(evaluator.xml)}],
                 'subjectPlan': {'steps': [{'name': 'capture', 'parameters': {'request': {
                     'domain': 'actor-morph-capture', 'familyId': 'Test', 'captureSnapshot': 'Twins-wolf', 'stage': 'linked-beast',
                     'actor': {'fixtureTag': 'Twins'}, 'sourceMorphs': ['HumanVolume'], 'targetMorphs': ['Ear.Size'],
                     'ownKey': 'CLAW.Distribution', 'requireFullNamespace': True}}}]}}
        path = self.folder/'order.json'
        path.write_text(json.dumps(order), encoding='ascii')
        result = capture.analyze_run(path, run, evaluator)
        self.assertTrue(result['numericAndObservedPreservationPassed'])
        self.assertEqual(result['captures'][0]['ownNamespaceEntries'], {'Ear.Size': 0.5})
        self.assertIn('unavailable', result['wholeModAcceptance'])


if __name__ == '__main__':
    unittest.main()
