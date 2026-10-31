"""Build a standalone CLAW preset mod ZIP from validated XML, without installing it."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

import presets

PREFIX = "CalienteTools/BodySlide/SliderPresets/CLAW/"
MAX_PACKAGE_BYTES = 64 * 1024 * 1024


def package(source):
    source = Path(source)
    if source.is_symlink() or not source.exists():
        raise ValueError("Source must be an existing XML file or directory")
    root = source.parent if source.is_file() else source
    entries = [source] if source.is_file() else sorted(source.rglob("*"))
    if any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()) for p in [source, *entries]):
        raise ValueError("Linked source entries are unsupported")
    files = [p for p in entries if p.is_file() and p.suffix.lower() == ".xml"]
    if not 0 < len(files) <= presets.MAX_PRESETS:
        raise ValueError("Expected 1..4096 XML files")
    names, paths, records, payloads = set(), set(), [], []
    total, count = 0, 0
    for path in files:
        relative = path.relative_to(root)
        for part in relative.parts:
            if (part[-1:] in (".", " ") or re.search(r'[<>:"\\|?*\x00-\x1f]', part)
                    or re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part, re.I)):
                raise ValueError("Path cannot be installed on Windows: " + str(relative))
        destination = PREFIX + relative.as_posix()
        if destination.casefold() in paths:
            raise ValueError("Case-insensitive package path collision")
        paths.add(destination.casefold())
        if path.stat().st_size > presets.MAX_BYTES:
            raise ValueError("Oversized XML file")
        payload = path.read_bytes()
        total += len(payload)
        if total > MAX_PACKAGE_BYTES:
            raise ValueError("Preset package exceeds 64 MiB")
        loaded = presets.parse_xml(payload)
        for row in loaded:
            if row["name"] in names:
                raise ValueError("Duplicate preset name across files: " + row["name"])
            names.add(row["name"])
        count += len(loaded)
        if count > presets.MAX_PRESETS:
            raise ValueError("Too many presets")
        payloads.append((destination, payload))
        records.append({"path": destination, "sha256": hashlib.sha256(payload).hexdigest(),
                        "bytes": len(payload), "presets": len(loaded)})
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, payload in payloads:
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, payload, compresslevel=9)
    result = output.getvalue()
    return result, {"schemaVersion": 1, "sha256": hashlib.sha256(result).hexdigest(),
                    "bytes": len(result), "presetCount": count, "files": records}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.out.suffix.lower() != ".zip" or not args.out.parent.is_dir():
            raise ValueError("Output must be a new ZIP in an existing staging directory")
        payload, receipt = package(args.source)
        with args.out.open("xb") as stream:
            stream.write(payload)
        print(json.dumps({"written": str(args.out), **receipt}, indent=2))
        return 0
    except (ValueError, OSError, TypeError, KeyError, ET.ParseError) as error:
        print("CLAW preset package: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
