"""Hands33 scoring with synthetic equipment phases and an optional native control replay."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from hands33_readback import HUMAN, MARKERS, REALM, WOLF, qualify
from test_human_firstperson_readback import gauntlet_sample, graph


ITEM = 0x0E000801
ADDON = ITEM - 1
PHASES = ('human', 'stock', 'equipped', 'restored')


def phases():
    human = gauntlet_sample()
    wolf = deepcopy(human)
    wolf['views']['firstPerson']['active'] = []
    wolf['distinctRoots'] = [graph(1, 'Wolf Body'), graph(2, 'Hands [Ovl0]'),
                             graph(3, 'Hands [Ovl0]'), graph(5, 'BODY', 'head')]
    wolf['views']['thirdPerson'].update(active=[{
        'slot': 2, 'item': 0xCDD86, 'addon': 0xCDD87, 'clone': 5,
        'modelPath': 'Stock Wolf Body', 'partHandlePresent': True,
    }], buffered=[])
    raws = {}
    for offset, name in enumerate(PHASES, 1):
        before = name == 'human'
        sample = deepcopy(human if before else wolf)
        sample.update(actor=0x14, base=7, cell=REALM, runtimeHandle=0x100000,
                      race=HUMAN if before else WOLF, sex=0)
        raws[name] = {'status': 'ready', 'schema': 'claw-vr-model-topology/' + ('4' if before else '8'),
                      'pid': 17, 'epoch': 1, 'nonce': offset, 'sample': sample}
    return raws


def fake_clone(raws, view, *, bank='active', direct=False, marker=None, make_incomplete=False):
    sample = raws['equipped']['sample']
    section = sample['views'][view]
    marker = marker or MARKERS[view]
    created = {'name': marker, 'appCulled': False, 'vertices': 0, 'triangles': 0, 'type': 3}
    clone = {'id': 100 + len(sample['distinctRoots']), 'geometryDetails': [created], 'geometryDetailsComplete': True,
             'geometries': 1, 'collection': 0, 'appCull': {'effective': False}}
    sample['distinctRoots'].append(clone)
    section[bank].append({'slot': 3, 'item': ITEM, 'addon': ADDON, 'clone': clone['id'],
                          'modelPath': 'declared record path', 'partHandlePresent': False})
    if direct or make_incomplete:
        actor = next(row for row in sample['distinctRoots'] if row['id'] == sample['roots'][view])
        if direct:
            actor['geometryDetails'].append(created)
            actor['geometries'] += 1
        if make_incomplete:
            actor['geometryDetailsComplete'] = False


class Hands33ReadbackTest(unittest.TestCase):
    def score(self, raws, equip=True):
        return qualify(raws, (ITEM, ADDON), equip)

    def test_unbound_equipped_phase(self):
        score = self.score(phases())
        self.assertEqual(score['result'], 'no_first_marker_after_equip')
        self.assertTrue(score['sameCameraStateId'])
        self.assertTrue(score['stockBody32Unchanged'])
        self.assertTrue(score['ordinaryControl']['vrGauntletRosterConfirmed'])
        self.assertFalse(score['headsetPixelsVerified'])

    def test_actual_human_and_stock_route_replay(self):
        archive = os.environ.get('CLAW_HANDS33_BASELINE')
        if archive is None:
            self.skipTest('Set CLAW_HANDS33_BASELINE to the archived native captures')
        human, stock = (json.loads((Path(archive) / (name + '.json')).read_bytes())['raw']
                        for name in ('human', 'stock'))
        self.assertLess(human['nonce'], stock['nonce'])
        equipped, restored = deepcopy(stock), deepcopy(stock)
        equipped['nonce'] += 1
        restored['nonce'] += 2
        score = self.score(dict(zip(PHASES, (human, stock, equipped, restored))), equip=False)
        self.assertEqual(score['result'], 'equip_not_confirmed')
        self.assertTrue(score['ordinaryControl']['vrGauntletRosterConfirmed'])

    def test_two_distinct_views(self):
        raws = phases()
        fake_clone(raws, 'thirdPerson')
        fake_clone(raws, 'firstPerson', direct=True)
        score = self.score(raws)
        self.assertEqual(score['result'], 'world_and_first_routes_observed')
        first = score['samples']['equipped']['routes']['firstPerson']
        self.assertTrue(first['rootChainAndLocalAppCullClearForMatch'])
        self.assertTrue(first['activeExpectedClone'])

    def test_first_clone_alone(self):
        raws = phases()
        fake_clone(raws, 'firstPerson')
        self.assertEqual(self.score(raws)['result'], 'first_clone_without_direct_graph_confirmation')

    def test_buffered_only(self):
        raws = phases()
        fake_clone(raws, 'firstPerson', bank='buffered', direct=True)
        self.assertEqual(self.score(raws)['result'], 'first_marker_in_buffered_clone_only')

    def test_model_path_only_still_qualified_absence(self):
        raws = phases()
        view = raws['equipped']['sample']['views']['firstPerson']
        view['active'].append({'slot': 3, 'item': ITEM, 'addon': ADDON, 'clone': 0, 'partHandlePresent': True,
                               'modelPath': r'CLAW\Test\VR Hands33\WolfHandsFirst.nif'})
        self.assertEqual(self.score(raws)['result'], 'no_first_marker_after_equip')

    def test_incomplete_direct_root_prevents_absence(self):
        raws = phases()
        fake_clone(raws, 'firstPerson', marker='fallback geometry', make_incomplete=True)
        self.assertEqual(self.score(raws)['result'], 'inconclusive_first_route')

    def test_world_clone_without_first_model(self):
        raws = phases()
        fake_clone(raws, 'thirdPerson')
        self.assertEqual(self.score(raws)['result'], 'world_clone_and_no_first_marker')

    def test_world_marker_routed_into_first_active_clone(self):
        raws = phases()
        fake_clone(raws, 'firstPerson', marker=MARKERS['thirdPerson'], direct=True)
        self.assertEqual(self.score(raws)['result'], 'world_marker_in_first_active_clone')

    def test_changed_camera_and_body_control(self):
        raws = phases()
        raws['equipped']['sample']['cameraStateId'] += 1
        self.assertEqual(self.score(raws)['result'], 'inconclusive_control_or_restoration')
        raws = phases()
        raws['equipped']['sample']['views']['thirdPerson']['active'][0]['item'] = ITEM
        self.assertEqual(self.score(raws)['result'], 'inconclusive_control_or_restoration')

    def test_absent_camera_is_not_a_stable_camera(self):
        raws = phases()
        for raw in raws.values():
            raw['sample']['cameraStateId'] = None
        score = self.score(raws)
        self.assertFalse(score['sameCameraStateId'])
        self.assertEqual(score['result'], 'inconclusive_control_or_restoration')

    def test_equip_refusal_is_separate(self):
        self.assertEqual(self.score(phases(), equip=False)['result'], 'equip_not_confirmed')

    def test_foreign_capture_is_refused(self):
        raws = phases()
        raws['equipped']['epoch'] += 1
        with self.assertRaisesRegex(ValueError, 'owner'):
            self.score(raws)


if __name__ == '__main__':
    unittest.main(verbosity=2)
