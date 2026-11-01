# SPDX-FileCopyrightText: 2026 CLAW contributors
"""Prepare a local-only Elegant palette library; never installs or publishes assets.

The inventory is metadata pinned to one already-qualified upstream archive. 7-Zip
only writes stdout: archive paths are never passed to a filesystem extractor.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import subprocess
import tempfile
import zlib
import xml.etree.ElementTree as ET

LIBRARY_ID = "elegant-2k-2.1"
SOURCE = {"modId": 93336, "fileId": 791439, "version": "2.1.0.0",
          "archiveBytes": 248252479,
          "archiveSha256": "622c7be3d10d4158e84e41ce0eb41941469879800e9a5effbe186aaddb305fcc"}
NAMES = frozenset(("body.dds", "head.dds", "furarms.dds", "furback.dds", "furbelly.dds",
                   "furchest.dds", "furface.dds", "furshoulders.dds", "furtail.dds"))
SURFACES = {"body": "body.dds", "head": "head.dds", "fur_arms": "furarms.dds",
            "fur_back": "furback.dds", "ChestBlend": "furback.dds", "ScalpFurBlend": "furback.dds",
            "fur_belly": "furbelly.dds", "fur_chest": "furchest.dds", "fur_face": "furface.dds",
            "FurfaceBlend": "furface.dds", "fur_shoulders": "furshoulders.dds", "fur_tailtip": "furtail.dds"}
MANIFEST_PATH = f"SKSE/Plugins/CLAW/CoatLibraries/{LIBRARY_ID}.json"
RUNTIME_XML_PATH = "SKSE/Plugins/CLAW/CoatLibrary.xml"
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_HEX8 = re.compile(r"[0-9a-f]{8}\Z")
_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_RESERVED = frozenset(("con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                       *(f"lpt{i}" for i in range(1, 10))))


class ValidationError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def relative_path(value):
    """Validate Windows-safe portable paths without silently collapsing components."""
    require(isinstance(value, str) and bool(value), "A nonempty relative path is required")
    value = value.replace("\\", "/")
    require(not value.startswith("/") and not re.search(r"[\x00-\x1f\x7f:*?\"<>|]", value), "Unsafe relative path")
    parts = value.split("/")
    require(all(part not in ("", ".", "..") and part[-1] not in (" ", ".") for part in parts), "Unsafe path component")
    require(all(part.split(".", 1)[0].casefold() not in _RESERVED for part in parts), "Reserved Windows path component")
    return "/".join(parts)


def game_path(pattern_id, name):
    require(isinstance(pattern_id, str) and _SLUG.fullmatch(pattern_id), "Invalid pattern id")
    require(name in NAMES, "Only the nine coat diffuse files are allowed")
    return f"textures/actors/character/werewolf/claw/{LIBRARY_ID}/{pattern_id}/{name}"


def _unique_json(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path):
    require(path.stat().st_size <= 2 * 1024 * 1024, "Metadata exceeds the 2 MiB limit")
    return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_unique_json)


def digest_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def payload_digests(path):
    digest, crc = hashlib.sha256(), 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block); crc = zlib.crc32(block, crc)
    return digest.hexdigest(), f"{crc:08x}"


def inventory_digest(inventory):
    return hashlib.sha256(json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_inventory(inventory):
    require(isinstance(inventory, dict) and set(inventory) == {"schemaVersion", "libraryId", "source", "patterns"}, "Invalid inventory fields")
    require(type(inventory["schemaVersion"]) is int and inventory["schemaVersion"] == 1, "Unsupported inventory schema")
    require(inventory["libraryId"] == LIBRARY_ID and inventory["source"] == SOURCE, "Unqualified source version or archive identity")
    patterns = inventory["patterns"]
    require(isinstance(patterns, list) and len(patterns) == 34, "Exactly 34 qualified Elegant patterns are required")
    ids, labels, members, targets = set(), set(), set(), set()
    for pattern in patterns:
        require(isinstance(pattern, dict) and set(pattern) == {"id", "label", "files"}, "Invalid pattern fields")
        slug, label = pattern["id"], pattern["label"]
        require(isinstance(slug, str) and _SLUG.fullmatch(slug) and slug not in ids, "Duplicate or invalid pattern id")
        require(isinstance(label, str) and 0 < len(label) <= 80 and label.casefold() not in labels, "Duplicate or invalid pattern label")
        ids.add(slug); labels.add(label.casefold())
        require(isinstance(pattern["files"], list) and len(pattern["files"]) == 9, "Each pattern needs nine diffuse files")
        names = set()
        for entry in pattern["files"]:
            require(isinstance(entry, dict) and set(entry) == {"name", "archivePath", "bytes", "crc32", "group"}, "Invalid source entry fields")
            name = entry["name"]
            require(name in NAMES and name not in names, "Unexpected or duplicate coat filename")
            names.add(name)
            member = relative_path(entry["archivePath"])
            require(member == entry["archivePath"] and member.startswith("Elegant Werewolf Replacer 2K 2026/Patterns/"), "Unexpected archive source prefix")
            require(member.endswith("/Data/Textures/Actors/Character/Werewolf/Elegant/" + name), "Unexpected archive source suffix")
            require(member.casefold() not in members, "Case-insensitive archive collision")
            members.add(member.casefold())
            target = game_path(slug, name)
            require(target.casefold() not in targets, "Case-insensitive output collision")
            targets.add(target.casefold())
            require(type(entry["bytes"]) is int and 128 <= entry["bytes"] <= 32 * 1024 * 1024, "Invalid DDS byte count")
            require(isinstance(entry["crc32"], str) and _HEX8.fullmatch(entry["crc32"]), "Invalid CRC32")
            require(entry["group"] == ("undercoat" if name in ("body.dds", "head.dds") else "fur"), "Incorrect diffuse group")
        require(names == NAMES, "Incomplete pattern")
    return inventory


def source_entries(inventory):
    validate_inventory(inventory)
    return {entry["archivePath"]: (pattern["id"], entry)
            for pattern in inventory["patterns"] for entry in pattern["files"]}


def dds_header(data):
    require(len(data) >= 128 and data[:4] == b"DDS " and struct.unpack_from("<I", data, 4)[0] == 124, "Invalid DDS header")
    height, width = struct.unpack_from("<II", data, 12)
    require(0 < width <= 16384 and 0 < height <= 16384, "Unsupported DDS dimensions")
    fourcc = data[84:88].decode("ascii", errors="replace")
    result = {"width": width, "height": height, "mipLevels": max(1, struct.unpack_from("<I", data, 28)[0]), "fourCC": fourcc}
    if fourcc == "DX10":
        require(len(data) >= 148, "Truncated DX10 DDS header")
        fmt, dimension, misc, array, _ = struct.unpack_from("<5I", data, 128)
        require(dimension == 3 and array == 1 and not misc & 4, "Only single 2D DDS textures are supported")
        result["dxgiFormat"] = fmt
    return result


def validate_manifest(manifest, inventory):
    expected = source_entries(inventory)
    require(isinstance(manifest, dict) and set(manifest) == {"schemaVersion", "libraryId", "source", "surfaceMap", "patterns", "scope"}, "Invalid manifest fields")
    require(type(manifest["schemaVersion"]) is int and manifest["schemaVersion"] == 1, "Unsupported library schema")
    require(manifest["libraryId"] == LIBRARY_ID and manifest["surfaceMap"] == SURFACES, "Wrong library or surface mapping")
    source = manifest["source"]
    require(isinstance(source, dict) and all(source.get(k) == v for k, v in SOURCE.items()), "Wrong source archive identity/version")
    require(source.get("inventorySha256") == inventory_digest(inventory), "Source inventory changed")
    require(isinstance(source.get("archivePath"), str) and bool(source["archivePath"]), "Archive provenance path is required")
    patterns = manifest["patterns"]
    require(isinstance(patterns, list) and len(patterns) == len(inventory["patterns"]), "Manifest palette count mismatch")
    seen, paths = set(), set()
    for pattern, source_pattern in zip(patterns, inventory["patterns"]):
        require(isinstance(pattern, dict) and set(pattern) == {"id", "label", "files"}, "Invalid manifest pattern")
        require(pattern["id"] == source_pattern["id"] and pattern["label"] == source_pattern["label"], "Pattern identity/order mismatch")
        require(isinstance(pattern["files"], list) and len(pattern["files"]) == 9, "Missing pattern file")
        for entry, source_entry in zip(pattern["files"], source_pattern["files"]):
            require(isinstance(entry, dict) and set(entry) == set(source_entry) | {"gamePath", "sha256", "dds"}, "Invalid manifest file")
            require(all(entry[k] == v for k, v in source_entry.items()), "Source file provenance mismatch")
            member = relative_path(entry["archivePath"])
            require(member in expected and member not in seen, "Unknown or duplicate source member")
            seen.add(member)
            path = relative_path(entry["gamePath"])
            require(path == game_path(pattern["id"], entry["name"]) and path.casefold() not in paths, "Output path mismatch/collision")
            paths.add(path.casefold())
            require(isinstance(entry["sha256"], str) and _HEX64.fullmatch(entry["sha256"]), "Invalid file SHA256")
            require(isinstance(entry["dds"], dict) and 0 < entry["dds"].get("width", 0) <= 16384 and 0 < entry["dds"].get("height", 0) <= 16384, "Invalid DDS metadata")
    require(seen == set(expected), "Manifest source coverage mismatch")
    return manifest


def measured_fur_rgb(pattern, metrics_pattern):
    """Return normalized sRGB only when all seven real-file fur samples exist."""
    require(metrics_pattern.get("id") == pattern["id"], "Palette metrics identity mismatch")
    files = metrics_pattern.get("files")
    require(isinstance(files, list) and len(files) == 9, "Palette metrics must cover all nine files")
    measured = {}
    for entry in files:
        require(isinstance(entry, dict) and entry.get("name") not in measured, "Duplicate/invalid metric file")
        measured[entry["name"]] = entry
    values, unavailable = [], False
    for original in pattern["files"]:
        entry = measured.get(original["name"])
        require(entry and entry.get("sha256") == original["sha256"] and entry.get("group") == original["group"], "Metrics source file hash/group mismatch")
        if original["group"] != "fur":
            continue
        sample = entry.get("metrics")
        require(isinstance(sample, dict) and type(sample.get("available")) is bool, "Invalid measurement availability")
        if not sample["available"]:
            unavailable = True
            continue
        require(sample.get("imagePixels") == original["dds"]["width"] * original["dds"]["height"], "Metric DDS dimensions mismatch")
        require(type(sample.get("visibleSamplePixels")) is int and type(sample.get("samplePixels")) is int and
                0 < sample["visibleSamplePixels"] <= sample["samplePixels"], "No alpha-visible measured samples")
        rgb = sample.get("alphaWeightedLinearMeanRgb")
        require(isinstance(rgb, list) and len(rgb) == 3 and all(type(x) in (int, float) and math.isfinite(x) and 0 <= x <= 1 for x in rgb), "Invalid measured RGB")
        values.append(rgb)
    if unavailable:
        return None  # No partial-palette fallback and no invented colour.
    require(len(values) == 7, "Exactly seven fur measurements are required")
    linear = [sum(v[channel] for v in values) / 7 for channel in range(3)]
    return [12.92 * x if x <= .0031308 else 1.055 * x ** (1 / 2.4) - .055 for x in linear]


def runtime_xml(manifest, inventory, metrics=None):
    """Small pugi-compatible runtime view; detailed source provenance stays JSON."""
    validate_manifest(manifest, inventory)
    measured = None
    if metrics is not None:
        require(isinstance(metrics, dict) and metrics.get("schemaVersion") == 1 and
                metrics.get("kind") == "claw-local-coat-palette-metrics" and metrics.get("libraryId") == LIBRARY_ID and
                metrics.get("sourceArchiveSha256") == SOURCE["archiveSha256"], "Metrics source identity mismatch")
        require(isinstance(metrics.get("patterns"), list) and len(metrics["patterns"]) == 34, "Incomplete palette metrics")
        measured = {}
        for item in metrics["patterns"]:
            require(isinstance(item, dict) and item.get("id") not in measured, "Duplicate/invalid palette metrics")
            measured[item["id"]] = item
        require(set(measured) == {p["id"] for p in manifest["patterns"]}, "Palette metrics coverage mismatch")
    root = ET.Element("CoatLibrary", schemaVersion="1", id=LIBRARY_ID, sourceArchiveSha256=SOURCE["archiveSha256"])
    surfaces = ET.SubElement(root, "Surfaces")
    for name, texture in SURFACES.items():
        ET.SubElement(surfaces, "Surface", name=name, texture=texture,
                      group="undercoat" if texture in ("body.dds", "head.dds") else "fur")
    patterns = ET.SubElement(root, "Patterns")
    for pattern in manifest["patterns"]:
        attributes = {"id": pattern["id"], "label": pattern["label"]}
        rgb = measured_fur_rgb(pattern, measured[pattern["id"]]) if measured is not None else None
        if rgb is not None:
            # furR/G/B are normalized sRGB. Average alpha-weighted linear RGB
            # per fur texture, weight the seven textures equally, convert back.
            attributes.update(zip(("furR", "furG", "furB"), (format(x, ".9g") for x in rgb)))
        node = ET.SubElement(patterns, "Pattern", attributes)
        for entry in pattern["files"]:
            ET.SubElement(node, "Texture", name=entry["name"], path=entry["gamePath"],
                          bytes=str(entry["bytes"]), sha256=entry["sha256"])
    ET.indent(root, space="  ")
    text = ET.tostring(root, encoding="unicode", xml_declaration=False) + "\n"
    validate_runtime_xml(text, manifest, inventory)
    return text


def validate_runtime_xml(text, manifest, inventory):
    validate_manifest(manifest, inventory)
    require(isinstance(text, str) and len(text.encode("utf-8")) <= 1024 * 1024 and
            "<!DOCTYPE" not in text and "<!ENTITY" not in text, "Unsafe/oversized runtime XML")
    root = ET.fromstring(text)
    require(root.tag == "CoatLibrary" and root.attrib == {"schemaVersion": "1", "id": LIBRARY_ID,
            "sourceArchiveSha256": SOURCE["archiveSha256"]}, "Invalid runtime library identity/version")
    require([node.tag for node in root] == ["Surfaces", "Patterns"], "Unexpected runtime sections")
    actual_surfaces = {}
    for node in root[0]:
        require(node.tag == "Surface" and not list(node) and set(node.attrib) == {"name", "texture", "group"}, "Invalid runtime surface")
        name = node.get("name")
        require(name in SURFACES and name not in actual_surfaces, "Unknown/duplicate runtime surface")
        texture = SURFACES[name]
        require(node.get("texture") == texture and node.get("group") == ("undercoat" if texture in ("body.dds", "head.dds") else "fur"), "Incorrect runtime material group")
        actual_surfaces[name] = texture
    require(actual_surfaces == SURFACES, "Missing runtime surface")
    require(len(root[1]) == 34, "Incorrect runtime palette count")
    for node, original in zip(root[1], manifest["patterns"]):
        require(node.tag == "Pattern" and set(node.attrib) in ({"id", "label"}, {"id", "label", "furR", "furG", "furB"}) and
                node.get("id") == original["id"] and node.get("label") == original["label"], "Invalid runtime pattern")
        if node.get("furR") is not None:
            try:
                rgb = [float(node.get(key)) for key in ("furR", "furG", "furB")]
            except ValueError as error:
                raise ValidationError("Invalid runtime palette RGB") from error
            require(len(rgb) == 3 and all(math.isfinite(x) and 0 <= x <= 1 for x in rgb), "Invalid runtime palette RGB")
        require(len(node) == 9, "Missing runtime texture")
        for texture, entry in zip(node, original["files"]):
            require(texture.tag == "Texture" and not list(texture) and texture.attrib == {
                "name": entry["name"], "path": entry["gamePath"], "bytes": str(entry["bytes"]), "sha256": entry["sha256"]}, "Runtime texture identity/path/hash mismatch")
    return root


def plain_ancestors(path):
    """Reject existing symlink/reparse ancestors before controlled local writes."""
    for parent in [path, *path.parents]:
        try:
            info = parent.lstat()
        except FileNotFoundError:
            continue
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
                "Symlink/reparse path is not a preparation destination")


def new_destination(path, protected=()):
    """Validate one new external output, matching the project's staging bounds."""
    path = Path(path).absolute()
    plain_ancestors(path)
    path = path.resolve()
    require(not path.exists() and path.parent.is_dir(), "Output must be a new path in an existing isolated parent")
    ancestors = [path, *path.parents]
    require(not any((parent / ".git").exists() or (parent / ".git").is_symlink() for parent in ancestors),
            "Generated output must remain outside Git repositories")
    require(not any(parent.name.casefold() in {"data", "mods", "profiles", "overwrite", "downloads"} for parent in ancestors),
            "Generated output cannot use a live Data/mod/profile/download directory")
    markers = ("ModOrganizer.ini", "ModOrganizer.exe", "SkyrimSE.exe", "SkyrimVR.exe", "TESV.exe")
    require(not any((parent / marker).is_file() for parent in ancestors for marker in markers),
            "Generated output cannot be inside a game or Mod Organizer instance")
    require(not any(path == Path(root).resolve() or path.is_relative_to(Path(root).resolve()) for root in protected),
            "Generated output cannot be inside input/tool directories")
    return path


class SevenZipArchive:
    def __init__(self, executable, archive):
        self.executable, self.archive = Path(executable), Path(archive)
        require(self.executable.is_absolute() and self.executable.is_file(), "An explicit trusted 7-Zip executable is required")
        require(self.archive.is_file(), "Source archive does not exist")

    def describe(self):
        result = subprocess.run([str(self.executable), "l", "-slt", "-sccUTF-8", str(self.archive)],
                                capture_output=True, check=True, text=True, encoding="utf-8")
        entries = []
        for block in result.stdout.split("\n\n"):
            entry = dict(line.split(" = ", 1) for line in block.splitlines() if " = " in line)
            if "CRC" in entry and "Size" in entry:
                entries.append(entry)
        return entries

    def stream(self, selection, stderr):
        # -so never creates archive-controlled filesystem paths. -spd disables
        # wildcards even though every selected member is already pinned/validated.
        return subprocess.Popen([str(self.executable), "e", "-so", "-spd", "-ssc", "-scsUTF-8",
                                 str(self.archive), "-i@" + str(selection)], stdout=subprocess.PIPE, stderr=stderr)


def selected_order(listing, expected):
    selected, found = [], set()
    identities = {path.casefold(): path for path in expected}
    for item in listing:
        member = relative_path(item["Path"])
        if member.casefold() in identities:
            require(member == identities[member.casefold()], "Case-insensitive archive alias collision")
        if member not in expected:
            continue
        require(member not in found, "Duplicate selected archive member")
        found.add(member)
        require(item.get("Attributes") == "A" and item.get("Encrypted") == "-", "Selected source must be a normal unencrypted file")
        entry = expected[member][1]
        require(int(item["Size"]) == entry["bytes"] and item["CRC"].lower() == entry["crc32"], "Archive member size/CRC mismatch")
        selected.append(member)
    require(found == set(expected), "Archive is missing a required palette file")
    return selected


def extract_stream(stream, ordered, expected, destination):
    records = {}
    for member in ordered:
        slug, entry = expected[member]
        target = destination / PurePosixPath(game_path(slug, entry["name"]))
        target.parent.mkdir(parents=True, exist_ok=True)
        digest, crc, remaining, header = hashlib.sha256(), 0, entry["bytes"], bytearray()
        with target.open("xb") as output:
            while remaining:
                block = stream.read(min(remaining, 1024 * 1024))
                require(bool(block), "7-Zip returned a truncated palette stream")
                remaining -= len(block); digest.update(block); crc = zlib.crc32(block, crc)
                if len(header) < 148:
                    header.extend(block[:148 - len(header)])
                output.write(block)
        require(f"{crc:08x}" == entry["crc32"], "Extracted stream order/content CRC mismatch")
        records[member] = {**entry, "gamePath": game_path(slug, entry["name"]),
                           "sha256": digest.hexdigest(), "dds": dds_header(header)}
    require(stream.read(1) == b"", "7-Zip returned unrequested trailing data")
    return records


def make_manifest(inventory, records, archive):
    result = {"schemaVersion": 1, "libraryId": LIBRARY_ID,
              "source": {**SOURCE, "inventorySha256": inventory_digest(inventory), "archivePath": str(archive)},
              "surfaceMap": SURFACES.copy(),
              "patterns": [{"id": p["id"], "label": p["label"], "files": [records[e["archivePath"]] for e in p["files"]]}
                           for p in inventory["patterns"]],
              "scope": "Local-only dependency resources copied from the user's original Elegant archive. Never include these DDS files in CLAW, Git or a public download. No installation, shader change or game qualification is performed."}
    return validate_manifest(result, inventory)


def prepare(archive, inventory, executable, output):
    inventory = validate_inventory(inventory)
    archive = Path(archive).absolute()
    protected = [archive.parent, Path(executable).absolute().parent, Path(__file__).resolve().parent]
    output = new_destination(output, protected)
    require(archive.is_file() and archive.stat().st_size == SOURCE["archiveBytes"], "Source archive size mismatch")
    require(digest_file(archive) == SOURCE["archiveSha256"], "Source archive SHA256 mismatch")
    reader = SevenZipArchive(executable, archive)
    expected = source_entries(inventory)
    ordered = selected_order(reader.describe(), expected)
    with tempfile.TemporaryDirectory(prefix=".claw-coat-", dir=output.parent) as temporary:
        temporary = Path(temporary)
        require(temporary.resolve().parent == output.parent.resolve(), "Temporary extraction escaped the intended parent")
        stage = temporary / "library"; stage.mkdir()
        selection = temporary / "selected.txt"
        selection.write_text("\n".join(ordered) + "\n", encoding="utf-8")
        with (temporary / "sevenzip.stderr").open("w+b") as errors:
            process = reader.stream(selection, errors)
            try:
                records = extract_stream(process.stdout, ordered, expected, stage)
            except BaseException:
                if process.poll() is None:
                    process.kill()
                process.wait(); raise
            finally:
                process.stdout.close()
            code = process.wait()
            errors.seek(0)
            require(code == 0, "7-Zip extraction failed: " + errors.read(2048).decode("utf-8", errors="replace"))
        manifest = make_manifest(inventory, records, archive)
        manifest_file = stage / MANIFEST_PATH
        manifest_file.parent.mkdir(parents=True)
        manifest_file.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        require(new_destination(output, protected) == output, "Output destination changed during extraction")
        # Windows rename refuses an existing directory. Never use replace(),
        # merge/copytree or archive-controlled paths to publish the result.
        stage.rename(output)
    return manifest


def verify_payload(path, entry):
    plain_ancestors(path)
    require(path.is_file() and path.stat().st_size == entry["bytes"], "Missing or wrong-size local DDS")
    sha, crc = payload_digests(path)
    require(sha == entry["sha256"], "Local DDS SHA256 mismatch")
    require(crc == entry["crc32"], "Local DDS CRC does not match the qualified source")
    with path.open("rb") as stream:
        require(dds_header(stream.read(148)) == entry["dds"], "DDS header metadata mismatch")


def verify(library, inventory):
    library = Path(library).absolute(); plain_ancestors(library)
    manifest = validate_manifest(read_json(library / MANIFEST_PATH), inventory)
    for pattern in manifest["patterns"]:
        for entry in pattern["files"]:
            path = library / PurePosixPath(relative_path(entry["gamePath"]))
            verify_payload(path, entry)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare", help="Prepare a NEW local directory; never install or upload it")
    p.add_argument("--archive", required=True, type=Path)
    p.add_argument("--seven-zip", required=True, type=Path, help="Absolute path to trusted installed 7z.exe")
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--inventory", required=True, type=Path)
    v = sub.add_parser("verify", help="Read-only check every prepared DDS against manifest hashes")
    v.add_argument("--library", required=True, type=Path)
    v.add_argument("--inventory", required=True, type=Path)
    args = parser.parse_args()
    inventory = validate_inventory(read_json(args.inventory))
    result = (prepare(args.archive, inventory, args.seven_zip, args.output) if args.command == "prepare"
              else verify(args.library, inventory))
    print(json.dumps({"libraryId": result["libraryId"], "patterns": len(result["patterns"]),
                      "files": sum(len(p["files"]) for p in result["patterns"]),
                      "sourceArchiveSha256": result["source"]["archiveSha256"],
                      "scope": "Local preparation/verification only; no installation or redistribution."}, indent=2))


if __name__ == "__main__":
    main()
