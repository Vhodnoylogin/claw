"""Build the complete, pinned Elegant texture payload outside Git and live mods.

The 306 coat diffuses keep their runtime library paths. Shared textures retain
their original paths; alternate eyes and the Lobo patch are namespaced, so merely
bundling them cannot override an installed eye/companion choice.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tempfile
import zlib

import coat_library as c

MANIFEST = "bundle-receipt.json"
METRICS = "palette-metrics.json"
ROOT = Path(__file__).resolve().parents[4]
ALL_INDEX = ROOT / "src/main/resources/appearance/elegant-2k-2.1.textures.json"
COAT_INDEX = ROOT / "src/main/resources/appearance/elegant-2k-2.1.inventory.json"
POLICY = ROOT / "src/main/resources/appearance/CoatPolicy.xml"
POLICY_PATH = "SKSE/Plugins/CLAW/CoatPolicy.xml"


def validate_inventory(value, coat_index):
    c.validate_inventory(coat_index)
    c.require(isinstance(value, dict) and set(value) == {"schemaVersion", "source", "files", "paletteMetricsSha256"}
              and value["schemaVersion"] == 1 and value["source"] == c.SOURCE,
              "Wrong complete-texture inventory identity")
    c.require(isinstance(value["paletteMetricsSha256"], str) and c._HEX64.fullmatch(value["paletteMetricsSha256"]),
              "Missing approved measured palette identity")
    rows = value["files"]
    c.require(isinstance(rows, list) and len(rows) == 355, "Expected all 355 original DDS members")
    members, targets = set(), set()
    coats = c.source_entries(coat_index)
    for row in rows:
        c.require(isinstance(row, dict) and set(row) == {"archivePath", "gamePath", "bytes", "crc32"},
                  "Wrong texture inventory fields")
        member, target = c.relative_path(row["archivePath"]), c.relative_path(row["gamePath"])
        c.require(member == row["archivePath"] and target == row["gamePath"] and
                  member.startswith("Elegant Werewolf Replacer 2K 2026/") and
                  target.startswith("textures/") and target.lower().endswith(".dds"), "Invalid texture path")
        c.require(member.casefold() not in members and target.casefold() not in targets, "Texture path collision")
        members.add(member.casefold()); targets.add(target.casefold())
        c.require(type(row["bytes"]) is int and 128 <= row["bytes"] <= 64 * 1024 * 1024 and
                  isinstance(row["crc32"], str) and c._HEX8.fullmatch(row["crc32"]), "Invalid texture size/CRC")
        if member in coats:
            slug, original = coats[member]
            c.require(target == c.game_path(slug, original["name"]) and
                      all(row[key] == original[key] for key in ("bytes", "crc32")), "Coat inventory mismatch")
    c.require(set(coats) <= {row["archivePath"] for row in rows}, "Missing coat diffuse members")
    return value


def extract(stream, ordered, rows, stage):
    records = []
    for member in ordered:
        row = rows[member]
        target = stage / PurePosixPath(row["gamePath"])
        target.parent.mkdir(parents=True, exist_ok=True)
        digest, crc, remaining, header = hashlib.sha256(), 0, row["bytes"], bytearray()
        with target.open("xb") as output:
            while remaining:
                block = stream.read(min(remaining, 1024 * 1024))
                c.require(bool(block), "Truncated full-texture stream")
                remaining -= len(block); digest.update(block); crc = zlib.crc32(block, crc)
                header.extend(block[:max(0, 148 - len(header))]); output.write(block)
        c.require(f"{crc:08x}" == row["crc32"], "Texture stream order/CRC mismatch")
        records.append({**row, "sha256": digest.hexdigest(), "dds": c.dds_header(header)})
    c.require(not stream.read(1), "Unexpected trailing texture bytes")
    return records


def prepare(archive, executable, metrics, output, inventory=ALL_INDEX, coat_inventory=COAT_INDEX, policy=POLICY):
    index = validate_inventory(c.read_json(Path(inventory)), c.read_json(Path(coat_inventory)))
    coats = c.read_json(Path(coat_inventory))
    archive = Path(archive).absolute()
    output = c.new_destination(output, [archive.parent, Path(executable).absolute().parent,
                                        Path(__file__).resolve().parent])
    c.require(archive.stat().st_size == c.SOURCE["archiveBytes"] and
              c.digest_file(archive) == c.SOURCE["archiveSha256"], "Wrong original Elegant archive")
    c.require(c.digest_file(Path(metrics)) == index["paletteMetricsSha256"], "Unreviewed palette metrics")
    reader = c.SevenZipArchive(executable, archive)
    rows = {row["archivePath"]: row for row in index["files"]}
    listing = reader.describe()
    dds = [c.relative_path(row["Path"]) for row in listing if row["Path"].lower().endswith(".dds")]
    c.require(len(dds) == len(rows) and set(dds) == set(rows), "Original DDS inventory is incomplete")
    ordered = c.selected_order(listing, {key: ("", row) for key, row in rows.items()})
    with tempfile.TemporaryDirectory(prefix=".claw-textures-", dir=output.parent) as temporary:
        temporary = Path(temporary); stage = temporary / "payload"; stage.mkdir()
        selection = temporary / "members.txt"
        selection.write_text("\n".join(ordered) + "\n", encoding="utf-8")
        with (temporary / "7z.stderr").open("w+b") as errors:
            process = reader.stream(selection, errors)
            try:
                records = extract(process.stdout, ordered, rows, stage)
            except BaseException:
                if process.poll() is None: process.kill()
                process.wait(); raise
            finally:
                process.stdout.close()
            c.require(process.wait() == 0, "7-Zip texture extraction failed")
        by_member = {row["archivePath"]: row for row in records}
        coat_records = {key: {**entry, **{field: by_member[key][field] for field in ("gamePath", "sha256", "dds")}}
                        for key, (_, entry) in c.source_entries(coats).items()}
        manifest = c.make_manifest(coats, coat_records, archive)
        xml = c.runtime_xml(manifest, coats, c.read_json(Path(metrics))).encode("ascii")
        (stage / METRICS).write_bytes(Path(metrics).read_bytes())
        policy_bytes = Path(policy).read_bytes()
        for path, data in ((c.RUNTIME_XML_PATH, xml), (POLICY_PATH, policy_bytes)):
            target = stage / path; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
        payloads = {row["gamePath"]: {"sha256": row["sha256"], "bytes": row["bytes"]} for row in records}
        payloads.update({path: {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
                         for path, data in ((c.RUNTIME_XML_PATH, xml), (POLICY_PATH, policy_bytes))})
        receipt = {"schemaVersion": 1, "source": c.SOURCE, "inventorySha256": c.digest_file(Path(inventory)),
                   "textureCount": len(records), "patternCount": 34, "textures": records, "payloads": payloads,
                   "scope": "All original 2K 2.1 DDS, runtime coat catalog and policy; no donor model/plugin. Elegant remains a declared requirement.",
                   "gameQualified": False}
        (stage / MANIFEST).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        c.new_destination(output, [archive.parent, Path(executable).absolute().parent])
        stage.rename(output)
    verify(output, inventory, coat_inventory, policy)
    return receipt


def verify(folder, inventory=ALL_INDEX, coat_inventory=COAT_INDEX, policy=POLICY):
    folder = Path(folder).absolute(); c.plain_ancestors(folder)
    index = validate_inventory(c.read_json(Path(inventory)), c.read_json(Path(coat_inventory)))
    receipt = c.read_json(folder / MANIFEST)
    c.require(receipt.get("schemaVersion") == 1 and receipt.get("source") == c.SOURCE and
              receipt.get("textureCount") == 355 and receipt.get("patternCount") == 34 and
              receipt.get("inventorySha256") == c.digest_file(Path(inventory)), "Bundle provenance mismatch")
    expected = {row["gamePath"]: row for row in index["files"]}
    texture_rows = receipt.get("textures", [])
    c.require(len(texture_rows) == 355 and {row["gamePath"] for row in texture_rows} == set(expected), "Missing texture coverage")
    for row in texture_rows:
        c.require(all(row.get(key) == value for key, value in expected[row["gamePath"]].items()), "Changed source mapping")
        c.verify_payload(folder / row["gamePath"], row)
    payloads = receipt.get("payloads", {})
    c.require(set(payloads) == set(expected) | {c.RUNTIME_XML_PATH, POLICY_PATH}, "Unexpected bundle payload")
    actual = set()
    for path in folder.rglob("*"):
        c.plain_ancestors(path)
        if path.is_file(): actual.add(path.relative_to(folder).as_posix())
    c.require(actual == set(payloads) | {MANIFEST, METRICS}, "Unexpected or missing bundle files")
    for name, value in payloads.items():
        path = folder / c.relative_path(name)
        c.require(path.stat().st_size == value["bytes"] and c.digest_file(path) == value["sha256"], "Bundle bytes changed")
    c.require((folder / POLICY_PATH).read_bytes() == Path(policy).read_bytes(), "Stale coat policy")
    # Exact catalog namespace/texture hashes are checked against every original diffuse.
    catalog_text = (folder / c.RUNTIME_XML_PATH).read_text(encoding="ascii")
    by_member = {row["archivePath"]: row for row in texture_rows}
    coats = c.read_json(Path(coat_inventory))
    records = {key: {**entry, **{field: by_member[key][field] for field in ("gamePath", "sha256", "dds")}}
               for key, (_, entry) in c.source_entries(coats).items()}
    manifest = c.make_manifest(coats, records, "validated-original-archive")
    c.validate_runtime_xml(catalog_text, manifest, coats)
    c.require(c.digest_file(folder / METRICS) == index["paletteMetricsSha256"], "Palette metrics changed")
    c.require(catalog_text == c.runtime_xml(manifest, coats, c.read_json(folder / METRICS)),
              "Catalog palettes differ from the approved real texture measurements")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("prepare")
    for name in ("archive", "executable", "metrics", "output"): build.add_argument("--" + name, type=Path, required=True)
    check = sub.add_parser("verify"); check.add_argument("--folder", type=Path, required=True)
    args = vars(parser.parse_args()); command = args.pop("command")
    result = prepare(**args) if command == "prepare" else verify(**args)
    print(json.dumps({"textureCount": result["textureCount"], "payloadFiles": len(result["payloads"]), "gameQualified": False}))


if __name__ == "__main__": main()
