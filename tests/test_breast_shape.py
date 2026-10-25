"""Shape-only opt-in profile contracts; no game/physics/provider fixtures."""
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import breast_shape as breast
import surface_collar as surface


class BreastShape(unittest.TestCase):
    def setUp(self):
        load = lambda name: json.loads((ROOT / 'recipes' / name).read_text(encoding='utf-8'))
        self.profile = load('breast-shape.json')
        self.female, self.full, self.collar = [load(n) for n in
            ('female.json', 'full-body.json', 'surface-collars.json')]
        self.v = np.array([[8, 20, 94], [-8, 20, 94], [8, 20, 90], [-8, 20, 90],
                           [0, 20, 94], [8, 50, 94]], dtype=float)
        self.old = np.tile([0, 0, -16.], (len(self.v), 1))
        self.distance = np.array([3, 3, 0, 0, 3, 3.])

    def validate(self, **changes):
        values = dict(profile=self.profile, female_recipe=self.female,
                      full_recipe=self.full, collar_recipe=self.collar, slim=.9)
        values.update(changes)
        return breast.validate_profile(**values)

    def test_pinned_recipe_semantics_and_required_repair(self):
        self.validate()
        with self.assertRaisesRegex(ValueError, 'requires --surface-collars'):
            self.validate(collar_recipe=None)
        with self.assertRaisesRegex(ValueError, 'SLIM'):
            self.validate(slim=None)
        changed = copy.deepcopy(self.female)
        next(r for r in changed if r.get('morph') == breast.PUBLIC_MORPH)['parts'][0]['amount'] = 17
        with self.assertRaisesRegex(ValueError, 'source morph semantics'):
            self.validate(female_recipe=changed)
        changed = copy.deepcopy(self.collar)
        changed['collars'][0]['width'] = 3
        with self.assertRaisesRegex(ValueError, 'pinned surface collar'):
            self.validate(collar_recipe=changed)

    def test_prose_does_not_change_executable_semantic_hash(self):
        changed = copy.deepcopy(self.female)
        for row in changed:
            row['_'] = 'Different documentation'
        self.validate(female_recipe=changed)
        self.assertEqual(breast.semantic_sha256({'a': [1, {'_': 'text'}]}),
                         breast.semantic_sha256({'a': [1, {}]}))

    def test_invalid_coefficients_and_aliases_are_rejected(self):
        for value in (-.1, 1.1, float('nan'), float('inf'), True, '1'):
            bad = copy.deepcopy(self.profile)
            bad['coefficients']['mass'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.validate(profile=bad)
        bad = copy.deepcopy(self.profile)
        bad['publicMorph'] = 'CLAWProtoBreastMass'
        with self.assertRaisesRegex(ValueError, 'public morph'):
            self.validate(profile=bad)
        bad = copy.deepcopy(self.profile)
        bad['coefficients'] = dict.fromkeys(breast.CHANNELS, 0.)
        with self.assertRaisesRegex(ValueError, 'nonzero public BreastSize'):
            self.validate(profile=bad)
        for name in ('midlineStart', 'lowerTop'):
            for value in (True, False, '2', float('nan')):
                bad = copy.deepcopy(self.profile)
                bad['fields'][name] = value
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    self.validate(profile=bad)

    def test_empty_tiny_roi_and_nonfinite_composite_rejected_before_writes(self):
        for coefficients, bounds in [(dict.fromkeys(breast.CHANNELS, 0.), None),
                                      (dict.fromkeys(breast.CHANNELS, 1e-8), None),
                                      (self.profile['coefficients'], [[70, 70, 70], [80, 80, 80]])]:
            profile = copy.deepcopy(self.profile)
            profile['coefficients'] = coefficients
            if bounds is not None:
                profile['fields']['bounds'] = bounds
            delta, _, _ = breast.shape_fields(self.v, self.old, self.distance, profile)
            with self.subTest(coefficients=coefficients, bounds=bounds), self.assertRaisesRegex(ValueError, 'threshold'):
                breast.require_exportable_composite(delta)
        for value in (float('nan'), float('inf'), np.finfo(np.float64).max):
            with self.subTest(value=value), self.assertRaises(ValueError):
                breast.require_exportable_composite(np.array([[value, 0., 0.]]))
        profile = copy.deepcopy(self.profile)
        profile['fields']['massForward'] = np.finfo(np.float64).max
        profile['fields']['projectionForward'] = np.finfo(np.float64).max
        self.validate(profile=profile)  # Individual finite fields do not guarantee a finite sum.
        with np.errstate(over='ignore', invalid='ignore'):
            delta, _, _ = breast.shape_fields(self.v, self.old, self.distance, profile)
        with self.assertRaises(ValueError):
            breast.require_exportable_composite(delta)

    def test_real_pynifly_roundtrip_detects_dropped_public_morph(self):
        try:
            trip_type = breast.load_tripfile_type()
        except RuntimeError as exc:
            self.skipTest(str(exc))
        basis = np.zeros((3, 3))
        expected = ['CLAWFixtureOther', breast.PUBLIC_MORPH]
        with tempfile.TemporaryDirectory(prefix='claw-breast-trip-') as folder:
            nif = Path(folder) / 'candidate.nif'
            for amount in (0., breast.TRIP_COMPONENT_EPSILON * .99,
                           breast.TRIP_COMPONENT_EPSILON * 1.01):
                target = basis.copy()
                target[0, 1] = amount
                other = basis.copy()
                other[1, 0] = 1.
                trip = trip_type()
                # This is the real export API, including its cutoff and binary writer.
                trip.set_morphs('head', {breast.PUBLIC_MORPH: target,
                                       'CLAWFixtureOther': other}, basis)
                trip.write(str(nif.with_suffix('.tri')))
                if amount <= breast.TRIP_COMPONENT_EPSILON:
                    with self.subTest(amount=amount), self.assertRaisesRegex(ValueError, 'missing=.*CLAWTorsoBreastSize'):
                        breast.verify_serialized_morphs(nif, expected)
                else:
                    checked = breast.verify_serialized_morphs(nif, expected)
                    self.assertEqual(checked['publicMorphs'], sorted(expected))
                    self.assertEqual(len(checked['triSha256']), 64)
            with self.assertRaisesRegex(ValueError, 'extra=.*CLAWTorsoBreastSize'):
                breast.verify_serialized_morphs(nif, ['CLAWFixtureOther'])

    def test_support_anchors_midline_and_face_stay_fixed(self):
        delta, private, _ = breast.shape_fields(self.v, self.old, self.distance, self.profile)
        np.testing.assert_array_equal(delta[2:], 0)
        self.assertEqual(set(private), set(breast.CHANNELS))
        self.assertLess(np.linalg.norm(delta, axis=1).max(), 3.46)
        np.testing.assert_allclose(delta[0], [.2, 3.25, -1.15])

    def test_symmetric_field_and_linear_base_half_full_range(self):
        full, _, _ = breast.shape_fields(self.v, self.old, self.distance, self.profile)
        np.testing.assert_array_equal(full[0], full[1] * [-1, 1, 1])
        for value in (0., .5, 1.):
            profile = copy.deepcopy(self.profile)
            profile['coefficients'] = {name: value for name in breast.CHANNELS}
            delta, _, _ = breast.shape_fields(self.v, self.old, self.distance, profile)
            np.testing.assert_allclose(delta, value * full)

    def test_unpaired_donor_surface_is_not_forced_and_invalid_source_rejected(self):
        bad = self.v.copy()
        bad[1, 0] -= .1
        delta, _, pairs = breast.shape_fields(bad, self.old, self.distance, self.profile)
        self.assertEqual(pairs, [])
        self.assertGreater(np.linalg.norm(delta[0]), 0)
        with self.assertRaises(ValueError):
            breast.shape_fields(self.v, self.old[:-1], self.distance, self.profile)
        with self.assertRaises(ValueError):
            breast.shape_fields(self.v, self.old, np.full(len(self.v), -1.), self.profile)

    def test_common_boundary_checks_relative_body_bary_offset(self):
        v = np.array([[0., 0, 0], [1, 0, 0], [0, 1, 0]])
        bind = surface.Bindings(v, v, np.array([[0, 1, 2]]))
        collar = SimpleNamespace(anchors=np.arange(3), binding=bind)
        body = np.tile([0., .2, -.1], (3, 1))
        head = body.copy()
        self.assertEqual(breast.attachment_metrics(collar, body, head), {'0.0': 0., '0.5': 0., '1.0': 0.})
        # Zero head alone would reopen the join when a legacy body key survives.
        broken = breast.attachment_metrics(collar, body, np.zeros_like(head))
        self.assertGreater(broken['1.0'], .2)
        self.assertAlmostEqual(broken['0.5'], .5 * broken['1.0'])

    def test_adapter_replaces_existing_legacy_body_and_zero_fur(self):
        key = '>' + breast.PUBLIC_MORPH
        obj = lambda exists: SimpleNamespace(data=SimpleNamespace(shape_keys=
            SimpleNamespace(key_blocks={key: object()}) if exists else None))
        calls = {}
        session = SimpleNamespace(objects={'body': obj(True), 'fur_chest': obj(True), 'other': obj(False)},
            _put_delta=lambda name, key_name, values: calls.update({name: values.copy()}))
        fields = {name: np.zeros((3, 3)) for name in session.objects}
        breast.replace_fields(session, fields, key, 1e-8)
        self.assertEqual(set(calls), {'body', 'fur_chest'})
        np.testing.assert_array_equal(calls['body'], 0)
        np.testing.assert_array_equal(calls['fur_chest'], 0)

    def test_profile_neutral_topology_and_bounds_pins(self):
        v = np.array([[0., 0, 0], [1, 0, 0], [0, 1, 0]])
        faces = np.array([[0, 1, 2]])
        expected = surface.signature(v, faces)
        surface.validate_geometry(v, faces, expected, .001)
        with self.assertRaisesRegex(ValueError, 'topology'):
            surface.validate_geometry(v, faces[:, ::-1], expected, .001)
        with self.assertRaisesRegex(ValueError, 'bounds'):
            surface.validate_geometry(v + [.01, 0, 0], faces, expected, .001)


if __name__ == '__main__':
    unittest.main()
