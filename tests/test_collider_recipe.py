"""Safety and CLI contracts for offline collider candidates; no mod assets needed."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("claw_fit_colliders", ROOT / "scripts/fit-colliders.py")
colliders = importlib.util.module_from_spec(spec)
spec.loader.exec_module(colliders)


class ColliderRecipeTests(unittest.TestCase):
    def recipe(self):
        return json.loads((ROOT / "recipes/colliders.json").read_text(encoding="utf-8"))

    def test_recipe_selects_solid_parts_and_explicit_fit_parameters(self):
        recipe = self.recipe()
        colliders.validate_recipe(recipe)
        self.assertEqual(recipe["fit"]["only"], ["body", "head", "claws"])
        self.assertEqual(recipe["fit"]["bundle"], 1)
        self.assertEqual(recipe["fit"]["sliders"], {})
        args = colliders.fit_arguments(recipe, Path("candidate/skeleton.nif"))
        self.assertEqual(args[:2], ["--only", "body,head,claws"])
        self.assertIn("--percentile", args)
        self.assertIn("--bundle", args)
        self.assertIn("--split", args)

    def test_invalid_fit_values_are_rejected(self):
        for key, value in (("percentile", float("nan")), ("percentile", 0),
                           ("bundle", 0), ("bundle", True), ("split", "guess"),
                           ("only", []), ("only", "body"), ("sliders", [])):
            with self.subTest(key=key, value=value):
                recipe = self.recipe()
                recipe["fit"][key] = value
                with self.assertRaises(ValueError):
                    colliders.validate_recipe(recipe)

    def test_existing_live_source_and_archive_destinations_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, mods = root / "repo", root / "mo2/instance/mods"
            source.mkdir(); mods.mkdir(parents=True)
            (source / ".git").mkdir()
            donor = root / "donor/body.nif"; donor.parent.mkdir(); donor.write_bytes(b"input")
            staging = source / "work/collider-candidates"
            existing = root / "existing"; existing.mkdir()
            for out in (existing, source / "scripts/run", mods / "candidate", mods.parent / "profiles/run",
                        donor.parent / "candidate", root / "Game/Data/candidate", root / "downloads/candidate"):
                with self.subTest(out=out), self.assertRaises(ValueError):
                    colliders.validate_destination(out, [donor], mods, source, staging)
            self.assertEqual(colliders.validate_destination(staging / "new", [donor], mods, source, staging),
                             (staging / "new").resolve())
            self.assertFalse((staging / "new").exists())

    def test_foreign_checkout_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); foreign = root / "other"; foreign.mkdir(); (foreign / ".git").write_text("gitdir: elsewhere")
            with self.assertRaises(ValueError):
                colliders.validate_destination(foreign / "new", [], None, root / "repo", root / "repo/work")

    def test_coverage_tracks_counts_and_keeps_unmeasured_bodies(self):
        before = [{"bone": "leg", "clearance": {"points": 10, "outside": .8, "worst": 4}},
                  {"bone": "neck", "clearance": None}]
        after = [{"bone": "leg", "clearance": {"points": 10, "outside": .1, "worst": 2}},
                 {"bone": "neck", "clearance": None}]
        delta = colliders.coverage_delta(before, after)
        self.assertEqual(delta[0]["outsideDelta"], -.7)
        self.assertEqual(delta[0]["worstDelta"], -2)
        self.assertIsNone(delta[1]["after"])
        after[0]["clearance"]["points"] = 11
        with self.assertRaises(ValueError):
            colliders.coverage_delta(before, after)

    def test_cli_failure_is_retained_and_no_candidate_is_written(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            proc = type("Proc", (), {"returncode": 2, "stdout": "", "stderr": "refused"})()
            commands = []
            with patch.object(colliders.subprocess, "run", return_value=proc), self.assertRaises(ValueError):
                colliders.run_cli("python", out / "mb.py", "fit", [], [], out, "fit", 1, commands)
            self.assertEqual((out / "fit.stderr.txt").read_text(), "refused")
            self.assertEqual(commands[0]["returnCode"], 2)
            self.assertFalse((out / "skeleton.nif").exists())

    def test_collision_physics_or_ragdoll_frame_change_is_rejected(self):
        before = [{"bone": "head", "kind": "bhkRigidBody", "physics": {"mass": 4},
                   "ragdoll": {"turn": 90}, "clearance": None}]
        for key, value in (("physics", {"mass": 1}), ("ragdoll", {"turn": 0})):
            after = [dict(before[0], **{key: value})]
            with self.subTest(key=key), self.assertRaises(ValueError):
                colliders.coverage_delta(before, after)

    def test_directory_creation_race_cannot_overwrite_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recipe = root / "colliders.json"; recipe.write_text(json.dumps(self.recipe()))
            mb = root / "mb.py"; mb.write_text("pass")
            settings = root / "morphbench.json"; settings.write_text(json.dumps(self.recipe()["requiredMorphbenchSettings"]))
            inputs = []
            for name in ("body.nif", "body.tri", "skeleton.nif", "skeleton.hkx"):
                path = root / name; path.write_bytes(b"fixture"); inputs.append(path)
            out = root / "existing"; out.mkdir()
            manifest = out / "collider-candidate.json"; manifest.write_bytes(b"preserve")
            argv = ["--recipe", str(recipe), "--body", str(inputs[0]), "--tri", str(inputs[1]),
                    "--skeleton", str(inputs[2]), "--hkx", str(inputs[3]), "--morphbench", str(mb), "--out", str(out)]
            with patch.object(colliders, "validate_destination", return_value=out), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(colliders.main(argv), 2)
            self.assertEqual(manifest.read_bytes(), b"preserve")

    def test_lfs_pointer_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "donor.nif"
            path.write_text("version https://git-lfs.github.com/spec/v1\noid sha256:missing\nsize 50000\n")
            with self.assertRaises(ValueError):
                colliders.digest(path)


if __name__ == "__main__":
    unittest.main()
