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

    def test_cbpc_master_is_required_by_default_but_not_for_fsmp_only_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "hdtSMP64.dll").write_bytes(b"synthetic provider presence")
            default = build.audit_provider(root)
            self.assertEqual([{"error": "Provider snapshot contains no master config"}], default["uncertainties"])
            with self.assertRaisesRegex(ValueError, "no master config"):
                build.require_provider_clear(default)
            fsmp_only = build.audit_provider(root, require_cbpc_master=False)
            build.require_provider_clear(fsmp_only, breast=True)
            self.assertEqual(default["files"], fsmp_only["files"])
            self.assertFalse(fsmp_only["runtimeQualified"])

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

    def test_breast_exclusive_ancestry_and_aliases_block_optional_trial_only(self):
        for row in ("NPC L Breast P1=Other=IsMale()", "Breast P1=Other", "NPC L PreBreast P1=Other",
                    "NPC R PreBreast P1=Other", "Other=CLAW_BreastL"):
            with self.subTest(row=row), tempfile.TemporaryDirectory() as folder:
                audit = self.snapshot(Path(folder), row + "\n")
                build.require_provider_clear(audit)
                with self.assertRaises(ValueError): build.require_provider_clear(audit, breast=True)

    def test_cbpc_exact_ear_tail_ancestors_block_with_or_without_breast_motion(self):
        for node in build.EAR_TAIL_ANCESTORS:
            with self.subTest(node=node), tempfile.TemporaryDirectory() as folder:
                audit = self.snapshot(Path(folder), node + "=Other=IsRaceFormId(Skyrim.esm|000CDD84)\n")
                self.assertEqual([row["node"] for row in audit["earTailConflicts"]], [node])
                for breast in (False, True):
                    with self.assertRaises(ValueError): build.require_provider_clear(audit, breast=breast)

    def test_known_bare_pelvis_records_real_write_targets_without_claiming_runtime(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            # Synthetic image contract tests inventory/parser integration only;
            # the production image/PDB evidence is recorded separately.
            image = b"synthetic role-contract fixture"
            (root / "cbp.dll").write_bytes(image)
            sha = hashlib.sha256(image).hexdigest()
            writes = ("NPC L Pussy02", "NPC R Pussy02", "VaginaB1", "Clitoral1")
            with patch.dict(build.CBPC_WRITE_ROLES, {(sha, "NPC Pelvis [Pelv]"): writes}):
                audit = self.snapshot(root, "NPC Pelvis [Pelv] # stock anchor\n")
            for breast in (False, True): build.require_provider_clear(audit, breast=breast)
            row, = audit["mappings"]
            self.assertEqual(row["node"], row["readOnlyAnchor"])
            self.assertEqual(row["writeNodes"], list(writes))
            self.assertEqual(row["providerSha256"], sha)
            self.assertFalse(audit["runtimeQualified"])
            # A future protected graph containing any child must still conflict.
            for node in writes:
                self.assertEqual(build.provider_conflicts(audit, (node,), ())[0]["node"], row["node"])
            (root / "cbp.dll").write_bytes(image + b"changed")
            with self.assertRaisesRegex(ValueError, "changed after audit"):
                build.verify_provider_unchanged(audit)

    def test_pelvis_role_requires_exact_image_and_bare_row_and_preserves_other_conflicts(self):
        image = b"synthetic role-contract fixture"
        sha = hashlib.sha256(image).hexdigest()
        role = {(sha, "NPC Pelvis [Pelv]"): ("NPC L Pussy02", "NPC R Pussy02", "VaginaB1", "Clitoral1")}
        for provider in (None, image + b"different", image):
            for row in ("NPC Pelvis [Pelv]", "NPC Pelvis [Pelv]=", "NPC Pelvis [Pelv]==",
                        "NPC Pelvis [Pelv]=Other", "NPC Pelvis [Pelv]=CLAW_Tail"):
                with self.subTest(provider=provider, row=row), tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    if provider is not None: (root / "cbp.dll").write_bytes(provider)
                    with patch.dict(build.CBPC_WRITE_ROLES, role):
                        audit = self.snapshot(root, row + "\n")
                    allowed = provider == image and row == "NPC Pelvis [Pelv]"
                    if allowed:
                        build.require_provider_clear(audit, breast=True)
                    else:
                        with self.assertRaises(ValueError): build.require_provider_clear(audit)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / "cbp.dll").write_bytes(image)
            with patch.dict(build.CBPC_WRITE_ROLES, role):
                audit = self.snapshot(root, "NPC Pelvis [Pelv]\nTailBone01=Other\nDifferent=CLAW_EarL\n")
            self.assertEqual(len(audit["mappings"]), 3)
            self.assertEqual(len(audit["earTailConflicts"]), 2)
            with self.assertRaises(ValueError): build.require_provider_clear(audit, breast=True)

    def test_dynamic_smp_ear_tail_ancestors_block_with_or_without_breast_motion(self):
        for node in build.EAR_TAIL_ANCESTORS:
            with self.subTest(node=node), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                (root / "other.xml").write_text('<system><bone name="' + node + '"><mass>1</mass></bone></system>')
                audit = self.snapshot(root)
                self.assertEqual([row["node"] for row in audit["earTailConflicts"]], [node])
                for breast in (False, True):
                    with self.assertRaises(ValueError): build.require_provider_clear(audit, breast=breast)

    def test_explicit_zero_mass_smp_anchors_and_constraint_references_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            protected = (*build.NODES, *build.EAR_TAIL_ANCESTORS, *build.BREAST_NODES, *build.BREAST_ANCESTORS)
            protected = tuple(dict.fromkeys(protected))
            (root / "static.xml").write_text('<system>' + ''.join(
                '<bone name="' + node + '"><mass>0</mass></bone>' for node in protected) + ''.join(
                '<generic-constraint bodyA="' + node + '" bodyB="Unrelated"/>' for node in protected) + '</system>')
            audit = self.snapshot(root, "")
            self.assertEqual(audit["smpReferences"], [])
            self.assertEqual({row["node"] for row in audit["smpStaticReferences"]}, set(protected))
            for breast in (False, True): build.require_provider_clear(audit, breast=breast)

    def test_ambiguous_mass_cannot_disguise_an_ancestor_writer(self):
        for bone in ('<bone name="Tails"/>', '<bone name="Tails" mass="0"/>',
                     '<bone name="Tails" template="Static"/>',
                     '<bone name="Tails"><mass>nan</mass></bone>',
                     '<bone name="Tails"><mass>0</mass><mass>1</mass></bone>',
                     '<bone name="Tails"><mass>0</mass></bone><bone name="Tails"><mass>1</mass></bone>',
                     '<bone name=" Tails "><mass>0</mass></bone>'):
            with self.subTest(bone=bone), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                (root / "other.xml").write_text('<system><bone-default name="Static"><mass>0</mass></bone-default>'
                    + bone + '<generic-constraint bodyA="Tails" bodyB="Unrelated"/></system>')
                audit = self.snapshot(root)
                self.assertTrue(audit["earTailConflicts"])
                for breast in (False, True):
                    with self.assertRaises(ValueError): build.require_provider_clear(audit, breast=breast)

    def test_implicit_creation_before_zero_mass_declaration_is_not_static_proof(self):
        for earlier in ('<generic-constraint bodyA="Tails" bodyB="Other"/>',
                        '<constraint-group><stiffspring-constraint bodyA="Other" bodyB="Tails"/></constraint-group>',
                        '<per-vertex-shape name="UnknownMesh"/>', '<per-triangle-shape name="UnknownMesh"/>'):
            with self.subTest(earlier=earlier), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                (root / "other.xml").write_text('<system><bone-default><mass>1</mass></bone-default>'
                    + earlier + '<bone name="Tails"><mass>0</mass></bone></system>')
                audit = self.snapshot(root)
                for breast in (False, True):
                    with self.assertRaises(ValueError): build.require_provider_clear(audit, breast=breast)

    def test_unrelated_constraint_does_not_disqualify_later_explicit_static_anchor(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "other.xml").write_text('<system><generic-constraint bodyA="OtherA" bodyB="OtherB"/>'
                '<bone name="Tails"><mass>0</mass></bone><generic-constraint bodyA="Tails" bodyB="OtherA"/></system>')
            audit = self.snapshot(root)
            for breast in (False, True): build.require_provider_clear(audit, breast=breast)

    def test_ordinary_unrelated_physics_and_animation_files_are_untouched(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "human.xml").write_text('<system><bone name="NPC L Breast"><mass>1</mass></bone>'
                                            '<bone name="TailBone010"><mass>1</mass></bone></system>')
            (root / "walk.hkx").write_bytes(b"NPC Head [Head] Tails CME TailBone02")
            audit = self.snapshot(root)
            for breast in (False, True): build.require_provider_clear(audit, breast=breast)
            self.assertFalse(any(row["path"].endswith(".hkx") for row in audit["files"]))

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
