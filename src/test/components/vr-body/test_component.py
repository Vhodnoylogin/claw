"""Offline current-body composition checks; never manager/engine/game calls."""
from pathlib import Path
import importlib.util
import itertools
import json
import os
import sys
import unittest
import numpy as np

REPO = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location('claw_vr_component_build', REPO/'src/main/components/vr-body/build.py')
component = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(component)


class CompositionPolicyTests(unittest.TestCase):
    def test_namespace_separates_every_sex_endpoint_from_world_assets(self):
        paths = {component.resource_paths(s, e) for s in ('male', 'female') for e in (None, 0, 1)}
        self.assertEqual(len(paths), 6)
        self.assertTrue(all('/CLAW/FirstPerson/' in p and 'Character Assets' not in p for p in paths))
        for sex in ('male', 'female'):
            self.assertTrue(component.bodytri_path(sex).startswith('actors\\werewolfbeast\\claw\\firstperson\\'))
        for sex, endpoint in [('unknown', 0), ('male', True), ('female', 2)]:
            with self.assertRaises(ValueError): component.resource_paths(sex, endpoint)

    def test_affine_box_encloses_all_corners_not_just_symmetric_endpoints(self):
        matrices = np.asarray([[[[1., -.3, .5, 2], [-.2, 1, .1, -1], [0, 0, 1, .5]],
                                [[.5, .1, 0, -.5], [0, .3, 0, 1], [.2, 0, 1, 0]]]])
        vertices = np.asarray([[1., 2, 3], [-3., .5, 2]])
        fields = [np.asarray([[.4, -.7, 1], [1, .2, -.3]]), np.asarray([[-1, .1, -.5], [-.6, -.8, 1]])]
        bound = component.affine_box_bound(matrices, vertices, fields)
        for corner in itertools.product((0, 1), repeat=2):
            points = vertices + sum((a*b for a, b in zip(corner, fields)), np.zeros_like(vertices))
            actual = np.einsum('pvij,vj->pvi', matrices[..., :3], points) + matrices[..., 3]
            self.assertLessEqual(float(np.linalg.norm(actual, axis=-1).max()), bound)

    def test_affine_bound_includes_translation_and_zero_padding(self):
        zero = np.zeros((1, 1, 3, 4)); vertices = np.zeros((1, 3))
        self.assertGreater(component.affine_box_bound(zero, vertices, []), 0)
        zero[0, 0, :, 3] = [3, 4, 0]
        self.assertGreaterEqual(component.affine_box_bound(zero, vertices, []), 5)

    def test_nonfinite_or_wrong_vertex_directions_reject(self):
        matrix = np.zeros((1, 2, 3, 4)); vertices = np.zeros((2, 3))
        for field in [np.full((2, 3), np.nan), np.zeros((1, 3))]:
            with self.assertRaises(ValueError): component.affine_box_bound(matrix, vertices, [field])

    def test_unqualified_reference_path_cannot_be_a_world_bodytri(self):
        with self.assertRaisesRegex(ValueError, 'namespace'):
            component.namespace_bodytri(b'', 'source.tri', 'actors\\werewolfbeast\\character assets\\malebodywerewolf.tri')

    def test_complete_field_tuple_map_cannot_silently_omit_directions(self):
        field = np.ones((2, 3)); other = np.zeros((2, 3))
        got = component.shape_fields({('body', 'new-current-morph'): field, ('head', 'another'): other}, 'body')
        self.assertEqual(len(got), 1); np.testing.assert_array_equal(got[0], field)

    def test_protected_cards_stay_whole_without_touching_other_cards(self):
        faces = np.asarray([[0, 1, 2], [1, 3, 2], [4, 5, 6]])
        protected = np.asarray([True, False, False, False, False, False, False])
        got = component.protect_selection(faces, np.ones(3, bool), protected, True)
        np.testing.assert_array_equal(got, [False, False, True])
        surface = component.protect_selection(faces, np.ones(3, bool), protected, False)
        np.testing.assert_array_equal(surface, [False, True, True])


@unittest.skipUnless(os.environ.get('CLAW_VR_COMPONENT_ROOT'), 'Explicit built component candidate required')
class NativeCurrentCompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(os.environ['CLAW_VR_COMPONENT_ROOT'])
        cls.profile = component.resource.read_json(component.HERE/'current-010.json')
        cls.api, _, cls.Trip, _ = component.resource.dependencies(Path(os.environ['CLAW_VR_COMPONENT_PYNIFLY']), Path(os.environ['CLAW_VR_COMPONENT_MORPHBENCH']))
        cls.skeleton = cls.api.NifFile(str(REPO/'src/main/resources/donors/skeleton.nif'))
        cls.head = component.resource.head_descendant_names(cls.skeleton, component.isolation.HEAD)

    def test_six_real_resources_match_manifest_and_namespace(self):
        manifest = component.resource.read_json(self.root/'install-manifest.json')
        self.assertEqual(len(manifest['files']), 6)
        self.assertEqual(manifest['worldOverrides'], [])
        self.assertFalse(manifest['nativeDispatchQualified'])
        self.assertFalse(manifest['defaultInstallEnabled'])
        for rel, digest in manifest['files'].items():
            self.assertEqual(component.resource.sha256(self.root/'resources'/rel), digest)
        for sex in ('female', 'male'):
            tri = self.root/'resources'/component.resource_paths(sex)
            for endpoint in (0, 1):
                with self.subTest(sex=sex, endpoint=endpoint):
                    nif = self.api.NifFile(str(self.root/'resources'/component.resource_paths(sex, endpoint)))
                    receipt = component.verify_first_person(nif, self.Trip, tri, sex, self.profile, self.head)
                    self.assertEqual(receipt['visibleHeadSubtreeWeights'], 0)
                    self.assertEqual(receipt['publicMorphCount'], 31 if sex == 'female' else 30)

    def test_actual_new_split_preserves_current_tri_material_uv_and_skin(self):
        report = component.resource.read_json(self.root/'build-report.json')
        for sex in ('female', 'male'):
            source = next(Path(p) for p in report['inputSha256'] if Path(p).name == sex+'bodywerewolf_0.nif')
            tri = source.with_name(sex+'bodywerewolf.tri')
            nif = self.api.NifFile(str(source)); raw = self.Trip.from_filepath(str(tri)).shapes
            fields, _ = component.morph_quality.decode_fields(tri.read_bytes(), raw, {s.name: len(s.verts) for s in nif.shapes})
            plan, _ = component.anatomical_plan(nif, fields, self.head, self.profile['protectedMorphs'][sex])
            receipt = component.head_split.verify(self.api, self.Trip, source, self.root/sex/'split.nif', tri, self.root/sex/'split.tri', plan)
            self.assertEqual(receipt['publicMorphCount'], self.profile['publicMorphCount'][sex])
            self.assertTrue(all(row['exactMaterialsBindsUvNormals'] for row in receipt['shapes'].values()))

    def test_hiding_retained_torso_is_rejected_on_actual_candidate(self):
        sex = 'female'; tri = self.root/'resources'/component.resource_paths(sex)
        nif = self.api.NifFile(str(self.root/'resources'/component.resource_paths(sex, 0)))
        next(s for s in nif.shapes if s.name == 'body').flags |= component.resource.HIDDEN
        with self.assertRaisesRegex(ValueError, 'visibility'):
            component.verify_first_person(nif, self.Trip, tri, sex, self.profile, self.head)


if __name__ == '__main__': unittest.main()
