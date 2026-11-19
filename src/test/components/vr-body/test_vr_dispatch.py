"""Portable checks for the VR CDD87 source derivation."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/"src/main/components/vr-body"))
import vr_dispatch as dispatch


class DispatchControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (dispatch.BASE/"ArmorAddons"/dispatch.ARMATURE).read_text(encoding="utf-8-sig")
        cls.header = (dispatch.BASE/"RecordData.yaml").read_text(encoding="utf-8-sig")

    def test_male_only_override_retains_world_and_female_weight(self):
        result = dispatch.armor_source(self.source, {"male"})
        self.assertIn("WeightSliderEnabled:\n  Male: False\n  Female: True\n",result)
        unchanged = lambda text: text.split("WorldModel:\n")[1].split("FirstPersonModel:\n")[0]
        self.assertEqual(unchanged(result),unchanged(self.source))
        for sex in dispatch.SEXES:
            self.assertIn(f"  {sex.capitalize()}:\n    File: {dispatch.armor_path(sex)}\n",result)
        self.assertIn("FormKey: 0CDD87:Skyrim.esm",result)

    def test_sex_controls_are_independent(self):
        self.assertIn("WeightSliderEnabled:\n  Male: True\n  Female: False\n",
                      dispatch.armor_source(self.source,{"female"}))
        self.assertIn("WeightSliderEnabled:\n  Male: False\n  Female: False\n",
                      dispatch.armor_source(self.source,{"male","female"}))

    def test_incomplete_or_ambiguous_base_fails(self):
        for source in (self.source.replace("FirstPersonModel:\n",""),
                       self.source.replace("0CDD87","000007"),
                       self.source + "\nFirstPersonModel:\n  Example:\n"):
            with self.subTest(source=source[:70]), self.assertRaises(ValueError):
                dispatch.armor_source(source,{"male"})
        for sexes in (set(),{"unknown"}):
            with self.subTest(sexes=sexes), self.assertRaises(ValueError):
                dispatch.armor_source(self.source,sexes)

    def test_header_requires_claw_load_order_without_small_flag(self):
        data = dispatch.addon_header(self.header)
        self.assertIn("ModKey: CLAW - VR Body.esp\n",data)
        self.assertNotIn("  - Small\n",data)
        self.assertIn("  - Master: Skyrim.esm\n    FileSize: 0\n  - Master: CLAW.esp\n",data)
