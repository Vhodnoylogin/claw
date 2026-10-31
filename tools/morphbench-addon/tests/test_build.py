"""Strict canonical mapping ingestion checks; no game, host or output files."""
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("claw_addon_build", Path(__file__).parents[1] / "build.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.source = builder.SOURCE.read_bytes()

    def test_current_canonical_profiles_are_pinned_and_ordered(self):
        catalog = builder.catalog_from_bytes(self.source)
        self.assertEqual([profile["family"] for profile in catalog["profiles"]], ["3BA", "HIMBO", "CBBE"])
        self.assertEqual(catalog["source"]["sha256"], builder.hashlib.sha256(self.source).hexdigest())
        self.assertEqual(catalog["profiles"][0]["rules"][0]["source"], "Arms")
        self.assertGreater(sum(len(profile["rules"]) for profile in catalog["profiles"]), 200)

    def test_invalid_target_sex_family_and_duplicate_profile_are_rejected(self):
        mutations = [
            self.source.replace(b'family="HIMBO"', b'family="Unknown"', 1),
            self.source.replace(b'sex="male"', b'sex="female"', 1),
            self.source.replace(b'target="CLAWArmGirth"', b'target="CLAWHeadEarSize"', 1),
            self.source.replace(b'id="CLAW.CBBE.2.0.3.Geometry1"', b'id="CLAW.3BA.2.48.Geometry1"', 1),
        ]
        for data in mutations:
            with self.subTest(data=data[:40]), self.assertRaises(ValueError):
                builder.catalog_from_bytes(data)

    def test_nonfinite_invalid_caps_and_duplicate_rules_are_rejected(self):
        rule = b'<Rule source="Arms" target="CLAWArmGirth" gain="-0.5886322" cap="1" />'
        for data in [self.source.replace(b'gain="-0.5886322"', b'gain="nan"', 1),
                     self.source.replace(b'gain="-0.5886322"', b'gain="inf"', 1),
                     self.source.replace(b'cap="1"', b'cap="0"', 1),
                     self.source.replace(b'cap="1"', b'cap="1.1"', 1),
                     self.source.replace(rule, rule + rule, 1)]:
            with self.subTest(data=data[:40]), self.assertRaises(ValueError):
                builder.catalog_from_bytes(data)

    def test_schema_unknown_attributes_substantive_text_and_declarations_are_rejected(self):
        for data in [self.source.replace(b'schemaVersion="1"', b'schemaVersion="2"', 1),
                     self.source.replace(b'<Rule source=', b'<Rule unexpected="1" source=', 1),
                     self.source.replace(b'<Profile ', b'ignored text<Profile ', 1),
                     b'<!DOCTYPE MorphLinkProfiles>' + self.source]:
            with self.subTest(data=data[:40]), self.assertRaises(ValueError):
                builder.catalog_from_bytes(data)

    def test_output_inside_the_checkout_is_rejected_before_writes(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            builder.build(builder.REPOSITORY / "work/addon-output")

    def test_function_parameters_and_constant_bias_are_preserved(self):
        source = self.source.replace(b'<Rule source="Arms"', b'<Rule function="power" exponent="3" source="Arms"', 1)
        first = builder.catalog_from_bytes(source)["profiles"][0]["rules"][0]
        self.assertEqual((first["function"], first["exponent"]), ("power", 3))
        source = self.source.replace(b'<Rule source="Arms"', b'<Rule function="constant" value="0.4" source=""', 1)
        first = builder.catalog_from_bytes(source)["profiles"][0]["rules"][0]
        self.assertEqual((first["source"], first["function"], first["value"]), ("", "constant", builder.float32("0.4")))

    def test_invalid_or_irrelevant_function_parameters_are_rejected(self):
        for attributes in [b'function="eval"', b'function="power"', b'function="power" exponent="2.5"',
                           b'function="power" exponent="9"', b'function="linear" value="0.5"',
                           b'function="constant" value="0.5"']:
            data = self.source.replace(b'<Rule source="Arms"', b'<Rule ' + attributes + b' source="Arms"', 1)
            with self.subTest(attributes=attributes), self.assertRaises(ValueError):
                builder.catalog_from_bytes(data)


if __name__ == "__main__":
    unittest.main()
