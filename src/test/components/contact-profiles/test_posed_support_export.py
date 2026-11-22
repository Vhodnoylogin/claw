from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'src/main/components/contact-profiles/python'))
from posed_support import HEAD, Skin, compose_sex, contract, read_paired_build, region_vertices, selected_slots, selected_source_shapes


class PosedSupportExportTests(unittest.TestCase):
    def skin(self, z=0., reverse=False, bone='TailBone02', weights=None):
        identity = SimpleNamespace(rotation=np.eye(3), translation=[0, 0, 0], scale=1.)
        return Skin(SimpleNamespace(verts=[(0, 0, z), (1, 0, z), (0, 1, z)],
                                    tris=[(0, 2, 1) if reverse else (0, 1, 2)],
                                    bone_weights=weights or {bone: [(0, 1.), (1, 1.), (2, 1.)]},
                                    extra_data=lambda _: (),
                                    global_to_skin=identity, get_shape_skin_to_bone=lambda _: identity))

    def detailed_layout(self):
        recipe = contract.read_recipes()['vr']
        slots = [{'node': group['node'], 'sexMask': group['sexMask']}
                 for group in recipe['supportRegions'] for _ in range(group['count'])]
        return {'supportProfile': recipe['supportProfile'], 'slots': slots}

    def test_expanded_default_and_explicit_archived_layout(self):
        model = self.detailed_layout()
        with patch.object(contract.host, 'validate_fitted_model'):
            full = selected_slots(model)
            archived = selected_slots(model, ear_tail_only=True)
        self.assertEqual([index for index, _ in full], [*range(20, 30), *range(88, 120)])
        self.assertEqual([slot['node'] for _, slot in full[:10]], [HEAD] * 10)
        self.assertEqual(full[10:], archived)

    def test_refuses_changed_owner_counts_masks_or_slot_order(self):
        with patch.object(contract.host, 'validate_fitted_model'):
            model = self.detailed_layout()
            model['slots'][20]['node'] = model['slots'][0]['node']
            with self.assertRaisesRegex(ValueError, 'both-sex head/ear/tail slot counts'):
                selected_slots(model)
            model = self.detailed_layout()
            model['slots'][20]['sexMask'] = 'female'
            with self.assertRaisesRegex(ValueError, 'both-sex head/ear/tail slot counts'):
                selected_slots(model)
            model = self.detailed_layout()
            model['slots'][20], model['slots'][0] = model['slots'][0], model['slots'][20]
            with self.assertRaisesRegex(ValueError, 'owner order'):
                selected_slots(model)
            model = self.detailed_layout()
            model['slots'][88], model['slots'][92] = model['slots'][92], model['slots'][88]
            with self.assertRaisesRegex(ValueError, 'owner order'):
                selected_slots(model, ear_tail_only=True)

    def test_native_shape_route_rejects_misassigned_or_additional_shapes(self):
        selected = [(20, {'node': HEAD}), (108, {'node': 'TailBone02'})]
        model = {'regions': {'male/' + HEAD: {'sources': [{'shape': 'head'}]},
                             'male/TailBone02': {'sources': [{'shape': 'body'}]}}}
        self.assertEqual(selected_source_shapes(model, selected, 'male'), {'body', 'head'})
        model['regions']['male/' + HEAD]['sources'] = [{'shape': 'body'}]
        with self.assertRaisesRegex(ValueError, 'must use the native head shape'):
            selected_source_shapes(model, selected, 'male')
        model['regions']['male/' + HEAD]['sources'] = [{'shape': 'head'}, {'shape': 'claws'}]
        with self.assertRaisesRegex(ValueError, 'must use the native head shape'):
            selected_source_shapes(model, selected, 'male')

    def test_head_preserves_jaw_influence_and_muzzle_field(self):
        field = 'CLAWHeadMuzzleLong'
        jaw = 'NPC Jaw [Jaw]'
        weights = {HEAD: [(0, .25), (1, 1.), (2, 1.)], jaw: [(0, .75)]}
        source = {'shape': 'head', 'vertices': [0, 1, 2], 'sourceTriangleIndices': [0],
                  'fullRegionTriangles': [[0, 1, 2]]}
        region = {'sources': [source], 'points': [[0, 0, 0]] * 3, 'faces': [[0, 1, 2]], 'padding': .0001}
        model = {'regions': {'male/' + HEAD: region}, 'morphs': [field]}
        slot = {'node': HEAD, 'male': {'partitionIndices': [0, 1, 2], 'triangleIndices': [0]}}
        low, high = {'head': self.skin(weights=weights)}, {'head': self.skin(z=2., weights=weights)}
        records = {('head', field, 0): SimpleNamespace(packed=(0, 1, 0), scale=.5)}
        result = compose_sex(model, [(20, slot)], 'male', low, high, records)
        self.assertEqual(result['bones'], [HEAD, jaw])
        self.assertEqual([(bone, weight) for bone, weight, _, _ in result['influences'][:2]], [(0, .25), (1, .75)])
        self.assertEqual(result['fields'][0], ([0., 0., 2.], 0, 1))
        self.assertEqual(result['deltas'], [(0, [0., .5, 0.])])

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
