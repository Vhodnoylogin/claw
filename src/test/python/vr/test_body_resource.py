"""Offline visibility admission, exact byte edits and preserved hand/TRI contracts."""
import copy
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0, str((Path(__file__).resolve().parents[4] / 'src/main/python/vr')))
import body_resource as vr


class BytePatchTests(unittest.TestCase):
    def fixture(self):
        raw = bytearray(b'\xcc' * 160)
        rows = []
        for i, (name, extra, flags) in enumerate([('body', 0, 14), ('head', 2, 524302), ('eyes', 1, 14)]):
            start = i * 48
            struct.pack_into('<I', raw, start + 4, extra)
            struct.pack_into('<I', raw, start + 12 + 4 * extra, flags)
            rows.append({'name': name, 'flags': flags, 'offset': start, 'size': 48, 'type': 'BSTriShape'})
        return bytes(raw), rows

    def test_only_hidden_bits_change_with_variable_extra_data(self):
        raw, rows = self.fixture()
        result, ledger = vr.patch_hidden(raw, rows, ['head', 'eyes'])
        self.assertEqual(2, vr.verify_bytes(raw, result, ledger))
        self.assertEqual(raw[:48], result[:48])
        self.assertEqual({68, 112}, {i for i, (a, b) in enumerate(zip(raw, result)) if a != b})
        self.assertEqual([524303, 15], [e['after'] for e in ledger])
        self.assertEqual(raw, self.fixture()[0], 'source buffer must remain untouched')

    def test_unrelated_change_is_rejected(self):
        raw, rows = self.fixture()
        result, ledger = vr.patch_hidden(raw, rows, ['head'])
        wrong = bytearray(result)
        wrong[0] ^= 1
        with self.assertRaisesRegex(ValueError, 'Unplanned bytes'):
            vr.verify_bytes(raw, wrong, ledger)

    def test_size_change_is_rejected(self):
        raw, rows = self.fixture()
        result, ledger = vr.patch_hidden(raw, rows, ['head'])
        with self.assertRaisesRegex(ValueError, 'byte count'):
            vr.verify_bytes(raw, result + b'x', ledger)

    def test_other_flag_changes_are_rejected(self):
        raw, rows = self.fixture()
        result, ledger = vr.patch_hidden(raw, rows, ['head'])
        ledger[0]['after'] |= 128
        with self.assertRaisesRegex(ValueError, 'only set the hidden bit'):
            vr.verify_bytes(raw, result, ledger)

    def test_unknown_or_duplicate_shape_is_rejected(self):
        raw, rows = self.fixture()
        for shapes, hidden in [(rows, ['absent']), (rows + [rows[0]], ['head']), (rows, ['head', 'head'])]:
            with self.subTest(hidden=hidden), self.assertRaises(ValueError):
                vr.patch_hidden(raw, shapes, hidden)

    def test_wrong_native_flags_or_already_hidden_is_rejected(self):
        raw, rows = self.fixture()
        for flags in (0, rows[1]['flags'] | 1):
            wrong = copy.deepcopy(rows)
            wrong[1]['flags'] = flags
            with self.subTest(flags=flags), self.assertRaises(ValueError):
                vr.patch_hidden(raw, wrong, ['head'])

    def test_truncation_extra_count_and_type_are_rejected(self):
        raw, rows = self.fixture()
        for key, value in [('type', 'NiNode'), ('offset', -1), ('size', 8), ('size', 1000)]:
            wrong = copy.deepcopy(rows)
            wrong[1][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                vr.patch_hidden(raw, wrong, ['head'])
        damaged = bytearray(raw)
        struct.pack_into('<I', damaged, rows[1]['offset'] + 4, 0xFFFFFFFF)
        with self.assertRaisesRegex(ValueError, 'extra-data'):
            vr.patch_hidden(damaged, rows, ['head'])

    def test_overlapping_offsets_are_rejected(self):
        raw, rows = self.fixture()
        wrong = [rows[1], dict(rows[1], name='eyes')]
        with self.assertRaisesRegex(ValueError, 'Overlapping'):
            vr.patch_hidden(raw, wrong, ['head', 'eyes'])

    def test_ledger_cannot_escape_buffer_or_overlap(self):
        raw, rows = self.fixture()
        result, ledger = vr.patch_hidden(raw, rows, ['head'])
        for wrong in [ledger + ledger, [dict(ledger[0], offset=-1)], [dict(ledger[0], offset=len(raw))]]:
            with self.assertRaises(ValueError):
                vr.verify_bytes(raw, result, wrong)


class AdmissionTests(unittest.TestCase):
    def test_reviewed_profile_loads(self):
        p = vr.load_profile(Path(vr.__file__).with_name('profile.json'))
        self.assertEqual(25, p['bodies']['female']['publicMorphCount'])

    def test_profile_duplicate_json_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'profile.json'
            path.write_text('{"schemaVersion":1,"schemaVersion":1}')
            with self.assertRaisesRegex(ValueError, 'Duplicate JSON'):
                vr.load_profile(path)

    def test_unreviewed_policy_or_pin_is_rejected(self):
        profile = vr.load_profile(Path(vr.__file__).with_name('profile.json'))
        changes = [('hiddenShapes', ['body']), ('handBones', ['NPC Hand']), ('schemaVersion', True),
                   ('skeletonSha256', 'a' * 64), ('unknownField', 1)]
        with tempfile.TemporaryDirectory() as directory:
            for key, value in changes:
                wrong = copy.deepcopy(profile)
                wrong[key] = value
                path = Path(directory) / 'profile.json'
                path.write_text(json.dumps(wrong))
                with self.subTest(key=key), self.assertRaises(ValueError):
                    vr.load_profile(path)
            for field, value in [('nif', '../escape.nif'), ('nodeCount', True), ('triSha256', 'x' * 64)]:
                wrong = copy.deepcopy(profile)
                wrong['bodies']['male'][field] = value
                path.write_text(json.dumps(wrong))
                with self.subTest(field=field), self.assertRaises(ValueError):
                    vr.load_profile(path)

    def test_existing_repo_source_and_live_destinations_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = base / 'repo'
            repo.mkdir()
            source = base / 'input' / 'body.nif'
            for output in [base, repo / 'generated', source.parent / 'generated',
                           base / 'mods' / 'new', base / 'MO2' / 'new', base / 'SkyrimVR' / 'new']:
                with self.subTest(output=output), self.assertRaises(ValueError):
                    vr.safe_output(output, [source], repo)
            good = base / 'builds' / 'new'
            self.assertEqual(good.resolve(), vr.safe_output(good, [source], repo))

    def test_other_git_checkout_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / '.git').write_text('gitdir: somewhere')
            with self.assertRaisesRegex(ValueError, 'Git checkout'):
                vr.safe_output(base / 'generated', [], base / 'different')

    def test_wrong_input_rejects_before_output_or_dependency_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / 'inputs'
            source.mkdir()
            (source / 'skeleton.nif').write_bytes(b'invalid')
            (source / 'malebodywerewolf_0.nif').write_bytes(b'invalid')
            output = base / 'candidate'
            with self.assertRaisesRegex(ValueError, 'Unsupported exact input'):
                vr.build(source, source / 'skeleton.nif', Path(vr.__file__).with_name('profile.json'), output)
            self.assertFalse(output.exists())


class BodyContractTests(unittest.TestCase):
    def fixture(self):
        profile = vr.load_profile(Path(vr.__file__).with_name('profile.json'))
        tri_path = 'actors\\werewolfbeast\\character assets\\malebodywerewolf.tri'
        def shape(name, weights):
            return SimpleNamespace(name=name, bone_names=list(weights), bone_weights=weights,
                                   verts=[(0., 0., 0.)] * 4,
                                   flags=14, parent=None,
                                   extra_data=lambda _: [SimpleNamespace(name='BODYTRI', string_data=tri_path)])
        body = shape('body', {vr.HAND_BONES[0]: [(0, 1.)], vr.HAND_BONES[1]: [(1, 1.)],
                              profile['headBone']: [(2, .2)], 'Ear': [(3, .5)]})
        mixed_head = shape('head', {profile['headBone']: [(0, 1.)], 'NPC Spine2 [Spn2]': [(1, 1.)],
                                    'NPC L Clavicle [RClv]': [(2, .5)]})
        shapes = [body, mixed_head, *[shape(name, {profile['headBone']: [(0, 1.)]}) for name in vr.HIDDEN_SHAPES]]
        for index, item in enumerate(shapes):
            item.id = index
        head = SimpleNamespace(parent=None)
        skeleton = SimpleNamespace(nodes={profile['headBone']: head, 'Ear': SimpleNamespace(parent=SimpleNamespace(name=profile['headBone'], parent=None)),
                                          **{b: SimpleNamespace(parent=None) for b in [*vr.HAND_BONES, 'NPC Spine2 [Spn2]', 'NPC L Clavicle [RClv]']}})
        nif = SimpleNamespace(nodes={'root': object()}, shapes=shapes, game='SKYRIMSE')
        profile['bodies']['male']['shapeCount'] = len(shapes)
        profile['bodies']['male']['nodeCount'] = 1
        return profile, nif, skeleton

    def test_residual_head_weight_is_reported_and_hands_remain(self):
        p, nif, skeleton = self.fixture()
        report = vr.audit_body(nif, skeleton, p, 'male')
        self.assertEqual({'body': 2, 'head': 1}, report['remainingVisibleHeadDescendantWeightedVertices'])
        self.assertEqual({b: 1 for b in vr.HAND_BONES}, report['weightedHandVertices'])
        self.assertIn('unqualified', report['cameraClearance'])

    def test_hidden_hand_geometry_is_rejected(self):
        p, nif, skeleton = self.fixture()
        nif.shapes[2].bone_weights[vr.HAND_BONES[0]] = [(1, 1.)]
        with self.assertRaisesRegex(ValueError, 'hide hand geometry'):
            vr.audit_body(nif, skeleton, p, 'male')

    def test_missing_hand_or_missing_xp32_bone_is_rejected(self):
        for fault in ('hand', 'bone'):
            p, nif, skeleton = self.fixture()
            if fault == 'hand':
                nif.shapes[0].bone_weights[vr.HAND_BONES[0]] = []
            else:
                del skeleton.nodes['Ear']
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                vr.audit_body(nif, skeleton, p, 'male')

    def test_wrong_bodytri_is_rejected(self):
        p, nif, skeleton = self.fixture()
        nif.shapes[0].extra_data = lambda _: []
        with self.assertRaisesRegex(ValueError, 'BODYTRI'):
            vr.audit_body(nif, skeleton, p, 'male')

    def test_tri_index_names_and_delta_admission(self):
        _, nif, _ = self.fixture()
        morphs = {s.name: {'CLAWTest': []} for s in nif.shapes}
        class Trip:
            is_valid = True
            shapes = morphs
            def read(self, stream):
                return 0
        with tempfile.TemporaryDirectory() as directory:
            tri = Path(directory) / 'body.tri'
            tri.write_bytes(b'fixture')
            self.assertEqual(['CLAWTest'], vr.tri_contract(Trip, tri, nif, 1))
            for delta in [[[4, (0., 0., 0.)]], [[0, (float('nan'), 0., 0.)]],
                          [[0, (1., 0., 0.)], [0, (2., 0., 0.)]]]:
                Trip.shapes['body']['CLAWTest'] = delta
                with self.subTest(delta=delta), self.assertRaises(ValueError):
                    vr.tri_contract(Trip, tri, nif, 1)
            Trip.shapes = {'unknown': {'CLAWTest': []}}
            with self.assertRaisesRegex(ValueError, 'shape names'):
                vr.tri_contract(Trip, tri, nif, 1)

    def trip(self, nif):
        return SimpleNamespace(shapes={s.name: {} for s in nif.shapes})

    def test_breast_morph_shape_must_stay_visible_by_file_attributes(self):
        p, nif, skeleton = self.fixture()
        trip = self.trip(nif)
        trip.shapes['head']['CLAWTorsoBreastSize'] = [[1, (0., 1., 0.)]]
        report = vr.visibility_admission(nif, skeleton, p, trip)
        support = report['breastMorphSupport']['head']
        self.assertEqual(1, support['nonzeroDeltaCount'])
        self.assertTrue(support['visibleByFileHiddenFlags'])
        self.assertEqual(14, support['shapeFlags'])
        self.assertEqual(2, report['retainedMixedHead']['torsoLevelNonHeadWeightedVertices'])
        nif.shapes[1].flags |= vr.HIDDEN
        with self.assertRaisesRegex(ValueError, 'Breast morph support would be hidden'):
            vr.visibility_admission(nif, skeleton, p, trip)

    def test_hidden_ancestor_disqualifies_breast_file_visibility(self):
        p, nif, skeleton = self.fixture()
        trip = self.trip(nif)
        trip.shapes['head']['CLAWTorsoBreastSize'] = [[1, (0., 1., 0.)]]
        nif.shapes[1].parent = SimpleNamespace(name='HiddenRoot', flags=1, parent=None)
        with self.assertRaisesRegex(ValueError, 'Breast morph support would be hidden'):
            vr.visibility_admission(nif, skeleton, p, trip)

    def test_auto_hide_breast_or_torso_morph_shape_is_refused(self):
        for morph in ('CLAWTorsoBreastSize', 'CLAWTorsoChestSize'):
            p, nif, skeleton = self.fixture()
            trip = self.trip(nif)
            # Even an empty torso-morph entry forbids whole-shape hiding.
            trip.shapes['eyes'][morph] = []
            with self.subTest(morph=morph), self.assertRaisesRegex(ValueError, 'Cannot auto-hide'):
                vr.visibility_admission(nif, skeleton, p, trip)

    def test_auto_hide_male_mixed_head_is_refused_without_breast_morph(self):
        p, nif, skeleton = self.fixture()
        p['hiddenShapes'] = [*p['hiddenShapes'], 'head']
        with self.assertRaisesRegex(ValueError, 'torso-level non-head geometry'):
            vr.visibility_admission(nif, skeleton, p, self.trip(nif))

    def test_torso_geometry_guard_distinguishes_head_owned_mouth_vertices(self):
        p, nif, skeleton = self.fixture()
        trip = self.trip(nif)
        self.assertEqual(5, len(vr.visibility_admission(nif, skeleton, p, trip)['hiddenShapeAdmission']))
        next(s for s in nif.shapes if s.name == 'mouth').bone_weights['NPC Spine2 [Spn2]'] = [(0, .0001)]
        with self.assertRaisesRegex(ValueError, 'torso-level non-head geometry: mouth'):
            vr.visibility_admission(nif, skeleton, p, trip)


@unittest.skipUnless(os.environ.get('CLAW_VR_NATIVE_TESTS') == '1', 'Set CLAW_VR_NATIVE_TESTS=1 for published NIF/native regressions')
class NativePublishedBodyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api, cls.NifPatch, cls.TripFile, _ = vr.dependencies()
        cls.profile = vr.load_profile(Path(vr.__file__).with_name('profile.json'))
        cls.directory = vr.ROOT / 'target/references/releases/0.6.2.0/base/Meshes/Actors/WerewolfBeast/Character Assets'
        cls.skeleton = cls.api.NifFile(str(vr.ROOT / 'src/main/resources/donors/skeleton.nif'))

    def fixture(self, sex):
        pin = self.profile['bodies'][sex]
        path = self.directory / pin['nif']
        nif = self.api.NifFile(str(path))
        _, trip = vr.tri_contract(self.TripFile, self.directory / pin['tri'], nif, pin['publicMorphCount'], include_trip=True)
        return path, nif, trip

    def test_published_female_head_has_real_breast_morph_and_torso_weights(self):
        _, nif, trip = self.fixture('female')
        head = next(s for s in nif.shapes if s.name == 'head')
        self.assertEqual(155, head.id)
        self.assertEqual(590, len(trip.shapes['head']['CLAWTorsoBreastSize']))
        self.assertEqual(2174, sum(w > 0 for _, w in head.bone_weights['NPC Spine2 [Spn2]']))
        self.assertTrue(any('Clavicle' in b and rows for b, rows in head.bone_weights.items()))
        p = copy.deepcopy(self.profile)
        p['hiddenShapes'].append('head')
        with self.assertRaisesRegex(ValueError, 'carrying CLAWTorsoBreastSize: head'):
            vr.visibility_admission(nif, self.skeleton, p, trip)

    def test_published_male_head_is_mixed_even_without_breast_morph(self):
        _, nif, trip = self.fixture('male')
        head = next(s for s in nif.shapes if s.name == 'head')
        self.assertEqual(163, head.id)
        self.assertNotIn('CLAWTorsoBreastSize', trip.shapes['head'])
        self.assertEqual(2174, sum(w > 0 for _, w in head.bone_weights['NPC Spine2 [Spn2]']))
        p = copy.deepcopy(self.profile)
        p['hiddenShapes'].append('head')
        with self.assertRaisesRegex(ValueError, 'Cannot auto-hide'):
            vr.visibility_admission(nif, self.skeleton, p, trip)

    def test_exact_five_flag_edits_keep_whole_mixed_head_block_and_native_visibility(self):
        with tempfile.TemporaryDirectory() as directory:
            for sex, expected_head_id in [('male', 163), ('female', 155)]:
                path, nif, trip = self.fixture(sex)
                before = vr.visibility_admission(nif, self.skeleton, self.profile, trip)
                table = self.NifPatch(path)
                rows = [{'name': s.name, 'flags': s.flags, 'type': table.types[s.id],
                         'offset': table.offsets[s.id], 'size': table.sizes[s.id]} for s in nif.shapes]
                raw, ledger = vr.patch_hidden(table.raw, rows, self.profile['hiddenShapes'])
                off, size = table.offsets[expected_head_id], table.sizes[expected_head_id]
                self.assertEqual(table.raw[off:off + size], raw[off:off + size])
                changed = [i for i, (a, b) in enumerate(zip(table.raw, raw)) if a != b]
                self.assertEqual(5, len(changed))
                self.assertEqual({e['offset'] for e in ledger}, set(changed))
                self.assertNotIn('head', {e['shape'] for e in ledger})
                target = Path(directory) / (sex + '.nif')
                target.write_bytes(raw)
                result = self.api.NifFile(str(target))
                head = next(s for s in result.shapes if s.name == 'head')
                self.assertEqual(expected_head_id, head.id)
                self.assertFalse(head.flags & vr.HIDDEN)
                after = vr.visibility_admission(result, self.skeleton, self.profile, trip)
                self.assertEqual(before['retainedMixedHead'], after['retainedMixedHead'])
                self.assertEqual(before['breastMorphSupport'], after['breastMorphSupport'])
                if sex == 'female':
                    self.assertTrue(after['breastMorphSupport']['head']['visibleByFileHiddenFlags'])
                    self.assertEqual(590, after['breastMorphSupport']['head']['nonzeroDeltaCount'])


if __name__ == '__main__':
    unittest.main()
