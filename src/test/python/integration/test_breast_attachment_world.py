"""Synthetic custody checks for the co-sampled bones and effective morphs."""

import copy
import importlib.util
from pathlib import Path
import unittest

import numpy as np

from breast_attachment_world import compare, deformation, observe, request


FIXTURE_SPEC = importlib.util.spec_from_file_location(
    'attachment_fsmp_fixture', Path(__file__).resolve().parents[1] / 'physics/test_fsmp_probe.py')
FIXTURE = importlib.util.module_from_spec(FIXTURE_SPEC)
FIXTURE_SPEC.loader.exec_module(FIXTURE)
BASELINE = FIXTURE.fixture()['baseline']
REFERENCE, BASE = '0xFF001234', '0x000A2C90'
NAMES = ('NPC Head [Head]', 'NPC Spine2 [Spn2]', 'NPC L Breast P1', 'NPC R Breast P1')
MORPHS = ('CLAWTorsoBreastSize', 'CLAWTorsoChestSize')


def packet():
    raw = copy.deepcopy(BASELINE)
    raw['nodes'] = [node for node in raw['nodes'] if node['name'] in NAMES]
    ref = raw['refs'][0]
    ref['form'] = REFERENCE
    ref['actor']['weight'].update(rawNPCWeight=100., normalizedNPCWeight=1.)
    raw['skee'] = [{
        'form': REFERENCE, 'identity': copy.deepcopy(ref['identity']),
        'rootIdentity': copy.deepcopy(ref['rootIdentity']), 'status': 'available',
        'provider': {'status': 'available', 'interfaceVersion': 5, 'interfaceEpoch': 1},
        'morphs': [{'name': name, 'status': 'available',
                    'keys': {'status': 'available', 'truncated': False},
                    'aggregate': {'method': 'GetBodyMorphs', 'status': 'available', 'value': value}}
                   for name, value in zip(MORPHS, (.25, 0), strict=True)],
    }]
    return raw


def read(raw, reference=REFERENCE, base=BASE, names=NAMES, morphs=MORPHS):
    return observe(raw, reference, base, names, morphs)


class BreastAttachmentWorldTests(unittest.TestCase):
    def test_requests_exact_actor_nodes_and_provider_in_one_snapshot(self):
        result = request(REFERENCE, NAMES, MORPHS)
        self.assertEqual(result['kind'], 'world_observer')
        self.assertEqual(result['refs'], [REFERENCE])
        self.assertIs(result['actors'], True)
        self.assertEqual(result['nodes'], [{'ref': REFERENCE, 'name': name, 'firstPerson': False} for name in NAMES])
        self.assertEqual(result['skee'], {'refs': [REFERENCE], 'morphs': list(MORPHS)})

    def test_returns_co_sampled_values_without_mutating_the_raw_packet(self):
        raw = packet()
        original = copy.deepcopy(raw)
        output = read(raw)
        self.assertEqual(raw, original)
        self.assertTrue({'guard', 'sample', 'time', 'nodes', 'root', 'morphs'} <= output.keys())
        self.assertEqual(output['sample'], raw['sampleId'])
        self.assertEqual(output['time'], raw['producerMonotonicNs'])
        self.assertEqual(set(output['nodes']), set(NAMES))
        self.assertEqual(output['morphs'], {MORPHS[0]: .25, MORPHS[1]: 0})

    def test_guard_changes_with_session_and_coherent_root_replacement(self):
        raw = packet()
        original = read(raw)['guard']
        raw['sampleId'] += 1
        raw['producerMonotonicNs'] += 100
        self.assertEqual(read(raw)['guard'], original)
        raw['sessionId'] = 'different-observer-session'
        self.assertNotEqual(read(raw)['guard'], original)
        raw['sessionId'] = 'synthetic-observer'
        for row in (*raw['refs'], *raw['nodes'], *raw['skee']):
            row['rootIdentity'] = dict(row['rootIdentity'], sampledRootToken=77)
        replaced = read(raw)['guard']
        self.assertNotEqual(replaced, original)
        raw['skee'][0]['provider']['interfaceEpoch'] += 1
        self.assertNotEqual(read(raw)['guard'], replaced)

    def test_wrong_actor_root_or_world_are_refused(self):
        changes = (
            lambda raw: raw.update(sessionId=''),
            lambda raw: raw.update(loadGeneration=8),
            lambda raw: raw.update(quality='partial'),
            lambda raw: raw['refs'][0]['actor'].update(race='0x00013745'),
            lambda raw: raw['refs'][0]['actor'].update(sex=0),
            lambda raw: raw['refs'][0]['actor']['weight'].update(rawNPCWeight=99.),
            lambda raw: raw['nodes'][0].update(firstPerson=True),
            lambda raw: raw['nodes'][0].update(identity=dict(raw['nodes'][0]['identity'], runtimeHandle=42)),
            lambda raw: raw['nodes'][0].update(rootIdentity=dict(raw['nodes'][0]['rootIdentity'], sampledRootToken=42)),
            lambda raw: raw['skee'][0].update(form='0xFF001235'),
            lambda raw: raw['skee'][0]['identity'].update(runtimeHandle=42),
            lambda raw: raw['skee'][0]['rootIdentity'].update(sampledRootToken=42),
        )
        for index, change in enumerate(changes):
            raw = packet()
            change(raw)
            with self.subTest(change=index), self.assertRaises(ValueError):
                read(raw)
        for args in ({'reference': '0xFF001235'}, {'base': '0x000A2C91'}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                read(packet(), **args)

    def test_missing_truncated_duplicate_or_unavailable_observations_are_refused(self):
        changes = (
            lambda raw: raw.pop('skee'),
            lambda raw: raw['skee'].append(copy.deepcopy(raw['skee'][0])),
            lambda raw: raw['skee'][0].update(status='unavailable'),
            lambda raw: raw['skee'][0].pop('provider'),
            lambda raw: raw['skee'][0].update(provider=None),
            lambda raw: raw['skee'][0]['provider'].update(status='unavailable'),
            lambda raw: raw['skee'][0]['provider'].update(interfaceVersion=3),
            lambda raw: raw['skee'][0]['provider'].update(interfaceEpoch=0),
            lambda raw: raw['skee'][0]['morphs'].pop(),
            lambda raw: raw['skee'][0]['morphs'][1].update(name=MORPHS[0]),
            lambda raw: raw['skee'][0]['morphs'][0].update(name='CLAWTorsoFlankWidth'),
            lambda raw: raw['skee'][0]['morphs'][0].update(status='unavailable'),
            lambda raw: raw['skee'][0]['morphs'][0].update(aggregate=None, value=.25),
            lambda raw: raw['skee'][0]['morphs'][0].pop('aggregate'),
            lambda raw: raw['skee'][0]['morphs'][0]['aggregate'].update(status='unavailable'),
            lambda raw: raw['skee'][0]['morphs'][0]['aggregate'].update(method='SynthesizedFromKeys'),
            lambda raw: raw['skee'][0]['morphs'][0]['keys'].update(truncated=True),
            lambda raw: raw['nodes'].pop(),
            lambda raw: raw['nodes'][1].update(name=raw['nodes'][0]['name']),
        )
        for index, change in enumerate(changes):
            raw = packet()
            change(raw)
            with self.subTest(change=index), self.assertRaises(ValueError):
                read(raw)

    def test_numeric_provider_aggregates_are_required(self):
        for invalid in (None, True, '.25', -.01, 1.01, float('nan'), float('inf'), -float('inf')):
            raw = packet()
            raw['skee'][0]['morphs'][0]['aggregate']['value'] = invalid
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                read(raw)

    def test_duplicate_request_or_observation_selection_is_refused(self):
        for names, morphs in (((), MORPHS), (NAMES, ()), ((NAMES[0], NAMES[0]), MORPHS),
                              (NAMES, (MORPHS[0], MORPHS[0]))):
            with self.subTest(names=names, morphs=morphs), self.assertRaises(ValueError):
                request(REFERENCE, names, morphs)
            with self.subTest(name='observe', names=names, morphs=morphs), self.assertRaises(ValueError):
                read(packet(), names=names, morphs=morphs)
        one_morph = packet()
        one_morph['skee'][0]['morphs'].pop()
        with self.assertRaises(ValueError):
            read(one_morph, morphs=(MORPHS[0], MORPHS[0]))

    def test_deformation_projects_morphed_bind_vertices_into_root_local_space(self):
        binds = np.stack((np.eye(4), np.eye(4)))
        binds[0, 0, 3] = 1.
        model = {'names': NAMES[:2], 'vertices': np.array([[1., 0., 0.], [0., 2., 0.]]),
                 'morphs': {MORPHS[0]: np.array([[2., 0., 0.], [0., 0., 2.]])},
                 'weights': np.array([[.25, .5], [0., 1.]]), 'binds': binds}
        root = FIXTURE.transform([10., 20., 30.], FIXTURE.YAW90, 2.)
        locals_ = (FIXTURE.transform([2., 0., 0.]), FIXTURE.transform([0., 0., 4.], FIXTURE.YAW90, .5))
        pose = {'root': root, 'morphs': {MORPHS[0]: .5},
                'nodes': {name: {'world': FIXTURE.compose(root, local)} for name, local in zip(NAMES[:2], locals_, strict=True)}}
        # After the morph and bind, the first point receives (5,0,0) and (0,1,4).
        np.testing.assert_allclose(deformation(model, pose, False), [[1.25, .5, 2.], [-1., 0., 4.5]])
        np.testing.assert_allclose(deformation(model, pose, True), [[5./3, 2./3, 8./3], [-1., 0., 4.5]])


class AttachmentDriftTests(unittest.TestCase):
    def test_common_local_rotation_transports_the_original_offset(self):
        name = "NPC Head [Head]"
        identity = {"translation": [0., 0., 0.], "scale": 1., "rotationRowMajor": np.eye(3).ravel().tolist()}
        turned = {**identity, "rotationRowMajor": [0., -1., 0., 1., 0., 0., 0., 0., 1.]}
        before = {"guard": {"owner": 1}, "sample": 1, "time": 2, "root": identity,
                  "nodes": {name: {"world": identity}}, "morphs": {}}
        after = {**before, "sample": 2, "time": 3, "nodes": {name: {"world": turned}}}
        shared = {"names": (name,), "binds": np.eye(4)[None, :, :], "morphs": {}}
        fur = {**shared, "vertices": np.tile([.2, .3, .8], (6, 1)), "weights": np.ones((6, 1))}
        head = {**shared, "vertices": np.array([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]]),
                "weights": np.ones((3, 1))}
        output = compare({"baseline": {"fur_belly": fur, "head": head}}, before, after)
        for convention in output.values():
            result = convention["baseline"]
            self.assertNotEqual(result["rootToTriangleBefore"], result["rootToTriangleAfter"])
            self.assertAlmostEqual(result["transportedOffsetDriftGU"], 0.)


if __name__ == '__main__':
    unittest.main()
