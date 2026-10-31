"""Authoring format, family isolation and independent preset package contracts."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location("claw_presets", ROOT / 'src/main/python/build-tools/presets.py')
presets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(presets)


class Presets(unittest.TestCase):
    def xml(self, text):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "author.xml"
        path.write_text(text, encoding="utf-8")
        return path

    def test_real_examples_preserve_endpoints_and_typed_families(self):
        data = json.loads((ROOT / 'src/main/resources/presets/examples.json').read_text())
        path = self.xml(presets.export_recipe(data).decode())
        loaded = presets.read_xml(path)
        self.assertEqual(len(loaded), 4)
        self.assertEqual(loaded[0]["morphs"]["CLAWHeadEarSize"], {"small": .15, "big": .3})
        self.assertEqual([row["sex"] for row in loaded], ["male", "male", "female", "female"])

    def test_bodyslide_omitted_zero_endpoint_is_supported(self):
        path = self.xml('<SliderPresets><Preset name="Wolf" set="CLAW Male"><SetSlider name="CLAWTailLength" size="big" value="30"/></Preset></SliderPresets>')
        self.assertEqual(presets.read_xml(path)[0]["morphs"]["CLAWTailLength"], {"small": 0, "big": .3})

    def test_unrelated_families_adult_and_wrong_sex_are_refused(self):
        for family, morph in (("HIMBO", "CLAWTailLength"), ("CLAW Male", "CLAWTorsoBreastSize"),
                              ("CLAW Female", "CLAWCrotchVulva"), ("CLAW Male", "TYPO")):
            with self.subTest(family=family, morph=morph), self.assertRaises(ValueError):
                presets.read_xml(self.xml(f'<SliderPresets><Preset name="Wolf" set="{family}"><SetSlider name="{morph}" size="big" value="10"/></Preset></SliderPresets>'))

    def test_duplicate_endpoints_and_cross_file_names_are_refused(self):
        text = '<SetSlider name="CLAWTailLength" size="big" value="10"/>'
        with self.assertRaises(ValueError):
            presets.read_xml(self.xml(f'<SliderPresets><Preset name="Wolf" set="CLAW Male">{text}{text}</Preset></SliderPresets>'))
        path = self.xml(f'<SliderPresets><Preset name="Wolf" set="CLAW Male">{text}</Preset></SliderPresets>')
        (path.parent / "another-author.xml").write_bytes(path.read_bytes())
        with self.assertRaises(ValueError):
            presets.load_tree(path.parent)

    def test_invalid_numeric_values_and_entities_are_refused(self):
        for value in ("NaN", "inf", "-1", "101"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                presets.read_xml(self.xml(f'<SliderPresets><Preset name="Wolf" set="CLAW Male"><SetSlider name="CLAWTailLength" size="big" value="{value}"/></Preset></SliderPresets>'))
        with self.assertRaises(ValueError):
            presets.read_xml(self.xml('<!DOCTYPE x [<!ENTITY e "bad">]><SliderPresets/>'))

    def test_export_never_overwrites_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "author.xml"
            out.write_bytes(b"owner content")
            result = presets.main(["export", str(ROOT / 'src/main/resources/presets/examples.json'), "--out", str(out)])
            self.assertEqual(result, 2)
            self.assertEqual(out.read_bytes(), b"owner content")

    def test_empty_typed_preset_is_a_valid_neutral_body(self):
        data = {"schemaVersion": 1, "presets": [{"name": "Neutral male", "sex": "male", "morphs": {}}]}
        loaded = presets.read_xml(self.xml(presets.export_recipe(data).decode()))
        self.assertEqual(loaded[0]["morphs"], {})

    def test_runtime_name_and_xml_contract_limits(self):
        for name in ("A" * 161, " padded", "padded ", "control\x7f"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                presets.validate_name(name)
        for body in ('<Preset name="Wolf" set="CLAW Male" extra="x"/>',
                     '<Preset name="Wolf" set="CLAW Male"><Group name="CLAW">text</Group></Preset>',
                     '<Preset name="Wolf" set="CLAW Male"><SetSlider name="CLAWHeadSize" size="big" value="+1"/></Preset>'):
            with self.subTest(body=body), self.assertRaises(ValueError):
                presets.read_xml(self.xml('<SliderPresets>' + body + '</SliderPresets>'))


if __name__ == "__main__":
    unittest.main()
