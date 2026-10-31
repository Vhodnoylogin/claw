"""Static ownership counterexamples and explicit P1 source packaging; no provider calls."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT = (Path(__file__).resolve().parents[4] / 'src/main/python/physics')
spec = importlib.util.spec_from_file_location("claw_provider_build", ROOT / "build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class ProviderAuditTests(unittest.TestCase):
    def snapshot(self, root, rows="NPC L Breast=Human=IsFemale()\n"):
        (root / "CBPCMasterConfig.txt").write_text("[ConfigMap]\n" + rows, encoding="utf-8")
        return build.audit_provider(root)

    def test_all_duplicate_conditions_are_preserved_without_guessing_winner(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "cbpcmasterconfig_OTHER.INI").write_text(
                "[ConfigMap]\nTailBone01=B=not IsFemale()\nTailBone01=C\n", encoding="utf-8")
            audit = self.snapshot(root, "#TailBone02=Comment\n<\nTailBone01=A=IsFemale() #tail comment\n>\n")
            declarations = [row for row in audit["mappings"] if row["node"] == "TailBone01"]
            self.assertEqual({(row["alias"], row["condition"]) for row in declarations},
                             {("A", "IsFemale()"), ("B", "not IsFemale()"), ("C", "")})
            self.assertEqual(len(audit["earTailConflicts"]), 3)
            self.assertFalse(audit["runtimeQualified"])
            with self.assertRaises(ValueError): build.require_provider_clear(audit)

    def test_settings_and_near_names_are_not_affected_node_mappings(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            audit = self.snapshot(root, "TailBone010=Unrelated\n[Settings]\nNoJitterFixNodes=TailBone01\n")
            build.require_provider_clear(audit)
            self.assertEqual(audit["earTailConflicts"], [])

    def test_private_alias_reuse_on_other_node_or_bounce_file_blocks_build(self):
        for source in ("master", "bounce"):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                if source == "master":
                    (root / "CBPCMasterConfig_Custom.ini").write_text("[ConfigMap]\nDifferentBone=CLAW_EarL=IsMale()\n")
                else:
                    (root / "CBPConfig_Conditioned.txt").write_text("Conditions = IsMale()\nCLAW_EarL.stiffness 0.9\n")
                audit = self.snapshot(root)
                with self.assertRaises(ValueError): build.require_provider_clear(audit)

    def test_breast_ancestry_and_aliases_block_optional_trial_only(self):
        for row in ("NPC L Breast P1=Other=IsMale()", "Breast P1=Other", "CME Spine2 [Spn2]=Other",
                    "NPC Spine2 [Spn2]=Other=IsFemale()", "NPC Root [Root]=Other", "Other=CLAW_BreastL"):
            with self.subTest(row=row), tempfile.TemporaryDirectory() as folder:
                audit = self.snapshot(Path(folder), row + "\n")
                build.require_provider_clear(audit)
                with self.assertRaises(ValueError): build.require_provider_clear(audit, breast=True)

    def test_smp_simulated_spine_ancestor_blocks_p1_even_without_p1_literal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "human-body.xml").write_text('<system><bone name="NPC Spine2 [Spn2]"/></system>')
            audit = self.snapshot(root)
            self.assertEqual(audit["breastConflicts"][0]["node"], "NPC Spine2 [Spn2]")
            with self.assertRaises(ValueError): build.require_provider_clear(audit, breast=True)

    def test_xml_exact_attributes_and_text_detect_potential_writer_without_comments(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            xml = root / "hdtSkinnedMeshConfigs" / "nested.xml"
            xml.parent.mkdir()
            xml.write_text('<system><!-- <bone name="TailBone01"/> -->'
                           '<bone name=" NPC L Breast P1 "/><bone>NPC R Breast P1</bone>'
                           '<bone name="TailBone010"/></system>')
            audit = self.snapshot(root)
            self.assertEqual({row["node"] for row in audit["smpReferences"]}, set(build.BREAST_NODES))
            self.assertEqual(len(audit["breastConflicts"]), 2)
            build.require_provider_clear(audit)
            with self.assertRaises(ValueError): build.require_provider_clear(audit, breast=True)

    def test_unreadable_xml_or_dtd_cannot_support_a_clean_audit(self):
        for text in ("<broken>", '<!DOCTYPE system [<!ENTITY b "TailBone01">]><system>&b;</system>'):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                (root / "settings.xml").write_text(text)
                audit = self.snapshot(root)
                self.assertEqual(len(audit["uncertainties"]), 1)
                with self.assertRaises(ValueError): build.require_provider_clear(audit)

    def test_dtd_rejection_happens_after_utf8_or_utf16_decoding(self):
        for encoding in ("utf-8", "utf-16", "utf-16-le", "utf-16-be"):
            with self.subTest(encoding=encoding), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                declared = "utf-8" if encoding == "utf-8" else "utf-16"
                text = ('<?xml version="1.0" encoding="' + declared + '"?>'
                        '<!DOCTYPE system [<!ENTITY other "Unrelated">]><system>&other;</system>')
                (root / "settings.xml").write_bytes(text.encode(encoding))
                audit = self.snapshot(root)
                self.assertEqual(len(audit["uncertainties"]), 1)
                self.assertIn("DTD/entity", audit["uncertainties"][0]["error"])
                with self.assertRaises(ValueError): build.require_provider_clear(audit, breast=True)

    def test_utf16_without_doctype_still_records_node_references(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "settings.xml").write_bytes(
                '<?xml version="1.0" encoding="utf-16"?><system><bone name="TailBone01"/></system>'.encode("utf-16"))
            audit = self.snapshot(root)
            self.assertEqual(audit["uncertainties"], [])
            self.assertEqual(audit["earTailConflicts"][0]["node"], "TailBone01")

    def test_snapshot_change_addition_and_removal_expire_receipt(self):
        for change in ("bytes", "add", "remove"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                audit = self.snapshot(root)
                build.verify_provider_unchanged(audit)
                if change == "bytes": (root / "CBPCMasterConfig.txt").write_text("[ConfigMap]\nTailBone01=X\n")
                if change == "add": (root / "CBPConfig_New.txt").write_text("CLAW_Tail.stiffness 1\n")
                if change == "remove": (root / "CBPCMasterConfig.txt").unlink()
                with self.assertRaises(ValueError): build.verify_provider_unchanged(audit)

    def test_default_build_embeds_exact_audit_without_enabling_breast_motion(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            baseline = root / "baseline"; baseline.mkdir()
            audit = self.snapshot(baseline)
            recipe = json.loads((ROOT / "recipe.json").read_text())
            capsules = json.loads((ROOT / "capsules.json").read_text())
            out = root / "candidate"
            manifest = build.build(out, recipe, capsules, audit)
            self.assertEqual(manifest["providerAudit"], audit)
            self.assertIsNone(manifest["breastMotion"])
            self.assertFalse((out / "FAILED-unverified-do-not-install").exists())
            self.assertEqual(len(list((out / "SKSE/Plugins").iterdir())), 2)
            for row in manifest["sourceInputs"]:
                self.assertEqual(row["sha256"], hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest())

    def test_breast_trial_requires_reviewed_input_hashes_and_clean_audit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bad = root / "wrong.nif"; bad.write_bytes(b"Not the reviewed rig")
            with self.assertRaisesRegex(ValueError, "body hash differs"):
                build.breast_motion_inputs(bad, bad)
            recipe = json.loads((ROOT / "recipe.json").read_text())
            capsules = json.loads((ROOT / "capsules.json").read_text())
            with self.assertRaisesRegex(ValueError, "explicit provider snapshot"):
                build.build(root / "candidate", recipe, capsules, breast=({}, []))
            self.assertFalse((root / "candidate").exists())

    def mirror(self, folder):
        mirror_root = Path(folder) / "repo/physics"
        shutil.copytree(ROOT, mirror_root, ignore=shutil.ignore_patterns("__pycache__"))
        spec = importlib.util.spec_from_file_location("external_physics_mirror", mirror_root / "build.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return mirror_root, module

    def test_cli_late_source_changes_keep_failed_marker_and_no_success_manifest(self):
        # Mutate external copies only, after the first config was rendered. Each
        # output must use captured inputs and the late disk change must reject it.
        for name in ("recipe.json", "capsules.json", "sources.json", "README.md",
                     "papyrus/CLAWPhysicsActor.psc", "build.py"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                mirror_root, module = self.mirror(folder)
                out = Path(folder) / "candidate"
                actor_before = (mirror_root / "papyrus/CLAWPhysicsActor.psc").read_bytes()
                original_render = module.render_motion
                def change_after_render(recipe):
                    result = original_render(recipe)
                    target = mirror_root / name
                    if name == "recipe.json":
                        changed = json.loads(target.read_bytes())
                        changed["groups"][0]["maxOffset"] = 0.1
                        target.write_text(json.dumps(changed))
                    else:
                        target.write_bytes(target.read_bytes() + b"\n ")
                    return result
                with patch.object(module, "render_motion", side_effect=change_after_render):
                    self.assertEqual(module.main(["--out", str(out)]), 2)
                self.assertTrue((out / "FAILED-unverified-do-not-install").exists())
                self.assertFalse((out / "claw-physics-source.json").exists())
                self.assertEqual((out / "Scripts/Source/CLAWPhysicsActor.psc").read_bytes(), actor_before)
                if name == "recipe.json":
                    self.assertIn("CLAW_EarL.Xmaxoffset 0.35", (out / "SKSE/Plugins/CBPConfig_CLAWPhysics.txt").read_text())

    def test_cli_breast_recipe_change_cannot_publish_a_late_hash_for_old_values(self):
        with tempfile.TemporaryDirectory() as folder:
            mirror_root, module = self.mirror(folder)
            root = Path(folder)
            body, skeleton = root / "body.nif", root / "skeleton.nif"
            # Synthetic bytes/pins exercise integrity only, never NIF/rig claims.
            body.write_bytes(b"synthetic-body-integrity-fixture")
            skeleton.write_bytes(b"synthetic-skeleton-integrity-fixture")
            recipe_path = mirror_root / "breast-motion.json"
            recipe = json.loads(recipe_path.read_bytes())
            recipe["inputs"]["bodyNifSha256"] = hashlib.sha256(body.read_bytes()).hexdigest()
            recipe["inputs"]["skeletonSha256"] = hashlib.sha256(skeleton.read_bytes()).hexdigest()
            recipe_path.write_text(json.dumps(recipe))
            baseline = root / "baseline"; baseline.mkdir()
            (baseline / "CBPCMasterConfig.txt").write_text("[ConfigMap]\n")
            out = root / "candidate"
            original_render = module.render_motion
            def change_after_render(recipe):
                result = original_render(recipe)
                changed = json.loads(recipe_path.read_bytes())
                changed["commonOverrides"]["forceMultipler"] = 0.02
                recipe_path.write_text(json.dumps(changed))
                return result
            with patch.object(module, "render_motion", side_effect=change_after_render):
                self.assertEqual(module.main(["--out", str(out), "--check-provider", str(baseline),
                    "--with-breast-motion", "--breast-body", str(body), "--skeleton", str(skeleton)]), 2)
            self.assertTrue((out / "FAILED-unverified-do-not-install").exists())
            self.assertFalse((out / "claw-physics-source.json").exists())
            self.assertIn("CLAW_BreastL.forceMultipler 0.03",
                          (out / "SKSE/Plugins/CBPConfig_CLAWBreastPhysics.txt").read_text())

    def test_source_bytes_must_compile_to_the_executing_builder(self):
        with tempfile.TemporaryDirectory() as folder:
            mirror_root, module = self.mirror(folder)
            builder = mirror_root / "build.py"
            loaded = builder.read_bytes()
            builder.write_bytes(loaded.replace(b"CLAW.Physics development candidate;", b"CLAW.Physics changed candidate;"))
            # Model stale loaded bytecode against a newer file, before its source
            # capture executes. The compiled live code must reject the mismatch.
            namespace = {"__name__":"stale_external_builder", "__file__":str(builder)}
            with self.assertRaisesRegex(ValueError, "do not match the loaded code"):
                exec(compile(loaded, str(builder), "exec"), namespace)
            with self.assertRaisesRegex(ValueError, "changed since its code was loaded"):
                module.SourceInputs()


if __name__ == "__main__": unittest.main()
