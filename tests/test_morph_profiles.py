from pathlib import Path
import importlib.util
import unittest
import xml.etree.ElementTree as ET
import math

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('claw_calibration',ROOT/'scripts/morph_calibration.py')
cal=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(cal)


class ShippedFamilyTests(unittest.TestCase):
    def setUp(self):
        self.profiles={node.attrib['family']:node for node in ET.parse(ROOT/'distribution/profiles/MorphLinks.xml').getroot()}

    def rules(self,family):
        return [{'source':r.attrib['source'],'target':r.attrib['target'],'gain':float(r.attrib['gain'])} for r in self.profiles[family]]

    def test_families_have_explicit_identities_and_no_implicit_activation(self):
        self.assertEqual(set(self.profiles),{'3BA','CBBE','HIMBO'})
        self.assertEqual(self.profiles['HIMBO'].attrib['sex'],'male')
        self.assertEqual(self.profiles['3BA'].attrib['sex'],'female')
        root=ET.parse(ROOT/'distribution/profiles/MorphLinks.xml').getroot()
        self.assertIsNone(root.find('Defaults'))

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

    def test_all_rules_are_finite_unique_bounded_and_preserve_zero(self):
        for family in self.profiles:
            rules=self.rules(family)
            self.assertLessEqual(len(rules),128)
            self.assertEqual(len(rules),len({(r['source'],r['target']) for r in rules}))
            self.assertTrue(all(math.isfinite(r['gain']) for r in rules))
            self.assertFalse(any(r['source'].startswith('CLAW') for r in rules))
            self.assertFalse(any(any(token in r['target'] for token in ('Head','Tail','Claw','Paw','Crotch')) for r in rules))
            self.assertTrue(all(value==0 for value in cal.compose(rules,{}).values()))


if __name__=='__main__':unittest.main()
