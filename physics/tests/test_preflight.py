"""Offline byte-binding counterexamples; these synthetic bytes are not NIF tests."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("claw_resource_preflight", ROOT / "preflight.py")
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)
sys.path.pop(0)
fit_spec = importlib.util.spec_from_file_location("claw_preflight_test_fit", ROOT / "fit-capsules.py")
fit = importlib.util.module_from_spec(fit_spec)
fit_spec.loader.exec_module(fit)


def sign(model):
    keys = ("evaluator", "morphs", "regions", "slots", "weightDependent")
    canonical = json.dumps({key:model[key] for key in keys}, sort_keys=True, separators=(",", ":")).encode()
    model["modelIdentity"] = "CLAW.Physics.CurrentVector." + hashlib.sha256(canonical).hexdigest()
    return model


def fixture(root):
    node, breast = preflight.build.NODES[0], preflight.build.BREAST_NODES[0]
    region = {"points":[[0,0,0],[0,0,1],[1,0,0]], "weightDeltas":[[0,0,0]]*3,
              "deltas":{}, "faces":[[0,1,2]], "contactPasses":1}
    model = sign({"schemaVersion":3, "frame":"node-local-game-units", "domain":[0,1],
                  "weightDependent":True, "contactPasses":1,
                  "evaluator":preflight.build._settings_module.CONTACT_EVALUATOR,
                  "morphs":["CLAWHeadEarSize"],
                  "slots":[{"node":node, **{sex:{"partitionIndices":[0,1,2], "triangleIndices":[0]} for sex in ("male","female")}},
                           {"node":breast, "sexMask":"female", "male":None,
                            "female":{"partitionIndices":[0,1,2], "triangleIndices":[0]}}],
                  "regions":{sex+"/"+node:copy.deepcopy(region) for sex in ("male","female")}})
    model["regions"]["female/"+breast] = copy.deepcopy(region)
    sign(model)
    binding = {"schemaVersion":1, "resources":{}}
    pins = []
    for role in preflight.ROLES:
        actual = root / (role + ".bin")
        # Identical bytes remain two independently bound endpoint files.
        payload = role.replace("Weight1", "").encode()
        actual.write_bytes(payload)
        source = "authoring/arbitrary-"+role+".input"
        pins.append({"path":source, "bytes":len(payload), "sha256":hashlib.sha256(payload).hexdigest()})
        binding["resources"][role] = {"modelSourcePath":source, "actualPath":actual.name}
    model["sourceInputs"] = pins
    model_path = root / "model.json"; model_path.write_text(json.dumps(model))
    binding_path = root / "bindings.json"; binding_path.write_text(json.dumps(binding))
    header = root / "model.h"; fit.write_cpp_model(model, header)
    data = root / "data.psc"
    recipe = json.loads((ROOT/"recipe.json").read_text())
    capsules = json.loads((ROOT/"capsules.json").read_text())
    data.write_text(preflight.build.render_data(recipe, capsules, model))
    provider = root / "provider"; provider.mkdir()
    (provider/"CBPCMasterConfig.txt").write_text("[ConfigMap]\nNPC L Breast=Human=IsFemale()\n")
    (provider/"cbp.dll").write_bytes(b"synthetic-dll-not-runtime-qualified")
    return model_path, binding_path, header, data, provider, root/"result"


class PreflightTests(unittest.TestCase):
    def test_exact_seven_roles_and_full_generated_sources_match_without_runtime_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            args = fixture(Path(directory)); report = preflight.run_preflight(*args)
            self.assertTrue(report["staticInputsMatched"])
            self.assertFalse(report["runtimeQualified"])
            self.assertFalse(report["model"]["sourcePinsAreIdentityBound"])
            self.assertEqual(len(report["resources"]), 7)
            self.assertTrue(report["runtimeGates"])
            self.assertFalse((args[-1]/"FAILED-unverified-do-not-install").exists())

    def test_same_identity_cannot_hide_a_changed_actual_weight_endpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); args = fixture(root)
            (root/"femaleWeight1Nif.bin").write_bytes(b"changed")
            report = preflight.run_preflight(*args)
            self.assertFalse(report["staticInputsMatched"])
            self.assertEqual([row["role"] for row in report["resources"] if not row["matched"]], ["femaleWeight1Nif"])
            self.assertTrue((args[-1]/"FAILED-unverified-do-not-install").is_file())

    def test_header_identity_cannot_hide_changed_numeric_support(self):
        with tempfile.TemporaryDirectory() as directory:
            args = fixture(Path(directory))
            args[2].write_text(args[2].read_text().replace("s.points={{0,0,0}", "s.points={{0.1,0,0}", 1))
            report = preflight.run_preflight(*args)
            self.assertFalse(report["checks"]["nativeHeader"])
            self.assertFalse(report["staticInputsMatched"])

    def test_psc_identity_cannot_hide_changed_reserved_index_or_male_p1_gate(self):
        for old, new in (("Return 1129054208 + slot", "Return 42 + slot"),
                         ("If !female && (slot == 1)", "If female && (slot == 1)")):
            with self.subTest(old=old), tempfile.TemporaryDirectory() as directory:
                args = fixture(Path(directory)); text = args[3].read_text()
                self.assertIn(old, text); args[3].write_text(text.replace(old,new))
                report = preflight.run_preflight(*args)
                self.assertFalse(report["checks"]["hostData"])
                self.assertFalse(report["staticInputsMatched"])

    def test_missing_files_and_unsupplied_sources_produce_retained_blocking_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); args = list(fixture(root))
            (root/"maleTri.bin").unlink(); args[2] = None; args[4] = None
            report = preflight.run_preflight(*args)
            self.assertFalse(report["staticInputsMatched"])
            self.assertIn("error", next(row for row in report["resources"] if row["role"] == "maleTri"))
            self.assertEqual(len(report["errors"]), 2)
            self.assertTrue((args[-1]/"physics-preflight.json").is_file())

    def test_duplicate_source_pins_and_reused_or_missing_roles_are_never_guessed(self):
        for mutation in ("duplicate", "reused-source", "reused-actual", "missing-role", "unknown-source", "bool-bytes"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                args = fixture(Path(directory))
                model = json.loads(args[0].read_text()); binding = json.loads(args[1].read_text())
                if mutation == "duplicate": model["sourceInputs"].append(model["sourceInputs"][0])
                if mutation == "bool-bytes": model["sourceInputs"][0]["bytes"] = True
                if mutation == "reused-source": binding["resources"]["maleWeight1Nif"]["modelSourcePath"] = model["sourceInputs"][0]["path"]
                if mutation == "reused-actual": binding["resources"]["maleWeight1Nif"]["actualPath"] = "maleNif.bin"
                if mutation == "missing-role": del binding["resources"]["maleWeight1Nif"]
                if mutation == "unknown-source": binding["resources"]["maleNif"]["modelSourcePath"] = "unrecorded"
                args[0].write_text(json.dumps(model)); args[1].write_text(json.dumps(binding))
                report = preflight.run_preflight(*args)
                self.assertFalse(report["staticInputsMatched"])
                self.assertTrue(report["errors"])

    def test_provider_conflict_or_missing_dll_blocks_offline_receipt(self):
        for mutation in ("conflict", "dll"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                args = fixture(Path(directory))
                if mutation == "conflict": (args[4]/"CBPCMasterConfig.txt").write_text("[ConfigMap]\nNPC L PreBreast P1=Other\n")
                else: (args[4]/"cbp.dll").unlink()
                report = preflight.run_preflight(*args)
                self.assertFalse(report["staticInputsMatched"])

    def test_late_resource_change_and_provider_inventory_addition_block_completion(self):
        original_verify = preflight.Inputs.verify
        for target in ("resource", "provider"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); args = fixture(root)
                def mutate_then_verify(inputs):
                    if target == "resource": (root/"maleTri.bin").write_bytes(b"late mutation")
                    else: (args[4]/"CBPConfig_Late.txt").write_text("CLAW_Tail.stiffness 0.5\n")
                    original_verify(inputs)
                with patch.object(preflight.Inputs, "verify", mutate_then_verify):
                    report = preflight.run_preflight(*args)
                self.assertFalse(report["staticInputsMatched"])
                self.assertIn("changed", report["errors"][0])


if __name__ == "__main__":
    unittest.main()
