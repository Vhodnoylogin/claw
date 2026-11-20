import unittest

import numpy as np

from posed_contact import compare_support, native_vector, owner_support, read_pose, world_matrix


def rig_transform():
    return world_matrix({"rotationRowMajor": [0, -1, 0, 1, 0, 0, 0, 0, 1],
                         "translation": [5478, -17284, 4529], "scale": 1.13})


class PosedContactControls(unittest.TestCase):
    def test_owner_inverse_applies_world_scale_and_ancestry_once(self):
        owner = rig_transform()
        driver_local = np.eye(4)
        driver_local[2, 3] = 2
        frames = {"owner": owner, "driver": owner @ driver_local}
        points = np.array([[0., 0., 0.], [2., 0., 0.], [2., 1., 0.]])
        weights = {"owner": [1., .125, 0.], "driver": [0., .375, 1.]}
        binds = dict.fromkeys(weights, np.eye(4))
        posed = owner_support(points, weights, binds, np.eye(4), frames, "owner")
        np.testing.assert_allclose(posed, [[0, 0, 0], [2, 0, 1.5], [2, 1, 2]], atol=1e-11, rtol=0)
        equal = compare_support(points, points, [[0, 1, 2]], 1e-4)
        self.assertEqual(equal["static"], equal["refit"])
        result = compare_support(points, posed, [[0, 1, 2]], 1e-4)
        self.assertGreater(result["static"]["maxAssignedExcess"], 1.)
        self.assertLessEqual(result["refit"]["maxAssignedExcess"], 1e-12)

    def test_missing_influential_bone_refuses(self):
        weights = {"owner": [1.], "pelvis": [.0001]}
        with self.assertRaisesRegex(ValueError, "Missing influential bone.*pelvis"):
            owner_support([[0, 0, 0]], weights, {}, np.eye(4), {"owner": rig_transform()}, "owner")

    def test_pose_binding_requires_full_normalized_vector(self):
        sample = {"phase": "skse_main_thread_task", "view": "third_person", "actor": 0xFF00010A,
                  "base": 0x0B000800, "runtimeHandle": 1112350, "loadEpoch": 2, "rootToken": 5,
                  "qpcBegin": 10, "qpcEnd": 11, "sex": 0, "weight": 50, "nodes": []}
        pose = {"schema": "claw-vr-npc-pose/1", "status": "ready", "nonce": 5, "sequence": 0,
                "pid": 7, "qpcFrequency": 100, "sample": sample}
        vector = {**sample, "pid": 7, "sequence": 0, "weight": .5,
                  "sex": "male", "modelIdentity": "fixture", "morphs": {"one": .15, "two": 0}}
        model = {"modelIdentity": "fixture", "morphs": ["one", "two"]}
        self.assertEqual(read_pose(pose, vector, model)[:3], ("male", {"one": .15, "two": 0}, .5))
        for changed in ({"morphs": {"one": .15}}, {"morphs": {"one": float("nan"), "two": 0}}, {"weight": 50}):
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, "explicit normalized morphs"):
                read_pose(pose, {**vector, **changed}, model)
        with self.assertRaisesRegex(ValueError, "does not belong"):
            read_pose(pose, {**vector, "rootToken": 6}, model)

    def test_native_morphs_keep_effective_values_until_validation(self):
        sample = {"phase": "skse_main_thread_task", "view": "third_person", "actor": 0xFF00010A,
                  "base": 0x0B000800, "runtimeHandle": 1112350, "loadEpoch": 2, "rootToken": 5,
                  "qpcBegin": 10, "qpcEnd": 11, "sex": 0, "weight": 75, "nodes": []}
        pose = {"schema": "claw-vr-npc-pose/1", "status": "ready", "nonce": 5, "sequence": 0,
                "pid": 7, "qpcFrequency": 100, "sample": sample}
        model = {"modelIdentity": "fixture", "morphs": ["one"]}
        with self.assertRaisesRegex(ValueError, "Typed native effective morph vector"):
            native_vector(model, pose)
        sample["effectiveMorphs"] = {"one": -.2}
        vector = native_vector(model, pose)
        self.assertEqual(vector["morphs"], {"one": -.2})
        self.assertEqual(vector["weight"], .75)
        with self.assertRaisesRegex(ValueError, "explicit normalized morphs"):
            read_pose(pose, vector, model)


if __name__ == "__main__":
    unittest.main()
