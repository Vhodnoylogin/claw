"""Motion package boundaries, actual-weight preconditions and late mutation checks."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[4] / "src/main/python/physics"
spec = importlib.util.spec_from_file_location("claw_motion_adapter_tests", ROOT / "motion_adapter.py")
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class MotionAdapterTests(unittest.TestCase):
    def fixture(self, directory, breast=True):
        root = Path(directory)
        inputs = root / "inputs"
        inputs.mkdir()
        resources = {}
        for role in (*adapter.BODY_ROLES, "skeleton"):
            resources[role] = inputs / (role + ".nif")
            resources[role].write_bytes(("synthetic integrity fixture " + role).encode())
        baseline = root / "baseline"
        baseline.mkdir()
        (baseline / "cbp.dll").write_bytes(b"synthetic DLL presence fixture, not a valid provider")
        (baseline / "CBPCMasterConfig.txt").write_text("[ConfigMap]\nNPC L Breast=Human=IsFemale()\n")
        nodes = adapter.source.NODES + adapter.source.BREAST_NODES
        nifs = {}
        for role, path in resources.items():
            weights = {node: [(0, .5)] for node in adapter.source.NODES}
            if breast and role.startswith("female"):
                weights.update({node: [(1, .25)] for node in adapter.source.BREAST_NODES})
            nifs[str(path)] = SimpleNamespace(nodes={node: None for node in nodes},
                                             shapes=[SimpleNamespace(name="skin", bone_weights=weights, verts=[(), ()])])
        api = SimpleNamespace(NifFile=lambda path: nifs[path])
        original_json = adapter.source.SourceInputs.json

        def fixture_json(instance, name):
            data = original_json(instance, name)
            if name == "capsules.json":
                data["provenance"]["xp32Sha256"] = hashlib.sha256(resources["skeleton"].read_bytes()).hexdigest()
            if name == "breast-motion.json":
                data["inputs"]["skeletonSha256"] = hashlib.sha256(resources["skeleton"].read_bytes()).hexdigest()
            return data

        return resources, baseline, api, nifs, patch.object(adapter.source.SourceInputs, "json", fixture_json)

    def test_archive_contains_only_motion_and_uses_current_inspected_p1_endpoints(self):
        with tempfile.TemporaryDirectory() as directory:
            resources, baseline, api, _, fixture = self.fixture(directory)
            out = Path(directory) / "candidate"
            with fixture:
                report = adapter.build_adapter(out, baseline, resources, None, breast=True, api=api)
            with zipfile.ZipFile(out / adapter.PACKAGE_NAME) as package:
                self.assertEqual(set(package.namelist()), {"README.txt",
                    "SKSE/Plugins/CBPCMasterConfig_CLAWMotion.txt", "SKSE/Plugins/CBPConfig_CLAWMotion.txt",
                    "SKSE/Plugins/CBPCMasterConfig_CLAWBreastMotion.txt", "SKSE/Plugins/CBPConfig_CLAWBreastMotion.txt"})
                for name in ("SKSE/Plugins/CBPConfig_CLAWMotion.txt", "SKSE/Plugins/CBPConfig_CLAWBreastMotion.txt"):
                    response = [row.split() for row in package.read(name).decode().splitlines()
                                if ".collisionMultipler " in row or ".collisionMultiplerRot " in row]
                    self.assertTrue(response)
                    self.assertTrue(all(float(value) == 0 for _, value in response))
            # Independently consume the real generated files with the ownership
            # scanner instead of asserting the renderer's own expected strings.
            generated = adapter.source.audit_provider(out / "package/SKSE/Plugins")
            self.assertEqual(len(generated["mappings"]), 11)
            self.assertEqual({row["node"] for row in generated["mappings"]}, set(report["motionNodes"]))
            for row in generated["mappings"]:
                self.assertEqual(row["condition"], "IsRaceFormId(Skyrim.esm|000CDD84)" +
                                 (" AND IsFemale()" if row["node"] in adapter.source.BREAST_NODES else ""))
            self.assertEqual(report["breastResourceProfile"]["inputs"]["bodyNifSha256"], adapter.pin(resources["female0"])["sha256"])
            self.assertFalse(report["collisionResponseEnabled"])
            self.assertFalse(report["runtimeQualified"])
            self.assertFalse((out / "FAILED-unverified-do-not-install").exists())
            # Consume the actual serialized builder receipt with the packager's
            # absolute-path/size/hash contract, without fabricating source rows.
            receipt = json.loads((out / "motion-adapter-build.json").read_bytes())
            self.assertTrue(receipt["sourceInputs"])
            for row in receipt["sourceInputs"]:
                path = Path(row["path"])
                self.assertTrue(path.is_absolute() and path.is_file())
                payload = path.read_bytes()
                self.assertEqual(row["bytes"], len(payload))
                self.assertEqual(row["sha256"], hashlib.sha256(payload).hexdigest())

    def test_explicit_source_profile_is_pinned_from_consumed_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_bytes(b'{"explicit":"source profile"}')
            inputs = adapter.source.SourceInputs(breast_profile=path)
            row = adapter.source_pins(inputs)[-1]
            self.assertEqual(row, {**adapter.pin(path), "role": "explicit-breast-resource-profile"})
            # Late edits cannot silently repin data that the builder did not consume.
            path.write_bytes(b'changed')
            self.assertEqual(adapter.source_pins(inputs)[-1], row)
            with self.assertRaisesRegex(ValueError, "Breast resource profile changed"):
                inputs.verify()

    def test_present_bone_names_without_stored_weights_cannot_enable_p1(self):
        with tempfile.TemporaryDirectory() as directory:
            resources, baseline, api, _, fixture = self.fixture(directory, breast=False)
            out = Path(directory) / "candidate"
            with fixture, self.assertRaisesRegex(ValueError, "no stored skin influence"):
                adapter.build_adapter(out, baseline, resources, None, breast=True, api=api)
            self.assertFalse(out.exists())

    def test_each_weight_endpoint_is_inspected_and_invalid_weights_fail(self):
        for mutation in ("missing-node", "zero", "nan", "vertex"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                resources, baseline, api, nifs, fixture = self.fixture(directory)
                nif = nifs[str(resources["female1"])]
                node = adapter.source.BREAST_NODES[1]
                if mutation == "missing-node": del nif.nodes[node]
                if mutation == "zero": nif.shapes[0].bone_weights[node] = [(0, 0)]
                if mutation == "nan": nif.shapes[0].bone_weights[node] = [(0, float("nan"))]
                if mutation == "vertex": nif.shapes[0].bone_weights[node] = [(2, .5)]
                with fixture, self.assertRaises(ValueError):
                    adapter.build_adapter(Path(directory) / "candidate", baseline, resources, None, breast=True, api=api)

    def test_existing_cbpc_or_smp_writer_blocks_selected_nodes(self):
        for writer in ("cbpc", "smp"):
            with self.subTest(writer=writer), tempfile.TemporaryDirectory() as directory:
                resources, baseline, api, _, fixture = self.fixture(directory)
                if writer == "cbpc":
                    (baseline / "CBPCMasterConfig_Existing.txt").write_text("[ConfigMap]\nTailBone04=Existing\n")
                else:
                    (baseline / "existing.xml").write_text('<system><bone name="NPC Spine2 [Spn2]"/></system>')
                with fixture, self.assertRaisesRegex(ValueError, "Provider snapshot unresolved"):
                    adapter.build_adapter(Path(directory) / "candidate", baseline, resources, None, breast=True, api=api)

    def test_late_resource_change_retains_failure_marker_and_no_success_report(self):
        with tempfile.TemporaryDirectory() as directory:
            resources, baseline, api, _, fixture = self.fixture(directory)
            original_archive = adapter.archive

            def mutate_after_archive(path, files):
                original_archive(path, files)
                resources["female1"].write_bytes(b"changed after inspection")

            out = Path(directory) / "candidate"
            with fixture, patch.object(adapter, "archive", mutate_after_archive), self.assertRaisesRegex(ValueError, "Input changed"):
                adapter.build_adapter(out, baseline, resources, None, api=api)
            self.assertTrue((out / "FAILED-unverified-do-not-install").exists())
            self.assertFalse((out / "motion-adapter-build.json").exists())

    def test_ear_tail_only_zip_is_repeatable_and_never_adds_female_p1(self):
        with tempfile.TemporaryDirectory() as directory:
            resources, baseline, api, _, fixture = self.fixture(directory, breast=False)
            with fixture:
                for name in ("first", "second"):
                    report = adapter.build_adapter(Path(directory) / name, baseline, resources, None, api=api)
                    self.assertEqual(len(report["motionNodes"]), 9)
                    self.assertIsNone(report["breastResourceProfile"])
            self.assertEqual((Path(directory) / "first" / adapter.PACKAGE_NAME).read_bytes(),
                             (Path(directory) / "second" / adapter.PACKAGE_NAME).read_bytes())

    def test_unknown_provider_does_not_create_a_placeholder_package(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "candidate"
            with self.assertRaisesRegex(ValueError, "Unsupported motion provider"):
                adapter.build_adapter(out, None, {}, None, provider="unknown")
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
