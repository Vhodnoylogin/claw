from types import SimpleNamespace
import unittest

from avatar_torso import clearance, observation_plan, retained_torso


def pose(position):
    return {'rotation': [[1, 0, 0], [0, 1, 0], [0, 0, 1]], 'position': position, 'scale': 1.0}


def case():
    bind = SimpleNamespace(rotation=[[1, 0, 0], [0, 1, 0], [0, 0, 1]], translation=[0, 0, 0], scale=1.0)
    shape = SimpleNamespace(name='head', verts=[[-4, -4, 0], [4, -4, 0], [0, 4, 0]], tris=[(0, 1, 2)],
                            bone_weights={'neck': [(0, 1.0), (1, 1.0), (2, 0.5)], 'spine': [(2, 0.5)]},
                            global_to_skin=bind, get_shape_skin_to_bone=lambda _: bind)
    records = {('head', 'CLAWTorsoNeckGirth', i): SimpleNamespace(packed=(0, 0, 2), scale=1.0) for i in range(3)}
    sample = {'phase': 'PostVrikPostHiggs', 'shapes': [{'name': 'HEAD', 'skinned': True, 'ancestorCull': False}],
              'bones': {'neck': {'world': pose([50, 20, 0])}, 'spine': {'world': pose([50, 20, 0])}},
              'camera': pose([50, 20, 3]), 'nearLeft': 2.0, 'effectiveMorphs': {'CLAWTorsoNeckGirth': 0.0}}
    return shape, records, sample


class AvatarTorsoTests(unittest.TestCase):
    def test_native_extension_uses_torso_palette_and_matches_its_typed_link(self):
        shape, records, sample = case()
        virtual_tri = 'Meshes/Actors/WerewolfBeast/CLAW/FirstPerson/male/Body.tri'
        with self.assertRaisesRegex(ValueError, 'native torso capture extension'):
            clearance(shape, records, sample, virtual_tri=virtual_tri)
        sample.update(torsoCaptureVersion=1, torsoBones=sample['bones'],
                      torsoBodyTri=r'actors\werewolfbeast\claw\firstperson\male\body.tri')
        sample['bones'] = {}
        self.assertTrue(clearance(shape, records, sample, virtual_tri=virtual_tri)['torsoSeparatesFromBall'])
        sample['torsoBodyTri'] = sample['torsoBodyTri'].replace('male', 'female')
        with self.assertRaisesRegex(ValueError, 'BODYTRI differs'):
            clearance(shape, records, sample, virtual_tri=virtual_tri)

    def test_rejects_world_tri_for_named_vr_mesh(self):
        with self.assertRaisesRegex(ValueError, 'namespaced VR Body.tri path'):
            retained_torso({}, {'virtualPath': 'Meshes/Actors/WerewolfBeast/Character Assets/MaleBodyWereWolf.tri'}, None)

    def test_rejects_out_of_range_tri_index_even_with_zero_effective_morph(self):
        shape, records, sample = case()
        records['head', 'CLAWTorsoNeckGirth', 3] = records['head', 'CLAWTorsoNeckGirth', 0]
        with self.assertRaisesRegex(ValueError, 'TRI index is outside the retained torso'):
            clearance(shape, records, sample)

    def test_triangle_interior_and_morph_change_the_camera_ball_margin(self):
        shape, records, sample = case()
        expected = {'shape': 'head', 'vertices': 3, 'triangles': 1,
                    'bones': ['neck', 'spine'], 'morphs': ['CLAWTorsoNeckGirth']}
        self.assertEqual(observation_plan(shape, records), expected)
        neutral = clearance(shape, records, sample)
        self.assertEqual(neutral['leftCameraBallMarginGu'], 1.0)
        self.assertTrue(neutral['torsoSeparatesFromBall'])
        sample['effectiveMorphs']['CLAWTorsoNeckGirth'] = 1.0
        changed = clearance(shape, records, sample)
        self.assertEqual(changed['leftCameraBallMarginGu'], -1.0)
        self.assertFalse(changed['torsoSeparatesFromBall'])
        self.assertFalse(changed['renderedPixelsVerified'])

    def test_rejects_incomplete_or_culled_observations(self):
        shape, records, sample = case()
        sample['bones'].pop('spine')
        with self.assertRaisesRegex(ValueError, 'Missing influential torso bones: spine'):
            clearance(shape, records, sample)
        shape, records, sample = case()
        sample.pop('effectiveMorphs')
        with self.assertRaisesRegex(ValueError, 'effective TRI values'):
            clearance(shape, records, sample)
        shape, records, sample = case()
        sample['shapes'][0]['ancestorCull'] = True
        with self.assertRaisesRegex(ValueError, 'unculled retained skinned torso'):
            clearance(shape, records, sample)


if __name__ == '__main__':
    unittest.main()
