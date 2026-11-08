"""Package the reviewed 0.9 runtime resource lineage with a freshly built DLL.

The pinned resource archive is a generated input, not a claimed fresh body build.
No installation, publication or source bundle is performed by this command.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[4]
RESOURCE_SHA256 = "9b0a915f00588468cef222e7845f3472def6c4f2199b52e90420e829ca73552d"
VERSION = "0.9.0"
NAME = "CLAW - Customizable Lycanthrope Appearance and Weight"
DLL_MEMBER = "10 Native/SKSE/Plugins/CLAWDistribution.dll"
PEX_MEMBER = "10 Native/Scripts/CLAWDistributionNative.pex"
RUNTIME_DOC = ROOT / "src/main/resources/publication/runtime-090/README.md"
FORBIDDEN = {".cpp", ".c", ".h", ".hpp", ".psc", ".pdb", ".obj", ".lib", ".zip", ".7z", ".rar", ".exe"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checked_path(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "\\" in value or ":" in value or str(path) != value:
        raise ValueError("Unsafe archive member: " + value)
    return value


def pin(path: Path) -> dict:
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": digest(path.read_bytes())}


def verify_selections(entries: dict[str, bytes]) -> list[dict]:
    spec = importlib.util.spec_from_file_location("claw_installer", ROOT / "src/main/python/build-tools/build-unified-release.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = ET.fromstring(entries["fomod/ModuleConfig.xml"])
    if b"encoding=" in entries["fomod/ModuleConfig.xml"].lower():
        raise ValueError("Keep the Vortex-compatible XML without an encoding declaration")
    required = {}
    for row in config.find("requiredInstallFiles"):
        if row.tag != "file":
            raise ValueError("Only explicit required files are reviewed")
        source, destination = checked_path(row.attrib["source"]), checked_path(row.attrib["destination"])
        if source not in entries or destination.casefold() in {p.casefold() for p in required}:
            raise ValueError("Missing or duplicate required destination")
        required[destination] = source
    selections = []
    for male in ("HIMBO", "Vanilla"):
        for female in ("CBBE", "3BA", "BHUNP", "UNP", "Vanilla"):
            for host in (False, True):
                optional = module.resolve_selection(config, entries, native=True, male_family=male, family=female, host=host)
                if {p.casefold() for p in required} & {p.casefold() for p in optional}:
                    raise ValueError("Required/optional destination collision")
                selected = required | optional
                family_source = f"20 Human Family/{male}-and-{female}/SKSE/Plugins/CLAW/MorphLinks.xml"
                if selected.get("SKSE/Plugins/CLAW/MorphLinks.xml") != family_source:
                    raise ValueError("Wrong body-family matrix selected")
                if sum(n.lower().endswith(".dds") for n in selected) != 355:
                    raise ValueError("Complete Elegant library missing from a selection")
                if ("CLAW - OBody Integration.esp" in selected) != host:
                    raise ValueError("OBody host selection mismatch")
                if len(selected) != (369 if host else 367):
                    raise ValueError("Nonminimal or incomplete runtime selection")
                if any("physics" in n.lower() or "test_" in n.lower() for n in selected):
                    raise ValueError("Experimental/test payload in working mod")
                selections.append({"male": male, "female": female, "obody": host,
                                   "files": [{"source": src, "destination": dst, "bytes": len(entries[src]), "sha256": digest(entries[src])}
                                             for dst, src in sorted(selected.items())]})
    return selections


def assemble(resource_archive: Path, dll: Path, dll_sha256: str, pex: Path, pex_sha256: str, out: Path, source_ref: str) -> dict:
    resource_bytes, dll_bytes, pex_bytes = resource_archive.read_bytes(), dll.read_bytes(), pex.read_bytes()
    if digest(resource_bytes) != RESOURCE_SHA256:
        raise ValueError("Resource lineage differs from the reviewed alpha archive")
    if digest(dll_bytes) != dll_sha256 or len(dll_bytes) < 500_000 or b"SKSEPlugin_Version" not in dll_bytes:
        raise ValueError("Native DLL does not match the supplied build identity")
    if b"CLAW.Physics.CurrentVector." in dll_bytes:
        raise ValueError("Fitted physics model must not enter this release")
    if digest(pex_bytes) != pex_sha256 or not pex_bytes.startswith(bytes.fromhex("fa57c0de")):
        raise ValueError("Native Papyrus declaration does not match the supplied build identity")
    with zipfile.ZipFile(resource_archive) as reader:
        names = reader.namelist()
        if len(names) != 396 or len(names) != len({n.casefold() for n in names}) or reader.testzip() is not None:
            raise ValueError("Resource archive CRC/member inventory mismatch")
        for name in names:
            checked_path(name)
            if PurePosixPath(name).suffix.lower() in FORBIDDEN:
                raise ValueError("Developer/tool/nested archive content: " + name)
        entries = {name: reader.read(name) for name in names}
    original = dict(entries)
    spec = importlib.util.spec_from_file_location("claw_source_package", ROOT / "src/main/python/build-tools/package-source-build.py")
    source_package = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(source_package)
    config = ET.fromstring(entries["fomod/ModuleConfig.xml"])
    source_package.installer_help(config)
    ET.indent(config, space="  ")
    entries["fomod/ModuleConfig.xml"] = ET.tostring(config, encoding="utf-8", xml_declaration=False) + b"\n"
    info = ET.fromstring(entries["fomod/info.xml"])
    info.find("Name").text, info.find("Version").text = NAME, VERSION
    info.find("Description").text = "Human-derived werewolf shapes and individual coat patterns."
    ET.indent(info, space="  ")
    entries["fomod/info.xml"] = ET.tostring(info, encoding="utf-8") + b"\n"
    entries[DLL_MEMBER] = dll_bytes
    entries[PEX_MEMBER] = pex_bytes
    readme = RUNTIME_DOC.read_bytes()
    if readme.count(b"@SOURCE_REF@") != 1 or not source_ref or any(c in source_ref for c in "\r\n \t"):
        raise ValueError("Invalid release source reference")
    entries["README.md"] = readme.replace(b"@SOURCE_REF@", source_ref.encode("ascii"))
    changed = sorted(n for n in entries if entries[n] != original[n])
    if changed != sorted([DLL_MEMBER, PEX_MEMBER, "README.md", "fomod/info.xml", "fomod/ModuleConfig.xml"]):
        raise ValueError("Unexpected release delta")
    selections = verify_selections(entries)
    out.mkdir(parents=True, exist_ok=False)
    archive = out / (NAME + ".zip")
    with zipfile.ZipFile(archive, "x") as writer:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo(name, (2026, 11, 8, 0, 0, 0))
            info.create_system, info.external_attr = 3, 0o100644 << 16
            writer.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
    with zipfile.ZipFile(archive) as reader:
        if reader.testzip() is not None or {n: digest(reader.read(n)) for n in reader.namelist()} != {n: digest(v) for n, v in entries.items()}:
            raise ValueError("Final archive readback mismatch")
    inventory = [{"path": n, "bytes": len(v), "sha256": digest(v)} for n, v in sorted(entries.items())]
    result = {"version": VERSION, "sourceRef": source_ref, "archive": pin(archive),
              "resourceArchive": pin(resource_archive), "dll": pin(dll), "pex": pin(pex),
              "members": len(entries), "changedMembers": changed, "unchangedMembers": len(entries) - len(changed),
              "all355DDSUnchanged": True, "resourcesRebuilt": False,
              "physicsModelIncluded": False, "physicsHostIncluded": False,
              "noSourcesPdbExeOrNestedArchives": True, "all20InstallerSelectionsPassed": True,
              "installed": False, "gameAccepted": False, "published": False}
    for name, value in (("inventory.json", inventory), ("selections.json", selections), ("verification.json", result)):
        (out / name).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    if resource_archive.read_bytes() != resource_bytes or dll.read_bytes() != dll_bytes or pex.read_bytes() != pex_bytes:
        raise ValueError("Input changed during packaging")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resource-archive", type=Path, required=True)
    parser.add_argument("--dll", type=Path, required=True)
    parser.add_argument("--dll-sha256", required=True)
    parser.add_argument("--pex", type=Path, required=True)
    parser.add_argument("--pex-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-ref", required=True)
    args = parser.parse_args()
    print(json.dumps(assemble(args.resource_archive, args.dll, args.dll_sha256, args.pex, args.pex_sha256, args.out, args.source_ref), indent=2))


if __name__ == "__main__":
    main()
