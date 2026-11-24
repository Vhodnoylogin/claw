"""Synthetic positive and refusal controls for native first-person inventories."""
import unittest

from human_firstperson_readback import HUMAN_HANDS, human_first_person


def graph(alias, *names):
    return {'id': alias, 'collection': 0, 'geometryDetailsComplete': True, 'geometries': len(names),
            'geometryDetails': [{'name': name, 'appCulled': False} for name in names],
            'appCull': {'effective': False}}


def ordinary_hands_slot(clone):
    return {'slot': 3, 'item': 0xD64, 'addon': 0xD6C, 'clone': clone, 'partHandlePresent': True,
            'modelPath': r'Actors\Character\Character Assets\1stpersonMaleHands_1.nif'}


def sample(first_actor='Hands [Ovl0]', first_biped='Hands [Ovl0]'):
    return {'roots': {'firstPerson': 2, 'thirdPerson': 1},
            'views': {'firstPerson': {'bipedRoot': 3, 'active': [], 'buffered': []},
                      'thirdPerson': {'bipedRoot': 1}},
            'distinctRoots': [graph(1, 'HandMaleBig3rd'), graph(2, first_actor), graph(3, first_biped)],
            'cameraStateId': 0, 'weaponState': 0}


def gauntlet_sample(actor=('HandMaleVR', 'leatherCuffs'), clone=('HandMaleVR', 'leatherCuffs')):
    observed = sample()
    observed['distinctRoots'][1] = graph(2, *actor, 'Hands [Ovl0]')
    observed['distinctRoots'].append(graph(4, *clone))
    observed['views']['firstPerson']['active'] = [ordinary_hands_slot(4)]
    return observed


class HumanFirstPersonTests(unittest.TestCase):
    def test_exact_geometry_in_a_distinct_complete_direct_first_person_graph(self):
        observed = sample(HUMAN_HANDS)
        observed['views']['firstPerson']['active'] = [ordinary_hands_slot(2)]
        report = human_first_person(observed)
        self.assertEqual(report['state'], 'ordinary_firstperson_hands_loaded')
        self.assertEqual(report['routes']['firstActor']['state'], 'found')
        self.assertTrue(report['activeHandsSlot']['ordinaryMaleHandsRecordAndPath'])
        self.assertTrue(report['stockHandsShapeConfirmed'])
        self.assertFalse(report['vrGauntletRosterConfirmed'])
        self.assertTrue(report['rootChainAndLocalAppCullClearForMatch'])
        self.assertFalse(report['headsetPixelsVerified'])

    def test_declared_path_and_hand_overlays_do_not_prove_hands_geometry(self):
        observed = sample()
        observed['views']['firstPerson']['active'] = [ordinary_hands_slot(0)]
        report = human_first_person(observed)
        self.assertTrue(report['activeHandsSlot']['ordinaryMaleHandsRecordAndPath'])
        self.assertEqual(report['state'], 'ordinary_hands_absent_in_complete_firstperson_graphs')

    def test_incomplete_or_world_aliased_direct_roots_are_inconclusive(self):
        incomplete = sample(HUMAN_HANDS)
        incomplete['distinctRoots'][1]['geometryDetailsComplete'] = False
        aliased = sample()
        aliased['roots']['firstPerson'] = 1
        missing = sample()
        missing['views']['firstPerson']['bipedRoot'] = 0
        for observed in (incomplete, aliased, missing):
            with self.subTest(observed=observed):
                self.assertEqual(human_first_person(observed)['state'], 'firstperson_control_inconclusive')

    def test_matching_hands_clone_without_direct_observation_is_inconclusive(self):
        observed = sample()
        observed['distinctRoots'].append(graph(4, HUMAN_HANDS))
        observed['views']['firstPerson']['buffered'] = [ordinary_hands_slot(4)]
        report = human_first_person(observed)
        self.assertEqual(report['routes']['firstBufferedHands']['state'], 'found')
        self.assertEqual(report['state'], 'firstperson_control_inconclusive')

    def test_root_chain_and_geometry_local_cull_do_not_invalidate_loaded_geometry(self):
        for level in ('root', 'local'):
            with self.subTest(level=level):
                observed = sample(HUMAN_HANDS)
                root = observed['distinctRoots'][1]
                if level == 'root':
                    root['appCull']['effective'] = True
                else:
                    root['geometryDetails'][0]['appCulled'] = True
                report = human_first_person(observed)
                self.assertEqual(report['state'], 'ordinary_firstperson_hands_loaded')
                self.assertFalse(report['rootChainAndLocalAppCullClearForMatch'])

    def test_vr_gauntlet_requires_the_matching_active_stock_hands_and_direct_graph(self):
        observed = gauntlet_sample()
        report = human_first_person(observed)
        self.assertEqual(report['state'], 'ordinary_firstperson_hands_loaded')
        self.assertTrue(report['vrGauntletRosterConfirmed'])
        self.assertFalse(report['stockHandsShapeConfirmed'])
        self.assertTrue(report['rootChainAndLocalAppCullClearForMatch'])
        self.assertEqual(report['routes']['firstActiveHands']['state'], 'found')
        self.assertFalse(report['headsetPixelsVerified'])

    def test_vr_gauntlet_without_active_stock_hands_is_inconclusive(self):
        missing = gauntlet_sample()
        missing['views']['firstPerson']['active'] = []
        buffered = gauntlet_sample()
        view = buffered['views']['firstPerson']
        view['buffered'], view['active'] = view['active'], []
        wrong_item = gauntlet_sample()
        wrong_item['views']['firstPerson']['active'][0]['item'] = 0xD65
        for observed in (missing, buffered, wrong_item):
            with self.subTest(observed=observed):
                report = human_first_person(observed)
                self.assertEqual(report['state'], 'firstperson_control_inconclusive')
                self.assertFalse(report['vrGauntletRosterConfirmed'])

    def test_a_single_vr_gauntlet_shape_or_inexact_clone_roster_is_inconclusive(self):
        for observed in (gauntlet_sample(actor=('HandMaleVR',)), gauntlet_sample(clone=('leatherCuffs',)),
                         gauntlet_sample(clone=('HandMaleVR', 'leatherCuffs', 'extra'))):
            with self.subTest(observed=observed):
                report = human_first_person(observed)
                self.assertEqual(report['state'], 'firstperson_control_inconclusive')
                self.assertFalse(report['vrGauntletRosterConfirmed'])


if __name__ == '__main__':
    unittest.main()
