"""Selective anatomical visibility, graph restriction and actual byte regressions."""
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import selective_visibility as visibility
import body_resource as resource


class SelectiveVisibilityTests(unittest.TestCase):
    def fixture(self, hidden=False):
        shapes = []
        names = ['body', 'head', 'head_CLAWHead', 'eyes']
        for index, name in enumerate(names):
            weights = {bone: [(0, 1.)] * count for bone, count in zip(resource.HAND_BONES, [846, 1571])} if name == 'body' else {}
            shapes.append(SimpleNamespace(name=name, id=index, flags=int(hidden and name in names[2:]),
                                          parent=None, verts=[(0., 0., 0.)], tris=[(0, 0, 0)],
                                          textures={'Diffuse': 'original-head.dds' if name.startswith('head') else 'original-body.dds'},
                                          bone_weights=weights, extra_data=lambda _: [SimpleNamespace(name='BODYTRI', string_data='actors\\werewolfbeast\\character assets\\femalebodywerewolf.tri')]))
        nif = SimpleNamespace(shapes=shapes, nodes={name: s for name, s in zip(names, shapes)}, game='SKYRIMSE')
        trip = SimpleNamespace(shapes={name: {} for name in names})
        trip.shapes['head'] = {'CLAWTorsoBreastSize': [(0, (1., 0., 0.))]}
        profile = {'hiddenShapes': names[2:], 'retainedTorsoShapes': names[:2],
                   'bodies': {'female': {'shapeCount': 4, 'nodeCount': 4, 'breastSupport': {'head': 1}}}}
        return nif, trip, profile

    def test_reviewed_selection_keeps_the_original_head_material_torso(self):
        profile = visibility.load_profile()
        self.assertIn('head_CLAWHead', profile['hiddenShapes'])
        self.assertNotIn('head', profile['hiddenShapes'])
        self.assertIn('head', profile['retainedTorsoShapes'])
        self.assertEqual(450, profile['bodies']['female']['breastSupport']['head'])
        for hidden in (False, True):
            nif, trip, profile = self.fixture(hidden)
            audit = visibility.admission(nif, trip, profile, 'female', hidden=hidden)
            self.assertTrue(audit['shapes']['head']['visibleByFileFlags'])
            self.assertEqual('original-head.dds', audit['shapes']['head']['textures']['Diffuse'])
            self.assertEqual(not hidden, audit['shapes']['head_CLAWHead']['visibleByFileFlags'])

    def test_third_person_or_unspecified_dispatch_is_refused(self):
        for graph in ('third-person', 'world', '', None):
            with self.subTest(graph=graph), self.assertRaisesRegex(ValueError, 'first-person graph'):
                visibility.resource_name(graph, 'female', 0)
        for sex, endpoint in [('unknown', 0), ('female', -1), ('male', 2), ('female', True), ('male', .3)]:
            with self.subTest(sex=sex, endpoint=endpoint), self.assertRaises(ValueError):
                visibility.resource_name('first-person', sex, endpoint)
        self.assertEqual('female/first-person_1.nif', visibility.resource_name('first-person', 'female', 1))

    def test_a_head_substring_cannot_admit_torso(self):
        nif, trip, profile = self.fixture()
        profile['hiddenShapes'].append('head')
        with self.assertRaisesRegex(ValueError, 'retained torso'):
            visibility.admission(nif, trip, profile, 'female')

    def test_any_hidden_breast_support_is_refused(self):
        nif, trip, profile = self.fixture()
        trip.shapes['head_CLAWHead']['CLAWTorsoBreastSize'] = [(0, (0., 1., 0.))]
        with self.assertRaisesRegex(ValueError, 'breast morph support'):
            visibility.admission(nif, trip, profile, 'female')

    def test_hidden_hand_support_is_refused(self):
        nif, trip, profile = self.fixture()
        nif.shapes[2].bone_weights[resource.HAND_BONES[0]] = [(0, 1.)]
        with self.assertRaisesRegex(ValueError, 'hand geometry'):
            visibility.admission(nif, trip, profile, 'female')

    def test_ancestor_culling_of_retained_torso_is_refused(self):
        nif, trip, profile = self.fixture(True)
        nif.shapes[1].parent = SimpleNamespace(name='hidden-root', flags=1, parent=None)
        with self.assertRaisesRegex(ValueError, 'ancestor visibility'):
            visibility.admission(nif, trip, profile, 'female', hidden=True)

    def test_missing_support_or_shape_is_refused(self):
        nif, trip, profile = self.fixture()
        del trip.shapes['head']['CLAWTorsoBreastSize']
        with self.assertRaisesRegex(ValueError, 'breast morph support changed'):
            visibility.admission(nif, trip, profile, 'female')
        nif, trip, profile = self.fixture()
        nif.shapes[-1].name = 'unexpected'
        with self.assertRaisesRegex(ValueError, 'Missing reviewed'):
            visibility.admission(nif, trip, profile, 'female')


@unittest.skipUnless(os.environ.get('CLAW_VR_VISIBILITY_ROOT') and os.environ.get('CLAW_VR_COMPOSED_ROOT'),
                     'Supply explicitly built selective resources and the pinned composed source root')
class NativeSelectiveVisibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(os.environ['CLAW_VR_VISIBILITY_ROOT'])
        cls.source = Path(os.environ['CLAW_VR_COMPOSED_ROOT'])
        cls.report = resource.read_json(cls.root / 'first-person-visibility-report.json')
        cls.profile = visibility.load_profile()
        cls.api, _, cls.TripFile, _ = resource.dependencies()

    def test_copied_source_texture_mutation_during_dependency_loading_is_refused(self):
        """Reproduce the admission race without touching any original source."""
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            copied = directory / 'copied-source'
            copied.mkdir()
            for sex in ('female', 'male'):
                for name in (f'{sex}bodywerewolf_0.nif', f'{sex}bodywerewolf_1.nif', f'{sex}bodywerewolf.tri'):
                    shutil.copy2(self.source / name, copied / name)
            changed = copied / 'femalebodywerewolf_0.nif'
            expected = self.profile['bodies']['female']['nifSha256'][0]
            self.assertEqual(expected, resource.sha256(changed))
            original_dependencies = resource.dependencies

            def mutate_during_dependency_load(*args, **kwargs):
                before = changed.read_bytes()
                self.assertIn(b'head.dds', before)
                changed.write_bytes(before.replace(b'head.dds', b'heax.dds'))
                self.assertNotEqual(expected, resource.sha256(changed))
                return original_dependencies(*args, **kwargs)

            target = directory / 'refused-candidate'
            with mock.patch.object(resource, 'dependencies', side_effect=mutate_during_dependency_load):
                with self.assertRaisesRegex(ValueError, 'changed after admission'):
                    visibility.build(copied, resource.ROOT / 'assets/donors/skeleton.nif', target)
            self.assertFalse(target.exists(), 'A changed admitted source must fail before output creation')
            self.assertEqual(expected, resource.sha256(self.source / changed.name))

    def test_all_four_endpoints_change_only_the_eleven_hidden_bits(self):
        self.assertEqual('offline-first-person-visibility-candidate', self.report['status'])
        self.assertFalse(self.report['installable'])
        self.assertEqual([], self.report['selection']['thirdPersonOverrides'])
        self.assertFalse((self.root / 'meshes').exists())
        for sex in ('female', 'male'):
            for endpoint in (0, 1):
                with self.subTest(sex=sex, endpoint=endpoint):
                    receipt = self.report['bodies'][sex]['endpoints'][str(endpoint)]
                    original = self.source / f'{sex}bodywerewolf_{endpoint}.nif'
                    target = self.root / receipt['resource']
                    self.assertEqual(11, resource.verify_bytes(original.read_bytes(), target.read_bytes(), receipt['editLedger']))
                    self.assertEqual(set(self.profile['hiddenShapes']), {row['shape'] for row in receipt['editLedger']})
                    self.assertEqual(receipt['nifSha256'], resource.sha256(target))
                    self.assertEqual(self.profile['bodies'][sex]['nifSha256'][endpoint], resource.sha256(original))

    def test_native_breast_hands_material_and_shared_tri_survive_both_endpoints(self):
        for sex, pin in self.profile['bodies'].items():
            tri = self.root / self.report['bodies'][sex]['tri']
            self.assertEqual(pin['triSha256'], resource.sha256(tri))
            self.assertEqual((self.source / tri.name).read_bytes(), tri.read_bytes())
            for endpoint in (0, 1):
                with self.subTest(sex=sex, endpoint=endpoint):
                    original = self.api.NifFile(str(self.source / f'{sex}bodywerewolf_{endpoint}.nif'))
                    result = self.api.NifFile(str(self.root / visibility.resource_name('first-person', sex, endpoint)))
                    visibility.compare_readback(original, result, self.profile['hiddenShapes'])
                    _, trip = resource.tri_contract(self.TripFile, tri, result, pin['publicMorphCount'], include_trip=True)
                    actual = visibility.admission(result, trip, self.profile, sex, hidden=True)
                    self.assertEqual(pin['breastSupport'], actual['visibleBreastMorphSupport'])
                    self.assertIn('head.dds', actual['shapes']['head']['textures']['Diffuse'])
                    self.assertTrue(actual['shapes']['head']['visibleByFileFlags'])


if __name__ == '__main__':
    unittest.main()
