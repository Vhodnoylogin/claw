"""Build the original optional finite-host ESP/PEX into fresh external staging.

Requires explicitly supplied, already installed Caprica and Spriggit tools.
Builds, round-trips and independently reads the binary records; never installs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import build
import wiring

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def input_hashes():
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(ROOT.rglob("*"))
            if p.is_file() and p.suffix in {".py", ".psc", ".json", ".md"} and "__pycache__" not in p.parts}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--spriggit", type=Path, required=True)
    parser.add_argument("--flags", type=Path, required=True)
    parser.add_argument("--import-path", type=Path, action="append", required=True)
    parser.add_argument("--fitted-capsules", type=Path, help="explicit node-local affine capsule fit; never install")
    args = parser.parse_args(argv)
    owned = None
    report = {"status": "incomplete", "gameValidated": False, "runtimeEventsExecuted": False, "commands": []}
    try:
        out = build.destination(args.out)
        imports = [p.resolve() for p in args.import_path]
        for path in (args.compiler, args.spriggit, args.flags):
            if not path.is_file():
                raise ValueError("Every explicitly supplied tool/flags file must exist")
        if not all(p.is_dir() for p in imports):
            raise ValueError("Every import directory must exist")
        if any(p == out or p in out.parents for p in imports):
            raise ValueError("Staging cannot be inside script import directories")
        contract = wiring.recipe()
        recipe = json.loads((ROOT / "recipe.json").read_text())
        capsules = json.loads((ROOT / "capsules.json").read_text())
        build.validate(recipe, capsules)
        fitted = build.fitted_model(args.fitted_capsules) if args.fitted_capsules else None
        inputs = input_hashes()
        out.mkdir(parents=True, exist_ok=False)
        owned = out
        temporary = out / "temporary"
        temporary.mkdir()
        environment = dict(os.environ, TEMP=str(temporary), TMP=str(temporary))
        report["inputs"] = {"sourceSha256": inputs, "compiler": str(args.compiler.resolve()), "compilerSha256": sha(args.compiler),
                            "spriggit": str(args.spriggit.resolve()), "spriggitSha256": sha(args.spriggit),
                            "flags": str(args.flags.resolve()), "flagsSha256": sha(args.flags), "imports": list(map(str, imports))}

        def run(command, cwd, name):
            receipt = {"argv": command, "cwd": str(cwd), "returnCode": None}
            report["commands"].append(receipt)
            try:
                result = subprocess.run(command, cwd=cwd, env=environment, capture_output=True, timeout=55)
            except subprocess.TimeoutExpired as error:
                receipt["timedOut"] = True
                (out / (name + ".stdout.log")).write_bytes(error.stdout or b"")
                (out / (name + ".stderr.log")).write_bytes(error.stderr or b"")
                raise
            receipt["returnCode"] = result.returncode
            (out / (name + ".stdout.log")).write_bytes(result.stdout)
            (out / (name + ".stderr.log")).write_bytes(result.stderr)
            if result.returncode:
                raise ValueError(name + " failed; inspect retained logs")

        build.build(out / "source-package", recipe, capsules, fitted=fitted)
        tree = out / "plugin-source" / Path(wiring.PLUGIN).stem
        wiring.write_sources(tree, contract)
        wiring.validate_source_tree(tree, contract)
        package = out / "package"
        scripts = package / "Scripts"
        scripts.mkdir(parents=True)
        source = out / "source-package/Scripts/Source"
        for name in ("CLAWPhysicsData.psc", *build.SCRIPTS):
            command = [str(args.compiler.resolve()), "--game", "skyrim", "--async-read", "0", "--async-write", "0",
                       "--flags", str(args.flags.resolve()), "--output", str(scripts)]
            for folder in imports:
                command += ["--import", str(folder)]
            command.append(name)
            run(command, source, Path(name).stem)
            if not (scripts / (Path(name).stem + ".pex")).is_file():
                raise ValueError("Compiler returned success without its expected PEX")
        esp = package / wiring.PLUGIN
        run([str(args.spriggit.resolve()), "deserialize", "--InputPath", str(tree), "--OutputPath", str(esp)], ROOT, "spriggit-build")
        decoded = wiring.validate_plugin(esp, contract)
        (out / "plugin-binary-readback.json").write_text(json.dumps(decoded, indent=2) + "\n", encoding="utf-8")
        again = out / "roundtrip-source"
        run([str(args.spriggit.resolve()), "serialize", "--InputPath", str(esp), "--OutputPath", str(again),
             "--GameRelease", "SkyrimSE", "--PackageName", "Spriggit.Yaml", "--PackageVersion", "0.41.0"], ROOT, "spriggit-readback")
        roundtrip = out / "roundtrip" / wiring.PLUGIN
        roundtrip.parent.mkdir()
        run([str(args.spriggit.resolve()), "deserialize", "--InputPath", str(again), "--OutputPath", str(roundtrip)], ROOT, "spriggit-rebuild")
        if wiring.validate_plugin(roundtrip, contract) != decoded:
            raise ValueError("Quest/VMAD binary wiring changed after text round-trip")
        run([sys.executable, "-m", "unittest", "discover", "-s", "physics/tests", "-v"], ROOT.parent, "offline-tests")
        if inputs != input_hashes():
            raise ValueError("Physics sources changed while building; candidate is not a verified snapshot")
        build.verify_fitted_unchanged(fitted)
        shutil.copytree(source, scripts / "Source")
        shutil.copyfile(ROOT / "README.md", package / "README.md")
        wiring.validate_host_package(package, ("CLAWPhysicsData.psc", *build.SCRIPTS))
        report.update(status="built-offline-records-verified-runtime-pending", binaryWiringVerified=True, spriggitRoundtripVerified=True,
                      plugin=wiring.PLUGIN, questFormId="000800", actorAliasIds=list(wiring.ACTOR_IDS), playerAliasId=wiring.PLAYER_ID,
                      startGameEnabled=False, automaticAssignment=False, defaultIntegrationOptIn=False,
                      defaultProviderQualified=False, lifecycleDeliveryValidated=False,
                      motionConfigsBundled=False, separateMotionSource="source-package/SKSE/Plugins")
        report["fittedCapsules"] = None if fitted is None else fitted["input"]
        report["artifacts"] = [{"path": p.relative_to(package).as_posix(), "sha256": sha(p), "bytes": p.stat().st_size}
                               for p in sorted(package.rglob("*")) if p.is_file()]
        print(json.dumps({"status": report["status"], "package": str(package), "gameValidated": False}))
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        report.update(status="failed", error=str(error))
        print("CLAW physics host: " + str(error), file=sys.stderr)
        return 2
    finally:
        if owned:
            (owned / "physics-host-build.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
