"""Optional immutable FAILED damping replay; a passing test reproduces refusal.

No live admission, assets, transport or positive physics qualification occurs.
"""
from pathlib import Path
import copy
import hashlib
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fsmp_damping_response_readback as response

EVIDENCE_ENV = 'CLAW_FSMP_DAMPING_RESPONSE_EVIDENCE'
REQUIRED_ENV = 'CLAW_FSMP_DAMPING_RESPONSE_REQUIRED'
ARCHIVED_EVIDENCE_SHA256 = '8de24591937f17c105fffd923d07ae0114dc37fcb85ea03608c2475415ea5395'
EXPECTED_FAILURE = 'Unchanged right certified peak control exceeded'


def read_selected_actual():
    selected = os.environ.get(EVIDENCE_ENV)
    if not selected:
        if os.environ.get(REQUIRED_ENV) == '1':
            raise AssertionError('Required failed damping evidence missing: set ' + EVIDENCE_ENV)
        raise unittest.SkipTest('Optional actual FAILED damping proof not selected; set ' + EVIDENCE_ENV)
    payload = Path(selected).expanduser().resolve(strict=True).read_bytes()
    if hashlib.sha256(payload).hexdigest() != ARCHIVED_EVIDENCE_SHA256:
        raise AssertionError('Explicit failed damping proof hash differs; new evidence requires review')
    actual = json.loads(payload)
    if actual.get('schema') != 'claw-actual-failed-damping-response-replay/1' or not {
            'sourceRun', 'reference', 'base', 'opening', 'heldInputs', 'finalWitness',
            'finalReturnedUtf8', 'restLocal', 'expectedFailure', 'expectedDiagnostic',
            'provenance', 'scope'} <= set(actual):
        raise AssertionError('Complete reviewed failed damping bundle required')
    return actual


def reconstruct(actual):
    """Recompute pairing/baseline/held proofs from original raw observations."""
    raw, rest = actual['opening'], actual['restLocal']
    associated = response.joint.pair(raw['worldA'], raw['worldB'], raw['witnessA'], raw['witnessB'],
        reference=actual['reference'], base=actual['base'], rest_local=rest,
        expected_inverse_mass=dict.fromkeys(response.DRIVERS, 20.))
    associated = response.baseline(associated, raw['witnessB'])
    held = response.held_inputs(associated, actual['heldInputs']['native'],
                                raw['worldB'], actual['heldInputs']['world'])
    return associated, held


class ExplicitActualFailedDampingReplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.actual = read_selected_actual()

    def test_original_failure_reproduced_from_raw_pair_held_and_complete_window(self):
        actual = self.actual
        before = copy.deepcopy(actual)
        with patch.object(response.joint.cached, 'module_admission',
                          side_effect=AssertionError('Historical admission must not run')):
            associated, held = reconstruct(actual)
            self.assertEqual(associated, actual['opening']['associated'])
            self.assertEqual(held, actual['heldInputs']['proof'])
            with self.assertRaisesRegex(ValueError, '^' + EXPECTED_FAILURE + '$'):
                response.score(associated, held, actual['finalWitness'], actual['restLocal'])
        self.assertEqual(actual, before)
        self.assertEqual(actual['expectedFailure'], EXPECTED_FAILURE)
        self.assertEqual(actual['scope']['originalResult'], 'failed')
        for key in ('rescoredPassed', 'runtimeDampingAccepted', 'atomicInput',
                    'timeCoverageProven', 'trajectoryRecovered', 'gpuObserved',
                    'renderedAttachmentAccepted', 'liveAdmissionOrRestorationRecheckedByReplay'):
            self.assertIs(actual['scope'][key], False)

    def test_recovered_final_bytes_and_extraction_provenance_retained(self):
        actual = self.actual
        returned = actual['finalReturnedUtf8'].encode('utf-8')
        extraction = actual['provenance']['finalExtraction']
        self.assertEqual(json.loads(returned), actual['finalWitness'])
        self.assertEqual(len(returned), extraction['returnedUtf8Bytes'])
        self.assertEqual(hashlib.sha256(returned).hexdigest(), extraction['returnedUtf8Sha256'])
        self.assertEqual(extraction['lineOneBased'], 1149)
        self.assertEqual(extraction['byteOffset'], 3363556)
        self.assertEqual(extraction['completedWindowCount'], 1)
        self.assertIs(actual['provenance']['originalFinalNotSavedBeforeScore'], True)
        self.assertIs(actual['provenance']['postResponseMorphReadRetained'], False)

    def test_actual_right_lower_already_exceeds_frozen_upper_gate(self):
        actual = self.actual
        associated, held = reconstruct(actual)
        window = actual['finalWitness']['sample']['objectWindow']
        self.assertEqual(window['pairedSteps'], 900)
        self.assertEqual(held['pairedStepsAfterSecondKnownUpdate'], 110)
        self.assertEqual(window['pairedSteps'] - held['pairedStepsAfterSecondKnownUpdate'], 790)
        objects = {row['token']: row for row in window['objects']}
        for parent, driver in zip(response.PARENTS, response.DRIVERS):
            bound = response.peak_bounds(objects[associated['A']['tokens'][driver]],
                held['anchors'][parent]['anchorPose'], actual['restLocal'][driver])
            expected = actual['expectedDiagnostic']['bounds'][driver]
            for key in ('lower', 'upper'):
                self.assertAlmostEqual(bound[key], expected[key], delta=1e-10)
            if driver == response.DRIVERS[1]:
                self.assertGreater(bound['lower'], .4 * held['anchors'][parent]['actualStep'])
        # These are conservative enclosures of this window, not a recovered trajectory.

    def test_corrupted_identity_window_mass_or_held_input_is_not_the_archived_failure(self):
        for kind in ('pid', 'nonce', 'drop', 'preimage', 'mass', 'stale_world', 'held_headroom'):
            value = copy.deepcopy(self.actual)
            final = value['finalWitness']
            window = final['sample']['objectWindow']
            if kind == 'pid':
                final['pid'] += 1
            elif kind == 'nonce':
                window['nonce'] += 1
            elif kind == 'drop':
                window['callbackDrops'] += 1
            elif kind == 'preimage':
                window['objects'][0]['initialPre']['world'][9] += .01
            elif kind == 'mass':
                token = value['opening']['associated']['A']['tokens'][response.DRIVERS[0]]
                row = next(item for item in window['objects'] if item['token'] == token)
                for stage in response.joint.STAGES:
                    row[stage]['inverseMass'] = 10.
            elif kind == 'stale_world':
                value['opening']['worldB']['sampleId'] = value['opening']['worldA']['sampleId']
            else:
                value['heldInputs']['native']['sample']['objectWindow']['pairedSteps'] = 661
            with self.subTest(kind=kind), self.assertRaises(ValueError) as caught:
                associated, held = reconstruct(value)
                response.score(associated, held, final, value['restLocal'])
            self.assertNotEqual(str(caught.exception), EXPECTED_FAILURE)


class ExplicitFailedDampingSelectionContract(unittest.TestCase):
    def test_unset_optional_skips_and_required_unset_fails(self):
        for required, error in (('', unittest.SkipTest), ('1', AssertionError)):
            with self.subTest(required=required), patch.dict(os.environ,
                    {EVIDENCE_ENV: '', REQUIRED_ENV: required}), self.assertRaises(error):
                read_selected_actual()

    def test_explicit_missing_or_changed_file_fails(self):
        with tempfile.TemporaryDirectory(prefix='claw-failed-damping-selection-') as folder:
            missing = Path(folder) / 'missing.json'
            with patch.dict(os.environ, {EVIDENCE_ENV: str(missing)}), self.assertRaises(FileNotFoundError):
                read_selected_actual()
            changed = Path(folder) / 'changed.json'
            changed.write_text('{}', encoding='utf-8')
            with patch.dict(os.environ, {EVIDENCE_ENV: str(changed)}), self.assertRaisesRegex(AssertionError, 'hash differs'):
                read_selected_actual()


if __name__ == '__main__':
    unittest.main()
