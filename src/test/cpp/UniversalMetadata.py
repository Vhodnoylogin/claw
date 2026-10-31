"""Inspect the universal DLL without loading it (requires external pefile)."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

import pefile


def packed(version):
    a, b, c, d = version
    return (a << 24) | (b << 16) | (c << 4) | d


def inspect(dll):
    dll = Path(dll).resolve()
    pe = pefile.PE(str(dll), fast_load=False)
    exports = {entry.name.decode("ascii"): entry.address for entry in pe.DIRECTORY_ENTRY_EXPORT.symbols if entry.name}
    for name in ("SKSEPlugin_Query", "SKSEPlugin_Load", "SKSEPlugin_Version"):
        if name not in exports:
            raise ValueError(f"Missing export: {name}")
    metadata = pe.get_data(exports["SKSEPlugin_Version"], 0x350)
    if len(metadata) != 0x350 or struct.unpack_from("<I", metadata)[0] != 1:
        raise ValueError("Invalid SKSE metadata layout/version")
    flags_ex, flags = struct.unpack_from("<II", metadata, 0x304)
    runtimes = list(struct.unpack_from("<16I", metadata, 0x30C))
    minimum = struct.unpack_from("<I", metadata, 0x34C)[0]
    expected = [(1, 5, 97, 0), (1, 6, 640, 0), (1, 6, 659, 0), (1, 6, 1170, 0),
                (1, 6, 1179, 0), (1, 7, 104, 0), (1, 4, 15, 0)]
    if runtimes != [packed(version) for version in expected] + [0] * 9:
        raise ValueError("Actual DLL metadata does not list exactly the seven candidate versions")
    if flags_ex != 3 or flags != 0 or minimum != 0:
        raise ValueError("Unexpected layout/Address Library/minimum-SKSE metadata")
    imports = sorted(entry.dll.decode("ascii") for entry in pe.DIRECTORY_ENTRY_IMPORT)
    if any(name.lower() in {"openvr_api.dll", "skee64.dll", "skeevr.dll"} for name in imports):
        raise ValueError("DLL has an unconditional engine-specific provider/OpenVR import")
    return {"dll": str(dll), "bytes": dll.stat().st_size,
            "sha256": hashlib.sha256(dll.read_bytes()).hexdigest(),
            "machine": hex(pe.FILE_HEADER.Machine), "exports": sorted(exports), "imports": imports,
            "metadata": {"candidateVersions": [".".join(map(str, version)) for version in expected],
                         "versionIndependenceEx": flags_ex, "versionIndependence": flags,
                         "sharedSKSEMinimum": minimum, "perRuntimeMinimaEnforcedByQueryAndLoad": True},
            "dllLoaded": False, "gameStarted": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dll", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = inspect(args.dll)
    if args.report:
        args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
