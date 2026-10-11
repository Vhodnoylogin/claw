"""Transformation, deterministic population diversity and morph ownership contracts."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("claw_distribution", ROOT / "scripts/distribution.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


class Distribution(unittest.TestCase):
    def setUp(self):
        self.recipe = json.loads((ROOT / "recipes/distribution.json").read_text())
        self.human = {"BigTorso": 0.8, "ChubbyWaist": 0.2, "Belly": 0.5, "Breasts": 1.0}

    def plan(self, previous=None, is_beast=True, loaded=True, human=None):
        return core.plan_update(previous, "save-a|Skyrim.esm|reference-123", "CBBE",
                                self.human if human is None else human, "female",
                                is_beast, loaded, self.recipe)

    def test_transform_back_clears_only_owned_key(self):
        original = copy.deepcopy(self.human)
        beast = self.plan()
        human = self.plan(beast["state"], is_beast=False)
        self.assertEqual(human["actions"], [{"op": "clear_key", "key": "CLAW.Link"},
                                           {"op": "update_model"}])
        self.assertEqual(self.human, original)
        self.assertEqual(human["state"]["sourceMorphs"], original)

    def test_save_load_does_not_reroll_traits(self):
        first = self.plan()
        saved = json.loads(json.dumps(first["state"]))
        second = self.plan(saved)
        self.assertEqual(first["state"]["beastMorphs"], second["state"]["beastMorphs"])
        self.assertEqual(second["generation"], first["generation"] + 1)

    def test_return_human_cleanup_survives_provider_loss(self):
        beast = self.plan()["state"]
        original = copy.deepcopy(beast)
        for family, morphs in (("UNKNOWN", {}), ("CBBE", {"Belly": float("nan")})):
            with self.subTest(family=family):
                back = core.plan_update(beast, beast["identity"], family, morphs,
                                        "female", False, True, self.recipe)
                self.assertEqual(back["actions"], [{"op": "clear_key", "key": "CLAW.Link"},
                                                   {"op": "update_model"}])
                self.assertEqual(back["state"]["sourceMorphs"], original["sourceMorphs"])
                self.assertEqual(beast, original)

    def test_corrupt_generation_is_refused(self):
        for generation in (-1, "1", True):
            state = self.plan()["state"]
            state["generation"] = generation
            with self.subTest(generation=generation), self.assertRaises(ValueError):
                self.plan(state)

    def test_changed_human_preset_changes_body_not_identity_traits(self):
        first = self.plan()
        changed = self.plan(first["state"], human={"BigTorso": 0.1})
        a, b = first["state"]["beastMorphs"], changed["state"]["beastMorphs"]
        self.assertNotEqual(a["CLAWTorsoGirth"], b["CLAWTorsoGirth"])
        self.assertEqual(a["CLAWHeadEarSize"], b["CLAWHeadEarSize"])

    def test_native_beasts_get_stable_individual_variation(self):
        a = core.derive("save|wolf-a", None, {}, "male", self.recipe)
        b = core.derive("save|wolf-b", None, {}, "male", self.recipe)
        self.assertNotEqual(a, b)
        self.assertEqual(a, core.derive("save|wolf-a", None, {}, "male", self.recipe))
        self.assertNotIn("CLAWTorsoBreastSize", a)

    def test_unloaded_and_superseded_plans_never_claim_application(self):
        unloaded = self.plan(loaded=False)
        self.assertEqual(unloaded["actions"], [])
        self.assertTrue(unloaded["state"]["pending"])
        back = self.plan(unloaded["state"], is_beast=False)
        self.assertGreater(back["generation"], unloaded["generation"])
        self.assertEqual(back["observedForm"], "human")

    def test_source_signed_values_and_extremes_are_bounded(self):
        morphs = core.derive("save|actor", "HIMBO", {"PecsSize": 10, "PecsMass": -10,
                                                     "TorsoMass": 100}, "male", self.recipe)
        self.assertEqual(morphs["CLAWTorsoChestSize"], 0.0)
        self.assertEqual(morphs["CLAWTorsoGirth"], 0.25)
        self.assertTrue(all(0 <= value <= 1 for value in morphs.values()))

    def test_breast_remains_neutral_until_new_rig(self):
        self.assertEqual(self.plan()["state"]["beastMorphs"]["CLAWTorsoBreastSize"], 0.0)

    def test_bad_state_and_inputs_are_refused(self):
        for value in (float("nan"), float("inf"), True, "0.5"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.plan(human={"Belly": value})
        wrong = self.plan()["state"]
        wrong["identity"] = "another actor"
        with self.assertRaises(ValueError):
            self.plan(wrong)
        with self.assertRaises(ValueError):
            core.derive("", None, {}, "male", self.recipe)
        with self.assertRaises(ValueError):
            core.derive("actor", "UNKNOWN", {}, "male", self.recipe)

    def test_adult_or_misspelled_targets_are_refused(self):
        for name in ("CLAWCrotchVulva", "CLAWTypo"):
            recipe = copy.deepcopy(self.recipe)
            recipe["inherentTraits"][name] = [0, 0.2]
            with self.assertRaises(ValueError):
                core.derive("actor", None, {}, "male", recipe)


if __name__ == "__main__":
    unittest.main()
