"""Compile companion menu/native Papyrus and quest ESP into fresh external staging."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = ROOT / 'src/main/python/build-tools'
sys.path.insert(0, str(HERE))


def module(name):
    spec = importlib.util.spec_from_file_location("claw_data_" + name, HERE / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--import-path", type=Path, action="append", required=True)
    parser.add_argument("--flags", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    builder = module("build-authoring")
    plugin = module("plugin")
    owned = None
    report = {"status": "incomplete", "gameValidated": False, "commands": []}
    try:
        sources = [ROOT / 'src/main/papyrus/claw/CLAWDistributionNative.psc',
                   ROOT / 'src/main/papyrus/integration/CLAWDistributionMenu.psc']
        imports = [p.resolve() for p in args.import_path] + [sources[0].parent]
        if not args.compiler.is_file() or not args.flags.is_file() or not all(p.is_dir() for p in imports):
            raise ValueError("Compiler, flags and every import directory must exist")
        owned = builder.new_staging(args.out, imports)
        scripts = owned / "package/Scripts"
        scripts.mkdir(parents=True)
        source_hashes = {str(p.relative_to(ROOT)): builder.sha(p) for p in sources}
        report["inputs"] = {"sourceSha256": source_hashes, "compiler": str(args.compiler),
                            "compilerSha256": builder.sha(args.compiler), "flags": str(args.flags),
                            "flagsSha256": builder.sha(args.flags), "imports": list(map(str, imports))}
        for source in sources:
            command = [str(args.compiler.resolve()), "--game", "skyrim", "--flags", str(args.flags.resolve()),
                       "--output", str(scripts)]
            for folder in imports:
                command += ["--import", str(folder)]
            command.append(source.name)
            proc = subprocess.run(command, cwd=source.parent, capture_output=True, timeout=120)
            report["commands"].append({"argv": command, "cwd": str(source.parent), "returnCode": proc.returncode})
            (owned / (source.stem + ".stdout.txt")).write_bytes(proc.stdout)
            (owned / (source.stem + ".stderr.txt")).write_bytes(proc.stderr)
            if proc.returncode or not (scripts / (source.stem + ".pex")).is_file():
                raise ValueError("Papyrus compilation failed for " + source.name)
        spriggit = plugin.Spriggit(plugin.WRAPPER)
        tree = ROOT / 'src/main/resources/plugins/CLAW - Distribution'
        command = spriggit.command_prefix + ["deserialize", "--InputPath", str(tree),
                                             "--OutputPath", str(owned / "package/CLAW - Distribution.esp")]
        proc = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=180)
        report["commands"].append({"argv": command, "cwd": str(ROOT), "returnCode": proc.returncode})
        (owned / "spriggit.stdout.txt").write_bytes(proc.stdout)
        (owned / "spriggit.stderr.txt").write_bytes(proc.stderr)
        if proc.returncode or not (owned / "package/CLAW - Distribution.esp").is_file():
            raise ValueError("Quest ESP build failed")
        report["inputs"]["questSourceSha256"] = {str(p.relative_to(tree)): builder.sha(p)
                                                  for p in sorted(tree.rglob("*")) if p.is_file()}
        if source_hashes != {str(p.relative_to(ROOT)): builder.sha(p) for p in sources}:
            raise ValueError("Papyrus sources changed while compiling")
        report["artifacts"] = [{"path": str(p.relative_to(owned / "package")), "sha256": builder.sha(p),
                                 "bytes": p.stat().st_size} for p in sorted((owned / "package").rglob("*")) if p.is_file()]
        report["status"] = "built-game-validation-pending"
        print(str(owned / "package"))
        return 0
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
        report.update(status="failed", error=str(error))
        print("CLAW distribution data: " + str(error), file=sys.stderr)
        return 2
    finally:
        if owned:
            (owned / "distribution-data-build.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
