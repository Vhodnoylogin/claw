# SPDX-FileCopyrightText: 2026 CLAW contributors
import copy
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src/main/python/build-tools"))
import coat_library as c

INDEX = Path(__file__).resolve().parents[4] / "src/main/resources/appearance/elegant-2k-2.1.inventory.json"


def dds(payload=b"texture-payload"):
    header = bytearray(128)
    header[:4] = b"DDS "
    struct.pack_into("<I", header, 4, 124)
    struct.pack_into("<II", header, 12, 4, 4)
    header[84:88] = b"DXT5"
    return bytes(header) + payload


def record(data, name="body.dds"):
    return {"name": name, "bytes": len(data), "crc32": f"{zlib.crc32(data):08x}",
            "sha256": hashlib.sha256(data).hexdigest(), "dds": c.dds_header(data)}


class CoatLibraryTests(unittest.TestCase):
    def setUp(self):
        self.inventory = c.read_json(INDEX)

    def manifest(self):
        records = {path: {**entry, "gamePath": c.game_path(slug, entry["name"]),
                          "sha256": "a" * 64, "dds": {"width": 1024, "height": 1024, "mipLevels": 1, "fourCC": "DX10", "dxgiFormat": 98}}
                   for path, (slug, entry) in c.source_entries(self.inventory).items()}
        return c.make_manifest(self.inventory, records, Path("D:/user-download.7z"))

    def test_complete_pinned_inventory_has_only_34_coherent_nine_diffuse_patterns(self):
        c.validate_inventory(self.inventory)
        self.assertEqual(len(c.source_entries(self.inventory)), 306)
        for p in self.inventory["patterns"]:
            self.assertEqual({f["name"] for f in p["files"]}, c.NAMES)
        self.assertNotIn("eyes.dds", c.NAMES)
        self.assertNotIn("body_n.dds", c.NAMES)

    def test_paths_reject_traversal_absolute_ads_wildcards_and_windows_aliases(self):
        for path in ["../body.dds", "a/../body.dds", "/body.dds", "C:/body.dds", "a//body.dds",
                     "a/./body.dds", "a/body.dds:stream", "a/*", "a/CON.dds", "a/body.dds.", "a/NUL", "a/\x00x"]:
            with self.subTest(path=path), self.assertRaises(c.ValidationError):
                c.relative_path(path)
        self.assertEqual(c.relative_path("a\\b.dds"), "a/b.dds")

    def test_inventory_version_hash_and_pattern_collision_are_rejected(self):
        for mutate in [lambda x: x.update(schemaVersion=2),
                       lambda x: x["source"].update(version="2.0"),
                       lambda x: x["source"].update(archiveSha256="0" * 64),
                       lambda x: x["patterns"][1].update(id=x["patterns"][0]["id"]),
                       lambda x: x["patterns"][1].update(label=x["patterns"][0]["label"].upper())]:
            bad = copy.deepcopy(self.inventory); mutate(bad)
            with self.assertRaises(c.ValidationError):
                c.validate_inventory(bad)

    def test_inventory_missing_diffuse_or_unexpected_normal_is_rejected(self):
        for name in [None, "body_n.dds"]:
            bad = copy.deepcopy(self.inventory)
            if name is None:
                bad["patterns"][0]["files"].pop()
            else:
                bad["patterns"][0]["files"][0]["name"] = name
            with self.assertRaises(c.ValidationError):
                c.validate_inventory(bad)

    def test_wrong_archive_size_and_sha_stop_before_any_output_or_external_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); inputs = root / "inputs"; inputs.mkdir()
            archive = inputs / "wrong.7z"; output = root / "library"
            archive.write_bytes(b"not-the-qualified-archive")
            with self.assertRaisesRegex(c.ValidationError, "size mismatch"):
                c.prepare(archive, self.inventory, Path(sys.executable), output)
            with archive.open("wb") as stream:
                stream.truncate(c.SOURCE["archiveBytes"])
            with self.assertRaisesRegex(c.ValidationError, "SHA256 mismatch"):
                c.prepare(archive, self.inventory, Path(sys.executable), output)
            self.assertFalse(output.exists())
            self.assertEqual(list(root.iterdir()), [inputs])

    def test_new_destination_rejects_git_directory_and_worktree_git_file_ancestors(self):
        for git_directory in [True, False]:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); repo = root / "checkout"; repo.mkdir()
                if git_directory:
                    (repo / ".git").mkdir()
                else:
                    (repo / ".git").write_text("gitdir: elsewhere")
                with self.assertRaisesRegex(c.ValidationError, "Git"):
                    c.new_destination(repo / "library")
                self.assertFalse((repo / "library").exists())

    def test_new_destination_rejects_exact_live_directory_components(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for component in ["Data", "MODS", "profiles", "overwrite", "downloads"]:
                directory = root / component; directory.mkdir()
                with self.subTest(component=component), self.assertRaisesRegex(c.ValidationError, "live"):
                    c.new_destination(directory / "library")
                self.assertFalse((directory / "library").exists())

    def test_new_destination_identifies_live_roots_by_marker_not_folder_substrings(self):
        for marker in ["SkyrimSE.exe", "SkyrimVR.exe", "TESV.exe", "ModOrganizer.ini", "ModOrganizer.exe"]:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); instance = root / "arbitrary-instance-name"; instance.mkdir()
                (instance / marker).write_bytes(b"marker")
                with self.subTest(marker=marker), self.assertRaisesRegex(c.ValidationError, "game or Mod Organizer"):
                    c.new_destination(instance / "library")

    def test_new_destination_preserves_isolated_builds_and_innocent_name_substrings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); builds = root / "Builds" / "modelling-data-downloads-review"; builds.mkdir(parents=True)
            self.assertEqual(c.new_destination(builds / "library"), (builds / "library").resolve())
            self.assertEqual(c.new_destination(builds / "metrics.json"), (builds / "metrics.json").resolve())
            self.assertFalse((builds / "library").exists())

    def test_new_destination_rejects_input_tool_trees_and_existing_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); inputs = root / "inputs"; inputs.mkdir()
            with self.assertRaisesRegex(c.ValidationError, "input/tool"):
                c.new_destination(inputs / "library", [inputs])
            output = root / "output"; output.mkdir(); (output / "retained.txt").write_text("original")
            with self.assertRaisesRegex(c.ValidationError, "new path"):
                c.new_destination(output)
            self.assertEqual((output / "retained.txt").read_text(), "original")

    def test_selected_listing_rejects_missing_case_collision_size_crc_or_symlink(self):
        path, value = next(iter(c.source_entries(self.inventory).items()))
        expected = {path: value}
        good = {"Path": path, "Size": str(value[1]["bytes"]), "CRC": value[1]["crc32"], "Attributes": "A", "Encrypted": "-"}
        self.assertEqual(c.selected_order([good], expected), [path])
        for listing in [[], [good, good], [{**good, "Path": path.upper()}], [{**good, "Size": "1"}],
                        [{**good, "CRC": "00000000"}], [{**good, "Attributes": "AL"}]]:
            with self.assertRaises(c.ValidationError):
                c.selected_order(listing, expected)

    def test_spirit_uses_actual_archive_member_and_correct_namespaced_path(self):
        p = next(p for p in self.inventory["patterns"] if p["id"] == "spirit")
        for entry in p["files"]:
            self.assertIn("/Spirit/Data/Textures/Actors/", entry["archivePath"])
            self.assertTrue(c.game_path(p["id"], entry["name"]).startswith("textures/"))
            self.assertNotIn("/Data/Textures/", c.game_path(p["id"], entry["name"]))

    def test_stream_extraction_validates_each_member_and_never_uses_its_source_path(self):
        data = dds()
        source = "safe/original/body.dds"
        entry = {**record(data), "archivePath": source, "group": "undercoat"}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = c.extract_stream(io.BytesIO(data), [source], {source: ("amber", entry)}, root)
            target = root / c.game_path("amber", "body.dds")
            self.assertEqual(target.read_bytes(), data)
            self.assertFalse((root / source).exists())
            self.assertEqual(result[source]["sha256"], hashlib.sha256(data).hexdigest())

    def test_stream_rejects_truncation_wrong_crc_and_trailing_unrequested_data(self):
        data = dds(); entry = {**record(data), "archivePath": "source", "group": "undercoat"}
        for raw in [data[:-1], data[:-1] + b"X", data + b"extra"]:
            with tempfile.TemporaryDirectory() as tmp, self.assertRaises(c.ValidationError):
                c.extract_stream(io.BytesIO(raw), ["source"], {"source": ("amber", entry)}, Path(tmp))

    def test_manifest_rejects_traversal_collision_missing_hash_or_wrong_source_version(self):
        for mutate in [lambda x: x.update(schemaVersion=2),
                       lambda x: x["source"].update(version="2.0"),
                       lambda x: x["source"].update(inventorySha256="0" * 64),
                       lambda x: x["patterns"][0]["files"][0].update(gamePath="../outside.dds"),
                       lambda x: x["patterns"][0]["files"][1].update(gamePath=x["patterns"][0]["files"][0]["gamePath"]),
                       lambda x: x["patterns"][0]["files"][0].update(sha256="not-a-hash"),
                       lambda x: x["patterns"][0]["files"].pop()]:
            bad = self.manifest(); mutate(bad)
            with self.assertRaises(c.ValidationError):
                c.validate_manifest(bad, self.inventory)

    def test_verify_detects_missing_changed_payload_and_forged_new_manifest_sha(self):
        data = dds(); entry = record(data)
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "body.dds"
            with self.assertRaises(c.ValidationError):
                c.verify_payload(file, entry)
            file.write_bytes(data); c.verify_payload(file, entry)
            altered = data[:-1] + b"X"; file.write_bytes(altered)
            with self.assertRaisesRegex(c.ValidationError, "SHA256"):
                c.verify_payload(file, entry)
            with self.assertRaisesRegex(c.ValidationError, "CRC"):
                c.verify_payload(file, {**entry, "sha256": hashlib.sha256(altered).hexdigest()})

    def test_invalid_dds_or_dx10_array_cannot_be_marked_ready(self):
        for raw in [b"bad", b"bad " + dds()[4:]]:
            with self.assertRaises(c.ValidationError):
                c.dds_header(raw)
        raw = bytearray(dds(b"\0" * 20)); raw[84:88] = b"DX10"
        struct.pack_into("<5I", raw, 128, 98, 3, 0, 2, 0)
        with self.assertRaises(c.ValidationError):
            c.dds_header(raw)

    def test_json_duplicate_keys_are_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.json"; p.write_text('{"schemaVersion":1,"schemaVersion":2}')
            with self.assertRaises(c.ValidationError):
                c.read_json(p)

    def test_runtime_xml_is_deterministic_complete_and_has_no_invented_palette_rgb(self):
        manifest = self.manifest()
        text = c.runtime_xml(manifest, self.inventory)
        self.assertEqual(text, c.runtime_xml(manifest, self.inventory))
        root = c.validate_runtime_xml(text, manifest, self.inventory)
        self.assertEqual(len(root.find("Surfaces")), 12)
        self.assertEqual(len(root.find("Patterns")), 34)
        self.assertTrue(all(len(p) == 9 for p in root.find("Patterns")))
        self.assertNotIn("furR", text)

    def test_runtime_xml_refuses_unsupported_version_paths_missing_surface_and_partial_rgb(self):
        manifest = self.manifest(); text = c.runtime_xml(manifest, self.inventory)
        first = manifest["patterns"][0]["files"][0]
        bad_texts = [text.replace('schemaVersion="1"', 'schemaVersion="2"', 1),
                     text.replace(first["gamePath"], "../outside.dds", 1),
                     text.replace('<Surface name="body" texture="body.dds" group="undercoat" />', "", 1),
                     text.replace('<Pattern id="amber"', '<Pattern furR="0.5" id="amber"', 1),
                     '<!DOCTYPE CoatLibrary>' + text]
        for bad in bad_texts:
            with self.assertRaises(c.ValidationError):
                c.validate_runtime_xml(bad, manifest, self.inventory)

    def test_real_measurement_adapter_requires_source_hash_and_all_fur_measurements(self):
        pattern = self.manifest()["patterns"][0]
        metrics = {"id": pattern["id"], "files": [{"name": f["name"], "sha256": f["sha256"], "group": f["group"],
                   "metrics": {"available": True, "imagePixels": f["dds"]["width"] * f["dds"]["height"],
                               "samplePixels": 1, "visibleSamplePixels": 1, "alphaWeightedLinearMeanRgb": [.5, 0, .5]}}
                  for f in pattern["files"]]}
        rgb = c.measured_fur_rgb(pattern, metrics)
        self.assertAlmostEqual(rgb[0], .7353569830524495)
        self.assertEqual(rgb[1], 0)
        bad = copy.deepcopy(metrics); bad["files"][2]["sha256"] = "b" * 64
        with self.assertRaises(c.ValidationError):
            c.measured_fur_rgb(pattern, bad)
        metrics["files"][2]["metrics"] = {"available": False, "reason": "Unsupported decoder"}
        self.assertIsNone(c.measured_fur_rgb(pattern, metrics))


if __name__ == "__main__":
    unittest.main()
