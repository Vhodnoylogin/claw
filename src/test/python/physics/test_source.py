"""Offline data, isolation and collision-source validation; no game/provider calls."""
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

ROOT = (Path(__file__).resolve().parents[4] / 'src/main/python/physics')
spec=importlib.util.spec_from_file_location("claw_physics_build",ROOT/"build.py")
build=importlib.util.module_from_spec(spec); spec.loader.exec_module(build)

class PhysicsSourceTests(unittest.TestCase):
    def inputs(self):
        return json.loads((ROOT/"recipe.json").read_text()), json.loads((ROOT/"capsules.json").read_text())

    def test_motion_retains_all_chains_and_has_no_shared_settings(self):
        recipe,capsules=self.inputs(); build.validate(recipe,capsules)
        master,bounce=build.render_motion(recipe)
        mappings=[line for line in master.splitlines() if "=" in line]
        self.assertEqual(len(mappings),9)
        self.assertEqual(master.count("\n<\n"),3)
        self.assertTrue(all(line.endswith("=IsRaceFormId(Skyrim.esm|000CDD84)") for line in mappings))
        self.assertNotIn("[Settings]",master)
        self.assertNotIn("Conditions =",bounce)
        self.assertTrue(all(line.startswith("CLAW_") for line in bounce.splitlines() if line and not line.startswith("#")))

    def test_wrong_race_alias_missing_hinge_and_nonfinite_refused(self):
        for change in ("race","alias","hinge","number","negative"):
            recipe,capsules=self.inputs()
            if change=="race":recipe["raceCondition"]="IsFemale()"
            if change=="alias":recipe["groups"][0]["alias"]="Breast"
            if change=="hinge":recipe["groups"][2]["nodes"].remove("TailBone04")
            if change=="number":recipe["common"]["damping"]=float("nan")
            if change=="negative":recipe["common"]["damping"]=-1
            with self.subTest(change=change),self.assertRaises(ValueError):build.validate(recipe,capsules)

    def test_capsules_require_pinned_node_frames_and_no_fake_tail04(self):
        for change in ("frame","hash","tail","radius","endpoint"):
            recipe,capsules=self.inputs()
            if change=="frame":capsules["frame"]="ragdoll"
            if change=="hash":capsules["provenance"]["xp32Sha256"]="missing"
            if change=="tail":capsules["male"]["TailBone04"]=dict(capsules["male"]["TailBone03"])
            if change=="radius":capsules["female"]["TailBone01"]["radius"]=float("inf")
            if change=="endpoint":capsules["male"]["TailBone01"]["p1"]=[1,2]
            with self.subTest(change=change),self.assertRaises(ValueError):build.validate(recipe,capsules)

    def test_generated_source_has_reserved_actor_node_capsule_ids(self):
        recipe,capsules=self.inputs()
        source=build.render_data(recipe,capsules)
        self.assertIn("Return 1129054208 + slot",source)
        self.assertIn("slot != 7",source)
        self.assertIn("NPC EarR [EarR]Bone02",source)
        self.assertEqual(source,build.render_data(recipe,capsules))

    def test_existing_live_and_source_outputs_are_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for path in (root,root/"Data/new",root/"mods/new",ROOT/"generated"):
                with self.subTest(path=path),self.assertRaises(ValueError):build.destination(path)

    def test_build_outputs_only_two_own_configs_and_sources(self):
        recipe,capsules=self.inputs()
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/"new"; manifest=build.build(out,recipe,capsules)
            self.assertFalse(manifest["releaseReady"])
            self.assertEqual(manifest["capsuleSlots"],8)
            self.assertEqual({p.name for p in (out/"SKSE/Plugins").iterdir()},
                {"CBPCMasterConfig_CLAWPhysics.txt","CBPConfig_CLAWPhysics.txt"})
            self.assertFalse(list(out.rglob("*.nif")))
            self.assertFalse(list(out.rglob("CBPCollisionConfig*")))
            self.assertEqual({p.name for p in (out/"Scripts/Source").iterdir()},
                             {"CLAWPhysicsData.psc", *build.SCRIPTS})
            self.assertFalse(manifest["host"]["automaticAssignment"])
            self.assertFalse(manifest["host"]["lifecycleDeliveryValidated"])
            for name in build.SCRIPTS:
                self.assertEqual((out/"Scripts/Source"/name).read_bytes(), (ROOT/"papyrus"/name).read_bytes())

    def test_explicit_provider_snapshot_duplicate_driver_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/"CBPCMasterConfig_Other.txt").write_text("[ConfigMap]\nTailBone01=Other\n")
            with self.assertRaises(ValueError):build.check_master_conflicts(root)
            (root/"CBPCMasterConfig_Other.txt").write_text("[Settings]\nNoJitterFixNodes=TailBone01\n[ConfigMap]\nNPC L Breast=Breast\n")
            build.check_master_conflicts(root)

    def test_missing_effective_provider_snapshot_cannot_claim_no_conflicts(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with self.assertRaises(ValueError):build.check_master_conflicts(root/"missing")
            with self.assertRaises(ValueError):build.check_master_conflicts(root)

    def test_ini_and_own_looking_names_cannot_hide_foreign_driver(self):
        for name in ("CBPCMasterConfig_Other.ini", "cbpcmasterconfig_OTHER.INI", "CBPCMasterConfig_CLAWPhysics.txt"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                root=Path(folder)
                (root/"CBPCMasterConfig.txt").write_text("[ConfigMap]\nNPC L Breast=Breast\n")
                (root/name).write_text("[ConfigMap]\nTailBone01=ForeignAlias\n")
                with self.assertRaises(ValueError):build.check_master_conflicts(root)

    def test_measurement_pin_and_exact_coordinates_are_verified(self):
        recipe,capsules=self.inputs()
        measured={}
        for sex in ("male","female"):
            links=[]
            for name,cap in capsules[sex].items():
                links.append({"bone":name,"points":0 if cap is None else cap["points"],"capsule":cap})
            measured[sex]=[{"links":links}]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"measurement.json"; payload=json.dumps(measured).encode(); path.write_bytes(payload)
            capsules["provenance"]["measurementSha256"]=hashlib.sha256(payload).hexdigest()
            build.verify_measurements(capsules,path)
            capsules["male"]["TailBone01"]["p1"][0]+=1
            with self.assertRaises(ValueError):build.verify_measurements(capsules,path)
            path.write_bytes(payload+b" ")
            with self.assertRaises(ValueError):build.verify_measurements(capsules,path)

if __name__=="__main__":unittest.main()
