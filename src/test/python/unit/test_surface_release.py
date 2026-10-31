"""Real frozen assets and packaging boundaries, without a game or installation."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'src/main/python/build-tools'))
import surface_edits as edit
spec=importlib.util.spec_from_file_location('core_candidate',ROOT/'src/main/python/build-tools/build-core-candidate.py')
package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)
BASE=ROOT/'target/references/releases/0.6.2.0/base/Meshes/Actors/WerewolfBeast/Character Assets'
RECIPE=ROOT/'src/main/resources/recipes/surface-repair-v1.json'


class SurfaceRelease(unittest.TestCase):


    def test_no_overwriting_or_input_descendant(self):
        for output in (BASE,BASE/'new'):
            with self.assertRaisesRegex(ValueError,'New external'):
                edit.build(BASE,RECIPE,output)


    def test_family_selection_keeps_rules_and_explicit_sex_defaults(self):
        import xml.etree.ElementTree as ET
        original=ET.parse(ROOT/'src/main/resources/profiles/MorphLinks.xml').getroot()
        for family in ('CBBE','3BA'):
            root=ET.fromstring(package.family_xml(family))
            self.assertEqual([(p.attrib,[r.attrib for r in p]) for p in root.findall('Profile')],
                             [(p.attrib,[r.attrib for r in p]) for p in original.findall('Profile')])
            d=root.find('Defaults')
            self.assertEqual(d.attrib['male'],'CLAW.HIMBO.5.8.Geometry1')
            self.assertEqual(d.attrib['female'],{'CBBE':'CLAW.CBBE.2.0.3.Geometry1','3BA':'CLAW.3BA.2.48.Geometry1'}[family])

    def test_package_paths_refuse_escape(self):
        for p in ('../bad','/bad','C:/bad','a\\bad'):
            with self.assertRaises(ValueError):package.destination(p)

if __name__=='__main__':unittest.main()
