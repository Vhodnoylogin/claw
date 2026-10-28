"""Schema-3 settings cannot diverge between pinned Python and native fits."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = load('claw_settings_build', ROOT/'build.py')
fit = load('claw_settings_fit', ROOT/'fit-capsules.py')
settings = load('claw_settings_contract', ROOT/'current_model.py')


def sign(model):
    fields = ('evaluator', 'morphs', 'regions', 'slots')
    canonical = json.dumps({key:model[key] for key in fields}, sort_keys=True, separators=(',', ':')).encode()
    model['modelIdentity'] = 'CLAW.Physics.CurrentVector.' + hashlib.sha256(canonical).hexdigest()
    return model


def model(passes=0, padding=1e-4):
    node = build.NODES[0]
    region = {'points':[[0.,0.,0.],[0.,0.,2.],[1.,0.,0.]], 'deltas':{},
              'morphs':[], 'partitions':[[0,1,2]], 'faces':[[0,1,2]], 'triangleGroups':[[0]],
              'padding':padding, 'contactPasses':passes}
    return sign({'schemaVersion':3, 'frame':'node-local-game-units', 'domain':[0,1],
                 'evaluator':settings.CONTACT_EVALUATOR if passes else settings.PCA_EVALUATOR,
                 'contactPasses':passes, 'morphs':['CLAWHeadEarSize'],
                 'slots':[{'node':node, 'partition':0,
                           'male':{'partitionIndices':[0,1,2], 'triangleIndices':[0]},
                           'female':{'partitionIndices':[0,1,2], 'triangleIndices':[0]}}],
                 'regions':{sex+'/'+node:copy.deepcopy(region) for sex in ('male','female')}})


class CurrentModelTests(unittest.TestCase):
    def test_top_level_override_cannot_reuse_the_pinned_identity(self):
        source = model(3)
        changed = copy.deepcopy(source)
        changed['contactPasses'] = 4
        self.assertEqual(sign(changed)['modelIdentity'], source['modelIdentity'])
        with self.assertRaisesRegex(ValueError, 'pinned support regions'):
            build.validate_fitted_model(changed)
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)/'model.h'
            with self.assertRaisesRegex(ValueError, 'pinned support regions'):
                fit.write_cpp_model(changed, output)
            self.assertFalse(output.exists())

    def test_finite_common_padding_is_emitted_instead_of_silently_defaulted(self):
        for padding in (1e-4, .001, .01):
            with self.subTest(padding=padding), tempfile.TemporaryDirectory() as folder:
                source = model(padding=padding)
                build.validate_fitted_model(source)
                self.assertEqual(settings.evaluator_settings(source), (0,padding))
                output = Path(folder)/'model.h'
                fit.write_cpp_model(source, output)
                text = output.read_text()
                self.assertEqual(text.count('m.padding='), 0 if padding == 1e-4 else 2)
                if padding != 1e-4:
                    self.assertIn('m.padding='+format(padding,'.17g')+';',text)

    def test_legacy_omitted_defaults_keep_the_same_native_header(self):
        explicit = model()
        implicit = copy.deepcopy(explicit)
        implicit.pop('contactPasses')
        for region in implicit['regions'].values():
            region.pop('contactPasses')
            region.pop('padding')
        sign(implicit)
        build.validate_fitted_model(implicit)
        self.assertEqual(settings.evaluator_settings(implicit), (0,1e-4))
        # Identity text records the intentionally different serialized support;
        # every emitted numerical setting and support value remains unchanged.
        with tempfile.TemporaryDirectory() as folder:
            outputs = [Path(folder)/name for name in ('explicit.h','implicit.h')]
            for source,path in zip((explicit,implicit),outputs):fit.write_cpp_model(source,path)
            self.assertEqual(outputs[0].read_text().replace(explicit['modelIdentity'],'IDENTITY'),
                             outputs[1].read_text().replace(implicit['modelIdentity'],'IDENTITY'))

    def test_invalid_padding_and_inconsistent_regions_are_rejected(self):
        for value in (True, 0, -.001, .01001, float('nan'), float('inf'), '0.001'):
            source = model()
            next(iter(source['regions'].values()))['padding'] = value
            sign(source)
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'padding'):
                build.validate_fitted_model(source)
        source = model()
        next(iter(source['regions'].values()))['padding'] = .001
        sign(source)
        with self.assertRaisesRegex(ValueError,'common pinned region padding'):
            build.validate_fitted_model(source)

    def test_passes_and_evaluator_are_strict_and_consistent(self):
        for value in (True, -1, 9, 3., '3', float('nan')):
            source = model(3);source['contactPasses'] = value
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'integer'):
                build.validate_fitted_model(source)
        for value in (True, 0, 4, 3., '3'):
            source = model(3);next(iter(source['regions'].values()))['contactPasses'] = value
            sign(source)
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'pinned support regions'):
                build.validate_fitted_model(source)
        for evaluator in ('test', settings.PCA_EVALUATOR):
            source = model(3);source['evaluator'] = evaluator;sign(source)
            with self.subTest(evaluator=evaluator),self.assertRaisesRegex(ValueError,'evaluator'):
                build.validate_fitted_model(source)
        for passes in (0,1,3,8):build.validate_fitted_model(model(passes))

    def test_prescribed_axis_remains_incompatible_with_contact_optimization(self):
        source = model(3)
        next(iter(source['regions'].values()))['axisHints'] = [[0,0,1]]
        sign(source)
        with self.assertRaisesRegex(ValueError,'Prescribed-axis'):
            build.validate_fitted_model(source)


if __name__ == '__main__':unittest.main()
