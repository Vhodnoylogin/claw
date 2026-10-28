import sys
import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import head_isolation as isolation


class NeckIsolationTests(unittest.TestCase):
    def test_derived_bind_preserves_complete_scaled_rest_product(self):
        target = np.eye(4); target[:3, :3] *= 2; target[:3, 3] = [2, 4, 8]
        source = np.eye(4); source[:3, 3] = [1, 3, 7]
        bind = np.eye(4); bind[:3, :3] *= .5; bind[2, 3] = 9
        got = isolation.derived_bind(target, source, bind)
        np.testing.assert_allclose(target @ got, source @ bind, atol=1e-12)

    def test_collapse_preserves_foreign_p1_and_hand_weights_and_budget(self):
        names = [isolation.HEAD, 'NPC Jaw [Jaw]', 'NPC L Breast P1', 'NPC L Hand [RHnd]']
        old = np.asarray([[.25, .125, .125, .5]])
        new, donor = isolation.collapse_weights(old, names, set(names[:2]))
        np.testing.assert_array_equal(new[:, 2:4], old[:, 2:4])
        np.testing.assert_array_equal(new[:, donor], 0)
        self.assertEqual(new[0, -1], .375)
        self.assertEqual(int((new > 0).sum()), 3)

    def test_half_merge_error_is_explicit_and_not_hidden_by_normalization(self):
        old = np.asarray([[.5, float(np.float16(.0001)), .25]])
        new, _ = isolation.collapse_weights(old, [isolation.HEAD, 'Jaw', 'Spine'], {isolation.HEAD, 'Jaw'})
        self.assertNotEqual(float(new.sum()), float(old.sum()))
        self.assertEqual(new[0, 2], old[0, 2])

    def test_head_local_motion_is_removed_but_parent_translation_survives(self):
        rest_head = np.eye(4); rest_head[2, 3] = 10
        rest_neck = np.eye(4); rest_neck[2, 3] = 8
        source_bind = np.linalg.inv(rest_head)
        bind = isolation.derived_bind(rest_neck, rest_head, source_bind)
        globals_ = np.asarray([[rest_neck], [rest_neck.copy()], [rest_neck.copy()]])
        globals_[2, 0, 0, 3] += 5
        result = isolation.evaluate([[1., 2, 3]], [[1.]], globals_, bind[None], False)
        np.testing.assert_array_equal(result[0], result[1])
        np.testing.assert_allclose(result[2] - result[0], [[5, 0, 0]])


@unittest.skipUnless(os.environ.get('CLAW_VR_HEAD_ISOLATION_ROOT') and os.environ.get('CLAW_VR_COMPOSED_ROOT'),
                     'Explicit composed source and serialized Neck-candidate roots required')
class NativeNeckIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api, _, cls.Trip, _ = isolation.resource.dependencies()
        cls.source = Path(os.environ['CLAW_VR_COMPOSED_ROOT'])
        cls.candidate = Path(os.environ['CLAW_VR_HEAD_ISOLATION_ROOT']) / 'resources'
        cls.skeleton = cls.api.NifFile(str(isolation.resource.ROOT / 'assets/donors/skeleton.nif'))

    def inputs(self, sex='female', endpoint=0):
        source = self.api.NifFile(str(self.source / f'{sex}bodywerewolf_{endpoint}.nif'))
        for shape in source.shapes:
            if shape.name in isolation.visibility.load_profile()['hiddenShapes']:
                shape.flags |= isolation.resource.HIDDEN
        study = isolation.Study(source, self.skeleton)
        target = self.api.NifFile(str(self.candidate / sex / f'first-person_{endpoint}.nif'))
        added = set(target.nodes) - set(source.nodes)
        return source, study, target, added

    def test_four_actual_endpoints_preserve_protected_native_fields_and_tri(self):
        for sex in ('female', 'male'):
            for endpoint in (0, 1):
                with self.subTest(sex=sex, endpoint=endpoint):
                    source, study, target, added = self.inputs(sex, endpoint)
                    isolation.compare_native(source, target, study, added, self.skeleton)
                    self.assertEqual(isolation.resource.sha256(self.source / (sex + 'bodywerewolf.tri')),
                                     isolation.resource.sha256(self.candidate / sex / (sex + 'bodywerewolf.tri')))

    def test_native_readback_rejects_changed_neck_bind(self):
        source, study, target, added = self.inputs()
        shape = next(s for s in target.shapes if s.name == 'head')
        bind = isolation.rig.matrix(shape.get_shape_skin_to_bone(isolation.NECK))
        bind[0, 3] += .01
        shape.set_skin_to_bone_xform(isolation.NECK, isolation.rig._transform_buffer(self.api, bind))
        with self.assertRaisesRegex(ValueError, 'derived Neck bind'):
            isolation.compare_native(source, target, study, added, self.skeleton)

    def test_native_readback_rejects_changed_foreign_p1_weight(self):
        source, study, target, added = self.inputs()
        shape = next(s for s in target.shapes if s.name == 'head')
        bone = 'NPC L Breast P1'
        index, value = next((i, w) for i, w in shape.bone_weights[bone] if w > 0)
        shape.setShapeWeights(bone, [(index, float(np.float16(value * .5)))])
        # A fresh file read avoids PyNifly's cached pre-setter bone_weights map.
        with tempfile.TemporaryDirectory(prefix='foreign-weight-rejection-', dir=self.candidate.parent) as folder:
            self.assertEqual(Path(folder).resolve().parent, self.candidate.parent.resolve())
            changed = Path(folder) / 'changed.nif'
            target.filepath = str(changed)
            target.save()
            reloaded = self.api.NifFile(str(changed))
            with self.assertRaisesRegex(ValueError, 'packed weights differ'):
                isolation.compare_native(source, reloaded, study, added, self.skeleton, public_scratch=True)

    def test_numeric_rejection_writes_no_candidate_and_never_claims_verified(self):
        # Exercise the real fixture admission, MorphBench readback and build
        # control flow; replace only the numerical measurement with a P1 failure.
        bad = {name: {'packedSumMaxChange': 0., 'states': {'neutral': {
            'normalized': {'desiredReferenceError': {'max': 0.},
                           'pureP1MotionChange': {'max': 1.}}}}}
               for name in isolation.visibility.load_profile()['retainedTorsoShapes']}
        frozen = self.candidate.parents[2] / 'tool' / 'morphbench-3ddc3af'
        with tempfile.TemporaryDirectory(prefix='numeric-rejection-', dir=self.candidate.parent) as folder:
            self.assertEqual(Path(folder).resolve().parent, self.candidate.parent.resolve())
            out = Path(folder) / 'rejected'
            with patch.object(isolation, 'shape_study', return_value=bad), \
                    patch.object(isolation, 'graft_resource') as writer, \
                    patch.object(isolation, 'audit_joins') as joins, \
                    self.assertRaises(isolation.NumericPlanRejected):
                isolation.build(self.source, isolation.resource.ROOT / 'assets/donors/skeleton.nif',
                                out, frozen, write_candidate=True)
            writer.assert_not_called()
            joins.assert_not_called()
            report = isolation.resource.read_json(out / 'head-isolation-report.json')
            self.assertEqual(report['status'], 'REJECTED-numeric-plan-no-candidate')
            self.assertEqual(len(report['bodies']), 4)
            self.assertFalse((out / 'resources').exists())
            self.assertFalse(any('serializedCandidate' in row for row in report['bodies'].values()))

    def test_cli_numeric_rejection_is_nonzero(self):
        import audit_head_isolation
        argv = ['audit_head_isolation.py', '--body-root', str(self.source), '--morphbench', 'unused',
                '--out-dir', 'unused', '--write-candidate']
        with patch.object(sys, 'argv', argv), \
                patch.object(isolation, 'build', side_effect=isolation.NumericPlanRejected('injected P1 failure')), \
                self.assertRaises(SystemExit) as exit_status:
            audit_head_isolation.main()
        self.assertEqual(exit_status.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
