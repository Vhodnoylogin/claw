import unittest

from coat_variation_readback import verify_skin_variation


class CoatVariationReadbackTests(unittest.TestCase):
    def test_distinguishes_skin_within_same_material_bin(self):
        audit = {'leaseRootCurrent': True,
                 'coatDecision': {'pattern': 'valley-brown', 'variation': .5733334}}
        self.assertTrue(verify_skin_variation(audit, 'valley-brown', .57333338, .50000003)['distinguishesSkinTerm'])

    def test_missing_runtime_value_does_not_qualify(self):
        with self.assertRaisesRegex(ValueError, 'missing'):
            verify_skin_variation({'leaseRootCurrent': True}, 'valley-brown', .57333338, .50000003)

    def test_decision_requires_current_lease_and_matched_selection(self):
        decision = {'pattern': 'valley-brown', 'variation': .5733334}
        with self.assertRaisesRegex(ValueError, 'missing'):
            verify_skin_variation({'leaseRootCurrent': False, 'coatDecision': decision}, 'valley-brown', .57333338, .50000003)
        with self.assertRaisesRegex(ValueError, 'applied pattern'):
            verify_skin_variation({'leaseRootCurrent': True, 'coatDecision': decision}, 'timber-dark', .57333338, .50000003)

    def test_wrong_and_unseparated_variation_remain_distinct(self):
        decision = {'pattern': 'valley-brown', 'variation': .5}
        audit = {'leaseRootCurrent': True, 'coatDecision': decision}
        with self.assertRaisesRegex(ValueError, 'skin-aware calculation'):
            verify_skin_variation(audit, 'valley-brown', .57333338, .5)
        self.assertFalse(verify_skin_variation(audit, 'valley-brown', .50000001, .5)['distinguishesSkinTerm'])
