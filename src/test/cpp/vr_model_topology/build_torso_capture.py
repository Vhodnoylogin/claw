"""Build the CLAW test-only torso extension to the pinned private R06 observer."""
from argparse import ArgumentParser
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from shutil import copyfile
import subprocess


HERE = Path(__file__).resolve().parent
R06_RECEIPT = "3637bdf0251903d7add1df144497424b2008a6cf9b3be6a083be151e419df4b4"
R06_COMMANDS = "ec2547ae1c73074fceecd8ecec5035e0a5aae8e127b17d1b523c7d005aaa2359"
SKEE_HEADER = "875410dd22230f76a014a6841004e7d346f5fa1c748cfff695f9f495234da277"
BUILD_ENVIRONMENT = "28131403690b16b8256b5d85c37cf88511c7e0330b23ac77664c2555787cc1c5"


def pin(path, expected=None):
    path = Path(path).resolve(strict=True)
    data = path.read_bytes()
    digest = sha256(data).hexdigest()
    if expected is not None and digest != expected:
        raise ValueError(f"Unexpected SHA-256 for {path}")
    return {"path": str(path), "bytes": len(data), "sha256": digest}


def verify(record):
    actual = pin(record["path"], record["sha256"])
    if actual["bytes"] != record["bytes"]:
        raise ValueError(f"Unexpected byte count for {record['path']}")
    return Path(actual["path"])


def replace(text, old, new):
    if text.count(old) != 1:
        raise ValueError("R06 patch anchor is missing or ambiguous: " + old.splitlines()[0])
    return text.replace(old, new)


def torso_overlay(source):
    source = replace(source, '#include "higgsinterface001.h"', '#include "higgsinterface001.h"\n#include "TorsoPose.h"')
    source = replace(source, "Json collect(Clock::time_point deadline,",
        r"""std::atomic<IBodyMorphInterface*> torsoMorphSource{};

std::string torsoBodyTri(const RE::BSGeometry& torso) {
    const auto* extra = netimmerse_cast<RE::NiStringExtraData*>(torso.GetExtraData("BODYTRI"));
    const auto path = extra ? bounded(extra->value) : std::string{};
    require(path == R"(actors\werewolfbeast\claw\firstperson\male\body.tri)",
            "Retained torso must use the admitted male BODYTRI route");
    return path;
}

Json collect(Clock::time_point deadline,""")
    source = replace(source, "    Json shapes = Json::array();", """    Json shapes = Json::array();
    RE::NiPointer<RE::BSGeometry> retainedTorso;""")
    source = replace(source, "        const auto& bound = object.worldBound;", """        const std::string_view shapeName = object.name;
        if (shapeName == "HEAD" || shapeName == "head") {
            require(!retainedTorso, "Ambiguous retained HEAD torso");
            retainedTorso.reset(geometry);
        }
        const auto& bound = object.worldBound;""")
    source = replace(source, "    std::size_t index{};", """    auto* morphs = torsoMorphSource.load();
    require(retainedTorso && morphs, "Retained HEAD torso or effective SKEE source unavailable");
    const auto bodyTri = torsoBodyTri(*retainedTorso);
    const auto measured = claw::vr_diagnostic::captureTorsoPose(*player, *root, *clone, *retainedTorso, *morphs, deadline);
    Json torsoBones = Json::object(), effectiveMorphs = Json::object();
    for (const auto& bone : measured.bones) torsoBones[bone.name] = {{"world", pose(bone.world)}};
    for (const auto& morph : measured.effectiveMorphs) effectiveMorphs[morph.name] = morph.value;
    require(torsoBodyTri(*retainedTorso) == bodyTri, "Retained torso BODYTRI changed during capture");
    std::size_t index{};""")
    source = replace(source, '            {"nearLeft", nearLeft}, {"renderedPixelsVerified", false}};',
        '''            {"nearLeft", nearLeft}, {"torsoCaptureVersion", 1}, {"torsoBodyTri", bodyTri},
            {"torsoBones", std::move(torsoBones)}, {"effectiveMorphs", std::move(effectiveMorphs)},
            {"renderedPixelsVerified", false}};''')
    source = replace(source, "        if (gate.loading()) return reply(nonce,", """        if (!torsoMorphSource.load()) return reply(nonce, "refused", diagnostics(), "torso_skee_unavailable").dump();
        if (gate.loading()) return reply(nonce,""")
    source = replace(source, "        auto* messaging = SKSE::GetMessagingInterface();", """        auto* messaging = SKSE::GetMessagingInterface();
        InterfaceExchangeMessage exchange;
        constexpr auto exchangeMessage = static_cast<std::uint32_t>(InterfaceExchangeMessage::kMessage_ExchangeInterface);
        if (messaging->Dispatch(exchangeMessage, &exchange, sizeof(exchange), "skee") && exchange.interfaceMap) {
            auto* bodyMorph = exchange.interfaceMap->QueryInterface("BodyMorph");
            if (bodyMorph && bodyMorph->GetVersion() >= IBodyMorphInterface::kPluginVersion4)
                torsoMorphSource.store(static_cast<IBodyMorphInterface*>(bodyMorph));
        }""")
    return source


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build(r06, skee, environment, output):
    receipt_pin = pin(r06 / "RECEIPT.json", R06_RECEIPT)
    commands_pin = pin(r06 / "commands.json", R06_COMMANDS)
    skee_pin = pin(skee, SKEE_HEADER)
    environment_pin = pin(environment, BUILD_ENVIRONMENT)
    base = read_json(Path(receipt_pin["path"]))
    source_files = [verify(row) for row in base["sources"]]
    original = next(path for path in source_files if path.name == "Plugin.cpp")
    header = pin(HERE / "TorsoPose.h")
    pex = verify(base["pex"])
    dependencies = read_json(verify(base["referenceDependencies"]))["files"]
    trusted = {Path(name).resolve(): digest for name, digest in dependencies.items()}
    for row in base["inputs"]:
        trusted[verify(row)] = row["sha256"]
    trusted[Path(skee_pin["path"])] = skee_pin["sha256"]
    trusted[Path(header["path"])] = header["sha256"]

    recipe = read_json(Path(commands_pin["path"]))
    baseline_compile = next(command for command in recipe if "/c" in command)
    baseline_link = next(command for command in recipe if Path(command[0]).name.casefold() == "link.exe")
    compiler, linker = verify(base["cl"]), verify(base["link"])
    if (Path(baseline_compile[0]).resolve(), Path(baseline_link[0]).resolve()) != (compiler, linker):
        raise ValueError("R06 tool paths differ from the sealed compiler and linker")
    for argument in baseline_link[1:]:
        library = Path(argument)
        if library.is_absolute() and library.suffix.casefold() == ".lib":
            pin(library, trusted[library.resolve()])

    output = output.resolve()
    output.mkdir()
    source = output / "Plugin.cpp"
    source.write_bytes(torso_overlay(original.read_text(encoding="utf-8")).encode("utf-8"))
    obj = output / "Plugin.obj"
    dll = output / "CLAWVRModelTopology.dll"
    depfile = output / "compiler-dependencies.json"
    compile_args = baseline_compile[:baseline_compile.index("/sourceDependencies")]
    compile_args = [arg for arg in compile_args
                    if arg != "/WX-" and not arg.casefold().startswith("/fo") and not arg.casefold().endswith(".cpp")]
    compile_args.extend(("/WX", "/I" + str(original.parent), "/I" + str(HERE), "/external:I", str(skee.resolve().parent),
                         "/Fo" + str(obj), str(source), "/sourceDependencies", str(depfile)))
    link_args = [arg for arg in baseline_link if not arg.casefold().endswith(".obj")
                 and not arg.casefold().startswith(("/out:", "/pdb:", "/implib:"))]
    link_args.extend(("/OUT:" + str(dll), "/IMPLIB:" + str(output / "CLAWVRModelTopology.lib"), str(obj)))

    env = os.environ.copy()
    startup = subprocess.run(["cmd.exe", "/d", "/c", environment_pin["path"]], capture_output=True,
                             text=True, check=True)
    for line in startup.stdout.splitlines():
        key, separator, value = line.partition("=")
        if separator and key.upper() in {"PATH", "INCLUDE", "LIB", "LIBPATH", "VCTOOLSINSTALLDIR", "WINDOWSSDKDIR"}:
            env[key] = value
    stages = []

    def run(name, command):
        result = subprocess.run(command, cwd=output, env=env, capture_output=True, text=True)
        log = output / (name + ".log")
        log.write_text(result.stdout + result.stderr, encoding="utf-8")
        if result.returncode:
            raise RuntimeError(f"{name} failed ({result.returncode}). See {log}")
        stages.append({"command": command, "exitCode": result.returncode, "log": pin(log)})

    run("compile", compile_args)
    observed = []
    for name in read_json(depfile)["Data"]["Includes"]:
        path = Path(name).resolve(strict=True)
        observed.append(pin(path, trusted[path]))
    run("link", link_args)
    run("exports", [str(linker.with_name("dumpbin.exe")), "/exports", str(dll)])
    exports = (output / "exports.log").read_text(encoding="utf-8")
    if not all(name in exports for name in ("SKSEPlugin_Query", "SKSEPlugin_Load")):
        raise ValueError("Missing legacy Skyrim VR loader exports")
    installed_pex = output / pex.name
    copyfile(pex, installed_pex)
    report = {"utc": datetime.now(timezone.utc).isoformat(), "baseline": receipt_pin,
              "baselineCommands": commands_pin, "environment": environment_pin, "builder": pin(Path(__file__)),
              "source": pin(source), "torsoPose": header, "skee": skee_pin, "includes": observed,
              "dll": pin(dll), "pex": pin(installed_pex, base["pex"]["sha256"]), "stages": stages,
              "schema": "claw-vr-vrik-world-avatar/1", "torsoCaptureVersion": 1, "runtimeChecked": False}
    (output / "RECEIPT.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report["dll"]


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--r06", type=Path, required=True, help="Sealed native-r06 build directory")
    parser.add_argument("--skee", type=Path, required=True, help="Pinned external RaceMenu IPluginInterface.h")
    parser.add_argument("--environment", type=Path, required=True, help="Retained MSVC capture-environment.cmd")
    parser.add_argument("--out", type=Path, required=True, help="New external build directory")
    args = parser.parse_args()
    print(json.dumps(build(args.r06, args.skee, args.environment, args.out), indent=2))
