"""Development selection must not silently reproduce or certify the old recipe."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

TOOLS = Path(__file__).resolve().parents[4]/'src/main/python/build-tools'
sys.path.insert(0, str(TOOLS))
SPEC = importlib.util.spec_from_file_location('fresh_body_pipeline', TOOLS/'fresh-body-pipeline.py')
pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pipeline)


class FreshBodyPipelineTests(unittest.TestCase):
    def test_development_default_and_explicit_legacy_are_distinct_pinned_sources(self):
        self.assertEqual(pipeline.DEFAULT_EXPRESSIVE_VERSION, 'v3')
        recipes = [pipeline.expressive_recipe(version) for version in ('v1', 'v2', 'v3')]
        self.assertNotEqual(recipes[0].read_bytes(), recipes[1].read_bytes())
        for version, recipe in zip(('v1', 'v2', 'v3'), recipes):
            self.assertEqual(json.loads(recipe.read_text())['name'], 'rest-frame-opposed-body-'+version)
        with self.assertRaises(ValueError):
            pipeline.expressive_recipe('unregistered')

    def _stage(self, root, version, *, issues=False):
        candidate = root/'expressive'/pipeline.MESH
        reference = root/'release'
        candidate.mkdir(parents=True)
        (reference/'fomod').mkdir(parents=True)
        xml = ET.Element('config')
        install = ET.SubElement(xml, 'requiredInstallFiles')
        names = [sex+'bodywerewolf'+ending for sex in ('male', 'female')
                 for ending in ('_0.nif', '_1.nif', '.tri')]
        for name in names:
            (candidate/name).write_bytes(b'candidate')
            (reference/name).write_bytes(b'candidate' if version == 'v1' else b'historical-v1')
            ET.SubElement(install, 'file', source=name,
                          destination=pipeline.MESH.as_posix()+'/'+name)
        ET.ElementTree(xml).write(reference/'fomod/ModuleConfig.xml')
        built = {'sexes': {'male': {'normalOrCollapseIssues': int(issues)},
                           'female': {'normalOrCollapseIssues': 0}},
                 'outputSha256': {name: pipeline.sha(candidate/name) for name in names}}
        with patch('expressive_body.build', return_value=built) as author, \
                patch('expressive_verify.verify', return_value={'status': 'passed'}) as reader:
            result = pipeline.build_expressive(root/'repaired', root, version, reference)
            self.assertEqual(author.call_args.args[1], pipeline.expressive_recipe(version))
            self.assertEqual(reader.call_args.args[0], candidate)
            self.assertEqual(reader.call_args.kwargs['base'], root/'repaired')
            self.assertEqual(reader.call_args.kwargs['recipe'], pipeline.expressive_recipe(version))
        return result

    def test_v2_keeps_measured_historical_differences_as_nonrelease_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self._stage(Path(directory), 'v2')
        self.assertEqual(result['expressiveVersion'], 'v2')
        self.assertEqual(result['publicReaderStatus'], 'passed')
        self.assertFalse(result['releaseComparison']['sameRecipeAs070'])
        self.assertFalse(result['releaseComparison']['allExact'])
        self.assertEqual(result['releaseComparison']['checked'], 6)

    def test_v1_still_selects_the_old_recipe_and_reads_all_six_destinations(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self._stage(Path(directory), 'v1')
        self.assertTrue(result['releaseComparison']['sameRecipeAs070'])
        self.assertTrue(result['releaseComparison']['allExact'])
        self.assertEqual(result['releaseComparison']['checked'], 6)

    def test_new_normal_or_collapse_issues_stop_before_independent_readback(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(ValueError, 'sample gates'):
            self._stage(Path(directory), 'v2', issues=True)

    def test_output_can_be_external_but_cannot_pollute_source_or_reuse_a_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'new-build'
            self.assertEqual(pipeline.new_output(output), output.resolve())
            with self.assertRaises(ValueError):
                pipeline.new_output(Path(directory))
        with self.assertRaises(ValueError):
            pipeline.new_output(pipeline.ROOT/'src'/'new-generated-body')


if __name__ == '__main__':
    unittest.main()
