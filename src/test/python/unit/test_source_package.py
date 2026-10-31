"""Direct-source packaging contracts using synthetic headers, not game fixtures."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "src/main/python/build-tools/package-source-build.py"
SPEC = importlib.util.spec_from_file_location("claw_source_package_contract", SCRIPT)
package = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package)
PIN = "1" * 40


class SourcePackageTests(unittest.TestCase):
    def setUp(self):
        temporary = ROOT / "target/test-source-package"
        temporary.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=temporary)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / "checkout"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "core.autocrlf", "false"], check=True)
        self.write(".gitignore", b"/target/\n")
        self.write("CMakeLists.txt", b"# synthetic native source fixture\n")
        self.write("src/main/cpp/src/Plugin.cpp", b"// synthetic code, not the supplied DLL implementation\n")
        for name in ("package-source-build.py", "build-unified-release.py"):
            self.write("src/main/python/build-tools/" + name,
                       (ROOT / "src/main/python/build-tools" / name).read_bytes())
        for name in ("ModuleConfig.xml", "info.xml"):
            self.write("src/main/resources/publication/unified-installer/" + name,
                       (ROOT / "src/main/resources/publication/unified-installer" / name).read_bytes())
        self.write("src/main/resources/profiles/MorphLinks.xml",
                   (ROOT / "src/main/resources/profiles/MorphLinks.xml").read_bytes())
        self.write("README.md", b"Synthetic package contract fixture; no real native source closure claim.\n")
        for name in ("src/main/papyrus/claw/CLAWDistributionNative.psc",
                     "src/main/papyrus/obody/CLAWOBodySourceHost.psc",
                     "src/main/papyrus/obody/build.py", "src/main/papyrus/obody/README.md",
                     "src/main/python/physics/wiring.py"):
            self.write(name, b"# synthetic source-closure fixture\n")
        subprocess.run(["git", "-C", str(self.root), "add", "--all"], check=True)
        self.native = self.write("target/native/CLAWDistribution.dll", b"MZ" + b"x" * 100)
        self.game = self.write("target/plugins/CLAW.esp", b"TES4" + b"x" * 100)
        self.pex = self.write("target/scripts/CLAWDistributionNative.pex", b"\xfa\x57\xc0\xde" + b"x" * 100)
        self.host = self.write("target/plugins/CLAW - OBody Integration.esp", b"TES4" + b"y" * 100)
        self.host_pex = self.write("target/scripts/CLAWOBodySourceHost.pex", b"\xfa\x57\xc0\xde" + b"y" * 100)
        self.bodies = self.root / "target/bodies"
        for sex in ("male", "female"):
            for ending in ("_0.nif", "_1.nif", ".tri"):
                self.write("target/bodies/" + sex + "bodywerewolf" + ending,
                           (b"PIRT" if ending == ".tri" else b"Gamebryo") + sex.encode() + b"x" * 100)
        self.closure = self.root / "target/source-companion"
        self.manifest = {"schemaVersion": 1, "kind": "claw-native-source-companion",
            "review": {"status": "source-closure-reviewed", "reviewId": "synthetic-contract-fixture-only",
                       "nativeDllSha256": package.sha(self.native.read_bytes()),
                       "nativeSources": {name: package.sha((self.root / name).read_bytes()) for name in (
                           "CMakeLists.txt", "src/main/cpp/src/Plugin.cpp")}},
            "commonlib": {"repository": "https://github.com/example/CommonLibSSE-NG", "commit": PIN,
                          "sourceRoot": "upstream/CommonLib", "license": "NOTICES/CommonLib.txt"}, "files": []}
        for name, role, data in (("upstream/CommonLib/CMakeLists.txt", "source", b"# fixture\n"),
                                 ("upstream/CommonLib/include/SKSE/Version.h", "source", b"// fixture\n"),
                                 ("NOTICES/CommonLib.txt", "license", b"Synthetic notice, not a real CommonLib licence.\n")):
            path = self.write("target/source-companion/" + name, data)
            self.manifest["files"].append({"path": name, "role": role, "bytes": len(data), "sha256": package.sha(data)})
        self.save_manifest()
        self.patcher = patch.object(package, "ROOT", self.root)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def write(self, name, data):
        path = self.root / name
        self.assertTrue(path.resolve().is_relative_to(self.root.resolve()))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def save_manifest(self):
        (self.closure / "companion-manifest.json").write_bytes(package.encoded(self.manifest))

    def arguments(self, *, host=True, output="first"):
        values = dict(native_dll=self.native, bodies_dir=self.bodies, game_esp=self.game,
                      native_pex=self.pex, source_companion_dir=self.closure, commonlib_commit=PIN,
                      out=self.root / "target" / output)
        if host:
            values.update(obody_esp=self.host, obody_pex=self.host_pex)
        return values

    def test_full_package_has_literal_minimal_four_selections_and_no_development_payload(self):
        result = package.build(**self.arguments())
        self.assertEqual([row["runtimeFiles"] for row in result["selections"]], [10, 12, 10, 12])
        files = package.read_zip(Path(result["archive"]).read_bytes())
        self.assertEqual(Path(result["archive"]).name, "CLAW.zip")
        self.assertEqual(sum(name.endswith(".dll") for name in files), 1)
        self.assertEqual(sum(name.endswith(".nif") for name in files), 2)
        self.assertFalse(result["gameOrManagerExecuted"])
        self.assertFalse(result["runtimeInputsCompiledByThisCommand"])
        self.assertFalse(result["historicalArchiveUsedAsSource"])
        self.assertFalse(any(name.startswith(("Source/", "source/", "claw/", "dependencies/")) for name in files))
        self.assertFalse(any(Path(name).suffix.lower() in {".cpp", ".h", ".hpp", ".py", ".ps1", ".psc", ".cmake"} for name in files))
        self.assertFalse(any(Path(name).suffix.lower() in package.ARCHIVES for name in files))
        self.assertEqual(result["packageLayout"], "runtime-results-only")
        self.assertEqual(result["sourceFilesIncluded"], 0)
        self.assertNotIn("claw-source-build.json", files)
        self.assertNotIn("NOTICES/CORRESPONDING-SOURCE.json", files)
        self.assertIn("NOTICES/CommonLib.txt", files)
        self.assertFalse(any(name.startswith("NOTICES/NOTICES/") for name in files))
        self.assertIn(b"https://github.com/Vhodnoylogin/claw", files["README.md"])
        self.assertNotIn(b"cmake -", files["README.md"])
        self.assertIsNone(result["sourceCommit"])
        self.assertFalse(result["sourceReference"]["publicAvailabilityChecked"])
        validation = json.loads((Path(result["archive"]).parent / "source-validation.json").read_text())
        self.assertFalse(validation["sourceIncludedInGameArchive"])
        self.assertIn("claw/src/main/cpp/src/Plugin.cpp", validation["validatedFiles"])
        self.assertIn("dependencies/upstream/CommonLib/include/SKSE/Version.h", validation["validatedFiles"])
        self.assertEqual(set(files), {item["source"] for choice in result["selections"] for item in choice["files"]}
                         | {"fomod/ModuleConfig.xml", "fomod/info.xml", "README.md", "NOTICES/CommonLib.txt", "NOTICES/THIRD-PARTY.txt"})
        for row in result["selections"]:
            matrix = next(item for item in row["files"] if item["path"].endswith("MorphLinks.xml"))
            installed_matrix = ET.fromstring(files[matrix["source"]])
            defaults = installed_matrix.find("Defaults")
            self.assertIn(row["family"], defaults.get("female"))
            installed_profiles = installed_matrix.findall("Profile")
            self.assertEqual(len(installed_profiles), 2)
            self.assertEqual({profile.get("family") for profile in installed_profiles},
                             {"HIMBO", row["family"]})
            self.assertEqual({profile.get("id") for profile in installed_profiles},
                             {defaults.get("male"), defaults.get("female")})

    def test_selected_profiles_preserve_each_authored_rule_and_reject_unknown_family(self):
        original = (self.root / "src/main/resources/profiles/MorphLinks.xml").read_bytes()
        source = ET.fromstring(original)
        for family in ("CBBE", "3BA"):
            actual = ET.fromstring(package.profiles(original, family))
            for profile in actual.findall("Profile"):
                donor = next(row for row in source.findall("Profile") if row.get("id") == profile.get("id"))
                self.assertEqual(profile.attrib, donor.attrib)
                self.assertEqual([rule.attrib for rule in profile], [rule.attrib for rule in donor])
        with self.assertRaisesRegex(ValueError, "supported female body"):
            package.profiles(original, "Unknown")

    def test_absent_optional_host_has_no_broken_host_choice(self):
        result = package.build(**self.arguments(host=False))
        self.assertEqual([row["runtimeFiles"] for row in result["selections"]], [10, 10])
        files = package.read_zip(Path(result["archive"]).read_bytes())
        self.assertNotIn(b'folder source="30 OBody Source"', files["fomod/ModuleConfig.xml"])
        self.assertFalse(any(name.startswith("30 OBody Source/") for name in files))

    def test_missing_pex_and_half_supplied_host_fail_before_output(self):
        for change in ("missing", "half-host"):
            args = self.arguments(output=change)
            if change == "missing": args["native_pex"] = self.root / "target/missing.pex"
            else: args.pop("obody_pex")
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "Missing required|supplied together"):
                package.build(**args)
            self.assertFalse(args["out"].exists())

    def test_frozen_reference_input_cannot_be_relabelled_as_a_fresh_result(self):
        old = self.write("target/references/releases/CLAWDistribution.dll", self.native.read_bytes())
        args = self.arguments();args["native_dll"] = old
        with self.assertRaisesRegex(ValueError, "frozen reference"):
            package.build(**args)
        self.assertFalse(args["out"].exists())

    def test_companion_native_pin_license_and_nested_archive_are_enforced(self):
        original = json.loads(json.dumps(self.manifest))
        for change in ("dll", "source", "commonlib", "license", "archive"):
            self.manifest = json.loads(json.dumps(original))
            if change == "dll": self.manifest["review"]["nativeDllSha256"] = "0" * 64
            if change == "source": self.manifest["review"]["nativeSources"] = {}
            if change == "commonlib": self.manifest["commonlib"]["commit"] = "2" * 40
            if change == "license": self.manifest["files"][-1]["sha256"] = "0" * 64
            if change == "archive":
                self.write("target/source-companion/old-source.zip", b"PK not source")
                self.manifest["files"].append({"path": "old-source.zip", "role": "source", "bytes": 13, "sha256": "0" * 64})
            self.save_manifest();args = self.arguments(output=change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                package.build(**args)
            self.assertFalse(args["out"].exists())

    def test_untracked_source_is_excluded_but_tracked_compiled_source_is_rejected(self):
        self.write("src/untracked.txt", b"untracked fixture must remain unshipped")
        result = package.build(**self.arguments())
        self.assertNotIn("src/untracked.txt", result["sourceSelection"]["selected"])
        self.write("src/main/cpp/compiled.dll", b"MZ forbidden tracked output")
        subprocess.run(["git", "-C", str(self.root), "add", "src/main/cpp/compiled.dll"], check=True)
        with self.assertRaisesRegex(ValueError, "not corresponding source"):
            package.build(**self.arguments(output="compiled"))
        self.assertFalse((self.root / "target/compiled").exists())

    def test_unused_publication_images_donors_scenes_physics_and_vr_are_omitted(self):
        names = ("src/main/resources/publication/media/large-photo.png",
                 "src/main/resources/donors/unused.nif", "src/test/resources/inspection/scene.json",
                 "src/main/python/physics/unshipped.py", "src/main/python/vr/unshipped.py")
        for name in names:
            self.write(name, b"unneeded tracked source fixture" * 10)
        subprocess.run(["git", "-C", str(self.root), "add", *names], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result = package.build(**self.arguments())
        files = package.read_zip(Path(result["archive"]).read_bytes())
        self.assertTrue(set(names).issubset(result["sourceSelection"]["omittedTrackedSource"]))
        for name in names:
            self.assertNotIn("claw/" + name, files)
            self.assertNotIn(name, result["sourceSelection"]["selected"])
        self.assertIn("src/main/python/physics/wiring.py", result["sourceSelection"]["selected"])
        self.assertGreater(sum(row["bytes"] for row in result["sourceSelection"]["omittedTrackedSource"].values()), 0)

    def test_different_weight_endpoints_are_preserved_not_silently_deduplicated(self):
        high = self.write("target/bodies/femalebodywerewolf_1.nif", b"Gamebryo larger high endpoint" + b"y" * 100)
        result = package.build(**self.arguments())
        files = package.read_zip(Path(result["archive"]).read_bytes())
        self.assertEqual(sum(name.endswith(".nif") for name in files), 3)
        for row in result["selections"]:
            item = next(item for item in row["files"] if item["path"].endswith("femalebodywerewolf_1.nif"))
            self.assertEqual(files[item["source"]], high.read_bytes())

    def test_nested_archives_are_rejected_by_name_and_content_without_renaming(self):
        for name in ("source.zip", "source.7z", "source.rar", "source.tar.gz", "source.whl", "source.nupkg"):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "Nested archive"):
                package.validate_no_nested_archives({"Source/" + name: b"fixture bytes"})
        payloads = (package.zip_bytes({"plain.txt": b"ordinary file"}), b"7z\xbc\xaf\x27\x1c" + b"x" * 20,
                    b"Rar!\x1a\x07" + b"x" * 20, b"\x1f\x8b" + b"x" * 20,
                    b"\x00" * 257 + b"ustar" + b"x" * 20)
        for index, data in enumerate(payloads):
            with self.subTest(signature=index), self.assertRaisesRegex(ValueError, "Nested archive"):
                package.validate_no_nested_archives({"Source/misnamed.txt": data})
        disguised = self.write("target/source-companion/upstream/CommonLib/archive-as-source.txt", payloads[0])
        self.manifest["files"].append({"path": "upstream/CommonLib/archive-as-source.txt", "role": "source",
                                      "bytes": disguised.stat().st_size, "sha256": package.sha(disguised.read_bytes())})
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "Nested archive"):
            package.build(**self.arguments(output="renamed-archive"))
        self.assertFalse((self.root / "target/renamed-archive").exists())

    def test_body_tri_requires_little_endian_bodymorph_magic(self):
        self.write("target/bodies/malebodywerewolf.tri", b"TRIP" + b"incorrect reversed body morph header" * 3)
        with self.assertRaisesRegex(ValueError, "Unexpected input header: malebodywerewolf.tri"):
            package.build(**self.arguments(output="wrong-tri"))
        self.assertFalse((self.root / "target/wrong-tri").exists())

    def test_source_commit_is_pinned_only_when_exact_reviewed_source_exists_there(self):
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Source Package Fixture",
                        "-c", "user.email=fixture@example.invalid", "commit", "-qm", "Synthetic source fixture"], check=True)
        commit = subprocess.check_output(["git", "-C", str(self.root), "rev-parse", "HEAD"], text=True).strip()
        args = self.arguments();args["source_commit"] = commit
        result = package.build(**args)
        self.assertEqual(result["sourceCommit"], commit)
        self.assertTrue(result["sourceReference"]["localCommitValidated"])
        self.assertFalse(result["sourceReference"]["publicAvailabilityChecked"])
        files = package.read_zip(Path(result["archive"]).read_bytes())
        self.assertIn(("https://github.com/Vhodnoylogin/claw/tree/" + commit).encode(), files["README.md"])
        self.write("src/main/resources/profiles/MorphLinks.xml", (self.root/"src/main/resources/profiles/MorphLinks.xml").read_bytes().replace(b'<MorphLinkProfiles', b'<MorphLinkProfiles ' ,1))
        args["out"] = self.root / "target/source-drift"
        with self.assertRaisesRegex(ValueError, "Source commit differs"):
            package.build(**args)
        self.assertFalse(args["out"].exists())

    def test_unknown_source_commit_and_header_notices_cannot_enter_runtime_payload(self):
        for requested in ("main", "0" * 40):
            args = self.arguments(output="bad-commit");args["source_commit"] = requested
            with self.subTest(commit=requested), self.assertRaisesRegex(ValueError, "Source commit"):
                package.build(**args)
            self.assertFalse(args["out"].exists())
        data = b"#pragma once\n// synthetic API declaration, not a licence text\n"
        self.write("target/source-companion/NOTICES/API.h", data)
        self.manifest["files"].append({"path": "NOTICES/API.h", "role": "license", "bytes": len(data), "sha256": package.sha(data)})
        self.save_manifest()
        result = package.build(**self.arguments(output="notices"))
        files = package.read_zip(Path(result["archive"]).read_bytes())
        self.assertFalse(any(name.endswith('.h') for name in files))
        self.assertIn('NOTICES/CommonLib.txt', files)

    def test_literal_missing_base_mapping_is_rejected_and_build_is_deterministic(self):
        first = package.build(**self.arguments())
        second = package.build(**self.arguments(output="second"))
        self.assertEqual(first["sha256"], second["sha256"])
        files = package.read_zip(Path(first["archive"]).read_bytes())
        xml = ET.fromstring(files["fomod/ModuleConfig.xml"])
        required = xml.find("requiredInstallFiles")
        required.remove(required[-1])
        files["fomod/ModuleConfig.xml"] = ET.tostring(xml)
        with self.assertRaisesRegex(ValueError, "seven explicit"):
            package.selection_audit(package.read_zip(package.zip_bytes(files)))


if __name__ == "__main__":
    unittest.main()
