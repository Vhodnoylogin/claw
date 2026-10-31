"""Real frozen assets and packaging boundaries, without a game or installation."""
import copy
import os
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
BODY_ROOT=Path(os.environ.get('CLAW_INTEGRATION_BODY_ROOT', ROOT/'target/bodies/fresh'))
BASE=BODY_ROOT/'legacy/Meshes/Actors/WerewolfBeast/Character Assets'
RECIPE=ROOT/'src/main/resources/recipes/surface-repair-v1.json'


class SurfaceResourceIntegrationTests(unittest.TestCase):
    def test_real_repair_rebuilds_exact_reviewed_game_inputs(self):
        expected={'malebodywerewolf_0.nif':'cff0f62e9c089cf8618e39cb4012be5d9041535d7a101c4242bfb87f8b25b0ef',
                  'malebodywerewolf_1.nif':'cff0f62e9c089cf8618e39cb4012be5d9041535d7a101c4242bfb87f8b25b0ef',
                  'malebodywerewolf.tri':'1e2dd49812870620072d3a426124a957486f292504d5173978fd3b5edb8db285',
                  'femalebodywerewolf_0.nif':'033c9828661e371d4d9eadbf85202235391ccd31408777e149631d57baafa3ff',
                  'femalebodywerewolf_1.nif':'033c9828661e371d4d9eadbf85202235391ccd31408777e149631d57baafa3ff',
                  'femalebodywerewolf.tri':'3fd1ce64adafa5d77a510d1829077b9b3aa06a23eb741377a4803432416fb28b'}
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(edit.build(BASE,RECIPE,Path(t)/'out'),expected)

    def test_source_drift_refused_before_output_creation(self):
        recipe=json.loads(RECIPE.read_text());recipe['files']['malebodywerewolf.tri']['before']='0'*64
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);(p/'recipe.json').write_text(json.dumps(recipe))
            with self.assertRaisesRegex(ValueError,'input drift'):
                edit.build(BASE,p/'recipe.json',p/'out')
            self.assertFalse((p/'out').exists())

    def test_nif_unrecognized_block_edit_rejected(self):
        recipe=json.loads(RECIPE.read_text())['files']['femalebodywerewolf_0.nif']
        recipe['blocks'][0]['kind']='BSLightingShaderProperty'
        with self.assertRaisesRegex(ValueError,'block binding'):
            edit.apply_nif((BASE/'femalebodywerewolf_0.nif').read_bytes(),recipe)


if __name__ == "__main__":
    unittest.main()
