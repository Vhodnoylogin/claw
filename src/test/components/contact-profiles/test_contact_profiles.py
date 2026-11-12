"""Finite profile composition tests; synthetic support does not qualify contact."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
COMPONENT = ROOT / 'src/main/components/contact-profiles/python'
sys.path.insert(0, str(COMPONENT))
import profile_contract as contract
import build_profiles


def sign(model):
    keys = contract.settings.identity_fields(model)
    model['modelIdentity'] = 'CLAW.Physics.CurrentVector.' + hashlib.sha256(
        json.dumps({key: model[key] for key in keys}, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return model


def synthetic_model(edition):
    recipe = contract.read_recipes()[edition]
    regions, slots = {}, []
    for row in recipe['supportRegions']:
        points = [[float(i), float(j), float(k)] for i in range(row['count'])
                  for j, k in ((0, 0), (1, 0), (0, 1))]
        faces = [[3 * i, 3 * i + 1, 3 * i + 2] for i in range(row['count'])]
        for sex in ('male', 'female'):
            if sex == 'male' and row['sexMask'] == 'female':
                continue
            regions[sex + '/' + row['node']] = {'points': points, 'deltas': {}, 'morphs': [],
                'faces': faces, 'partitions': faces, 'triangleGroups': [[i] for i in range(row['count'])],
                'contactPasses': 0, 'padding': .0001}
        for i, face in enumerate(faces):
            slot = {'node': row['node'], 'partition': i, 'sexMask': row['sexMask']}
            for sex in ('male', 'female'):
                slot[sex] = None if sex == 'male' and row['sexMask'] == 'female' else {'partitionIndices': face, 'triangleIndices': [i]}
            slots.append(slot)
    model = {'schemaVersion': 3, 'frame': 'node-local-game-units', 'domain': [0, 1],
             'evaluator': contract.settings.PCA_EVALUATOR, 'morphs': ['CLAWHeadSize'], 'regions': regions, 'slots': slots,
             'supportProfile': recipe['supportProfile'], 'coveredShapes': recipe['skinShapes'],
             'sourceInputs': [{'sha256': 'a' * 64}], 'runtimeQualified': False, 'surfaceFitAccepted': False,
             'supportDeclaration': {'skinShapes': recipe['skinShapes'], 'skeletonSha256': 'a' * 64,
                 'regions': [dict(row, ancestry=[row['node'], 'Root']) for row in recipe['supportRegions']]}}
    return sign(model)


class ContactProfileTests(unittest.TestCase):
    def test_explicit_allocations_keep_one_budget_and_finer_vr_support(self):
        recipes = contract.read_recipes()
        self.assertEqual([sum(row['count'] for row in recipes[edition]['supportRegions']) for edition in ('flat', 'vr')], [52, 128])
        self.assertEqual([sum(row['count'] for row in recipes[edition]['supportRegions'] if row['sexMask'] == 'both')
                          for edition in ('flat', 'vr')], [48, 120])
        for edition in recipes:
            self.assertEqual(recipes[edition]['skinShapes'], ['body', 'head', 'claws'])
            self.assertFalse(recipes[edition]['runtimeQualified'])
        legacy = json.loads((contract.PHYSICS / 'contact-whole-body-coarse.json').read_bytes())
        self.assertEqual(legacy['capsuleBudget'], 128)
        self.assertEqual(legacy['supportProfile'], contract.settings.COARSE_PROFILE)

    def test_rejects_duplicate_overbudget_missing_or_relabelled_profiles(self):
        for change in ('duplicate', 'budget', 'shape', 'identity', 'not_finer', 'missing'):
            value = copy.deepcopy(contract.read_recipes())
            if change == 'duplicate': value['vr']['supportRegions'].append(value['vr']['supportRegions'][0])
            if change == 'budget': value['flat']['supportRegions'][0]['count'] += 1
            if change == 'shape': value['vr']['skinShapes'].remove('claws')
            if change == 'identity': value['flat']['supportProfile'] = contract.settings.COARSE_PROFILE
            if change == 'not_finer': value['flat']['supportRegions'][0]['count'] = value['vr']['supportRegions'][0]['count']
            if change == 'missing': value.pop('vr')
            with self.subTest(change=change), self.assertRaises(ValueError): contract.validate_recipes(value)

    def test_both_models_retain_exact_declared_slots_sex_masks_and_identity(self):
        models = {edition: synthetic_model(edition) for edition in contract.PROFILES}
        contract.validate_models(models)
        self.assertNotEqual(models['flat']['modelIdentity'], models['vr']['modelIdentity'])
        for edition in models:
            broken = copy.deepcopy(models)
            broken[edition]['slots'].pop()
            with self.assertRaises(ValueError): contract.validate_models(broken)

    def test_new_profiles_do_not_allow_contact_passes_or_unbounded_flat_support(self):
        for edition in contract.PROFILES:
            model = synthetic_model(edition)
            model['contactPasses'] = 1
            with self.subTest(edition=edition), self.assertRaises(ValueError): contract.settings.support_declaration(model)
        model = synthetic_model('flat')
        model['supportDeclaration']['regions'][0]['count'] += 5
        with self.assertRaisesRegex(ValueError, '56-slot'): contract.settings.support_declaration(model)
        model['supportProfile'] = 'undeclared-future-profile'
        with self.assertRaisesRegex(ValueError, 'Unknown'): contract.settings.support_declaration(model)

    def test_pair_emission_requires_explicit_edition_and_preserves_single_emitter(self):
        models = {edition: synthetic_model(edition) for edition in contract.PROFILES}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            contract.fit.write_cpp_model(models['flat'], root / 'legacy.h')
            legacy = (root / 'legacy.h').read_bytes()
            pair = contract.write_pair_header(models, root).read_text()
            self.assertIn('CompiledModel(bool female, ContactRuntimeEdition edition)', pair)
            self.assertIn('Unknown contact runtime edition', pair)
            self.assertIn(models['flat']['modelIdentity'], pair)
            self.assertIn(models['vr']['modelIdentity'], pair)
            self.assertNotIn('CompiledModel(bool isFemale)', pair)
            contract.fit.write_cpp_model(models['flat'], root / 'legacy-again.h')
            self.assertEqual(legacy, (root / 'legacy-again.h').read_bytes())
            with self.assertRaises(ValueError):
                contract.fit.write_cpp_model(models['flat'], root / 'unsafe.h', function_name='wrong();')
            self.assertFalse((root / 'unsafe.h').exists())

    def test_matching_host_data_binds_model_and_platform_count_without_activation(self):
        recipe = json.loads((contract.PHYSICS / 'recipe.json').read_bytes())
        capsules = json.loads((contract.PHYSICS / 'capsules.json').read_bytes())
        for edition in contract.PROFILES:
            model = synthetic_model(edition)
            data = contract.host.render_data(recipe, capsules, model)
            self.assertIn(model['modelIdentity'], data)
            self.assertIn('Return ' + str(len(model['slots'])), data)
            self.assertNotIn('BeginSession', data)
            self.assertIn('Return None', data)  # Schema3 cannot silently use affine Papyrus fitting.

    def test_runtime_manifest_hashes_all_six_inputs_and_rejects_changed_or_duplicate(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            rows = []
            for sex in ('male', 'female'):
                for suffix in ('_0.nif', '_1.nif', '.tri'):
                    path = root / (sex + 'bodywerewolf' + suffix)
                    path.write_bytes((sex + suffix).encode())
                    rows.append({'path': str(path), **contract.pin(path)})
            manifest = root / 'runtime.json'
            manifest.write_text(json.dumps({'files': rows}))
            self.assertEqual(len(build_profiles.runtime_inputs(manifest)), 6)
            Path(rows[0]['path']).write_bytes(b'changed')
            with self.assertRaises(ValueError): build_profiles.runtime_inputs(manifest)
            rows[0] = rows[1]
            manifest.write_text(json.dumps({'files': rows}))
            with self.assertRaises(ValueError): build_profiles.runtime_inputs(manifest)

    def test_vr_contact_trial_reuses_allocation_and_requires_exactly_three_passes(self):
        base = contract.read_recipes()['vr']
        trial = contract.read_vr_contact_recipe()
        self.assertEqual(trial['supportRegions'], base['supportRegions'])
        self.assertEqual(trial['capsuleBudget'], 128)
        self.assertEqual(trial['fixtureSet'], 'compact')
        self.assertEqual(contract.read_recipes()['vr']['contactPasses'], 0)
        model = synthetic_model('vr')
        model['supportProfile'] = contract.settings.VR_CONTACT_PROFILE
        for passes in (0, 1, 2, 4, 8):
            model['contactPasses'] = passes
            with self.subTest(passes=passes), self.assertRaisesRegex(ValueError, 'exactly three'):
                contract.settings.support_declaration(model)
        model['contactPasses'] = 3
        self.assertTrue(contract.settings.support_declaration(model))

    def test_contact_trial_model_cannot_replace_enclosing_vr_without_explicit_selection(self):
        models = {edition: synthetic_model(edition) for edition in contract.PROFILES}
        model = models['vr']
        model.update(supportProfile=contract.settings.VR_CONTACT_PROFILE,
                     evaluator=contract.settings.CONTACT_EVALUATOR, contactPasses=3)
        for region in model['regions'].values(): region['contactPasses'] = 3
        sign(model)
        with self.assertRaisesRegex(ValueError, 'explicit profile'): contract.validate_models(models)
        contract.validate_models(models, vr_contact_trial=True)
        with tempfile.TemporaryDirectory() as folder:
            header = contract.write_pair_header(models, Path(folder), vr_contact_trial=True).read_text()
            self.assertIn('m.contactPasses=3;', header)
            self.assertIn('static const std::array<std::size_t,3> data[]', header)

    def test_default_new_profile_storage_is_static_and_legacy_coarse_bytes_are_exact(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            legacy = synthetic_model('flat')
            legacy['supportProfile'] = contract.settings.COARSE_PROFILE
            sign(legacy)
            path = root / 'coarse.h'
            contract.fit.write_cpp_model(legacy, path)
            self.assertEqual(hashlib.sha256(path.read_text(encoding='utf-8').encode('utf-8')).hexdigest(),
                             '36ea65b7f5188a484bbf02b52397c88a5186fb36b51f798f8e83818cafc2edc9')
            for edition in contract.PROFILES:
                contract.fit.write_cpp_model(synthetic_model(edition), path)
                self.assertIn('static const Vec3 data[]', path.read_text())
            contact = synthetic_model('vr')
            contact.update(supportProfile=contract.settings.VR_CONTACT_PROFILE,
                           evaluator=contract.settings.CONTACT_EVALUATOR, contactPasses=3)
            for region in contact['regions'].values(): region['contactPasses'] = 3
            sign(contact)
            contract.fit.write_cpp_model(contact, path)
            self.assertIn('static const std::array<std::size_t,3> data[]', path.read_text())


if __name__ == '__main__':
    unittest.main()
