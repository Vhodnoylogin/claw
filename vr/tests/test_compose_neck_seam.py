"""Artifact-boundary regressions; opaque NIF bytes are fixture identities only."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import compose_neck_seam as compose


def name(value):
    return bytes([len(value)]) + value.encode('ascii')


def tri():
    rows = []
    for shape in ('body', 'head', 'tail'):
        record = name('G') + struct.pack('<fH', .01, 1) + struct.pack('<H3h', 0, 1, 2, 3)
        rows.append(name(shape) + struct.pack('<H', 1) + record)
    return b'PIRT' + struct.pack('<H', 3) + b''.join(rows)


class ComposeBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.neck = self.root/'neck'
        self.neck.mkdir()
        self.report = {'status': 'offline-first-person-neck-graft-native-verified-joins-measured-runtime-pending',
                       'bodies': {}, 'joins': {}, 'inputSha256': {}}
        self.profile = {'bodies': {}}
        self.old = self.root/'old.tri'
        self.old.write_bytes(tri())
        candidate, _ = compose.morph_seam.append_record(tri(), 'head', 'CLAWTorsoWaistNarrow', .01, {0: (1, 0, 0)})
        self.new = self.root/'new.tri'
        self.new.write_bytes(candidate)
        original_nifs = []
        for sex in ('female', 'male'):
            folder = self.neck/'resources'/sex
            folder.mkdir(parents=True)
            for endpoint in (0, 1):
                source = self.root/'source'/sex/f'{sex}bodywerewolf_{endpoint}.nif'
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_bytes(f'opaque-{sex}-{endpoint}'.encode())
                path = folder/f'first-person_{endpoint}.nif'
                path.write_bytes(source.read_bytes())
                self.report['bodies'][sex+str(endpoint)] = {
                    'numericPlanPasses': True, 'numericFailures': [],
                    'serializedCandidate': {'nifSha256': compose.resource.sha256(path),
                        'nativeProtectedGeometryMaterialsUvFramesAndForeignWeightsExact': True,
                        'originalNodesAndBindsExact': True, 'originalBlockIdsStable': True,
                        'originalStringIdsStable': True}}
                self.report['inputSha256'][str(source.resolve())] = compose.resource.sha256(source)
                if sex == 'male':
                    original_nifs.append(self.pin(source))
            path = folder/(sex+'bodywerewolf.tri')
            path.write_bytes(tri())
            tri_source = self.root/'source'/sex/(sex+'bodywerewolf.tri')
            tri_source.write_bytes(tri())
            self.report['inputSha256'][str(tri_source)] = compose.resource.sha256(tri_source)
            self.profile['bodies'][sex] = {'nifSha256': [self.report['inputSha256'][str(self.root/'source'/sex/f'{sex}bodywerewolf_{i}.nif')] for i in (0, 1)],
                                         'triSha256': compose.resource.sha256(tri_source)}
            joined = self.root/(sex+'-join.json')
            joined.write_text('{}')
            self.report['joins'][sex] = {'report': str(joined), 'sha256': compose.resource.sha256(joined)}
        self.manifest = self.root/'seam.json'
        self.seam = {'unchangedNifs': original_nifs, 'sourceTri': self.pin(self.old), 'candidateTri': self.pin(self.new)}
        skeleton = self.root/'source/skeleton.nif'
        skeleton.write_bytes(b'opaque reviewed skeleton')
        self.profile['skeletonSha256'] = compose.resource.sha256(skeleton)
        self.report['inputSha256'][str(skeleton)] = self.profile['skeletonSha256']
        profile_path = self.root/'composed-visibility-profile.json'
        profile_path.write_text(json.dumps(self.profile))
        self.report['inputSha256'][str(profile_path)] = compose.resource.sha256(profile_path)
        patched = patch.object(compose, 'reviewed_profile', return_value=(self.profile, profile_path))
        patched.start()
        self.addCleanup(patched.stop)
        self.write()

    @staticmethod
    def pin(path):
        return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def write(self):
        (self.neck/'head-isolation-report.json').write_text(json.dumps(self.report))
        self.manifest.write_text(json.dumps(self.seam))

    def test_one_record_extension_allows_later_offsets_to_shift(self):
        sources, _ = compose.admit(self.neck, self.manifest)
        self.assertEqual(sources['male/malebodywerewolf.tri'], self.new)
        old = compose.tri_patch.offsets(self.old.read_bytes())
        new = compose.tri_patch.offsets(self.new.read_bytes())
        self.assertNotEqual(old['tail', 'G', 0].position, new['tail', 'G', 0].position)

    def test_false_success_or_missing_native_receipt_is_refused(self):
        original = copy.deepcopy(self.report)
        for bad in (False, 'true', None):
            self.report = copy.deepcopy(original)
            self.report['bodies']['male0']['numericPlanPasses'] = bad
            self.write()
            with self.assertRaisesRegex(ValueError, 'Rejected or missing'):
                compose.admit(self.neck, self.manifest)
        self.report = copy.deepcopy(original)
        del self.report['bodies']['female1']['serializedCandidate']
        self.write()
        with self.assertRaises(ValueError):
            compose.admit(self.neck, self.manifest)

    def test_changed_source_field_is_not_hidden_by_new_candidate_hash(self):
        data = bytearray(self.new.read_bytes())
        offset = compose.tri_patch.offsets(data)['body', 'G', 0]
        struct.pack_into('<h', data, offset.position, 9)
        self.new.write_bytes(data)
        self.seam['candidateTri'] = self.pin(self.new)
        self.write()
        with self.assertRaisesRegex(ValueError, 'pre-existing serialized'):
            compose.admit(self.neck, self.manifest)

    def test_different_neck_and_seam_endpoint_is_refused(self):
        self.report['inputSha256'][self.seam['unchangedNifs'][0]['path']] = '0'*64
        self.write()
        with self.assertRaisesRegex(ValueError, 'reviewed profile'):
            compose.admit(self.neck, self.manifest)

    def test_explicit_failed_native_receipt_is_refused(self):
        self.report['bodies']['female0']['serializedCandidate']['originalNodesAndBindsExact'] = False
        self.write()
        with self.assertRaisesRegex(ValueError, 'preservation was not confirmed'):
            compose.admit(self.neck, self.manifest)

    def test_missing_or_duplicate_male_endpoint_receipt_is_refused(self):
        original = copy.deepcopy(self.seam['unchangedNifs'])
        for rows in ([], original[:1], [original[0], original[0]]):
            self.seam['unchangedNifs'] = rows
            self.write()
            with self.assertRaisesRegex(ValueError, 'Both distinct'):
                compose.admit(self.neck, self.manifest)


if __name__ == '__main__':
    unittest.main()
