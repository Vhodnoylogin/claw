from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
import sys
from tempfile import TemporaryDirectory
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'src/main/components/contact-profiles/python'))
from posed_support import Skin, compose_sex, read_paired_build, region_vertices


class PosedSupportExportTests(unittest.TestCase):
    def skin(self, z=0., reverse=False, bone='TailBone02'):
        identity = SimpleNamespace(rotation=np.eye(3), translation=[0, 0, 0], scale=1.)
        return Skin(SimpleNamespace(verts=[(0, 0, z), (1, 0, z), (0, 1, z)],
                                    tris=[(0, 2, 1) if reverse else (0, 1, 2)],
                                    bone_weights={bone: [(0, 1.), (1, 1.), (2, 1.)]},
                                    extra_data=lambda _: (),
                                    global_to_skin=identity, get_shape_skin_to_bone=lambda _: identity))

    def test_fitted_chunks_preserve_shape_identity_and_slot_membership(self):
        source = {'vertices': [0, 1, 2], 'sourceTriangleIndices': [0], 'fullRegionTriangles': [[0, 1, 2]]}
        region = {'sources': [dict(source, shape=name) for name in ('body', 'head')],
                  'points': [[0, 0, 0]] * 6, 'faces': [[0, 1, 2], [3, 4, 5]], 'padding': .0001}
        model = {'regions': {'male/TailBone02': region}, 'morphs': ['CLAWTailLength']}
        slot = {'node': 'TailBone02', 'male': {'partitionIndices': [0, 1, 2, 3, 4, 5], 'triangleIndices': [0, 1]}}
        low = {'body': self.skin(), 'head': self.skin()}
        high = {'body': self.skin(z=2.), 'head': self.skin()}
        records = {('body', 'CLAWTailLength', 0): SimpleNamespace(packed=(0, 1, 0), scale=.5)}
        result = compose_sex(model, [(105, slot), (106, slot)], 'male', low, high, records)
        self.assertEqual(result['slotIndexes'], [105, 106])
        self.assertEqual(result['memberships'], list(range(6)) * 2)
        self.assertEqual(result['fields'][0], ([0., 0., 2.], 0, 1))
        self.assertEqual(result['fields'][3], ([0., 0., 0.], 1, 0))
        self.assertEqual(result['deltas'], [(0, [0., .5, 0.])])
        slot['male']['triangleIndices'] = [-1, 0]
        with self.assertRaisesRegex(ValueError, 'invalid region triangle indices'):
            compose_sex(model, [(105, slot)], 'male', low, high, records)

    def test_endpoint_with_new_skin_binding_cannot_use_weight_interpolation(self):
        with self.assertRaisesRegex(ValueError, 'change actual pose skin'):
            self.skin().weight_delta(self.skin(bone='TailBone03'))

    def test_refuses_fitted_winding_that_does_not_describe_the_nif(self):
        source = {'shape': 'head', 'vertices': [0, 1, 2], 'sourceTriangleIndices': [0],
                  'fullRegionTriangles': [[0, 1, 2]]}
        with self.assertRaisesRegex(ValueError, 'triangle differs from its NIF'):
            region_vertices({'sources': [source]}, {'head': self.skin(reverse=True)})

    def test_pair_requires_the_exact_vr_model_and_unmodified_header(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            header = root / 'physics-fit-model.h'
            content = b'#pragma once\n'
            model = {'sha256': 'a' * 64, 'bytes': 12}
            receipt = {'status': 'offline-model-pair-generated-game-pending',
                       'profiles': {'vr': {'model': model}},
                       'pairedHeader': {'sha256': sha256(content).hexdigest(), 'bytes': len(content)}}
            (root / 'contact-profiles-build.json').write_text(json.dumps(receipt), encoding='utf-8')
            header.write_bytes(content)
            self.assertEqual(read_paired_build(root, model), content)
            with self.assertRaisesRegex(ValueError, 'Paired build and posed model differ'):
                read_paired_build(root, dict(model, bytes=13))
            header.write_bytes(b'#pragma late\n')
            with self.assertRaisesRegex(ValueError, 'header differs'):
                read_paired_build(root, model)


if __name__ == '__main__':
    unittest.main()
