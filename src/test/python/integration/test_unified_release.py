"""Read the real frozen payload and actual FOMOD choices; never load a game/DLL."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location("claw_unified_release",ROOT/'src/main/python/build-tools/build-unified-release.py')
release = importlib.util.module_from_spec(spec); spec.loader.exec_module(release)


class UnifiedReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = release.Inputs()
        cls.manifest,cls.entries,cls.provenance = release.compose(cls.inputs,release.FROZEN)

    def config(self): return ET.fromstring(self.entries["fomod/ModuleConfig.xml"])

    def test_five_choices_have_exact_runtime_files_and_only_the_selected_mapping(self):
        reports = release.verify_selections(self.entries)
        self.assertEqual(len(reports),5)
        self.assertEqual([row["runtimeFileCount"] for row in reports],[7,9,9,11,11])
        for row in reports:
            installed = {pin["path"] for pin in row["installedFiles"]}
            self.assertFalse(any(name.startswith("Source/") or name.endswith(".zip") for name in installed))
            self.assertEqual({name for name in installed if name.endswith(".pex")},
                             set() if row["selection"] == "base-only" else
                             {"Scripts/CLAWDistributionNative.pex"} |
                             ({"Scripts/CLAWOBodySourceHost.pex"} if "+OBody" in row["selection"] else set()))

    def test_installer_identity_and_default_archive_use_the_full_owner_name(self):
        expected = "CLAW - Configurable Lycanthrope Anatomy and Weight"
        self.assertEqual(self.config().findtext("moduleName"),expected)
        self.assertEqual(ET.fromstring(self.entries["fomod/info.xml"]).findtext("Name"),expected)
        self.assertEqual(release.ARCHIVE,expected+" - 20261030.zip")

    def test_exact_version_range_rejects_ae_vr_both_neighbors_and_later_build_components(self):
        config = self.config()
        for game in ("1.4.15.0","1.5.97.0","1.6.1170.0","1.7.103.9","1.7.104.1","1.7.104.65535","1.7.105.0","2.0.0.0"):
            with self.subTest(game=game):
                base = release.resolve_selection(config,self.entries,game_version=game)
                self.assertFalse(any(name.endswith((".dll",".pex")) for name in base))
                with self.assertRaisesRegex(ValueError,"Unsupported"):
                    release.resolve_selection(config,self.entries,game_version=game,native=True,family="CBBE")
        for game in ("1.7.104", "1.7.104.0"):
            self.assertIn("SKSE/Plugins/CLAWDistribution.dll",release.resolve_selection(
                config,self.entries,game_version=game,native=True,family="CBBE"))

    def test_racemenu_and_obody_gate_only_their_optional_features(self):
        config = self.config()
        release.resolve_selection(config,self.entries,racemenu=False,obody=False)
        release.resolve_selection(config,self.entries,obody=False,native=True,family="3BA")
        with self.assertRaisesRegex(ValueError,"Unsupported"):
            release.resolve_selection(config,self.entries,racemenu=False,native=True,family="CBBE")
        with self.assertRaisesRegex(ValueError,"Unsupported"):
            release.resolve_selection(config,self.entries,obody=False,native=True,family="CBBE",host=True)
        for kwargs in ({"family":"CBBE"},{"host":True},{"native":True}):
            with self.assertRaises(ValueError): release.resolve_selection(config,self.entries,**kwargs)

    def test_reversing_first_match_pattern_order_is_detected(self):
        config = self.config()
        patterns = config.find(".//dependencyType/patterns")
        first = patterns[0]; patterns.remove(first); patterns.append(first)
        changed = dict(self.entries); changed["fomod/ModuleConfig.xml"] = ET.tostring(config)
        with self.assertRaisesRegex(ValueError,"Unsupported runtime accepted"):
            release.verify_selections(changed)

    def test_source_zip_or_unselected_script_leak_is_detected(self):
        config = self.config()
        ET.SubElement(config.find("requiredInstallFiles"),"folder",source="Source",destination="Source")
        changed = dict(self.entries); changed["fomod/ModuleConfig.xml"] = ET.tostring(config)
        with self.assertRaisesRegex(ValueError,"source selected"):
            release.verify_selections(changed)
        changed = dict(self.entries); changed["00 Base/Scripts/CLAWOBodySourceHost.pex"] = b"leaked"
        with self.assertRaisesRegex(ValueError,"runtime inventory differs"):
            release.verify_selections(changed)

    def test_all_frozen_input_bytes_are_retained_with_provenance_and_no_added_foreign_assets(self):
        origins = set(self.provenance.values())
        for package in self.manifest["packages"]:
            component = package["component"]
            for pin in package["files"]:
                origin = component+"/"+pin["path"]
                self.assertIn(origin,origins)
                destination = next(name for name,value in self.provenance.items() if value == origin)
                self.assertEqual(release.sha(self.entries[destination]),pin["sha256"])
        self.assertEqual(len([name for name in self.entries if name.endswith(".zip")]),1)
        self.assertFalse(any(name.lower().endswith((".dds",".pdb",".exe",".psc")) for name in self.entries))
        self.assertEqual({name for name in self.entries if name.endswith(".nif")},
                         {"00 Base/"+name for name in release.BASE_RUNTIME if name.endswith(".nif")})

    def test_corrupted_frozen_manifest_or_runtime_bytes_are_refused(self):
        original_read = release.Inputs.read
        for target in ("claw-build.json","CLAW.esp"):
            inputs = release.Inputs()
            def corrupt(instance,path):
                payload = original_read(instance,path)
                return payload+b" " if Path(path).name == target else payload
            with self.subTest(target=target), patch.object(release.Inputs,"read",corrupt):
                with self.assertRaises(ValueError): release.checked_frozen(inputs,release.FROZEN)

    def test_unsafe_paths_case_collisions_and_live_or_existing_outputs_are_refused(self):
        for name in ("../outside","/absolute","a\\b","a/../b","C:/bad"):
            with self.subTest(name=name),self.assertRaises(ValueError): release.safe_path(name)
        changed = dict(self.entries); changed["00 Base/claw.esp"] = changed["00 Base/CLAW.esp"]
        with self.assertRaisesRegex(ValueError,"Conflicting"):
            release.resolve_selection(self.config(),changed)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError): release.output_directory(Path(directory))
            with self.assertRaises(ValueError): release.output_directory(Path(directory)/"mods"/"new")
        with self.assertRaises(ValueError): release.output_directory(ROOT/"new")

    def test_whole_zip_is_deterministic_and_manifest_hashes_match_actual_entries(self):
        # Test-local primary contracts keep this test independent of machine paths;
        # the release CLI separately requires the reviewed real source hashes.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); installer = root/"installer"; installer.mkdir()
            for name in ("ModuleConfig.xml","info.xml","README.md"):
                (installer/name).write_bytes((release.INSTALLER/name).read_bytes())
            schema = root/"schema"; schema.write_bytes(b"test-local-schema")
            source = root/"source"; source.write_bytes(b"test-local-installer")
            contract = json.loads((release.INSTALLER/"installer-contract.json").read_text())
            contract["primaryReferences"][0]["sha256"] = release.sha(schema.read_bytes())
            contract["primaryReferences"][1]["sha256"] = release.sha(source.read_bytes())
            (installer/"installer-contract.json").write_text(json.dumps(contract))
            with patch.object(release,"INSTALLER",installer):
                # compose's default was bound at definition time, so pass the
                # actual test installer explicitly while exercising full build.
                original_compose = release.compose
                def local_compose(inputs,frozen): return original_compose(inputs,frozen,installer)
                with patch.object(release,"compose",local_compose):
                    first = release.build(root/"first",schema,source)
                    second = release.build(root/"second",schema,source)
            self.assertEqual(first["sha256"],second["sha256"])
            self.assertEqual(Path(first["archive"]).read_bytes(),Path(second["archive"]).read_bytes())
            with zipfile.ZipFile(first["archive"]) as archive:
                manifest = json.loads(archive.read("claw-unified-release.json"))
                for pin in manifest["files"]:
                    self.assertEqual(release.sha(archive.read(pin["path"])),pin["sha256"])
                self.assertEqual(set(archive.namelist()),{row["path"] for row in manifest["files"]}|{"claw-unified-release.json"})
            selected = json.loads((root/"first/selection-3BA-OBody.json").read_text())
            self.assertFalse(selected["installed"])
            self.assertEqual(selected["archiveSha256"],first["sha256"])
            self.assertEqual(selected["runtimeFileCount"],11)
            mappings = [row for row in selected["installedFiles"] if row["path"] == release.FAMILY_DEST]
            self.assertEqual(len(mappings),1)
            self.assertIn("HIMBO-and-3BA",mappings[0]["archivePath"])


if __name__ == "__main__": unittest.main()
