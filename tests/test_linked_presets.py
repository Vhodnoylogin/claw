"""Fixed paired-preset numerical/ownership/lifecycle oracle, without game claims."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import presets
spec = importlib.util.spec_from_file_location("claw_linked", ROOT / "scripts/linked_presets.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


class LinkedPresets(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads((ROOT / "tests/fixtures/paired-link.json").read_text())
        self.snapshot = self.fixture["snapshot"]
        self.rules = self.fixture["rules"]
        self.catalog = self.fixture["catalog"]
        self.allowed = presets.inventory()

    def plan(self):
        return core.plan(self.snapshot, self.rules, self.catalog, self.allowed)

    def assertCoefficients(self, plan, expected):
        for name, value in expected.items():
            self.assertAlmostEqual(plan["desiredMorphs"][name], value, places=7)

    def test_exact_pair_replaces_domain_and_keeps_traits(self):
        plan = self.plan()
        self.assertEqual(plan["policy"], "linked")
        self.assertEqual(plan["activeKey"], "CLAW.Link")
        self.assertEqual(plan["clearKeys"], ["CLAW.Distribution", "CLAW.Link"])
        self.assertTrue(plan["pending"])
        self.assertCoefficients(plan, self.fixture["expected"]["pairA"])
        self.assertEqual(plan["desiredMorphs"][core.BREAST], 0)

    def test_endpoints_interpolate_once(self):
        for weight, expected in ((0, .2), (50, .4), (100, .6)):
            self.snapshot["weight"] = weight
            self.assertAlmostEqual(self.plan()["desiredMorphs"]["CLAWTorsoGirth"], expected)

    def test_changed_source_pair_zeros_previous_value_without_reroll(self):
        first = self.plan()
        self.snapshot["previous"] = first["state"]
        self.snapshot["source"]["preset"] = "Human B"
        second = self.plan()
        self.assertEqual(second["generation"], first["generation"] + 1)
        self.assertCoefficients(second, self.fixture["expected"]["pairB"])
        self.assertEqual(second["state"]["traits"], first["state"]["traits"])

    def test_manual_neutral_overrides_link(self):
        self.snapshot.update(mode="manual", manualPreset="Neutral Female")
        result = self.plan()
        self.assertEqual(result["policy"], "manual")
        self.assertEqual(result["activeKey"], "CLAW.Distribution")
        self.assertTrue(all(v == 0 for v in result["desiredMorphs"].values()))

    def test_suppression_precedes_missing_dependencies(self):
        self.snapshot["suppressed"] = True
        result = core.plan(self.snapshot)
        self.assertEqual(result["policy"], "suppressed")
        self.assertIsNone(result["activeKey"])
        self.assertEqual(result["desiredMorphs"], {})
        self.assertEqual(result["clearKeys"], core.KEYS)

    def test_human_cleanup_survives_invalid_provider_rules_and_catalog(self):
        first = self.plan()
        self.snapshot.update(previous=first["state"], isBeast=False, source="broken", weight="broken")
        result = core.plan(self.snapshot, "broken", "broken")
        self.assertEqual(result["policy"], "human")
        self.assertEqual(result["clearKeys"], core.KEYS)
        self.assertEqual(result["desiredMorphs"], {})
        self.assertGreater(result["generation"], first["generation"])

    def test_unloaded_plans_never_write_even_with_bad_dependencies(self):
        self.snapshot.update(loaded=False, source="broken")
        result = core.plan(self.snapshot)
        self.assertEqual(result["policy"], "deferred")
        self.assertEqual(result["clearKeys"], [])
        self.assertEqual(result["desiredMorphs"], {})

    def test_unmapped_exact_profile_and_names_stay_independent(self):
        for field, value in (("profile", "Other Body With Same Names"), ("preset", "Human A Extra")):
            with self.subTest(field=field):
                self.snapshot["source"] = {"profile":"Synthetic CBBE Profile", "preset":"Human A", "confirmed":True}
                self.snapshot["source"][field] = value
                result = self.plan()
                self.assertEqual(result["policy"], "independent")
                self.assertCoefficients(result, self.fixture["expected"]["independent"] | {"CLAWHeadEarSize":.23})

    def test_unmapped_new_human_preset_preserves_saved_individuality(self):
        first = self.plan()
        self.snapshot.update(previous=first["state"])
        self.snapshot["source"]["preset"] = "Unmapped Human"
        result = self.plan()
        self.assertEqual(result["policy"], "independent")
        self.assertAlmostEqual(result["desiredMorphs"]["CLAWHeadEarSize"], .23)
        self.assertEqual(result["state"]["traits"], first["state"]["traits"])

    def test_provider_loss_preserves_resolved_pending_intent(self):
        first = self.plan()
        self.snapshot.update(previous=json.loads(json.dumps(first["state"])), source=None)
        result = core.plan(self.snapshot, allowed=self.allowed)
        self.assertEqual(result["policy"], "stale-link")
        self.assertEqual(result["desiredMorphs"], first["desiredMorphs"])
        self.assertTrue(result["pending"])

    def test_confirmed_unassignment_retires_link_before_later_provider_loss(self):
        first = self.plan()
        self.snapshot["previous"] = first["state"]
        self.snapshot["source"]["preset"] = None
        unassigned = core.plan(self.snapshot, catalog=self.catalog, allowed=self.allowed)
        self.assertEqual(unassigned["policy"], "independent")
        self.assertEqual(unassigned["activeKey"], "CLAW.Distribution")
        self.assertEqual(unassigned["clearKeys"], core.KEYS)
        self.assertCoefficients(unassigned, {"CLAWTorsoGirth": .15, "CLAWArmGirth": .4, "CLAWHeadEarSize": .23})
        self.assertNotIn("lastLink", unassigned["state"])
        self.assertEqual(unassigned["state"]["traits"], first["state"]["traits"])
        self.assertEqual(unassigned["generation"], first["generation"] + 1)
        self.snapshot.update(previous=unassigned["state"], source=None)
        unavailable = core.plan(self.snapshot, catalog=self.catalog, allowed=self.allowed)
        self.assertEqual(unavailable["policy"], "independent")
        self.assertEqual(unavailable["desiredMorphs"], unassigned["desiredMorphs"])
        self.assertNotIn("lastLink", unavailable["state"])
        self.assertEqual(unavailable["state"]["traits"], first["state"]["traits"])

    def test_unassignment_does_not_retire_link_when_fallback_cannot_resolve(self):
        first = self.plan()
        self.snapshot.update(previous=first["state"])
        self.snapshot["source"]["preset"] = None
        original = copy.deepcopy(self.snapshot)
        for change in ("missing-preset", "missing-catalog", "changed-traits", "invalid-weight", "invalid-profile"):
            with self.subTest(change=change):
                self.snapshot = copy.deepcopy(original)
                catalog = self.catalog
                if change == "missing-preset":
                    self.snapshot["independentPreset"] = "Missing"
                elif change == "missing-catalog":
                    catalog = None
                elif change == "changed-traits":
                    self.snapshot["traits"]["CLAWHeadEarSize"] = .9
                elif change == "invalid-weight":
                    self.snapshot["weight"] = 101
                else:
                    self.snapshot["source"]["profile"] = ""
                result = core.plan(self.snapshot, catalog=catalog, allowed=self.allowed)
                self.assertEqual(result["policy"], "error")
                self.assertEqual(result["clearKeys"], [])
                self.assertEqual(result["desiredMorphs"], {})
                self.assertEqual(result["state"]["lastLink"], first["state"]["lastLink"])

    def test_unconfirmed_null_is_unavailable_but_confirmed_empty_is_invalid(self):
        first = self.plan()
        self.snapshot.update(previous=first["state"])
        self.snapshot["source"].update(preset=None, confirmed=False)
        unavailable = core.plan(self.snapshot, allowed=self.allowed)
        self.assertEqual(unavailable["policy"], "stale-link")
        self.assertEqual(unavailable["desiredMorphs"], first["desiredMorphs"])
        self.snapshot["source"].update(preset="", confirmed=True)
        invalid = self.plan()
        self.assertEqual(invalid["policy"], "error")
        self.assertEqual(invalid["clearKeys"], [])
        self.assertEqual(invalid["state"]["lastLink"], first["state"]["lastLink"])

    def test_unassignment_does_not_override_manual_or_cleanup_precedence(self):
        first = self.plan()
        self.snapshot.update(previous=first["state"], mode="manual", manualPreset="Neutral Female")
        self.snapshot["source"]["preset"] = None
        manual = core.plan(self.snapshot, catalog=self.catalog, allowed=self.allowed)
        self.assertEqual(manual["policy"], "manual")
        self.assertTrue(all(value == 0 for value in manual["desiredMorphs"].values()))
        self.assertEqual(manual["state"]["lastLink"], first["state"]["lastLink"])
        for controls, policy, clear in (({"suppressed": True}, "suppressed", core.KEYS),
                                         ({"isBeast": False, "sex": None}, "human", core.KEYS),
                                         ({"loaded": False}, "deferred", [])):
            with self.subTest(policy=policy):
                snapshot = copy.deepcopy(self.snapshot)
                snapshot.update(mode="linked", **controls)
                result = core.plan(snapshot)
                self.assertEqual(result["policy"], policy)
                self.assertEqual(result["clearKeys"], clear)
                self.assertEqual(result["desiredMorphs"], {})
                self.assertEqual(result["state"]["lastLink"], first["state"]["lastLink"])

    def test_changed_or_deleted_pinned_pair_needs_explicit_rebind(self):
        first = self.plan()
        self.snapshot["previous"] = first["state"]
        original = copy.deepcopy(self.rules)
        for change in ("delete", "rule", "target", "replace-id-and-target"):
            self.rules = copy.deepcopy(original)
            self.catalog = copy.deepcopy(self.fixture["catalog"])
            if change == "delete":
                self.rules["pairs"].pop(0)
            elif change == "rule":
                self.rules["pairs"][0]["bodyMorphs"] = ["CLAWTorsoGirth"]
            elif change == "replace-id-and-target":
                self.rules["pairs"][0].update(id="fixture/replaced", targetPreset="Pair B Female")
            else:
                self.catalog[1]["morphs"]["CLAWTorsoGirth"]["big"] = .7
            result = self.plan()
            self.assertEqual(result["policy"], "error", change)
            self.assertEqual(result["clearKeys"], [])

    def test_human_cleanup_survives_changed_or_unreadable_sex(self):
        first = self.plan()["state"]
        for sex in ("male", None):
            self.snapshot.update(previous=first, isBeast=False, sex=sex, source=None)
            result = core.plan(self.snapshot)
            self.assertEqual(result["policy"], "human")
            self.assertEqual(result["clearKeys"], core.KEYS)
            self.assertEqual(result["state"]["sex"], "female")
        self.snapshot.update(previous=result["state"], sex="male", isBeast=True)
        self.assertEqual(self.plan()["policy"], "error")

    def test_cli_stale_source_skips_missing_catalog_and_rules(self):
        self.snapshot.update(previous=self.plan()["state"], source=None)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            snapshot = folder / "snapshot.json"
            snapshot.write_text(json.dumps(self.snapshot))
            result = subprocess.run([sys.executable, str(ROOT / "scripts/linked_presets.py"), str(snapshot),
                                     "--pairs", str(folder / "missing.json"), "--presets", str(folder / "missing-xml")],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["policy"], "stale-link")

    def test_cli_independent_ignores_unrelated_broken_rules(self):
        self.snapshot.update(mode="independent")
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            snapshot = folder / "snapshot.json"
            snapshot.write_text(json.dumps(self.snapshot))
            # Use the real XML exporter, while the pair input deliberately does not exist.
            xml = folder / "presets.xml"
            xml.write_bytes(presets.export_recipe({"schemaVersion":1, "presets":[self.catalog[0]]}))
            result = subprocess.run([sys.executable, str(ROOT / "scripts/linked_presets.py"), str(snapshot),
                                     "--pairs", str(folder / "missing.json"), "--presets", str(xml)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["policy"], "independent")

    def test_cli_confirmed_unassignment_skips_absent_rules_but_requires_catalog(self):
        self.snapshot.update(previous=self.plan()["state"])
        self.snapshot["source"]["preset"] = None
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            snapshot = folder / "snapshot.json"
            snapshot.write_text(json.dumps(self.snapshot))
            xml = folder / "presets.xml"
            xml.write_bytes(presets.export_recipe({"schemaVersion": 1, "presets": [self.catalog[0]]}))
            command = [sys.executable, str(ROOT / "scripts/linked_presets.py"), str(snapshot)]
            for pair_args in ([], ["--pairs", str(folder / "missing.json")]):
                with self.subTest(pair_args=pair_args):
                    result = subprocess.run(command + pair_args + ["--presets", str(xml)], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    resolved = json.loads(result.stdout)
                    self.assertEqual(resolved["policy"], "independent")
                    self.assertAlmostEqual(resolved["desiredMorphs"]["CLAWHeadEarSize"], .23)
                    self.assertNotIn("lastLink", resolved["state"])
            missing = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(missing.returncode, 2, missing.stderr)
            self.assertEqual(json.loads(missing.stdout)["policy"], "error")
            self.assertIn("lastLink", json.loads(missing.stdout)["state"])

    def test_invalid_or_ambiguous_rules_do_not_plan_writes(self):
        original = copy.deepcopy(self.rules)
        for change in ("duplicate", "unknown", "breast", "wrong-sex", "overlap"):
            self.rules = copy.deepcopy(original)
            rule = self.rules["pairs"][0]
            if change == "duplicate":
                self.rules["pairs"].append(copy.deepcopy(rule))
            elif change == "unknown":
                rule["guessFamily"] = True
            elif change == "breast":
                rule["bodyMorphs"].append(core.BREAST)
            elif change == "wrong-sex":
                rule["targetPreset"] = "Neutral Male"
            else:
                rule["bodyMorphs"].append("CLAWHeadEarSize")
            result = self.plan()
            self.assertEqual(result["policy"], "error", change)
            self.assertEqual(result["clearKeys"], [])

    def test_previous_identity_or_generation_corruption_is_refused(self):
        first = self.plan()["state"]
        for field, value in (("identity", "another actor"), ("generation", True), ("generation", -1), ("schemaVersion", True)):
            self.snapshot["previous"] = copy.deepcopy(first)
            self.snapshot["previous"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.plan()

    def test_input_is_not_mutated(self):
        before = copy.deepcopy((self.snapshot, self.rules, self.catalog))
        self.plan()
        self.assertEqual((self.snapshot, self.rules, self.catalog), before)

    def test_human_unassignment_survives_cleanup_and_provider_loss(self):
        first = self.plan()
        self.snapshot.update(previous=first["state"], isBeast=False)
        self.snapshot["source"]["preset"] = None
        human = core.plan(self.snapshot)
        self.assertEqual(human["policy"], "human")
        self.assertIn("lastLink", human["state"])
        self.assertIsNone(human["state"]["lastSource"]["preset"])
        self.snapshot.update(previous=human["state"], isBeast=True, source=None)
        beast = self.plan()
        self.assertEqual(beast["policy"], "independent")
        self.assertNotIn("lastLink", beast["state"])
        self.assertAlmostEqual(beast["desiredMorphs"]["CLAWTorsoGirth"], .15)
        self.assertAlmostEqual(beast["desiredMorphs"]["CLAWHeadEarSize"], .23)

    def test_human_source_change_disables_stale_old_pair(self):
        first = self.plan()
        self.snapshot.update(previous=first["state"], isBeast=False)
        self.snapshot["source"]["preset"] = "Human B"
        human = core.plan(self.snapshot)
        self.snapshot.update(previous=human["state"], isBeast=True, source=None)
        beast = self.plan()
        self.assertEqual(beast["policy"], "independent")
        self.assertAlmostEqual(beast["desiredMorphs"]["CLAWTorsoGirth"], .15)


if __name__ == "__main__":
    unittest.main()
