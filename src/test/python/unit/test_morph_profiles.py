from pathlib import Path
import importlib.util
import unittest
import xml.etree.ElementTree as ET
import math
import struct

ROOT=Path(__file__).resolve().parents[4]
SPEC=importlib.util.spec_from_file_location('claw_calibration',ROOT/'src/main/python/build-tools/morph_calibration.py')
cal=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(cal)


class ShippedFamilyTests(unittest.TestCase):
    def setUp(self):
        self.root=ET.parse(ROOT/'src/main/resources/profiles/MorphLinks.xml').getroot()
        self.profiles={(node.attrib['sex'],node.attrib['family']):node for node in self.root.findall('Profile')}

    def rules(self,family):
        """Legacy calibrated linear submatrix, at neutral actor weight (0.5).

        The old calibration helper is not a second function/scalar evaluator.
        Centered actor rows have zero combined contribution at neutral weight;
        function-based lean extensions and all actor/constant rows stay outside
        these retained shape regressions. Native/WASM checks cover full math.
        """
        sex='male' if family=='HIMBO' else 'female'
        return [{'source':r.attrib['source'],'target':r.attrib['target'],'gain':float(r.attrib['gain'])}
                for r in self.profiles[sex,family]
                if r.get('source') and not r.get('source').startswith('$actor.')
                and r.get('function','linear')=='linear']

    def test_families_have_explicit_identities_and_no_implicit_activation(self):
        expected={('male','HIMBO'):'CLAW.HIMBO.5.8.Geometry1',
                  ('female','CBBE'):'CLAW.CBBE.2.0.3.Geometry1',
                  ('female','3BA'):'CLAW.3BA.2.48.Geometry1',
                  ('male','Vanilla'):'CLAW.VanillaMale.Weight1',
                  ('female','Vanilla'):'CLAW.VanillaFemale.Weight1'}
        self.assertEqual(len(self.root.findall('Profile')),5)
        self.assertEqual({key:node.get('id') for key,node in self.profiles.items()},expected)
        self.assertEqual(len({node.get('id') for node in self.profiles.values()}),5)
        self.assertIsNone(self.root.find('Defaults'))
        for (sex,family),profile in self.profiles.items():
            self.assertEqual(profile.get('sex'),sex)
            self.assertTrue(profile.get('version'))
            self.assertTrue(profile.get('calibration'))
            self.assertTrue(any(rule.get('source')=='$actor.weight' for rule in profile))
            if family=='Vanilla':
                self.assertEqual(profile.get('version'),'game-weight-v1')
                self.assertEqual(len(profile),20)
                self.assertEqual({rule.get('source') for rule in profile},{'','$actor.weight'})
                self.assertTrue(all((rule.get('function')=='constant') == (rule.get('source')=='') for rule in profile))

    def test_actual_source_girth_sign_is_preserved(self):
        for family in ('CBBE','3BA'):
            rules=self.rules(family)
            arms=next(r for r in rules if r['source']=='Arms' and r['target']=='CLAWArmGirth')
            self.assertLess(arms['gain'],0)
            self.assertGreater(cal.compose(rules,{'Arms':-.5})['CLAWArmGirth'],0)
            self.assertEqual(cal.compose(rules,{'Arms':.5})['CLAWArmGirth'],0)

    def test_breast_size_is_female_and_based_on_authored_shape(self):
        self.assertFalse(any(r['target']=='CLAWTorsoBreastSize' for r in self.rules('HIMBO')))
        for family in ('CBBE','3BA'):
            self.assertGreater(cal.compose(self.rules(family),{'Breasts':.2})['CLAWTorsoBreastSize'],0)
            self.assertTrue(any(r['source']=='BreastsSmall' and r['gain']<0 for r in self.rules(family)))

    def test_himbo_actual_slim_and_heavy_waist_inputs_keep_geometric_direction(self):
        rules=self.rules('HIMBO')
        # Actual manual-scene inputs; positive HIMBO waist field narrows.
        self.assertAlmostEqual(cal.compose(rules,{'TorsoWaistSize':.2})['CLAWTorsoWaistNarrow'],.76709574)
        self.assertEqual(cal.compose(rules,{'TorsoWaistSize':-.4})['CLAWTorsoWaistNarrow'],0)

    def test_full_canonical_rules_are_active_finite_unique_and_have_consistent_caps(self):
        f32=lambda value:struct.unpack('<f',struct.pack('<f',float(value)))[0]
        epsilon=f32(1e-6)
        for identity,profile in self.profiles.items():
            rules=[rule.attrib for rule in profile]
            self.assertLessEqual(len(rules),128)
            self.assertEqual(len(rules),len({(r['source'],r['target']) for r in rules}))
            self.assertLessEqual(len({r['target'] for r in rules}),64)
            caps={}
            for rule in rules:
                with self.subTest(profile=identity,source=rule['source'],target=rule['target']):
                    self.assertTrue(math.isfinite(f32(rule['gain'])))
                    self.assertGreater(abs(f32(rule['gain'])),epsilon)
                    cap=f32(rule['cap'])
                    self.assertTrue(math.isfinite(cap) and 0<cap<=1)
                    self.assertEqual(caps.setdefault(rule['target'],cap),cap)
                    function=rule.get('function','linear')
                    self.assertIn(function,{'linear','positive','negative','smoothstep','power','constant'})
                    self.assertEqual(rule['source']=='',function=='constant')
                    if function=='constant':self.assertTrue(math.isfinite(f32(rule['value'])))

    def test_ordinary_calibrated_submatrices_preserve_zero_at_neutral_actor_weight(self):
        for family in ('HIMBO','CBBE','3BA'):
            self.assertTrue(all(value==0 for value in cal.compose(self.rules(family),{}).values()))

    def test_observed_muscular_human_keeps_nontrivial_pecs_signal(self):
        # Manual-scene regression: these nonzero source shapes previously gave
        # an almost zero pecs response. Waist direction has a separate geometry
        # regression; global muscle legitimately counters waist narrowing.
        wolf=cal.compose(self.rules('HIMBO'),{
            'PecsMass':.25,'PecsSize':.5,'TorsoWaistSize':.2,'Muscle':.2})
        self.assertGreater(wolf['CLAWTorsoChestSize'],.2)
        self.assertLessEqual(wolf['CLAWTorsoChestSize'],.4)

    def test_observed_heavy_humans_reach_distinct_bounded_belly_shapes(self):
        male=cal.compose(self.rules('HIMBO'),{
            'BellyPot':.5,'BellyRounder':.2,'TorsoBelly':.6,'TorsoBellyChub':.35})
        female=cal.compose(self.rules('3BA'),{'Belly':.7,'BigBelly':.7})
        self.assertGreater(male['CLAWTorsoBellyRound'],.7)
        self.assertGreater(female['CLAWTorsoBellyRound'],.9)
        self.assertLessEqual(male['CLAWTorsoBellyRound'],1)
        self.assertLessEqual(female['CLAWTorsoBellyRound'],1)


if __name__=='__main__':unittest.main()
