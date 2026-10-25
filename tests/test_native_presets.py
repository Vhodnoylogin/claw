"""Cross-check the actual native loader against Python's authoring validator.

Set CLAW_PRESET_TOOL to a compiled claw-preset-tool.exe. These tests otherwise
skip explicitly; the default offline suite never downloads or builds tools.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("claw_cross_presets", ROOT / "scripts/presets.py")
authoring = importlib.util.module_from_spec(spec)
spec.loader.exec_module(authoring)
TOOL = os.environ.get("CLAW_PRESET_TOOL")


@unittest.skipUnless(TOOL and Path(TOOL).is_file(), "Compiled native preset tool was not supplied")
class NativePresetCompatibility(unittest.TestCase):
    def check(self, xml, expected):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Author.xml"
            path.write_text(xml, encoding="utf-8")
            try:
                authoring.load_tree(Path(directory))
                python_ok = True
            except (ValueError, TypeError):
                python_ok = False
            native = subprocess.run([TOOL, "validate", directory], capture_output=True, text=True, timeout=20)
            self.assertEqual(python_ok, expected)
            self.assertEqual(native.returncode == 0, expected, native.stdout + native.stderr)

    def test_neutral_and_sparse_bodyslide_exports(self):
        for body in ('<Preset name="Neutral" set="CLAW Male"/>',
                     '<Preset name="Sparse female" set="CLAW Female"><SetSlider name="CLAWHeadEarSize" size="big" value="25"/></Preset>'):
            with self.subTest(body=body):
                self.check('<SliderPresets>' + body + '</SliderPresets>', True)

    def test_names_and_xml_contract_match(self):
        bodies = [f'<Preset name="{"A" * 161}" set="CLAW Male"/>',
                  '<Preset name=" padded" set="CLAW Male"/>',
                  '<Preset name="Male" set="CLAW Male" extra="x"/>',
                  '<Preset name="Male" set="CLAW Male"><Group name="CLAW">text</Group></Preset>',
                  '<Preset name="Male" set="CLAW Male"><SetSlider name="CLAWHeadSize" size="big" value="+1"/></Preset>']
        for body in bodies:
            with self.subTest(body=body):
                self.check('<SliderPresets>' + body + '</SliderPresets>', False)

    def test_real_independent_example_package(self):
        data = json.loads((ROOT / "presets/examples.json").read_text())
        self.check(authoring.export_recipe(data).decode(), True)

    def test_wrong_sex_adult_nonfinite_and_duplicate_are_rejected(self):
        for name, value in (("CLAWTorsoBreastSize", "10"), ("CLAWCrotchVulva", "10"),
                            ("CLAWTailLength", "NaN")):
            with self.subTest(name=name):
                self.check(f'<SliderPresets><Preset name="Male" set="CLAW Male"><SetSlider name="{name}" size="big" value="{value}"/></Preset></SliderPresets>', False)
        row = '<SetSlider name="CLAWHeadSize" size="big" value="10"/>'
        self.check('<SliderPresets><Preset name="Male" set="CLAW Male">' + row + row + '</Preset></SliderPresets>', False)


if __name__ == "__main__":
    unittest.main()
