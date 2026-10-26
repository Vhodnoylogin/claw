"""Explicit resource/model pinning for the optional P1 contact variant."""
from pathlib import Path
import hashlib
import importlib.util
import json
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('claw_breast_contact_build',ROOT/'build.py')
build = importlib.util.module_from_spec(spec); spec.loader.exec_module(build)

def profile():
    return {'schemaVersion':1,'id':'fixture.P1.Weight1',
            'inputs':{'bodyNifSha256':'a'*64,'bodyWeight1NifSha256':'b'*64,
                      'skeletonSha256':json.loads((ROOT/'breast-motion.json').read_text())['inputs']['skeletonSha256']},
            'p1Bones':list(build.BREAST_NODES),
            'capsuleModelIdentity':'CLAW.Physics.CurrentVector.'+'c'*64}

class BreastContactProfileTests(unittest.TestCase):
    def test_contact_is_separate_nonzero_and_requires_an_explicit_resource_profile(self):
        legacy = build.read_breast_recipe(build.SourceInputs(breast=True))
        self.assertEqual(legacy['commonOverrides']['collisionMultipler'],0)
        with self.assertRaisesRegex(ValueError,'explicit current resource profile'):
            build.read_breast_recipe(build.SourceInputs(breast_contact=True))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'binding.json'; path.write_text(json.dumps(profile()))
            inputs = build.SourceInputs(breast_contact=True,breast_profile=path)
            recipe = build.read_breast_recipe(inputs)
            self.assertEqual(recipe['commonOverrides']['collisionMultipler'],.05)
            self.assertEqual(recipe['commonOverrides']['collisionMultiplerRot'],.01)
            self.assertEqual(recipe['raceCondition'],'IsRaceFormId(Skyrim.esm|000CDD84) AND IsFemale()')
            self.assertEqual(recipe['resourceProfile']['sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
            path.write_text(json.dumps(profile())+' ')
            with self.assertRaisesRegex(ValueError,'profile changed'): inputs.verify()

    def test_wrong_skeleton_bones_or_missing_high_endpoint_cannot_repin_the_rig(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'binding.json'
            for mutation in ('skeleton','bones','weight1'):
                binding = profile()
                if mutation == 'skeleton': binding['inputs']['skeletonSha256'] = 'd'*64
                if mutation == 'bones': binding['p1Bones'][0] = 'NPC L Breast'
                if mutation == 'weight1': del binding['inputs']['bodyWeight1NifSha256']
                path.write_text(json.dumps(binding))
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    build.read_breast_recipe(build.SourceInputs(breast_contact=True,breast_profile=path))

    def test_current_vector_contact_must_match_both_female_p1_regions_and_all_input_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'binding.json'; path.write_text(json.dumps(profile()))
            recipe = build.read_breast_recipe(build.SourceInputs(breast_contact=True,breast_profile=path))
            pins = [{'sha256':value} for value in profile()['inputs'].values()]
            fitted = {'model':{'schemaVersion':3,'weightDependent':True,'modelIdentity':profile()['capsuleModelIdentity'],
                              'slots':[{'node':node,'sexMask':'female'} for node in build.BREAST_NODES],
                              'sourceInputs':pins.copy()}}
            build.require_breast_fit((recipe,pins),fitted)
            fitted['model']['sourceInputs'] = pins[:1]
            with self.assertRaisesRegex(ValueError,'does not pin'): build.require_breast_fit((recipe,pins),fitted)
            fitted['model']['sourceInputs'] = pins
            fitted['model']['weightDependent'] = False
            with self.assertRaisesRegex(ValueError,'weight endpoints'): build.require_breast_fit((recipe,pins),fitted)

if __name__ == '__main__': unittest.main()
