"""Build the private player callback witness using the sealed VR compiler recipe."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess


SOURCE = Path(__file__).resolve().parent
MODULE = "CLAWVRPlayerCBPCEvents"
BASE_MODULE = "CLAWVRCBPCEvents"
BASE_RECEIPT = "06a8ff3492fe3dee87637e3d4994e0d8951c605d107740d6aa21babe76195643"
BASE_COMMANDS = "ab555f3b770d41cc7353b60371f8fa2d8a76411d1aa25701dde6ea5d2494758c"


def pin(path, expected=None):
    data = path.read_bytes()
    digest = sha256(data).hexdigest()
    if expected is not None and digest != expected:
        raise ValueError(f"Unexpected input bytes: {path}")
    return {"path": str(path), "sha256": digest, "bytes": len(data)}


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build(base, out):
    base, out = base.resolve(strict=True), out.resolve()
    baseline = pin(base / "RECEIPT.json", BASE_RECEIPT)
    recipe = pin(base / "commands.json", BASE_COMMANDS)
    receipt, commands = read(base / "RECEIPT.json"), read(base / "commands.json")
    paths = ("Plugin.cpp", "Window.h", "WindowTests.cpp", "PlayerSubject.h", MODULE + ".psc", "build_player.py")
    source_pins = [pin(SOURCE / name) for name in paths]
    include = SOURCE.parents[3] / "src/main/cpp/include"
    product = [pin(include / "claw" / name) for name in ("RuntimeSupport.h", "WorldStartPolicy.h", "PhysicsContactRoute.h")]
    retained = receipt["earlyTools"] + receipt["linkedRetainedLibraries"] + [receipt["papyrusCompiler"]]
    shell = next(row for row in receipt["referenceInputs"] if Path(row["path"]).suffix == ".cmd")
    for row in retained + [shell]:
        pin(Path(row["path"]), row["sha256"])
    old_source = Path(next(row["path"] for row in receipt["sources"] if Path(row["path"]).name == "Plugin.cpp")).parent
    old_out = Path(receipt["commands"]["path"]).parent
    old_product = next(Path(arg[2:]) for arg in commands[2] if arg.startswith("/I") and "claw\\src" in arg)
    substitutions = {str(old_out): str(out), str(old_source): str(SOURCE), str(old_product): str(include), BASE_MODULE: MODULE}
    for command in commands:
        for index, arg in enumerate(command):
            for old, new in substitutions.items():
                arg = arg.replace(old, new)
            command[index] = arg
    commands[2].append("/DCLAW_CBPC_PLAYER_WITNESS=1")
    env = os.environ.copy()
    startup = subprocess.run(["cmd.exe", "/d", "/c", shell["path"]], capture_output=True, text=True, check=True)
    for line in startup.stdout.splitlines():
        key, sep, value = line.partition("=")
        if sep and key.upper() in {"PATH", "INCLUDE", "LIB", "LIBPATH", "VCTOOLSINSTALLDIR", "WINDOWSSDKDIR"}:
            env[key] = value
    out.mkdir()
    stages = []
    for name, command in zip(("pure-compile", "pure-tests", "compile", "link", "binary", "papyrus"), commands, strict=True):
        result = subprocess.run(command, cwd=out, env=env, capture_output=True, text=True)
        log = out / (name + ".log")
        log.write_text(result.stdout + result.stderr, encoding="utf-8")
        if result.returncode != 0:
            raise RuntimeError(f"{name} failed with {result.returncode}. Read {log}")
        stages.append({"command": command, "exitCode": result.returncode, "log": pin(log)})
    headers = {Path(row["path"]).resolve(): row["sha256"] for row in receipt["compilerHeaders"] + source_pins + product}
    observed = [pin(Path(name).resolve(), headers[Path(name).resolve()])
                for name in read(out / "compiler-dependencies.json")["Data"]["Includes"]]
    dump = (out / "binary.log").read_text(encoding="utf-8")
    if not all(value in dump for value in ("8664 machine (x64)", "SKSEPlugin_Query", "SKSEPlugin_Load")):
        raise ValueError("Missing Skyrim VR loader exports")
    record = {"schema": "claw-vr-player-cbpc-witness-build/1", "runtimeChecked": False, "module": MODULE,
              "baseline": baseline, "recipe": recipe, "sources": source_pins, "headers": observed,
              "stages": stages, "dll": pin(out / (MODULE + ".dll")), "pex": pin(out / (MODULE + ".pex"))}
    (out / "RECEIPT.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record["dll"], record["pex"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True, help="Retained NPC witness build-03")
    parser.add_argument("--out", type=Path, required=True, help="Fresh external build directory")
    args = parser.parse_args()
    print(json.dumps(build(args.baseline, args.out), indent=2))
