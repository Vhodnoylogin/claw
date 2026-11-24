import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vr_coat_readback import verify_managed_fur


class VRCoatReadbackTests(unittest.TestCase):
    paths = ['Textures/Example/' + name + '.dds' for name in ('body', 'head', 'fur_back')]

    def sample(self):
        rows = [{'name': name, 'managed': True, 'diffusePath': path, 'diffuseResource': path.upper().replace('/', '\\')}
                for name, path in zip(('BODY', 'HEAD', 'fur_back'), self.paths, strict=True)]
        return {'schema': 1, 'ageMs': 100, 'surfaces': rows}

    def test_texture_objects_match_proven_paths_on_body_head_and_fur(self):
        proof = verify_managed_fur(self.sample(), self.paths)
        self.assertTrue(proof['materialTextureObjectsVerified'])

    def test_unmanaged_split_head_must_resolve_its_texture_too(self):
        audit = self.sample()
        head = audit['surfaces'][1]
        head.update(name='head_CLAWHead', managed=False)
        self.assertTrue(verify_managed_fur(audit, self.paths)['materialTextureObjectsVerified'])
        head['diffuseResource'] = None
        self.assertFalse(verify_managed_fur(audit, self.paths)['materialTextureObjectsVerified'])

    def test_missing_vfs_winner_or_matching_texture_object_refuses_the_claim(self):
        self.assertFalse(verify_managed_fur(self.sample(), self.paths[1:])['materialTextureObjectsVerified'])
        for resource in (None, 'textures/default.dds'):
            with self.subTest(resource=resource):
                audit = self.sample()
                audit['surfaces'][0]['diffuseResource'] = resource
                self.assertFalse(verify_managed_fur(audit, self.paths)['materialTextureObjectsVerified'])

    def test_stale_or_incomplete_sample_does_not_qualify(self):
        audit = self.sample()
        audit['surfaces'].pop()
        self.assertFalse(verify_managed_fur(audit, self.paths)['materialTextureObjectsVerified'])
        with self.assertRaisesRegex(ValueError, 'current'):
            verify_managed_fur({**audit, 'ageMs': 2001}, self.paths)
